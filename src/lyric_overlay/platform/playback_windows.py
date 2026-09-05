from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from ..models import TrackInfo


# Windows media session can occasionally reject a COM/WinRT call after running for
# a long time. Treat it as a transient miss instead of showing raw HRESULT text.
WINDOWS_MEDIA_TRANSIENT_WINERRORS = {-2147418110, -214741810}
MAX_WINDOWS_COVER_BYTES = 8 * 1024 * 1024


def stable_windows_track_id(source_app: str, artist: str, title: str, duration_ms: int) -> str:
    normalized_artist = " ".join(artist.casefold().split())
    normalized_title = " ".join(title.casefold().split())
    duration_seconds = round(duration_ms / 1000) if duration_ms > 0 else 0
    return f"{source_app}:{normalized_artist}:{normalized_title}:{duration_seconds}"


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
        self._cover_cache: dict[str, bytes] = {}
        self._cover_retry_at: dict[str, float] = {}

    def get_current_track(self) -> TrackInfo | None:
        try:
            return asyncio.run(self._get_current_track_async())
        except OSError as exc:
            if getattr(exc, "winerror", None) in WINDOWS_MEDIA_TRANSIENT_WINERRORS:
                return None
            raise

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
        track_id = stable_windows_track_id(
            source_app=source_app,
            artist=artist,
            title=title,
            duration_ms=duration_ms,
        )
        cover_data = self._cover_cache.get(track_id)
        if cover_data is None and time.monotonic() >= self._cover_retry_at.get(track_id, 0.0):
            cover_data = await self._read_thumbnail_bytes(getattr(media, "thumbnail", None))
            if cover_data:
                self._cover_cache[track_id] = cover_data
            else:
                self._cover_retry_at[track_id] = time.monotonic() + 5.0

        return TrackInfo(
            track_id=track_id,
            title=title,
            artist=artist or "Unknown artist",
            album=(media.album_title or "").strip(),
            duration_ms=duration_ms,
            progress_ms=min(progress_ms, duration_ms) if duration_ms > 0 else progress_ms,
            is_playing=is_playing,
            cover_url=None,
            cover_data=cover_data,
        )

    @staticmethod
    async def _read_thumbnail_bytes(thumbnail) -> bytes | None:
        if thumbnail is None:
            return None
        try:
            from winsdk.windows.storage.streams import DataReader

            stream = await thumbnail.open_read_async()
            size = int(stream.size)
            if size <= 0 or size > MAX_WINDOWS_COVER_BYTES:
                stream.close()
                return None
            input_stream = stream.get_input_stream_at(0)
            reader = DataReader(input_stream)
            loaded = await reader.load_async(size)
            if loaded <= 0:
                reader.close()
                stream.close()
                return None
            output = bytearray(loaded)
            reader.read_bytes(output)
            data = bytes(output)
            reader.close()
            stream.close()
            return data or None
        except (AttributeError, OSError, RuntimeError, ValueError):
            return None

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


__all__ = ["WindowsMediaSpotifyClient", "stable_windows_track_id"]
