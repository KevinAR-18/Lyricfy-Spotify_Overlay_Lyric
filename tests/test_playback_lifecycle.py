import threading
import time
from dataclasses import replace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QTimer

from lyric_overlay.app_controller import AppController, PlaybackWorker
from lyric_overlay.config import default_config
from lyric_overlay.models import TrackInfo
from lyric_overlay.overlay import create_application, OverlayWindow
from lyric_overlay.platform.playback_macos import AutomationPermissionError


def pump_until(condition, timeout=2):
    app = create_application()
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert condition()


class BlockingClient:
    def __init__(self, cancellable=True):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.cancellable = cancellable
        self.calls = 0

    def get_current_track(self):
        self.calls += 1
        self.entered.set()
        assert self.release.wait(5)
        return None

    def cancel(self):
        if self.cancellable:
            self.release.set()


def controller(client):
    create_application()
    overlay = Mock()
    value = AppController(client, Mock(), overlay, default_config())
    value.lyrics_worker.fetch = Mock()
    return value


def test_worker_cancellation_stops_without_late_emit():
    create_application()
    client = BlockingClient()
    worker = PlaybackWorker(client, 1000)
    emitted = []
    worker.refreshed.connect(emitted.append)
    worker.start()
    try:
        assert client.entered.wait(1)
        worker.stop()
        pump_until(lambda: not worker.is_running)
        create_application().processEvents()
        assert not emitted
    finally:
        client.release.set()
        worker.stop()


def test_reconnect_waits_for_previous_worker_and_ignores_old_signals():
    old, new = BlockingClient(cancellable=False), BlockingClient()
    value = controller(old)
    value.start()
    try:
        assert old.entered.wait(1)
        old_worker = value.worker
        value.reconnect(new, default_config())
        assert value.worker is old_worker and new.calls == 0
        old.release.set()
        pump_until(lambda: new.calls == 1)
        value.overlay.set_track.reset_mock()
        # A queued result from the previous sender must be ignored.
        # Its signal may already be disconnected by Qt after deleteLater.
        if value.worker is not old_worker:
            value._receive_track(TrackInfo("old", "Old", "Artist", "", 1000, 0, True))
        value.overlay.set_track.assert_not_called()
    finally:
        old.release.set()
        new.release.set()
        value.stop()
        pump_until(lambda: not value.worker.is_running)


def test_permission_denial_waits_for_reconnect_instead_of_prompt_loop():
    create_application()
    entered = threading.Event()
    client = Mock()
    def fail():
        entered.set()
        raise AutomationPermissionError("Allow Spotify Automation")
    client.get_current_track.side_effect = fail
    worker = PlaybackWorker(client, 10)
    worker.start()
    try:
        assert entered.wait(1)
        time.sleep(0.05)
        assert client.get_current_track.call_count == 1
    finally:
        worker.stop()
        pump_until(lambda: not worker.is_running)


def test_pause_clears_stale_track_and_unknown_duration_interpolates(monkeypatch):
    value = controller(None)
    track = TrackInfo("id", "Song", "Artist", "", 0, 4000, True)
    value._last_track_refresh_at = 10.0
    monkeypatch.setattr("lyric_overlay.app_controller.time.monotonic", lambda: 11.0)
    assert value._estimated_progress_ms(track) == 5000
    assert value._estimated_progress_ms(replace(track, is_playing=False)) == 4000
    value.snapshot.track = track
    value.pause_polling()
    assert value.snapshot.track is None and not value._polling_enabled


def test_hidden_application_does_not_build_client_until_show(monkeypatch):
    from lyric_overlay import main as entry
    from lyric_overlay.platform import AutostartResult, AutostartStatus
    from types import SimpleNamespace
    app = create_application()
    overlays, clients = [], []
    class Window(OverlayWindow):
        def __init__(self):
            super().__init__()
            overlays.append(self)
    class Tray:
        def __init__(self, *args):
            self.activated = Mock()
        def __getattr__(self, name):
            return Mock()
        @staticmethod
        def isSystemTrayAvailable():
            return True
    monkeypatch.setattr(entry, "sys", SimpleNamespace(platform="win32", argv=["Lyricfy", "--start-hidden"]))
    monkeypatch.setattr(entry, "QSystemTrayIcon", Tray)
    monkeypatch.setattr(entry, "OverlayWindow", Window)
    monkeypatch.setattr(entry, "ensure_directories", Mock())
    monkeypatch.setattr(entry, "ensure_env_file", Mock())
    monkeypatch.setattr(entry, "load_config", default_config)
    monkeypatch.setattr(entry, "set_autostart", lambda *args: AutostartResult(True))
    monkeypatch.setattr(entry, "get_autostart_status", lambda: AutostartStatus(True, False))
    monkeypatch.setattr(entry, "build_playback_client", lambda cfg: (clients.append(cfg), None))
    observed = []
    def check_hidden():
        observed.append(len(clients))
        overlays[0].show_from_tray()
        observed.append(len(clients))
        app.quit()
    QTimer.singleShot(50, check_hidden)
    QTimer.singleShot(2000, app.quit)
    entry.main()
    for overlay in overlays:
        overlay.allow_exit()
        overlay.close()
    assert observed == [0, 1]


def test_no_tray_keeps_visible_startup_and_has_quit_path(monkeypatch):
    create_application()
    overlay = OverlayWindow()
    overlay.set_tray_available(False)
    overlay.show()
    assert overlay.isVisible()
    overlay.hide_to_tray()
    assert overlay._allow_exit and not overlay.isVisible()
