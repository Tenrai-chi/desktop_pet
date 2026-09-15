import logging
import time
from enum import Enum, auto

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from config import (
    DIRECTION_MIN_SPEED,
    GRAVITY,
    MAX_FALL_SPEED,
    SPEED_EMA_ALPHA,
    SPEED_START,
    SPEED_STOP,
    SPEED_ZERO_MS,
)
from render import Animation, DragAnimSet


log = logging.getLogger(__name__)


class PetState(Enum):
    """ Общее состояние питомца: покой, перетаскивание, падение, приземление """
    
    IDLE = auto()
    DRAG = auto()
    FALL = auto()
    LAND = auto()


class DragPhase(Enum):
    """ Подфазы перетаскивания. Переключаются по скорости курсора """
    
    ACCEL = auto()
    HOLD = auto()
    DECEL = auto()


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
        fall: Animation,
        tick_ms: int = 16,
        scale: float = 1.0,
        start_position: str = 'bottom-center',
        span_all_screens: bool = True,
    ):
        super().__init__()

        assert scale > 0, f'scale должен быть > 0, получено {scale}'

        # --- анимации ---
        self.idle_animation = idle
        self.fall_animation = fall
        self.drag_animation_sets = {1: drag_right, -1: drag_left}
        # Пока один статичный кадр, позже обновить на полноценную анимацию падения
        self.free_fall_animation = Animation([idle.frames[0]], fps=1.0, loop=True)

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
        self.drag_phase: DragPhase | None = None
        self.drag_direction = 1
        self.grab_offset = QPoint()
        self.last_cursor_move_time = 0.0
        self.last_cursor_x = 0
        self.cursor_speed = 0.0

        # Падение
        self.fall_velocity = 0.0

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
        elif mode == 'bottom-right':
            self.pet_position = QPoint(
                window_width - pet_width,
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
        self.setMask(
            QRegion(
                self.pet_position.x(),
                self.pet_position.y(),
                self.pet_render_size.width(),
                self.pet_render_size.height(),
            )
        )

    # Управление анимацией
    def _activate_animation(self, animation: Animation) -> None:
        """ Переключает активную анимацию и сбрасывает её в начало """
        
        animation.reset()
        self.active_animation = animation

    # Жизненный цикл
    def shutdown(self) -> None:
        """ Останавливает таймер, закрывает окно, завершает приложение """
        
        log.info('Выход через контекстное меню')
        self.tick_timer.stop()
        self.close()
        QApplication.instance().quit()

    # Обработка событий мыши

    def mousePressEvent(self, event):
        """ Начало перетаскивания: запоминаем точку захвата, снимаем маску """
        
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Хватание отменяет падение/приземление, если они были в процессе.
        self.fall_velocity = 0.0
        self.pet_state = PetState.DRAG
        self.drag_phase = DragPhase.ACCEL

        click_position = event.position().toPoint()
        self.grab_offset = click_position - self.pet_position

        # На время перетаскивания маску удаляется целиком
        self.clearMask()

        self.last_cursor_move_time = time.perf_counter()
        self.last_cursor_x = event.globalPosition().toPoint().x()
        self.cursor_speed = 0.0
        self._activate_animation(
            self.drag_animation_sets[self.drag_direction].accel
        )
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
                    self._apply_drag_phase_animation()

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

        self.drag_phase = None
        self.cursor_speed = 0.0

        if self.pet_position.y() < self._floor_top_y():
            self.pet_state = PetState.FALL
            self.fall_velocity = 0.0
            self._activate_animation(self.free_fall_animation)
        else:
            self.pet_state = PetState.IDLE
            self._activate_animation(self.idle_animation)

    def _apply_drag_phase_animation(self) -> None:
        """ Устанавливает анимацию, соответствующую текущей фазе перетаскивания и направлению """

        if self.drag_phase is None:
            return

        direction_set = self.drag_animation_sets[self.drag_direction]
        if self.drag_phase is DragPhase.ACCEL:
            self._activate_animation(direction_set.accel)
        elif self.drag_phase is DragPhase.HOLD:
            self._activate_animation(direction_set.hold)
        elif self.drag_phase is DragPhase.DECEL:
            self._activate_animation(direction_set.decel)

    def _update_drag(self, delta_time: float) -> None:
        """ Переключает фазы перетаскивания по скорости курсора и завершению анимаций """

        if (time.perf_counter() - self.last_cursor_move_time) * 1000 > SPEED_ZERO_MS:
            self.cursor_speed = 0.0

        current_phase = self.drag_phase

        # Резко ускорился — играем ACCEL из любого состояния.
        if self.cursor_speed > SPEED_START and current_phase is not DragPhase.ACCEL:
            self.drag_phase = DragPhase.ACCEL
            self._apply_drag_phase_animation()
            return

        if current_phase is DragPhase.ACCEL:
            if self.active_animation.finished:
                self.drag_phase = DragPhase.HOLD
                self._apply_drag_phase_animation()

        elif current_phase is DragPhase.HOLD:
            if self.cursor_speed < SPEED_STOP:
                self.drag_phase = DragPhase.DECEL
                self._apply_drag_phase_animation()

        elif current_phase is DragPhase.DECEL:
            if self.active_animation.finished:
                self.drag_phase = None
                self._activate_animation(self.idle_animation)

    # Логика падения и приземления

    def _update_fall(self, delta_time: float) -> None:
        """ Применяет ускорение для падения, двигает питомца, проверяет, достиг ли питомец пола """

        self.fall_velocity = min(
            self.fall_velocity + GRAVITY * delta_time,
            MAX_FALL_SPEED,
        )
        new_y = self.pet_position.y() + self.fall_velocity * delta_time
        floor_y = self._floor_top_y()

        if new_y >= floor_y:
            self.pet_position.setY(floor_y)
            self.fall_velocity = 0.0
            self.pet_state = PetState.LAND
            self._activate_animation(self.fall_animation)
        else:
            self.pet_position.setY(int(new_y))

        # Падение обновляет маску, чтобы можно было поймать его налету
        self._update_mask()
        self.update()

    def _update_land(self, delta_time: float) -> None:
        """ Ожидание окончания анимации приземления, затем возвращает idle """

        if self.active_animation.finished:
            self.pet_state = PetState.IDLE
            self._activate_animation(self.idle_animation)

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

        self.active_animation.update(delta_time)
        new_frame = self.active_animation.current
        if new_frame is not self.active_frame:
            self.active_frame = new_frame
            self.update()

    # Отрисовка
    def paintEvent(self, _event):
        """ Рисует текущий кадр питомца в его прямоугольнике внутри окна. """

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        target_rect = QRect(self.pet_position, self.pet_render_size)
        painter.drawImage(target_rect, self.active_frame.qimage)
