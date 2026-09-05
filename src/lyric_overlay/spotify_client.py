from __future__ import annotations

import sys
import time
from typing import Any, Protocol

from .config import SPOTIFY_API_PLAYBACK_SOURCE, TOKEN_CACHE, LOCAL_PLAYBACK_SOURCE, _normalize_playback_source
from .models import TrackInfo


SPOTIFY_SCOPES = "user-read-currently-playing user-read-playback-state"
RATE_LIMIT_COOLDOWN_SECONDS = 60

class PlaybackClient(Protocol):
    def get_current_track(self) -> TrackInfo | None:
        ...


class SpotifyApiClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("Spotify credentials are incomplete in .env")

        import spotipy
        from spotipy import SpotifyException
        from .oauth import DesktopSpotifyOAuth

        auth_manager = DesktopSpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SPOTIFY_SCOPES,
            cache_path=str(TOKEN_CACHE),
            open_browser=True,
        )
        self._spotify = spotipy.Spotify(
            auth_manager=auth_manager,
            requests_timeout=3,
            retries=0,
            status_retries=0,
            backoff_factor=0,
            status_forcelist=(),
        )
        self._spotify_exception = SpotifyException
        self._auth_manager = auth_manager
        self._rate_limited_until = 0.0

    def prepare(self) -> None:
        self._auth_manager.prepare()

    def cancel(self) -> None:
        self._auth_manager.cancel()

    def get_current_track(self) -> TrackInfo | None:
        cooldown_seconds = self._cooldown_seconds_remaining()
        if cooldown_seconds > 0:
            raise RuntimeError(
                f"Spotify API cooldown active. Try again in {cooldown_seconds} seconds."
            )

        try:
            payload = self._spotify.current_user_playing_track()
        except self._spotify_exception as exc:
            if exc.http_status == 429:
                self._rate_limited_until = time.monotonic() + RATE_LIMIT_COOLDOWN_SECONDS
                raise RuntimeError(
                    f"Spotify API rate limit reached. Cooldown {RATE_LIMIT_COOLDOWN_SECONDS} seconds."
                ) from exc
            raise RuntimeError(str(exc)) from exc
        if not payload or not payload.get("item"):
            return None

        item = payload["item"]
        artists = item.get("artists") or []
        images = (item.get("album") or {}).get("images") or []

        return TrackInfo(
            track_id=item["id"],
            title=item["name"],
            artist=", ".join(artist["name"] for artist in artists),
            album=(item.get("album") or {}).get("name", ""),
            duration_ms=item.get("duration_ms", 0),
            progress_ms=payload.get("progress_ms", 0),
            is_playing=payload.get("is_playing", False),
            cover_url=images[0]["url"] if images else None,
            cover_data=None,
        )

    def raw_playback_state(self) -> dict[str, Any] | None:
        return self._spotify.current_playback()

    def _cooldown_seconds_remaining(self) -> int:
        remaining = int(self._rate_limited_until - time.monotonic())
        return remaining if remaining > 0 else 0


def create_playback_client(
    playback_source: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> PlaybackClient:
    normalized_source = _normalize_playback_source(playback_source)
    if normalized_source == SPOTIFY_API_PLAYBACK_SOURCE:
        return SpotifyApiClient(client_id, client_secret, redirect_uri)
    if sys.platform == "win32":
        from .platform.playback_windows import WindowsMediaSpotifyClient
        return WindowsMediaSpotifyClient()
    if sys.platform == "darwin":
        from .platform.playback_macos import MacSpotifyClient
        return MacSpotifyClient()
    raise ValueError("Local Spotify playback is supported on Windows and macOS. Select API mode on this platform.")
