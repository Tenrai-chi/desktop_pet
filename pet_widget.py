""" Модуль виджета питомца (главное окно, состояния, физика) """

import logging
import random
import time
from enum import Enum, auto

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent, QPainter, QPaintEvent, QRegion
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QWidget

from config import (
    BUBBLE_DEFAULT_DURATION,
    BUBBLE_MAX_WIDTH,
    BUBBLE_OFFSET_Y,
    DIRECTION_MIN_SPEED,
    GRAVITY,
    HARD_FALL_THRESHOLD,
    IDLE_EVENT_WEIGHTS,
    IDLE_WAIT_MAX,
    IDLE_WAIT_MIN,
    LANDING_SLOWDOWN_DISTANCE,
    LANDING_SLOWDOWN_SPEED,
    MAX_FALL_SPEED,
    REACTIONS_SOUND_ENABLED,
    REACTIONS_TEXT_ENABLED,
    SPEED_EMA_ALPHA,
    SPEED_STOP,
    SPEED_ZERO_MS,
    VIDEO_SITES,
    VOICE_LISTEN_DURATION,
    WALK_DURATION_MAX,
    WALK_DURATION_MIN,
    WALK_SPEED,
)
from loads_media import PetAnimations
from reactions import ReactionBook
from render import Animation
from sound_player import SoundPlayer

log = logging.getLogger(__name__)


class PetState(Enum):
    """ Общее состояние питомца """

    APPEARING = auto()
    IDLE = auto()
    WALK = auto()
    DRAG = auto()
    KISS = auto()
    POTION = auto()
    FALL = auto()
    LAND = auto()
    MUSIC = auto()
    WATCHING = auto()


def _virtual_desktop_geometry() -> QRect:
    """
    Возвращает объединенное пространство всех мониторов.

    Returns:
        Общий прямоугольник (QRect) всех экранов.
    """
    
    screens = QApplication.screens()
    combined_rect = screens[0].geometry()
    for screen in screens[1:]:
        combined_rect = combined_rect.united(screen.geometry())
    return combined_rect


def _single_screen_geometry(index: int) -> QRect:
    """
    Возвращает рабочую область одного монитора по индексу.
    Если индекс вне диапазона — возвращает основной монитор
    и пишет warning в лог (чтобы приложение не падало).

    Args:
        index: Индекс монитора.

    Returns:
        Рабочая область выбранного монитора (QRect).
    """

    screens = QApplication.screens()
    if 0 <= index < len(screens):
        return screens[index].availableGeometry()
    log.warning(
        f'Неверный параметр индекса монитора {index}, возможный индекс от 1 до {len(screens)}'
    )
    return QApplication.primaryScreen().availableGeometry()


