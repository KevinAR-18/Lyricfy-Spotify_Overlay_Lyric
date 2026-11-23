from dataclasses import replace

import pytest

from lyric_overlay.app_controller import AppController, PlaybackSnapshot
from lyric_overlay.config import (
    CARD_DEFAULT_PRESET,
    FLOATING_CONTEXT_PRESET,
    FLOATING_MINIMAL_PRESET,
    default_config,
)
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.models import LyricLine, LyricsData, TrackInfo
from lyric_overlay.overlay import OverlayWindow, create_application
from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, QObject, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QWidget


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


def _track(*, is_playing):
    return TrackInfo("track", "Blue Hour", "The Midnight Atlas", "Album", 180_000, 30_000, is_playing)


@pytest.mark.parametrize("manual", [False, True], ids=["auto", "manual"])
def test_taskbar_pause_adds_row_above_wrapped_lyric_without_moving_it(monkeypatch, manual):
    overlay = _overlay()
    screen = overlay.screen().geometry()
    area = QRect(screen.x() + 8, screen.bottom() - 47, 260, 48)
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: area)
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", show_album_cover=True,
                                       taskbar_manual=manual, taskbar_width=255))
    overlay.set_album_cover(_image_bytes())
    track = _track(is_playing=True)
    line = "Acres of open stars, headlights of precious cars, life imitating art"
    overlay.set_track(track, lyrics_source="local")
    overlay.set_lines(line, "", transition_ms=0)
    overlay.show()
    create_application().processEvents()
    # Disable geometry animation in this layout test to check the settled rectangles.
    overlay._dock_animation.setDuration(0)
    playing = overlay.geometry()
    playing_lyric = overlay.compact_label.mapToGlobal(overlay.compact_label.rect().topLeft())
    playing_width = overlay.compact_label.width()
    assert overlay.compact_label.wordWrap()
    assert overlay.compact_label.height() > overlay.compact_label.fontMetrics().lineSpacing()
    assert overlay._pause_badge.isHidden()

    overlay.set_track(replace(track, is_playing=False), lyrics_source="local")
    overlay.set_paused()
    create_application().processEvents()
    badge = overlay._pause_badge
    assert badge.isVisible() and badge.text() == "⏸ Paused"
    assert overlay.geometry().bottomLeft() == playing.bottomLeft()
    assert overlay.width() == playing.width()
    assert overlay.height() > playing.height()
    assert overlay.compact_label.width() == playing_width
    assert overlay.compact_label.mapToGlobal(overlay.compact_label.rect().topLeft()) == playing_lyric
    assert badge.mapToGlobal(badge.rect().topLeft()).x() == playing_lyric.x()
    assert badge.mapToGlobal(badge.rect().bottomLeft()).y() < playing_lyric.y()
    assert overlay.album_cover_label.mapToGlobal(overlay.album_cover_label.rect().bottomLeft()) == playing.bottomLeft()
    assert overlay.compact_label.text() == line

    overlay.set_track(track, lyrics_source="local")
    overlay.show_status("")
    create_application().processEvents()
    assert badge.isHidden() and overlay.geometry() == playing
    overlay.allow_exit()
    overlay.close()


def test_taskbar_pause_is_independent_of_lyrics_and_ends_with_track(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: None)
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left"))
    paused = _track(is_playing=False)
    overlay.set_track(paused, lyrics_source="loading")
    overlay.show_status("Fetching lyrics...")
    assert not overlay._pause_badge.isHidden()
    assert overlay.album_cover_label.isHidden()
    assert overlay.compact_label.text() == "Blue Hour — The Midnight Atlas"

    overlay.set_track(paused, lyrics_source="local")
    overlay.show_status("")
    overlay.set_lines("Lirik yang baru dimuat", "", transition_ms=0)
    assert not overlay._pause_badge.isHidden()
    assert overlay.compact_label.text() == "Lirik yang baru dimuat"
    assert overlay.status_label.isHidden()

    overlay.set_track(None)
    overlay.show_status("Playback paused")  # A generic status isn't playback state.
    assert overlay._pause_badge.isHidden()
    overlay.close()


