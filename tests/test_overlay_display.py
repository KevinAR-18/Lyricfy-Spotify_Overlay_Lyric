from dataclasses import replace

from lyric_overlay.config import (
    CARD_DEFAULT_PRESET,
    FLOATING_CONTEXT_PRESET,
    FLOATING_MINIMAL_PRESET,
    default_config,
)
from lyric_overlay.overlay import OverlayWindow, create_application


def _overlay():
    create_application()
    overlay = OverlayWindow()
    overlay.load_config_values(default_config())
    return overlay


def test_floating_minimal_hides_next_line():
    overlay = _overlay()
    overlay._lyrics_available = True
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay.set_lines("Current", "Next")
    assert overlay.compact_label.text() == "Current"
    assert overlay.next_line_label.isHidden()


def test_floating_context_shows_small_next_line():
    overlay = _overlay()
    overlay._lyrics_available = True
    overlay.apply_display_preset(FLOATING_CONTEXT_PRESET)
    overlay.set_lines("Current", "Next")
    assert overlay.next_line_label.text() == "Next"
    assert not overlay.next_line_label.isHidden()
    assert overlay.next_line_label.font().pointSize() < overlay.compact_label.font().pointSize()


def test_custom_display_selection():
    overlay = _overlay()
    config = replace(
        default_config(),
        display_style="floating",
        lyric_lines="current_next",
        track_info_mode="always",
    )
    overlay.load_config_values(config)
    assert overlay.display_preset_input.currentData() == "custom"


def test_card_hover_checkbox_previews_without_save():
    overlay = _overlay()
    overlay._mouse_over_overlay = False
    overlay.hover_buttons_checkbox.setChecked(True)
    assert overlay._hover_buttons_enabled is True
    assert overlay.settings_button.isHidden()
    assert overlay.close_button.isHidden()

    overlay._mouse_over_overlay = True
    overlay._sync_overlay_buttons_ui()
    assert not overlay.settings_button.isHidden()
    assert not overlay.close_button.isHidden()


def test_floating_always_uses_hover_controls():
    overlay = _overlay()
    overlay.hover_buttons_checkbox.setChecked(False)
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    assert overlay._uses_hover_controls() is True

    overlay._mouse_over_overlay = False
    overlay._sync_overlay_buttons_ui()
    assert overlay.settings_button.isHidden()
    assert overlay.close_button.isHidden()

    overlay._mouse_over_overlay = True
    overlay._sync_overlay_buttons_ui()
    assert not overlay.settings_button.isHidden()
    assert not overlay.close_button.isHidden()


def test_settings_keep_controls_visible_in_floating_mode():
    overlay = _overlay()
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay._expanded = True
    overlay._mouse_over_overlay = False
    overlay._sync_overlay_buttons_ui()
    assert not overlay.settings_button.isHidden()
    assert not overlay.close_button.isHidden()


def test_card_preset_restores_saved_hover_preference():
    overlay = _overlay()
    overlay.hover_buttons_checkbox.setChecked(True)
    overlay.apply_display_preset(FLOATING_CONTEXT_PRESET)
    overlay.apply_display_preset(CARD_DEFAULT_PRESET)
    assert overlay._hover_buttons_enabled is True
    assert overlay._uses_hover_controls() is True
