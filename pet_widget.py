import logging
import time
import random
from enum import Enum, auto

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QWidget, QLabel

from config import (
    DIRECTION_MIN_SPEED,
    GRAVITY,
    HARD_FALL_THRESHOLD,
    IDLE_WAIT_MAX,
    IDLE_WAIT_MIN,
    LANDING_SLOWDOWN_DISTANCE,
    LANDING_SLOWDOWN_SPEED,
    MAX_FALL_SPEED,
    SPEED_EMA_ALPHA,
    SPEED_START,
    SPEED_STOP,
    SPEED_ZERO_MS,
    WALK_DURATION_MAX,
    WALK_DURATION_MIN,
    WALK_SPEED,
    BUBBLE_DEFAULT_DURATION,
    BUBBLE_MAX_WIDTH,
    BUBBLE_OFFSET_Y,
    REACTIONS_SOUND_ENABLED,
    REACTIONS_TEXT_ENABLED,
    IDLE_EVENT_WEIGHTS,
)

from render import Animation, DragAnimSet
from sound_player import SoundPlayer
from reactions import ReactionBook


log = logging.getLogger(__name__)


class PetState(Enum):
    """ Общее состояние питомца: покой, перетаскивание, падение, приземление и тд."""

    IDLE = auto()
    WALK = auto()
    DRAG = auto()
    KISS = auto()
    FALL = auto()
    LAND = auto()
    MUSIC = auto()
    WATCHING = auto()


def _virtual_desktop_geometry() -> QRect:
    """ Объединение пространства нескольких мониторов в одну рабочее пространство """
    
    screens = QApplication.screens()
    combined_rect = screens[0].geometry()
    for screen in screens[1:]:
        combined_rect = combined_rect.united(screen.geometry())
    return combined_rect


