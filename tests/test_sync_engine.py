from lyric_overlay.models import LyricLine, LyricsData
from lyric_overlay.sync_engine import SyncEngine


def _engine(*timestamps):
    lyrics = LyricsData(
        source="test",
        lines=[LyricLine(timestamp_ms=ts, text=f"line@{ts}") for ts in timestamps],
    )
    engine = SyncEngine()
    engine.set_lyrics(lyrics)
    return engine


class TestCurrentLine:
    def test_empty_lyrics_returns_none(self):
        engine = SyncEngine()
        assert engine.current_line(1000) == (-1, None)

    def test_before_first_timestamp_returns_none(self):
        engine = _engine(1000, 2000)
        assert engine.current_line(500) == (-1, None)

    def test_exact_boundary_is_active(self):
        engine = _engine(1000, 2000)
        index, line = engine.current_line(1000)
        assert index == 0
        assert line.timestamp_ms == 1000

    def test_between_lines_returns_earlier(self):
        engine = _engine(1000, 2000, 3000)
        index, line = engine.current_line(2500)
        assert index == 1
        assert line.timestamp_ms == 2000

    def test_after_last_timestamp_returns_last(self):
        engine = _engine(1000, 2000)
        index, line = engine.current_line(9999)
        assert index == 1
        assert line.timestamp_ms == 2000


class TestNextLine:
    def test_next_after_active(self):
        engine = _engine(1000, 2000, 3000)
        nxt = engine.next_line(0)
        assert nxt.timestamp_ms == 2000

    def test_next_when_no_active_returns_first(self):
        engine = _engine(1000, 2000)
        nxt = engine.next_line(-1)
        assert nxt.timestamp_ms == 1000

    def test_next_past_end_returns_none(self):
        engine = _engine(1000, 2000)
        assert engine.next_line(1) is None

    def test_next_when_empty_returns_none(self):
        engine = SyncEngine()
        assert engine.next_line(-1) is None
