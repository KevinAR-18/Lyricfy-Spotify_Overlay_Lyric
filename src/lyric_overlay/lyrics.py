from __future__ import annotations

import re
from pathlib import Path

import requests

from .config import LRC_DIR
from .models import LyricLine, LyricsData


TIMESTAMP_RE = re.compile(r"\[(\d{2}):(\d{2})(?:[.:](\d{2,3}))?\]")


def sanitize_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", value).strip()


def parse_lrc(text: str, source: str) -> LyricsData:
    lines: list[LyricLine] = []

    for raw_line in text.splitlines():
        matches = list(TIMESTAMP_RE.finditer(raw_line))
        if not matches:
            continue

        lyric_text = TIMESTAMP_RE.sub("", raw_line).strip()
        if not lyric_text:
            continue

        for match in matches:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            fraction = match.group(3) or "0"
            milliseconds = int(fraction.ljust(3, "0")[:3])
            timestamp_ms = (minutes * 60 * 1000) + (seconds * 1000) + milliseconds
            lines.append(LyricLine(timestamp_ms=timestamp_ms, text=lyric_text))

    lines.sort(key=lambda line: line.timestamp_ms)
    return LyricsData(source=source, lines=lines)


class LyricsRepository:
    def __init__(self, lrclib_enabled: bool = True) -> None:
        self.lrclib_enabled = lrclib_enabled
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "lyric-overlay-starter/1.0"})
        self._cache: dict[tuple[str, str, int], LyricsData] = {}

    def get_lyrics(self, artist: str, title: str, duration_ms: int) -> LyricsData:
        cache_key = self._cache_key(artist=artist, title=title, duration_ms=duration_ms)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        local = self._load_local_lrc(artist=artist, title=title)
        if not local.is_empty:
            self._cache[cache_key] = local
            return local

        if self.lrclib_enabled:
            remote = self._load_lrclib(artist=artist, title=title, duration_ms=duration_ms)
            if not remote.is_empty:
                self._cache[cache_key] = remote
                return remote

        return LyricsData(source="none", lines=[])

    def _cache_key(self, artist: str, title: str, duration_ms: int) -> tuple[str, str, int]:
        normalized_artist = " ".join(artist.casefold().split())
        normalized_title = " ".join(title.casefold().split())
        normalized_duration = round(duration_ms / 1000)
        return normalized_artist, normalized_title, normalized_duration

    def _load_local_lrc(self, artist: str, title: str) -> LyricsData:
        filename = f"{sanitize_filename(artist)} - {sanitize_filename(title)}.lrc"
        path = LRC_DIR / filename
        if not path.exists():
            return LyricsData(source="local", lines=[])

        return parse_lrc(path.read_text(encoding="utf-8"), source=f"local:{path.name}")

    def _load_lrclib(self, artist: str, title: str, duration_ms: int) -> LyricsData:
        try:
            response = self._session.get(
                "https://lrclib.net/api/get",
                params={
                    "artist_name": artist,
                    "track_name": title,
                    "duration": round(duration_ms / 1000),
                },
                timeout=5,
            )
            if response.status_code != 200:
                return LyricsData(source="lrclib", lines=[])

            data = response.json()
            synced = data.get("syncedLyrics") or ""
            if not synced.strip():
                return LyricsData(source="lrclib", lines=[])

            return parse_lrc(synced, source="lrclib")
        except requests.RequestException:
            return LyricsData(source="lrclib", lines=[])
