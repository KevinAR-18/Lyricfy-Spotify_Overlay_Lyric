import sys
import asyncio
import pytest

if sys.platform != "win32":
    pytest.skip("Requires Windows WinRT", allow_module_level=True)

from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream, RandomAccessStreamReference
from lyric_overlay.platform.playback_windows import WindowsMediaSpotifyClient


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
