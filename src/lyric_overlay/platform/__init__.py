"""Native integration facade. Import OS dependencies only when selected."""
from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class AutostartResult:
    success: bool
    message: str = ""


@dataclass(frozen=True)
class AutostartStatus:
    supported: bool
    registered: bool
    message: str = ""


def _autostart_backend():
    if sys.platform == "win32":
        from . import autostart_windows
        return autostart_windows
    if sys.platform == "darwin":
        from . import autostart_macos
        return autostart_macos
    return None


def set_autostart(enabled: bool, start_hidden: bool) -> AutostartResult:
    backend = _autostart_backend()
    if backend is None:
        return AutostartResult(False, "Login startup is supported on Windows and macOS.")
    try:
        return backend.set_autostart(enabled, start_hidden)
    except (OSError, ValueError) as exc:
        return AutostartResult(False, f"Could not update login startup ({type(exc).__name__}).")


def get_autostart_status() -> AutostartStatus:
    backend = _autostart_backend()
    if backend is None:
        return AutostartStatus(False, False, "Login startup is unavailable on this platform.")
    try:
        return backend.get_autostart_status()
    except (OSError, ValueError):
        return AutostartStatus(True, False, "Could not read login startup. Retry in Settings.")
