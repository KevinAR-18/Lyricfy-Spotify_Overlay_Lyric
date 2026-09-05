from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .config import AppConfig, SPOTIFY_API_PLAYBACK_SOURCE, reload_shortcut_label
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
        prepare = getattr(self.playback_client, "prepare", None)
        if prepare is not None:
            prepare()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        cancel = getattr(self.playback_client, "cancel", None)
        if cancel is not None:
            cancel()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.1)
        # Keep the reference until it actually exits. A replacement must wait.

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stopping(self) -> bool:
        return self._stop_event.is_set()

    def _run(self) -> None:
        failures = 0
        last_error = None
        while not self._stop_event.is_set():
            delay = max(0.05, self.poll_interval_ms / 1000)
            try:
                track = self.playback_client.get_current_track()
                if not self._stop_event.is_set():
                    self.refreshed.emit(track)
                failures = 0
                last_error = None
            except Exception as exc:  # noqa: BLE001
                if self._stop_event.is_set():
                    break
                if not self._is_transient_error(exc):
                    message = str(exc)
                    if message != last_error:
                        self.failed.emit(message)
                        last_error = message
                    if not getattr(exc, "retryable", True):
                        self._stop_event.wait()
                        break
                    failures = min(failures + 1, 5)
                    delay = max(delay, min(30, 2 ** (failures - 1)))
            self._stop_event.wait(delay)

    def _is_transient_error(self, exc: Exception) -> bool:
        return getattr(exc, "winerror", None) in self._TRANSIENT_WINERRORS



class LyricsWorker(QObject):
    fetched = Signal(str, object, int)

    def __init__(self, lyrics_repository: LyricsRepository) -> None:
        super().__init__()
        self.lyrics_repository = lyrics_repository

    def fetch(self, track: TrackInfo, request_id: int) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(track, request_id),
            daemon=True,
        )
        thread.start()

    def _run(self, track: TrackInfo, request_id: int) -> None:
        lyrics = self.lyrics_repository.get_lyrics(
            artist=track.artist,
            title=track.title,
            duration_ms=track.duration_ms,
        )
        self.fetched.emit(track.track_id, lyrics, request_id)


class CoverArtWorker(QObject):
    fetched = Signal(str, object, int)

    def __init__(self, repository: CoverArtRepository) -> None:
        super().__init__()
        self.repository = repository

    def fetch(self, track: TrackInfo, request_id: int) -> None:
        threading.Thread(target=self._run, args=(track, request_id), daemon=True).start()

    def _run(self, track: TrackInfo, request_id: int) -> None:
        data = self.repository.get_cover(track)
        self.fetched.emit(track.track_id, data, request_id)


