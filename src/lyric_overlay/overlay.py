from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig
from .models import TrackInfo


class OverlayWindow(QWidget):
    save_requested = Signal(object)
    reconnect_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._drag_origin = None
        self._initial_positioned = False
        self._expanded = False
        self._snap_pos = None
        self._snap_threshold = 28
        self._user_positioned = False
        self._allow_exit = False
        self._track_text = "Spotify tidak sedang memutar lagu"
        self._artist_text = ""
        self._current_line_text = ""
        self._status_text = ""
        self._header_visible_until = 0.0
        self._overlay_bg_color = "#0A0A0AEB"
        self._overlay_text_color = "#F4F4F4"
        self._lyric_text_color = "#F4F4F4"
        self._lyric_glow_color = "#66CCFFFF"
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Lyricfy")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(640, 76)
        self.resize(640, 76)

        root = QWidget(self)
        root.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
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
        self.close_button.setText("x")
        self.close_button.setToolTip("Tray mode")
        self.close_button.clicked.connect(self.request_close)

        self.compact_label = QLabel("Spotify tidak sedang memutar lagu")
        self.compact_label.setFont(QFont("Segoe UI Semibold", 11))
        self.compact_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.compact_label.setMinimumWidth(540)
        self.compact_label.setWordWrap(True)
        self.compact_label.setMaximumHeight(38)

        header_layout.addWidget(self.compact_label, 1)
        header_layout.addWidget(self.settings_button)
        header_layout.addWidget(self.close_button)

        self.track_title_label = QLabel("")
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
        settings_layout.setSpacing(8)

        self.client_id_input = self._create_input("Enter Spotify Client ID")
        self.client_secret_input = self._create_input("Enter Spotify Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.redirect_uri_input = self._create_input("Enter Redirect URI")
        self.lyric_offset_input = self._create_input("Example: -250 or 300")
        self.overlay_color_input = self._create_input("Example: #0A0A0AEB")
        self.text_color_input = self._create_input("Example: #F4F4F4")
        self.lyric_color_input = self._create_input("Example: #F4F4F4")
        self.glow_color_input = self._create_input("Example: #66CCFFFF")

        settings_actions = QHBoxLayout()
        settings_actions.setSpacing(8)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._emit_save)

        self.reconnect_button = QPushButton("Reload Spotify")
        self.reconnect_button.clicked.connect(self.reconnect_requested.emit)

        settings_actions.addWidget(self.save_button)
        settings_actions.addWidget(self.reconnect_button)
        settings_actions.addStretch(1)

        settings_layout.addWidget(self._create_field("Spotify Client ID", self.client_id_input))
        settings_layout.addWidget(self._create_field("Spotify Client Secret", self.client_secret_input))
        settings_layout.addWidget(self._create_field("Redirect URI", self.redirect_uri_input))
        settings_layout.addWidget(self._create_offset_field())
        settings_layout.addWidget(self._create_field("Overlay Color", self.overlay_color_input))
        settings_layout.addWidget(self._create_field("Text Color", self.text_color_input))
        settings_layout.addWidget(self._create_field("Lyric Color", self.lyric_color_input))
        settings_layout.addWidget(self._create_field("Lyric Glow Color", self.glow_color_input))
        settings_layout.addLayout(settings_actions)
        self.settings_panel.hide()

        card_layout.addLayout(header_layout)
        card_layout.addWidget(self.track_title_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.settings_panel)

        self._lyric_glow = QGraphicsDropShadowEffect(self)
        self._lyric_glow.setBlurRadius(18)
        self._lyric_glow.setOffset(0, 0)
        self.compact_label.setGraphicsEffect(self._lyric_glow)

        self._apply_theme()
        self._refresh_compact_text()

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#card {{
                background: {self._overlay_bg_color};
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 26px;
            }}
            QLabel {{
                color: {self._overlay_text_color};
                background: transparent;
            }}
            QLabel#compactLyric {{
                color: {self._lyric_text_color};
            }}
            QLineEdit {{
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 10px;
                color: {self._overlay_text_color};
                padding: 6px 10px;
                min-height: 32px;
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
        self._lyric_glow.setColor(QColor(self._lyric_glow_color))

    def _create_input(self, placeholder: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        return widget

    def _create_field(self, label_text: str, input_widget: QLineEdit) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Segoe UI Semibold", 9))
        layout.addWidget(label)
        layout.addWidget(input_widget)
        return container

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
        self.client_id_input.setText(config.spotify_client_id)
        self.client_secret_input.setText(config.spotify_client_secret)
        self.redirect_uri_input.setText(config.spotify_redirect_uri)
        self.lyric_offset_input.setText(str(config.lyric_offset_ms))
        self.overlay_color_input.setText(config.overlay_bg_color)
        self.text_color_input.setText(config.overlay_text_color)
        self.lyric_color_input.setText(config.lyric_text_color)
        self.glow_color_input.setText(config.lyric_glow_color)
        self.apply_config_theme(config)

    def current_form_config(self) -> AppConfig:
        try:
            lyric_offset_ms = int(self.lyric_offset_input.text().strip() or "0")
        except ValueError:
            lyric_offset_ms = 0

        return AppConfig(
            spotify_client_id=self.client_id_input.text().strip(),
            spotify_client_secret=self.client_secret_input.text().strip(),
            spotify_redirect_uri=self.redirect_uri_input.text().strip(),
            poll_interval_ms=2500,
            lrclib_enabled=True,
            lyric_offset_ms=lyric_offset_ms,
            overlay_bg_color=self.overlay_color_input.text().strip() or "#0A0A0AEB",
            overlay_text_color=self.text_color_input.text().strip() or "#F4F4F4",
            lyric_text_color=self.lyric_color_input.text().strip() or "#F4F4F4",
            lyric_glow_color=self.glow_color_input.text().strip() or "#66CCFFFF",
        )

    def apply_config_theme(self, config: AppConfig) -> None:
        self._overlay_bg_color = config.overlay_bg_color or "#0A0A0AEB"
        self._overlay_text_color = config.overlay_text_color or "#F4F4F4"
        self._lyric_text_color = config.lyric_text_color or "#F4F4F4"
        self._lyric_glow_color = config.lyric_glow_color or "#66CCFFFF"
        self._apply_theme()

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
        if visibility_changed:
            self._apply_window_mode()

    def toggle_settings(self) -> None:
        self._expanded = not self._expanded
        self.settings_panel.setVisible(self._expanded)
        self.status_label.setVisible(bool(self._status_text) or self._expanded)
        self._apply_window_mode()

    def _emit_save(self) -> None:
        self.save_requested.emit(self.current_form_config())

    def set_track(self, track: TrackInfo | None, lyrics_source: str = "") -> None:
        del lyrics_source
        if track is None:
            self._track_text = "Spotify is not playing"
            self._artist_text = "Waiting for playback"
            self._header_visible_until = 0.0
            self._refresh_compact_text()
            return

        previous_title = self._track_text
        previous_artist = self._artist_text
        self._track_text = track.title
        self._artist_text = track.artist
        if self._track_text != previous_title or self._artist_text != previous_artist:
            self._header_visible_until = time.monotonic() + 10.0
        self._refresh_compact_text()

    def set_lines(self, current_line: str, next_line: str) -> None:
        del next_line
        self._current_line_text = current_line.strip()
        self._refresh_compact_text()

    def set_paused(self) -> None:
        self._status_text = "Playback paused"
        self.status_label.setText(self._status_text)
        self.status_label.setVisible(True)
        self._refresh_compact_text()
        self._apply_window_mode()

    def _refresh_compact_text(self) -> None:
        title_text = self._track_text.strip()
        artist_text = self._artist_text.strip()
        header_text = f"{artist_text} - {title_text}" if artist_text and title_text else (artist_text or title_text)
        self.track_title_label.setText(header_text)
        self.track_title_label.setVisible(bool(header_text) and time.monotonic() < self._header_visible_until)

        if self._current_line_text:
            compact_text = self._current_line_text
        elif artist_text:
            compact_text = artist_text
        else:
            compact_text = title_text

        self.compact_label.setText(compact_text)

    def _apply_window_mode(self) -> None:
        target_width = 640 if not self._expanded else 760
        if self._expanded:
            target_height = 470
        else:
            target_height = 82 if self.compact_label.heightForWidth(self.compact_label.width()) <= 24 else 100
        self.setMinimumSize(target_width, 76)
        self.resize(target_width, target_height)
        self._reposition_after_resize()

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
            self.move(self._snap_pos)
            return
        self._position_top_center()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._initial_positioned:
            self._apply_window_mode()
            self._initial_positioned = True

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
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

    def request_close(self) -> None:
        self.show_status("Lyricfy is running from the system tray.")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._allow_exit:
            super().closeEvent(event)
            return
        event.ignore()
        self.show_status("Lyricfy is running from the system tray.")

    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self) -> None:
        self.hide()

    def open_settings_from_tray(self) -> None:
        if not self.isVisible():
            self.show()
        if not self._expanded:
            self.toggle_settings()
        self.raise_()
        self.activateWindow()

    def allow_exit(self) -> None:
        self._allow_exit = True


def create_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(True)
    return app
