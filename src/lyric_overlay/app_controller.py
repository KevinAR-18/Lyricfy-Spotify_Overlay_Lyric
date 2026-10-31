from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

from .cinematic.preferences import needs_artwork
from .config import AppConfig, SPOTIFY_API_PLAYBACK_SOURCE
from .cover_art import CoverArtRepository
from .lyrics import LyricsRepository
from .models import LyricsData, TrackInfo
from .overlay import OverlayWindow
from .spotify_client import PlaybackClient
from .sync_engine import SyncEngine


@dataclass(slots=True)
class PlaybackSnapshot:
    track: TrackInfo | None = None
    lyrics: LyricsData | None = None


class PlaybackWorker(QObject):
    refreshed = Signal(object)
    failed = Signal(str)

    # Error sesaat dari media session/COM tidak perlu ditampilkan ke user;
    # polling berikutnya biasanya langsung berhasil lagi.
    _TRANSIENT_WINERRORS = {-2147418110, -214741810}

    def __init__(self, playback_client: PlaybackClient, poll_interval_ms: int) -> None:
        super().__init__()
        self.playback_client = playback_client
        self.poll_interval_ms = poll_interval_ms
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                track = self.playback_client.get_current_track()
                if self._stop_event.is_set():
                    return
                self.refreshed.emit(track)
            except Exception as exc:  # noqa: BLE001
                if not self._is_transient_error(exc):
                    self.failed.emit(str(exc))
            self._stop_event.wait(self.poll_interval_ms / 1000)

    def _is_transient_error(self, exc: Exception) -> bool:
        return getattr(exc, "winerror", None) in self._TRANSIENT_WINERRORS



class LatestRequestWorker(QObject):
    """Keep at most one running and one replaceable pending request."""

    def __init__(self) -> None:
        super().__init__()
        self._request_lock = threading.Lock()
        self._pending = None
        self._running = False
        self._closed = False

    def fetch(self, track: TrackInfo, request_id: int) -> None:
        with self._request_lock:
            if self._closed:
                return
            self._pending = (track, request_id)
            if self._running:
                return
            self._running = True
        threading.Thread(target=self._dispatch, daemon=True).start()

    def cancel_pending(self) -> None:
        with self._request_lock:
            self._pending = None

    def close(self) -> None:
        with self._request_lock:
            if self._closed:
                return
            self._closed = True
            self._pending = None
            idle = not self._running
        if idle:
            self._close_repository()

    def _close_repository(self) -> None:
        repository = getattr(self, "repository", getattr(self, "lyrics_repository", None))
        close = getattr(repository, "close", None)
        if close is not None:
            close()

    def _dispatch(self) -> None:
        while True:
            with self._request_lock:
                request = self._pending
                self._pending = None
                if request is None:
                    self._running = False
                    closed = self._closed
                else:
                    closed = False
            if request is None:
                if closed:
                    self._close_repository()
                return
            try:
                self._run(*request)
            except Exception:
                logging.getLogger(__name__).exception("Background fetch failed")


class LyricsWorker(LatestRequestWorker):
    fetched = Signal(str, object, int)

    def __init__(self, lyrics_repository: LyricsRepository) -> None:
        super().__init__()
        self.lyrics_repository = lyrics_repository

    def _run(self, track: TrackInfo, request_id: int) -> None:
        try:
            lyrics = self.lyrics_repository.get_lyrics(
                artist=track.artist,
                title=track.title,
                duration_ms=track.duration_ms,
            )
        except Exception:
            logging.getLogger(__name__).exception("Lyrics fetch failed")
            lyrics = LyricsData(source="none", lines=[])
        self.fetched.emit(track.track_id, lyrics, request_id)


class CoverArtWorker(LatestRequestWorker):
    fetched = Signal(str, object, int)

    def __init__(self, repository: CoverArtRepository) -> None:
        super().__init__()
        self.repository = repository

    def _run(self, track: TrackInfo, request_id: int) -> None:
        try:
            data = self.repository.get_cover(track)
        except Exception:
            logging.getLogger(__name__).exception("Cover fetch failed")
            data = None
        self.fetched.emit(track.track_id, data, request_id)


