from PySide6.QtCore import QRect

from lyric_overlay.placement import dock_geometry


def test_top_dock_stays_centered_on_selected_monitor():
    screen = QRect(-1920, 0, 1920, 1080)
    result = dock_geometry("top", screen, QRect(-1920, 0, 1920, 1040), 400, 48)
    assert result == QRect(-1160, 0, 400, 48)


def test_taskbar_fallback_stays_above_work_area_bottom():
    screen = QRect(0, 0, 1920, 1080)
    available = QRect(0, 0, 1920, 1040)
    result = dock_geometry("taskbar_left", screen, available, 400, 48)
    assert result == QRect(0, 992, 400, 48)


def test_autohide_fallback_leaves_activation_strip():
    screen = QRect(0, 0, 1920, 1080)
    result = dock_geometry("taskbar_left", screen, screen, 400, 48)
    assert result.bottom() <= screen.bottom() - 2
