"""Плеер коротких звуков через QSoundEffect.

QSoundEffect буферизует WAV при setSource, поэтому загрузка — один раз
при старте приложения. В рантайме play() — мгновенный.
"""

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect


log = logging.getLogger(__name__)


class SoundPlayer:
    """Кэш QSoundEffect по имени файла без расширения."""

    def __init__(self, sounds_dir: Path, volume: float = 0.8):
        self._effects: dict[str, QSoundEffect] = {}
        self._volume = volume
        self._load(sounds_dir)

    def _load(self, sounds_dir: Path) -> None:
        if not sounds_dir.exists():
            log.warning("Папка звуков не найдена: %s", sounds_dir)
            return

        for wav in sounds_dir.glob("*.wav"):
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(wav)))
            effect.setVolume(self._volume)
            self._effects[wav.stem] = effect

        log.info("Загружено звуков: %d", len(self._effects))

    def play(self, name: str) -> None:
        """Проиграть звук по имени. Если не найден — только warning."""
        effect = self._effects.get(name)
        if effect is None:
            log.warning("Звук не найден: %s", name)
            return
        effect.play()