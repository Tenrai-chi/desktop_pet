""" Модуль воспроизведения звуков (реплик питомца) """

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import (
    QAudioOutput,
    QMediaDevices,
    QMediaPlayer,
    QSoundEffect,
)


log = logging.getLogger(__name__)


class SoundPlayer:
    """
    Кэш звуков по имени файла (без расширения) для быстрого воспроизведения.
    Поддерживает два режима работы:
    1. Системное устройство по умолчанию (использует QSoundEffect для мгновенного старта).
    2. Конкретное устройство вывода (использует QMediaPlayer).
    """

    def __init__(self,
                 sounds_dir: Path,
                 volume: float = 0.8,
                 output_device: str = '',
                 ) -> None:
        """
        Инициализирует плеер звуков.

        Args:
            sounds_dir: Путь к папке с WAV-файлами.
            volume: Громкость (от 0.0 до 1.0).
            output_device: Имя устройства вывода. Пустая строка — системное.
        """

        self._sounds_dir = sounds_dir
        self._volume = max(0.0, min(1.0, volume))
        self._output_device = output_device

        # Имя файла без расширения → путь к WAV
        self._sources: dict[str, Path] = {}

        # QSoundEffect — только для системного устройства
        self._effects: dict[str, QSoundEffect] = {}

        # QMediaPlayer — только для конкретного устройства, создаётся лениво
        self._media_player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None

        self._load()

    # Загрузка
    def _load(self) -> None:
        """ Загружает звуки из директории и инициализирует QSoundEffect """

        if not self._sounds_dir.exists():
            log.warning(f'Папка звуков не найдена: {self._sounds_dir}')
            return

        use_default_device = not self._output_device

        for wav in self._sounds_dir.glob('*.wav'):
            self._sources[wav.stem] = wav

            # QSoundEffect грузим только если устройство системное.
            # Для конкретного устройства — QMediaPlayer, создаём при play.
            if use_default_device:
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(wav)))
                effect.setVolume(self._volume)
                self._effects[wav.stem] = effect

        mode = 'системное' if use_default_device else self._output_device
        log.info(
            f'Загружено звуков: {len(self._sources)} (устройство: {mode}, громкость: {self._volume * 100:.0f}%)'
        )

    # Ленивое создание QMediaPlayer
    def _ensure_media_player(self) -> bool:
        """
        Создает QMediaPlayer на выбранном устройстве.

        Returns:
            True, если плеер готов к работе, иначе False.
        """

        if self._media_player is not None:
            return True

        device = None
        for dev in QMediaDevices.audioOutputs():
            if dev.description() == self._output_device:
                device = dev
                break

        if device is None:
            log.warning(
                f'Устройство вывода "{self._output_device}" не найдено',
            )
            return False

        self._audio_output = QAudioOutput(device)
        self._audio_output.setVolume(self._volume)

        self._media_player = QMediaPlayer()
        self._media_player.setAudioOutput(self._audio_output)

        log.info(f'QMediaPlayer создан для устройства: {device.description()}')
        return True

    # Воспроизведение
    def play(self, name: str) -> None:
        """
        Проигрывает звук по имени.

        Args:
            name: Имя файла без расширения.
        """

        if name not in self._sources:
            log.warning('Звук не найден: %s', name)
            return

        # Режим 1: системное устройство — QSoundEffect
        if not self._output_device:
            effect = self._effects.get(name)
            if effect is None:
                log.warning(f'QSoundEffect не создан для: {name}')
                return
            effect.play()
            return

        # Режим 2: конкретное устройство — QMediaPlayer
        if not self._ensure_media_player():
            return

        assert self._media_player is not None
        self._media_player.stop()
        self._media_player.setSource(QUrl.fromLocalFile(str(self._sources[name])))
        self._media_player.play()
