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

    def test_duplicate_timestamps_and_backward_seek(self):
        engine = _engine(1000, 2000, 2000, 3000)
        assert engine.current_line(3000)[0] == 3
        assert engine.current_line(2000)[0] == 2
        assert engine.current_line(1999)[0] == 0
        assert engine.current_line(999) == (-1, None)

    def test_replacing_lyrics_rebuilds_timestamp_index(self):
        engine = _engine(1000, 2000, 3000)
        replacement = LyricLine(5000, "New track")
        engine.set_lyrics(LyricsData(source="test", lines=[replacement]))
        assert engine.current_line(3000) == (-1, None)
        assert engine.current_line(5000) == (0, replacement)
        engine.set_lyrics(LyricsData(source="none", lines=[]))
        assert engine.current_line(5000) == (-1, None)


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
