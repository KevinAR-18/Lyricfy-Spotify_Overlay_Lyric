from dataclasses import replace

from lyric_overlay.config import (
    CARD_DEFAULT_PRESET,
    FLOATING_CONTEXT_PRESET,
    FLOATING_MINIMAL_PRESET,
    default_config,
)
from lyric_overlay.overlay import OverlayWindow, create_application
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage


def _overlay():
    create_application()
    overlay = OverlayWindow()
    overlay.load_config_values(default_config())
    return overlay


def _image_bytes():
    image = QImage(16, 16, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


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


def test_floating_hover_shows_enabled_controls():
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


def test_floating_hover_hides_both_disabled_controls():
    overlay = _overlay()
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay.set_overlay_buttons_visibility(False, False)
    overlay._mouse_over_overlay = True
    overlay._sync_overlay_buttons_ui()
    assert overlay.settings_button.isHidden()
    assert overlay.close_button.isHidden()


def test_floating_hover_can_show_only_settings():
    overlay = _overlay()
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay.set_overlay_buttons_visibility(True, False)
    overlay._mouse_over_overlay = True
    overlay._sync_overlay_buttons_ui()
    assert not overlay.settings_button.isHidden()
    assert overlay.close_button.isHidden()


def test_floating_hover_can_show_only_hide():
    overlay = _overlay()
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay.set_overlay_buttons_visibility(False, True)
    overlay._mouse_over_overlay = True
    overlay._sync_overlay_buttons_ui()
    assert overlay.settings_button.isHidden()
    assert not overlay.close_button.isHidden()


def test_card_hover_respects_disabled_controls():
    overlay = _overlay()
    overlay.hover_buttons_checkbox.setChecked(True)
    overlay.set_overlay_buttons_visibility(False, False)
    overlay._mouse_over_overlay = True
    overlay._sync_overlay_buttons_ui()
    assert overlay.settings_button.isHidden()
    assert overlay.close_button.isHidden()


def test_settings_keep_controls_visible_in_floating_mode():
    overlay = _overlay()
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay._expanded = True
    overlay.set_overlay_buttons_visibility(False, False)
    overlay._mouse_over_overlay = False
    overlay._sync_overlay_buttons_ui()
    assert not overlay.settings_button.isHidden()
    assert overlay.close_button.isHidden()


def test_card_preset_restores_saved_hover_preference():
    overlay = _overlay()
    overlay.hover_buttons_checkbox.setChecked(True)
    overlay.apply_display_preset(FLOATING_CONTEXT_PRESET)
    overlay.apply_display_preset(CARD_DEFAULT_PRESET)
    assert overlay._hover_buttons_enabled is True
    assert overlay._uses_hover_controls() is True


def test_album_cover_is_hidden_by_default():
    overlay = _overlay()
    overlay.set_album_cover(_image_bytes())
    assert overlay.album_cover_label.isHidden()


def test_album_cover_shows_only_in_card_mode():
    overlay = _overlay()
    overlay._show_album_cover = True
    overlay.set_album_cover(_image_bytes())
    assert not overlay.album_cover_label.isHidden()
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    assert not overlay.album_cover_label.isHidden()
    overlay.apply_display_preset(CARD_DEFAULT_PRESET)
    assert not overlay.album_cover_label.isHidden()


def test_floating_cover_can_be_hover_only():
    overlay = _overlay()
    overlay._show_album_cover = True
    overlay._floating_cover_mode = "hover"
    overlay.apply_display_preset(FLOATING_MINIMAL_PRESET)
    overlay._mouse_over_overlay = False
    overlay.set_album_cover(_image_bytes())
    assert overlay.album_cover_label.isHidden()

    overlay._mouse_over_overlay = True
    overlay._sync_album_cover_ui()
    assert not overlay.album_cover_label.isHidden()

    overlay._mouse_over_overlay = False
    overlay._sync_album_cover_ui()
    assert overlay.album_cover_label.isHidden()


def test_album_cover_hides_while_settings_are_open():
    overlay = _overlay()
    overlay._show_album_cover = True
    overlay.set_album_cover(_image_bytes())
    assert not overlay.album_cover_label.isHidden()
    overlay._expanded = True
    overlay._sync_album_cover_ui()
    assert overlay.album_cover_label.isHidden()


def test_corner_radius_preview_updates_state():
    overlay = _overlay()
    assert overlay._overlay_corner_radius == 30
    overlay.overlay_corner_radius_input.setValue(12)
    assert overlay._overlay_corner_radius == 12
    overlay.overlay_corner_radius_input.setValue(0)
    assert overlay._overlay_corner_radius == 0


def test_track_info_gap_preview_updates_spacing_and_layout():
    overlay = _overlay()
    overlay.track_info_gap_input.setValue(12)
    assert overlay._track_info_gap_px == 12
    assert overlay.track_title_label.contentsMargins().top() == 12
    assert overlay._last_window_size is not None


def test_cover_is_centered_when_lyrics_are_unavailable():
    overlay = _overlay()
    overlay._current_line_text = ""
    overlay._sync_album_cover_alignment()
    alignment = overlay._compact_row.itemAt(0).alignment()
    assert alignment & Qt.AlignmentFlag.AlignVCenter


def test_cover_is_centered_when_current_lyric_is_visible():
    overlay = _overlay()
    overlay._current_line_text = "Current lyric"
    overlay._sync_album_cover_alignment()
    alignment = overlay._compact_row.itemAt(0).alignment()
    assert alignment & Qt.AlignmentFlag.AlignVCenter


def test_compact_width_accounts_for_visible_cover_and_controls():
    overlay = _overlay()
    overlay._show_album_cover = True
    overlay.set_album_cover(_image_bytes())
    overlay.set_overlay_buttons_visibility(False, False)
    lyric_width, text_width = overlay._compact_layout_widths(overlay._COMPACT_WINDOW_WIDTH)
    assert text_width - lyric_width == 0

    overlay.set_overlay_buttons_visibility(True, True)
    lyric_width, text_width = overlay._compact_layout_widths(overlay._COMPACT_WINDOW_WIDTH)
    assert lyric_width < text_width


def test_wrapped_lyrics_and_cover_share_center_alignment():
    overlay = _overlay()
    overlay._show_album_cover = True
    overlay.set_album_cover(_image_bytes())
    overlay._lyrics_available = True
    overlay.set_lines("A lyric line long enough to wrap over two display lines", "Next lyric")
    overlay._apply_window_mode()
    cover_alignment = overlay._compact_row.itemAt(0).alignment()
    text_alignment = overlay._compact_row.itemAt(1).alignment()
    assert cover_alignment & Qt.AlignmentFlag.AlignVCenter
    assert text_alignment & Qt.AlignmentFlag.AlignVCenter
    assert overlay.height() >= overlay._COMPACT_MIN_HEIGHT


def test_invalid_or_missing_cover_collapses_layout():
    overlay = _overlay()
    overlay._show_album_cover = True
    overlay.set_album_cover(b"not-an-image")
    assert overlay.album_cover_label.isHidden()
    overlay.set_album_cover(None)
    assert overlay.album_cover_label.isHidden()
