from __future__ import annotations

from collections import OrderedDict

import requests

from .models import TrackInfo


MAX_COVER_BYTES = 8 * 1024 * 1024
COVER_TIMEOUT_SECONDS = 5


class CoverArtRepository:
    def __init__(self, max_entries: int = 32) -> None:
        self.max_entries = max(1, max_entries)
        self._cache: OrderedDict[str, bytes | None] = OrderedDict()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Lyricfy/1.4"})

    def get_cover(self, track: TrackInfo) -> bytes | None:
        key = track.track_id
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        data = track.cover_data or self._download_cover(track.cover_url)
        self._cache[key] = data
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return data

    def _download_cover(self, url: str | None) -> bytes | None:
        if not url:
            return None
        try:
            response = self._session.get(url, timeout=COVER_TIMEOUT_SECONDS)
            response.raise_for_status()
            content = response.content
        except requests.RequestException:
            return None
        if not content or len(content) > MAX_COVER_BYTES:
            return None
        return content
