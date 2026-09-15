import logging
import sys

from config import is_frozen, LOG_FILE


def setup_logging() -> None:
    """ Настраивает корневое логирование без дублирования """
    
    root = logging.getLogger()
    if root.handlers:
        return

    if is_frozen():
        handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fmt = '%(asctime)s [%(levelname)s]: %(message)s'
        level = logging.INFO
    else:
        handler = logging.StreamHandler(sys.stderr)
        fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        level = logging.DEBUG

    handler.setFormatter(logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S'))

    root.setLevel(level)
    root.addHandler(handler)

    logging.getLogger('PySide6').setLevel(logging.WARNING)
    logging.getLogger('pygame').setLevel(logging.INFO)
