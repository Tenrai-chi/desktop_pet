""" Модуль распознавания голоса с использованием Vosk """

import json
import logging
import numpy as np
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

    def __init__(self, model_path: Path, sample_rate: int = 16000, input_device: str = '') -> None:
        """
        Инициализирует слушатель и запускает фоновую загрузку модели.

        Args:
            model_path: Путь к папке с моделью Vosk.
            sample_rate: Частота дискретизации микрофона (по умолчанию 16000).
            input_device: Имя входного устройства
        """

        super().__init__()
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._input_device = input_device
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
            # 1. Определяем нужное устройство (по имени из настроек или системное)
            device_idx = None
            if self._input_device:
                for i, dev in enumerate(sounddevice.query_devices()):
                    if dev['name'] == self._input_device and dev['max_input_channels'] > 0:
                        device_idx = i
                        break

            if device_idx is None:
                # Берем индекс устройства ввода по умолчанию
                device_idx = sounddevice.default.device[0]

            if device_idx is None or device_idx < 0:
                self.failed.emit('Микрофон не найден.')
                return

            # 2. Узнаем частоту микрофона (безопасно получаем словарь)
            if device_idx is not None:
                dev_info = sounddevice.query_devices(device_idx)
            else:
                dev_info = sounddevice.query_devices(kind='input')

            native_sr = int(dev_info['default_samplerate'])
            log.info(f'Запись с устройства: {dev_info["name"]} ({native_sr} Гц)')

            q = queue.Queue()

            def callback(indata, frames, time_info, status):
                q.put(indata.copy())

            # Открываем поток на родной частоте микрофона
            with sounddevice.InputStream(
                    samplerate=native_sr,
                    blocksize=0,
                    device=device_idx,
                    channels=1,
                    dtype='int16',
                    callback=callback
            ):
                recognizer = KaldiRecognizer(self._model, self._sample_rate)
                start_time = time.perf_counter()

                while time.perf_counter() - start_time < duration:
                    try:
                        data = q.get(timeout=0.1)
                        flat_data = data.flatten()

                        # 3. Если частота не 16000, делаем ресемплинг
                        if native_sr != self._sample_rate:
                            flat_data = self._resample(flat_data, native_sr, self._sample_rate)

                        recognizer.AcceptWaveform(flat_data.tobytes())
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

    @staticmethod
    def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """ Линейная интерполяция для приведения частоты дискретизации  """

        duration = len(data) / orig_sr
        time_old = np.linspace(0, duration, len(data))
        time_new = np.linspace(0, duration, int(len(data) * target_sr / orig_sr))
        resampled = np.interp(time_new, time_old, data)
        return resampled.astype(np.int16)