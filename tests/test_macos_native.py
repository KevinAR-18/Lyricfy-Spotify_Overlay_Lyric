"""No Spotify/TCC dependency: verify the shipped script on a native Mac runner."""
import json
import subprocess
import sys

import pytest

from lyric_overlay.platform.playback_macos import SCRIPT_FILE

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Native macOS scripting runtime")


def test_script_when_spotify_is_closed():
    running = subprocess.run(["/usr/bin/pgrep", "-x", "Spotify"], capture_output=True, timeout=3)
    if running.returncode == 0:
        pytest.skip("Close Spotify to test absence without triggering Automation")
    assert running.returncode == 1, "Could not determine whether Spotify is running"
    result = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", str(SCRIPT_FILE)],
                            capture_output=True, timeout=5, check=True)
    snapshot = json.loads(result.stdout)
    assert snapshot == {"version": 1, "status": "not_running"}
    after = subprocess.run(["/usr/bin/pgrep", "-x", "Spotify"], capture_output=True, timeout=3)
    assert after.returncode == 1, "The snapshot query must not launch Spotify"
