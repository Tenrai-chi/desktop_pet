""" Модуль распознавания голоса с использованием Vosk """

import json
import logging
import queue
import threading
import time
from pathlib import Path

import sounddevice
from PySide6.QtCore import QObject, Signal
from vosk import KaldiRecognizer, Model

log = logging.getLogger(__name__)


class VoiceListener(QObject):
    """
    Слушает микрофон по требованию.
    Загружает модель Vosk в фоновом потоке при старте. Запись и распознавание
    также происходят в отдельном потоке, чтобы не блокировать интерфейс.
    """

    recognized = Signal(str)  # распознанный текст
    failed = Signal(str)  # причина неудачи (нет микро, тишина и т.д.)
    model_ready = Signal(bool)  # True, если модель загрузилась

    def __init__(self, model_path: Path, sample_rate: int = 16000) -> None:
        """
        Инициализирует слушатель и запускает фоновую загрузку модели.

        Args:
            model_path: Путь к папке с моделью Vosk.
            sample_rate: Частота дискретизации микрофона (по умолчанию 16000).
        """

        super().__init__()
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._model = None
        self._busy = threading.Lock()

        # Загрузка модели в фоне, чтобы не морозить интерфейс
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self) -> None:
        """ Загружает модель Vosk из файловой системы в фоновом потоке """

        if not self._model_path.exists():
            log.error(f'Модель не найдена: {self._model_path}')
            self.model_ready.emit(False)
            return
        try:
            log.info('Загрузка модели Vosk...')
            self._model = Model(str(self._model_path))
            log.info('Модель Vosk загружена.')
            self.model_ready.emit(True)
        except Exception:
            log.exception('Ошибка загрузки модели Vosk')
            self.model_ready.emit(False)

    def listen_once(self, duration: float = 5.0) -> None:
        """
        Запускает запись и распознавание речи в отдельном потоке.

        Args:
            duration: Длительность записи в секундах.
        """

        if not self._busy.acquire(blocking=False):
            log.debug('Прослушивание уже идёт.')
            return

        if self._model is None:
            self._busy.release()
            self.failed.emit('Голосовая модель не загружена.')
            return

        threading.Thread(target=self._do_listen, args=(duration,), daemon=True).start()

    def _do_listen(self, duration: float) -> None:
        """
        Записывает звук с микрофона и передает его в Vosk.

        Args:
            duration: Длительность записи в секундах.
        """

        try:
            q = queue.Queue()

            def callback(indata, frames, time_info, status):
                q.put(bytes(indata))

            try:
                sounddevice.query_devices(kind='input')
            except Exception as e:
                log.error(f'Микрофон не найден: {e}')
                self.failed.emit('Микрофон не найден.')
                return

            with sounddevice.RawInputStream(
                    samplerate=self._sample_rate, blocksize=8000,
                    dtype='int16', channels=1, callback=callback
            ):
                recognizer = KaldiRecognizer(self._model, self._sample_rate)
                start_time = time.perf_counter()

                while time.perf_counter() - start_time < duration:
                    try:
                        data = q.get(timeout=0.1)
                        recognizer.AcceptWaveform(data)
                    except queue.Empty:
                        pass

                result = json.loads(recognizer.FinalResult())
                text = result.get('text', '').strip().lower()

                if text:
                    log.info('Распознано: %r', text)
                    self.recognized.emit(text)
                else:
                    self.failed.emit('Ничего не расслышала.')
        except Exception as e:
            log.exception('Ошибка при прослушивании')
            self.failed.emit(f'Ошибка записи: {e}')
        finally:
            self._busy.release()
