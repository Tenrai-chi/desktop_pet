""" Конфигурация приложения: пути, настройки по умолчанию и их чтение/запись """

import json
import logging
import os
import sys
from pathlib import Path

APP_NAME = 'DesktopPet'
APP_VERSION = '0.3.0'

log = logging.getLogger(__name__)


# ---- Пути и директории ----
def is_frozen() -> bool:
    """
    Проверяет, запущено ли приложение из скомпилированного exe-файла.
    Returns:
        True, если приложение запущено как exe (PyInstaller), иначе False.
    """

    return getattr(sys, 'frozen', False)


def _project_root() -> Path:
    """
    Возвращает путь к корневой папке проекта (только при разработке).
    Returns:
        Путь к папке, в которой лежит config.py.
    """

    return Path(__file__).parent


def resources_dir() -> Path:
    """
    Возвращает папку с ресурсами (спрайты, звуки, реплики и тд).
    * Режим разработки — корень проекта.
    * Exe-файл — папка, куда установлено приложение.
    Returns:
        Путь к директории ресурсов.
    """

    if is_frozen():
        return Path(sys.executable).parent
    return _project_root()


def user_data_dir() -> Path:
    """
    Возвращает папку для записи данных пользователя.

    * Режим разработки — корень проекта.
    * Exe-файл — системная папка пользователя (%APPDATA%/DesktopPet_v0.1).

    Вычисляется вручную по переменным окружения, без QStandardPaths,
    чтобы не зависеть от порядка инициализации QApplication.

    Returns:
        Путь к папке с пользовательскими данными.
    """

    if is_frozen():
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        path = base / APP_NAME
    else:
        path = _project_root()

    path.mkdir(parents=True, exist_ok=True)
    return path


# ---- ПУТИ К РЕСУРСАМ ----

RESOURCES_DIR = resources_dir()
ASSETS_DIR = RESOURCES_DIR / 'assets'
MODELS_DIR = ASSETS_DIR / 'models'
VOSK_MODEL_PATH = MODELS_DIR / 'vosk-model-small-ru-0.22'

ICON_FILE = ASSETS_DIR / 'icon.ico'
COMMANDS_FILE = ASSETS_DIR / 'commands.toml'

# ---- Спрайты ----
SPRITES_DIR = ASSETS_DIR / 'sprites'
IDLE_DIR = SPRITES_DIR / 'idle'
DRAG_DIR = SPRITES_DIR / 'drag'
WALK_DIR = SPRITES_DIR / 'walk'
MUSIC_DIR = SPRITES_DIR / 'music'
VIDEO_DIR = SPRITES_DIR / 'video'
KISS_DIR = SPRITES_DIR / 'kiss'
POTION_DIR = SPRITES_DIR / 'potion'

APPEAR_DIR = SPRITES_DIR / 'appear'
APPEAR_CENTER_DIR = APPEAR_DIR / 'center'
APPEAR_LEFT_DIR = APPEAR_DIR / 'left'
APPEAR_RIGHT_DIR = APPEAR_DIR / 'right'

FALL_DIR = SPRITES_DIR / 'fall'
FALL_FALLING_DIR = FALL_DIR / 'falling'
FALL_LANDING_NORMAL_DIR = FALL_DIR / 'landing_normal'
FALL_LANDING_MAGIC_DIR = FALL_DIR / 'landing_magic'

# ---- Звуки и реплики ----
SOUNDS_DIR = ASSETS_DIR / 'sounds'
REACTIONS_FILE = ASSETS_DIR / 'reactions.toml'

# ---- Файлы пользователя ----
SETTINGS_PATH = user_data_dir() / 'settings.json'
LOG_FILE = user_data_dir() / 'logs.txt'


# ---- Браузеры и сайты ----
BROWSER_PROCESSES = {
    'chrome.exe',
    'msedge.exe',
    'firefox.exe',
    'opera.exe',
}

BROWSER_SITES: dict[str, list[str]] = {
    'youtube': ['youtube'],
    'twitch': ['twitch'],
    'netflix': ['netflix'],
}

# Сайты, где контент — видео. Если такой сайт активен и медиа играет,
# показываем анимацию просмотра, даже если GSMTC вернул 'music'.
VIDEO_SITES = {'youtube', 'twitch', 'netflix',}


