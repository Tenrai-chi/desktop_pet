import ctypes
import logging
from ctypes import wintypes

import win32gui
import win32process
from PySide6.QtCore import QObject, QTimer, Signal


log = logging.getLogger(__name__)


# Константы WinAPI. Берём минимум — только то, что нужно.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MAX_PATH = 260


def _get_process_name(pid: int) -> str | None:
    """Возвращает имя exe-файла процесса (например, 'chrome.exe').

    Использует QueryFullProcessImageNameW — работает без прав администратора
    для процессов текущего пользователя. Возвращает None для системных
    процессов, к которым нет доступа.
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
    """Имя exe-процесса, чьё окно сейчас в фокусе. None, если не удалось."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid == 0:
        return None
    return _get_process_name(pid)


class WindowWatcher(QObject):
    """Периодически опрашивает активное окно, шлёт сигнал при смене процесса."""

    process_changed = Signal(str)

    def __init__(self, poll_interval_ms: int = 1000, parent: QObject | None = None):
        super().__init__(parent)
        self._last_process: str | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(poll_interval_ms)

    def _poll(self) -> None:
        process = get_active_process_name()
        if process is None or process == self._last_process:
            return
        self._last_process = process
        log.debug("Активный процесс: %s", process)
        self.process_changed.emit(process)

    def stop(self) -> None:
        self._timer.stop()