import logging

from config import (
    DRAG_DIR,
    DRAG_FPS,
    FALL_FALLING_DIR,
    FALL_FPS,
    FALL_LANDING_MAGIC_DIR,
    FALL_LANDING_NORMAL_DIR,
    IDLE_DIR,
    IDLE_FPS,
    WALK_DIR,
    WALK_FPS,
    MUSIC_DIR,
    MUSIC_FPS,
    VIDEO_DIR,
    VIDEO_FPS,
    KISS_FPS,
    KISS_DIR
)

from render import (
    load_frames,
    Animation,
    DragAnimSet, Frame,
)

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


def load_kiss_animation() -> Animation:
    """ Анимация поцелуя — событие в idle, играется один раз """

    paths = list(KISS_DIR.glob('kiss_*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Не найдено kiss_*.png в {KISS_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров поцелуя: {len(frames)}')
    return Animation(frames, fps=KISS_FPS, loop=False)


def load_drag_still_frame() -> Frame:
    """ Статичный кадр перетаскивания (drag_0.png) — питомец висит неподвижно """

    path = DRAG_DIR / 'drag_0.png'
    if not path.exists():
        raise FileNotFoundError(f'Нет файла {path}')
    return load_frames([path])[0]


def load_drag_animation(direction: str, still_frame: Frame) -> DragAnimSet:
    """
    Анимация перетаскивания в одном направлении.
    Args:
        direction: 'right' или 'left'
        still_frame: общий статичный кадр drag_0
    """

    paths = list(DRAG_DIR.glob(f'{direction}_*.png'))
    if len(paths) < 2:
        raise FileNotFoundError(
            f'Нужно минимум 2 кадра {direction}_*.png в {DRAG_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров перетаскивания {direction}: {len(frames)}')
    return DragAnimSet(frames, still_frame, fps=DRAG_FPS)


def load_falling_animation() -> Animation:
    """ Анимация парения в воздухе (до приземления) """

    paths = list(FALL_FALLING_DIR.glob('*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Нет кадров в {FALL_FALLING_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров падения: {len(frames)}')
    return Animation(frames, fps=FALL_FPS, loop=True)


def load_landing_normal_animation() -> Animation:
    """ Обычное приземление (после невысокого падения) """

    paths = list(FALL_LANDING_NORMAL_DIR.glob('*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Нет кадров в {FALL_LANDING_NORMAL_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров обычного приземления: {len(frames)}')
    return Animation(frames, fps=FALL_FPS, loop=False)


def load_landing_magic_animation() -> Animation:
    """ Магическое приземление (после высокого падения) """
    
    paths = list(FALL_LANDING_MAGIC_DIR.glob('*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Нет кадров в {FALL_LANDING_MAGIC_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров магического приземления: {len(frames)}')
    return Animation(frames, fps=FALL_FPS, loop=False)


def load_walk_animation(direction: str) -> Animation:
    """ Анимация ходьбы для направления 'right' или 'left' """

    paths = list(WALK_DIR.glob(f'{direction}_*.png'))
    if len(paths) < 2:
        raise FileNotFoundError(
            f'Нужно минимум 2 кадра {direction}_*.png в {WALK_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров ходьбы {direction}: {len(frames)}')
    return Animation(frames, fps=WALK_FPS, loop=True)


def load_music_animation() -> Animation:
    """ Анимация прослушивания музыки """
    
    paths = list(MUSIC_DIR.glob('music_*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Не найдено music_*.png в {MUSIC_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров прослушивания музыки: {len(frames)}')
    return Animation(frames, fps=MUSIC_FPS, loop=True)


def load_video_animation() -> Animation:
    """ Анимация просмотра видео """

    paths = list(VIDEO_DIR.glob('video_*.png'))
    if not paths:
        raise FileNotFoundError(
            f'Не найдено video_*.png в {VIDEO_DIR}'
        )
    frames = load_frames(paths)
    log.info(f'Загружено кадров просмотра видео: {len(frames)}')
    return Animation(frames, fps=VIDEO_FPS, loop=True)