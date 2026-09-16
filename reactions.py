import logging
import random
import time

from dataclasses import dataclass, field
from pathlib import Path

import tomllib


log = logging.getLogger(__name__)


@dataclass
class Reaction:
    """ Описание одной реакции: фразы, звуки, пауза между срабатываниями """

    texts: list[str] = field(default_factory=list)
    sounds: list[str] = field(default_factory=list)
    cooldown: float = 60.0
    text_enabled: bool = True
    sound_enabled: bool = True

    def pick_text(self) -> str | None:
        """ Случайная фраза или None, если фраз нет или текст выключен """
        
        if not self.text_enabled:
            return None
        return random.choice(self.texts) if self.texts else None

    def pick_sound(self) -> str | None:
        """ Случайное имя звука или None, если звуков нет или звук выключен """
        
        if not self.sound_enabled:
            return None
        return random.choice(self.sounds) if self.sounds else None


class ReactionBook:
    """
    Реакции на приложения с учётом перезарядки.
    Хранит карту {process_name_lower: Reaction}. Один процесс может быть
    только в одной секции.
    """

    def __init__(self) -> None:
        self._by_process: dict[str, Reaction] = {}
        self._last_fired: dict[str, float] = {}

    def load(self, path: Path) -> None:
        """ Читает TOML с реакциями. Тихо выходит, если файла нет """
        
        if not path.exists():
            log.info(f'Файл реакций не найден: {path}')
            return

        try:
            with path.open('rb') as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as error:
            log.error(f'Не удалось прочитать {path}: {error}')
            return

        apps_section = data.get('apps', {})
        for key, cfg in apps_section.items():
            reaction = Reaction(
                texts=list(cfg.get('texts', [])),
                sounds=list(cfg.get('sounds', [])),
                cooldown=float(cfg.get('cooldown', 60.0)),
                text_enabled=bool(cfg.get('text_enabled', True)),
                sound_enabled=bool(cfg.get('sound_enabled', True)),
            )
            for proc in cfg.get('process_names', []):
                self._by_process[proc.lower()] = reaction
                log.debug(f'Реакция {key} привязана к {proc}')

        log.debug(f'Загружено реакций на {len(self._by_process)} процессов')

    def match(self, process_name: str) -> Reaction | None:
        """
        Возвращает реакцию для процесса, если cooldown истёк. Иначе None.
        Не сбрасывает таймер — это делает PetWidget после показа реакции.
        """

        reaction = self._by_process.get(process_name.lower())
        if reaction is None:
            return None

        last = self._last_fired.get(process_name.lower(), 0.0)
        if time.perf_counter() - last < reaction.cooldown:
            return None
        return reaction

    def mark_fired(self, process_name: str) -> None:
        """ Запомнить момент срабатывания — для cooldown """

        self._last_fired[process_name.lower()] = time.perf_counter()