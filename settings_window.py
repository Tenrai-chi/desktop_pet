""" Модуль окна настроек приложения """

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSlider, QSpinBox, QStackedWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

import config
from config import (
    APP_NAME, APP_VERSION, ASSETS_DIR, LOG_FILE, SETTINGS_PATH, SOUNDS_DIR,
)
from reference import html_reference


log = logging.getLogger(__name__)


# ---- Вспомогательные функции ----
def _open_path_in_explorer(path: Path) -> None:
    """
    Открывает папку или файл в Проводнике (или ассоциированном редакторе).

    Args:
        path: Путь к файлу или директории.
    """

    if not path.exists():
        QMessageBox.warning(None, 'Не найдено', f'Файл или папка не существует:\n{path}')
        return
    try:
        import os
        os.startfile(str(path))
    except OSError as e:
        QMessageBox.warning(None, 'Ошибка', f'Не удалось открыть:\n{e}')


def _get_pet_command() -> list[str] | None:
    """
    Возвращает команду для запуска питомца.

    Returns:
        Список аргументов для subprocess.Popen или None, если путь не найден.
    """

    if getattr(sys, 'frozen', False):
        pet_exe = Path(sys.executable).parent / f'{APP_NAME}.exe'
        if pet_exe.exists():
            return [str(pet_exe)]
        return None

    main_py = Path(__file__).parent / 'main.py'
    if main_py.exists():
        return [sys.executable, str(main_py)]
    return None


def _kill_pet_process() -> None:
    """ Убивает запущенный процесс питомца (только в режиме exe) """

    if not getattr(sys, 'frozen', False):
        log.info('dev-режим: убийство процесса питомца пропущено')
        return

    exe_name = f'{APP_NAME}.exe'

    # 0x08000000 — это числовое значение флага CREATE_NO_WINDOW (скрывает окно cmd)
    creation_flags = 0x08000000 if sys.platform == 'win32' else 0

    try:
        # УБРАЛИ флаг /T! Теперь убиваем ТОЛЬКО сам процесс питомца, не трогая настройки
        result = subprocess.run(
            ['taskkill', '/F', '/IM', exe_name],
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags
        )

        if result.returncode == 0:
            log.info(f'Процесс {exe_name} успешно завершен.')
        else:
            log.warning(
                f'Не удалось завершить {exe_name} (Код: {result.returncode}). '
                f'Возможно, он уже закрыт. {result.stdout.strip()}'
            )

    except Exception:
        log.exception(f'Ошибка при вызове taskkill для {exe_name}')


class RecordHotkeyDialog(QDialog):
    """ Диалог для записи новой горячей клавиши. """

    def __init__(self, parent=None) -> None:
        """
        Инициализирует диалог.

        Args:
            parent: Родительский виджет.
        """

        super().__init__(parent)
        self.setWindowTitle('Запись комбинации')
        self.setFixedSize(320, 120)
        self.hotkey = None

        layout = QVBoxLayout(self)
        label = QLabel('Нажмите нужную комбинацию клавиш...\n(Например, Ctrl+Alt+F)')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def keyPressEvent(self, event):
        """
        Перехватывает нажатия клавиш для формирования хоткея.

        Args:
            event: Событие нажатия клавиши.
        """

        # Игнорируем нажатия самих модификаторов
        if event.key() in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier: parts.append('Ctrl')
        if modifiers & Qt.KeyboardModifier.AltModifier: parts.append('Alt')
        if modifiers & Qt.KeyboardModifier.ShiftModifier: parts.append('Shift')
        if modifiers & Qt.KeyboardModifier.MetaModifier: parts.append('Win')

        # Требуем хотя бы один модификатор
        if not parts:
            return

        key_str = event.text().upper() if event.text() else ''
        if not key_str:
            if Qt.Key.Key_F1 <= event.key() <= Qt.Key.Key_F12:
                key_str = f'F{event.key() - Qt.Key.Key_F1 + 1}'
            else:
                return

        parts.append(key_str)
        self.hotkey = '+'.join(parts)
        self.accept()


