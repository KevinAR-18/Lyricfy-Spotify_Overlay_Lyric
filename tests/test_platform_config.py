import builtins
from dataclasses import replace
from types import SimpleNamespace

import pytest

from lyric_overlay import config, spotify_client
from lyric_overlay.platform import playback_windows, playback_macos


@pytest.mark.parametrize("value", ["local", " LOCAL ", "windows", " WINDOWS ", "", "invalid"])
def test_local_migration(value):
    assert config._normalize_playback_source(value) == "local"


def test_mac_paths_ignore_windows_environment(tmp_path):
    assert config.user_data_dir("darwin", tmp_path, "wrong-appdata") == tmp_path / "Library/Application Support/Lyricfy"
    assert config.user_data_dir("win32", tmp_path) == tmp_path / ".lyricfy"
    assert config.user_data_dir("win32", tmp_path, str(tmp_path / "Roaming")) == tmp_path / "Roaming/Lyricfy"


@pytest.mark.parametrize("frozen", [False, True])
def test_resource_paths_follow_bundle_while_source_uses_checkout(tmp_path, monkeypatch, frozen):
    checkout = tmp_path / "checkout"
    executable = tmp_path / "Applications/Lyricfy.app/Contents/MacOS/Lyricfy"
    resources = executable.parent / "_internal"
    runtime = SimpleNamespace(frozen=frozen, executable=str(executable))
    if frozen:
        runtime._MEIPASS = str(resources)
    monkeypatch.setattr(config, "sys", runtime)
    monkeypatch.setattr(config, "_repo_base_dir", lambda: checkout)
    assert config._runtime_base_dir() == (executable.parent if frozen else checkout)
    assert config._resource_dir() == (resources if frozen else checkout)
    assert config.user_data_dir("darwin", tmp_path) != executable.parent


def test_mac_font_fallback_and_shortcut_label(monkeypatch):
    from lyric_overlay import overlay
    application = overlay.create_application()
    monkeypatch.setattr(overlay, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(config, "sys", SimpleNamespace(platform="darwin"))
    system_family = application.font().family()
    assert overlay.resolved_font_family("system") == system_family
    assert overlay.resolved_font_family("Lyricfy missing font test 0123456789") == system_family
    assert overlay.resolved_font_family(system_family) == system_family
    assert ("Command+R", "Reload playback") in overlay.shortcuts_guide_lines()


@pytest.mark.parametrize("platform,backend,name", [
    ("win32", playback_windows, "WindowsMediaSpotifyClient"),
    ("darwin", playback_macos, "MacSpotifyClient"),
])
def test_factory_selects_only_local_backend(monkeypatch, platform, backend, name):
    monkeypatch.setattr(spotify_client, "sys", SimpleNamespace(platform=platform))
    sentinel = object()
    monkeypatch.setattr(backend, name, lambda: sentinel)
    for value in ("local", "windows", "", "invalid"):
        assert spotify_client.create_playback_client(value, "", "", "") is sentinel


def test_foreign_platform_api_and_unsupported_local(monkeypatch):
    monkeypatch.setattr(spotify_client, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(spotify_client, "SpotifyApiClient", lambda *args: args)
    assert spotify_client.create_playback_client("spotify_api", "id", "secret", "uri") == ("id", "secret", "uri")
    with pytest.raises(ValueError, match="supported on Windows and macOS"):
        spotify_client.create_playback_client("local", "", "", "")


def test_legacy_round_trip_preserves_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "settings.env")
    monkeypatch.setattr(config, "FALLBACK_ENV_FILE", tmp_path / "missing.env")
    original = replace(config.default_config(), playback_source="windows", spotify_client_id="example",
                       spotify_client_secret="test-only", lyric_offset_ms=234)
    config.save_config(original)
    loaded = config.load_config()
    assert loaded.playback_source == "local"
    assert loaded.spotify_client_secret == "test-only" and loaded.lyric_offset_ms == 234


def test_import_does_not_load_native_bindings(monkeypatch):
    import importlib
    actual_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith(("winsdk", "winreg"))
        return actual_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    importlib.reload(spotify_client)
