import asyncio
from dataclasses import replace
from datetime import timedelta, datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from lyric_overlay.app_controller import AppController, LatestRequestWorker
from lyric_overlay.config import default_config
from lyric_overlay.cover_art import CoverArtRepository
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.memory_cache import ByteCache
from lyric_overlay.models import LyricsData, LyricLine, TrackInfo
from lyric_overlay.overlay import OverlayWindow, create_application
from lyric_overlay.spotify_client import WindowsMediaSpotifyClient


def test_byte_cache_budgets_and_lru():
    cache = ByteCache(max_entries=2, max_bytes=6)
    cache["a"] = b"abc"
    cache["b"] = b"de"
    assert cache.get("a") == b"abc"
    cache["c"] = b"fgh"
    assert list(cache) == ["a", "c"]
    assert cache.total_bytes == 6
    cache["a"] = b"x"
    assert cache.total_bytes == 4
    cache["oversized"] = b"1234567"
    assert "oversized" not in cache
    cache.clear()
    assert cache.total_bytes == 0


def test_cache_stays_bounded_across_many_track_changes():
    cache = ByteCache(max_entries=8, max_bytes=1024)
    for index in range(2000):
        cache[str(index)] = b"x" * (index % 300)
        assert len(cache) <= 8
        assert cache.total_bytes <= 1024
        assert cache.total_bytes == sum(len(value) for value in cache.values())


def test_lyrics_cache_evicts_least_recently_used(monkeypatch):
    repository = LyricsRepository(lrclib_enabled=False, max_entries=2)
    monkeypatch.setattr(repository, "_load_local_lrc", lambda **kw: LyricsData("local", [LyricLine(0, kw["title"])]))
    for title in ("one", "two", "one", "three"):
        repository.get_lyrics("artist", title, 1000)
    assert [key[1] for key in repository._cache] == ["one", "three"]


def test_startup_does_not_load_settings_or_qtquick():
    code = """
import json, sys
from lyric_overlay.overlay import OverlayWindow, create_application
from lyric_overlay.app_controller import AppController
from lyric_overlay.cinematic.manager import CinematicManager
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.config import default_config
app = create_application()
w = OverlayWindow(); w.load_config_values(default_config())
c = AppController(None, LyricsRepository(), w, default_config())
m = CinematicManager(w, c)
print(json.dumps([w._settings_built, 'PySide6.QtQuick' in sys.modules,
                  'lyric_overlay.settings_panel' in sys.modules, len(app.allWidgets())]))
c.stop(); w.allow_exit(); w.close()
"""
    import os
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    result = subprocess.check_output([sys.executable, "-c", code], env=env, text=True, timeout=30)
    built, quick, settings, widgets = json.loads(result.strip().splitlines()[-1])
    assert (built, quick, settings) == (False, False, False)
    assert widgets < 30


def test_lazy_settings_preserves_shortcuts_config_and_reuses_form():
    app = create_application()
    window = OverlayWindow()
    config = replace(default_config(), lyric_offset_ms=350, lyric_font_size=18)
    try:
        window.load_config_values(config)
        window.sync_external_preferences(autostart_enabled=True)
        window.toggle_lyric_color_shortcut()
        assert not window._settings_built
        assert window._lyric_text_color == config.lyric_toggle_color
        window.ensure_settings()
        assert window.lyric_offset_input.text() == "350"
        assert window.autostart_checkbox.isChecked()
        assert window.font_size_input.value() == 18
        count = len(app.allWidgets())
        panel = window.settings_tabs
        window.ensure_settings()
        assert window.settings_tabs is panel
        assert len(app.allWidgets()) == count
    finally:
        window.allow_exit()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_classic_cover_keeps_only_display_sized_pixmap():
    app = create_application()
    window = OverlayWindow()
    image = QImage(2048, 2048, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "JPEG")
    buffer.close()
    try:
        window.set_album_cover(bytes(data))
        pixmap = window._album_cover_source
        assert pixmap is not None
        assert pixmap.width() <= round(window._ALBUM_COVER_SIZE * window.devicePixelRatioF())
        window.set_album_cover(None)
        assert window._album_cover_source is None
    finally:
        window.allow_exit()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_cover_response_closed_on_oversized_and_invalid_length(monkeypatch):
    repository = CoverArtRepository()
    for length in ("999999999", "invalid"):
        closed = []
        response = SimpleNamespace(headers={"Content-Length": length},
                                   raise_for_status=lambda: None, close=lambda: closed.append(True))
        monkeypatch.setattr(repository._session, "get", lambda *a, **k: response)
        assert repository._download_cover("https://example.test/cover") is None
        assert closed == [True]


def test_failed_download_not_cached_forever(monkeypatch):
    repository = CoverArtRepository()
    results = iter((None, b"image"))
    monkeypatch.setattr(repository, "_download_cover", lambda url: next(results))
    track = TrackInfo("id", "Title", "Artist", "Album", 1000, 0, True, cover_url="https://example.test")
    assert repository.get_cover(track) is None
    assert repository.get_cover(track) == b"image"