# ---- Главное окно настроек ----
class SettingsWindow(QDialog):
    """ Главное окно настроек. """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f'Настройки {APP_NAME} v{APP_VERSION}')
        self.setMinimumSize(800, 620)
        self._set_window_icon()

        # Снимок текущих значений — отсюда заполняем поля
        self._initial = config.get_settings_snapshot()

        # Собираем UI
        self._tabs = QListWidget()
        self._tabs.setFixedWidth(180)
        self._stack = QStackedWidget()

        self._tabs.addItems([
            'Внешний вид',
            'Анимации',
            'IDLE-поведение',
            'Реакции',
            'Ввод и вывод',
            'Дополнительно',
        ])
        self._tabs.currentRowChanged.connect(self._stack.setCurrentIndex)

        self._stack.addWidget(self._build_appearance_tab())
        self._stack.addWidget(self._build_animations_tab())
        self._stack.addWidget(self._build_idle_tab())
        self._stack.addWidget(self._build_reactions_tab())
        self._stack.addWidget(self._build_io_tab())
        self._stack.addWidget(self._build_advanced_tab())

        self._tabs.setCurrentRow(0)

        # Правая часть: вкладки + нижняя панель
        right = QVBoxLayout()
        right.addWidget(self._stack, stretch=1)
        right.addLayout(self._build_bottom_bar())

        # Левая + правая
        main = QHBoxLayout(self)
        main.addWidget(self._tabs)
        main.addLayout(right, stretch=1)

        # Тестовый плеер для звука
        self._test_player: QMediaPlayer | None = None
        self._test_audio_out: QAudioOutput | None = None

    def _set_window_icon(self) -> None:
        """ Устанавливает иконку приложения """

        icon_path = ASSETS_DIR / 'icon.ico'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    # Вкладка 1: Внешний вид
    def _build_appearance_tab(self) -> QWidget:
        """ Создает вкладку внешнего вида """

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Размер питомца
        size_group = QGroupBox('Размер питомца')
        size_layout = QHBoxLayout(size_group)
        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setRange(30, 200)
        self._scale_slider.setValue(int(self._initial['pet_scale'] * 100))
        self._scale_label = QLabel(f'{self._initial["pet_scale"]:.2f}')
        self._scale_label.setFixedWidth(50)
        self._scale_slider.valueChanged.connect(
            lambda v: self._scale_label.setText(f'{v / 100:.2f}')
        )
        size_layout.addWidget(QLabel('0.3'))
        size_layout.addWidget(self._scale_slider, stretch=1)
        size_layout.addWidget(QLabel('2.0'))
        size_layout.addWidget(self._scale_label)
        layout.addWidget(size_group)

        # Стартовая позиция
        pos_group = QGroupBox('Стартовая позиция')
        pos_layout = QHBoxLayout(pos_group)
        self._pos_combo = QComboBox()
        self._pos_combo.addItems(['left', 'center', 'right'])
        current_pos = self._initial['pet_start_position']
        if current_pos in ('left', 'center', 'right'):
            self._pos_combo.setCurrentText(current_pos)
        pos_layout.addWidget(QLabel('Сторона:'))
        pos_layout.addWidget(self._pos_combo)
        pos_layout.addStretch()
        layout.addWidget(pos_group)

        # Мониторы
        mon_group = QGroupBox('Мониторы')
        mon_layout = QVBoxLayout(mon_group)
        self._all_screens_cb = QCheckBox('Использовать все мониторы')
        self._all_screens_cb.setChecked(self._initial['use_all_screens'])
        self._all_screens_cb.toggled.connect(self._on_all_screens_toggled)

        self._monitor_combo = QComboBox()
        screens = QApplication.screens()
        for i, screen in enumerate(screens):
            geo = screen.geometry()
            label = f'Монитор {i + 1} ({geo.width()}×{geo.height()})'
            if screen == QApplication.primaryScreen():
                label += ' — основной'
            self._monitor_combo.addItem(label, i)

        current_index = self._initial['pet_monitor_index']
        if 0 <= current_index < self._monitor_combo.count():
            self._monitor_combo.setCurrentIndex(current_index)

        self._monitor_combo.setEnabled(not self._initial['use_all_screens'])

        mon_layout.addWidget(self._all_screens_cb)
        mon_row = QHBoxLayout()
        mon_row.addWidget(QLabel('Монитор:'))
        mon_row.addWidget(self._monitor_combo)
        mon_row.addStretch()
        mon_layout.addLayout(mon_row)
        layout.addWidget(mon_group)

        # Облачко
        bubble_group = QGroupBox('Облачко с репликами')
        form = QFormLayout(bubble_group)

        self._bubble_width = QSpinBox()
        self._bubble_width.setRange(150, 500)
        self._bubble_width.setValue(self._initial['bubble_max_width'])
        self._bubble_width.setSuffix(' пикс')
        form.addRow('Ширина:', self._bubble_width)

        self._bubble_offset = QSpinBox()
        self._bubble_offset.setRange(0, 50)
        self._bubble_offset.setValue(self._initial['bubble_offset_y'])
        self._bubble_offset.setSuffix(' пикс')
        form.addRow('Отступ от питомца:', self._bubble_offset)

        self._bubble_duration = QDoubleSpinBox()
        self._bubble_duration.setRange(1.0, 10.0)
        self._bubble_duration.setSingleStep(0.5)
        self._bubble_duration.setValue(self._initial['bubble_default_duration'])
        self._bubble_duration.setSuffix(' сек')
        form.addRow('Время показа:', self._bubble_duration)

        layout.addWidget(bubble_group)
        layout.addStretch()
        return widget

    def _on_all_screens_toggled(self, checked: bool) -> None:
        """
        Включает/отключает выбор конкретного монитора.

        Args:
            checked: True, если выбраны все мониторы.
        """

        self._monitor_combo.setEnabled(not checked)

    # Вкладка 2: Анимации
    def _build_animations_tab(self) -> QWidget:
        """ Создает вкладку настроек анимаций """

        widget = QWidget()
        layout = QVBoxLayout(widget)

        fps_group = QGroupBox('Скорость анимаций (кадров в секунду)')
        form = QFormLayout(fps_group)

        self._fps_spins: dict[str, QDoubleSpinBox] = {}
        for key, label in [
            ('idle_fps', 'Покой (idle)'),
            ('drag_fps', 'Перетаскивание'),
            ('fall_fps', 'Приземление'),
            ('walk_fps', 'Ходьба'),
            ('music_fps', 'Прослушивание музыки'),
            ('video_fps', 'Просмотр видео'),
        ]:
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 60.0)
            spin.setSingleStep(0.5)
            spin.setDecimals(1)
            spin.setValue(self._initial[key])
            self._fps_spins[key] = spin
            form.addRow(label + ':', spin)

        layout.addWidget(fps_group)

        # Тик
        tick_group = QGroupBox('Игровой цикл')
        tick_form = QFormLayout(tick_group)
        self._tick_spin = QSpinBox()
        self._tick_spin.setRange(8, 33)
        self._tick_spin.setValue(self._initial['tick_interval_ms'])
        self._tick_spin.setSuffix(' мс')
        tick_form.addRow('Интервал тика:', self._tick_spin)
        layout.addWidget(tick_group)

        # Медиа
        media_group = QGroupBox('Медиа')
        media_layout = QVBoxLayout(media_group)
        self._music_enabled_cb = QCheckBox('Прослушивание музыки')
        self._music_enabled_cb.setChecked(self._initial['music_enabled'])
        self._video_enabled_cb = QCheckBox('Просмотр видео')
        self._video_enabled_cb.setChecked(self._initial['video_enabled'])
        media_layout.addWidget(self._music_enabled_cb)
        media_layout.addWidget(self._video_enabled_cb)

        media_form = QFormLayout()
        self._media_poll_spin = QSpinBox()
        self._media_poll_spin.setRange(500, 5000)
        self._media_poll_spin.setSingleStep(250)
        self._media_poll_spin.setValue(self._initial['media_poll_interval_ms'])
        self._media_poll_spin.setSuffix(' мс')
        media_form.addRow('Интервал проверки медиа:', self._media_poll_spin)
        media_layout.addLayout(media_form)

        layout.addWidget(media_group)
        layout.addStretch()
        return widget

    # Вкладка 3: Idle-поведение
    def _build_idle_tab(self) -> QWidget:
        """ Создает вкладку настроек IDLE-поведения """

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Паузы
        wait_group = QGroupBox('Пауза между событиями')
        wait_form = QFormLayout(wait_group)
        self._wait_min_spin = QDoubleSpinBox()
        self._wait_min_spin.setRange(1.0, 600.0)
        self._wait_min_spin.setValue(self._initial['idle_wait_min'])
        self._wait_min_spin.setSuffix(' сек')
        self._wait_max_spin = QDoubleSpinBox()
        self._wait_max_spin.setRange(1.0, 600.0)
        self._wait_max_spin.setValue(self._initial['idle_wait_max'])
        self._wait_max_spin.setSuffix(' сек')
        wait_form.addRow('Минимум:', self._wait_min_spin)
        wait_form.addRow('Максимум:', self._wait_max_spin)
        layout.addWidget(wait_group)

        # Веса
        weight_group = QGroupBox('Вероятности событий')
        weight_layout = QVBoxLayout(weight_group)
        hint = QLabel(
            'Относительные веса в процентах. 0 — событие отключено.\n'
            'Если все нули — питомец просто стоит.'
        )
        hint.setStyleSheet('color: #666; font-size: 11px;')
        weight_layout.addWidget(hint)

        weight_form = QFormLayout()
        self._weight_spins: dict[str, QDoubleSpinBox] = {}
        for key, label in [
            ('idle_weight_walk', 'Прогулка'),
            ('idle_weight_kiss', 'Поцелуй'),
            ('idle_weight_potion', 'Зелье'),
        ]:
            spin = QDoubleSpinBox()
            spin.setRange(0, 100)
            spin.setSingleStep(5)
            spin.setSuffix(' %')
            spin.setValue(self._initial[key])
            self._weight_spins[key] = spin
            weight_form.addRow(label + ':', spin)
        weight_layout.addLayout(weight_form)
        layout.addWidget(weight_group)

        # Ходьба
        walk_group = QGroupBox('Ходьба')
        walk_form = QFormLayout(walk_group)
        self._walk_speed_spin = QSpinBox()
        self._walk_speed_spin.setRange(20, 300)
        self._walk_speed_spin.setValue(int(self._initial['walk_speed']))
        self._walk_speed_spin.setSuffix(' пикс/с')
        walk_form.addRow('Скорость ходьбы:', self._walk_speed_spin)

        self._walk_min_spin = QDoubleSpinBox()
        self._walk_min_spin.setRange(1.0, 60.0)
        self._walk_min_spin.setValue(self._initial['walk_duration_min'])
        self._walk_min_spin.setSuffix(' сек')
        walk_form.addRow('Длительность (мин):', self._walk_min_spin)

        self._walk_max_spin = QDoubleSpinBox()
        self._walk_max_spin.setRange(1.0, 60.0)
        self._walk_max_spin.setValue(self._initial['walk_duration_max'])
        self._walk_max_spin.setSuffix(' сек')
        walk_form.addRow('Длительность (макс):', self._walk_max_spin)

        layout.addWidget(walk_group)
        layout.addStretch()
        return widget

    # Вкладка 4: Реакции
    def _build_reactions_tab(self) -> QWidget:
        """ Создает вкладку настроек реакций """

        widget = QWidget()
        layout = QVBoxLayout(widget)

        react_group = QGroupBox('Реакции на приложения и сайты')
        react_layout = QVBoxLayout(react_group)

        self._reactions_enabled_cb = QCheckBox('Реакции включены')
        self._reactions_enabled_cb.setChecked(self._initial['reactions_enabled'])

        self._reactions_text_cb = QCheckBox('Текстовые реплики')
        self._reactions_text_cb.setChecked(self._initial['reactions_text_enabled'])

        self._reactions_sound_cb = QCheckBox('Звуковые реплики')
        self._reactions_sound_cb.setChecked(self._initial['reactions_sound_enabled'])

        react_layout.addWidget(self._reactions_enabled_cb)
        react_layout.addWidget(self._reactions_text_cb)
        react_layout.addWidget(self._reactions_sound_cb)

        poll_form = QFormLayout()
        self._reactions_poll_spin = QSpinBox()
        self._reactions_poll_spin.setRange(200, 5000)
        self._reactions_poll_spin.setSingleStep(100)
        self._reactions_poll_spin.setValue(self._initial['reactions_poll_interval_ms'])
        self._reactions_poll_spin.setSuffix(' мс')
        poll_form.addRow('Интервал опроса окон:', self._reactions_poll_spin)
        react_layout.addLayout(poll_form)

        edit_btn = QPushButton('Открыть reactions.toml…')
        edit_btn.clicked.connect(
            lambda: _open_path_in_explorer(config.REACTIONS_FILE)
        )
        react_layout.addWidget(edit_btn)

        layout.addWidget(react_group)
        layout.addStretch()
        return widget

    # Вкладка 5: Ввод и вывод
    def _build_io_tab(self) -> QWidget:
        """ Создает вкладку настроек ввода и вывода """

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Голос
        voice_group = QGroupBox('Голосовые команды')
        voice_layout = QVBoxLayout(voice_group)

        self._voice_enabled_cb = QCheckBox('Включить голосовые команды')
        self._voice_enabled_cb.setChecked(self._initial['voice_enabled'])
        self._voice_enabled_cb.toggled.connect(self._on_voice_toggled)
        voice_layout.addWidget(self._voice_enabled_cb)

        # Способы активации
        act_layout = QHBoxLayout()
        act_layout.addWidget(QLabel('Способы активации:'))
        self._act_middle_cb = QCheckBox('Клик колёсиком')
        self._act_middle_cb.setChecked(self._initial['voice_activation_middle'])
        self._act_hotkey_cb = QCheckBox('Горячая клавиша')
        self._act_hotkey_cb.setChecked(self._initial['voice_activation_hotkey'])
        act_layout.addWidget(self._act_middle_cb)
        act_layout.addWidget(self._act_hotkey_cb)
        act_layout.addStretch()
        voice_layout.addLayout(act_layout)

        # Горячие клавиши
        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(QLabel('Комбинация:'))
        self._hotkey_edit = QLineEdit(self._initial['voice_hotkey'])
        self._hotkey_edit.setReadOnly(True)
        hotkey_layout.addWidget(self._hotkey_edit, stretch=1)
        record_btn = QPushButton('Записать…')
        record_btn.setToolTip('Нажмите, чтобы задать новую комбинацию')
        record_btn.clicked.connect(self._record_hotkey)
        hotkey_layout.addWidget(record_btn)
        voice_layout.addLayout(hotkey_layout)

        # Микрофон
        mic_layout = QHBoxLayout()
        mic_layout.addWidget(QLabel('Микрофон:'))
        self._mic_combo = QComboBox()
        self._mic_combo.addItem('Системное по умолчанию', '')
        try:
            for dev in QMediaDevices.audioInputs():
                self._mic_combo.addItem(dev.description(), dev.description())
        except Exception:
            log.warning('Не удалось получить список микрофонов')
        current_mic = self._initial['voice_input_device']
        for i in range(self._mic_combo.count()):
            if self._mic_combo.itemData(i) == current_mic:
                self._mic_combo.setCurrentIndex(i)
                break
        mic_layout.addWidget(self._mic_combo, stretch=1)
        mic_test_btn = QPushButton('Тест 2 сек')
        mic_test_btn.setToolTip('Будет доступно после подключения Vosk')
        mic_test_btn.setEnabled(False)
        mic_layout.addWidget(mic_test_btn)
        voice_layout.addLayout(mic_layout)

        # Длительность запроса
        voice_form = QFormLayout()
        self._voice_duration_spin = QDoubleSpinBox()
        self._voice_duration_spin.setRange(2.0, 15.0)
        self._voice_duration_spin.setValue(self._initial['voice_listen_duration'])
        self._voice_duration_spin.setSuffix(' сек')
        voice_form.addRow('Длительность запроса:', self._voice_duration_spin)

        # Поисковик
        self._search_engine_combo = QComboBox()
        self._search_engine_combo.addItem('Google', 'google')
        self._search_engine_combo.addItem('Яндекс', 'yandex')
        self._search_engine_combo.addItem('Bing', 'bing')
        self._search_engine_combo.addItem('DuckDuckGo', 'duckduckgo')
        current_search = self._initial['voice_search_engine']
        for i in range(self._search_engine_combo.count()):
            if self._search_engine_combo.itemData(i) == current_search:
                self._search_engine_combo.setCurrentIndex(i)
                break
        voice_form.addRow('Поисковик:', self._search_engine_combo)

        # Браузер
        self._browser_combo = QComboBox()
        self._browser_combo.addItem('Системный по умолчанию', 'system')
        self._browser_combo.addItem('Google Chrome', 'chrome')
        self._browser_combo.addItem('Mozilla Firefox', 'firefox')
        self._browser_combo.addItem('Microsoft Edge', 'edge')
        self._browser_combo.addItem('Яндекс Браузер', 'yandex')
        self._browser_combo.addItem('Opera', 'opera')
        self._browser_combo.addItem('Brave', 'brave')
        current_browser = self._initial['voice_browser']
        for i in range(self._browser_combo.count()):
            if self._browser_combo.itemData(i) == current_browser:
                self._browser_combo.setCurrentIndex(i)
                break
        voice_form.addRow('Браузер для поиска:', self._browser_combo)

        voice_layout.addLayout(voice_form)
        layout.addWidget(voice_group)

        # Звук
        sound_group = QGroupBox('Вывод звука')
        sound_layout = QVBoxLayout(sound_group)

        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel('Устройство:'))
        self._out_combo = QComboBox()
        self._out_combo.addItem('Системное по умолчанию', '')
        try:
            for dev in QMediaDevices.audioOutputs():
                self._out_combo.addItem(dev.description(), dev.description())
        except Exception:
            log.warning('Не удалось получить список устройств вывода')
        current_out = self._initial['sound_output_device']
        for i in range(self._out_combo.count()):
            if self._out_combo.itemData(i) == current_out:
                self._out_combo.setCurrentIndex(i)
                break
        out_layout.addWidget(self._out_combo, stretch=1)

        test_sound_btn = QPushButton('Тест')
        test_sound_btn.clicked.connect(self._test_sound)
        out_layout.addWidget(test_sound_btn)
        sound_layout.addLayout(out_layout)

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel('Громкость:'))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(int(self._initial['sound_volume'] * 100))
        self._volume_label = QLabel(f"{int(self._initial['sound_volume'] * 100)}%")
        self._volume_label.setFixedWidth(45)
        self._volume_slider.valueChanged.connect(
            lambda v: self._volume_label.setText(f'{v}%')
        )
        vol_layout.addWidget(self._volume_slider, stretch=1)
        vol_layout.addWidget(self._volume_label)
        sound_layout.addLayout(vol_layout)

        layout.addWidget(sound_group)
        layout.addStretch()

        self._on_voice_toggled(self._initial['voice_enabled'])
        return widget

    def _on_voice_toggled(self, enabled: bool) -> None:
        """
        Блокирует или разблокирует поля голосовых настроек.

        Args:
            enabled: Включены ли голосовые команды.
        """

        voice_dependent_widgets = [
            self._act_middle_cb,
            self._act_hotkey_cb,
            self._hotkey_edit,
            self._mic_combo,
            self._voice_duration_spin,
            self._search_engine_combo,
            self._browser_combo,
        ]

        for widget in voice_dependent_widgets:
            widget.setEnabled(enabled)

    def _test_sound(self) -> None:
        """ Проигрывает короткий WAV на выбранном устройстве. """

        if not SOUNDS_DIR.exists():
            QApplication.beep()
            return

        wavs = list(SOUNDS_DIR.rglob('*.wav'))
        if not wavs:
            log.info('WAV-файлов нет, использую системный beep')
            QApplication.beep()
            return

        wav_path = wavs[0]
        device_name = self._out_combo.currentData()

        # Останавливаем предыдущий тест
        if self._test_player is not None:
            self._test_player.stop()

        if not device_name:
            # Системное устройство — QSoundEffect быстрее, но здесь
            # используем QMediaPlayer ради единообразия
            device = QMediaDevices.defaultAudioOutput()
        else:
            device = None
            for dev in QMediaDevices.audioOutputs():
                if dev.description() == device_name:
                    device = dev
                    break

        if device is None:
            QMessageBox.warning(self, 'Звук', f'Устройство не найдено:\n{device_name}')
            return

        self._test_audio_out = QAudioOutput(device)
        self._test_audio_out.setVolume(self._volume_slider.value() / 100.0)

        self._test_player = QMediaPlayer()
        self._test_player.setAudioOutput(self._test_audio_out)
        self._test_player.setSource(QUrl.fromLocalFile(str(wav_path)))
        self._test_player.play()

    # Вкладка 6: Дополнительно
    def _build_advanced_tab(self) -> QWidget:
        """ Создает вкладку с дополнительными настройками и обслуживанием """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        tools_group = QGroupBox('Обслуживание')
        tools_layout = QVBoxLayout(tools_group)

        btn_settings = QPushButton('Открыть папку с настройками')
        btn_settings.clicked.connect(lambda: _open_path_in_explorer(SETTINGS_PATH.parent))
        tools_layout.addWidget(btn_settings)

        btn_logs = QPushButton('Открыть logs.txt')
        btn_logs.clicked.connect(lambda: _open_path_in_explorer(LOG_FILE))
        tools_layout.addWidget(btn_logs)

        btn_install = QPushButton('Открыть папку установки')
        install_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        btn_install.clicked.connect(lambda: _open_path_in_explorer(install_dir))
        tools_layout.addWidget(btn_install)

        btn_help = QPushButton('📖 Открыть справку')
        btn_help.setStyleSheet('font-size: 14px; padding: 10px; font-weight: bold;')
        btn_help.clicked.connect(self._show_help_dialog)
        layout.addWidget(btn_help)

        tools_layout.addSpacing(15)

        btn_reset = QPushButton('Сбросить всё к значениям по умолчанию')
        btn_reset.setStyleSheet('color: #a00;')
        btn_reset.clicked.connect(self._on_reset_clicked)
        tools_layout.addWidget(btn_reset)

        layout.addWidget(tools_group)

        # Информация
        info_group = QGroupBox('О приложении')
        info_layout = QVBoxLayout(info_group)
        info_layout.addWidget(QLabel(f'{APP_NAME} v{APP_VERSION}'))
        info_layout.addWidget(QLabel('© Tenrai Production'))
        layout.addWidget(info_group)

        layout.addStretch()
        return widget

    def _on_reset_clicked(self) -> None:
        """ Сбрасывает настройки к значениям по умолчанию (с подтверждением) """
        reply = QMessageBox.question(
            self, 'Сброс настроек',
            'Все настройки будут сброшены к значениям по умолчанию.\n'
            'Продолжить?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        config.reset_to_defaults()
        QMessageBox.information(
            self, 'Готово',
            'Настройки сброшены. Перезапустите питомца, чтобы применить.'
        )
        # Обновить поля — проще всего перезапустить окно
        self._initial = config.get_settings_snapshot()
        self._reload_fields_from_snapshot()

    def _reload_fields_from_snapshot(self) -> None:
        """ Обновляет все поля из self._initial после сброса. """
        self._initial = config.get_settings_snapshot()

        # Внешний вид
        self._scale_slider.setValue(int(self._initial['pet_scale'] * 100))
        self._pos_combo.setCurrentText(self._initial['pet_start_position'])
        self._all_screens_cb.setChecked(self._initial['use_all_screens'])
        self._monitor_combo.setCurrentIndex(self._initial['pet_monitor_index'])
        self._bubble_width.setValue(self._initial['bubble_max_width'])
        self._bubble_offset.setValue(self._initial['bubble_offset_y'])
        self._bubble_duration.setValue(self._initial['bubble_default_duration'])

        # Анимации
        for key, spin in self._fps_spins.items():
            spin.setValue(self._initial[key])
        self._tick_spin.setValue(self._initial['tick_interval_ms'])
        self._music_enabled_cb.setChecked(self._initial['music_enabled'])
        self._video_enabled_cb.setChecked(self._initial['video_enabled'])
        self._media_poll_spin.setValue(self._initial['media_poll_interval_ms'])

        # Idle
        self._wait_min_spin.setValue(self._initial['idle_wait_min'])
        self._wait_max_spin.setValue(self._initial['idle_wait_max'])
        for key, spin in self._weight_spins.items():
            spin.setValue(int(self._initial[key]))
        self._walk_speed_spin.setValue(int(self._initial['walk_speed']))
        self._walk_min_spin.setValue(self._initial['walk_duration_min'])
        self._walk_max_spin.setValue(self._initial['walk_duration_max'])

        # Реакции
        self._reactions_enabled_cb.setChecked(self._initial['reactions_enabled'])
        self._reactions_text_cb.setChecked(self._initial['reactions_text_enabled'])
        self._reactions_sound_cb.setChecked(self._initial['reactions_sound_enabled'])
        self._reactions_poll_spin.setValue(self._initial['reactions_poll_interval_ms'])

        # Ввод-вывод
        self._voice_enabled_cb.setChecked(self._initial['voice_enabled'])
        self._act_middle_cb.setChecked(self._initial['voice_activation_middle'])
        self._act_hotkey_cb.setChecked(self._initial['voice_activation_hotkey'])
        self._hotkey_edit.setText(self._initial['voice_hotkey'])
        self._voice_duration_spin.setValue(self._initial['voice_listen_duration'])
        self._volume_slider.setValue(int(self._initial['sound_volume'] * 100))

    # Нижняя панель
    def _build_bottom_bar(self) -> QHBoxLayout:
        """ Создает нижнюю панель с кнопками управления """

        layout = QHBoxLayout()
        layout.addWidget(QLabel(f'Файл настроек: {SETTINGS_PATH.name}'))
        layout.addStretch()

        btn_cancel = QPushButton('Отмена')
        btn_cancel.clicked.connect(self.reject)

        btn_apply = QPushButton('Применить')
        btn_apply.clicked.connect(self._on_apply)

        btn_restart = QPushButton('Перезапустить питомца')
        btn_restart.clicked.connect(self._on_restart_pet)

        btn_ok = QPushButton('OK')
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)

        layout.addWidget(btn_cancel)
        layout.addWidget(btn_apply)
        layout.addWidget(btn_restart)
        layout.addWidget(btn_ok)
        return layout

    # ---- Сбор значений и сохранение ----
    def _collect_values(self) -> dict:
        """
        Собирает значения из всех полей в словарь для config.save_settings.

        Returns:
            Словарь с новыми настройками.
        """

        values = dict(self._initial)

        # Внешний вид
        values['pet_scale'] = self._scale_slider.value() / 100.0
        values['pet_start_position'] = self._pos_combo.currentText()
        values['use_all_screens'] = self._all_screens_cb.isChecked()
        values['pet_monitor_index'] = self._monitor_combo.currentData()
        values['bubble_max_width'] = self._bubble_width.value()
        values['bubble_offset_y'] = self._bubble_offset.value()
        values['bubble_default_duration'] = self._bubble_duration.value()

        # Анимации
        for key, spin in self._fps_spins.items():
            values[key] = spin.value()
        values['tick_interval_ms'] = self._tick_spin.value()
        values['music_enabled'] = self._music_enabled_cb.isChecked()
        values['video_enabled'] = self._video_enabled_cb.isChecked()
        values['media_poll_interval_ms'] = self._media_poll_spin.value()

        # Idle
        wait_min = self._wait_min_spin.value()
        wait_max = self._wait_max_spin.value()
        if wait_min > wait_max:
            wait_min, wait_max = wait_max, wait_min
        values['idle_wait_min'] = wait_min
        values['idle_wait_max'] = wait_max

        for key, spin in self._weight_spins.items():
            values[key] = spin.value()

        values['walk_speed'] = float(self._walk_speed_spin.value())
        walk_min = self._walk_min_spin.value()
        walk_max = self._walk_max_spin.value()
        if walk_min > walk_max:
            walk_min, walk_max = walk_max, walk_min
        values['walk_duration_min'] = walk_min
        values['walk_duration_max'] = walk_max

        # Реакции
        values['reactions_enabled'] = self._reactions_enabled_cb.isChecked()
        values['reactions_text_enabled'] = self._reactions_text_cb.isChecked()
        values['reactions_sound_enabled'] = self._reactions_sound_cb.isChecked()
        values['reactions_poll_interval_ms'] = self._reactions_poll_spin.value()

        # Ввод-вывод
        values['voice_enabled'] = self._voice_enabled_cb.isChecked()
        values['voice_activation_middle'] = self._act_middle_cb.isChecked()
        values['voice_activation_hotkey'] = self._act_hotkey_cb.isChecked()
        values['voice_hotkey'] = self._hotkey_edit.text()
        values['voice_input_device'] = self._mic_combo.currentData() or ''
        values['voice_listen_duration'] = self._voice_duration_spin.value()
        values['voice_search_engine'] = self._search_engine_combo.currentData()
        values['voice_browser'] = self._browser_combo.currentData()
        values['sound_output_device'] = self._out_combo.currentData() or ''
        values['sound_volume'] = self._volume_slider.value() / 100.0

        return values

    def _on_apply(self) -> None:
        """ Сохраняет настройки и обновляет снимок self._initial """

        values = self._collect_values()
        config.save_settings(values)
        self._initial = values
        QMessageBox.information(
            self, 'Сохранено',
            'Настройки сохранены.\n'
            'Если питомец запущен — перезапустите его, чтобы применить изменения.'
        )

    def _on_ok(self) -> None:
        """ Сохраняет настройки и закрывает окно """

        values = self._collect_values()
        config.save_settings(values)
        self.accept()

    def _on_restart_pet(self) -> None:
        """Сохраняет настройки и перезапускает питомца."""
        values = self._collect_values()
        config.save_settings(values)
        self._initial = values

        pet_cmd = _get_pet_command()
        if pet_cmd is None:
            QMessageBox.warning(
                self, 'Ошибка',
                f'Не удалось найти {APP_NAME}.exe или main.py.\n'
                'Запустите питомца вручную.'
            )
            return

        _kill_pet_process()

        # Увеличиваем паузу до 2 секунд, чтобы Windows гарантированно
        # освободила exe-файл перед запуском нового
        QTimer.singleShot(2000, lambda: self._launch_pet(pet_cmd))

    def _launch_pet(self, cmd: list[str]) -> None:
        """
        Запускает процесс питомца.

        Args:
            cmd: Команда для subprocess.Popen.
        """

        try:
            if sys.platform == 'win32':
                # 0x08000000 (CREATE_NO_WINDOW) + 0x00000008 (DETACHED_PROCESS)
                # DETACHED_PROCESS отвязывает нового питомца от процесса настроек
                creation_flags = 0x08000000 | 0x00000008
            else:
                creation_flags = 0

            subprocess.Popen(cmd, creationflags=creation_flags)
            log.info(f'Питомец перезапущен: {cmd}')
        except Exception as e:
            log.exception('Не удалось запустить питомца')
            QMessageBox.critical(self, 'Ошибка', f'Не удалось запустить:\n{e}')

    def _record_hotkey(self):
        """ Открывает диалог записи горячей клавиши """

        dialog = RecordHotkeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.hotkey:
            self._hotkey_edit.setText(dialog.hotkey)

    def _show_help_dialog(self) -> None:
        """ Открывает окно с инструкцией """

        from PySide6.QtWidgets import QTextBrowser

        dialog = QDialog(self)
        dialog.setWindowTitle('Справка DesktopPet_v0.1')
        dialog.resize(700, 600)

        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html_reference)
        layout.addWidget(browser)

        # Кнопка "Закрыть"
        btn_close = QPushButton('Закрыть')
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()
