import ctypes
import logging
from ctypes import wintypes

import win32gui
import win32process
from PySide6.QtCore import QObject, QTimer, Signal

from config import BROWSER_PROCESSES, BROWSER_SITES

log = logging.getLogger(__name__)


# Константы WinAPI. Берём минимум — только то, что нужно.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MAX_PATH = 260


def _get_process_name(pid: int) -> str | None:
    """
    Возвращает имя исполняемого файла процесса (например, 'chrome.exe').
    Использует QueryFullProcessImageNameW. Работает без прав администратора
    для процессов текущего пользователя. Возвращает None для системных
    процессов, к которым нет доступа.

    Args:
        pid: Идентификатор процесса (Process ID).

    Returns:
        Имя файла процесса в нижнем регистре или None в случае ошибки.
    """

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(_MAX_PATH)
        size = wintypes.DWORD(_MAX_PATH)
        ok = kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size),
        )
        if not ok:
            return None
        full_path = buffer.value
        return full_path.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(handle)


def get_active_process_name() -> str | None:
    """
    Возвращает имя exe-процесса, чье окно сейчас в фокусе.

    Returns:
        Имя процесса или None, если получить не удалось.
    """

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid == 0:
        return None
    return _get_process_name(pid)


def get_active_window_title() -> str | None:
    """
    Возвращает заголовок активного окна.

    Returns:
        Заголовок окна или None, если получить не удалось.
    """

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    title = win32gui.GetWindowText(hwnd)
    return title or None


def detect_site(title: str | None) -> str:
    """
    Ищет в заголовке окна известный сайт.

    Args:
        title: Заголовок окна браузера.

    Returns:
        Ключ сайта (например, 'youtube') или пустая строка, если сайт не распознан.
    """

    if not title:
        return ''
    title_lower = title.lower()
    for site, patterns in BROWSER_SITES.items():
        if any(p in title_lower for p in patterns):
            return site
    return ''


class WindowWatcher(QObject):
    """Периодически опрашивает активное окно, отправляя сигналы при изменениях."""

    process_changed = Signal(str)
    site_changed = Signal(str)

    def __init__(self, poll_interval_ms: int = 1000, parent: QObject | None = None) -> None:
        """
        Инициализирует наблюдатель за окнами.

        Args:
            poll_interval_ms: Интервал опроса в миллисекундах.
            parent: Родительский QObject.
        """

        super().__init__(parent)
        self._last_process: str | None = None
        self._last_site: str = ''
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(poll_interval_ms)

    def _poll(self) -> None:
        """ Опрашивает активное окно и генерирует сигналы при изменениях """

        process = get_active_process_name()

        if process is not None and process != self._last_process:
            self._last_process = process
            log.debug(f'Активный процесс: {process}')
            self.process_changed.emit(process)

        # Сайт определяем только для браузеров
        site = ''
        if process in BROWSER_PROCESSES:
            title = get_active_window_title()
            site = detect_site(title)
            # log.debug(f'Браузер: заголовок={title}, сайт={site}')

        if site != self._last_site:
            self._last_site = site
            log.debug(f'Активный сайт: {site}')
            self.site_changed.emit(site)

    def stop(self) -> None:
        """ Останавливает таймер опроса """

        self._timer.stop()
