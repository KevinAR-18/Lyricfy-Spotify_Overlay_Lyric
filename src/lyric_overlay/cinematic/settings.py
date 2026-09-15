from __future__ import annotations

from PySide6.QtCore import Signal, QSignalBlocker
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFontComboBox, QFormLayout, QLabel, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from ..font_combobox import CompactFontComboBox
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
    "ambient_effect": "Ambient effect", "ambient_intensity": "Ambient intensity (%)",
}

CHOICE_LABELS = {
    "ambient_effect": {
        "none": "None",
        "leaves": "Autumn Leaves",
        "snowfall": "Winter Snowfall",
        "rain": "Gentle Rain",
        "fireflies": "Fireflies",
        "blobs": "Fluid Color Blobs",
        "stardust": "Stardust",
        "sakura": "Cherry Blossoms (Sakura)",
        "bubbles": "Floating Bubbles",
        "underwater": "Underwater",
        "shooting_stars": "Shooting Stars",
        "embers": "Fiery Embers",
        "light_beams": "Light Beams",
    },
}


class CinematicEditor(QWidget):
    preview = Signal(object)

    def __init__(self, options: dict):
        super().__init__()
        self.options = normalize_options(options)
        self.controls = {}
        layout = QVBoxLayout(self)
        note = QLabel("Changes preview live. Long lyrics wrap automatically at the maximum width.")
        note.setWordWrap(True)
        layout.addWidget(note)
        groups = {
            "Typography": ("font_family", "font_size", "bold", "alignment"),
            "Lyric colors": ("active_color", "previous_color", "next_color", "context_opacity"),
            "Layout": ("text_width", "padding", "gap"),
            "Background": ("background", "background_color", "gradient_color", "background_motion"),
            "Motion & glow": ("duration", "motion", "glow_color", "glow_strength", "vignette"),
            "Ambient effects": ("ambient_effect", "ambient_intensity"),
            "Track details": ("show_info", "show_cover"),
        }
        for title, keys in groups.items():
            heading = QLabel(title)
            heading.setObjectName("sectionTitle")
            layout.addWidget(heading)
            form = QFormLayout()
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            layout.addLayout(form)
            for key in keys:
                self._add_control(form, key)
        layout.addStretch()
        self.sync_enabled()

    def _add_control(self, form, key):
        default = DEFAULTS[key]
        value = self.options[key]
        if key == "font_family":
            control = CompactFontComboBox()
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
            labels = CHOICE_LABELS.get(key, {})
            for choice in CHOICES[key]:
                control.addItem(labels.get(choice, choice.title()), choice)
            control.setCurrentIndex(control.findData(value))
            control.currentIndexChanged.connect(lambda index, k=key, c=control: self.update_option(k, c.itemData(index)))
        else:
            control = QPushButton(value)
            control.clicked.connect(lambda checked=False, k=key: self.choose_color(k))
        self.controls[key] = control
        form.addRow(LABELS[key], control)

    def load_options(self, options):
        self.options = normalize_options(options)
        for key, control in self.controls.items():
            value = self.options[key]
            with QSignalBlocker(control):
                if key == "font_family":
                    control.setCurrentFont(QFont(value))
                elif isinstance(control, QCheckBox):
                    control.setChecked(value)
                elif isinstance(control, QSpinBox):
                    control.setValue(value)
                elif isinstance(control, QComboBox):
                    control.setCurrentIndex(control.findData(value))
                else:
                    control.setText(value)
        self.sync_enabled()

    def sync_enabled(self):
        background = self.options["background"]
        self.controls["background_color"].setEnabled(background in ("solid", "gradient"))
        self.controls["gradient_color"].setEnabled(background == "gradient")
        self.controls["ambient_intensity"].setEnabled(self.options["ambient_effect"] != "none")

    def update_option(self, key, value):
        self.options[key] = value
        self.options = normalize_options(self.options)
        self.sync_enabled()
        self.preview.emit(dict(self.options))

    def choose_color(self, key):
        color = QColorDialog.getColor(QColor(self.options[key]), self, LABELS[key], QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            value = color.name(QColor.NameFormat.HexArgb)
            self.controls[key].setText(value)
            self.update_option(key, value)

class CinematicSettings(QDialog):
    """Standalone editor retained for the offline cinematic demo."""

    preview = Signal(object)
    saved = Signal(object)

    def __init__(self, options: dict):
        super().__init__()
        self.setWindowTitle("Lyricfy — Cinematic Style")
        self.resize(480, 660)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.editor = CinematicEditor(options)
        self.controls = self.editor.controls
        self.editor.preview.connect(self.preview)
        scroll.setWidget(self.editor)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def options(self):
        return self.editor.options

    def update_option(self, key, value):
        self.editor.update_option(key, value)

    def save(self):
        self.saved.emit(dict(self.editor.options))
        self.accept()
