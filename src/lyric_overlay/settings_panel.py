"""Tabbed settings content embedded in the classic overlay window."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from . import __version__
from .cinematic.settings import CinematicEditor
from .config import SPOTIFY_API_PLAYBACK_SOURCE, WINDOWS_PLAYBACK_SOURCE


def choice_buttons(choices):
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    group = QButtonGroup(widget)
    buttons = {}
    for value, label in choices:
        button = QPushButton(label)
        button.setCheckable(True)
        group.addButton(button)
        layout.addWidget(button)
        buttons[value] = button
    return widget, buttons


def build_settings_panel(overlay):
    o = overlay
    layout = o.settings_panel.layout()
    o.settings_panel.setObjectName("settingsPanel")
    # Inherit Classic's live theme. The existing lyric header stays above the tabs.
    o.settings_tabs = QTabWidget()
    o.settings_tabs.setMinimumSize(0, 0)
    o.settings_tabs.setUsesScrollButtons(True)
    layout.addWidget(o.settings_tabs, 1)

    def tab(name):
        body = QWidget()
        body.setObjectName("tabBody")
        box = QVBoxLayout(body)
        box.setContentsMargins(12, 4, 12, 12)
        box.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        scroll.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        o.settings_tabs.addTab(scroll, name)
        return box

    def section(box, title):
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        box.addWidget(label)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(8)
        box.addLayout(form)
        return form

    def note(box, text):
        label = QLabel(text)
        label.setWordWrap(True)
        box.addWidget(label)
        return label

    def color_field(edit):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        edit.setMinimumWidth(0)
        button = QPushButton("Color…")
        def update_swatch():
            color = QColor(edit.text())
            if color.isValid():
                button.setStyleSheet(f"border-left: 14px solid {color.name()};")
        def choose():
            color = QColorDialog.getColor(QColor(edit.text()), o, "Choose color", QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                edit.setText(color.name(QColor.NameFormat.HexArgb))
        button.clicked.connect(choose)
        edit.textChanged.connect(update_swatch)
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(button)
        return row

    general = tab("General")
    form = section(general, "Startup")
    form.addRow(o.autostart_checkbox)
    form.addRow("When auto-started", o.startup_visibility_input)
    o.autostart_checkbox.toggled.connect(o.startup_visibility_input.setEnabled)
    form = section(general, "Overlay controls")
    o.show_settings_checkbox = QCheckBox("Show Settings button")
    o.show_hide_checkbox = QCheckBox("Show Hide button")
    form.addRow(o.show_settings_checkbox)
    form.addRow(o.show_hide_checkbox)
    form.addRow(o.hover_buttons_checkbox)
    note(general, "Floating controls appear on hover and respect the button preferences above.")
    section(general, "Shortcuts")
    general.addWidget(o.shortcuts_label)
    note(general, "Shift+M — Classic / Cinematic\nCinematic: F11 / double-click — fullscreen; Esc — leave fullscreen.\nShortcuts act on the focused overlay window.")
    section(general, "About")
    note(general, f"Lyricfy {__version__}")
    general.addStretch()

    playback = tab("Playback")
    section(playback, "Playback source")
    source_widget, o.playback_buttons = choice_buttons(((WINDOWS_PLAYBACK_SOURCE, "Non-API (Windows)"), (SPOTIFY_API_PLAYBACK_SOURCE, "Spotify API")))
    playback.addWidget(source_widget)
    for source, button in o.playback_buttons.items():
        button.clicked.connect(lambda checked=False, value=source: o.select_playback_source(value))
    o.playback_note = note(playback, "")
    o.credentials_section = QWidget()
    credentials = QFormLayout(o.credentials_section)
    credentials.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    credentials.addRow("Client ID", o.client_id_input)
    secret = QWidget()
    secret_layout = QHBoxLayout(secret)
    secret_layout.setContentsMargins(0, 0, 0, 0)
    secret_layout.addWidget(o.client_secret_input, 1)
    show = QPushButton("Show")
    show.setCheckable(True)
    show.toggled.connect(lambda checked: (o.client_secret_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password), show.setText("Hide" if checked else "Show")))
    secret_layout.addWidget(show)
    credentials.addRow("Client secret", secret)
    credentials.addRow("Redirect URI", o.redirect_uri_input)
    dashboard = QLabel('<a href="https://developer.spotify.com/dashboard">Spotify Developer Dashboard</a>')
    dashboard.setOpenExternalLinks(True)
    credentials.addRow(dashboard)
    playback.addWidget(o.credentials_section)
    o.playback_status = note(playback, "Waiting for playback")
    playback.addWidget(o.reconnect_button)
    form = section(playback, "Advanced")
    o.poll_interval_input = QSpinBox()
    o.poll_interval_input.setRange(250, 60000)
    o.poll_interval_input.setSuffix(" ms")
    form.addRow("Polling interval", o.poll_interval_input)
    note(playback, "Apply playback changes before reconnecting. Lower intervals request playback more frequently.")
    playback.addStretch()

    appearance = tab("Appearance")
    section(appearance, "Presentation")
    presentation, o.presentation_buttons = choice_buttons(((False, "Classic"), (True, "Cinematic")))
    appearance.addWidget(presentation)
    customize = QPushButton("Customize Cinematic →")
    customize.clicked.connect(lambda: o.settings_tabs.setCurrentIndex(3))
    appearance.addWidget(customize)
    form = section(appearance, "Classic display")
    for label, control in (("Preset", o.display_preset_input), ("Style", o.display_style_input), ("Lyric lines", o.lyric_lines_input), ("Track information", o.track_info_mode_input)):
        form.addRow(label, control)
    form = section(appearance, "Typography")
    for label, control in (("Font", o.font_family_input), ("Size", o.font_size_input), ("Alignment", o.text_alignment_input)):
        form.addRow(label, control)
    form = section(appearance, "Colors")
    for label, control in (("Background", o.overlay_color_input), ("Secondary text", o.text_color_input), ("Active lyric", o.lyric_color_input), ("Glow", o.glow_color_input), ("Toggle lyric", o.toggle_color_input)):
        form.addRow(label, color_field(control))
    form = section(appearance, "Artwork & layout")
    form.addRow(o.show_album_cover_checkbox)
    for label, control in (("Floating cover", o.floating_cover_mode_input), ("Track info gap", o.track_info_gap_input), ("Corner radius", o.overlay_corner_radius_input)):
        form.addRow(label, control)
    appearance.addStretch()

    cinematic = tab("Cinematic")
    o.cinematic_editor = CinematicEditor({})
    cinematic.addWidget(o.cinematic_editor)
    o.cinematic_editor.preview.connect(o.preview_cinematic_options)

    lyrics = tab("Lyrics")
    section(lyrics, "Synchronization")
    lyrics.addWidget(o._create_offset_field())
    note(lyrics, "Positive offset advances lyrics; negative offset delays them.")
    zero = QPushButton("Reset offset to 0")
    zero.clicked.connect(lambda: o.lyric_offset_input.setText("0"))
    lyrics.addWidget(zero)
    section(lyrics, "Lyrics source")
    o.lrclib_checkbox = QCheckBox("Enable LRCLIB lookup")
    lyrics.addWidget(o.lrclib_checkbox)
    note(lyrics, "Local .lrc files are checked first, then LRCLIB if enabled.")
    section(lyrics, "Cache")
    lyrics.addWidget(o.auto_save_lrc_checkbox)
    lyrics.addWidget(o.clear_cache_button)
    note(lyrics, "Clearing downloaded lyrics is immediate and cannot be undone with Cancel.")
    lyrics.addStretch()

    # Reset lives inside the scroll area so the footer fits scaled displays.
    for index in range(o.settings_tabs.count()):
        reset = QPushButton("Reset this tab to defaults")
        reset.clicked.connect(o.reset_settings_tab)
        body_layout = o.settings_tabs.widget(index).widget().layout()
        body_layout.addWidget(reset)
    for combo in o.settings_panel.findChildren(QComboBox):
        o._install_popup_topmost_guard(combo)

    footer = QHBoxLayout()
    o.settings_feedback = QLabel("")
    o.settings_feedback.setWordWrap(True)
    o.settings_feedback.setMinimumWidth(0)
    footer.addWidget(o.settings_feedback, 1)
    o.close_settings_button.setText("Cancel")
    footer.addWidget(o.close_settings_button)
    o.apply_button = QPushButton("Apply")
    o.apply_button.clicked.connect(o.apply_settings)
    footer.addWidget(o.apply_button)
    o.save_button.setObjectName("primary")
    footer.addWidget(o.save_button)
    layout.addLayout(footer)

    # All form changes feed one dirty-state/preview path; loading is guarded.
    for control in o.settings_panel.findChildren(QWidget):
        if isinstance(control, QLineEdit):
            control.textChanged.connect(o.settings_edited)
        elif isinstance(control, QComboBox):
            control.currentIndexChanged.connect(o.settings_edited)
        elif isinstance(control, QSpinBox):
            control.valueChanged.connect(o.settings_edited)
        elif isinstance(control, (QCheckBox, QPushButton)) and control.isCheckable():
            control.toggled.connect(o.settings_edited)
