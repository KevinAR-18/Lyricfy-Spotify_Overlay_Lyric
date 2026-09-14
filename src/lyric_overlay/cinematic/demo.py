"""Offline visual preview, also usable to smoke-test a packaged QML runtime."""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer

from ..overlay import create_application
from .preferences import DEFAULTS
from .settings import CinematicSettings
from .window import CinematicWindow


def run_demo() -> int:
    app = create_application()
    window = CinematicWindow(dict(DEFAULTS, background="gradient"))
    lyrics = ["Cahaya jatuh perlahan", "Aku ingin berjalan bersamamu sampai akhir waktu",
              "Melewati malam", "Melewati malam", "Dan menemukan pagi yang baru"]
    elapsed = 0
    dialog = None

    def tick():
        nonlocal elapsed
        index = (elapsed // 3000) % len(lyrics)
        window.bridge.set_frame({
            "track": "demo", "title": "Cinematic Lyrics", "artist": "Lyricfy • Offline preview",
            "playing": True, "index": index, "progress": elapsed % (len(lyrics) * 3000),
            "remaining": 3000 - elapsed % 3000, "message": "",
            "rows": [{"index": i, "text": text} for i, text in enumerate(lyrics)
                     if index - 2 <= i <= index + 2],
        })
        elapsed += 50

    def settings():
        nonlocal dialog
        if dialog is not None:
            dialog.raise_()
            return
        original = dict(window.bridge.options)
        dialog = CinematicSettings(original)
        dialog.preview.connect(window.bridge.set_options)

        def finished(result):
            nonlocal dialog
            if result == 0:
                window.bridge.set_options(original)
            dialog.deleteLater()
            dialog = None

        dialog.finished.connect(finished)
        dialog.show()

    window.bridge.settingsRequested.connect(settings)
    window.bridge.classicRequested.connect(app.quit)
    window.hidden.connect(app.quit)
    timer = QTimer(window)
    timer.setInterval(50)
    timer.timeout.connect(tick)
    tick()
    timer.start()
    window.show()
    if "--demo-seconds" in sys.argv:
        index = sys.argv.index("--demo-seconds")
        seconds = max(1, int(sys.argv[index + 1]))
        QTimer.singleShot(seconds * 1000, app.quit)
    result = app.exec()
    window.hide()
    return result
