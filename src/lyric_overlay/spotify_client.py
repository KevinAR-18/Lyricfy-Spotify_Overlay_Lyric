from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Protocol

import spotipy
from spotipy import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from .config import SPOTIFY_API_PLAYBACK_SOURCE, TOKEN_CACHE, WINDOWS_PLAYBACK_SOURCE
from .models import TrackInfo


SPOTIFY_SCOPES = "user-read-currently-playing user-read-playback-state"
RATE_LIMIT_COOLDOWN_SECONDS = 60


class PlaybackClient(Protocol):
    def get_current_track(self) -> TrackInfo | None:
        ...


class WindowsMediaSpotifyClient:
    def __init__(self) -> None:
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus,
            )
        except ImportError as exc:
            raise RuntimeError(
                "Windows media session support is not installed. Install the `winsdk` package."
            ) from exc

        self._manager_class = GlobalSystemMediaTransportControlsSessionManager
        self._playback_status = GlobalSystemMediaTransportControlsSessionPlaybackStatus

    def get_current_track(self) -> TrackInfo | None:
        return asyncio.run(self._get_current_track_async())

    async def _get_current_track_async(self) -> TrackInfo | None:
        manager = await self._manager_class.request_async()
        session = self._pick_spotify_session(manager.get_current_session(), manager.get_sessions())
        if session is None:
            return None

        media = await session.try_get_media_properties_async()
        if media is None:
            return None

        timeline = session.get_timeline_properties()
        playback = session.get_playback_info()
        if timeline is None or playback is None:
            return None

        title = (media.title or "").strip()
        artist = (media.artist or "").strip()
        if not title:
            return None

        is_playing = playback.playback_status == self._playback_status.PLAYING
        progress_ms = self._timeline_position_ms(
            timeline.position,
            timeline.last_updated_time,
            advance=is_playing,
        )
        duration_ms = max(
            self._timedelta_to_ms(timeline.end_time) - self._timedelta_to_ms(timeline.start_time),
            0,
        )
        source_app = (session.source_app_user_model_id or "").strip() or "Spotify.exe"

        return TrackInfo(
            track_id=f"{source_app}:{artist}:{title}:{duration_ms}",
            title=title,
            artist=artist or "Unknown artist",
            album=(media.album_title or "").strip(),
            duration_ms=duration_ms,
            progress_ms=min(progress_ms, duration_ms) if duration_ms > 0 else progress_ms,
            is_playing=is_playing,
            cover_url=None,
        )

    def _pick_spotify_session(self, current_session, sessions):
        if current_session is not None and self._is_spotify_session(current_session):
            return current_session

        for session in sessions:
            if self._is_spotify_session(session):
                return session
        return None

    @staticmethod
    def _is_spotify_session(session) -> bool:
        source_app = (session.source_app_user_model_id or "").lower()
        return "spotify" in source_app

    @staticmethod
    def _timedelta_to_ms(value) -> int:
        return max(int(value.total_seconds() * 1000), 0)

    def _timeline_position_ms(self, position, last_updated_time: datetime, advance: bool) -> int:
        progress_ms = self._timedelta_to_ms(position)
        if not advance or last_updated_time is None:
            return progress_ms

        updated_utc = last_updated_time.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        elapsed_ms = max(int((now_utc - updated_utc).total_seconds() * 1000), 0)
        return progress_ms + elapsed_ms


class SpotifyApiClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("Spotify credentials are incomplete in .env")

        auth_manager = SpotifyOAuth(
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
        self._rate_limited_until = 0.0

    def get_current_track(self) -> TrackInfo | None:
        cooldown_seconds = self._cooldown_seconds_remaining()
        if cooldown_seconds > 0:
            raise RuntimeError(
                f"Spotify API cooldown active. Try again in {cooldown_seconds} seconds."
            )

        try:
            payload = self._spotify.current_user_playing_track()
        except SpotifyException as exc:
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
    normalized_source = (playback_source or "").strip().lower()

    if normalized_source in {"", WINDOWS_PLAYBACK_SOURCE}:
        return WindowsMediaSpotifyClient()
    if normalized_source == SPOTIFY_API_PLAYBACK_SOURCE:
        return SpotifyApiClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    raise ValueError(
        f"Unsupported PLAYBACK_SOURCE={playback_source!r}. Use `{WINDOWS_PLAYBACK_SOURCE}` or `{SPOTIFY_API_PLAYBACK_SOURCE}`."
    )