def test_worker_coalesces_pending_requests():
    create_application()
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    calls = []

    class Worker(LatestRequestWorker):
        def _run(self, track, request_id):
            calls.append(request_id)
            if request_id == 1:
                entered.set()
                assert release.wait(5)
            if request_id == 100:
                done.set()

    worker = Worker()
    worker.fetch(None, 1)
    assert entered.wait(5)
    try:
        for request_id in range(2, 101):
            worker.fetch(None, request_id)
    finally:
        release.set()
    assert done.wait(5)
    assert calls == [1, 100]


def test_worker_shutdown_cancels_pending_and_closes_after_active_request():
    create_application()
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    calls = []

    class Worker(LatestRequestWorker):
        def _run(self, track, request_id):
            calls.append(request_id)
            entered.set()
            assert release.wait(5)

    worker = Worker()
    worker.repository = SimpleNamespace(close=closed.set)
    worker.fetch(None, 1)
    assert entered.wait(5)
    try:
        worker.fetch(None, 2)
        worker.close()
        worker.fetch(None, 3)
        assert not closed.is_set()
    finally:
        release.set()
    assert closed.wait(5)
    assert calls == [1]


def test_resume_reissues_fetches_invalidated_while_hidden(monkeypatch):
    app = create_application()
    window = OverlayWindow()
    config = default_config()
    config.show_album_cover = True
    controller = AppController(SimpleNamespace(), LyricsRepository(), window, config)
    from lyric_overlay.app_controller import PlaybackSnapshot
    controller.snapshot = PlaybackSnapshot(
        TrackInfo("song", "Song", "Artist", "Album", 1000, 0, True),
        LyricsData("loading", []),
    )
    controller._cover_retry_due_at = float("inf")
    calls = []
    monkeypatch.setattr(controller, "_start_worker", lambda: None)
    monkeypatch.setattr(controller.lyrics_worker, "fetch", lambda track, request_id: calls.append("lyrics"))
    monkeypatch.setattr(controller.cover_worker, "fetch", lambda track, request_id: calls.append("cover"))
    try:
        old_id = controller._lyrics_request_id
        controller.pause_polling()
        controller.resume_polling()
        assert controller._lyrics_request_id > old_id
        assert calls == ["lyrics", "cover"]
    finally:
        controller.shutdown()
        window.allow_exit()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_windows_artwork_on_demand_and_retry_metadata_bounded(monkeypatch):
    client = WindowsMediaSpotifyClient()
    reads = []
    media = SimpleNamespace(title="Song", artist="Artist", album_title="Album", thumbnail=object())

    async def properties():
        return media

    async def thumbnail(_):
        reads.append(media.title)
        return None

    timeline = SimpleNamespace(position=timedelta(0), start_time=timedelta(0),
                               end_time=timedelta(seconds=10), last_updated_time=datetime.now(timezone.utc))
    session = SimpleNamespace(source_app_user_model_id="Spotify.exe", try_get_media_properties_async=properties,
                              get_timeline_properties=lambda: timeline,
                              get_playback_info=lambda: SimpleNamespace(playback_status=client._playback_status.PLAYING))

    class Manager:
        @staticmethod
        async def request_async():
            return SimpleNamespace(get_current_session=lambda: session, get_sessions=lambda: [session])

    client._manager_class = Manager
    monkeypatch.setattr(client, "_read_thumbnail_bytes", thumbnail)
    client.set_artwork_enabled(False)
    assert asyncio.run(client._get_current_track_async()).cover_data is None
    assert not reads
    client.set_artwork_enabled(True)
    for index in range(30):
        media.title = str(index)
        asyncio.run(client._get_current_track_async())
    assert len(reads) == 30
    assert len(client._cover_retry_at) == 8
    client.set_artwork_enabled(False)
    asyncio.run(client._get_current_track_async())
    assert not client._cover_retry_at
    assert not client._cover_cache


def test_controller_tells_windows_client_when_cover_is_needed():
    app = create_application()
    client = WindowsMediaSpotifyClient()
    window = OverlayWindow()
    controller = AppController(client, LyricsRepository(), window, default_config())
    try:
        assert client._artwork_enabled is False
        controller.config.show_album_cover = True
        controller.refresh_album_cover()
        assert client._artwork_enabled is True
        controller.config.show_album_cover = False
        controller.refresh_album_cover()
        assert client._artwork_enabled is False
    finally:
        controller.stop()
        window.allow_exit()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_successful_cover_is_not_decoded_again_on_every_poll(monkeypatch):
    app = create_application()
    window = OverlayWindow()
    config = default_config()
    config.show_album_cover = True
    controller = AppController(None, LyricsRepository(), window, config)
    from lyric_overlay.app_controller import PlaybackSnapshot
    track = TrackInfo("song", "Song", "Artist", "Album", 1000, 0, True, cover_data=b"image")
    controller.snapshot = PlaybackSnapshot(track, LyricsData("local", [LyricLine(0, "Line")]))
    requests = []
    monkeypatch.setattr(controller.cover_worker, "fetch", lambda *args: requests.append(args))
    try:
        controller._cover_retry_due_at = 0.0  # Successful fetch: no retry needed.
        for progress in range(10):
            controller.refresh(replace(track, progress_ms=progress))
        assert requests == []
        controller.snapshot.track = replace(track, cover_data=None)
        controller._cover_retry_due_at = float("inf")
        controller.refresh(track)
        assert len(requests) == 1  # Artwork just arrived after enabling cover.
    finally:
        controller.shutdown()
        window.allow_exit()
        window.close()
        window.deleteLater()
        app.processEvents()
