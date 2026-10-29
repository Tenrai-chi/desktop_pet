""" Модуль системы реакций питомца на события (процессы и сайты) """

import logging
import random
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


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
        """
        Возвращает случайную фразу.

        Returns:
            Случайная строка из списка texts или None, если фраз нет
            или текстовые реакции отключены.
        """
        
        if not self.text_enabled:
            return None
        return random.choice(self.texts) if self.texts else None

    def pick_sound(self) -> str | None:
        """
        Возвращает случайное имя звука.

        Returns:
            Случайная строка из списка sounds или None, если звуков нет
            или звуковые реакции отключены.
        """
        
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
        """ Инициализирует пустые словари для реакций и таймеров """

        self._by_process: dict[str, Reaction] = {}
        self._by_site: dict[str, Reaction] = {}
        self._last_fired: dict[str, float] = {}
        self._last_site_fired: dict[str, float] = {}

    def load(self, path: Path) -> None:
        """
        Загружает реакции из TOML-файла.

        Args:
            path: Путь к файлу конфигурации (например, reactions.toml).
        """
        
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

        sites_section = data.get('sites', {})
        for key, cfg in sites_section.items():
            reaction = Reaction(
                texts=list(cfg.get('texts', [])),
                sounds=list(cfg.get('sounds', [])),
                cooldown=float(cfg.get('cooldown', 180.0)),
                text_enabled=bool(cfg.get('text_enabled', True)),
                sound_enabled=bool(cfg.get('sound_enabled', True)),
            )
            self._by_site[key.lower()] = reaction
            log.debug(f'Реакция на сайт {key} загружена')

        log.debug(
            f'Загружено реакций: {len(self._by_process)} на процессы, {len(self._by_site)} на сайты',
        )

    def match(self, process_name: str) -> Reaction | None:
        """
        Ищет реакцию для процесса, если перезарядка истекла.
        Не сбрасывает таймер.

        Args:
            process_name: Имя исполняемого файла процесса (например, 'chrome.exe').

        Returns:
            Экземпляр Reaction или None, если реакции нет или cooldown не прошёл.
        """

        reaction = self._by_process.get(process_name.lower())
        if reaction is None:
            return None

        last = self._last_fired.get(process_name.lower(), 0.0)
        if time.perf_counter() - last < reaction.cooldown:
            return None
        return reaction

    def mark_fired(self, process_name: str) -> None:
        """
        Запоминает момент срабатывания реакции для процесса.

        Args:
            process_name: Имя процесса.
        """

        self._last_fired[process_name.lower()] = time.perf_counter()

    def match_site(self, site: str) -> Reaction | None:
        """
        Ищет реакцию для сайта, если перезарядка истекла.

        Args:
            site: Идентификатор сайта (например, 'youtube').

        Returns:
            Экземпляр Reaction или None, если реакции нет или cooldown не прошёл.
        """

        reaction = self._by_site.get(site.lower())
        if reaction is None:
            return None

        last = self._last_site_fired.get(site.lower(), 0.0)
        if time.perf_counter() - last < reaction.cooldown:
            return None
        return reaction

    def mark_site_fired(self, site: str) -> None:
        """
        Запоминает момент срабатывания реакции на сайт.

        Args:
            site: Идентификатор сайта.
        """

        self._last_site_fired[site.lower()] = time.perf_counter()
