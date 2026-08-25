from __future__ import annotations

import sys
import time

from PySide6.QtCore import QObject, QEvent, QEasingCurve, QPoint, QRect, QRectF, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFontComboBox,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import (
    ALWAYS_TRACK_INFO_MODE,
    CARD_DISPLAY_STYLE,
    CURRENT_NEXT_LYRIC_LINES,
    CUSTOM_DISPLAY_PRESET,
    FLOATING_DISPLAY_STYLE,
    NEVER_TRACK_INFO_MODE,
    SINGLE_LYRIC_LINES,
    SPOTIFY_API_PLAYBACK_SOURCE,
    TRACK_CHANGE_INFO_MODE,
    AppConfig,
    WINDOWS_PLAYBACK_SOURCE,
    default_config,
    display_preset_for,
    display_preset_values,
)
from .models import TrackInfo


def shortcuts_guide_lines() -> list[tuple[str, str]]:
    return [
        ("Ctrl+R", "Reload playback"),
        ("Shift+C", "Toggle lyric color"),
        ("Shift+S", "Open or close settings"),
        ("Shift+F", "Hide overlay to tray"),
    ]


def shortcuts_guide_text() -> str:
    return "\n".join(f"{shortcut}  {description}" for shortcut, description in shortcuts_guide_lines())


def suppress_windows_native_frame(widget: QWidget) -> None:
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    try:
        hwnd = wintypes.HWND(int(widget.winId()))
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        ggw_style = -16
        ggw_exstyle = -20
        ws_caption = 0x00C00000
        ws_thickframe = 0x00040000
        ws_border = 0x00800000
        ws_dlgframe = 0x00400000
        ws_ex_dlgmodalframe = 0x00000001
        ws_ex_clientedge = 0x00000200
        ws_ex_staticedge = 0x00020000
        ws_ex_windowedge = 0x00000100
        ws_ex_appwindow = 0x00040000
        ws_ex_toolwindow = 0x00000080
        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_nozorder = 0x0004
        swp_noactivate = 0x0010
        swp_framechanged = 0x0020

        get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_window_long.restype = ctypes.c_ssize_t
        set_window_long.restype = ctypes.c_ssize_t

        style = get_window_long(hwnd, ggw_style)
        style &= ~(ws_caption | ws_thickframe | ws_border | ws_dlgframe)
        set_window_long(hwnd, ggw_style, style)

        exstyle = get_window_long(hwnd, ggw_exstyle)
        exstyle &= ~(ws_ex_dlgmodalframe | ws_ex_clientedge | ws_ex_staticedge | ws_ex_windowedge)
        exstyle &= ~ws_ex_appwindow
        exstyle |= ws_ex_toolwindow
        set_window_long(hwnd, ggw_exstyle, exstyle)

        user32.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            swp_nomove | swp_nosize | swp_nozorder | swp_noactivate | swp_framechanged,
        )

        ncrendering_disabled = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            2,  # DWMWA_NCRENDERING_POLICY
            ctypes.byref(ncrendering_disabled),
            ctypes.sizeof(ncrendering_disabled),
        )
        color_none = ctypes.c_uint(0xFFFFFFFE)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            34,  # DWMWA_BORDER_COLOR
            ctypes.byref(color_none),
            ctypes.sizeof(color_none),
        )
        corner_preference_do_not_round = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            33,  # DWMWA_WINDOW_CORNER_PREFERENCE
            ctypes.byref(corner_preference_do_not_round),
            ctypes.sizeof(corner_preference_do_not_round),
        )
    except (AttributeError, OSError, ValueError):
        return


def force_windows_topmost(widget: QWidget) -> None:
    if not sys.platform.startswith("win"):
        return

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    try:
        hwnd = wintypes.HWND(int(widget.winId()))
        hwnd_topmost = wintypes.HWND(-1)
        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_noactivate = 0x0010
        swp_showwindow = 0x0040
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            hwnd_topmost,
            0,
            0,
            0,
            0,
            swp_nomove | swp_nosize | swp_noactivate | swp_showwindow,
        )
    except (AttributeError, OSError, ValueError):
        return


class _PopupTopmostFilter(QObject):
    def __init__(self, overlay: QWidget) -> None:
        super().__init__(overlay)
        self._overlay = overlay

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show:
            self._overlay._topmost_timer.stop()
        elif event.type() == QEvent.Type.Hide:
            if self._overlay.isVisible() and not self._overlay._hide_requested:
                self._overlay._topmost_timer.start()
                force_windows_topmost(self._overlay)
        return super().eventFilter(watched, event)


