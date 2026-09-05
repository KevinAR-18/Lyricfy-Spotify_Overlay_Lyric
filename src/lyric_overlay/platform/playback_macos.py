"""Read Spotify's scripting interface without launching Spotify or using Web API."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
import threading
from pathlib import Path

from ..models import TrackInfo

MAX_SNAPSHOT_BYTES = 256 * 1024
QUERY_TIMEOUT_SECONDS = 2
AUTHORIZATION_TIMEOUT_SECONDS = 30
SCRIPT_FILE = Path(__file__).with_name("spotify_snapshot.js")
PERMISSION_MESSAGE = (
    "Allow Lyricfy to read Spotify in System Settings > Privacy & Security > "
    "Automation, then use Reload playback (Command+R)."
)


class AutomationPermissionError(RuntimeError):
    retryable = False


class PlaybackCancelled(RuntimeError):
    pass


def _text(value: object, *, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str):
        raise ValueError("Invalid Spotify text metadata")
    return value.strip()


def _milliseconds(value: object, multiplier: int = 1) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid Spotify time value")
    if not math.isfinite(value) or abs(value) > 2**53 / multiplier:
        raise ValueError("Invalid Spotify time range")
    return max(0, round(value * multiplier))


def parse_snapshot(raw: bytes | str) -> TrackInfo | None:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Spotify snapshot is too large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or type(payload.get("version")) is not int or payload["version"] != 1:
        raise ValueError("Unsupported Spotify snapshot format")
    status = payload.get("status")
    if status in {"not_running", "no_track", "changed"}:
        return None
    if status == "permission_denied":
        raise AutomationPermissionError(PERMISSION_MESSAGE)
    if status == "error":
        raise RuntimeError("Spotify scripting is unavailable. Open Spotify and reload playback.")
    if status != "ok" or not isinstance(payload.get("track"), dict):
        raise ValueError("Invalid Spotify snapshot status")
    item = payload["track"]
    title = _text(item.get("title"))
    if not title:
        return None
    artist = _text(item.get("artist"), optional=True)
    album = _text(item.get("album"), optional=True)
    identity = _text(item.get("id"), optional=True)
    duration_ms = _milliseconds(item.get("duration_ms"))
    progress_ms = _milliseconds(item.get("position_seconds"), 1000)
    playing = item.get("is_playing")
    if type(playing) is not bool:
        raise ValueError("Invalid Spotify playing state")
    cover = _text(item.get("artwork_url"), optional=True)
    if cover and not cover.startswith(("https://", "http://")):
        cover = ""
    if not identity:
        fields = [" ".join(field.casefold().split()) for field in (artist, title, album)]
        fields.append(str(round(duration_ms / 1000)))
        identity = "macos:local:" + hashlib.sha256(
            json.dumps(fields, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return TrackInfo(
        track_id=identity, title=title, artist=artist or "Unknown artist", album=album,
        duration_ms=duration_ms,
        progress_ms=min(progress_ms, duration_ms) if duration_ms else progress_ms,
        is_playing=playing, cover_url=cover or None,
    )


class MacSpotifyClient:
    def __init__(self, *, process_factory=None, script_path: Path = SCRIPT_FILE) -> None:
        self._process_factory = process_factory or subprocess.Popen
        self._script_path = script_path
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._process = None
        self._needs_authorization = True
        self._permission_denied = False

    def prepare(self) -> None:
        """Called only after the previous polling worker has finished."""
        self._cancelled.clear()

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass

    def get_current_track(self) -> TrackInfo | None:
        if self._cancelled.is_set():
            raise PlaybackCancelled("Playback query canceled")
        if self._permission_denied:
            raise AutomationPermissionError(PERMISSION_MESSAGE)
        timeout = AUTHORIZATION_TIMEOUT_SECONDS if self._needs_authorization else QUERY_TIMEOUT_SECONDS
        # Files avoid unbounded in-memory communicate() buffers. The static script
        # also limits its output, and the deadline bounds a malfunctioning child.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            with self._lock:
                if self._cancelled.is_set():
                    raise PlaybackCancelled("Playback query canceled")
                self._process = self._process_factory(
                    ["/usr/bin/osascript", "-l", "JavaScript", str(self._script_path)],
                    stdin=subprocess.DEVNULL, stdout=output, stderr=errors, shell=False,
                )
                process = self._process
            try:
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    process.wait()
                    if self._needs_authorization:
                        self._permission_denied = True
                        raise AutomationPermissionError(
                            "Spotify authorization timed out. " + PERMISSION_MESSAGE
                        ) from exc
                    raise RuntimeError("Spotify did not respond in time. Retrying shortly.") from exc
                if self._cancelled.is_set():
                    raise PlaybackCancelled("Playback query canceled")
                errors.seek(0)
                stderr = errors.read(MAX_SNAPSHOT_BYTES + 1)
                if process.returncode:
                    if b"-1743" in stderr:
                        self._permission_denied = True
                        raise AutomationPermissionError(PERMISSION_MESSAGE)
                    raise RuntimeError("Could not read Spotify. Open Spotify and reload playback.")
                output.seek(0)
                raw = output.read(MAX_SNAPSHOT_BYTES + 1)
                try:
                    track = parse_snapshot(raw)
                    # A missing process has not asked for Automation access yet.
                    if json.loads(raw).get("status") != "not_running":
                        self._needs_authorization = False
                    return track
                except AutomationPermissionError:
                    self._permission_denied = True
                    raise
                except (ValueError, UnicodeError, TypeError) as exc:
                    raise RuntimeError("Spotify returned an invalid playback snapshot. Retrying shortly.") from exc
            finally:
                with self._lock:
                    self._process = None