# ---- Значения по умолчанию ----
_DEFAULTS: dict = {
    # Персонаж
    'pet_scale': 1.0,  # размер персонажа 1.0 -> 256x256
    'pet_start_position': 'right',

    # Мониторы
    'use_all_screens': True,
    'pet_monitor_index': 0,

    # Анимации
    'idle_fps': 11.0,
    'drag_fps': 12.0,
    'fall_fps': 22.0,
    'walk_fps': 6.0,
    'tick_interval_ms': 16,

    # Анимация прослушивания музыки
    'music_enabled': True,
    'music_fps': 8.0,
    'media_poll_interval_ms': 2000,

    # Анимация просмотра видео
    'video_enabled': True,
    'video_fps': 8.0,

    # Реакции
    'reactions_enabled': True,
    'reactions_poll_interval_ms': 1000,
    'reactions_text_enabled': True,
    'reactions_sound_enabled': False,

    # Реплики
    'bubble_max_width': 240,
    'bubble_offset_y': 8,
    'bubble_default_duration': 3.0,

    # Физика перетаскивания
    'speed_start': 350.0,
    'speed_stop': 120.0,
    'speed_zero_ms': 80,
    'direction_min_speed': 50.0,
    'speed_ema_alpha': 0.5,

    # Физика падения
    'gravity': 2500.0,
    'max_fall_speed': 2200.0,
    'hard_fall_threshold': 400.0,
    'landing_slowdown_distance': 150.0,
    'landing_slowdown_speed': 400.0,

    # Ходьба и idle
    'walk_speed': 80.0,
    'walk_duration_min': 3.0,
    'walk_duration_max': 7.0,
    'idle_wait_min': 4.0,
    'idle_wait_max': 12.0,

    # Веса IDLE событий
    'idle_weight_walk': 60,
    'idle_weight_kiss': 25,
    'idle_weight_potion': 15,

    # Голосовые команды
    'voice_enabled': False,
    'voice_input_device': '',
    'voice_listen_duration': 5.0,
    'voice_sample_rate': 16000,
    'voice_browser': 'system',
    'voice_search_engine': 'google',

    # Звук (для вывода реплик)
    'sound_volume': 0.8,
    'sound_output_device': '',

    # Голос — способы активации
    'voice_activation_middle': True,
    'voice_activation_hotkey': False,
    'voice_hotkey': 'Ctrl+Alt+F',
}


# ---- Чтение / запись settings.json ----
def _write_settings_file(settings: dict) -> None:
    """
    Записывает настройки в файл settings.json.

    Args:
        settings: Словарь с настройками для сохранения.
    """

    payload = dict(settings)
    payload['_version'] = 1

    SETTINGS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def _read_settings_file() -> dict:
    """
    Читает settings.json. Создает файл со значениями по умолчанию, если его нет.
    Returns:
        Словарь с настройками.
    """

    if not SETTINGS_PATH.exists():
        _write_settings_file(_DEFAULTS)
        log.info(f'Создан файл настроек: {SETTINGS_PATH}')
        return dict(_DEFAULTS)

    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        log.warning(f'Не удалось прочитать {SETTINGS_PATH}: {e}')
        log.info('Использую значения по умолчанию. Файл не перезаписываю.')
        return dict(_DEFAULTS)

    # Убираем служебные ключи перед слиянием
    raw.pop('_version', None)

    merged = {key: raw.get(key, default) for key, default in _DEFAULTS.items()}

    # Новые ключи — дополняем файл
    if set(merged) != set(raw):
        _write_settings_file(merged)
        log.info(f'settings.json дополнен новыми полями')

    return merged


def save_settings(new_values: dict) -> None:
    """
    Сохраняет настройки при вызове из GUI.
    Неизвестные ключи отбрасываются, недостающие берутся из _DEFAULTS.

    Args:
        new_values: Словарь с новыми значениями настроек.
    """

    merged = {key: new_values.get(key, default) for key, default in _DEFAULTS.items()}
    _write_settings_file(merged)
    log.info(f'Настройки сохранены: {SETTINGS_PATH}')


def get_settings_snapshot() -> dict:
    """
    Возвращает копию текущих настроек — для GUI
    Returns:
        Словарь с текущими настройками.
    """

    return dict(_settings)


def reset_to_defaults() -> None:
    """ Сбрасывает настройки к значениям по умолчанию """

    _write_settings_file(_DEFAULTS)
    log.info('Настройки сброшены к значениям по умолчанию')


