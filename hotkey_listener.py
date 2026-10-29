""" Модуль перехвата глобальных горячих клавиш Windows """

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

log = logging.getLogger(__name__)

# Константы WinAPI
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# ID сообщения для горячих клавиш
WM_HOTKEY = 0x0312


def _parse_hotkey(hotkey_str: str) -> tuple[int, int] | None:
    """
    Парсит строку вида 'Ctrl+Alt+F' в модификаторы и код клавиши.

    Args:
        hotkey_str: Строковое представление комбинации (например, 'Ctrl+Alt+F').

    Returns:
        Кортеж (модификаторы, vk_code) или None, если формат неверный.
    """

    parts = [p.strip().lower() for p in hotkey_str.split('+')]
    if not parts:
        return None

    modifiers = 0
    vk = 0

    for part in parts:
        if part in ('ctrl', 'control'):
            modifiers |= MOD_CONTROL
        elif part == 'alt':
            modifiers |= MOD_ALT
        elif part == 'shift':
            modifiers |= MOD_SHIFT
        elif part in ('win', 'windows'):
            modifiers |= MOD_WIN
        else:
            # Это должна быть сама клавиша
            if len(part) == 1 and part.isalpha():
                vk = ord(part.upper())
            elif len(part) == 1 and part.isdigit():
                vk = ord(part)
            elif part.startswith('f') and part[1:].isdigit():
                f_num = int(part[1:])
                if 1 <= f_num <= 12:
                    vk = 0x70 + f_num - 1
                else:
                    return None
            else:
                return None

    if vk == 0 or modifiers == 0:
        return None
    return modifiers, vk


class HotkeyListener(QObject, QAbstractNativeEventFilter):
    """ Слушает глобальные связки клавиш для прослушивания и передает сигнал """

    triggered = Signal()

    def __init__(self, hotkey_str: str, hotkey_id: int = 1, parent=None) -> None:
        """
        Инициализирует слушатель горячих клавиш.

        Args:
            hotkey_str: Комбинация клавиш (например, 'Ctrl+Alt+F').
            hotkey_id: Уникальный идентификатор хоткея для Windows.
            parent: Родительский QObject.
        """

        super().__init__(parent)
        QAbstractNativeEventFilter.__init__(self)

        self._hotkey_id = hotkey_id
        self._hotkey_str = hotkey_str
        self._registered = False

        parsed = _parse_hotkey(hotkey_str)
        if not parsed:
            log.error(f'Неверный формат горячих клавиш: {hotkey_str}')
            self._modifiers, self._vk = 0, 0
        else:
            self._modifiers, self._vk = parsed

    def register(self) -> bool:
        """
        Регистрирует горячую клавишу в системе.

        Returns:
            True, если регистрация прошла успешно, иначе False.
        """

        if not self._vk:
            return False

        user32 = ctypes.windll.user32
        if user32.RegisterHotKey(None, self._hotkey_id, self._modifiers, self._vk):
            self._registered = True
            log.info(f'Комбинация клавиш {self._hotkey_str} успешно зарегистрирована', )
            return True
        else:
            log.warning(f'Не удалось зарегистрировать комбинацию клавиш {self._hotkey_str} (возможно, занят)')
            return False

    def unregister(self) -> None:
        """ Отменяет регистрацию горячей клавиши """

        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, self._hotkey_id)
            self._registered = False
            log.info('Комбинация клавиш отключена')

    def nativeEventFilter(self, eventType, message: None):
        """ Перехват системных сообщений Windows """

        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                log.debug('Комбинация клавиш нажата')
                self.triggered.emit()
                return True, 0
        return False, 0
