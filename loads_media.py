""" Модуль загрузки всех медиа-ресурсов (анимаций) для питомца """

import logging
from dataclasses import dataclass

from config import (
    APPEAR_CENTER_DIR,
    APPEAR_FPS,
    APPEAR_LEFT_DIR,
    APPEAR_RIGHT_DIR,
    DRAG_DIR,
    DRAG_FPS,
    FALL_FALLING_DIR,
    FALL_FPS,
    FALL_LANDING_MAGIC_DIR,
    FALL_LANDING_NORMAL_DIR,
    IDLE_DIR,
    IDLE_FPS,
    KISS_DIR,
    KISS_FPS,
    MUSIC_DIR,
    MUSIC_FPS,
    POTION_DIR,
    POTION_FPS,
    VIDEO_DIR,
    VIDEO_FPS,
    WALK_DIR,
    WALK_FPS,
)

from render import (
    Animation,
    DragAnimSet,
    Frame,
    load_frames,
)


log = logging.getLogger(__name__)

_APPEAR_DIRS = {
    'center': APPEAR_CENTER_DIR,
    'left': APPEAR_LEFT_DIR,
    'right': APPEAR_RIGHT_DIR,
}


class MediaLoader:
    """ Загрузчик всех анимаций питомца """

    @staticmethod
    def load_idle_animation() -> Animation:
        """
        Загружает анимацию бездействия (idle).

        Returns:
            Зацикленная анимация.
        """

        paths = list(IDLE_DIR.glob('idle_*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Не найдено ни одного idle_*.png в {IDLE_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено idle кадров: {len(frames)}')
        return Animation(frames, fps=IDLE_FPS, loop=True)

    @staticmethod
    def load_kiss_animation() -> Animation:
        """
        Загружает анимацию поцелуя (разовое событие).

        Returns:
            Разовая анимация.
        """

        paths = list(KISS_DIR.glob('kiss_*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Не найдено kiss_*.png в {KISS_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров поцелуя: {len(frames)}')
        return Animation(frames, fps=KISS_FPS, loop=False)

    @staticmethod
    def load_potion_animation() -> Animation:
        """
        Загружает анимацию с зельем (разовое событие).

        Returns:
            Разовая анимация.
        """

        paths = list(POTION_DIR.glob('potion_*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Не найдено potion_*.png в {POTION_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров зелья: {len(frames)}')
        return Animation(frames, fps=POTION_FPS, loop=False)

    @staticmethod
    def load_appear_animation(direction: str) -> Animation:
        """
        Загружает анимацию появления.

        Args:
            direction: Направление появления ('center', 'left', 'right').

        Returns:
            Разовая анимация появления.
        """

        if direction not in _APPEAR_DIRS:
            raise ValueError(f'Неизвестная сторона появления: {direction!r}')

        appear_dir = _APPEAR_DIRS[direction]
        paths = list(appear_dir.glob(f'appear_{direction}_*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Не найдено appear_{direction}_*.png в {appear_dir}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров появления {direction}: {len(frames)}')
        return Animation(frames, fps=APPEAR_FPS, loop=False)

    @staticmethod
    def load_drag_still_frame() -> Frame:
        """
        Загружает статичный кадр перетаскивания (drag_0.png).

        Returns:
            Один кадр (Frame).
        """

        path = DRAG_DIR / 'drag_0.png'
        if not path.exists():
            raise FileNotFoundError(f'Нет файла {path}')
        return load_frames([path])[0]

    @staticmethod
    def load_drag_animation(direction: str, still_frame: Frame) -> DragAnimSet:
        """Загружает анимацию перетаскивания для указанного направления.

        Args:
            direction: Направление ('right', 'left').
            still_frame: Общий статичный кадр (drag_0).

        Returns:
            Набор анимаций перетаскивания.
        """

        paths = list(DRAG_DIR.glob(f'{direction}_*.png'))
        if len(paths) < 2:
            raise FileNotFoundError(
                f'Нужно минимум 2 кадра {direction}_*.png в {DRAG_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров перетаскивания {direction}: {len(frames)}')
        return DragAnimSet(frames, still_frame, fps=DRAG_FPS)

    @staticmethod
    def load_falling_animation() -> Animation:
        """
        Загружает анимацию парения в воздухе.

        Returns:
            Зацикленная анимация падения.
        """

        paths = list(FALL_FALLING_DIR.glob('*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Нет кадров в {FALL_FALLING_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров падения: {len(frames)}')
        return Animation(frames, fps=FALL_FPS, loop=True)

    @staticmethod
    def load_landing_normal_animation() -> Animation:
        """
        Загружает анимацию обычного приземления.

        Returns:
            Разовая анимация.
        """

        paths = list(FALL_LANDING_NORMAL_DIR.glob('*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Нет кадров в {FALL_LANDING_NORMAL_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров обычного приземления: {len(frames)}')
        return Animation(frames, fps=FALL_FPS, loop=False)

    @staticmethod
    def load_landing_magic_animation() -> Animation:
        """
        Загружает анимацию магического приземления.

        Returns:
            Разовая анимация.
        """

        paths = list(FALL_LANDING_MAGIC_DIR.glob('*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Нет кадров в {FALL_LANDING_MAGIC_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров магического приземления: {len(frames)}')
        return Animation(frames, fps=FALL_FPS, loop=False)

    @staticmethod
    def load_walk_animation(direction: str) -> Animation:
        """
        Загружает анимацию ходьбы для указанного направления.

        Args:
            direction: Направление ('right', 'left').

        Returns:
            Зацикленная анимация ходьбы.
        """

        paths = list(WALK_DIR.glob(f'{direction}_*.png'))
        if len(paths) < 2:
            raise FileNotFoundError(
                f'Нужно минимум 2 кадра {direction}_*.png в {WALK_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров ходьбы {direction}: {len(frames)}')
        return Animation(frames, fps=WALK_FPS, loop=True)

    @staticmethod
    def load_music_animation() -> Animation:
        """
        Загружает анимацию прослушивания музыки.

        Returns:
            Зацикленная анимация.
        """

        paths = list(MUSIC_DIR.glob('music_*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Не найдено music_*.png в {MUSIC_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров прослушивания музыки: {len(frames)}')
        return Animation(frames, fps=MUSIC_FPS, loop=True)

    @staticmethod
    def load_video_animation() -> Animation:
        """
        Загружает анимацию просмотра видео.

        Returns:
            Зацикленная анимация.
        """

        paths = list(VIDEO_DIR.glob('video_*.png'))
        if not paths:
            raise FileNotFoundError(
                f'Не найдено video_*.png в {VIDEO_DIR}'
            )
        frames = load_frames(paths)
        log.info(f'Загружено кадров просмотра видео: {len(frames)}')
        return Animation(frames, fps=VIDEO_FPS, loop=True)


@dataclass(frozen=True)
class PetAnimations:
    """ Набор всех анимаций питомца для передачи в PetWidget одним аргументом """

    idle: Animation
    appear_center: Animation
    appear_left: Animation
    appear_right: Animation
    drag_still: Frame
    drag_right: DragAnimSet
    drag_left: DragAnimSet
    falling: Animation
    landing_normal: Animation
    landing_magic: Animation
    walk_right: Animation
    walk_left: Animation
    music: Animation
    video: Animation
    kiss: Animation
    potion: Animation


def load_all() -> PetAnimations:
    """
    Загружает все анимации питомца и упаковывает их в dataclass.

    Returns:
        Экземпляр PetAnimations со всеми загруженными анимациями.
    """

    idle = MediaLoader.load_idle_animation()
    drag_still = MediaLoader.load_drag_still_frame()
    return PetAnimations(
        idle=idle,
        appear_center=MediaLoader.load_appear_animation('center'),
        appear_left=MediaLoader.load_appear_animation('left'),
        appear_right=MediaLoader.load_appear_animation('right'),
        drag_still=drag_still,
        drag_right=MediaLoader.load_drag_animation('right', drag_still),
        drag_left=MediaLoader.load_drag_animation('left', drag_still),
        falling=MediaLoader.load_falling_animation(),
        landing_normal=MediaLoader.load_landing_normal_animation(),
        landing_magic=MediaLoader.load_landing_magic_animation(),
        walk_right=MediaLoader.load_walk_animation('right'),
        walk_left=MediaLoader.load_walk_animation('left'),
        music=MediaLoader.load_music_animation(),
        video=MediaLoader.load_video_animation(),
        kiss=MediaLoader.load_kiss_animation(),
        potion=MediaLoader.load_potion_animation()
    )
