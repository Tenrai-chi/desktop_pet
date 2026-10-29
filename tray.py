""" Модуль иконки в системном трее (уведомлениях) """

import logging
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from config import APP_NAME, ICON_FILE


log = logging.getLogger(__name__)


def _get_settings_command() -> list[str] | None:
    """
    Возвращает команду для запуска приложения настроек.

    В exe-режиме ищет рядом лежащий DesktopPetSettings.exe.
    В режиме разработки запускает settings_main.py.

    Returns:
        Список аргументов для subprocess.Popen или None, если путь не найден.
    """

    if getattr(sys, 'frozen', False):
        settings_exe = Path(sys.executable).parent / 'DesktopPetSettings.exe'
        if settings_exe.exists():
            return [str(settings_exe)]
        return None

    settings_py = Path(__file__).parent / 'settings_main.py'
    if settings_py.exists():
        return [sys.executable, str(settings_py)]
    return None


class TrayIcon(QObject):
    """ Иконка в трее с меню управления питомцем """

    toggle_pet_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        """
        Инициализирует иконку в трее.

        Args:
            parent: Родительский QObject.
        """

        super().__init__(parent)

        self._tray: QSystemTrayIcon | None = None
        self._pet_visible = True

        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning('Системный трей недоступен — иконка не будет создана')
            return

        self._build_tray()

    def _build_tray(self) -> None:
        """ Создает иконку и контекстное меню """

        icon_path = ICON_FILE
        if not icon_path.exists():
            log.warning(f'Иконка для трея не найдена: {icon_path}')
            icon = QIcon()
        else:
            icon = QIcon(str(icon_path))

        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip(APP_NAME)

        self._menu = QMenu()

        self._toggle_action = QAction('Скрыть питомца', self._menu)
        self._toggle_action.triggered.connect(self.toggle_pet_requested.emit)
        self._menu.addAction(self._toggle_action)

        self._menu.addSeparator()

        self._settings_action = QAction('Настройки…', self._menu)
        self._settings_action.triggered.connect(self._open_settings)
        self._menu.addAction(self._settings_action)

        self._menu.addSeparator()

        self._quit_action = QAction('Выход', self._menu)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._quit_action)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

        log.info('Иконка трея создана')

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """
        Обрабатывает клики по иконке в трее.

        Args:
            reason: Причина срабатывания события (одинарный клик, двойной и т.д.).
        """

        # Двойной клик — показать/скрыть питомца
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_pet_requested.emit()

    @staticmethod
    def _open_settings() -> None:
        """ Запускает приложение настроек """

        cmd = _get_settings_command()
        if cmd is None:
            log.error('Не удалось найти DesktopPetSettings.exe или settings_main.py')
            return

        try:
            subprocess.Popen(cmd)
            log.info(f'Открыто окно настроек: {cmd}', )
        except Exception:
            log.exception('Не удалось запустить настройки')

    def set_pet_visible(self, visible: bool) -> None:
        """ Обновляет текст пункта меню """

        self._pet_visible = visible
        if self._tray is not None:
            self._toggle_action.setText(
                'Скрыть питомца' if visible else 'Показать питомца'
            )

    def show_message(self, title: str, message: str) -> None:
        """ Показывает системное уведомление """

        if self._tray is not None:
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def hide(self) -> None:
        if self._tray is not None:
            self._tray.hide()
