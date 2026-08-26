import asyncio

from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream, RandomAccessStreamReference

from lyric_overlay.spotify_client import WindowsMediaSpotifyClient, stable_windows_track_id


class TestStableWindowsTrackId:
    def test_normalizes_case_and_whitespace(self):
        a = stable_windows_track_id("Spotify.exe", "  Cold Play ", "Yellow", 267000)
        b = stable_windows_track_id("Spotify.exe", "cold play", "yellow", 267000)
        assert a == b

    def test_duration_rounded_to_seconds(self):
        a = stable_windows_track_id("Spotify.exe", "A", "B", 267400)
        b = stable_windows_track_id("Spotify.exe", "A", "B", 267000)
        assert a == b

    def test_duration_rounds_up(self):
        track_id = stable_windows_track_id("app", "a", "b", 1600)
        assert track_id.endswith(":2")

    def test_zero_duration(self):
        track_id = stable_windows_track_id("app", "a", "b", 0)
        assert track_id.endswith(":0")

    def test_different_titles_differ(self):
        a = stable_windows_track_id("app", "artist", "title1", 1000)
        b = stable_windows_track_id("app", "artist", "title2", 1000)
        assert a != b

    def test_format_structure(self):
        track_id = stable_windows_track_id("Spotify.exe", "Coldplay", "Yellow", 267000)
        assert track_id == "Spotify.exe:coldplay:yellow:267"


def test_windows_thumbnail_stream_is_read_as_bytes():
    async def read_thumbnail():
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(b"cover-data")
        await writer.store_async()
        writer.detach_stream()
        writer.close()
        thumbnail = RandomAccessStreamReference.create_from_stream(stream)
        return await WindowsMediaSpotifyClient._read_thumbnail_bytes(thumbnail)

    assert asyncio.run(read_thumbnail()) == b"cover-data"
