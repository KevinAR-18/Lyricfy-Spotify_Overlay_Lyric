from __future__ import annotations

import re
from pathlib import Path

import requests

from .config import FETCHED_LRC_DIR, LRC_DIR
from .models import LyricLine, LyricsData


TIMESTAMP_RE = re.compile(r"\[(\d{2}):(\d{2})(?:[.:](\d{2,3}))?\]")
LRCLIB_TIMEOUT_SECONDS = 5
LOCAL_LRC_SEPARATOR = " - "


def sanitize_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", value).strip()


def normalize_match_text(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"[^\w\s]+", " ", normalized)
    return " ".join(normalized.split())


def artist_parts(value: str) -> set[str]:
    parts = re.split(
        r"\s*(?:,|&|\+|;|\bfeat\.?\b|\bfeaturing\b|\bwith\b|/)\s*",
        value,
        flags=re.IGNORECASE,
    )
    return {normalized for part in parts if (normalized := normalize_match_text(part))}


def debug_log(message: str) -> None:
    del message


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
    def __init__(self, lrclib_enabled: bool = True, auto_save_fetched_lrc: bool = True) -> None:
        self.lrclib_enabled = lrclib_enabled
        self.auto_save_fetched_lrc = auto_save_fetched_lrc
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
        for path in self._local_lrc_paths(artist=artist, title=title):
            if not path.exists():
                continue
            return parse_lrc(path.read_text(encoding="utf-8"), source=f"local:{path.name}")
        return LyricsData(source="local", lines=[])

    def _load_lrclib(self, artist: str, title: str, duration_ms: int) -> LyricsData:
        duration_seconds = round(duration_ms / 1000)
        try:
            response = self._session.get(
                "https://lrclib.net/api/get",
                params={
                    "artist_name": artist,
                    "track_name": title,
                    "duration": duration_seconds,
                },
                timeout=LRCLIB_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                return self._search_lrclib(
                    artist=artist,
                    title=title,
                    duration_seconds=duration_seconds,
                )

            data = response.json()
            synced = data.get("syncedLyrics") or ""
            if not synced.strip():
                return self._search_lrclib(
                    artist=artist,
                    title=title,
                    duration_seconds=duration_seconds,
                )

            lyrics = parse_lrc(synced, source="lrclib")
            if not lyrics.is_empty and self.auto_save_fetched_lrc:
                self._save_fetched_lrc(artist=artist, title=title, text=synced)
            return lyrics
        except requests.RequestException:
            return self._search_lrclib(
                artist=artist,
                title=title,
                duration_seconds=duration_seconds,
            )

    def _search_lrclib(
        self,
        artist: str,
        title: str,
        duration_seconds: int,
    ) -> LyricsData:
        try:
            response = self._session.get(
                "https://lrclib.net/api/search",
                params={
                    "artist_name": artist,
                    "track_name": title,
                },
                timeout=LRCLIB_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                return LyricsData(source="lrclib", lines=[])

            results = response.json()
            if not isinstance(results, list):
                return LyricsData(source="lrclib", lines=[])

            for item in results:
                synced = (item.get("syncedLyrics") or "").strip()
                if not synced:
                    continue

                item_artist = str(item.get("artistName") or "")
                item_title = str(item.get("trackName") or item.get("name") or "")
                if not self._lrclib_result_matches(
                    requested_artist=artist,
                    requested_title=title,
                    item_artist=item_artist,
                    item_title=item_title,
                ):
                    continue
                item_duration = item.get("duration")
                try:
                    item_duration_seconds = int(round(float(item_duration)))
                except (TypeError, ValueError):
                    item_duration_seconds = 0

                if item_duration_seconds and abs(item_duration_seconds - duration_seconds) > 2:
                    continue

                lyrics = parse_lrc(synced, source="lrclib")
                if not lyrics.is_empty and self.auto_save_fetched_lrc:
                    self._save_fetched_lrc(artist=artist, title=title, text=synced)
                return lyrics
        except requests.RequestException:
            return LyricsData(source="lrclib", lines=[])

        return LyricsData(source="lrclib", lines=[])

    @staticmethod
    def _lrclib_result_matches(
        requested_artist: str,
        requested_title: str,
        item_artist: str,
        item_title: str,
    ) -> bool:
        if normalize_match_text(item_title) != normalize_match_text(requested_title):
            return False

        normalized_requested_artist = normalize_match_text(requested_artist)
        normalized_item_artist = normalize_match_text(item_artist)
        if normalized_requested_artist == normalized_item_artist:
            return True

        requested_parts = artist_parts(requested_artist)
        item_parts = artist_parts(item_artist)
        if requested_parts and item_parts and requested_parts & item_parts:
            return True

        if normalized_requested_artist and normalized_item_artist:
            return (
                normalized_requested_artist in normalized_item_artist
                or normalized_item_artist in normalized_requested_artist
            )

        return False

    def set_lrclib_enabled(self, enabled: bool) -> None:
        self.lrclib_enabled = enabled

    def set_auto_save_fetched_lrc(self, enabled: bool) -> None:
        self.auto_save_fetched_lrc = enabled

    def clear_downloaded_cache(self) -> int:
        removed = 0
        for path in FETCHED_LRC_DIR.glob("*.lrc"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        self._cache.clear()
        return removed

    def _local_lrc_paths(self, artist: str, title: str) -> list[Path]:
        filename = f"{sanitize_filename(artist)} - {sanitize_filename(title)}.lrc"
        exact_paths = [LRC_DIR / filename, FETCHED_LRC_DIR / filename]
        paths = list(exact_paths)
        seen = {path.resolve() for path in exact_paths if path.exists()}

        for path in self._matching_local_lrc_paths(artist=artist, title=title):
            resolved = path.resolve()
            if resolved in seen:
                continue
            paths.append(path)
            seen.add(resolved)

        return paths

    def _matching_local_lrc_paths(self, artist: str, title: str) -> list[Path]:
        requested_artist = normalize_match_text(artist)
        requested_title = normalize_match_text(title)
        requested_artist_parts = artist_parts(artist)
        matches: list[tuple[int, str, Path]] = []

        if not requested_title:
            return []

        for directory in (LRC_DIR, FETCHED_LRC_DIR):
            try:
                files = list(directory.glob("*.lrc"))
            except OSError:
                continue

            for path in files:
                stem = path.stem
                if LOCAL_LRC_SEPARATOR not in stem:
                    continue

                file_artist, file_title = stem.split(LOCAL_LRC_SEPARATOR, 1)
                normalized_file_artist = normalize_match_text(file_artist)
                normalized_file_title = normalize_match_text(file_title)
                score = self._local_lrc_match_score(
                    requested_artist=requested_artist,
                    requested_artist_parts=requested_artist_parts,
                    requested_title=requested_title,
                    file_artist=normalized_file_artist,
                    file_artist_parts=artist_parts(file_artist),
                    file_title=normalized_file_title,
                )
                if score <= 0:
                    continue

                matches.append((score, path.name.casefold(), path))

        matches.sort(key=lambda match: (-match[0], match[1]))
        return [path for _, _, path in matches]

    @staticmethod
    def _local_lrc_match_score(
        requested_artist: str,
        requested_artist_parts: set[str],
        requested_title: str,
        file_artist: str,
        file_artist_parts: set[str],
        file_title: str,
    ) -> int:
        if requested_title != file_title:
            return 0

        if requested_artist == file_artist:
            return 100

        if requested_artist and file_artist:
            if requested_artist in file_artist or file_artist in requested_artist:
                return 90

        if requested_artist_parts and file_artist_parts and requested_artist_parts & file_artist_parts:
            return 80

        return 0

    def _save_fetched_lrc(self, artist: str, title: str, text: str) -> None:
        path = FETCHED_LRC_DIR / f"{sanitize_filename(artist)} - {sanitize_filename(title)}.lrc"
        try:
            path.write_text(text.strip() + "\n", encoding="utf-8")
        except OSError:
            return
