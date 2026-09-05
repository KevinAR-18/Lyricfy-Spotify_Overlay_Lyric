from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

from . import AutostartResult, AutostartStatus

LABEL = "com.lyricfy.overlay"
INSTALL_MESSAGE = "Install Lyricfy.app in Applications to enable login startup."
REGISTERED_MESSAGE = "Registered for next login; check System Settings > General > Login Items if blocked."


def installed_bundle(executable: Path, frozen: bool, home: Path,
                     applications: Path = Path("/Applications")) -> Path | None:
    if not frozen:
        return None
    executable = executable.resolve()
    for parent in executable.parents:
        if parent.suffix == ".app":
            roots = (applications.resolve(), (home / "Applications").resolve())
            return parent if any(root in parent.parents for root in roots) and parent.is_dir() else None
    return None


def launch_agent_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def agent_payload(bundle: Path, start_hidden: bool) -> dict:
    args = ["/usr/bin/open", "-g", "-a", str(bundle)]
    if start_hidden:
        args += ["--args", "--start-hidden"]
    return {"Label": LABEL, "ProgramArguments": args, "RunAtLoad": True}


def _current_bundle(home: Path) -> Path | None:
    return installed_bundle(Path(sys.executable), getattr(sys, "frozen", False), home)


def get_autostart_status() -> AutostartStatus:
    home = Path.home()
    bundle = _current_bundle(home)
    path = launch_agent_path(home)
    if not path.exists():
        return AutostartStatus(bundle is not None, False, "" if bundle else INSTALL_MESSAGE)
    try:
        data = plistlib.loads(path.read_bytes())
        args = data.get("ProgramArguments", [])
        valid = data.get("Label") == LABEL and len(args) >= 4 and args[:3] == ["/usr/bin/open", "-g", "-a"]
        if not valid or bundle is None or args[3] != str(bundle):
            return AutostartStatus(True, True, "Login startup needs repair. Install Lyricfy, then turn Auto Start off and on.")
    except (ValueError, TypeError, AttributeError, plistlib.InvalidFileException):
        return AutostartStatus(True, True, "Login startup needs repair. Turn Auto Start off and on.")
    # Registered is deliberately not called authorized: macOS can disable this
    # legacy job independently in System Settings.
    return AutostartStatus(True, True, REGISTERED_MESSAGE)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{LABEL}-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def set_autostart(enabled: bool, start_hidden: bool) -> AutostartResult:
    home = Path.home()
    path = launch_agent_path(home)
    if enabled:
        bundle = _current_bundle(home)
        if bundle is None:
            return AutostartResult(False, INSTALL_MESSAGE)
        data = plistlib.dumps(agent_payload(bundle, start_hidden), sort_keys=True)
        if not path.exists() or path.read_bytes() != data:
            _atomic_write(path, data)
        return AutostartResult(True, REGISTERED_MESSAGE)
    try:
        result = subprocess.run(
            ["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return AutostartResult(False, "Could not disable login startup. Retry in Settings.")
    # launchctl reports ESRCH (3), or its service-not-found code (113), when
    # nothing was loaded. Other failures (including permissions) are errors.
    if result.returncode not in (0, 3, 113):
        return AutostartResult(False, "macOS could not disable login startup. Check Login Items and retry.")
    path.unlink(missing_ok=True)
    return AutostartResult(True, "Login startup disabled.")
