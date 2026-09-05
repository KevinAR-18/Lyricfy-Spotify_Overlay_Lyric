import json
import subprocess
import threading

import pytest

from lyric_overlay.platform.playback_macos import (
    AUTHORIZATION_TIMEOUT_SECONDS, QUERY_TIMEOUT_SECONDS, MAX_SNAPSHOT_BYTES,
    AutomationPermissionError, MacSpotifyClient, PlaybackCancelled, parse_snapshot,
)


def snapshot(**overrides):
    track = dict(id="spotify:track:example", title='Title "quoted"\n\\\t日本語 🎵',
                 artist="Artist", album="Album", duration_ms=200000,
                 position_seconds=1.25, is_playing=True, artwork_url="https://example.org/art.jpg")
    track.update(overrides)
    return json.dumps(dict(version=1, status="ok", track=track), ensure_ascii=False).encode()


def test_snapshot_preserves_metadata_and_units():
    track = parse_snapshot(snapshot())
    assert track.progress_ms == 1250
    assert track.duration_ms == 200000
    assert track.title == 'Title "quoted"\n\\\t日本語 🎵'
    assert track.cover_url == "https://example.org/art.jpg"
    assert track.is_playing


@pytest.mark.parametrize("status", ["not_running", "no_track", "changed"])
def test_absent_states(status):
    assert parse_snapshot(json.dumps(dict(version=1, status=status))) is None


@pytest.mark.parametrize("field,value", [
    ("title", 12), ("is_playing", "false"), ("is_playing", None),
    ("duration_ms", float("nan")), ("position_seconds", float("inf")),
    ("position_seconds", True), ("position_seconds", "1.2"),
])
def test_malformed_fields_rejected(field, value):
    with pytest.raises(ValueError):
        parse_snapshot(snapshot(**{field: value}))


@pytest.mark.parametrize("raw", [b"not json", b"[]", b"{}", b"\xff", b"x" * (MAX_SNAPSHOT_BYTES + 1),
                                   b'{"version":true,"status":"no_track"}'],
                         ids=["malformed", "array", "empty-object", "invalid-utf8", "oversized", "invalid-version"])
def test_bad_payload_rejected(raw):
    with pytest.raises((ValueError, UnicodeError)):
        parse_snapshot(raw)


def test_paused_optional_metadata_and_clamping():
    track = parse_snapshot(snapshot(is_playing=False, artist=None, album=None,
                                    artwork_url=None, position_seconds=1000))
    assert not track.is_playing
    assert track.progress_ms == track.duration_ms
    assert track.artist == "Unknown artist" and track.cover_url is None
    assert parse_snapshot(snapshot(position_seconds=-10)).progress_ms == 0
    assert parse_snapshot(snapshot(duration_ms=None)).duration_ms == 0
    assert parse_snapshot(snapshot(title=" ")) is None


def test_fallback_identity_is_stable_and_namespaced():
    first = parse_snapshot(snapshot(id="", title=" Song ", artist="ARTIST"))
    second = parse_snapshot(snapshot(id=None, title="song", artist="artist", position_seconds=99,
                                     is_playing=False, artwork_url=None))
    assert first.track_id == second.track_id
    assert first.track_id.startswith("macos:local:")
    assert parse_snapshot(snapshot(id="", album="Other")).track_id != first.track_id


class Process:
    def __init__(self, raw, options, *, timeout=False):
        options["stdout"].write(raw)
        self.returncode = None
        self.timeout = timeout
        self.killed = False
        self.waits = []

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.timeout and not self.killed:
            raise subprocess.TimeoutExpired("osascript", timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def test_client_command_and_first_authorization_deadline():
    processes, calls = [], []
    def factory(args, **kwargs):
        calls.append((args, kwargs))
        process = Process(snapshot(), kwargs)
        processes.append(process)
        return process
    client = MacSpotifyClient(process_factory=factory)
    client.get_current_track()
    client.get_current_track()
    assert calls[0][0][:3] == ["/usr/bin/osascript", "-l", "JavaScript"]
    assert calls[0][1]["shell"] is False
    assert processes[0].waits == [AUTHORIZATION_TIMEOUT_SECONDS]
    assert processes[1].waits == [QUERY_TIMEOUT_SECONDS]


def test_denial_does_not_spawn_again_until_new_connection():
    calls = []
    def factory(args, **kwargs):
        calls.append(args)
        return Process(b'{"version":1,"status":"permission_denied"}', kwargs)
    client = MacSpotifyClient(process_factory=factory)
    for _ in range(2):
        with pytest.raises(AutomationPermissionError):
            client.get_current_track()
    assert len(calls) == 1


def test_timeout_kills_and_reaps_child():
    processes = []
    def factory(args, **kwargs):
        process = Process(snapshot(), kwargs, timeout=True)
        processes.append(process)
        return process
    client = MacSpotifyClient(process_factory=factory)
    with pytest.raises(AutomationPermissionError, match="timed out"):
        client.get_current_track()
    assert processes[0].killed
    assert processes[0].waits == [30, None]
    assert client._process is None


def test_cancellation_reaps_pending_process():
    entered, killed = threading.Event(), threading.Event()
    failures = []
    class BlockingProcess(Process):
        def wait(self, timeout=None):
            entered.set()
            assert killed.wait(3)
            return self.returncode
        def kill(self):
            super().kill()
            killed.set()
    client = MacSpotifyClient(process_factory=lambda args, **kwargs: BlockingProcess(snapshot(), kwargs))
    def query():
        try:
            client.get_current_track()
        except Exception as exc:
            failures.append(exc)
    thread = threading.Thread(target=query)
    thread.start()
    try:
        assert entered.wait(2)
        client.cancel()
    finally:
        killed.set()
        thread.join(2)
    assert not thread.is_alive()
    assert isinstance(failures[0], PlaybackCancelled)
    assert client._process is None
