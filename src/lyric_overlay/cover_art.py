from __future__ import annotations

import threading

import requests

from .models import TrackInfo
from .memory_cache import ByteCache


MAX_COVER_BYTES = 8 * 1024 * 1024
COVER_TIMEOUT_SECONDS = 5


class CoverArtRepository:
    def __init__(self, max_entries: int = 8, max_bytes: int = 8 * 1024 * 1024) -> None:
        self.max_entries = max(1, max_entries)
        self._cache = ByteCache(self.max_entries, max_bytes)
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Lyricfy/1.4"})

    def get_cover(self, track: TrackInfo) -> bytes | None:
        with self._lock:
            return self._get_cover(track)

    def _get_cover(self, track: TrackInfo) -> bytes | None:
        key = track.track_id
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        data = track.cover_data or self._download_cover(track.cover_url)
        if data is not None:
            self._cache[key] = data
        return data

    def close(self) -> None:
        with self._lock:
            self._cache.clear()
            self._session.close()

    def _download_cover(self, url: str | None) -> bytes | None:
        if not url:
            return None
        response = None
        try:
            response = self._session.get(url, timeout=COVER_TIMEOUT_SECONDS, stream=True)
            response.raise_for_status()
            content_length = int(response.headers.get("Content-Length") or 0)
            if content_length > MAX_COVER_BYTES:
                return None
            parts: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_COVER_BYTES:
                    return None
                parts.append(chunk)
            content = b"".join(parts)
        except (requests.RequestException, ValueError):
            return None
        finally:
            if response is not None:
                response.close()
        if not content or len(content) > MAX_COVER_BYTES:
            return None
        return content
