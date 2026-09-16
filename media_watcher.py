import asyncio
import logging
import threading

from PySide6.QtCore import QObject, Signal


log = logging.getLogger(__name__)

_STATUS_PLAYING = 4
_TYPE_UNKNOWN = 0
_TYPE_MUSIC = 1
_TYPE_VIDEO = 2
_TYPE_IMAGE = 3

_TYPE_NAMES = {
    _TYPE_UNKNOWN: 'unknown',
    _TYPE_MUSIC: 'music',
    _TYPE_VIDEO: 'video',
    _TYPE_IMAGE: 'image',
}


class MediaWatcher(QObject):
    """ Периодически читает GSMTC, эмитит сигнал при смене состояния """

    # media_type: 'music' | 'video' | 'image' | 'unknown'
    # is_playing: True, если статус PLAYING
    media_state_changed = Signal(str, bool)

    def __init__(self, poll_interval_ms: int = 2000, parent: QObject | None = None):
        super().__init__(parent)
        self._interval_sec = poll_interval_ms / 1000.0
        self._stop = threading.Event()
        self._last_state: tuple[str, bool] | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # Общее
    def stop(self) -> None:
        """ Останавливает фоновый поток """
        
        self._stop.set()

    # Фоновый поток
    def _run(self) -> None:
        try:
            asyncio.run(self._poll_loop())
        except Exception:
            log.exception('MediaWatcher упал')

    async def _poll_loop(self) -> None:
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        )

        try:
            manager = await SessionManager.request_async()
        except Exception:
            log.exception('Не удалось получить GSMTC-менеджер')
            return

        log.info('MediaWatcher запущен, интервал %.1f с', self._interval_sec)

        while not self._stop.is_set():
            try:
                state = await self._read_state(manager)
            except Exception:
                log.exception('Ошибка чтения медиа-сессии')
                state = ('unknown', False)

            if state != self._last_state:
                self._last_state = state
                media_type, is_playing = state
                self.media_state_changed.emit(media_type, is_playing)

            await asyncio.sleep(self._interval_sec)

    @staticmethod
    async def _read_state(manager) -> tuple[str, bool]:
        """ Читает текущую сессию и возвращает (media_type, is_playing) """
        
        session = manager.get_current_session()
        if session is None:
            return 'unknown', False

        playback = session.get_playback_info()
        is_playing = int(playback.playback_status) == _STATUS_PLAYING

        props = await session.try_get_media_properties_async()
        media_type = _TYPE_NAMES.get(int(props.playback_type), 'unknown')

        return media_type, is_playing
