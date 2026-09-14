"""Small, layout-independent lyric transitions for the classic Qt Widgets overlay."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QLabel, QWidget, QGraphicsDropShadowEffect


class AnimatedLyricLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self._previous = QPixmap()
        self.transition_masked = False
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
        if self.transition_masked:
            return
        # The existing drop-shadow effect wraps this paint pass, preserving lyric glow.
        painter = QPainter(self)
        self._paint_text(painter)
        painter.end()

    def hideEvent(self, event):
        self.finish_transition()
        super().hideEvent(event)


class LyricTransitionLayer(QWidget):
    """One timeline moves current/next blocks between their real layout slots.

    Layout labels keep measuring/wrapping text, while this transparent surface
    paints the transition. Retargeting captures the current composited frame.
    """

    def __init__(self, parent, labels):
        super().__init__(parent)
        self.labels = labels
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._advance)
        self._animation.finished.connect(self.finish)
        self.progress = 1.0
        self.blocks = []
        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setBlurRadius(18)
        self.glow.setOffset(0, 0)
        self.setGraphicsEffect(self.glow)
        self.hide()

    def _advance(self, value):
        self.progress = float(value)
        self.update()

    def snapshot(self):
        if self.isVisible():
            image = QPixmap(self.size() * self.devicePixelRatioF())
            image.setDevicePixelRatio(self.devicePixelRatioF())
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            self._paint(painter)
            painter.end()
            return [(image, QRectF(self.geometry()), "")]
        result = []
        for label in self.labels:
            if label.isVisible() and label.text():
                pos = label.mapTo(self.parentWidget(), label.rect().topLeft())
                result.append((label.capture_text(), QRectF(pos.x(), pos.y(), label.width(), label.height()), " ".join(label.text().split())))
        return result

    def start(self, old, duration, color):
        self.finish()
        new = self.snapshot()
        if not old or not new or duration <= 0:
            return
        bounds = QRectF(new[0][1])
        for _, rect, _ in new[1:]:
            bounds = bounds.united(rect)
        self.setGeometry(bounds.toAlignedRect())
        origin = bounds.topLeft()
        self.blocks = []
        old_current, old_rect, _ = old[0]
        old_rect = old_rect.translated(-origin)
        self.blocks.append((old_current, old_current, old_rect, old_rect.translated(0, -max(old_rect.height(), 24)), 1.0, 0.0))
        for index, (image, rect, text) in enumerate(new):
            target = rect.translated(-origin)
            if index == 0 and len(old) > 1 and old[1][2] == text:
                source_image, source_rect, _ = old[1]
                self.blocks.append((source_image, image, source_rect.translated(-origin), target, 1.0, 1.0))
            else:
                source = target.translated(0, max(target.height(), 24))
                self.blocks.append((image, image, source, target, 0.0, 1.0))
        for label in self.labels:
            label.finish_transition()
            label.transition_masked = True
            label.update()
        self.glow.setColor(color)
        self.progress = 0.0
        self.show()
        self.raise_()
        self._animation.setDuration(duration)
        self._animation.start()

    def finish(self):
        self._animation.stop()
        self.progress = 1.0
        self.blocks = []
        self.hide()
        for label in self.labels:
            label.transition_masked = False
            label.update()

    def _paint(self, painter):
        p = self.progress
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for old, new, start, end, first_opacity, last_opacity in self.blocks:
            rect = QRectF(start.x() + (end.x() - start.x()) * p,
                          start.y() + (end.y() - start.y()) * p,
                          start.width() + (end.width() - start.width()) * p,
                          start.height() + (end.height() - start.height()) * p)
            opacity = first_opacity + (last_opacity - first_opacity) * p
            painter.setOpacity(opacity * (1 - p))
            painter.drawPixmap(rect, old, QRectF(old.rect()))
            painter.setOpacity(opacity * p)
            painter.drawPixmap(rect, new, QRectF(new.rect()))

    def paintEvent(self, event):
        painter = QPainter(self)
        self._paint(painter)
        painter.end()
