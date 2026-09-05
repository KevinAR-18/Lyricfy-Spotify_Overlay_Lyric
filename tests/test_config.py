from lyric_overlay import config as config_module
from lyric_overlay.config import (
    ALWAYS_FLOATING_COVER_MODE,
    CARD_DEFAULT_PRESET,
    CUSTOM_DISPLAY_PRESET,
    FLOATING_CONTEXT_PRESET,
    FLOATING_MINIMAL_PRESET,
    LOCAL_PLAYBACK_SOURCE,
    _normalize_display_style,
    _normalize_floating_cover_mode,
    _normalize_lyric_lines,
    _normalize_playback_source,
    _normalize_text_alignment,
    _normalize_track_info_mode,
    default_config,
    display_preset_for,
    display_preset_values,
)


class TestNormalizePlaybackSource:
    def test_valid_windows(self):
        assert _normalize_playback_source("windows") == "local"

    def test_valid_spotify_api(self):
        assert _normalize_playback_source("spotify_api") == "spotify_api"

    def test_case_and_whitespace(self):
        assert _normalize_playback_source("  SPOTIFY_API  ") == "spotify_api"

    def test_invalid_falls_back_to_local(self):
        assert _normalize_playback_source("nonsense") == LOCAL_PLAYBACK_SOURCE

    def test_empty_falls_back(self):
        assert _normalize_playback_source("") == LOCAL_PLAYBACK_SOURCE


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
        assert cfg.playback_source == LOCAL_PLAYBACK_SOURCE
        assert cfg.poll_interval_ms == 1000
        assert cfg.lrclib_enabled is True
        assert cfg.text_alignment == "left"
        assert cfg.show_album_cover is False
        assert cfg.floating_cover_mode == ALWAYS_FLOATING_COVER_MODE
        assert cfg.track_info_gap_px == 4
        assert cfg.overlay_corner_radius == 30
        assert display_preset_for(cfg) == CARD_DEFAULT_PRESET


class TestDisplayConfig:
    def test_invalid_values_fall_back_to_defaults(self):
        assert _normalize_display_style("invalid") == "card"
        assert _normalize_lyric_lines("invalid") == "single"
        assert _normalize_track_info_mode("invalid") == "track_change"
        assert _normalize_floating_cover_mode("invalid") == ALWAYS_FLOATING_COVER_MODE
        assert _normalize_floating_cover_mode("hover") == "hover"

    def test_builtin_presets(self):
        config = default_config()
        for preset in (
            CARD_DEFAULT_PRESET,
            FLOATING_MINIMAL_PRESET,
            FLOATING_CONTEXT_PRESET,
        ):
            style, lines, info = display_preset_values(preset)
            config.display_style = style
            config.lyric_lines = lines
            config.track_info_mode = info
            assert display_preset_for(config) == preset

    def test_custom_combination(self):
        config = default_config()
        config.display_style = "floating"
        config.lyric_lines = "current_next"
        config.track_info_mode = "always"
        assert display_preset_for(config) == CUSTOM_DISPLAY_PRESET


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
        original.display_style = "floating"
        original.lyric_lines = "current_next"
        original.track_info_mode = "always"
        original.show_album_cover = True
        original.floating_cover_mode = "hover"
        original.track_info_gap_px = 12
        original.overlay_corner_radius = 12

        config_module.save_config(original)
        assert env_file.exists()

        loaded = config_module.load_config()
        assert loaded.spotify_client_id == "abc123"
        assert loaded.lyric_offset_ms == -250
        assert loaded.text_alignment == "center"
        assert loaded.lrclib_enabled is False
        assert loaded.autostart_enabled is True
        assert loaded.playback_source == original.playback_source
        assert loaded.display_style == "floating"
        assert loaded.lyric_lines == "current_next"
        assert loaded.track_info_mode == "always"
        assert loaded.show_album_cover is True
        assert loaded.floating_cover_mode == "hover"
        assert loaded.track_info_gap_px == 12
        assert loaded.overlay_corner_radius == 12

    def test_corner_radius_is_clamped(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        monkeypatch.setattr(config_module, "ENV_FILE", env_file)
        monkeypatch.setattr(config_module, "FALLBACK_ENV_FILE", tmp_path / "missing.env")
        env_file.write_text("OVERLAY_CORNER_RADIUS=99\n", encoding="utf-8")
        assert config_module.load_config().overlay_corner_radius == 40

    def test_track_info_gap_is_clamped(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        monkeypatch.setattr(config_module, "ENV_FILE", env_file)
        monkeypatch.setattr(config_module, "FALLBACK_ENV_FILE", tmp_path / "missing.env")
        env_file.write_text("TRACK_INFO_GAP_PX=99\n", encoding="utf-8")
        assert config_module.load_config().track_info_gap_px == 24
