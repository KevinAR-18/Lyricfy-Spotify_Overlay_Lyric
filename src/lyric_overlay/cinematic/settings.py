from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFontComboBox, QFormLayout, QLabel, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from .preferences import CHOICES, DEFAULTS, RANGES, normalize_options


LABELS = {
    "font_family": "Font", "font_size": "Font size (px)", "bold": "Bold lyrics",
    "alignment": "Alignment", "active_color": "Active lyric color",
    "previous_color": "Previous lyric color", "next_color": "Next lyric color",
    "context_opacity": "Context opacity (%)", "text_width": "Maximum lyric width (px)",
    "padding": "Padding (px)", "gap": "Space between lyric blocks (px)",
    "background": "Background", "background_color": "Background color",
    "gradient_color": "Gradient color", "background_motion": "Moving background",
    "glow_color": "Glow color", "glow_strength": "Glow intensity (%)",
    "vignette": "Vignette intensity (%)", "duration": "Transition duration (ms)",
    "motion": "Motion intensity (%)", "show_info": "Show title and artist",
    "show_cover": "Show album cover",
}


class CinematicSettings(QDialog):
    preview = Signal(object)
    saved = Signal(object)

    def __init__(self, options: dict):
        super().__init__()
        self.setWindowTitle("Lyricfy — Cinematic Style")
        self.resize(480, 660)
        self.options = normalize_options(options)
        self.controls = {}
        layout = QVBoxLayout(self)
        note = QLabel("Changes preview live. Long lyrics wrap automatically at the maximum width.")
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        for key, default in DEFAULTS.items():
            value = self.options[key]
            if key == "font_family":
                control = QFontComboBox()
                control.setCurrentFont(QFont(value))
                control.currentFontChanged.connect(lambda font, k=key: self.update_option(k, font.family()))
            elif isinstance(default, bool):
                control = QCheckBox()
                control.setChecked(value)
                control.toggled.connect(lambda checked, k=key: self.update_option(k, checked))
            elif key in RANGES:
                control = QSpinBox()
                control.setRange(*RANGES[key])
                control.setValue(value)
                control.valueChanged.connect(lambda number, k=key: self.update_option(k, number))
            elif key in CHOICES:
                control = QComboBox()
                for choice in CHOICES[key]:
                    control.addItem(choice.title(), choice)
                control.setCurrentIndex(control.findData(value))
                control.currentIndexChanged.connect(lambda index, k=key, c=control: self.update_option(k, c.itemData(index)))
            else:
                control = QPushButton(value)
                control.clicked.connect(lambda checked=False, k=key: self.choose_color(k))
            self.controls[key] = control
            form.addRow(LABELS[key], control)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_option(self, key, value):
        self.options[key] = value
        self.options = normalize_options(self.options)
        self.preview.emit(dict(self.options))

    def choose_color(self, key):
        color = QColorDialog.getColor(QColor(self.options[key]), self, LABELS[key], QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            value = color.name(QColor.NameFormat.HexArgb)
            self.controls[key].setText(value)
            self.update_option(key, value)

    def save(self):
        self.saved.emit(dict(self.options))
        self.accept()