# Загрузка настроек при импорте модуля
_settings = _read_settings_file()

# ---- ПУБЛИЧНЫЕ КОНСТАНТЫ ----

# Персонаж
PET_SCALE: float = _settings['pet_scale']
PET_START_POSITION: str = _settings['pet_start_position']

# Мониторы
USE_ALL_SCREENS: bool = _settings['use_all_screens']
PET_MONITOR_INDEX: int = _settings['pet_monitor_index']

# Анимации
IDLE_FPS: float = _settings['idle_fps']
DRAG_FPS: float = _settings['drag_fps']
FALL_FPS: float = _settings['fall_fps']
WALK_FPS: float = _settings['walk_fps']
TICK_INTERVAL_MS: int = _settings['tick_interval_ms']

# Реплики
BUBBLE_MAX_WIDTH: int = _settings['bubble_max_width']
BUBBLE_OFFSET_Y: int = _settings['bubble_offset_y']
BUBBLE_DEFAULT_DURATION: float = _settings['bubble_default_duration']

# Перетаскивание
SPEED_START: float = _settings['speed_start']
SPEED_STOP: float = _settings['speed_stop']
SPEED_ZERO_MS: int = _settings['speed_zero_ms']
DIRECTION_MIN_SPEED: float = _settings['direction_min_speed']
SPEED_EMA_ALPHA: float = _settings['speed_ema_alpha']

# Физика падения
GRAVITY: float = _settings['gravity']
MAX_FALL_SPEED: float = _settings['max_fall_speed']
HARD_FALL_THRESHOLD: float = _settings['hard_fall_threshold']
LANDING_SLOWDOWN_DISTANCE: float = _settings['landing_slowdown_distance']
LANDING_SLOWDOWN_SPEED: float = _settings['landing_slowdown_speed']

# Ходьба и idle
WALK_SPEED: float = _settings['walk_speed']
WALK_DURATION_MIN: float = _settings['walk_duration_min']
WALK_DURATION_MAX: float = _settings['walk_duration_max']
IDLE_WAIT_MIN: float = _settings['idle_wait_min']
IDLE_WAIT_MAX: float = _settings['idle_wait_max']

# Веса событий в idle. Значение = относительная вероятность.
# Сюда добавлять новые события
IDLE_EVENT_WEIGHTS: dict[str, float] = {
    'walk': _settings['idle_weight_walk'],
    'kiss': _settings['idle_weight_kiss'],
    'potion': _settings['idle_weight_potion'],
}

# Реакции
REACTIONS_ENABLED: bool = _settings['reactions_enabled']
REACTIONS_POLL_INTERVAL_MS: int = _settings['reactions_poll_interval_ms']
REACTIONS_TEXT_ENABLED: bool = _settings["reactions_text_enabled"]
REACTIONS_SOUND_ENABLED: bool = _settings["reactions_sound_enabled"]

# Прослушивание музыки
MUSIC_ENABLED: bool = _settings['music_enabled']
MUSIC_FPS: float = _settings['music_fps']
MEDIA_POLL_INTERVAL_MS: int = _settings['media_poll_interval_ms']

# Просмотр видео
VIDEO_ENABLED: bool = _settings['video_enabled']
VIDEO_FPS: float = _settings['video_fps']

# Голос
VOICE_ENABLED: bool = _settings['voice_enabled']
VOICE_INPUT_DEVICE: str = _settings['voice_input_device']
VOICE_LISTEN_DURATION: float = _settings['voice_listen_duration']
VOICE_SAMPLE_RATE: int = _settings['voice_sample_rate']
VOICE_SEARCH_ENGINE: str = _settings['voice_search_engine']

SOUND_VOLUME: float = _settings['sound_volume']
SOUND_OUTPUT_DEVICE: str = _settings['sound_output_device']
VOICE_ACTIVATION_MIDDLE: bool = _settings['voice_activation_middle']
VOICE_ACTIVATION_HOTKEY: bool = _settings['voice_activation_hotkey']
VOICE_HOTKEY: str = _settings['voice_hotkey']

VOICE_BROWSER: str = _settings['voice_browser']

# Фиксированные (не настраиваются пользователем)
KISS_FPS: float = 10.0
APPEAR_FPS: float = 12.0
POTION_FPS: float = 10.0
