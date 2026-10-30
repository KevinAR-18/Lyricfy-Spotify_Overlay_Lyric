"""Geometry helpers for anchored overlays, in Qt logical screen coordinates."""
from PySide6.QtCore import QRect


def dock_geometry(mode: str, screen: QRect, available: QRect, width: int, height: int) -> QRect:
    width = max(1, min(width, screen.width()))
    height = max(1, min(height, screen.height()))
    if mode == "top":
        return QRect(screen.x() + (screen.width() - width) // 2, screen.y(), width, height)
    # Without a reliable inventory of taskbar controls, never overlay the shell.
    # availableGeometry already excludes a visible taskbar; when auto-hidden,
    # leave a small strip clear for the activation gesture.
    bottom = min(available.bottom(), screen.bottom() - 2)
    return QRect(available.x(), max(screen.y(), bottom - height + 1), min(width, available.width()), height)
