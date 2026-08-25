from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TrackInfo:
    track_id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    progress_ms: int
    is_playing: bool
    cover_url: str | None = None
    cover_data: bytes | None = None


@dataclass(slots=True)
class LyricLine:
    timestamp_ms: int
    text: str


@dataclass(slots=True)
class LyricsData:
    source: str
    lines: list[LyricLine] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.lines) == 0
