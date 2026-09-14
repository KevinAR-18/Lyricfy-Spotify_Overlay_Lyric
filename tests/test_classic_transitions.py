from dataclasses import replace

import pytest
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtTest import QTest

from lyric_overlay.app_controller import AppController, PlaybackSnapshot
from lyric_overlay.config import CURRENT_NEXT_LYRIC_LINES, default_config
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.models import LyricLine, LyricsData, TrackInfo
from lyric_overlay.overlay import OverlayWindow, create_application


@pytest.fixture
def overlay():
    app = create_application()
    window = OverlayWindow()
    window.load_config_values(replace(default_config(), lyric_lines=CURRENT_NEXT_LYRIC_LINES))
    window._lyrics_available = True
    window.show()
    QTest.qWait(50)
    yield window
    window.hide()
    window.deleteLater()
    app.processEvents()


def test_classic_crossfade_keeps_layout_and_glow_and_settles(overlay):
    overlay.set_lines("First line", "Second line", transition_ms=0)
    QTest.qWait(50)
    glow = overlay.compact_label.graphicsEffect()
    overlay.set_lines("Second line", "Third line", transition_ms=240)
    labels = (overlay.compact_label, overlay.next_line_label)
    assert [label.text() for label in labels] == ["Second line", "Third line"]
    positions = [label.pos() for label in labels]
    for label in labels:
        assert label._animation.state() == QAbstractAnimation.State.Running
        label._animation.pause()
        label._animation.setCurrentTime(120)
        assert 0 < label._progress < 1
    middle = overlay.compact_label.capture_text().toImage()
    assert not middle.isNull()
    assert overlay.compact_label.graphicsEffect() is glow
    assert positions == [label.pos() for label in labels]
    for label in labels:
        label._animation.resume()
    QTest.qWait(200)
    for label in labels:
        assert label._animation.state() == QAbstractAnimation.State.Stopped
        assert label._progress == 1
        assert label._previous.isNull()
    final = overlay.compact_label.capture_text().toImage()
    assert final != middle
    assert any(final.pixelColor(x, y).alpha() > 0
               for y in range(final.height()) for x in range(final.width()))


def test_classic_rapid_changes_wrapping_pause_and_hide(overlay):
    overlay.set_lines("Before", "Next", transition_ms=0)
    QTest.qWait(30)
    overlay.set_lines("A lyric with enough words to wrap " * 5, "Following", transition_ms=240)
    assert "\n" in overlay.compact_label.text()
    QTest.qWait(40)
    # Retarget a running fade using its current rendered content instead of queuing.
    snapshot = overlay.compact_label.capture_text().toImage()
    overlay.set_lines("Latest", "End", transition_ms=100)
    assert overlay.compact_label._previous.toImage() == snapshot
    assert overlay.compact_label.text() == "Latest"
    assert overlay.compact_label._animation.duration() == 100
    overlay.set_paused()
    assert overlay.compact_label._progress == 1
    assert overlay.next_line_label._progress == 1
    overlay.set_lines("Resume", "After", transition_ms=240)
    overlay.hide()
    assert overlay.compact_label._animation.state() == QAbstractAnimation.State.Stopped
    assert overlay.next_line_label._animation.state() == QAbstractAnimation.State.Stopped
    overlay.set_lines("Hidden latest", "", transition_ms=240)
    assert overlay.compact_label._previous.isNull()
    overlay.show()
    assert overlay.compact_label.text() == "Hidden latest"


def test_classic_controller_animates_repeated_indices_but_not_seek_or_track_change():
    create_application()

    class Overlay:
        def __init__(self):
            self.updates = []

        def set_lines(self, *lines, **kwargs):
            self.updates.append((lines, kwargs["transition_ms"]))

    target = Overlay()
    controller = AppController(None, LyricsRepository(), target, default_config())
    track = TrackInfo("song", "Song", "Artist", "Album", 10000, 0, True)
    lyrics = LyricsData("local", [LyricLine(0, "Repeat"), LyricLine(1000, "Repeat"),
                                  LyricLine(1200, "Repeat"), LyricLine(4000, "End")])
    controller.snapshot = PlaybackSnapshot(track, lyrics)
    controller.sync_engine.set_lyrics(lyrics)
    controller._render_current_state()
    assert target.updates[-1][1] == 0
    track.progress_ms = 50
    controller._render_current_state()
    assert len(target.updates) == 1
    track.progress_ms = 1000
    controller._render_current_state()
    assert target.updates[-1][0] == target.updates[0][0]  # Identical current/next strings.
    assert target.updates[-1][1] == 90  # Short lyric interval reduces animation duration.
    track.progress_ms = 1200
    controller._render_current_state()
    assert target.updates[-1][1] == 240
    track.is_playing = False
    controller._render_current_state()
    assert target.updates[-1][1] == 0
    track.is_playing = True
    controller._render_current_state()
    assert target.updates[-1][1] == 0
    track.progress_ms = 100
    controller._render_current_state()
    assert target.updates[-1][1] == 0
    track.progress_ms = 4000
    controller._render_current_state()
    assert target.updates[-1][1] == 0
    track.track_id = "other"
    controller._render_current_state()
    assert target.updates[-1][1] == 0
