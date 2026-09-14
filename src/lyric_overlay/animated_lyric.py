"""Small, layout-independent lyric transitions for the classic Qt Widgets overlay."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QLabel


class AnimatedLyricLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self._previous = QPixmap()
        self._progress = 1.0
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._advance)
        self._animation.finished.connect(self.finish_transition)

    def _advance(self, value):
        self._progress = float(value)
        self.update()

    def capture_text(self):
        if not self.isVisible() or not self.text():
            return QPixmap()
        ratio = self.devicePixelRatioF()
        image = QPixmap(round(self.width() * ratio), round(self.height() * ratio))
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self._paint_text(painter)
        painter.end()
        return image

    def start_transition(self, previous, duration):
        self.finish_transition()
        if previous.isNull() or not self.isVisible() or not self.text() or duration <= 0:
            return
        self._previous = previous
        self._progress = 0.0
        self._animation.setDuration(duration)
        self._animation.start()

    def finish_transition(self):
        self._animation.stop()
        self._previous = QPixmap()
        self._progress = 1.0
        self.update()

    def _paint_text(self, painter):
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        progress = self._progress
        if not self._previous.isNull():
            painter.setOpacity(1.0 - progress)
            painter.drawPixmap(QPointF(0, -5 * progress), self._previous)
        painter.setOpacity(progress)
        rect = QRectF(self.contentsRect())
        rect.translate(0, 5 * (1.0 - progress))
        flags = int(self.alignment())
        if self.wordWrap():
            flags |= int(Qt.TextFlag.TextWordWrap)
        painter.drawText(rect, flags, self.text())

    def paintEvent(self, event):
        # The existing drop-shadow effect wraps this paint pass, preserving lyric glow.
        painter = QPainter(self)
        self._paint_text(painter)
        painter.end()

    def hideEvent(self, event):
        self.finish_transition()
        super().hideEvent(event)