class AppController(QObject):
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
        self.sync_engine = SyncEngine()
        self.snapshot = PlaybackSnapshot()
        self.worker: PlaybackWorker | None = None
        self._polling_enabled = False
        self.lyrics_worker = LyricsWorker(lyrics_repository)
        self.cover_worker = CoverArtWorker(CoverArtRepository())
        self._last_track_refresh_at = 0.0
        self._last_rendered_line: tuple[str, str] | None = None
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
        self._polling_enabled = True
        if self.playback_client is None:
            self.overlay.set_track(None)
            self.overlay.set_lines(*self._playback_unavailable_lines())
            return
        if not self._render_timer.isActive():
            self._render_timer.start()
        self._start_worker()

    def stop(self) -> None:
        self._polling_enabled = False
        if self.worker is not None:
            self.worker.stop()
        self._render_timer.stop()
        self._lyrics_request_id += 1
        self._cover_request_id += 1

    def reconnect(
        self,
        playback_client: PlaybackClient | None,
        config: AppConfig,
        unavailable_message: str | None = None,
    ) -> None:
        self.stop()
        self.playback_client = playback_client
        self.config = config
        self.snapshot = PlaybackSnapshot()
        self._lyrics_request_id += 1
        self._lyrics_retry_count = 0
        self._lyrics_retry_due_at = 0.0
        self._cover_request_id += 1
        self._cover_retry_due_at = 0.0
        self.sync_engine.set_lyrics(LyricsData(source="none", lines=[]))
        self._last_track_refresh_at = 0.0
        self._last_rendered_line = None
        self.overlay.set_album_cover(None)
        self.overlay.load_config_values(config)
        if self.playback_client is None:
            self.overlay.set_track(None)
            primary, secondary = self._playback_unavailable_lines()
            self.overlay.set_lines(unavailable_message or primary, secondary)
            return

        self.overlay.show_status("Spotify playback connected")
        self.start()

    def pause_polling(self) -> None:
        self.stop()
        self.refresh(None)

    def resume_polling(self) -> None:
        self.start()

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
            return

        track_changed = self.snapshot.track is None or self.snapshot.track.track_id != track.track_id

        if track_changed:
            self._lyrics_retry_count = 0
            self._lyrics_retry_due_at = 0.0
            self.snapshot = PlaybackSnapshot(track=track, lyrics=LyricsData(source="none", lines=[]))
            self._cover_request_id += 1
            self._cover_retry_due_at = 0.0
            self.overlay.set_album_cover(None)
            if self.config.show_album_cover:
                self._request_album_cover(track)
            self._request_lyrics(track)
        else:
            self.snapshot.track = track
            self._retry_lyrics_if_needed(track)
            if self.config.show_album_cover and time.monotonic() >= self._cover_retry_due_at:
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
        self._cover_request_id += 1
        self._cover_retry_due_at = 0.0
        self.overlay.set_album_cover(None)
        track = self.snapshot.track
        if self.config.show_album_cover and track is not None:
            self._request_album_cover(track)

    def _request_album_cover(self, track: TrackInfo) -> None:
        self._cover_retry_due_at = float("inf")
        self.cover_worker.fetch(track, self._cover_request_id)

    def _apply_fetched_cover(self, track_id: str, data: bytes | None, request_id: int) -> None:
        track = self.snapshot.track
        if track is None or track.track_id != track_id or request_id != self._cover_request_id:
            return
        if not self.config.show_album_cover:
            return
        self._cover_retry_due_at = 0.0 if data else time.monotonic() + 5.0
        self.overlay.set_album_cover(data)

    def show_error(self, message: str) -> None:
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
        if not self._polling_enabled or self.playback_client is None:
            return
        if self.worker is not None:
            if self.worker.is_running:
                if self.worker.stopping:
                    QTimer.singleShot(50, self._start_worker)
                return
            self.worker.deleteLater()

        self.worker = PlaybackWorker(
            playback_client=self.playback_client,
            poll_interval_ms=self.config.poll_interval_ms,
        )
        self.worker.refreshed.connect(self._receive_track)
        self.worker.failed.connect(self._receive_error)
        self.worker.start()

    @Slot(object)
    def _receive_track(self, track: TrackInfo | None) -> None:
        if self._polling_enabled and self.sender() is self.worker and not self.worker.stopping:
            self.refresh(track)

    @Slot(str)
    def _receive_error(self, message: str) -> None:
        if self._polling_enabled and self.sender() is self.worker and not self.worker.stopping:
            self.refresh(None)
            self.show_error(message)

    def _render_current_state(self) -> None:
        track = self.snapshot.track
        if track is None:
            return

        estimated_progress_ms = self._estimated_progress_ms(track)
        adjusted_progress_ms = max(0, estimated_progress_ms + self.config.lyric_offset_ms)
        active_index, active_line = self.sync_engine.current_line(adjusted_progress_ms)
        next_line = self.sync_engine.next_line(active_index)
        rendered_line = (
            active_line.text if active_line else "",
            next_line.text if next_line else "",
        )

        if rendered_line == self._last_rendered_line:
            return

        self._last_rendered_line = rendered_line
        self.overlay.set_lines(*rendered_line)

    def _estimated_progress_ms(self, track: TrackInfo) -> int:
        if not track.is_playing or self._last_track_refresh_at <= 0:
            return track.progress_ms

        elapsed_ms = int((time.monotonic() - self._last_track_refresh_at) * 1000)
        position = track.progress_ms + max(0, elapsed_ms)
        return min(track.duration_ms, position) if track.duration_ms > 0 else position

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
                f"Then press {reload_shortcut_label()} to retry",
            )
        return (
            "Open Spotify desktop and start playback",
            f"Then press {reload_shortcut_label()} to retry",
        )