class PetWidget(QWidget):
    """ Прозрачное окно с питомцем. Управляет состояниями, вводом и физикой """

    def __init__(
            self,
            idle: Animation,
            drag_right: DragAnimSet,
            drag_left: DragAnimSet,
            walk_right: Animation,
            walk_left: Animation,
            falling: Animation,
            landing_normal: Animation,
            landing_magic: Animation,
            music: Animation,
            video: Animation,
            kiss: Animation,
            reactions: ReactionBook,
            sounds: SoundPlayer,
            tick_ms: int = 16,
            scale: float = 1.0,
            start_position: str = 'bottom-center',
            span_all_screens: bool = True,
    ):
        super().__init__()

        assert scale > 0, f'scale должен быть > 0, получено {scale}'

        # Анимации
        self.idle_animation = idle
        self.falling_animation = falling
        self.landing_normal_animation = landing_normal
        self.landing_magic_animation = landing_magic
        self.drag_animation_sets = {1: drag_right, -1: drag_left}
        self.walk_animations = {1: walk_right, -1: walk_left}
        self.music_animation = music
        self.video_animation = video
        self.kiss_animation = kiss

        # Текущее состояние
        self.pet_state = PetState.IDLE
        self.active_animation = idle
        self.active_frame = idle.current

        # Размер спрайта на экране
        frame_width, frame_height = self.active_frame.size
        self.pet_render_size = QSize(
            round(frame_width * scale),
            round(frame_height * scale),
        )

        # Позиция питомца на экране
        self.pet_position = QPoint(0, 0)

        # Перетаскивание
        self.drag_moving = False
        self.drag_direction = 1
        self.grab_offset = QPoint()
        self.last_cursor_move_time = 0.0
        self.last_cursor_x = 0
        self.cursor_speed = 0.0

        # Падение
        self.fall_velocity = 0.0
        self.fall_is_hard = False
        self.fall_magic_active = False

        # Ходьба и IDLE планировщик
        self.walk_direction = 1
        self.walk_time_left = 0.0
        self.idle_wait_left = random.uniform(IDLE_WAIT_MIN, IDLE_WAIT_MAX)

        # Музыка и видео
        self.music_playing = False
        self.video_playing = False

        # Реакции
        self.reactions = reactions
        self.sounds = sounds

        # Облачко с репликами
        self.bubble = QLabel(self)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setStyleSheet("""
                   QLabel {
                       background-color: rgba(255, 255, 255, 235);
                       color: #222;
                       border: 1px solid #888;
                       border-radius: 12px;
                       padding: 8px 12px;
                       font-size: 14px;
                   }
               """)
        self.bubble.hide()
        self.bubble_visible = False
        self.bubble_queue: list[tuple[str, float]] = []
        self.bubble_hide_timer = QTimer(self)
        self.bubble_hide_timer.setSingleShot(True)
        self.bubble_hide_timer.timeout.connect(self._hide_bubble)

        # Окно
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # Окно на весь рабочий стол при наличии нескольких мониторов
        if span_all_screens:
            self.setGeometry(_virtual_desktop_geometry())
        else:
            self.setGeometry(QApplication.primaryScreen().availableGeometry())

        self._apply_start_position(start_position)
        self._update_mask()

        # Игровой цикл
        self.last_tick_time = time.perf_counter()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._on_tick)
        self.tick_timer.start(tick_ms)

    # Облачко и реакции
    def say(self, text: str, duration: float = BUBBLE_DEFAULT_DURATION) -> None:
        """ Показать реплику в облачке. Если что-то уже висит — в очередь """

        if self.bubble_visible:
            self.bubble_queue.append((text, duration))
            return
        self._show_bubble(text, duration)

    def react(self, process_name: str) -> None:
        """Реакция на смену активного процесса. Cooldown уже учтён в ReactionBook """

        if not self.reactions:
            return
        reaction = self.reactions.match(process_name)
        if reaction is None:
            return

        # Глобальные флаги — выключатель поверх всего.
        text = reaction.pick_text() if REACTIONS_TEXT_ENABLED else None
        sound = reaction.pick_sound() if REACTIONS_SOUND_ENABLED else None

        if text:
            self.say(text)
        if sound:
            self.sounds.play(sound)

        self.reactions.mark_fired(process_name)
        log.debug(f'Реакция на {process_name}: текст={text}, звук={sound}')

    def set_media_state(self, media_type: str, is_playing: bool) -> None:
        """ Реакция на смену медиа-состояния от MediaWatcher """

        want_music = (media_type == "music" and is_playing)
        want_video = (media_type == "video" and is_playing)

        # Если ничего не изменилось — выходим.
        if (want_music == self.music_playing
                and want_video == self.video_playing):
            return

        self.music_playing = want_music
        self.video_playing = want_video

        # Питомца не трогаем, если он занят перетаскиванием или падением.
        busy = self.pet_state in (PetState.DRAG, PetState.FALL, PetState.LAND, PetState.KISS)
        if busy:
            return

        if want_music:
            log.debug('Музыка заиграла: прослушивание')
            self.pet_state = PetState.MUSIC
            self._activate_animation(self.music_animation)
        elif want_video:
            log.debug('Видео заиграло: просмотр')
            self.pet_state = PetState.WATCHING
            self._activate_animation(self.video_animation)
        else:
            # Ничего не играет — возвращаемся в idle.
            if self.pet_state in (PetState.MUSIC, PetState.WATCHING):
                log.debug('Медиа закончилось: возврат в idle')
                self._enter_idle()

    def _enter_idle(self) -> None:
        """ Единая точка возврата в покой. Учитывает прослушивание музыки и видео """

        if self.music_playing:
            log.debug('Музыка играет: переход в прослушивание')
            self.pet_state = PetState.MUSIC
            self._activate_animation(self.music_animation)
            return

        if self.video_playing:
            log.debug('Видео играет: переход к просмотру')
            self.pet_state = PetState.WATCHING
            self._activate_animation(self.video_animation)
            return

        log.debug('Начало idle')
        self.pet_state = PetState.IDLE
        self.idle_wait_left = random.uniform(IDLE_WAIT_MIN, IDLE_WAIT_MAX)
        self._activate_animation(self.idle_animation)

    def _show_bubble(self, text: str, duration: float) -> None:
        """ Вывод окошка с репликой """

        self.bubble.setText(text)
        self.bubble.setFixedWidth(BUBBLE_MAX_WIDTH)
        self.bubble.adjustSize()
        self.bubble.show()
        self.bubble_visible = True
        self._reposition_bubble()
        self.bubble.raise_()
        self._update_mask()
        self.bubble_hide_timer.start(int(duration * 1000))

    def _hide_bubble(self) -> None:
        """ Удаление окошка с репликой по истечению времени """

        self.bubble.hide()
        self.bubble_visible = False
        self._update_mask()
        if self.bubble_queue:
            next_text, next_duration = self.bubble_queue.pop(0)
            self._show_bubble(next_text, next_duration)

    def _reposition_bubble(self) -> None:
        """ Ставит облачко над питомцем, не вылезая за края окна """

        bubble_width = self.bubble.width()
        bubble_height = self.bubble.height()
        pet_width = self.pet_render_size.width()
        pet_height = self.pet_render_size.height()

        x = self.pet_position.x() + pet_width // 2 - bubble_width // 2
        y = self.pet_position.y() - bubble_height - BUBBLE_OFFSET_Y

        # Не вылезать за левый/правый край окна.
        x = max(8, min(x, self.width() - bubble_width - 8))
        # Если сверху нет места — показать под питомцем.
        if y < 8:
            y = self.pet_position.y() + pet_height + BUBBLE_OFFSET_Y

        self.bubble.move(x, y)

    # Позиционирование и маска
    def _floor_top_y(self) -> int:
        """ Координата Y верхнего края питомца, при котором питомец расположен внизу экрана """

        return self.height() - self.pet_render_size.height()

    def _apply_start_position(self, mode: str) -> None:
        """ Располагает питомца в заданную стартовую позицию внутри окна """
        
        pet_width = self.pet_render_size.width()
        pet_height = self.pet_render_size.height()
        window_width = self.width()
        window_height = self.height()

        if mode == 'bottom-center':
            self.pet_position = QPoint(
                (window_width - pet_width) // 2,
                window_height - pet_height,
            )
        elif mode == 'bottom-right':
            self.pet_position = QPoint(
                window_width - pet_width,
                window_height - pet_height,
            )
        elif mode == 'bottom-left':
            self.pet_position = QPoint(
                0,
                window_height - pet_height,
            )
        else:
            raise ValueError(f'Неизвестная стартовая позиция: {mode!r}')

    def _update_mask(self) -> None:
        """
        Обновляет маску окна по рамке питомца.
        При перетаскивании маска не обновляется за ненадобностью, затем снова устанавливается при окончании анимации.
        """

        if self.pet_state is PetState.DRAG:
            return

        mask = QRegion(
            self.pet_position.x(),
            self.pet_position.y(),
            self.pet_render_size.width(),
            self.pet_render_size.height(),
        )

        if self.bubble_visible:
            mask = mask.united(QRegion(self.bubble.geometry()))

        self.setMask(mask)

    # Управление анимацией
    def _activate_animation(self, animation: Animation) -> None:
        """ Переключает активную анимацию и сбрасывает её в начало """
        
        animation.reset()
        self.active_animation = animation

    # Жизненный цикл
    def shutdown(self) -> None:
        """ Останавливает таймер, закрывает окно, завершает приложение """
        
        log.debug('Выход через контекстное меню')
        self.tick_timer.stop()
        self.close()
        QApplication.instance().quit()

    # Обработка событий мыши
    def mousePressEvent(self, event):
        """ Начало перетаскивания: запоминаем точку захвата, снимаем маску """
        
        if event.button() != Qt.MouseButton.LeftButton:
            return

        log.debug('Стадия перетаскивания')

        # Хватание отменяет падение/приземление, если они были в процессе.
        self.fall_velocity = 0.0
        self.pet_state = PetState.DRAG
        self.drag_moving = False

        click_position = event.position().toPoint()
        self.grab_offset = click_position - self.pet_position

        # На время перетаскивания маску удаляется целиком
        self.clearMask()

        self.last_cursor_move_time = time.perf_counter()
        self.last_cursor_x = event.globalPosition().toPoint().x()
        self.cursor_speed = 0.0

        drag_set = self.drag_animation_sets[self.drag_direction]
        self._activate_animation(drag_set.still)
        event.accept()

    def mouseMoveEvent(self, event):
        """ Двигает питомца вслед за курсором, обновляет скорость и направление """
        
        if self.pet_state is not PetState.DRAG:
            return

        current_time = time.perf_counter()
        click_position = event.position().toPoint()
        new_global_x = event.globalPosition().toPoint().x()
        delta_time = current_time - self.last_cursor_move_time
        delta_x = new_global_x - self.last_cursor_x

        if delta_time > 0:
            horizontal_velocity = delta_x / delta_time
            self.cursor_speed = (
                (1 - SPEED_EMA_ALPHA) * self.cursor_speed
                + SPEED_EMA_ALPHA * abs(horizontal_velocity)
            )

            if abs(horizontal_velocity) > DIRECTION_MIN_SPEED:
                new_direction = 1 if horizontal_velocity > 0 else -1
                if new_direction != self.drag_direction:
                    self.drag_direction = new_direction
                    # Если движемся — сразу переключаемся на цикл нового направления
                    if self.drag_moving:
                        drag_set = self.drag_animation_sets[self.drag_direction]
                        self._activate_animation(drag_set.cycle)

        self.last_cursor_move_time = current_time
        self.last_cursor_x = new_global_x

        # Спрайт двигается внутри окна без маски
        self.pet_position = click_position - self.grab_offset
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        """ Завершение перетаскивания: установка маски, запуск падения """
        
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.pet_state is not PetState.DRAG:
            return
        self._end_drag()
        self._update_mask()
        event.accept()

    def contextMenuEvent(self, event):
        """ Вывод контекстного меню через правый клик мышки """
        
        menu = QMenu(self)
        quit_action = QAction('Выход', self)
        quit_action.triggered.connect(self.shutdown)
        menu.addAction(quit_action)
        menu.exec(event.globalPos())
        event.accept()

    # Логика перетаскивания
    def _end_drag(self) -> None:
        """ Отпустили мышь. Если питомец в воздухе — падает, иначе в idle """

        self.cursor_speed = 0.0
        self.drag_moving = False

        if self.pet_position.y() < self._floor_top_y():
            fall_height = self._floor_top_y() - self.pet_position.y()
            self.fall_is_hard = fall_height > HARD_FALL_THRESHOLD
            self.fall_magic_active = False
            log.debug(f'Конец перетаскивания: падение, высота {fall_height}, '
                      f'падение {"магическое" if self.fall_is_hard else "обычное"}')
            self.pet_state = PetState.FALL
            self.fall_velocity = 0.0
            self._activate_animation(self.falling_animation)
        else:
            log.debug('Конец перетаскивания: возврат в idle')
            self._enter_idle()

    def _update_drag(self, delta_time: float) -> None:
        """ Переключает фазы перетаскивания по скорости курсора и завершению анимаций """

        if (time.perf_counter() - self.last_cursor_move_time) * 1000 > SPEED_ZERO_MS:
            self.cursor_speed = 0.0

        moving = self.cursor_speed > SPEED_STOP

        if moving == self.drag_moving:
            return

        self.drag_moving = moving
        drag_set = self.drag_animation_sets[self.drag_direction]

        if moving:
            log.debug('Перетаскивание')
            self._activate_animation(drag_set.cycle)
        else:
            log.debug('Движение')
            self._activate_animation(drag_set.still)

    # Логика падения и приземления
    def _update_fall(self, delta_time: float) -> None:
        """ Применяет ускорение для падения, двигает питомца, проверяет, достиг ли питомец пола """

        self.fall_velocity = min(
            self.fall_velocity + GRAVITY * delta_time,
            MAX_FALL_SPEED,
        )

        floor_y = self._floor_top_y()
        distance_to_floor = floor_y - self.pet_position.y()

        # Зона магического торможения: только для высокого падения.
        in_slowdown_zone = (
                self.fall_is_hard
                and distance_to_floor < LANDING_SLOWDOWN_DISTANCE
        )

        if in_slowdown_zone:
            self.fall_velocity = LANDING_SLOWDOWN_SPEED
            if not self.fall_magic_active:
                self.fall_magic_active = True
                log.debug('Магическое торможение включено')

        new_y = self.pet_position.y() + self.fall_velocity * delta_time

        if new_y >= floor_y:
            self.pet_position.setY(floor_y)
            self.fall_velocity = 0.0
            self.pet_state = PetState.LAND
            if self.fall_is_hard:
                log.debug('Падение завершено: магическое приземление')
                self._activate_animation(self.landing_magic_animation)
            else:
                log.debug('Падение завершено: обычное приземление')
                self._activate_animation(self.landing_normal_animation)
        else:
            self.pet_position.setY(int(new_y))

        self._update_mask()
        self.update()

    def _update_land(self, delta_time: float) -> None:
        """ Ожидание окончания анимации приземления, затем возвращает idle """

        if self.active_animation.finished:
            log.debug('Приземление завершено: возврат в idle')
            self._enter_idle()

    def _start_walk(self) -> None:
        """ Выбирает направление и длительность, запускает ходьбу """

        pet_width = self.pet_render_size.width()
        current_x = self.pet_position.x()
        max_x = self.width() - pet_width

        # Идём в сторону от ближнего края — больше места для прогулки.
        distance_to_left = current_x
        distance_to_right = max_x - current_x
        # Минимальное расстояние, которое питомец пройдёт за самую короткую прогулку.
        # Если до края меньше, то гулять туда смысла нет.
        min_walk_distance = WALK_SPEED * WALK_DURATION_MIN

        left_has_room = distance_to_left >= min_walk_distance
        right_has_room = distance_to_right >= min_walk_distance

        if left_has_room and not right_has_room:
            direction = -1
        elif right_has_room and not left_has_room:
            direction = 1
        else:
            # Обе стороны подходят
            direction = random.choice([1, -1])

        self.walk_direction = direction
        self.walk_time_left = random.uniform(WALK_DURATION_MIN, WALK_DURATION_MAX)
        self.pet_state = PetState.WALK
        self._activate_animation(self.walk_animations[direction])
        log.debug(f'Начало ходьбы: {"вправо" if direction > 0 else "влево"}')

    def _start_kiss(self) -> None:
        """ Запускает анимацию поцелуя — событие в idle """

        log.debug('Событие idle: поцелуй')
        self.pet_state = PetState.KISS
        self._activate_animation(self.kiss_animation)

    def _start_idle_event(self) -> None:
        """ Выбирает случайное событие в idle по весам из config """

        events = list(IDLE_EVENT_WEIGHTS.keys())
        weights = list(IDLE_EVENT_WEIGHTS.values())
        event = random.choices(events, weights=weights, k=1)[0]

        if event == 'walk':
            self._start_walk()
        elif event == 'kiss':
            self._start_kiss()
        else:
            log.warning('Неизвестное idle-событие: %s', event)

    def _update_idle(self, delta_time: float) -> None:
        """ Планировщик idle-событий. Пока — только ходьба """

        if self.music_playing or self.video_playing:
            self._enter_idle()
            return

        self.idle_wait_left -= delta_time
        if self.idle_wait_left <= 0:
            self._start_idle_event()

    def _update_walk(self, delta_time: float) -> None:
        """ Двигает питомца, следит за краями экрана и таймером ходьбы """

        self.walk_time_left -= delta_time

        pet_width = self.pet_render_size.width()
        min_x = 0
        max_x = self.width() - pet_width

        new_x = self.pet_position.x() + WALK_SPEED * self.walk_direction * delta_time

        if new_x <= min_x or new_x >= max_x or self.walk_time_left <= 0:
            new_x = max(min_x, min(max_x, new_x))
            self.pet_position.setX(int(new_x))
            self._update_mask()
            self.update()
            log.info('Ходьба завершена')
            self._enter_idle()
            return

        self.pet_position.setX(int(new_x))
        self._update_mask()
        self.update()

    def _update_kiss(self, _delta_time: float) -> None:
        """ Ждёт окончания анимации поцелуя, затем возвращает в idle """

        if self.active_animation.finished:
            log.debug('Поцелуй завершён: возврат в idle')
            self._enter_idle()

    # Игровой цикл
    def _on_tick(self) -> None:
        """ Вызывается таймером ~60 раз в секунду. Обновляет состояние """

        current_time = time.perf_counter()
        delta_time = current_time - self.last_tick_time
        self.last_tick_time = current_time

        if self.pet_state is PetState.DRAG:
            self._update_drag(delta_time)
        elif self.pet_state is PetState.FALL:
            self._update_fall(delta_time)
        elif self.pet_state is PetState.LAND:
            self._update_land(delta_time)
        elif self.pet_state is PetState.WALK:
            self._update_walk(delta_time)
        elif self.pet_state is PetState.KISS:
            self._update_kiss(delta_time)
        elif self.pet_state is PetState.MUSIC:
            pass
        elif self.pet_state is PetState.WATCHING:
            pass
        elif self.pet_state is PetState.IDLE:
            self._update_idle(delta_time)

        if self.bubble_visible:
            self._reposition_bubble()

        self.active_animation.update(delta_time)
        new_frame = self.active_animation.current
        if new_frame is not self.active_frame:
            self.active_frame = new_frame
            self.update()

    # Отрисовка
    def paintEvent(self, _event):
        """ Рисует текущий кадр питомца в его прямоугольнике внутри окна """

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        target_rect = QRect(self.pet_position, self.pet_render_size)
        painter.drawImage(target_rect, self.active_frame.qimage)
