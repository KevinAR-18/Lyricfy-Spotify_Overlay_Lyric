from __future__ import annotations

from bisect import bisect_right

from .models import LyricLine, LyricsData


class SyncEngine:
    def __init__(self) -> None:
        self._lyrics = LyricsData(source="none", lines=[])
        self._timestamps: tuple[int, ...] = ()

    def set_lyrics(self, lyrics: LyricsData) -> None:
        self._lyrics = lyrics
        self._timestamps = tuple(line.timestamp_ms for line in lyrics.lines)

    def current_line(self, progress_ms: int) -> tuple[int, LyricLine | None]:
        active_index = bisect_right(self._timestamps, progress_ms) - 1
        if active_index == -1:
            return -1, None

        return active_index, self._lyrics.lines[active_index]

    def next_line(self, active_index: int) -> LyricLine | None:
        if active_index < 0:
            return self._lyrics.lines[0] if self._lyrics.lines else None

        next_index = active_index + 1
        if next_index >= len(self._lyrics.lines):
            return None

        return self._lyrics.lines[next_index]
