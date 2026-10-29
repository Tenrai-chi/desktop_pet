""" модуль обработки голосовых команд """

import ctypes
import datetime
import logging
import os
import random
import subprocess
import tomllib
import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject

log = logging.getLogger(__name__)

# Константы виртуальных клавиш Windows для управления громкостью
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

# Пути к популярным браузерам для команды поиска
_BROWSER_PATHS = {
    'chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'firefox': r'C:\Program Files\Mozilla Firefox\firefox.exe',
    'edge': r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
}


def _press_key(vk_code: int, count: int = 1) -> None:
    """
    Имитирует нажатие мультимедийной клавиши.
    Args:
        vk_code: Код виртуальной клавиши Windows.
        count: Количество нажатий. По умолчанию 1.
        """

    for _ in range(count):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


class CommandHandler(QObject):
    """ Обработчик голосовых команд """

    def __init__(self, config_path: Path, search_engine: str = 'google', browser: str = 'system') -> None:
        """
        Инициализирует обработчик команд.
        Args:
            config_path: Путь к файлу конфигурации команд (commands.toml).
            search_engine: Поисковая система для динамических команд.
            browser: Браузер для открытия ссылок.
        """

        super().__init__()
        self._commands: dict[str, dict] = {}
        self._search_engine = search_engine
        self._browser = browser
        self._load_commands(config_path)

        self._search_urls = {
            'google': 'https://www.google.com/search?q=',
            'yandex': 'https://yandex.ru/search/?text=',
            'bing': 'https://www.bing.com/search?q=',
            'duckduckgo': 'https://duckduckgo.com/?q='
        }

    def _load_commands(self, path: Path) -> None:
        """
        Загружает команды из toml файла
        Args:
            path: Путь к файлу с командами.
        """

        if not path.exists():
            log.warning(f'Файл команд не найден: {path}')
            return
        try:
            with open(path, 'rb') as f:
                data = tomllib.load(f)
            for name, cfg in data.get('commands', {}).items():
                triggers = [t.lower() for t in cfg.get('triggers', [])]
                for t in triggers:
                    self._commands[t] = cfg
            log.info(f'Загружено простых команд: {len(self._commands)}')
        except Exception as e:
            log.exception(f'Ошибка чтения commands.toml: {e}')

    def execute(self, text: str) -> tuple[str, str | None]:
        """
        Выполняет голосовую команду.
        Args:
            text: Распознанный текст команды.

        Returns:
            Кортеж из (ответ_питомца, действие_для_питомца).
            Действие может быть 'exit' для выключения или None.
        """

        text = text.lower().strip()

        # 1. Точное совпадение из TOML
        if text in self._commands:
            cfg = self._commands[text]
            action = cfg.get('action')
            target = cfg.get('target')
            replies = cfg.get('replies', [])

            reply = random.choice(replies) if replies else ''

            if action == 'launch':
                success = self._launch(target)
                if success:
                    return reply, None
                else:
                    return f'Не могу найти {text}. Возможно, программы нет на компьютере.', None

            elif action == 'url':
                self._open_url(target)
                return reply, None
            elif action == 'exit':
                return reply, 'exit'
            elif action == 'reply':
                return reply, None
            elif action == 'time':
                now = datetime.datetime.now().strftime('%H:%M')
                return f'Сейчас {now}', None
            elif action == 'volume_up':
                _press_key(VK_VOLUME_UP, count=5)
                return reply, None
            elif action == 'volume_down':
                _press_key(VK_VOLUME_DOWN, count=5)
                return reply, None
            elif action == 'volume_mute':
                _press_key(VK_VOLUME_MUTE, count=1)
                return reply, None
            elif action == 'volume_unmute':
                _press_key(VK_VOLUME_MUTE, count=1)
                return reply, None

        # 2. Динамические команды
        if text.startswith('найди '):
            query = text[6:].strip()
            if query:
                url = self._search_urls.get(self._search_engine, self._search_urls['google']) + query
                self._open_url(url)
                return f'Ищу: {query}', None

        if text.startswith('включи ') or text.startswith('открой '):
            app_name = text.split(' ', 1)[1].strip()
            return f'Не знаю, где найти {app_name}. Добавь в commands.toml.', None

        return 'Не поняла команду.', None

    @staticmethod
    def _launch(path: str) -> bool:
        """
        Запускает внешнее приложение.
        Args:
            path: Путь к исполняемому файлу.

        Returns:
            True, если удалось запустить, иначе False.
        """

        if not path:
            return False

        expanded_path = os.path.expandvars(path)

        # Проверяем, существует ли файл (отрезаем аргументы командной строки, если есть)
        base_path = expanded_path.split(' --')[0].strip('"')

        if not os.path.exists(base_path):
            log.warning(f'Файл не найден: {base_path}')
            return False

        try:
            if ' ' in expanded_path:
                subprocess.Popen(expanded_path, shell=True)
            else:
                subprocess.Popen([expanded_path])
            log.info(f'Запущено: {expanded_path}')
            return True
        except Exception:
            log.exception(f'Ошибка запуска {expanded_path}')
            return False

    def _open_url(self, url: str) -> None:
        """
        Открывает URL в браузере.
        Args:
            url: Адрес для открытия.
        """

        if not url:
            return
        try:
            if self._browser == 'system':
                webbrowser.open(url)
            else:
                exe = _BROWSER_PATHS.get(self._browser)
                if exe and os.path.exists(exe):
                    subprocess.Popen([exe, url])
                else:
                    webbrowser.open(url)
        except Exception:
            log.exception(f'Ошибка открытия URL: {url}')
