import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import re
import logging
import pygame

from PySide6.QtGui import QImage
from pathlib import Path

log = logging.getLogger(__name__)


def init_pygame_offscreen() -> None:
    """ Инициализирует pygame без настоящего окна. """

    pygame.init()
    pygame.display.set_mode((1, 1))


def shutdown_pygame() -> None:
    """ Корректное завершение pygame для закрытия программы """
    pygame.quit()


class Frame:
    """
    Один кадр анимации: pygame.Surface + ленивый кэш QImage.
    QImage строится при первом обращении, потому что не каждый кадр
    гарантированно попадёт на экран (например, ветки ACCEL/DECEL могут
    не доиграть до конца при резкой смене направления)
    """
    
    __slots__ = ('surface', '_qimage')

    def __init__(self, surface: pygame.Surface):
        self.surface = surface
        self._qimage: QImage | None = None

    @property
    def qimage(self) -> QImage:
        """ QImage, построенный из pygame.Surface. Кэшируется после первого вызова """

        if self._qimage is None:
            data = pygame.image.tostring(self.surface, 'RGBA')
            # .copy() чтобы QImage не ссылался на буфер pygame и не перезаписывал его
            self._qimage = QImage(
                data,
                self.surface.get_width(),
                self.surface.get_height(),
                QImage.Format.Format_RGBA8888,
            ).copy()
        return self._qimage

    @property
    def size(self) -> tuple[int, int]:
        """ Размер кадра в пикселях """

        return self.surface.get_size()


def _extract_frame_number(file_path: Path) -> tuple[int, str]:
    """
    Ключ сортировки кадров.
    Если в имени нет числа — считаем его нулевым, сортируем по строке.
    Args:
        file_path: путь к папке с файлами
    Returns:
        tuple:
            - число из имени файла
            - имя файла
    """

    number_match = re.search(r'(\d+)', file_path.stem)
    number = int(number_match.group(1)) if number_match else 0
    return number, file_path.stem


def load_frames(file_paths: list[Path]) -> list[Frame]:
    """
    Загружает PNG, сортирует и возвращает список.
    Args:
        file_paths: путь к файлам
    Returns:
        frames: список кадров для анимации
    """

    sorted_paths = sorted(file_paths, key=_extract_frame_number)
    frames: list[Frame] = []
    for file_path in sorted_paths:
        surface = pygame.image.load(str(file_path)).convert_alpha()
        frames.append(Frame(surface))
    return frames


class Animation:
    """ Покадровая анимация с фиксированным fps из настроек """

    def __init__(self, frames: list[Frame], fps: float = 6.0, loop: bool = True):
        assert frames, 'Пустая анимация'
        self.frames = frames
        self.fps = fps
        self.loop = loop
        self.time_accumulator = 0.0
        self.frame_index = 0
        self.finished = False

    def reset(self) -> None:
        """ Сброс в начало. Нужно при переключении фаз перетягивания. """

        self.time_accumulator = 0.0
        self.frame_index = 0
        self.finished = False

    def update(self, delta_time: float) -> None:
        """ Продвигает анимацию на delta_time  секунд. При loop=False выставляет finished. """

        if self.finished:
            return

        self.time_accumulator += delta_time
        frame_duration = 1.0 / self.fps

        while self.time_accumulator >= frame_duration:
            self.time_accumulator -= frame_duration
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                if self.loop:
                    self.frame_index = 0
                else:
                    self.frame_index = len(self.frames) - 1
                    self.finished = True
                    return

    @property
    def current(self) -> Frame:
        """ Текущий кадр анимации """

        return self.frames[self.frame_index]


class DragAnimSet:
    """
    Набор кадров перетаскивания для одного направления.
    Ожидает 2 кадра: 1 — нейтральный, 2 — сдвиг в сторону.
    При движении играем зацикленный цикл [1, 2], в покое — статичный кадр 1.
    """

    def __init__(self, cycle_frames: list[Frame], still_frame: Frame, fps: float = 14.0):
        assert len(cycle_frames) >= 2, (
            f'Ожидается минимум 2 кадра движения, получено {len(cycle_frames)}'
        )
        self.all_frames = cycle_frames
        self.cycle = Animation(cycle_frames[:2], fps=fps, loop=True)
        self.still = Animation([still_frame], fps=1.0, loop=True)
