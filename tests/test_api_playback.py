from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from spotipy import SpotifyException

from lyric_overlay import spotify_client as module


def client(payload=None):
    value = module.SpotifyApiClient.__new__(module.SpotifyApiClient)
    value._spotify = SimpleNamespace(current_user_playing_track=Mock(return_value=payload))
    value._spotify_exception = SpotifyException
    value._rate_limited_until = 0.0
    return value


def test_api_playing_and_paused_snapshots():
    payload = dict(item=dict(id="track-id", name="Title", artists=[dict(name="Artist")],
                            album=dict(name="Album", images=[dict(url="https://example.org/cover")]),
                            duration_ms=123000), progress_ms=4100, is_playing=True)
    value = client(payload)
    track = value.get_current_track()
    assert track.track_id == "track-id" and track.progress_ms == 4100
    assert track.cover_url == "https://example.org/cover"
    payload["is_playing"] = False
    assert not value.get_current_track().is_playing


@pytest.mark.parametrize("payload", [None, {}, {"item": None}])
def test_api_missing_track(payload):
    assert client(payload).get_current_track() is None


def test_api_rate_limit_prevents_network_calls_during_cooldown(monkeypatch):
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: 100))
    value = client()
    value._spotify.current_user_playing_track.side_effect = SpotifyException(429, -1, "rate limited")
    with pytest.raises(RuntimeError, match="Cooldown 60"):
        value.get_current_track()
    value._spotify.current_user_playing_track.reset_mock()
    with pytest.raises(RuntimeError, match="cooldown active"):
        value.get_current_track()
    value._spotify.current_user_playing_track.assert_not_called()


def test_api_invalid_credentials_fail_before_network():
    with pytest.raises(ValueError, match="incomplete"):
        module.SpotifyApiClient("", "", "")
