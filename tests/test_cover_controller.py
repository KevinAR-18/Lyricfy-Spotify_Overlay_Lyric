from lyric_overlay.app_controller import AppController
from lyric_overlay.config import default_config
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.models import TrackInfo


class OverlayStub:
    def __init__(self):
        self.cover_calls = []

    def set_album_cover(self, data):
        self.cover_calls.append(data)


def _track(track_id="track"):
    return TrackInfo(track_id, "Title", "Artist", "Album", 1000, 0, True)


def _controller():
    controller = AppController.__new__(AppController)
    controller.config = default_config()
    controller.overlay = OverlayStub()
    controller.snapshot = type("Snapshot", (), {"track": _track()})()
    controller._cover_request_id = 1
    return controller


def test_stale_cover_result_is_ignored():
    controller = _controller()
    controller._apply_fetched_cover("track", b"old", 0)
    assert controller.overlay.cover_calls == []


def test_current_cover_result_is_applied_when_enabled():
    controller = _controller()
    controller.config.show_album_cover = True
    controller._apply_fetched_cover("track", b"new", 1)
    assert controller.overlay.cover_calls == [b"new"]


def test_cover_result_is_ignored_when_disabled():
    controller = _controller()
    controller._apply_fetched_cover("track", b"new", 1)
    assert controller.overlay.cover_calls == []