class AppController(QObject):
    cinematic_frame = Signal(object)
    cinematic_artwork = Signal(object)
    playback_error = Signal(str)
    _RENDER_INTERVAL_MS = 50
    _MAX_LYRICS_RETRIES = 3
    _LYRICS_RETRY_DELAY_SECONDS = 4.0
    _FETCHING_LYRICS_STATUS = "Fetching lyrics..."

    def __init__(
        self,
        playback_client: PlaybackClient | None,
        lyrics_repository: LyricsRepository,
        overlay: OverlayWindow,
        config: AppConfig,
    ) -> None:
        super().__init__()
        self.playback_client = playback_client
        self.lyrics_repository = lyrics_repository
        self.overlay = overlay
        self.config = config
        self.cinematic_cover_preview = False
        self._sync_artwork_requirement()
        self.sync_engine = SyncEngine()
        self.snapshot = PlaybackSnapshot()
        self.worker: PlaybackWorker | None = None
        self.lyrics_worker = LyricsWorker(lyrics_repository)
        self.cover_worker = CoverArtWorker(CoverArtRepository())
        self._last_track_refresh_at = 0.0
        self._last_rendered_line: tuple[str, str] | None = None
        self._classic_frame = None
        self._classic_progress = None
        self._lyrics_request_id = 0
        self._lyrics_retry_count = 0
        self._lyrics_retry_due_at = 0.0
        self._cover_request_id = 0
        self._cover_retry_due_at = 0.0
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(self._RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._render_current_state)
        self.lyrics_worker.fetched.connect(self._apply_fetched_lyrics)
        self.cover_worker.fetched.connect(self._apply_fetched_cover)

    def start(self) -> None:
        if self.playback_client is None:
            self.overlay.set_track(None)
            self.overlay.set_lines(*self._playback_unavailable_lines())
            return
        if not self._render_timer.isActive():
            self._render_timer.start()
        self._start_worker()

    def stop(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self._render_timer.stop()
        self._lyrics_request_id += 1
        self._cover_request_id += 1
        self.lyrics_worker.cancel_pending()
        self.cover_worker.cancel_pending()

    def shutdown(self) -> None:
        """Close sessions after in-flight fetches finish; do not block the GUI."""
        self.stop()
        self.lyrics_worker.close()
        self.cover_worker.close()

    def reconnect(
        self,
        playback_client: PlaybackClient | None,
        config: AppConfig,
        unavailable_message: str | None = None,
    ) -> None:
        self.stop()
        self._classic_frame = None
        self._classic_progress = None
        self.playback_client = playback_client
        self.config = config
        self._sync_artwork_requirement()
        self.snapshot = PlaybackSnapshot()
        self._lyrics_request_id += 1
        self._lyrics_retry_count = 0
        self._lyrics_retry_due_at = 0.0
        self._cover_request_id += 1
        self._cover_retry_due_at = 0.0
        self.sync_engine.set_lyrics(LyricsData(source="none", lines=[]))
        self._render_cinematic_state()
        self.overlay.load_config_values(config)
        if self.playback_client is None:
            self.overlay.set_track(None)
            primary, secondary = self._playback_unavailable_lines()
            self.overlay.set_lines(unavailable_message or primary, secondary)
            return

        self.overlay.show_status("Playback client ready — waiting for Spotify")
        self.start()

    def pause_polling(self) -> None:
        self.stop()

    def resume_polling(self) -> None:
        if self.playback_client is None:
            return
        if not self._render_timer.isActive():
            self._render_timer.start()
        track = self.snapshot.track
        if track is not None:
            if self.snapshot.lyrics is None or self.snapshot.lyrics.source == "loading":
                self._request_lyrics(track)
            if self._needs_cover() and self._cover_retry_due_at:
                self._request_album_cover(track)
        self._start_worker()

    def refresh(self, track: TrackInfo | None) -> None:
        if track is None:
            self._last_track_refresh_at = 0.0
            self._last_rendered_line = None
            self._lyrics_request_id += 1
            self._lyrics_retry_count = 0
            self._lyrics_retry_due_at = 0.0
            self._cover_request_id += 1
            self._cover_retry_due_at = 0.0
            self.snapshot = PlaybackSnapshot(track=None, lyrics=LyricsData(source="none", lines=[]))
            self.sync_engine.set_lyrics(self.snapshot.lyrics)
            self.overlay.set_track(None)
            self.overlay.set_album_cover(None)
            self.overlay.set_lines("", "")
            self.overlay.show_status("")
            self._render_cinematic_state()
            return

        track_changed = self.snapshot.track is None or self.snapshot.track.track_id != track.track_id

        if track_changed:
            self._lyrics_retry_count = 0
            self._lyrics_retry_due_at = 0.0
            self.snapshot = PlaybackSnapshot(track=track, lyrics=LyricsData(source="none", lines=[]))
            self._cover_request_id += 1
            self._cover_retry_due_at = 0.0
            self.overlay.set_album_cover(None)
            if self._needs_cover():
                self._request_album_cover(track)
            self._request_lyrics(track)
        else:
            artwork_arrived = bool(track.cover_data) and not self.snapshot.track.cover_data
            self.snapshot.track = track
            self._retry_lyrics_if_needed(track)
            if self._needs_cover() and self._cover_retry_due_at and (artwork_arrived or time.monotonic() >= self._cover_retry_due_at):
                self._request_album_cover(track)

        self._last_track_refresh_at = time.monotonic()
        self._last_rendered_line = None
        lyrics_source = self.snapshot.lyrics.source if self.snapshot.lyrics else ""
        self.overlay.set_track(track, lyrics_source=lyrics_source)

        if not track.is_playing:
            self.overlay.set_paused()
        elif self._should_show_fetching_status():
            self.overlay.show_status(self._FETCHING_LYRICS_STATUS)
        else:
            self.overlay.show_status("")

        self._render_current_state()

    def refresh_album_cover(self) -> None:
        self._sync_artwork_requirement()
        self.cover_worker.cancel_pending()
        self._cover_request_id += 1
        self._cover_retry_due_at = 0.0
        self.overlay.set_album_cover(None)
        self.cinematic_artwork.emit(None)
        track = self.snapshot.track
        if self._needs_cover() and track is not None:
            self._request_album_cover(track)

    def _needs_cover(self) -> bool:
        return self.config.show_album_cover or getattr(self, "cinematic_cover_preview", False) or (
            self.config.cinematic_enabled and needs_artwork(self.config.cinematic_options)
        )

    def _sync_artwork_requirement(self) -> None:
        setter = getattr(self.playback_client, "set_artwork_enabled", None)
        if setter is not None:
            setter(self._needs_cover())

    def _request_album_cover(self, track: TrackInfo) -> None:
        self._cover_retry_due_at = float("inf")
        self.cover_worker.fetch(track, self._cover_request_id)

    def _apply_fetched_cover(self, track_id: str, data: bytes | None, request_id: int) -> None:
        track = self.snapshot.track
        if track is None or track.track_id != track_id or request_id != self._cover_request_id:
            return
        if not self._needs_cover():
            return
        self._cover_retry_due_at = 0.0 if data else time.monotonic() + 5.0
        self.overlay.set_album_cover(data if self.config.show_album_cover else None)
        self.cinematic_artwork.emit(data)

    def show_error(self, message: str) -> None:
        self.playback_error.emit(self._format_error_message(message))
        self.overlay.show_status(self._format_error_message(message))

    def _apply_fetched_lyrics(self, track_id: str, lyrics: LyricsData, request_id: int) -> None:
        current_track = self.snapshot.track
        if current_track is None:
            return
        if request_id != self._lyrics_request_id or current_track.track_id != track_id:
            return

        self.snapshot.lyrics = lyrics
        self.sync_engine.set_lyrics(lyrics)
        self._last_rendered_line = None
        self.overlay.set_track(current_track, lyrics_source=lyrics.source)
        if lyrics.is_empty:
            self._lyrics_retry_count += 1
            self._lyrics_retry_due_at = time.monotonic() + self._LYRICS_RETRY_DELAY_SECONDS
            if self._lyrics_retry_count >= self._MAX_LYRICS_RETRIES:
                self.overlay.show_no_lyrics_notice()
                self.overlay.show_status("")
            else:
                self.overlay.show_status(self._FETCHING_LYRICS_STATUS)
        else:
            self._lyrics_retry_count = 0
            self._lyrics_retry_due_at = 0.0
            self.overlay.show_status("")

        if current_track.is_playing and not lyrics.is_empty:
            self.overlay.show_status("")

        self._render_current_state()

    def _request_lyrics(self, track: TrackInfo) -> None:
        self._lyrics_request_id += 1
        self._lyrics_retry_due_at = 0.0
        loading_lyrics = LyricsData(source="loading", lines=[])
        self.snapshot.lyrics = loading_lyrics
        self.sync_engine.set_lyrics(loading_lyrics)
        self.overlay.show_status(self._FETCHING_LYRICS_STATUS)
        self.lyrics_worker.fetch(track, self._lyrics_request_id)

    def _retry_lyrics_if_needed(self, track: TrackInfo) -> None:
        lyrics = self.snapshot.lyrics
        if lyrics is None or lyrics.source != "none":
            return
        if self._lyrics_retry_count >= self._MAX_LYRICS_RETRIES:
            return
        if time.monotonic() < self._lyrics_retry_due_at:
            return

        self._request_lyrics(track)

    def _start_worker(self) -> None:
        if self.playback_client is None:
            return
        if self.worker is not None:
            return

        self.worker = PlaybackWorker(
            playback_client=self.playback_client,
            poll_interval_ms=self.config.poll_interval_ms,
        )
        self.worker.refreshed.connect(self.refresh)
        self.worker.failed.connect(self.show_error)
        self.worker.start()

    def _render_current_state(self) -> None:
        self._render_cinematic_state()
        track = self.snapshot.track
        if track is None:
            self._classic_frame = None
            self._classic_progress = None
            return

        estimated_progress_ms = self._estimated_progress_ms(track)
        adjusted_progress_ms = max(0, estimated_progress_ms + self.config.lyric_offset_ms)
        active_index, active_line = self.sync_engine.current_line(adjusted_progress_ms)
        next_line = self.sync_engine.next_line(active_index)
        rendered_line = (
            active_line.text if active_line else "",
            next_line.text if next_line else "",
        )

        identity = (track.track_id, active_index, track.is_playing)
        discontinuity = self._classic_progress is not None and (
            adjusted_progress_ms < self._classic_progress - 200
            or adjusted_progress_ms > self._classic_progress + 1500
        )
        self._classic_progress = adjusted_progress_ms
        previous_identity = self._classic_frame
        self._classic_frame = identity
        if rendered_line == self._last_rendered_line and identity == previous_identity and not discontinuity:
            return

        sequential = (previous_identity is not None and track.is_playing and previous_identity[2]
                      and previous_identity[0] == track.track_id
                      and active_index == previous_identity[1] + 1 and not discontinuity)
        remaining = next_line.timestamp_ms - adjusted_progress_ms if next_line else 1000
        duration = max(0, min(360, int(remaining * 0.45))) if sequential else 0
        self._last_rendered_line = rendered_line
        self.overlay.set_lines(*rendered_line, transition_ms=duration)

    def _render_cinematic_state(self) -> None:
        track = self.snapshot.track
        lyrics = self.snapshot.lyrics
        progress = max(0, self._estimated_progress_ms(track) + self.config.lyric_offset_ms) if track else 0
        index, _ = self.sync_engine.current_line(progress)
        lines = lyrics.lines if lyrics else []
        rows = [{"index": i, "text": lines[i].text}
                for i in range(max(0, index - 2), min(len(lines), index + 3))]
        message = ""
        if not track:
            message = "Waiting for Spotify playback"
        elif not lines:
            message = "Fetching lyrics…" if self._should_show_fetching_status() else "No synced lyrics found"
        elif index < 0:
            message = "♪"
        elif not lines[index].text.strip():
            message = "♪"
        remaining = lines[index + 1].timestamp_ms - progress if index + 1 < len(lines) else 1000
        self.cinematic_frame.emit({
            "track": track.track_id if track else "", "title": track.title if track else "Lyricfy",
            "artist": track.artist if track else "Open Spotify to start", "playing": bool(track and track.is_playing),
            "index": index, "rows": rows, "progress": progress, "remaining": remaining, "message": message,
        })

    def _estimated_progress_ms(self, track: TrackInfo) -> int:
        if not track.is_playing or self._last_track_refresh_at <= 0:
            return track.progress_ms

        elapsed_ms = int((time.monotonic() - self._last_track_refresh_at) * 1000)
        return min(track.duration_ms, track.progress_ms + max(0, elapsed_ms))

    def _format_error_message(self, message: str) -> str:
        normalized = message.strip()
        lowered = normalized.lower()

        if "cooldown active" in lowered or "cooldown " in lowered:
            return normalized
        if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
            return "Spotify API rate limit reached. Please try again shortly."
        if "connectionerror" in lowered or "failed to establish a new connection" in lowered:
            return "Failed to connect to the Spotify API."
        if normalized:
            return normalized
        return "An error occurred while fetching Spotify data."

    def _should_show_fetching_status(self) -> bool:
        lyrics = self.snapshot.lyrics
        if lyrics is None:
            return False
        return lyrics.source in {"loading", "none"} and self._lyrics_retry_count < self._MAX_LYRICS_RETRIES

    def _playback_unavailable_lines(self) -> tuple[str, str]:
        if self.config.playback_source == SPOTIFY_API_PLAYBACK_SOURCE:
            return (
                "Fill Spotify API credentials in Settings",
                "Then press Ctrl+R to retry",
            )
        return (
            "Open Spotify desktop and start playback",
            "Then press Ctrl+R to retry",
        )