class OverlayWindow(QWidget):
    save_requested = Signal(object)
    reconnect_requested = Signal()
    lyric_color_toggle_requested = Signal(object)
    clear_lyrics_cache_requested = Signal()
    overlay_hidden = Signal()
    overlay_shown = Signal()

    _DEFAULT_LYRIC_COLOR = "#F4F4F4"
    _HEADER_VISIBLE_DURATION_SECONDS = 7.0
    _NO_LYRICS_NOTICE_SECONDS = 4.0
    _COMPACT_MIN_HEIGHT = 60
    _OVERLAY_CORNER_RADIUS = 30
    _COMPACT_WINDOW_WIDTH = 620
    _EXPANDED_WINDOW_WIDTH = 740
    _API_COLUMN_EXTRA_WIDTH = 260

    def __init__(self) -> None:
        super().__init__()
        self._drag_origin = None
        self._initial_positioned = False
        self._expanded = False
        self._snap_pos = None
        self._snap_threshold = 28
        self._user_positioned = False
        self._allow_exit = False
        self._hide_requested = False
        self._track_text = "Spotify is not playing"
        self._artist_text = ""
        self._current_line_text = ""
        self._next_line_text = ""
        self._status_text = ""
        self._lyrics_available = False
        self._header_visible_until = 0.0
        self._no_lyrics_notice_until = 0.0
        self._overlay_bg_color = "#0A0A0AEB"
        self._overlay_text_color = "#F4F4F4"
        self._lyric_text_color = "#F4F4F4"
        self._lyric_glow_color = "#66CCFFFF"
        self._lyric_toggle_color = "#1A1A1A"
        self._last_non_toggle_lyric_color = self._lyric_text_color
        self._lyric_font_family = "Segoe UI"
        self._lyric_font_size = 11
        self._text_alignment = "left"
        self._display_style = CARD_DISPLAY_STYLE
        self._lyric_lines = SINGLE_LYRIC_LINES
        self._track_info_mode = TRACK_CHANGE_INFO_MODE
        self._playback_source = WINDOWS_PLAYBACK_SOURCE
        self._show_settings_button = True
        self._show_hide_button = True
        self._hover_buttons_enabled = False
        self._mouse_over_overlay = False
        self._last_window_size: tuple[int, int] | None = None
        self._last_screen = None
        self._screen_signal_connected = False
        self._popup_filters: list[_PopupTopmostFilter] = []
        self._resize_animation = QPropertyAnimation(self, b"geometry", self)
        self._resize_animation.setDuration(180)
        self._resize_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(100)
        self._topmost_timer.timeout.connect(self._keep_topmost_above_shell)
        self._transient_refresh_timer = QTimer(self)
        self._transient_refresh_timer.setSingleShot(True)
        self._transient_refresh_timer.timeout.connect(self._refresh_timed_overlay_state)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Lyricfy")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(620, self._COMPACT_MIN_HEIGHT)
        self.resize(620, self._COMPACT_MIN_HEIGHT)

        root = QWidget(self)
        root.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(root)

        card_layout = QVBoxLayout(root)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.settings_button = QToolButton()
        self.settings_button.setText("...")
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(self.toggle_settings)

        self.close_button = QToolButton()
        self.close_button.setText("-")
        self.close_button.setToolTip("Hide Overlay")
        self.close_button.clicked.connect(self.request_close)

        self.compact_label = QLabel("Spotify is not playing")
        self.compact_label.setFont(QFont("Segoe UI Semibold", 11))
        self.compact_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.compact_label.setMinimumWidth(500)
        self.compact_label.setWordWrap(True)

        header_layout.addWidget(self.compact_label, 1)
        header_layout.addWidget(self.settings_button)
        header_layout.addWidget(self.close_button)

        self.track_title_label = QLabel("")
        self.track_title_label.setObjectName("trackMeta")
        self.track_title_label.setFont(QFont("Segoe UI", 8))
        self.track_title_label.setWordWrap(False)
        self.track_title_label.hide()

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setWordWrap(True)
        self.status_label.hide()

        self.settings_panel = QWidget()
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(0, 4, 0, 0)
        settings_layout.setSpacing(10)

        self.client_id_input = self._create_input("Enter Spotify Client ID")
        self.client_secret_input = self._create_input("Enter Spotify Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.redirect_uri_input = self._create_input("Enter Redirect URI")
        self.lyric_offset_input = self._create_input("Default: 0")
        self.text_alignment_input = QComboBox()
        self.text_alignment_input.addItem("Left", "left")
        self.text_alignment_input.addItem("Center", "center")
        self.text_alignment_input.addItem("Right", "right")
        self.display_preset_input = QComboBox()
        self.display_preset_input.addItem("Card Default", "card_default")
        self.display_preset_input.addItem("Floating Minimal", "floating_minimal")
        self.display_preset_input.addItem("Floating Context", "floating_context")
        self.display_preset_input.addItem("Custom", CUSTOM_DISPLAY_PRESET)
        self.display_style_input = QComboBox()
        self.display_style_input.addItem("Card", CARD_DISPLAY_STYLE)
        self.display_style_input.addItem("Floating Text", FLOATING_DISPLAY_STYLE)
        self.lyric_lines_input = QComboBox()
        self.lyric_lines_input.addItem("Single Line", SINGLE_LYRIC_LINES)
        self.lyric_lines_input.addItem("Current + Next", CURRENT_NEXT_LYRIC_LINES)
        self.track_info_mode_input = QComboBox()
        self.track_info_mode_input.addItem("On Track Change", TRACK_CHANGE_INFO_MODE)
        self.track_info_mode_input.addItem("Always", ALWAYS_TRACK_INFO_MODE)
        self.track_info_mode_input.addItem("Never", NEVER_TRACK_INFO_MODE)
        self.startup_visibility_input = QComboBox()
        self.startup_visibility_input.addItem("Show Overlay", False)
        self.startup_visibility_input.addItem("Start Hidden", True)
        self.font_family_input = QFontComboBox()
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 48)
        self.font_size_input.setSingleStep(1)
        self.overlay_color_input = self._create_input("Example: #0A0A0AEB")
        self.text_color_input = self._create_input("Example: #F4F4F4")
        self.lyric_color_input = self._create_input("Example: #F4F4F4")
        self.glow_color_input = self._create_input("Example: #66CCFFFF")
        self.toggle_color_input = self._create_input("Example: #1A1A1A")
        self.auto_save_lrc_checkbox = QCheckBox("Save fetched lyrics as local .lrc cache")
        self.hover_buttons_checkbox = QCheckBox("Card controls on hover")
        self.hover_buttons_checkbox.setToolTip(
            "Floating presets always show Settings and Hide controls on hover."
        )
        self.autostart_checkbox = QCheckBox("Auto start when Windows starts")
        self.shortcuts_label = QLabel(shortcuts_guide_text())
        self.shortcuts_label.setObjectName("shortcutsGuide")
        self.shortcuts_label.setWordWrap(True)

        for combo_box in (
            self.text_alignment_input,
            self.display_preset_input,
            self.display_style_input,
            self.lyric_lines_input,
            self.track_info_mode_input,
            self.startup_visibility_input,
            self.font_family_input,
        ):
            self._install_popup_topmost_guard(combo_box)

        settings_actions = QHBoxLayout()
        settings_actions.setSpacing(8)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._emit_save)

        self.reconnect_button = QPushButton("Reload Playback")
        self.reconnect_button.clicked.connect(self.trigger_reconnect_shortcut)

        self.clear_cache_button = QPushButton("Clear Downloaded Lyrics")
        self.clear_cache_button.clicked.connect(self.confirm_clear_downloaded_lyrics)

        self.reset_defaults_button = QPushButton("Reset Default")
        self.reset_defaults_button.clicked.connect(self.confirm_reset_default_settings)

        self.close_settings_button = QPushButton("Close Settings")
        self.close_settings_button.clicked.connect(self.close_settings_panel)

        settings_actions.addWidget(self.save_button)
        settings_actions.addWidget(self.reset_defaults_button)
        settings_actions.addWidget(self.reconnect_button)
        settings_actions.addWidget(self.clear_cache_button)
        settings_actions.addWidget(self.close_settings_button)
        settings_actions.addStretch(1)

        self.client_id_field = self._create_field("Spotify Client ID", self.client_id_input)
        self.client_secret_field = self._create_field("Spotify Client Secret", self.client_secret_input)
        self.redirect_uri_field = self._create_field("Redirect URI", self.redirect_uri_input)
        self._oauth_fields = [
            self.client_id_field,
            self.client_secret_field,
            self.redirect_uri_field,
        ]

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(8)
        left_column.addWidget(self._create_section_title("Text"))
        left_column.addWidget(self._create_offset_field())
        left_column.addWidget(self._create_field("Text Alignment", self.text_alignment_input))
        left_column.addWidget(self._create_field("Lyric Font", self.font_family_input))
        left_column.addWidget(self._create_field("Font Size", self.font_size_input))
        left_column.addWidget(self.auto_save_lrc_checkbox)
        left_column.addWidget(self.hover_buttons_checkbox)
        left_column.addWidget(self.autostart_checkbox)
        left_column.addWidget(self._create_field("Auto Start Mode", self.startup_visibility_input))
        left_column.addWidget(self._create_section_title("Shortcuts"))
        left_column.addWidget(self.shortcuts_label)
        left_column.addStretch(1)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(8)
        right_column.addWidget(self._create_section_title("Display"))
        right_column.addWidget(self._create_field("Display Preset", self.display_preset_input))
        right_column.addWidget(self._create_field("Display Style", self.display_style_input))
        right_column.addWidget(self._create_field("Lyric Lines", self.lyric_lines_input))
        right_column.addWidget(self._create_field("Track Information", self.track_info_mode_input))
        right_column.addWidget(self._create_section_title("Appearance"))
        right_column.addWidget(self._create_field("Overlay Color", self.overlay_color_input))
        right_column.addWidget(self._create_field("Text Color", self.text_color_input))
        right_column.addWidget(self._create_field("Lyric Color", self.lyric_color_input))
        right_column.addWidget(self._create_field("Lyric Glow Color", self.glow_color_input))
        right_column.addWidget(self._create_field("Toggle Lyric Color", self.toggle_color_input))
        right_column.addStretch(1)

        credentials_layout = QVBoxLayout()
        credentials_layout.setContentsMargins(0, 0, 0, 0)
        credentials_layout.setSpacing(8)
        credentials_layout.addWidget(self._create_section_title("Spotify API"))
        credentials_layout.addWidget(self.client_id_field)
        credentials_layout.addWidget(self.client_secret_field)
        credentials_layout.addWidget(self.redirect_uri_field)
        credentials_layout.addStretch(1)
        self.credentials_section = QWidget()
        self.credentials_section.setLayout(credentials_layout)

        # Spotify API menempati kolom ketiga agar panel melebar ke samping,
        # bukan memanjang ke bawah saat mode API aktif.
        self._content_grid = QGridLayout()
        self._content_grid.setContentsMargins(0, 0, 0, 0)
        self._content_grid.setHorizontalSpacing(12)
        self._content_grid.setVerticalSpacing(10)
        self._content_grid.addLayout(left_column, 0, 0)
        self._content_grid.addLayout(right_column, 0, 1)
        self._content_grid.addWidget(self.credentials_section, 0, 2)
        self._content_grid.setColumnStretch(0, 1)
        self._content_grid.setColumnStretch(1, 1)
        self._content_grid.setColumnStretch(2, 0)

        settings_layout.addLayout(self._content_grid)
        settings_layout.addLayout(settings_actions)
        self.settings_panel.setMaximumHeight(0)
        self.settings_panel.hide()

        card_layout.addLayout(header_layout)
        self.next_line_label = QLabel("")
        self.next_line_label.setObjectName("nextLyric")
        self.next_line_label.setWordWrap(True)
        self.next_line_label.hide()
        card_layout.addWidget(self.next_line_label)
        card_layout.addWidget(self.track_title_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.settings_panel)

        self._lyric_glow = QGraphicsDropShadowEffect(self)
        self._lyric_glow.setBlurRadius(18)
        self._lyric_glow.setOffset(0, 0)
        self.compact_label.setGraphicsEffect(self._lyric_glow)

        self.display_preset_input.currentIndexChanged.connect(self._apply_selected_display_preset)
        self.display_style_input.currentIndexChanged.connect(self._sync_custom_display_preset)
        self.lyric_lines_input.currentIndexChanged.connect(self._sync_custom_display_preset)
        self.track_info_mode_input.currentIndexChanged.connect(self._sync_custom_display_preset)
        self.hover_buttons_checkbox.toggled.connect(self._preview_card_hover_controls)

        self._sync_playback_source_ui()
        self._apply_theme()
        self._refresh_compact_text()

    def _apply_theme(self) -> None:
        next_lyric_color = QColor(self._overlay_text_color)
        if not next_lyric_color.isValid():
            next_lyric_color = QColor("#F4F4F4")
        next_lyric_color.setAlpha(153)
        self.setStyleSheet(
            f"""
            QWidget#card {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                color: {self._overlay_text_color};
                background: transparent;
            }}
            QLabel#compactLyric {{
                color: {self._lyric_text_color};
            }}
            QLabel#trackMeta {{
                color: {self._lyric_text_color};
            }}
            QLabel#nextLyric {{
                color: {next_lyric_color.name(QColor.NameFormat.HexArgb)};
            }}
            QLabel#sectionTitle {{
                color: {self._overlay_text_color};
                font: 9pt "Segoe UI Semibold";
                letter-spacing: 0.5px;
                padding-bottom: 2px;
            }}
            QLabel#shortcutsGuide {{
                color: {self._overlay_text_color};
                background: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 12px;
                padding: 8px 10px;
                font: 9pt "Segoe UI";
            }}
            QLineEdit {{
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 10px;
                color: {self._overlay_text_color};
                padding: 6px 10px;
                min-height: 32px;
            }}
            QComboBox, QFontComboBox, QSpinBox {{
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 10px;
                color: {self._overlay_text_color};
                padding: 6px 10px;
                min-height: 32px;
            }}
            QComboBox QAbstractItemView, QFontComboBox QAbstractItemView {{
                background: #171717;
                color: {self._overlay_text_color};
                border: 1px solid rgba(255, 255, 255, 28);
                selection-background-color: rgba(255, 255, 255, 20);
                selection-color: {self._overlay_text_color};
                outline: 0;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: rgba(255, 255, 255, 12);
                border: none;
                width: 18px;
                margin: 2px;
                border-radius: 6px;
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 0px;
                height: 0px;
            }}
            QCheckBox {{
                color: {self._overlay_text_color};
                background: transparent;
            }}
            QPushButton, QToolButton {{
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 10px;
                color: {self._overlay_text_color};
                padding: 6px 10px;
            }}
            QPushButton {{
                min-height: 36px;
            }}
            QToolButton {{
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                padding: 0px;
                font: 9pt "Segoe UI Semibold";
            }}
            """
        )
        self.compact_label.setObjectName("compactLyric")
        self.compact_label.style().unpolish(self.compact_label)
        self.compact_label.style().polish(self.compact_label)
        self.track_title_label.style().unpolish(self.track_title_label)
        self.track_title_label.style().polish(self.track_title_label)
        self._lyric_glow.setColor(QColor(self._lyric_glow_color))
        self._apply_text_preferences()
        self.update()

    def _create_input(self, placeholder: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        return widget

    def _install_popup_topmost_guard(self, combo_box: QComboBox) -> None:
        popup_filter = _PopupTopmostFilter(self)
        combo_box.view().window().installEventFilter(popup_filter)
        self._popup_filters.append(popup_filter)

    def _create_field(self, label_text: str, input_widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Segoe UI Semibold", 9))
        layout.addWidget(label)
        layout.addWidget(input_widget)
        return container

    def _create_section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _create_offset_field(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("Lyric Offset (ms)")
        label.setFont(QFont("Segoe UI Semibold", 9))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        minus_button = QPushButton("-100")
        minus_button.clicked.connect(lambda: self._adjust_offset(-100))

        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(lambda: self.lyric_offset_input.setText("0"))

        plus_button = QPushButton("+100")
        plus_button.clicked.connect(lambda: self._adjust_offset(100))

        row.addWidget(self.lyric_offset_input, 1)
        row.addWidget(minus_button)
        row.addWidget(reset_button)
        row.addWidget(plus_button)

        layout.addWidget(label)
        layout.addLayout(row)
        return container

    def _adjust_offset(self, delta_ms: int) -> None:
        try:
            current_value = int(self.lyric_offset_input.text().strip() or "0")
        except ValueError:
            current_value = 0
        self.lyric_offset_input.setText(str(current_value + delta_ms))

    def load_config_values(self, config: AppConfig) -> None:
        self._playback_source = config.playback_source or WINDOWS_PLAYBACK_SOURCE
        self.client_id_input.setText(config.spotify_client_id)
        self.client_secret_input.setText(config.spotify_client_secret)
        self.redirect_uri_input.setText(config.spotify_redirect_uri)
        self.lyric_offset_input.setText(str(config.lyric_offset_ms or 0))
        self._lyric_font_family = config.lyric_font_family or "Segoe UI"
        self._lyric_font_size = max(8, config.lyric_font_size or 11)
        self._text_alignment = config.text_alignment or "left"
        self._display_style = config.display_style or CARD_DISPLAY_STYLE
        self._lyric_lines = config.lyric_lines or SINGLE_LYRIC_LINES
        self._track_info_mode = config.track_info_mode or TRACK_CHANGE_INFO_MODE
        self.font_family_input.setCurrentFont(QFont(self._lyric_font_family))
        self.font_size_input.setValue(self._lyric_font_size)
        self._set_alignment_selection(self._text_alignment)
        self._set_combo_data(self.display_style_input, self._display_style)
        self._set_combo_data(self.lyric_lines_input, self._lyric_lines)
        self._set_combo_data(self.track_info_mode_input, self._track_info_mode)
        self._set_combo_data(self.display_preset_input, display_preset_for(config))
        self.overlay_color_input.setText(config.overlay_bg_color)
        self.text_color_input.setText(config.overlay_text_color)
        self.lyric_color_input.setText(config.lyric_text_color)
        self.glow_color_input.setText(config.lyric_glow_color)
        self.toggle_color_input.setText(config.lyric_toggle_color)
        self._lyric_toggle_color = config.lyric_toggle_color or "#1A1A1A"
        if self._same_color(config.lyric_text_color, self._lyric_toggle_color):
            self._last_non_toggle_lyric_color = self._DEFAULT_LYRIC_COLOR
        else:
            self._last_non_toggle_lyric_color = config.lyric_text_color or self._DEFAULT_LYRIC_COLOR
        self.auto_save_lrc_checkbox.setChecked(config.auto_save_fetched_lrc)
        self._show_settings_button = config.show_settings_button
        self._show_hide_button = config.show_hide_button
        self._hover_buttons_enabled = config.hover_buttons_enabled
        self.hover_buttons_checkbox.setChecked(config.hover_buttons_enabled)
        self.autostart_checkbox.setChecked(config.autostart_enabled)
        self._set_startup_visibility_selection(config.autostart_start_hidden)
        self._sync_playback_source_ui()
        self._sync_overlay_buttons_ui()
        self._refresh_compact_text()
        self.apply_config_theme(config)
        self._refresh_layout_after_settings_change()

    def current_form_config(self) -> AppConfig:
        try:
            lyric_offset_ms = int(self.lyric_offset_input.text().strip() or "0")
        except ValueError:
            lyric_offset_ms = 0

        return AppConfig(
            playback_source=self._playback_source,
            spotify_client_id=self.client_id_input.text().strip(),
            spotify_client_secret=self.client_secret_input.text().strip(),
            spotify_redirect_uri=self.redirect_uri_input.text().strip(),
            poll_interval_ms=1000,
            lrclib_enabled=True,
            auto_save_fetched_lrc=self.auto_save_lrc_checkbox.isChecked(),
            lyric_offset_ms=lyric_offset_ms,
            overlay_bg_color=self.overlay_color_input.text().strip() or "#0A0A0AEB",
            overlay_text_color=self.text_color_input.text().strip() or "#F4F4F4",
            lyric_text_color=self.lyric_color_input.text().strip() or "#F4F4F4",
            lyric_glow_color=self.glow_color_input.text().strip() or "#66CCFFFF",
            lyric_toggle_color=self.toggle_color_input.text().strip() or "#1A1A1A",
            lyric_font_family=self.font_family_input.currentFont().family().strip() or "Segoe UI",
            lyric_font_size=self.font_size_input.value(),
            text_alignment=self.text_alignment_input.currentData(),
            display_style=self.display_style_input.currentData(),
            lyric_lines=self.lyric_lines_input.currentData(),
            track_info_mode=self.track_info_mode_input.currentData(),
            show_settings_button=self._show_settings_button,
            show_hide_button=self._show_hide_button,
            hover_buttons_enabled=self.hover_buttons_checkbox.isChecked(),
            autostart_enabled=self.autostart_checkbox.isChecked(),
            autostart_start_hidden=bool(self.startup_visibility_input.currentData()),
        )

    def apply_config_theme(self, config: AppConfig) -> None:
        self._overlay_bg_color = config.overlay_bg_color or "#0A0A0AEB"
        self._overlay_text_color = config.overlay_text_color or "#F4F4F4"
        self._lyric_text_color = config.lyric_text_color or "#F4F4F4"
        self._lyric_glow_color = config.lyric_glow_color or "#66CCFFFF"
        self._lyric_toggle_color = config.lyric_toggle_color or "#1A1A1A"
        self._lyric_font_family = config.lyric_font_family or "Segoe UI"
        self._lyric_font_size = max(8, config.lyric_font_size or 11)
        self._text_alignment = config.text_alignment or "left"
        self._display_style = config.display_style or CARD_DISPLAY_STYLE
        self._lyric_lines = config.lyric_lines or SINGLE_LYRIC_LINES
        self._track_info_mode = config.track_info_mode or TRACK_CHANGE_INFO_MODE
        self._apply_theme()

    def set_playback_source(self, playback_source: str) -> None:
        self._playback_source = playback_source or WINDOWS_PLAYBACK_SOURCE
        self._sync_playback_source_ui()
        self._refresh_layout_after_settings_change()

    def apply_display_preset(self, preset: str) -> None:
        values = display_preset_values(preset)
        if values is None:
            return
        self._display_style, self._lyric_lines, self._track_info_mode = values
        self._set_combo_data(self.display_style_input, self._display_style)
        self._set_combo_data(self.lyric_lines_input, self._lyric_lines)
        self._set_combo_data(self.track_info_mode_input, self._track_info_mode)
        self._set_combo_data(self.display_preset_input, preset)
        self._sync_overlay_buttons_ui()
        self._refresh_compact_text()
        self._last_window_size = None
        self._apply_window_mode()
        self.update()
        self.update()

    def playback_source(self) -> str:
        return self._playback_source

    def set_overlay_buttons_visibility(
        self,
        show_settings_button: bool,
        show_hide_button: bool,
        hover_buttons_enabled: bool | None = None,
    ) -> None:
        self._show_settings_button = show_settings_button
        self._show_hide_button = show_hide_button
        if hover_buttons_enabled is not None:
            self._hover_buttons_enabled = hover_buttons_enabled
            self.hover_buttons_checkbox.setChecked(hover_buttons_enabled)
        self._sync_overlay_buttons_ui()
        self._refresh_layout_after_settings_change()

    def show_status(self, message: str) -> None:
        new_status = message.strip()
        new_visible = bool(new_status) or self._expanded
        text_changed = new_status != self._status_text
        visibility_changed = new_visible != self.status_label.isVisible()

        self._status_text = new_status
        if text_changed:
            self.status_label.setText(self._status_text)
        if visibility_changed:
            self.status_label.setVisible(new_visible)
        self._refresh_compact_text()
        if (text_changed or visibility_changed) and not self._expanded:
            self._apply_window_mode()

    def toggle_settings(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self.settings_panel.setMaximumHeight(16777215)
            self.settings_panel.show()
        else:
            self.settings_panel.hide()
            self.settings_panel.setMaximumHeight(0)
        self.status_label.setVisible(bool(self._status_text) or self._expanded)
        self._sync_playback_source_ui()
        self._sync_overlay_buttons_ui()
        if self.layout() is not None:
            self.layout().invalidate()
            self.layout().activate()
        self._last_window_size = None
        self._apply_window_mode()

    def close_settings_panel(self) -> None:
        if not self._expanded:
            return
        self.toggle_settings()

    def reset_to_default_settings(self) -> None:
        defaults = default_config()
        self.load_config_values(defaults)

    def confirm_reset_default_settings(self) -> None:
        confirmed = self._confirm_action(
            window_title="Reset Default",
            title_text="Reset settings to default?",
            message_text="This will replace the current form values with Lyricfy default settings. Save is still required to write them to .env.",
            confirm_text="Reset",
            danger=True,
        )
        if confirmed:
            self.reset_to_default_settings()

    def confirm_clear_downloaded_lyrics(self) -> None:
        confirmed = self._confirm_action(
            window_title="Clear Downloaded Lyrics",
            title_text="Clear downloaded lyrics?",
            message_text="This will delete all saved .lrc cache files. Downloaded lyrics can be fetched again later.",
            confirm_text="Delete",
            danger=True,
        )
        if confirmed:
            self.clear_lyrics_cache_requested.emit()

    def _confirm_action(
        self,
        *,
        window_title: str,
        title_text: str,
        message_text: str,
        confirm_text: str,
        danger: bool = False,
    ) -> bool:
        dialog = QDialog(self)
        dialog.setWindowTitle(window_title)
        dialog.setModal(True)
        dialog.setFixedWidth(360)
        dialog.setObjectName("confirmDialog")
        dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        drag_offset = {"value": QPoint()}

        def start_drag(event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                drag_offset["value"] = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
                event.accept()

        def move_drag(event) -> None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                dialog.move(event.globalPosition().toPoint() - drag_offset["value"])
                event.accept()

        def enable_drag(widget: QWidget) -> None:
            widget.mousePressEvent = start_drag
            widget.mouseMoveEvent = move_drag

        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        surface = QWidget()
        surface.setObjectName("confirmSurface")
        outer_layout.addWidget(surface)

        layout = QVBoxLayout(surface)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(title_text)
        title.setObjectName("confirmTitle")

        message = QLabel(message_text)
        message.setObjectName("confirmMessage")
        message.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setSpacing(8)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)

        confirm_button = QPushButton(confirm_text)
        if danger:
            confirm_button.setObjectName("dangerButton")
        confirm_button.clicked.connect(dialog.accept)

        actions.addStretch(1)
        actions.addWidget(cancel_button)
        actions.addWidget(confirm_button)

        layout.addWidget(title)
        layout.addWidget(message)
        layout.addLayout(actions)

        for draggable_widget in (dialog, surface, title, message):
            enable_drag(draggable_widget)

        shadow = QGraphicsDropShadowEffect(dialog)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        surface.setGraphicsEffect(shadow)

        dialog.setStyleSheet(
            f"""
            QDialog#confirmDialog {{
                background: transparent;
            }}
            QWidget#confirmSurface {{
                background: rgba(3, 3, 4, 252);
                border: 2px solid rgba(255, 255, 255, 92);
                border-radius: 18px;
            }}
            QLabel {{
                color: {self._overlay_text_color};
                background: transparent;
            }}
            QLabel#confirmTitle {{
                font: 11pt "Segoe UI Semibold";
            }}
            QLabel#confirmMessage {{
                color: rgba(244, 244, 244, 204);
                font: 9pt "Segoe UI";
                line-height: 130%;
            }}
            QPushButton {{
                background: rgba(255, 255, 255, 18);
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 10px;
                color: {self._overlay_text_color};
                min-height: 34px;
                min-width: 82px;
                padding: 6px 12px;
            }}
            QPushButton#dangerButton {{
                background: rgba(255, 76, 76, 64);
                border: 1px solid rgba(255, 130, 130, 112);
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 34);
            }}
            QPushButton#dangerButton:hover {{
                background: rgba(255, 76, 76, 86);
            }}
            """
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _emit_save(self) -> None:
        self.save_requested.emit(self.current_form_config())

    def trigger_reconnect_shortcut(self) -> None:
        self.show_status("Spotify playback trying to reconnect...")
        QTimer.singleShot(0, self.reconnect_requested.emit)

    def toggle_lyric_color_shortcut(self) -> None:
        current_color = (self.lyric_color_input.text().strip() or self._lyric_text_color).upper()
        toggle_color = (self.toggle_color_input.text().strip() or self._lyric_toggle_color).upper()
        if self._same_color(current_color, toggle_color):
            next_color = self._last_non_toggle_lyric_color or self._DEFAULT_LYRIC_COLOR
        else:
            self._last_non_toggle_lyric_color = current_color
            next_color = toggle_color

        self.lyric_color_input.setText(next_color)
        updated_config = self.current_form_config()
        self.apply_config_theme(updated_config)
        self.show_status(f"Lyric color: {next_color}")
        self.lyric_color_toggle_requested.emit(updated_config)

    @staticmethod
    def _same_color(left: str, right: str) -> bool:
        return (left or "").strip().upper() == (right or "").strip().upper()

    def set_track(self, track: TrackInfo | None, lyrics_source: str = "") -> None:
        previous_compact_text = self.compact_label.text()
        previous_header_visible = self.track_title_label.isVisible()
        previous_header_text = self.track_title_label.text()
        normalized_source = (lyrics_source or "").strip().lower()
        self._lyrics_available = bool(normalized_source) and normalized_source not in {"none", "loading"}
        if track is None:
            self._track_text = "Spotify is not playing"
            self._artist_text = "Waiting for playback"
            self._current_line_text = ""
            self._next_line_text = ""
            self._lyrics_available = False
            self._header_visible_until = 0.0
            self._no_lyrics_notice_until = 0.0
            self._refresh_compact_text()
            self._apply_window_mode_if_layout_changed(
                previous_compact_text,
                previous_header_text,
                previous_header_visible,
            )
            return

        previous_title = self._track_text
        previous_artist = self._artist_text
        self._track_text = track.title
        self._artist_text = track.artist
        if (
            self._track_text != previous_title
            or self._artist_text != previous_artist
            or not self._lyrics_available
        ):
            self._current_line_text = ""
            self._next_line_text = ""
        if self._lyrics_available and (
            self._track_text != previous_title or self._artist_text != previous_artist
        ):
            self._header_visible_until = time.monotonic() + self._HEADER_VISIBLE_DURATION_SECONDS
        elif self._lyrics_available and self._header_visible_until <= 0.0:
            self._header_visible_until = time.monotonic() + self._HEADER_VISIBLE_DURATION_SECONDS
        elif not self._lyrics_available:
            self._header_visible_until = 0.0
        self._refresh_compact_text()
        self._apply_window_mode_if_layout_changed(
            previous_compact_text,
            previous_header_text,
            previous_header_visible,
        )

    def set_lines(self, current_line: str, next_line: str) -> None:
        previous_compact_text = self.compact_label.text()
        previous_header_visible = self.track_title_label.isVisible()
        previous_header_text = self.track_title_label.text()
        self._current_line_text = current_line.strip()
        self._next_line_text = next_line.strip()
        self._refresh_compact_text()
        if (
            self.compact_label.text() != previous_compact_text
            or self.track_title_label.isVisible() != previous_header_visible
            or self.track_title_label.text() != previous_header_text
        ):
            self._apply_window_mode_if_needed()

    def set_paused(self) -> None:
        self._status_text = "Playback paused"
        self.status_label.setText(self._status_text)
        self.status_label.setVisible(True)
        self._refresh_compact_text()
        self._apply_window_mode_if_needed()

    def show_no_lyrics_notice(self) -> None:
        self._no_lyrics_notice_until = time.monotonic() + self._NO_LYRICS_NOTICE_SECONDS
        self._refresh_compact_text()
        self._apply_window_mode_if_needed()

    def _refresh_compact_text(self, *, compact_width: int | None = None) -> None:
        title_text = self._track_text.strip()
        artist_text = self._artist_text.strip()
        if self._current_line_text:
            compact_text = self._current_line_text
        elif time.monotonic() < self._no_lyrics_notice_until:
            compact_text = "No lyric found"
        else:
            compact_text = title_text or artist_text

        if self._lyrics_available:
            header_text = f"{title_text} - {artist_text}" if title_text and artist_text else title_text or artist_text
            if self._track_info_mode == ALWAYS_TRACK_INFO_MODE:
                show_small_track = bool(header_text)
            elif self._track_info_mode == NEVER_TRACK_INFO_MODE:
                show_small_track = False
            else:
                show_small_track = bool(header_text) and time.monotonic() < self._header_visible_until
        else:
            header_text = artist_text
            show_small_track = bool(header_text)

        self.track_title_label.setText(
            self._elide_label_text(self.track_title_label, header_text, available_width=compact_width)
        )
        self.track_title_label.setVisible(show_small_track)
        self.compact_label.setText(self._format_compact_text(compact_text, available_width=compact_width))
        show_next = (
            self._lyrics_available
            and self._lyric_lines == CURRENT_NEXT_LYRIC_LINES
            and bool(self._current_line_text)
            and bool(self._next_line_text)
        )
        self.next_line_label.setText(
            self._format_next_line_text(self._next_line_text, available_width=compact_width)
        )
        self.next_line_label.setVisible(show_next)
        self._schedule_transient_refresh()

    def _apply_text_preferences(self) -> None:
        compact_font = QFont(self._lyric_font_family, self._lyric_font_size)
        compact_font.setBold(True)
        self.compact_label.setFont(compact_font)
        line_height = self.compact_label.fontMetrics().lineSpacing()
        self.compact_label.setMaximumHeight(max(40, line_height * 2 + 6))
        self.compact_label.setMinimumHeight(max(32, line_height + 4))

        meta_font = QFont(self._lyric_font_family, max(8, self._lyric_font_size - 3))
        self.track_title_label.setFont(meta_font)
        self.status_label.setFont(meta_font)
        next_font = QFont(self._lyric_font_family, max(8, self._lyric_font_size - 2))
        next_font.setBold(False)
        self.next_line_label.setFont(next_font)

        alignment = self._qt_alignment(self._text_alignment)
        self.compact_label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        self.track_title_label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        self.next_line_label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        self._refresh_compact_text()

    def _elide_label_text(
        self,
        label: QLabel,
        text: str,
        *,
        available_width: int | None = None,
    ) -> str:
        if not text:
            return ""
        target_width = available_width
        if target_width is None:
            target_width = label.width() or label.sizeHint().width() or label.minimumWidth()
        target_width = max(120, target_width)
        metrics = QFontMetrics(label.font())
        return metrics.elidedText(text, Qt.TextElideMode.ElideRight, target_width)

    def _format_compact_text(self, text: str, *, available_width: int | None = None) -> str:
        normalized = " ".join(text.split())
        if not normalized:
            return ""

        if available_width is None:
            available_width = self.compact_label.width() or self.compact_label.minimumWidth()
        available_width = max(180, available_width)
        metrics = QFontMetrics(self.compact_label.font())
        if metrics.horizontalAdvance(normalized) <= available_width:
            return normalized

        words = normalized.split(" ")
        first_line_words: list[str] = []
        second_line_words: list[str] = []

        for word in words:
            candidate = " ".join(first_line_words + [word]).strip()
            if not first_line_words and metrics.horizontalAdvance(word) > available_width:
                first_line_words.append(metrics.elidedText(word, Qt.TextElideMode.ElideRight, available_width))
                second_line_words.extend(words[1:])
                break
            if not first_line_words or metrics.horizontalAdvance(candidate) <= available_width:
                first_line_words.append(word)
                continue
            second_line_words.append(word)

        first_line = " ".join(first_line_words).strip()
        if not second_line_words:
            return metrics.elidedText(first_line, Qt.TextElideMode.ElideRight, available_width)

        remaining = " ".join(second_line_words).strip()
        second_line = metrics.elidedText(remaining, Qt.TextElideMode.ElideRight, available_width)
        return f"{first_line}\n{second_line}"

    def _format_next_line_text(self, text: str, *, available_width: int | None = None) -> str:
        normalized = " ".join(text.split())
        if not normalized:
            return ""
        if available_width is None:
            available_width = self.next_line_label.width() or self.compact_label.minimumWidth()
        metrics = QFontMetrics(self.next_line_label.font())
        return metrics.elidedText(normalized, Qt.TextElideMode.ElideRight, max(180, available_width))

    def _set_alignment_selection(self, alignment: str) -> None:
        for index in range(self.text_alignment_input.count()):
            if self.text_alignment_input.itemData(index) == alignment:
                self.text_alignment_input.setCurrentIndex(index)
                return
        self.text_alignment_input.setCurrentIndex(0)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    def _apply_selected_display_preset(self) -> None:
        preset = self.display_preset_input.currentData()
        values = display_preset_values(preset)
        if values is None:
            return
        style, lyric_lines, track_info_mode = values
        self._set_combo_data(self.display_style_input, style)
        self._set_combo_data(self.lyric_lines_input, lyric_lines)
        self._set_combo_data(self.track_info_mode_input, track_info_mode)

    def _sync_custom_display_preset(self) -> None:
        config = self.current_form_config()
        self._set_combo_data(self.display_preset_input, display_preset_for(config))
        self._display_style = config.display_style
        self._lyric_lines = config.lyric_lines
        self._track_info_mode = config.track_info_mode
        self._sync_overlay_buttons_ui()
        self._refresh_compact_text()
        self.update()

    def _preview_card_hover_controls(self, enabled: bool) -> None:
        self._hover_buttons_enabled = enabled
        self._sync_overlay_buttons_ui()
        self._apply_window_mode_if_needed()
        self.update()

    def _set_startup_visibility_selection(self, start_hidden: bool) -> None:
        for index in range(self.startup_visibility_input.count()):
            if bool(self.startup_visibility_input.itemData(index)) == start_hidden:
                self.startup_visibility_input.setCurrentIndex(index)
                return
        self.startup_visibility_input.setCurrentIndex(0)

    def _qt_alignment(self, alignment: str) -> Qt.AlignmentFlag:
        normalized = (alignment or "").strip().lower()
        if normalized == "center":
            return Qt.AlignmentFlag.AlignHCenter
        if normalized == "right":
            return Qt.AlignmentFlag.AlignRight
        return Qt.AlignmentFlag.AlignLeft

    def _sync_playback_source_ui(self) -> None:
        show_oauth_fields = self._playback_source == SPOTIFY_API_PLAYBACK_SOURCE
        self.credentials_section.setVisible(show_oauth_fields)
        for field in self._oauth_fields:
            field.setVisible(show_oauth_fields)
        # Kolom Spotify API hanya ikut melebar saat mode API aktif.
        self._content_grid.setColumnStretch(2, 1 if show_oauth_fields else 0)

    def _sync_overlay_buttons_ui(self) -> None:
        if self._uses_hover_controls():
            self.settings_button.setVisible(
                self._expanded or (self._mouse_over_overlay and self._show_settings_button)
            )
            self.close_button.setVisible(self._mouse_over_overlay and self._show_hide_button)
            return

        self.settings_button.setVisible(self._show_settings_button or self._expanded)
        self.close_button.setVisible(self._show_hide_button)

    def _uses_hover_controls(self) -> bool:
        return self._hover_buttons_enabled or (
            self._display_style == FLOATING_DISPLAY_STYLE and not self._expanded
        )

    def _refresh_layout_after_settings_change(self) -> None:
        if self._expanded:
            self._apply_window_mode()
            return
        self._apply_window_mode_if_needed()

    def _apply_window_mode_if_layout_changed(
        self,
        previous_compact_text: str,
        previous_header_text: str,
        previous_header_visible: bool,
    ) -> None:
        if self._expanded:
            return
        if (
            self.compact_label.text() != previous_compact_text
            or self.track_title_label.text() != previous_header_text
            or self.track_title_label.isVisible() != previous_header_visible
        ):
            self._apply_window_mode()

    def _apply_window_mode_if_needed(self) -> None:
        if self._expanded:
            return
        self._apply_window_mode()

    def _compact_text_width_for_window(self, target_width: int) -> int:
        outer_layout = self.layout()
        outer_margins = outer_layout.contentsMargins() if outer_layout is not None else self.contentsMargins()
        card_widget = self.findChild(QWidget, "card")
        card_layout = card_widget.layout() if card_widget is not None else None
        card_margins = card_layout.contentsMargins() if card_layout is not None else outer_margins
        content_width = max(320, target_width - outer_margins.left() - outer_margins.right())
        card_width = max(280, content_width - card_margins.left() - card_margins.right())
        button_width = 64 if not self._expanded else 0
        return max(180, card_width - button_width)

    def _schedule_transient_refresh(self) -> None:
        deadlines = []
        now = time.monotonic()
        if self._header_visible_until > now:
            deadlines.append(self._header_visible_until)
        if self._no_lyrics_notice_until > now:
            deadlines.append(self._no_lyrics_notice_until)

        if not deadlines:
            self._transient_refresh_timer.stop()
            return

        delay_ms = max(50, int((min(deadlines) - now) * 1000) + 10)
        self._transient_refresh_timer.start(delay_ms)

    def _refresh_timed_overlay_state(self) -> None:
        previous_compact_text = self.compact_label.text()
        previous_header_text = self.track_title_label.text()
        previous_header_visible = self.track_title_label.isVisible()
        self._refresh_compact_text()
        if self._expanded:
            return
        if (
            self.track_title_label.text() != previous_header_text
            or self.track_title_label.isVisible() != previous_header_visible
            or self.compact_label.text() != previous_compact_text
        ):
            self._apply_window_mode()

    def _apply_window_mode(self) -> None:
        width_bonus = max(0, self._lyric_font_size - 11) * 16
        target_width = self._target_window_width() + width_bonus
        if self._expanded:
            target_height = self._expanded_target_height(target_width)
        else:
            self._refresh_compact_text(compact_width=self._compact_text_width_for_window(target_width))
            target_height = self._compact_target_height(target_width)
        target_size = (target_width, target_height)
        self.setMinimumSize(target_width, self._COMPACT_MIN_HEIGHT)
        if self._last_window_size == target_size:
            return
        self._last_window_size = target_size
        if self._expanded and self.isVisible():
            self._animate_window_resize(target_width, target_height)
            return
        self._resize_animation.stop()
        self.resize(target_width, target_height)
        self._reposition_after_resize()

    def _target_window_width(self) -> int:
        if not self._expanded:
            return self._COMPACT_WINDOW_WIDTH
        if self._playback_source == SPOTIFY_API_PLAYBACK_SOURCE:
            # Mode API menampilkan kolom Spotify API tambahan di samping kanan.
            return self._EXPANDED_WINDOW_WIDTH + self._API_COLUMN_EXTRA_WIDTH
        return self._EXPANDED_WINDOW_WIDTH

    def _expanded_target_height(self, target_width: int) -> int:
        self.layout().activate()
        outer_layout = self.layout()
        outer_margins = outer_layout.contentsMargins()

        card_widget = self.findChild(QWidget, "card")
        if card_widget is None:
            return 470

        content_width = max(320, target_width - outer_margins.left() - outer_margins.right())
        card_widget.setFixedWidth(content_width)
        card_widget.layout().activate()
        card_height = card_widget.sizeHint().height()
        card_widget.setMinimumWidth(0)
        card_widget.setMaximumWidth(16777215)

        total_height = outer_margins.top() + outer_margins.bottom() + card_height
        return max(76, total_height)

    def _animate_window_resize(self, target_width: int, target_height: int) -> None:
        current_geometry = self.geometry()
        target_geometry = QRect(current_geometry)
        target_geometry.setWidth(target_width)
        target_geometry.setHeight(target_height)

        if not self._user_positioned or self._snap_pos is None:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                target_geometry.moveLeft(available.x() + (available.width() - target_width) // 2)
                target_geometry.moveTop(available.y() + 12)

        if current_geometry == target_geometry:
            return

        self._resize_animation.stop()
        self._resize_animation.setStartValue(current_geometry)
        self._resize_animation.setEndValue(target_geometry)
        self._resize_animation.start()

    def _compact_target_height(self, target_width: int) -> int:
        # Recalculate compact height only from visible compact-mode widgets.
        self.layout().activate()

        outer_layout = self.layout()
        outer_margins = outer_layout.contentsMargins()
        outer_height = outer_margins.top() + outer_margins.bottom()

        card_widget = self.findChild(QWidget, "card")
        card_layout = card_widget.layout() if card_widget is not None else None
        card_margins = card_layout.contentsMargins() if card_layout is not None else outer_margins
        spacing = card_layout.spacing() if card_layout is not None else 0

        content_width = max(320, target_width - outer_margins.left() - outer_margins.right())
        card_width = max(280, content_width - card_margins.left() - card_margins.right())
        compact_width = max(240, card_width - 64)

        compact_height = self.compact_label.heightForWidth(compact_width)
        if compact_height <= 0:
            compact_height = self.compact_label.sizeHint().height()

        total = outer_height + card_margins.top() + card_margins.bottom() + compact_height

        visible_extra_heights = []
        if self.track_title_label.isVisible():
            visible_extra_heights.append(self.track_title_label.sizeHint().height())
        if self.status_label.isVisible():
            visible_extra_heights.append(self.status_label.sizeHint().height())
        if self.next_line_label.isVisible():
            visible_extra_heights.append(self.next_line_label.sizeHint().height())

        if visible_extra_heights:
            total += spacing * len(visible_extra_heights) + sum(visible_extra_heights)

        return max(self._COMPACT_MIN_HEIGHT, total)

    def _position_top_center(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + 12
        self.move(x, y)
        if self._snap_pos is None:
            self._snap_pos = self.pos()

    def _reposition_after_resize(self) -> None:
        if self._user_positioned and self._snap_pos is not None:
            self._snap_pos = self._clamped_horizontal_pos(self._snap_pos)
            self.move(self._snap_pos)
            return
        self._position_top_center()

    def _clamped_horizontal_pos(self, pos: QPoint) -> QPoint:
        # Hanya sumbu X yang dibatasi agar overlay tetap boleh menimpa taskbar.
        screen = QApplication.screenAt(pos) or self.screen() or QApplication.primaryScreen()
        if screen is None:
            return pos

        available = screen.availableGeometry()
        max_x = available.right() - self.width() + 1
        clamped_x = min(max(pos.x(), available.left()), max(available.left(), max_x))
        if clamped_x == pos.x():
            return pos
        return QPoint(clamped_x, pos.y())

    def _on_screen_changed(self, screen) -> None:
        self._last_screen = screen
        self._last_window_size = None
        self._resize_animation.stop()
        self._apply_window_mode()

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        screen = self.screen()
        if screen is not self._last_screen:
            self._on_screen_changed(screen)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        window_handle = self.windowHandle()
        if window_handle is not None and not self._screen_signal_connected:
            window_handle.screenChanged.connect(self._on_screen_changed)
            self._screen_signal_connected = True
        self._last_screen = self.screen()
        suppress_windows_native_frame(self)
        force_windows_topmost(self)
        QTimer.singleShot(0, lambda: suppress_windows_native_frame(self))
        QTimer.singleShot(0, lambda: force_windows_topmost(self))
        if not self._hide_requested:
            self._topmost_timer.start()
        if not self._initial_positioned:
            self._apply_window_mode()
            self._initial_positioned = True

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_compact_text()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self._restore_visible_above_shell)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        if self._allow_exit or self._hide_requested:
            return
        if event.spontaneous():
            QTimer.singleShot(0, self._restore_visible_above_shell)

    def _keep_topmost_above_shell(self) -> None:
        if (
            self._allow_exit
            or self._hide_requested
            or not self.isVisible()
            or self.isMinimized()
            or QApplication.activePopupWidget() is not None
            or QApplication.activeModalWidget() is not None
        ):
            return
        force_windows_topmost(self)

    def _restore_visible_above_shell(self) -> None:
        if self._allow_exit or self._hide_requested:
            return
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        force_windows_topmost(self)

    def enterEvent(self, event) -> None:  # noqa: N802
        super().enterEvent(event)
        self._mouse_over_overlay = True
        if self._uses_hover_controls():
            self._sync_overlay_buttons_ui()
            self._apply_window_mode_if_needed()
        if self._display_style == FLOATING_DISPLAY_STYLE:
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._mouse_over_overlay = False
        if self._uses_hover_controls():
            self._sync_overlay_buttons_ui()
            self._apply_window_mode_if_needed()
        if self._display_style == FLOATING_DISPLAY_STYLE:
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        if (
            self._display_style == FLOATING_DISPLAY_STYLE
            and not self._expanded
            and not self._mouse_over_overlay
        ):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        background = self._overlay_background_qcolor()
        if self._display_style == FLOATING_DISPLAY_STYLE and not self._expanded:
            background.setAlpha(min(background.alpha(), 72))
        painter.setBrush(background)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = min(self._OVERLAY_CORNER_RADIUS, max(1.0, rect.height() / 2))
        painter.drawRoundedRect(rect, radius, radius)

    def _overlay_background_qcolor(self) -> QColor:
        color = QColor(self._overlay_bg_color)
        if color.isValid():
            return color
        return QColor(10, 10, 10, 235)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._snap_pos is not None:
            current_pos = self.pos()
            dx = abs(current_pos.x() - self._snap_pos.x())
            dy = abs(current_pos.y() - self._snap_pos.y())
            if dx <= self._snap_threshold and dy <= self._snap_threshold:
                self.move(self._snap_pos)
            else:
                self._snap_pos = current_pos
                self._user_positioned = True
        self._drag_origin = None
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_R and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.trigger_reconnect_shortcut()
            event.accept()
            return
        if event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.toggle_lyric_color_shortcut()
            event.accept()
            return
        if event.key() == Qt.Key.Key_S and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.toggle_settings()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.hide_to_tray()
            event.accept()
            return
        super().keyPressEvent(event)

    def request_close(self) -> None:
        self.hide_to_tray()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._allow_exit:
            super().closeEvent(event)
            return
        event.ignore()
        self.hide_to_tray()

    def show_from_tray(self) -> None:
        self._hide_requested = False
        was_visible = self.isVisible()
        self.show()
        self.raise_()
        self.activateWindow()
        self._topmost_timer.start()
        force_windows_topmost(self)
        if not was_visible:
            self.overlay_shown.emit()

    def hide_to_tray(self) -> None:
        was_visible = self.isVisible()
        self._hide_requested = True
        self._topmost_timer.stop()
        self.hide()
        if was_visible:
            self.overlay_hidden.emit()

    def open_settings_from_tray(self) -> None:
        self._hide_requested = False
        was_visible = self.isVisible()
        if not was_visible:
            self.show()
        self._topmost_timer.start()
        if not self._expanded:
            self.toggle_settings()
        self.raise_()
        self.activateWindow()
        force_windows_topmost(self)
        if not was_visible:
            self.overlay_shown.emit()

    def allow_exit(self) -> None:
        self._allow_exit = True


def create_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app
