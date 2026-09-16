import sys
import logging

from PySide6.QtWidgets import QApplication

from config import (
    APP_VERSION,
    PET_SCALE,
    PET_SPAN_ALL_SCREENS,
    PET_START_POSITION,
    REACTIONS_ENABLED,
    REACTIONS_FILE,
    REACTIONS_POLL_INTERVAL_MS,
    SOUNDS_DIR,
    TICK_INTERVAL_MS,
    APP_NAME,
    MEDIA_POLL_INTERVAL_MS,
    MUSIC_ENABLED,
    VIDEO_ENABLED,
)
from media_watcher import MediaWatcher

from render import init_pygame_offscreen, shutdown_pygame
from logger import setup_logging
from pet_widget import PetWidget
from reactions import ReactionBook
from sound_player import SoundPlayer
from window_watcher import WindowWatcher
from loads_media import (
    load_idle_animation,
    load_drag_animation,
    load_falling_animation,
    load_landing_normal_animation,
    load_landing_magic_animation,
    load_walk_animation,
    load_music_animation,
    load_video_animation,
)

log = logging.getLogger(__name__)


def main() -> int | None:
    setup_logging()
    log.info(f'Запуск {APP_NAME} v{APP_VERSION}')
    try:
        app = QApplication(sys.argv)

        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        app.aboutToQuit.connect(shutdown_pygame)

        init_pygame_offscreen()
        idle_animation = load_idle_animation()
        drag_right_animation = load_drag_animation('right')
        drag_left_animation = load_drag_animation('left')
        falling_animation = load_falling_animation()
        landing_normal_animation = load_landing_normal_animation()
        landing_magic_animation = load_landing_magic_animation()
        walk_right_anim = load_walk_animation('right')
        walk_left_anim = load_walk_animation('left')
        music_animation = load_music_animation()
        video_animation = load_video_animation()

        reactions = ReactionBook()
        reactions.load(REACTIONS_FILE)

        sounds = SoundPlayer(SOUNDS_DIR / 'replicas')

        pet = PetWidget(
            idle=idle_animation,
            drag_right=drag_right_animation,
            drag_left=drag_left_animation,
            falling=falling_animation,
            landing_normal=landing_normal_animation,
            landing_magic=landing_magic_animation,
            walk_right=walk_right_anim,
            walk_left=walk_left_anim,
            music=music_animation,
            video=video_animation,
            reactions=reactions,
            sounds=sounds,
            tick_ms=TICK_INTERVAL_MS,
            scale=PET_SCALE,
            start_position=PET_START_POSITION,
            span_all_screens=PET_SPAN_ALL_SCREENS
        )
        pet.show()

        window_watcher = None
        if REACTIONS_ENABLED:
            window_watcher = WindowWatcher(poll_interval_ms=REACTIONS_POLL_INTERVAL_MS)
            window_watcher.process_changed.connect(pet.react)
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


if __name__ == '__main__':
    sys.exit(main())
