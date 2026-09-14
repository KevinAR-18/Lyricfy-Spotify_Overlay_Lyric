from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut

from ..config import save_config
from .preferences import needs_artwork
from .settings import CinematicSettings
from .window import CinematicWindow


class CinematicManager(QObject):
    modeChanged = Signal(bool)

    def __init__(self, overlay, controller, parent=None):
        super().__init__(parent)
        self.overlay = overlay
        self.controller = controller
        self.window = None
        self.dialog = None
        self.enabled = controller.config.cinematic_enabled
        self._frame = None
        self._artwork = None
        controller.cinematic_frame.connect(self.set_frame)
        controller.cinematic_artwork.connect(self.set_artwork)
        self.shortcut = QShortcut(QKeySequence("Shift+M"), overlay)
        self.shortcut.activated.connect(lambda: self.set_enabled(not self.enabled))

    def ensure_window(self):
        if self.window is None:
            self.window = CinematicWindow(self.controller.config.cinematic_options)
            self.window.bridge.settingsRequested.connect(self.open_settings)
            self.window.bridge.classicRequested.connect(lambda: self.set_enabled(False))
            self.window.hidden.connect(self.pause_if_hidden)
            if self._frame is not None:
                self.window.bridge.set_frame(self._frame)
            self.window.bridge.set_artwork(self._artwork)
            self.mode_shortcut = QShortcut(QKeySequence("Shift+M"), self.window)
            self.mode_shortcut.activated.connect(lambda: self.set_enabled(False))
        return self.window

    def set_frame(self, frame):
        if self._frame is None or self._frame["track"] != frame["track"]:
            self._artwork = None
        self._frame = frame
        if self.window is not None:
            self.window.bridge.set_frame(frame)

    def set_artwork(self, data):
        self._artwork = data
        if self.window is not None:
            self.window.bridge.set_artwork(data)

    def set_enabled(self, enabled):
        # Load QML before saving the selection, so a load error cannot strand startup.
        if enabled:
            self.ensure_window()
        self.enabled = enabled
        self.controller.config = replace(self.controller.config, cinematic_enabled=enabled)
        save_config(self.controller.config)
        self.modeChanged.emit(enabled)
        self.show()
        self.controller.refresh_album_cover()

    def sync_config(self, config):
        self.enabled = config.cinematic_enabled
        if self.window is not None and self.dialog is None:
            self.window.bridge.set_options(config.cinematic_options)
        self.modeChanged.emit(self.enabled)

    def show(self):
        if self.enabled:
            self.ensure_window().show_from_tray()
            self.overlay.hide_to_tray()
        else:
            self.overlay.show_from_tray()
            if self.window:
                self.window.hide()
        self.controller.resume_polling()

    def hide(self):
        self.overlay.hide_to_tray()
        if self.window:
            self.window.hide()
        if self.dialog:
            self.dialog.reject()
        self.controller.pause_polling()

    def pause_if_hidden(self):
        if not self.overlay.isVisible() and not (self.window and self.window.isVisible()):
            self.controller.pause_polling()

    def snap_home(self):
        if self.enabled:
            self.ensure_window().snap_home()
        else:
            self.overlay.snap_to_home()

    def open_settings(self):
        if self.dialog:
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        window = self.ensure_window()
        self.dialog = CinematicSettings(self.controller.config.cinematic_options)
        self.dialog.preview.connect(self.preview_style)
        self.dialog.saved.connect(self.save_style)
        self.dialog.finished.connect(self.finish_settings)
        self.dialog.show()

    def preview_style(self, options):
        self.window.bridge.set_options(options)
        needs_cover = needs_artwork(options)
        changed = needs_cover != self.controller.cinematic_cover_preview
        self.controller.cinematic_cover_preview = needs_cover
        if changed and needs_cover and not self._artwork:
            self.controller.refresh_album_cover()

    def save_style(self, options):
        self.controller.config = replace(self.controller.config, cinematic_options=options)
        save_config(self.controller.config)
        self.controller.refresh_album_cover()

    def finish_settings(self, result):
        self.controller.cinematic_cover_preview = False
        self.window.bridge.set_options(self.controller.config.cinematic_options)
        self.dialog.deleteLater()
        self.dialog = None

    def shutdown(self):
        if self.dialog:
            self.dialog.reject()
        if self.window:
            self.window.hide()
