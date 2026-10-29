""" Точка входа для приложения настроек DesktopPet """

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config import APP_NAME, APP_VERSION, ICON_FILE
from logger import setup_logging
from settings_window import SettingsWindow


def main() -> int:
    """
    Запускает приложение настроек.

    Returns:
        Код выхода приложения.
    """

    setup_logging(app_tag='SETTINGS')

    app = QApplication(sys.argv)
    app.setApplicationName(f'{APP_NAME} Settings')
    app.setApplicationVersion(APP_VERSION)

    if ICON_FILE.exists():
        app.setWindowIcon(QIcon(str(ICON_FILE)))

    window = SettingsWindow()
    window.show()

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
