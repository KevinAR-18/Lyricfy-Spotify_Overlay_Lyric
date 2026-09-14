from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QFontComboBox


class CompactFontComboBox(QFontComboBox):
    """Font combo box whose popup dropdown width matches the control rather
    than expanding to the maximum font family name width across all system fonts.
    """

    def showPopup(self) -> None:
        super().showPopup()
        popup = self.view().window()
        target_width = self.width()
        self.view().setMinimumWidth(0)
        self.view().setMaximumWidth(target_width)
        popup.setMinimumWidth(0)
        popup.setMaximumWidth(target_width)
        popup.resize(target_width, popup.height())
        global_pos = self.mapToGlobal(QPoint(0, 0))
        popup.move(global_pos.x(), popup.y())
