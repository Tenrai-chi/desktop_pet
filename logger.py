""" Модуль настройки логирования приложения """

import logging
import sys

from config import LOG_FILE, is_frozen


def setup_logging(app_tag: str = 'PET') -> None:
    """
    Настраивает корневое логирование без дублирования обработчиков.

    Args:
        app_tag: Префикс приложения в логах ('PET' для питомца,
                 'SETTINGS' для окна настроек). По умолчанию 'PET'.
    """
    
    root = logging.getLogger()
    if root.handlers:
        return

    if is_frozen():
        handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        level = logging.INFO
    else:
        handler = logging.StreamHandler(sys.stderr)
        level = logging.DEBUG

    # Все строки получают префикс [PET] или [SETTINGS]
    fmt = f'%(asctime)s [%(levelname)s] [{app_tag}] %(message)s'
    handler.setFormatter(
        logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S')
    )

    root.setLevel(level)
    root.addHandler(handler)

    logging.getLogger('PySide6').setLevel(logging.WARNING)
    logging.getLogger('pygame').setLevel(logging.WARNING)
    logging.getLogger('vosk').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('sounddevice').setLevel(logging.WARNING)
