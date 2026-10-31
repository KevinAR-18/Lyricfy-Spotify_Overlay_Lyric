r"""Measure a fresh Classic process on Windows, without network or user config.

Run with .venv\Scripts\python.exe tools\measure_memory.py --samples 3.
Each sample is a fresh subprocess; settings and cinematic scenarios include the
cost of first opening those features. This is a source-runtime benchmark, not
a substitute for measuring the packaged executable under real playback.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import statistics
import subprocess
import sys


def measure(args):
    if sys.platform != "win32":
        raise SystemExit("Windows process memory counters are required.")
    sys.path.insert(0, str(args.source_dir))
    from PySide6.QtCore import QEventLoop, QTimer
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.cinematic.manager import CinematicManager
    from lyric_overlay.config import default_config
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.overlay import OverlayWindow, create_application

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage",
            )
        ]

    app = create_application()
    config = default_config()
    window = OverlayWindow()
    window.load_config_values(config)
    controller = AppController(None, LyricsRepository(), window, config)
    manager = CinematicManager(window, controller)
    cinematic = None
    window.show()
    if args.scenario == "settings":
        window.toggle_settings()
    elif args.scenario == "cinematic":
        # Do not persist presentation or touch autostart/user settings.
        cinematic = manager.ensure_window()
        cinematic.show_from_tray()
        window.hide()
    loop = QEventLoop()
    QTimer.singleShot(args.settle_ms, loop.quit)
    loop.exec()
    if args.scenario == "settings":
        window.close_settings_panel()
        QTimer.singleShot(500, loop.quit)
        loop.exec()
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb,
    ):
        raise ctypes.WinError()
    result = {
        "scenario": args.scenario,
        "working_set_mib": round(counters.WorkingSetSize / 1048576, 2),
        "private_commit_mib": round(counters.PrivateUsage / 1048576, 2),
        "widgets": len(app.allWidgets()),
        "qtquick_loaded": "PySide6.QtQuick" in sys.modules,
    }
    controller.stop()
    window.allow_exit()
    window.close()
    if cinematic is not None:
        cinematic.hide()
        cinematic.releaseResources()
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parents[1] / "src")
    parser.add_argument("--scenario", choices=("classic", "settings", "cinematic"), default="classic")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--settle-ms", type=int, default=2000)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        measure(args)
        return
    if args.samples < 1 or args.settle_ms < 0:
        parser.error("samples must be positive and settle-ms must be non-negative")
    samples = []
    for _ in range(args.samples):
        output = subprocess.check_output([
            sys.executable, str(Path(__file__).resolve()), "--child",
            "--source-dir", str(args.source_dir.resolve()), "--scenario", args.scenario,
            "--settle-ms", str(args.settle_ms),
        ], text=True, timeout=max(30, args.settle_ms / 1000 + 15))
        sample = json.loads(output.strip().splitlines()[-1])
        samples.append(sample)
        print(json.dumps(sample))
    print(json.dumps({"median": {
        key: statistics.median(sample[key] for sample in samples)
        for key in ("working_set_mib", "private_commit_mib", "widgets")
    }}))


if __name__ == "__main__":
    main()
