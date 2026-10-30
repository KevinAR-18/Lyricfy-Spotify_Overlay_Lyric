from dataclasses import replace

from lyric_overlay.config import default_config
from lyric_overlay.overlay import OverlayWindow, create_application
from lyric_overlay.settings_theme import PALETTES, normalize_theme, settings_stylesheet


def test_unknown_theme_falls_back_to_midnight():
    assert normalize_theme("unknown") == "midnight"


def test_palettes_use_opaque_colors():
    for name, palette in PALETTES.items():
        assert all(len(color) == 7 for color in palette)
        assert palette[0] in settings_stylesheet(name)


def test_settings_palette_does_not_change_overlay_colors():
    create_application()
    overlay = OverlayWindow()
    config = replace(default_config(), settings_theme="light", overlay_bg_color="#11223344")
    overlay.load_config_values(config)
    assert overlay.current_form_config().settings_theme == "light"
    assert overlay._overlay_bg_color == "#11223344"
    assert "#F3F5F8" in overlay.settings_panel.styleSheet()
    overlay.apply_config_theme(replace(config, settings_theme="warm_dark"))
    assert "#211D1A" in overlay.settings_panel.styleSheet()
    assert overlay._overlay_bg_color == "#11223344"
    overlay.close()
