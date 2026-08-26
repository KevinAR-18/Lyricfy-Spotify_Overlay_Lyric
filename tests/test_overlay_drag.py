from PySide6.QtCore import QPoint

from lyric_overlay.config import default_config
from lyric_overlay.overlay import OverlayWindow, create_application, shortcuts_guide_lines


def _overlay():
    create_application()
    overlay = OverlayWindow()
    overlay.load_config_values(default_config())
    overlay.move(100, 100)
    overlay._snap_pos = overlay.pos()
    return overlay


def test_two_pixel_movement_does_not_start_drag():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    assert overlay._continue_drag(QPoint(102, 102)) is False
    assert overlay._dragging is False
    assert overlay.pos() == QPoint(100, 100)


def test_three_pixel_movement_starts_drag():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    assert overlay._continue_drag(QPoint(103, 100)) is True
    assert overlay._dragging is True
    assert overlay.pos() == QPoint(103, 100)


def test_small_drag_is_kept_without_snap_back():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    overlay._continue_drag(QPoint(105, 106))
    assert overlay._finish_drag() is True
    assert overlay.pos() == QPoint(105, 106)
    assert overlay._snap_pos == QPoint(105, 106)
    assert overlay._user_positioned is True


def test_click_without_drag_does_not_update_saved_position():
    overlay = _overlay()
    original_snap = QPoint(overlay._snap_pos)
    overlay._prepare_drag(QPoint(100, 100))
    assert overlay._finish_drag() is False
    assert overlay._snap_pos == original_snap
    assert overlay._user_positioned is False


def test_layout_refresh_is_deferred_while_dragging():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    overlay._continue_drag(QPoint(105, 100))
    overlay._apply_window_mode()
    assert overlay._layout_refresh_pending is True
    overlay._finish_drag()
    assert overlay._layout_refresh_pending is False
    assert overlay._last_window_size is not None


def test_screen_change_is_deferred_while_dragging():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    overlay._continue_drag(QPoint(105, 100))
    overlay._layout_refresh_pending = False
    overlay._on_screen_changed(overlay.screen())
    assert overlay._layout_refresh_pending is True
    overlay._finish_drag()
    assert overlay._layout_refresh_pending is False


def test_drag_state_is_cleared_after_release():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    overlay._continue_drag(QPoint(110, 110))
    overlay._finish_drag()
    assert overlay._drag_press_global is None
    assert overlay._drag_start_window_pos is None
    assert overlay._dragging is False


def test_home_position_uses_current_screen_top_center():
    overlay = _overlay()
    home = overlay._home_position()
    geometry = overlay.screen().availableGeometry()
    assert home == QPoint(
        geometry.x() + (geometry.width() - overlay.width()) // 2,
        geometry.y() + 12,
    )


def test_snap_to_home_resets_user_position():
    overlay = _overlay()
    overlay.move(250, 300)
    overlay._snap_pos = overlay.pos()
    overlay._user_positioned = True
    overlay.snap_to_home()
    assert overlay.pos() == overlay._home_position()
    assert overlay._snap_pos == overlay.pos()
    assert overlay._user_positioned is False


def test_snap_to_home_clears_active_drag_state():
    overlay = _overlay()
    overlay._prepare_drag(QPoint(100, 100))
    overlay._continue_drag(QPoint(110, 110))
    overlay._layout_refresh_pending = True
    overlay.snap_to_home()
    assert overlay._drag_press_global is None
    assert overlay._drag_start_window_pos is None
    assert overlay._dragging is False
    assert overlay._layout_refresh_pending is False


def test_shortcut_guide_lists_shift_h():
    assert ("Shift+H", "Snap overlay home") in shortcuts_guide_lines()


def test_compact_overlay_can_remain_partially_beyond_left_edge():
    overlay = _overlay()
    available = overlay.screen().availableGeometry()
    requested = QPoint(available.left() - overlay.width() + 80, overlay.y())
    assert overlay._clamped_compact_horizontal_pos(requested) == requested


def test_compact_overlay_keeps_minimum_visible_width_on_left():
    overlay = _overlay()
    available = overlay.screen().availableGeometry()
    requested = QPoint(available.left() - overlay.width() - 200, overlay.y())
    clamped = overlay._clamped_compact_horizontal_pos(requested)
    assert clamped.x() == available.left() - overlay.width() + overlay._MIN_VISIBLE_DRAG_WIDTH


def test_compact_overlay_keeps_minimum_visible_width_on_right():
    overlay = _overlay()
    available = overlay.screen().availableGeometry()
    requested = QPoint(available.right() + 200, overlay.y())
    clamped = overlay._clamped_compact_horizontal_pos(requested)
    assert clamped.x() == available.right() - overlay._MIN_VISIBLE_DRAG_WIDTH + 1


def test_settings_overlay_is_fully_clamped_horizontally():
    overlay = _overlay()
    available = overlay.screen().availableGeometry()
    requested = QPoint(available.left() - 200, overlay.y())
    assert overlay._clamped_settings_horizontal_pos(requested).x() == available.left()

    requested = QPoint(available.right() + 200, overlay.y())
    max_x = max(available.left(), available.right() - overlay.width() + 1)
    assert overlay._clamped_settings_horizontal_pos(requested).x() == max_x


def test_snap_home_recovers_partially_offscreen_overlay():
    overlay = _overlay()
    available = overlay.screen().availableGeometry()
    overlay.move(available.left() - overlay.width() + overlay._MIN_VISIBLE_DRAG_WIDTH, overlay.y())
    overlay._snap_pos = overlay.pos()
    overlay._user_positioned = True
    overlay.snap_to_home()
    assert overlay.pos() == overlay._home_position()
    assert available.contains(overlay.geometry())
