import sys
import logging

from PySide6.QtWidgets import QApplication

from config import (
    APP_NAME,
    APP_VERSION,
    DRAG_DIR,
    DRAG_FPS,
    FALL_DIR,
    FALL_FPS,
    IDLE_DIR,
    IDLE_FPS,
    TICK_INTERVAL_MS,
    PET_SPAN_ALL_SCREENS,
    PET_SCALE,
    PET_START_POSITION
)

from render import (
    init_pygame_offscreen,
    load_frames,
    Animation,
    DragAnimSet,
    shutdown_pygame,
)
from logger import setup_logging
from pet_widget import PetWidget

log = logging.getLogger(__name__)


def load_idle_animation() -> Animation:
    """ Анимация простаивания """
    
    paths = list(IDLE_DIR.glob('idle_*.png'))
    if not paths:
        raise FileNotFoundError(
             f'Не найдено ни одного idle_*.png в {IDLE_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено idle кадров: {len(frames)}')
    return Animation(frames, fps=IDLE_FPS, loop=True)


def load_drag_animation(direction: str) -> DragAnimSet:
    """
    Анимация перетаскивания в одном направлении.
    Args:
        direction: 'right' или 'left'
    """
    
    paths = list(DRAG_DIR.glob(f'{direction}_*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Не найдено {direction}_*.png в {DRAG_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров перемещения {direction}: {len(frames)}')
    return DragAnimSet(frames, fps=DRAG_FPS)


def load_fall_animation() -> Animation:
    """ Разовая анимация приземления """

    paths = list(FALL_DIR.glob('fall_*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Не найдено fall_*.png в {FALL_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров падения: {len(frames)}')
    return Animation(frames, fps=FALL_FPS, loop=False)


def main() -> int | None:
    setup_logging()
    log.info(f'Запуск {APP_NAME} v{APP_VERSION}')
    try:
        app = QApplication(sys.argv)

        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        app.aboutToQuit.connect(shutdown_pygame)

        init_pygame_offscreen()
        idle_animation = load_idle_animation()
        drag_right_animation = load_drag_animation('right')
        drag_left_animation = load_drag_animation('left')
        fall_animation = load_fall_animation()

        pet = PetWidget(
            idle=idle_animation,
            drag_right=drag_right_animation,
            drag_left=drag_left_animation,
            fall=fall_animation,
            tick_ms=TICK_INTERVAL_MS,
            scale=PET_SCALE,
            start_position=PET_START_POSITION,
            span_all_screens=PET_SPAN_ALL_SCREENS
        )
        pet.show()
        log.info(f'Запуск приложения прошел успешно')
        return app.exec()
    except Exception as error:
        log.exception(f'Произошла ошибка: {error}')
        return None


if __name__ == '__main__':
    sys.exit(main())
