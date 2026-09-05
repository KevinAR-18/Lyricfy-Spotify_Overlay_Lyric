from __future__ import annotations

import sys
from pathlib import Path

from . import AutostartResult, AutostartStatus

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Lyricfy"


def startup_command(executable: str, entrypoint: str, frozen: bool, start_hidden: bool) -> str:
    command = f'"{executable}"' if frozen else f'"{executable}" "{entrypoint}"'
    return command + (" --start-hidden" if start_hidden else "")


def set_autostart(enabled: bool, start_hidden: bool) -> AutostartResult:
    import winreg

    command = startup_command(sys.executable, str(Path(sys.argv[0]).resolve()),
                              getattr(sys, "frozen", False), start_hidden)
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        return AutostartResult(False, "Windows could not update login startup. Check your account permissions.")
    return AutostartResult(True)


def get_autostart_status() -> AutostartStatus:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return AutostartStatus(True, bool(value))
    except FileNotFoundError:
        return AutostartStatus(True, False)
