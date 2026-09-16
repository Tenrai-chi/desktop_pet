import logging
import os
import sys
import tomllib

from pathlib import Path

APP_NAME = 'DesktopPet'
APP_VERSION = '0.1.0'

log = logging.getLogger(__name__)


# Пути
def is_frozen() -> bool:
    """ True, если приложение запущено как исполняемый файл """

    return getattr(sys, 'frozen', False)


def _project_root() -> Path:
    """ Получение пути к корневой папке проекта """

    return Path(__file__).parent


def resources_dir() -> Path:
    """
    Папка с ресурсами: спрайты, музыка, реплики и тд.
    * Разработка — корень проекта.
    * Приложение — папка приложения, куда установлено.
    """
    if is_frozen():
        return Path(sys.executable).parent
    return _project_root()


def user_data_dir() -> Path:
    """
    Папка для записи данных пользователя.
    * Разработка — корень проекта.
    * Приложение — системная папка пользователя: %APPDATA%/DesktopPet
    Вычисляется вручную по переменным окружения, без QStandardPaths —
    чтобы не зависеть от порядка инициализации QApplication.
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

# Спрайты
SPRITES_DIR = ASSETS_DIR / 'sprites'
IDLE_DIR = SPRITES_DIR / 'idle'  # анимация бездействия
DRAG_DIR = SPRITES_DIR / 'drag'  # анимация перетягивания
WALK_DIR = SPRITES_DIR / 'walk'  # анимация ходьбы
MUSIC_DIR = SPRITES_DIR / 'music'  # анимация прослушивания музыки
VIDEO_DIR = SPRITES_DIR / 'video'  # анимация просмотра видео

FALL_DIR = SPRITES_DIR / 'fall'
FALL_FALLING_DIR = FALL_DIR / 'falling'  # анимация падения
FALL_LANDING_NORMAL_DIR = FALL_DIR / 'landing_normal'  # обычное приземление при небольшой высоте
FALL_LANDING_MAGIC_DIR = FALL_DIR / 'landing_magic'  # магическое замедленное приземление

# Звуки
SOUNDS_DIR = ASSETS_DIR / 'sounds'

# Реплики
REACTIONS_FILE = ASSETS_DIR / 'reactions.toml'

# Файл настроек и логов пользователя
SETTINGS_PATH = user_data_dir() / 'settings.toml'
LOG_FILE = user_data_dir() / 'logs.txt'

# Значения по умолчанию.
# Меняются только при выпуске новой версии. Пользователь правит settings.toml
_DEFAULTS: dict = {
    # Персонаж
    'pet_scale': 1.0,  # размер персонажа 1.0 -> 256x256
    'pet_start_position': 'bottom-right',  # начальная позиция на мониторе
    'pet_span_all_screens': True,  # True - использовать все экраны, False - только основной

    # Анимации
    'idle_fps': 13.0,
    'drag_fps': 14.0,
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
    'reactions_enabled': True,  # выводить ли реакции на открытие приложений
    'reactions_poll_interval_ms': 1000,
    'reactions_text_enabled': True,  # текстовая реакция
    'reactions_sound_enabled': False,  # звуковая реакция

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
}


# Подсказки к каждому параметру в settings.toml
_SETTINGS_HELP: dict = {
    'pet_scale':
        'Масштаб спрайта. 0.5 — вдвое меньше, 1.0 — как в PNG, '
        '1.5 — крупнее. Значения больше 1.5 могут выглядеть размыто.',

    'pet_start_position':
        'Где появляется питомец при запуске. '
        'Варианты: bottom-center, bottom-left, bottom-right.',

    'pet_span_all_screens':
        'true — окно покрывает все мониторы; false — только основной.',

    'idle_fps':
        'Скорость анимации покоя, кадров в секунду.',

    'drag_fps':
        'Скорость анимации перетаскивания.',

    'fall_fps':
        'Скорость анимации приземления. Больше — короче и резче.',

    
    'walk_fps':
        "Скорость анимации ходьбы. Больше — быстрее перебирает лапами.",

    'tick_interval_ms':
        'Интервал игрового цикла в миллисекундах. 16 ≈ 60 FPS. '
        'Меньше 8 не имеет смысла, больше 33 — рывки.',

    'music_enabled':
        'true — питомец слушает музыку (проигрывает анимацию, когда играет '
        'музыка в браузере или плеере); false — отключить.',

    'music_fps':
        'Скорость анимации прослушивания музыки, кадров в секунду.',

    'media_poll_interval_ms':
        'Как часто проверять, играет ли музыка, миллисекунды. 2000 — раз в 2 секунды.',

    'video_enabled':
        'true — питомец смотрит видео вместе с хозяином (проигрывает '
        'отдельную анимацию, когда в браузере играет видео); false — отключить.',

    'video_fps':
        'Скорость анимации просмотра видео, кадров в секунду.',


    'reactions_enabled':
        'true — питомец реагирует на смену активного приложения; false — выключить.',

    'reactions_poll_interval_ms':
        'Как часто проверять активное окно, миллисекунды. 1000 — раз в секунду.',

    "reactions_text_enabled":
        "true — питомец показывает текстовые реплики при реакциях на "
        "приложения; false — только звук (или ничего).",

    "reactions_sound_enabled":
        "true — питомец проигрывает звуки при реакциях на приложения; "
        "false — только текст.",

    'bubble_max_width':
        'Максимальная ширина облачка с репликой, пиксели.',

    'bubble_offset_y':
        'Отступ облачка от питомца, пиксели.',

    'bubble_default_duration':
        'Сколько секунд облачко висит на экране по умолчанию.',

    'speed_start':
        'Порог скорости курсора (px/s), выше которого питомец '
        'ускоряется (играет анимацию 1-2-3).',

    'speed_stop':
        'Порог скорости курсора (px/s), ниже которого питомец '
        'тормозит (играет анимацию 3-4-5).',

    'speed_zero_ms':
        'Если мышь не двигалась столько миллисекунд — скорость '
        'считается нулевой. Питомец возвращается в покой даже '
        'с зажатой кнопкой мыши.',

    'direction_min_speed':
        'Минимальная горизонтальная скорость (px/s), при которой '
        'меняется направление спрайта (влево/вправо).',

    'speed_ema_alpha':
        'Сглаживание скорости курсора (EMA). 0.5 — компромисс. '
        'Меньше — плавнее, больше — резче.',

    'gravity':
        'Ускорение свободного падения, px/s². Больше — падает быстрее. '
        '2500 — падение с 400 px занимает около 0.55 с.',

    'max_fall_speed':
        'Максимальная скорость падения, px/s. Обрезает разгон, '
        'чтобы с большой высоты питомец не телепортировался.',

    'hard_fall_threshold':
        'Порог высоты падения (px), при котором срабатывает «жёсткое» '
        'приземление с отдельной анимацией. Ниже — обычное.',

    'landing_slowdown_distance':
        'За сколько пикселей до пола начинать замедление при большом '
        'падении. 0 — отключить замедление.',

    'landing_slowdown_speed':
        'До какой скорости (px/s) ограничивается падение в зоне замедления.',

    'walk_speed':
        'Скорость ходьбы питомца, px/s. 80 — спокойный шаг.',

    'walk_duration_min':
        'Минимальная длительность одной прогулки, секунды.',

    'walk_duration_max':
        'Максимальная длительность одной прогулки, секунды.',

    'idle_wait_min':
        'Минимальная пауза между прогулками, секунды.',

    'idle_wait_max':
        'Максимальная пауза между прогулками, секунды.',
}


# Запись / чтение settings.toml
def _format_toml_value(value) -> str:
    """
    Форматирует Python-значение как TOML-литерал.
    Поддерживает только плоские типы: bool, int, float, str.
    """

    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f'Неподдерживаемый тип в TOML: {type(value).__name__}')


def _wrap_comment(text: str, width: int = 78, prefix: str = '# ') -> list[str]:
    """ Разбивает длинный комментарий на строки по словам """

    words = text.split()
    lines: list[str] = []
    current = prefix
    for word in words:
        if len(current) + len(word) + 1 > width and current != prefix:
            lines.append(current.rstrip())
            current = prefix + word + ' '
        else:
            current += word + ' '
    if current.strip():
        lines.append(current.rstrip())
    return lines


def _write_settings(settings: dict) -> None:
    """ Пишет settings.toml: комментарий-подсказка над каждым ключом """

    lines: list[str] = [
        '# Настройки DesktopPet.',
        '# Файл можно редактировать вручную — изменения применятся',
        '# при следующем запуске приложения.',
        '',
    ]

    for key, value in settings.items():
        help_text = _SETTINGS_HELP.get(key)
        if help_text:
            lines.extend(_wrap_comment(help_text))
        lines.append(f'{key} = {_format_toml_value(value)}')
        lines.append('')

    SETTINGS_PATH.write_text('\n'.join(lines), encoding='utf-8')


def _load_settings() -> dict:
    """
    Читает settings.toml. Создаёт шаблон, если файла нет.
    Недостающие ключи берутся из _DEFAULTS. Если в файле чего-то не хватало,
    файл перезаписывается.
    """

    if not SETTINGS_PATH.exists():
        _write_settings(_DEFAULTS)
        log.info(f'Создан шаблон настроек: {SETTINGS_PATH}')
        return dict(_DEFAULTS)

    try:
        with SETTINGS_PATH.open('rb') as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        log.warning(f'Не удалось прочитать {SETTINGS_PATH}: {e}')
        log.info(f'Используются значения по умолчанию')
        return dict(_DEFAULTS)

    merged = {key: raw.get(key, default) for key, default in _DEFAULTS.items()}

    if set(merged) != set(raw):
        _write_settings(merged)
        log.info(f'settings.toml дополнен новыми полями: {SETTINGS_PATH}')
    return merged


_settings = _load_settings()

# Установка констант после слияния настроен из setting.toml

# Персонаж
PET_SCALE: float = _settings['pet_scale']
PET_START_POSITION: str = _settings['pet_start_position']
PET_SPAN_ALL_SCREENS: bool = _settings['pet_span_all_screens']

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

# Реакции
REACTIONS_ENABLED: bool = _settings['reactions_enabled']
REACTIONS_POLL_INTERVAL_MS: int = _settings['reactions_poll_interval_ms']
REACTIONS_TEXT_ENABLED: bool = _settings["reactions_text_enabled"]
REACTIONS_SOUND_ENABLED: bool = _settings["reactions_sound_enabled"]

# Реплики
BUBBLE_MAX_WIDTH: int = _settings['bubble_max_width']
BUBBLE_OFFSET_Y: int = _settings['bubble_offset_y']
BUBBLE_DEFAULT_DURATION: float = _settings['bubble_default_duration']

# Прослушивание музыки
MUSIC_ENABLED: bool = _settings['music_enabled']
MUSIC_FPS: float = _settings['music_fps']
MEDIA_POLL_INTERVAL_MS: int = _settings['media_poll_interval_ms']

# Просмотр видео
VIDEO_ENABLED: bool = _settings['video_enabled']
VIDEO_FPS: float = _settings['video_fps']
