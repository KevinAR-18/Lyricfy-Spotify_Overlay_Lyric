"""Conservative native taskbar bounds. Never guess the Start button position."""
import sys

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication


def taskbar_left_area(screen) -> QRect | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user = ctypes.windll.user32
    user.FindWindowW.restype = wintypes.HWND
    user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user.MonitorFromWindow.restype = wintypes.HANDLE
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    candidates = []

    def inspect(hwnd, _):
        name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, name, 256)
        if name.value in {"Shell_TrayWnd", "Shell_SecondaryTrayWnd"} and user.IsWindowVisible(hwnd):
            candidates.append(hwnd)
        return True

    user.EnumWindows(callback_type(inspect), 0)
    logical = screen.geometry()
    ratio = screen.devicePixelRatio()
    for hwnd in candidates:
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if not user.GetMonitorInfoW(user.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
            continue
        monitor = info.monitor
        # Match physical monitor origin/size to Qt's logical monitor.
        if abs((monitor.right - monitor.left) / ratio - logical.width()) > 2:
            continue
        # QScreen names use the same DISPLAYn name as MONITORINFOEX.
        class MonitorInfoEx(ctypes.Structure):
            _fields_ = MonitorInfo._fields_ + [("device", wintypes.WCHAR * 32)]
        extended = MonitorInfoEx()
        extended.size = ctypes.sizeof(extended)
        if not user.GetMonitorInfoW(user.MonitorFromWindow(hwnd, 2), ctypes.cast(ctypes.byref(extended), ctypes.POINTER(MonitorInfo))):
            continue
        # Some Qt backends report the EDID model rather than \\.\DISPLAYn.
        origin_matches = (abs(monitor.left / ratio - logical.x()) <= 2
                          and abs(monitor.top / ratio - logical.y()) <= 2)
        if extended.device != screen.name() and not (len(QApplication.screens()) == 1 or origin_matches):
            continue
        bar = wintypes.RECT()
        if not user.GetWindowRect(hwnd, ctypes.byref(bar)):
            continue
        if bar.bottom - bar.top > bar.right - bar.left:
            continue
        starts, occupied = [], []

        def child(child_hwnd, _):
            if not user.IsWindowVisible(child_hwnd):
                return True
            name = ctypes.create_unicode_buffer(256)
            user.GetClassNameW(child_hwnd, name, 256)
            rect = wintypes.RECT()
            if user.GetWindowRect(child_hwnd, ctypes.byref(rect)):
                if name.value.lower() in {"start", "startbutton"}:
                    starts.append(rect.left)
                # Exclude broad container windows, but reserve concrete controls.
                if name.value in {"TrayButton", "TrayDummySearchControl", "DynamicContent1", "DynamicContent2"}:
                    occupied.append((rect.left, rect.right))
            return True

        user.EnumChildWindows(hwnd, callback_type(child), 0)
        if not starts:
            from .taskbar_accessibility import cached_controls
            controls = cached_controls(int(hwnd)) or []
            for control in controls:
                if control.get("start"):
                    starts.append(control["left"])
                elif control.get("right", 0) > control.get("left", 0):
                    occupied.append((control["left"], control["right"]))
            if not starts:
                continue
        left, right = bar.left, min(starts) - round(8 * ratio)
        for begin, end in occupied:
            if begin < right and end > left:
                left = max(left, end + round(8 * ratio))
        if right - left < 96 * ratio:
            continue
        area = QRect(logical.x() + round((left - monitor.left) / ratio),
                     logical.y() + round((bar.top - monitor.top) / ratio),
                     round((right - left) / ratio), round((bar.bottom - bar.top) / ratio))
        if logical.contains(area) and area.height() >= 24:
            return area
    return None
