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


def test_shortcut_guide_lists_ctrl_h():
    assert ("Ctrl+H", "Snap overlay home") in shortcuts_guide_lines()
