from __future__ import annotations

import base64

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Property, Signal, Slot
from PySide6.QtGui import QColor, QImage

from .preferences import normalize_options


class CinematicBridge(QObject):
    optionsChanged = Signal()
    frameChanged = Signal()
    artworkChanged = Signal()
    settingsRequested = Signal()
    hideRequested = Signal()
    classicRequested = Signal()
    fullscreenRequested = Signal()
    homeRequested = Signal()

    def __init__(self, options: dict, parent=None):
        super().__init__(parent)
        self._options = normalize_options(options)
        self._frame = {"track": "", "title": "Lyricfy", "artist": "Open Spotify to start",
                       "playing": False, "index": -1, "rows": [], "duration": 400,
                       "sequential": False, "message": "Waiting for playback"}
        self._artwork = ""
        self._album_color = "#46304F"
        self._signature = None
        self._progress = None

    @Property("QVariantMap", notify=optionsChanged)
    def options(self):
        return self._options

    @Property("QVariantMap", notify=frameChanged)
    def frame(self):
        return self._frame

    @Property(str, notify=artworkChanged)
    def artwork(self):
        return self._artwork

    @Property(str, notify=artworkChanged)
    def albumColor(self):
        return self._album_color

    def set_options(self, options: dict):
        self._options = normalize_options(options)
        self.optionsChanged.emit()

    def set_frame(self, frame: dict):
        progress = frame.get("progress", 0)
        discontinuity = self._progress is not None and (progress < self._progress - 200 or progress > self._progress + 1500)
        self._progress = progress
        signature = (frame["track"], frame["index"], frame["playing"], frame["title"],
                     frame["artist"], frame["message"], tuple((r["index"], r["text"]) for r in frame["rows"]))
        if signature == self._signature and not discontinuity:
            return
        sequential = (self._frame["track"] == frame["track"]
                      and frame["index"] == self._frame["index"] + 1
                      and not discontinuity)
        if self._frame["track"] != frame["track"]:
            self.set_artwork(None)
        self._frame = dict(frame, sequential=sequential,
                           duration=max(80, min(self._options["duration"], frame.get("remaining", 1000) * 0.7)))
        self._signature = signature
        self.frameChanged.emit()

    def set_artwork(self, data: bytes | None):
        self._artwork = ""
        self._album_color = "#46304F"
        if data:
            image = QImage.fromData(data)
            if not image.isNull():
                png = QByteArray()
                buffer = QBuffer(png)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(buffer, "PNG")
                buffer.close()
                self._artwork = "data:image/png;base64," + base64.b64encode(bytes(png)).decode("ascii")
                sample = image.scaled(1, 1).pixelColor(0, 0)
                hue = max(0.0, sample.hsvHueF())
                self._album_color = QColor.fromHsvF(hue, max(0.25, sample.hsvSaturationF()), 0.32).name()
        self.artworkChanged.emit()

    @Slot(str)
    def command(self, action: str):
        signals = {"settings": self.settingsRequested, "hide": self.hideRequested,
                   "classic": self.classicRequested, "fullscreen": self.fullscreenRequested,
                   "home": self.homeRequested}
        if action in signals:
            signals[action].emit()
