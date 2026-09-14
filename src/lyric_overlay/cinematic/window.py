from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtQuick import QQuickView

from .bridge import CinematicBridge


class CinematicWindow(QQuickView):
    hidden = Signal()

    def __init__(self, options: dict):
        super().__init__()
        self.setTitle("Lyricfy — Cinematic Lyrics")
        self.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setColor(QColor("transparent"))
        self.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        self.setMinimumSize(QSize(320, 300))
        self.resize(760, 580)
        self.bridge = CinematicBridge(options, self)
        self.rootContext().setContextProperty("cinematic", self.bridge)
        self.setSource(QUrl.fromLocalFile(str(Path(__file__).with_name("Cinematic.qml"))))
        if self.status() == QQuickView.Status.Error:
            raise RuntimeError("Unable to load Cinematic Lyrics: " + "; ".join(e.toString() for e in self.errors()))
        self.bridge.hideRequested.connect(self.hide_to_tray)
        self.bridge.fullscreenRequested.connect(self.toggle_fullscreen)
        self.bridge.homeRequested.connect(self.snap_home)
        self._shortcuts = []
        for key, callback in (("F11", self.toggle_fullscreen), ("Escape", self.exit_fullscreen),
                              ("Shift+S", self.bridge.settingsRequested.emit),
                              ("Shift+F", self.hide_to_tray), ("Shift+H", self.snap_home)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self.snap_home()

    def snap_home(self):
        screen = self.screen()
        if screen and self.visibility() != self.Visibility.FullScreen:
            area = screen.availableGeometry()
            self.setPosition(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)

    def toggle_fullscreen(self):
        if self.visibility() == self.Visibility.FullScreen:
            self.showNormal()
        else:
            self.showFullScreen()

    def exit_fullscreen(self):
        if self.visibility() == self.Visibility.FullScreen:
            self.showNormal()

    def show_from_tray(self):
        self.show()
        self.raise_()
        self.requestActivate()

    def hide_to_tray(self):
        self.hide()
        self.hidden.emit()

    def closeEvent(self, event):
        event.ignore()
        self.hide_to_tray()