@pytest.mark.parametrize("manual", [False, True], ids=["auto", "manual"])
def test_taskbar_repeated_pause_polls_do_not_toggle_status_or_move_widgets(monkeypatch, manual):
    app = create_application()
    overlay = _overlay()
    screen = overlay.screen().geometry()
    area = QRect(screen.x() + 8, screen.bottom() - 47, 260, 48)
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: area)
    config = replace(default_config(), placement="taskbar_left", taskbar_manual=manual,
                     taskbar_width=255, show_album_cover=True)
    overlay.load_config_values(config)
    overlay.set_album_cover(_image_bytes())
    overlay._dock_animation.setDuration(0)
    controller = AppController(None, LyricsRepository(lrclib_enabled=False), overlay, config)
    track = _track(is_playing=False)
    line = "Acres of open stars, headlights of precious cars, life imitating art"
    lyrics = LyricsData("local", [LyricLine(0, line)])
    controller.snapshot = PlaybackSnapshot(track, lyrics)
    controller.sync_engine.set_lyrics(lyrics)
    controller.refresh(track)
    overlay.show()
    app.processEvents()

    events = []

    class LayoutWatcher(QObject):
        def eventFilter(self, watched, event):
            if event.type() in (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Move, QEvent.Type.Resize):
                events.append(event.type().name)
            return False

    watcher = LayoutWatcher()
    for widget in (overlay.status_label, overlay._pause_badge, overlay.compact_label, overlay.album_cover_label):
        widget.installEventFilter(watcher)
    try:
        for _ in range(3):
            controller.refresh(replace(track))
            app.processEvents()
        overlay.show_status("Fetching lyrics...")
        app.processEvents()
        assert not events
        assert overlay.status_label.isHidden()
        assert overlay._pause_badge.isVisible()
        assert overlay.compact_label.text() == line
    finally:
        controller.shutdown()
        overlay.allow_exit()
        overlay.close()


def test_taskbar_pause_uses_icon_in_minimum_width_with_cover():
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", taskbar_manual=True,
                                       taskbar_width=96, show_album_cover=True))
    overlay.set_album_cover(_image_bytes())
    overlay.set_track(_track(is_playing=True), lyrics_source="local")
    overlay.set_lines("Lyric", "", transition_ms=0)
    overlay.show()
    create_application().processEvents()
    overlay._dock_animation.setDuration(0)
    anchor = overlay.geometry().bottomLeft()
    lyric_width = overlay.compact_label.width()
    overlay.set_track(_track(is_playing=False), lyrics_source="local")
    create_application().processEvents()
    badge = overlay._pause_badge
    assert badge.isVisible() and badge.text() == "⏸"
    assert overlay.width() == 96 and overlay.geometry().bottomLeft() == anchor
    assert badge.width() <= lyric_width == overlay.compact_label.width()
    assert badge.contentsRect().width() >= badge.fontMetrics().horizontalAdvance(badge.text())
    overlay.allow_exit()
    overlay.close()


def test_taskbar_pause_badge_is_hidden_in_settings_and_other_placements():
    overlay = _overlay()
    taskbar = replace(default_config(), placement="taskbar_left", taskbar_manual=True)
    overlay.load_config_values(taskbar)
    overlay.set_track(_track(is_playing=False), lyrics_source="local")
    overlay.set_paused()
    assert not overlay._pause_badge.isHidden()
    assert overlay.status_label.isHidden()

    overlay.toggle_settings()
    assert overlay._pause_badge.isHidden()
    assert not overlay.status_label.isHidden()
    assert overlay.status_label.text() == "Playback paused"
    overlay._resize_animation.stop()
    overlay._finish_panel_animation()
    overlay.close_settings_panel()
    overlay._resize_animation.stop()
    overlay._finish_panel_animation()
    assert not overlay._pause_badge.isHidden()

    for placement in ("top", "free"):
        overlay.load_config_values(replace(taskbar, placement=placement))
        overlay.set_paused()
        assert overlay._pause_badge.isHidden()
    overlay.close()


def test_taskbar_dock_uses_native_area_and_updates_long_lyrics(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: QRect(8, 1000, 260, 48))
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left"))
    overlay._lyrics_available = True
    overlay.set_lines("Very long lyric " * 12, "", transition_ms=0)
    assert overlay.width() <= 260
    assert overlay.geometry().bottom() == 1042
    assert overlay.y() < 1000
    assert "\n" not in overlay.compact_label.text()
    assert overlay.compact_label.wordWrap()
    assert overlay.compact_label.text() == ("Very long lyric " * 12).strip()
    overlay.set_lines("New line", "", transition_ms=0)
    assert overlay.compact_label.text() == "New line"
    assert overlay.height() == 48
    assert overlay.geometry().bottom() == 1042
    assert overlay.x() == 13
    assert overlay.width() == 255
    overlay.close()


def test_manual_taskbar_bounds_keep_anchor_when_lyrics_wrap(monkeypatch):
    def unexpected_detection(screen):
        raise AssertionError("Manual bounds must not query Start")
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", unexpected_detection)
    overlay = _overlay()
    config = replace(default_config(), placement="taskbar_left", taskbar_manual=True,
                     taskbar_width=220, taskbar_left=24, taskbar_bottom=4)
    overlay.load_config_values(config)
    form = overlay.current_form_config()
    assert (form.taskbar_manual, form.taskbar_width, form.taskbar_left, form.taskbar_bottom) == (True, 220, 24, 4)
    overlay._lyrics_available = True
    overlay.set_lines("Short", "", transition_ms=0)
    initial = overlay.geometry()
    overlay.set_lines("A longer lyric which should wrap into multiple lines within the same width", "", transition_ms=0)
    assert overlay.geometry().bottomLeft() == initial.bottomLeft()
    assert overlay.width() == initial.width()
    assert overlay.height() > initial.height()
    overlay.close()