class PetWidget(QWidget):
    """ Прозрачное окно с питомцем. Управляет состояниями, вводом и физикой """

    def __init__(
            self,
            animations: PetAnimations,
            reactions: ReactionBook,
            sounds: SoundPlayer,
            tick_ms: int = 16,
            scale: float = 1.0,
            start_position: str = 'center',
            use_all_screens: bool = True,
            monitor_index: int = 0,
    ) -> None:
        """
        Инициализирует виджет питомца.
        Args:
            animations: Набор всех анимаций.
            reactions: Книга реакций на приложения и сайты.
            sounds: Плеер звуков.
            tick_ms: Интервал игрового цикла в миллисекундах.
            scale: Масштаб отображения питомца.
            start_position: Стартовая позиция ('center', 'left', 'right').
            use_all_screens: Использовать ли все мониторы.
            monitor_index: Индекс монитора (если use_all_screens=False).
        """

        super().__init__()

        assert scale > 0, f'scale должен быть > 0, получено {scale}'

        # Голосовые команды
        self.voice_listener = None
        self.command_handler = None

        # Анимации
        self.idle_animation = animations.idle
        self.falling_animation = animations.falling
        self.landing_normal_animation = animations.landing_normal
        self.landing_magic_animation = animations.landing_magic
        self.drag_animation_sets = {1: animations.drag_right, -1: animations.drag_left}
        self.walk_animations = {1: animations.walk_right, -1: animations.walk_left}
        self.music_animation = animations.music
        self.video_animation = animations.video
        self.kiss_animation = animations.kiss
        self.potion_animation = animations.potion

        # Стартовое состояние
        self._appear_side = {
            'left': 'left',
            'right': 'right',
            'center': 'center',
        }[start_position]
        self._appear_elapsed = 0.0
        self.pet_state = PetState.APPEARING
        self.active_animation = getattr(animations, f'appear_{self._appear_side}')
        self.active_frame = animations.idle.current

        # Размер спрайта на экране
        frame_width, frame_height = self.active_frame.size
        self.pet_render_size = QSize(
            round(frame_width * scale / 2),
            round(frame_height * scale / 2),
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
        self._walk_from_appear = False
        self._appear_walk_elapsed = 0.0
        self.idle_wait_left = random.uniform(IDLE_WAIT_MIN, IDLE_WAIT_MAX)

        # Музыка и видео
        self.music_playing = False
        self.video_playing = False

        # Браузер
        self.browser_site = ''
        self._raw_media_type = 'unknown'
        self._raw_is_playing = False

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
        if use_all_screens:
            self.setGeometry(_virtual_desktop_geometry())
        else:
            self.setGeometry(_single_screen_geometry(monitor_index))

        self._apply_start_position(start_position)
        self._update_mask()

        # Игровой цикл
        self.last_tick_time = time.perf_counter()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._on_tick)
        self.tick_timer.start(tick_ms)

    # ---- Облачко и реакции ----
    def say(self, text: str, duration: float = BUBBLE_DEFAULT_DURATION) -> None:
        """
        Показывает реплику в облачке (или ставит в очередь).

        Args:
            text: Текст реплики.
            duration: Время отображения в секундах.
        """

        if self.bubble_visible:
            self.bubble_queue.append((text, duration))
            return
        self._show_bubble(text, duration)

    def set_voice_modules(self, listener, handler) -> None:
        """
        Внедряет голосовые модули (слушатель и обработчик команд).

        Args:
            listener: Экземпляр VoiceListener.
            handler: Экземпляр CommandHandler.
        """

        self.voice_listener = listener
        self.command_handler = handler

    def _start_voice_listening(self) -> None:
        """ Запускает прослушивание микрофона (если питомец свободен) """

        if not self.voice_listener:
            return
        if self.pet_state in (PetState.DRAG, PetState.FALL, PetState.LAND, PetState.KISS):
            return

        self.say('Слушаю...')
        # Длительность из настроек
        from config import VOICE_LISTEN_DURATION
        self.voice_listener.listen_once(duration=VOICE_LISTEN_DURATION)

    def on_voice_failed(self, reason: str) -> None:
        """
        Обрабатывает неудачную попытку распознавания речи.

        Args:
            reason: Причина ошибки.
        """

        log.debug(f'Голосовая команда не выполнена: {reason}')
        self.say(reason)

    def on_voice_command(self, text: str) -> None:
        """
        Обрабатывает успешно распознанную команду.

        Args:
            text: Распознанный текст.
        """

        log.debug(f'Голосовая команда: {text}')
        if not self.command_handler:
            return

        reply, action = self.command_handler.execute(text)
        if reply:
            self.say(reply)

        if action == 'exit':
            QTimer.singleShot(1500, self.shutdown)

    def react(self, process_name: str) -> None:
        """
        Реакция на смену активного процесса.

        Args:
            process_name: Имя исполняемого файла процесса.
        """

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
        """
        Сигнал от MediaWatcher (сохраняет сырое состояние).

        Args:
            media_type: Тип медиа ('music', 'video' и т.д.).
            is_playing: Играет ли сейчас.
        """

        self._raw_media_type = media_type
        self._raw_is_playing = is_playing
        self._recompute_media_state()

    def set_browser_site(self, site: str) -> None:
        """
        Сигнал от WindowWatcher (активный сайт в браузере).

        Args:
            site: Ключ активного сайта.
        """

        if site == self.browser_site:
            return
        self.browser_site = site
        log.debug('Браузер: сайт=%r', site)

        # Пересчитываем медиа — вдруг YouTube, и надо сменить WATCHING/MUSIC
        self._recompute_media_state()

        # Реакция на открытие сайта
        if site:
            self._react_to_site(site)

    def _react_to_site(self, site: str) -> None:
        """
        Показывает реплику при открытии известного сайта.

        Args:
            site: Ключ сайта.
        """

        reaction = self.reactions.match_site(site) if self.reactions else None
        if reaction is None:
            return

        text = reaction.pick_text() if REACTIONS_TEXT_ENABLED else None
        sound = reaction.pick_sound() if REACTIONS_SOUND_ENABLED else None

        if text:
            self.say(text)
        if sound:
            self.sounds.play(sound)

        self.reactions.mark_site_fired(site)
        log.debug('Реакция на сайт %s: text=%r, sound=%r', site, text, sound)

    def _recompute_media_state(self) -> None:
        """ Пересчитывает эффективный тип медиа с учётом активного сайта """

        media_type = self._raw_media_type
        is_playing = self._raw_is_playing

        # YouTube/Twitch: даже если GSMTC вернул music — считаем видео
        if is_playing and self.browser_site in VIDEO_SITES:
            media_type = 'video'

        want_music = (media_type == 'music' and is_playing)
        want_video = (media_type == 'video' and is_playing)

        if (want_music == self.music_playing
                and want_video == self.video_playing):
            return

        self.music_playing = want_music
        self.video_playing = want_video

        busy = self.pet_state in (
            PetState.APPEARING,
            PetState.DRAG,
            PetState.FALL,
            PetState.LAND,
            PetState.KISS,
            PetState.POTION,
        )
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
        """
        Выводит окошко с репликой.

        Args:
            text: Текст реплики.
            duration: Время отображения в секундах.
        """

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

    # ---- Позиционирование и маска ----
    def _floor_top_y(self) -> int:
        """
        Координата Y верхнего края питомца (на уровне пола).

        Returns:
            Y-координата пола.
        """

        return self.height() - self.pet_render_size.height()

    def _clamp_pet_position(self) -> None:
        """ Возвращает питомца в допустимые границы экрана """

        pet_width = self.pet_render_size.width()
        min_x = 0
        max_x = self.width() - pet_width
        floor_y = self._floor_top_y()

        old_x, old_y = self.pet_position.x(), self.pet_position.y()
        new_x = max(min_x, min(max_x, old_x))
        new_y = min(old_y, floor_y)

        if new_x == old_x and new_y == old_y:
            return

        self.pet_position = QPoint(new_x, new_y)
        self._update_mask()
        self.update()
        log.debug(
            f'Питомец вытолкнут в границы экрана: ({old_x}, {old_y}) -> ({new_x}, {new_y})'
        )

    def _apply_start_position(self, mode: str) -> None:
        """
        Располагает питомца в стартовую позицию внутри окна.

        Args:
            mode: Позиция ('center', 'left', 'right').
        """
        
        pet_width = self.pet_render_size.width()
        pet_height = self.pet_render_size.height()
        window_width = self.width()
        window_height = self.height()

        if mode == 'center':
            self.pet_position = QPoint(
                (window_width - pet_width) // 2,
                window_height - pet_height,
            )
        elif mode == 'right':
            self.pet_position = QPoint(
                window_width - pet_width,
                window_height - pet_height,
            )
        elif mode == 'left':
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

    def _activate_animation(self, animation: Animation) -> None:
        """
        Переключает активную анимацию и сбрасывает её в начало.

        Args:
            animation: Новая анимация.
        """
        
        animation.reset()
        self.active_animation = animation

    # Жизненный цикл
    def shutdown(self) -> None:
        """ Останавливает таймер, закрывает окно, завершает приложение """
        
        log.debug('Выход через контекстное меню')
        self.tick_timer.stop()
        self.close()
        QApplication.instance().quit()

    # ---- Обработка событий мыши ----
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Обрабатывает нажатие кнопок мыши (драг или активация голоса).

        Args:
            event: Событие мыши.
        """

        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_voice_listening()
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        log.debug('Стадия перетаскивания')

        # Хватание отменяет падение/приземление, если они были в процессе.
        self.fall_velocity = 0.0
        self.pet_state = PetState.DRAG
        self.drag_moving = False
        self._walk_from_appear = False
        self._appear_walk_elapsed = 0.0

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

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Двигает питомца вслед за курсором, обновляет скорость и направление.

        Args:
            event: Событие движения мыши.
        """
        
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Завершает перетаскивание: устанавливает маску, запускает падение.

        Args:
            event: Событие мыши.
        """
        
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.pet_state is not PetState.DRAG:
            return
        self._end_drag()
        self._update_mask()
        event.accept()

    def contextMenuEvent(self, event) -> None:
        """
        Выводит контекстное меню через правый клик мыши.

        Args:
            event: Событие контекстного меню.
        """
        
        menu = QMenu(self)
        quit_action = QAction('Выход', self)
        quit_action.triggered.connect(self.shutdown)
        menu.addAction(quit_action)
        menu.exec(event.globalPos())
        event.accept()

    # Логика перетаскивания
    def _end_drag(self) -> None:
        """ Завершает перетаскивание (переход в падение или idle) """

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
            self._clamp_pet_position()
            log.debug('Конец перетаскивания: возврат в idle')
            self._enter_idle()

    def _update_drag(self, delta_time: float) -> None:
        """
        Переключает фазы перетаскивания по скорости курсора.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

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

    # ---- Логика падения и приземления ----
    def _update_fall(self, delta_time: float) -> None:
        """
        Применяет физику падения и проверяет достижение пола.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

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
            self._clamp_pet_position()
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
        """
        Ожидание окончания анимации приземления.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

        if self.active_animation.finished:
            log.debug('Приземление завершено: возврат в idle')
            self._enter_idle()

    # ---- Логика появления ----
    def _update_appearing(self, delta_time: float) -> None:
        """
        Ждёт окончания анимации появления.

        Для center — сразу в idle. Для left/right — шаг из-за края.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

        if not self.active_animation.finished:
            return

        log.debug(f'Появление завершено (side={self._appear_side})')

        if self._appear_side == 'center':
            self._enter_idle()
            return

        pet_width = self.pet_render_size.width()
        max_x = self.width() - pet_width

        if self._appear_side == 'left':
            self.pet_position.setX(-pet_width)
            direction = 1
        else:  # right
            self.pet_position.setX(max_x + pet_width)
            direction = -1

        self._update_mask()
        self.update()

        # Шаг в сторону центра ровно на ширину спрайта
        walk_duration = pet_width / WALK_SPEED
        self.walk_direction = direction
        self.walk_time_left = walk_duration
        self._walk_from_appear = True
        self._appear_walk_elapsed = 0.0
        self.pet_state = PetState.WALK
        self._activate_animation(self.walk_animations[direction])
        log.debug(f'После появления: шаг {"вправо" if direction > 0 else "влево"}')

    # ---- Логика ходьбы и IDLE-планировшика ----
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

    def _start_potion(self) -> None:
        """ Запускает анимацию с зельем — событие в idle """

        log.debug('Событие idle: зелье')
        self.pet_state = PetState.POTION
        self._activate_animation(self.potion_animation)

    def _start_idle_event(self) -> None:
        """
        Выбирает случайное событие в idle по весам из config.
        Если все веса = 0 — событие не выбирается, питомец остаётся в idle.
        """

        events = list(IDLE_EVENT_WEIGHTS.keys())
        weights = list(IDLE_EVENT_WEIGHTS.values())

        if sum(weights) <= 0:
            log.debug('Все веса idle-событий = 0, остаёмся в idle')
            self._enter_idle()
            return
        event = random.choices(events, weights=weights, k=1)[0]

        if event == 'walk':
            self._start_walk()
        elif event == 'kiss':
            self._start_kiss()
        elif event == 'potion':
            self._start_potion()
        else:
            log.warning('Неизвестное idle-событие: %s', event)

    def _update_idle(self, delta_time: float) -> None:
        """
        Планировщик idle-событий (ожидание и выбор следующего).

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

        if self.music_playing or self.video_playing:
            self._enter_idle()
            return

        self.idle_wait_left -= delta_time
        if self.idle_wait_left <= 0:
            self._start_idle_event()

    def _update_walk(self, delta_time: float) -> None:
        """
        Двигает питомца, следит за краями экрана и таймером ходьбы.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

        pet_width = self.pet_render_size.width()

        if self._walk_from_appear:
            self._appear_walk_elapsed += delta_time
            total_duration = pet_width / WALK_SPEED
            progress = min(1.0, self._appear_walk_elapsed / total_duration)

            if self._appear_side == 'left':
                start_x, end_x = -pet_width, 0
            else:  # right
                start_x = self.width()
                end_x = self.width() - pet_width

            new_x = int(start_x + (end_x - start_x) * progress)
            self.pet_position.setX(new_x)
            self._update_mask()
            self.update()

            if progress >= 1.0:
                self._walk_from_appear = False
                self._appear_walk_elapsed = 0.0
                log.debug('Выход из-за края завершён')
                self._enter_idle()
            return

            # Обычная ходьба
        self.walk_time_left -= delta_time

        min_x = 0
        max_x = self.width() - pet_width
        new_x = self.pet_position.x() + WALK_SPEED * self.walk_direction * delta_time

        if new_x <= min_x or new_x >= max_x or self.walk_time_left <= 0:
            new_x = max(min_x, min(max_x, new_x))
            self.pet_position.setX(int(new_x))
            self._update_mask()
            self.update()
            log.debug('Ходьба завершена')
            self._enter_idle()
            return

        self.pet_position.setX(int(new_x))
        self._update_mask()
        self.update()

    def _update_kiss(self, _delta_time: float) -> None:
        """
        Ждёт окончания анимации поцелуя.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

        if self.active_animation.finished:
            log.debug('Поцелуй завершён: возврат в idle')
            self._enter_idle()

    def _update_potion(self, _delta_time: float) -> None:
        """
        Ждёт окончания анимации зелья.

        Args:
            delta_time: Время с прошлого тика (секунды).
        """

        if self.active_animation.finished:
            log.debug('Зелье завершено: возврат в idle')
            self._enter_idle()

    # ---- Игровой цикл и отрисовка ----
    def _on_tick(self) -> None:
        """ Вызывается таймером ~60 раз в секунду. Обновляет состояние """

        current_time = time.perf_counter()
        delta_time = current_time - self.last_tick_time
        self.last_tick_time = current_time

        if self.pet_state is PetState.APPEARING:
            self._update_appearing(delta_time)
        elif self.pet_state is PetState.DRAG:
            self._update_drag(delta_time)
        elif self.pet_state is PetState.FALL:
            self._update_fall(delta_time)
        elif self.pet_state is PetState.LAND:
            self._update_land(delta_time)
        elif self.pet_state is PetState.WALK:
            self._update_walk(delta_time)
        elif self.pet_state is PetState.KISS:
            self._update_kiss(delta_time)
        elif self.pet_state is PetState.POTION:
            self._update_potion(delta_time)
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

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Рисует текущий кадр питомца в его прямоугольнике внутри окна.

        Args:
            event: Событие отрисовки.
        """

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        target_rect = QRect(self.pet_position, self.pet_render_size)
        painter.drawImage(target_rect, self.active_frame.qimage)
