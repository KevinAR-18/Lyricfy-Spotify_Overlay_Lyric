import os
import plistlib
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lyric_overlay import main as entry
from lyric_overlay.config import default_config
from lyric_overlay.platform import AutostartResult
from lyric_overlay.platform import autostart_macos as mac, autostart_windows as windows


@pytest.fixture
def mac_environment(tmp_path, monkeypatch):
    bundle = tmp_path / "Applications" / "Lyricfy.app"
    bundle.mkdir(parents=True)
    monkeypatch.setattr(mac.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mac, "_current_bundle", lambda home: bundle)
    monkeypatch.setattr(mac.os, "getuid", lambda: 501, raising=False)
    runner = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(mac.subprocess, "run", runner)
    return tmp_path, bundle, runner


def test_install_detection_requires_a_stable_packaged_location(tmp_path):
    home, system = tmp_path / "user", tmp_path / "Applications"
    executable = system / "Lyricfy.app/Contents/MacOS/Lyricfy"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert mac.installed_bundle(executable, True, home, system) == system / "Lyricfy.app"
    assert mac.installed_bundle(executable, False, home, system) is None
    elsewhere = tmp_path / "Volumes/DMG/Lyricfy.app/Contents/MacOS/Lyricfy"
    elsewhere.parent.mkdir(parents=True)
    assert mac.installed_bundle(elsewhere, True, home, system) is None


def test_enable_update_disable_are_idempotent_and_do_not_launch(mac_environment):
    home, bundle, runner = mac_environment
    other = home / "Library/LaunchAgents/other.plist"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"unrelated")
    for _ in range(2):
        assert mac.set_autostart(True, True).success
    path = mac.launch_agent_path(home)
    data = plistlib.loads(path.read_bytes())
    assert data["ProgramArguments"] == ["/usr/bin/open", "-g", "-a", str(bundle), "--args", "--start-hidden"]
    assert data["RunAtLoad"] is True and not data.get("KeepAlive")
    runner.assert_not_called()
    assert mac.get_autostart_status().registered
    assert mac.set_autostart(True, False).success
    assert "--start-hidden" not in plistlib.loads(path.read_bytes())["ProgramArguments"]
    assert mac.set_autostart(False, False).success
    runner.return_value.returncode = 3
    assert mac.set_autostart(False, False).success
    assert not path.exists() and other.read_bytes() == b"unrelated"
    assert runner.call_args.args[0] == ["/bin/launchctl", "bootout", "gui/501/com.lyricfy.overlay"]


def test_launchctl_failure_preserves_existing_registration(mac_environment):
    home, _, runner = mac_environment
    mac.set_autostart(True, False)
    path = mac.launch_agent_path(home)
    original = path.read_bytes()
    runner.return_value.returncode = 1
    assert not mac.set_autostart(False, False).success
    assert path.read_bytes() == original


def test_failed_atomic_write_preserves_previous_plist(mac_environment, monkeypatch):
    home, _, _ = mac_environment
    mac.set_autostart(True, False)
    path = mac.launch_agent_path(home)
    original = path.read_bytes()
    monkeypatch.setattr(mac.Path, "replace", Mock(side_effect=PermissionError("test failure")))
    with pytest.raises(PermissionError):
        mac.set_autostart(True, True)
    assert path.read_bytes() == original
    assert list(path.parent.glob(".com.lyricfy.overlay-*")) == []


def test_source_build_cannot_enable_but_can_remove_existing_job(mac_environment, monkeypatch):
    home, _, _ = mac_environment
    mac.set_autostart(True, False)
    monkeypatch.setattr(mac, "_current_bundle", lambda home: None)
    assert not mac.set_autostart(True, False).success
    assert mac.get_autostart_status().registered
    assert mac.set_autostart(False, False).success
    assert not mac.get_autostart_status().supported


def test_windows_command_retains_spaces_and_hidden_argument():
    assert windows.startup_command(r"C:\Program Files\Lyricfy.exe", "unused", True, True) == '"C:\\Program Files\\Lyricfy.exe" --start-hidden'
    assert windows.startup_command("python.exe", "project space/main.py", False, False) == '"python.exe" "project space/main.py"'


def test_registry_errors_are_reported(monkeypatch):
    registry = SimpleNamespace(CreateKeyEx=Mock(side_effect=PermissionError()), HKEY_CURRENT_USER=1, KEY_SET_VALUE=2)
    monkeypatch.setitem(__import__("sys").modules, "winreg", registry)
    assert not windows.set_autostart(True, True).success


def test_settings_failure_does_not_fake_success_or_discard_other_changes(monkeypatch):
    original = default_config()
    updated = replace(original, autostart_enabled=True, lyric_offset_ms=400)
    saved = []
    monkeypatch.setattr(entry, "set_autostart", lambda *args: AutostartResult(False, "Registration failed"))
    monkeypatch.setattr(entry, "save_config", saved.append)
    result, message = entry.persist_settings(original, updated)
    assert not result.autostart_enabled and result.lyric_offset_ms == 400
    assert message == "Registration failed" and saved == [result]


def test_no_startup_rewrite_when_only_unrelated_setting_changes(monkeypatch):
    original = default_config()
    operation = Mock()
    monkeypatch.setattr(entry, "set_autostart", operation)
    monkeypatch.setattr(entry, "save_config", Mock())
    entry.persist_settings(original, replace(original, lyric_offset_ms=250))
    operation.assert_not_called()


def test_config_write_failure_rolls_back_startup(monkeypatch):
    original = default_config()
    operation = Mock(return_value=AutostartResult(True))
    monkeypatch.setattr(entry, "set_autostart", operation)
    monkeypatch.setattr(entry, "save_config", Mock(side_effect=PermissionError()))
    result, message = entry.persist_settings(original, replace(original, autostart_enabled=True))
    assert result == original and "could not be saved" in message
    assert [call.args for call in operation.call_args_list] == [(True, False), (False, False)]
