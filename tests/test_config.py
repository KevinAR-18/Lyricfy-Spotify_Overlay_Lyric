import importlib

from lyric_overlay import config as config_module
from lyric_overlay.config import (
    WINDOWS_PLAYBACK_SOURCE,
    _normalize_playback_source,
    _normalize_text_alignment,
    default_config,
)


class TestNormalizePlaybackSource:
    def test_valid_windows(self):
        assert _normalize_playback_source("windows") == "windows"

    def test_valid_spotify_api(self):
        assert _normalize_playback_source("spotify_api") == "spotify_api"

    def test_case_and_whitespace(self):
        assert _normalize_playback_source("  SPOTIFY_API  ") == "spotify_api"

    def test_invalid_falls_back_to_windows(self):
        assert _normalize_playback_source("nonsense") == WINDOWS_PLAYBACK_SOURCE

    def test_empty_falls_back(self):
        assert _normalize_playback_source("") == WINDOWS_PLAYBACK_SOURCE


class TestNormalizeTextAlignment:
    def test_valid_values(self):
        assert _normalize_text_alignment("center") == "center"
        assert _normalize_text_alignment("right") == "right"

    def test_case_insensitive(self):
        assert _normalize_text_alignment("LEFT") == "left"

    def test_invalid_falls_back_to_left(self):
        assert _normalize_text_alignment("justified") == "left"


class TestDefaultConfig:
    def test_defaults_are_sane(self):
        cfg = default_config()
        assert cfg.playback_source == WINDOWS_PLAYBACK_SOURCE
        assert cfg.poll_interval_ms == 1000
        assert cfg.lrclib_enabled is True
        assert cfg.text_alignment == "left"


class TestSaveLoadRoundTrip:
    def test_round_trip(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        monkeypatch.setattr(config_module, "ENV_FILE", env_file)
        monkeypatch.setattr(config_module, "FALLBACK_ENV_FILE", tmp_path / "nonexistent.env")

        original = default_config()
        original.spotify_client_id = "abc123"
        original.lyric_offset_ms = -250
        original.text_alignment = "center"
        original.lrclib_enabled = False
        original.autostart_enabled = True

        config_module.save_config(original)
        assert env_file.exists()

        loaded = config_module.load_config()
        assert loaded.spotify_client_id == "abc123"
        assert loaded.lyric_offset_ms == -250
        assert loaded.text_alignment == "center"
        assert loaded.lrclib_enabled is False
        assert loaded.autostart_enabled is True
        assert loaded.playback_source == original.playback_source
