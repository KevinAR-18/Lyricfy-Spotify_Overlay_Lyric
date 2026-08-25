from lyric_overlay.cover_art import CoverArtRepository
from lyric_overlay.models import TrackInfo


def _track(track_id: str, *, cover_data=None, cover_url=None):
    return TrackInfo(
        track_id=track_id,
        title="Title",
        artist="Artist",
        album="Album",
        duration_ms=1000,
        progress_ms=0,
        is_playing=True,
        cover_url=cover_url,
        cover_data=cover_data,
    )


def test_returns_windows_cover_bytes_without_download(monkeypatch):
    repository = CoverArtRepository()
    monkeypatch.setattr(repository, "_download_cover", lambda url: (_ for _ in ()).throw(AssertionError()))
    assert repository.get_cover(_track("one", cover_data=b"image")) == b"image"


def test_downloads_and_caches_url_cover(monkeypatch):
    repository = CoverArtRepository()
    calls = []
    monkeypatch.setattr(repository, "_download_cover", lambda url: calls.append(url) or b"image")
    track = _track("one", cover_url="https://example.test/cover.jpg")
    assert repository.get_cover(track) == b"image"
    assert repository.get_cover(track) == b"image"
    assert calls == ["https://example.test/cover.jpg"]


def test_cache_is_bounded(monkeypatch):
    repository = CoverArtRepository(max_entries=2)
    monkeypatch.setattr(repository, "_download_cover", lambda url: url.encode())
    for index in range(3):
        repository.get_cover(_track(str(index), cover_url=str(index)))
    assert list(repository._cache) == ["1", "2"]


def test_missing_cover_is_cached(monkeypatch):
    repository = CoverArtRepository()
    calls = []
    monkeypatch.setattr(repository, "_download_cover", lambda url: calls.append(url) or None)
    track = _track("one")
    assert repository.get_cover(track) is None
    assert repository.get_cover(track) is None
    assert len(calls) == 1
