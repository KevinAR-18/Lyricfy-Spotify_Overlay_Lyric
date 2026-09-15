"""Exercise Settings against a live polling worker without Spotify/network access."""
from dataclasses import replace
import os
import time

import pytest
from PySide6.QtCore import QAbstractAnimation, QEventLoop, QTimer

from lyric_overlay.app_controller import AppController
from lyric_overlay.cinematic.manager import CinematicManager
from lyric_overlay.config import default_config
from lyric_overlay.models import LyricLine, LyricsData, TrackInfo
from lyric_overlay.overlay import OverlayWindow, create_application
from lyric_overlay.spotify_client import WindowsMediaSpotifyClient


def wait(ms):
    # A real event loop also releases the GIL for the Python playback worker.
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_until(predicate, timeout_ms=2500):
    deadline = time.monotonic() + timeout_ms / 1000
    while not predicate():
        assert time.monotonic() < deadline, "Playback/UI did not advance before timeout"
        wait(10)


class PlayingClient:
    def __init__(self):
        self.started = time.monotonic()
        self.calls = 0

    def get_current_track(self):
        self.calls += 1
        progress = int((time.monotonic() - self.started) * 1000)
        return TrackInfo("test-song", "Song", "Artist", "Album", 120000, progress, True)


class LocalLyrics:
    def get_lyrics(self, **kwargs):
        return LyricsData("local", [LyricLine(i * 800, f"Lyric number {i:03d}")
                                    for i in range(1500)])


@pytest.mark.parametrize("style,lines", [
    ("card", "single"), ("floating", "single"), ("floating", "current_next"),
])
@pytest.mark.parametrize("close_delay_ms", [0, 100, 400])
def test_playback_keeps_advancing_after_settings_close(style, lines, close_delay_ms):
    exercise_settings_playback(PlayingClient(), style, lines, close_delay_ms)


@pytest.mark.skipif(os.getenv("LYRICFY_TEST_LIVE_PLAYBACK") != "1",
                    reason="Opt-in: requires Spotify playing on Windows")
@pytest.mark.parametrize("close_delay_ms", [0, 100, 400])
def test_live_windows_playback_after_settings_close(close_delay_ms):
    class CountingWindowsClient:
        def __init__(self):
            self.client = WindowsMediaSpotifyClient()
            self.calls = 0

        def get_current_track(self):
            self.calls += 1
            return self.client.get_current_track()

    exercise_settings_playback(CountingWindowsClient(), "card", "single", close_delay_ms)


def exercise_settings_playback(client, style, lines, close_delay_ms):
    app = create_application()
    config = replace(default_config(), display_style=style, lyric_lines=lines)
    overlay = OverlayWindow()
    overlay.load_config_values(config)
    controller = AppController(client, LocalLyrics(), overlay, config)
    manager = CinematicManager(overlay, controller)
    # Same visibility wiring as the application entry point.
    overlay.overlay_hidden.connect(manager.pause_if_hidden)
    overlay.overlay_shown.connect(controller.resume_polling)
    try:
        manager.show()
        controller.start()
        wait_until(lambda: overlay.compact_label.text().startswith("Lyric number"))
        worker = controller.worker
        for _ in range(3):
            wait_until(lambda: overlay._lyric_transition._animation.state()
                       == QAbstractAnimation.State.Running)
            overlay.toggle_settings()
            if close_delay_ms:
                wait(close_delay_ms)
            overlay.close_settings_panel()
            assert controller._render_timer.isActive()
            assert controller.worker is worker
            assert worker._thread.is_alive()
            calls = client.calls
            index = controller._classic_frame[1]
            wait_until(lambda: controller._classic_frame[1] > index)
            wait_until(lambda: not overlay._panel_animating
                       and overlay._lyric_transition._animation.state()
                       == QAbstractAnimation.State.Stopped)
            assert overlay.isVisible() and not overlay._expanded
            assert overlay.settings_panel.isHidden()
            assert overlay._lyric_transition.isHidden()
            assert not overlay.compact_label.transition_masked
            assert not overlay.next_line_label.transition_masked
            assert overlay.compact_label.text() == f"Lyric number {controller._classic_frame[1]:03d}"
            image = overlay.compact_label.grab().toImage()
            assert not image.isNull()
            wait_until(lambda: client.calls > calls)
    finally:
        controller.stop()
        manager.shutdown()
        overlay.allow_exit()
        overlay.close()
        overlay.deleteLater()
        app.processEvents()