def test_taskbar_detection_failure_uses_visible_manual_bounds(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: None)
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left"))
    assert overlay.windowOpacity() == 1.0
    assert overlay.geometry().bottom() == overlay.screen().geometry().bottom() - 5
    overlay.load_config_values(default_config())
    assert overlay.windowOpacity() == 1.0
    overlay.close()


def test_taskbar_auto_uses_all_space_even_with_small_manual_width(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: QRect(8, 1000, 820, 48))
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", taskbar_width=280))
    assert overlay.width() == 815
    overlay.close()


def test_taskbar_auto_keeps_last_valid_area_during_detection_failures(monkeypatch):
    detected = [QRect(8, 1000, 820, 48)]
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: detected[0])
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", taskbar_width=280))
    original = overlay.geometry()
    detected[0] = None
    for _ in range(3):
        overlay._taskbar_detection_time = 0
        overlay._apply_dock_geometry()
        assert overlay.geometry() == original
    overlay.close()


def test_taskbar_auto_fallback_ignores_old_narrow_manual_width(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: None)
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", taskbar_width=280))
    assert overlay.width() == min(620, overlay.screen().geometry().width() - 5)
    overlay.close()


def test_settings_from_taskbar_resets_preview_layout_before_animation(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: QRect(8, 1000, 300, 48))
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left"))
    overlay._lyrics_available = True
    overlay.set_lines("Long lyric " * 20, "", transition_ms=0)
    overlay.toggle_settings()
    margins = overlay.findChild(QWidget, "card").layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (16, 12, 16, 12)
    assert overlay.compact_label.maximumHeight() == max(40, overlay.compact_label.fontMetrics().lineSpacing() * 2 + 6)
    assert overlay.compact_label.wordWrap()
    overlay._resize_animation.stop()
    overlay.close()


def test_taskbar_cold_show_places_cover_without_click(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: QRect(8, 1000, 820, 48))
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", show_album_cover=True))
    overlay.set_album_cover(_image_bytes())
    overlay.show()
    QApplication.processEvents()
    QTest.qWait(40)
    assert overlay.x() == 13
    assert overlay.geometry().bottom() == 1042
    assert overlay.album_cover_label.mapToGlobal(overlay.album_cover_label.rect().bottomLeft()) == overlay.geometry().bottomLeft()
    assert not overlay._dock_initializing
    overlay._allow_exit = True
    overlay.close()


def test_taskbar_cover_stays_visible_and_bottom_aligned_with_active_lyrics(monkeypatch):
    monkeypatch.setattr("lyric_overlay.platform.taskbar_windows.taskbar_left_area", lambda screen: QRect(8, 1000, 260, 48))
    overlay = _overlay()
    overlay.load_config_values(replace(default_config(), placement="taskbar_left", show_album_cover=True,
                                      display_style="floating", floating_cover_mode="hover"))
    overlay._lyrics_available = True
    overlay.set_album_cover(_image_bytes())
    overlay.set_lines("A long lyric with artwork " * 8, "", transition_ms=0)
    assert not overlay.album_cover_label.isHidden()
    assert overlay.album_cover_label.width() == 48
    assert overlay._compact_row.itemAt(0).alignment() & Qt.AlignmentFlag.AlignBottom
    margins = overlay.findChild(QWidget, "card").layout().contentsMargins()
    assert margins.left() == 0
    assert margins.bottom() == 0
    assert overlay.height() > 48
    assert overlay.geometry().bottom() == 1042
    overlay.set_album_cover(None)
    assert overlay.album_cover_label.isHidden()
    overlay.close()


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
    overlay.ensure_settings()
    assert overlay.display_preset_input.currentData() == "custom"


def test_card_hover_checkbox_previews_without_save():
    overlay = _overlay()
    overlay.ensure_settings()
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
    overlay.ensure_settings()
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
    overlay.ensure_settings()
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
    overlay.ensure_settings()
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
    overlay.ensure_settings()
    assert overlay._overlay_corner_radius == 30
    overlay.overlay_corner_radius_input.setValue(12)
    assert overlay._overlay_corner_radius == 12
    overlay.overlay_corner_radius_input.setValue(0)
    assert overlay._overlay_corner_radius == 0


def test_track_info_gap_preview_updates_spacing_and_layout():
    overlay = _overlay()
    overlay.ensure_settings()
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
