""" Модуль приложения для запуска виртуального питомца """

import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from command_handler import CommandHandler
from config import (
    APP_NAME,
    APP_VERSION,
    COMMANDS_FILE,
    ICON_FILE,
    MEDIA_POLL_INTERVAL_MS,
    MUSIC_ENABLED,
    PET_MONITOR_INDEX,
    PET_SCALE,
    PET_START_POSITION,
    REACTIONS_ENABLED,
    REACTIONS_FILE,
    REACTIONS_POLL_INTERVAL_MS,
    SOUND_OUTPUT_DEVICE,
    SOUND_VOLUME,
    SOUNDS_DIR,
    TICK_INTERVAL_MS,
    USE_ALL_SCREENS,
    VIDEO_ENABLED,
    VOICE_ACTIVATION_HOTKEY,
    VOICE_BROWSER,
    VOICE_ENABLED,
    VOICE_HOTKEY,
    VOICE_SAMPLE_RATE,
    VOICE_SEARCH_ENGINE,
    VOSK_MODEL_PATH,
)
from hotkey_listener import HotkeyListener
from loads_media import load_all
from logger import setup_logging
from media_watcher import MediaWatcher
from pet_widget import PetWidget
from reactions import ReactionBook
from render import init_pygame_offscreen, shutdown_pygame
from sound_player import SoundPlayer
from tray import TrayIcon
from voice_listener import VoiceListener
from window_watcher import WindowWatcher

log = logging.getLogger(__name__)


def main() -> int | None:
    """
    Точка входа приложения.

    Инициализирует Qt, pygame, загружает ресурсы, настраивает
    наблюдатели и запускает цикл событий.

    Returns:
        Код выхода приложения.

    """

    setup_logging()
    log.info(f'Запуск {APP_NAME} v{APP_VERSION}')
    try:
        app = QApplication(sys.argv)

        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        if ICON_FILE.exists():
            app.setWindowIcon(QIcon(str(ICON_FILE)))
        app.aboutToQuit.connect(shutdown_pygame)

        init_pygame_offscreen()

        animations = load_all()

        reactions = ReactionBook()
        reactions.load(REACTIONS_FILE)

        sounds = SoundPlayer(
            SOUNDS_DIR / 'replicas',
            volume=SOUND_VOLUME,
            output_device=SOUND_OUTPUT_DEVICE,
        )

        pet = PetWidget(
            animations=animations,
            reactions=reactions,
            sounds=sounds,
            tick_ms=TICK_INTERVAL_MS,
            scale=PET_SCALE,
            start_position=PET_START_POSITION,
            use_all_screens=USE_ALL_SCREENS,
            monitor_index=PET_MONITOR_INDEX,
        )
        pet.show()

        # Голосовые команды
        if VOICE_ENABLED:
            voice_listener = VoiceListener(VOSK_MODEL_PATH, VOICE_SAMPLE_RATE)
            command_handler = CommandHandler(
                COMMANDS_FILE,
                search_engine=VOICE_SEARCH_ENGINE,
                browser=VOICE_BROWSER
            )

            voice_listener.recognized.connect(pet.on_voice_command)
            voice_listener.failed.connect(pet.on_voice_failed)

            pet.set_voice_modules(voice_listener, command_handler)
            log.info('Голосовой модуль подключен')

            # Горячая клавиша
            if VOICE_ACTIVATION_HOTKEY:
                hotkey_listener = HotkeyListener(VOICE_HOTKEY)
                # Устанавливаем фильтр на уровне приложения
                app.installNativeEventFilter(hotkey_listener)

                if hotkey_listener.register():
                    hotkey_listener.triggered.connect(pet._start_voice_listening)
                    # Отписываемся при выходе
                    app.aboutToQuit.connect(hotkey_listener.unregister)

        # Иконка в области уведомлений
        tray = TrayIcon()
        tray.toggle_pet_requested.connect(
            lambda: _toggle_pet(pet, tray)
        )
        tray.quit_requested.connect(pet.shutdown)
        app.aboutToQuit.connect(tray.hide)

        window_watcher = None
        if REACTIONS_ENABLED:
            window_watcher = WindowWatcher(poll_interval_ms=REACTIONS_POLL_INTERVAL_MS)
            window_watcher.process_changed.connect(pet.react)
            window_watcher.site_changed.connect(pet.set_browser_site)
            app.aboutToQuit.connect(window_watcher.stop)

        media_watcher = None
        if MUSIC_ENABLED or VIDEO_ENABLED:
            media_watcher = MediaWatcher(
                poll_interval_ms=MEDIA_POLL_INTERVAL_MS,
            )
            media_watcher.media_state_changed.connect(
                pet.set_media_state
            )
            app.aboutToQuit.connect(media_watcher.stop)
        log.info(f'Запуск приложения прошел успешно')
        return app.exec()
    except Exception as error:
        log.exception(f'Произошла ошибка: {error}')
        return None


def _toggle_pet(pet, tray) -> None:
    """
    Показывает или скрывает питомца.

    Args:
        pet: Экземпляр виджета питомца.
        tray: Экземпляр иконки в трее.
    """

    if pet.isVisible():
        pet.hide()
        tray.set_pet_visible(False)
        log.info('Питомец скрыт')
    else:
        pet.show()
        tray.set_pet_visible(True)
        log.info('Питомец показан')


if __name__ == '__main__':
    sys.exit(main())
