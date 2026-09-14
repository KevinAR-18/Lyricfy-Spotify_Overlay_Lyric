from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lyric_overlay.app_controller import AppController
from lyric_overlay import __version__
from lyric_overlay.config import (
    AppConfig, ICON_FILE, SPOTIFY_API_PLAYBACK_SOURCE, ensure_directories,
    ensure_env_file, load_config, save_config,
)
from lyric_overlay.lyrics import LyricsRepository
from lyric_overlay.overlay import OverlayWindow, create_application
from lyric_overlay.spotify_client import PlaybackClient, create_playback_client

APP_NAME = "Lyricfy"
START_HIDDEN_ARG = "--start-hidden"


def build_playback_client(config: AppConfig) -> tuple[PlaybackClient | None, str | None]:
    try:
        return create_playback_client(
            playback_source=config.playback_source,
            client_id=config.spotify_client_id,
            client_secret=config.spotify_client_secret,
            redirect_uri=config.spotify_redirect_uri,
        ), None
    except (RuntimeError, ValueError) as exc:
        return None, str(exc)


def qt_message_handler(mode, context, message) -> None:
    del context
    if mode == QtMsgType.QtWarningMsg and "QWindowsWindow::setGeometry" in message:
        return
    print(message, flush=True)


def playback_startup_lines(playback_source: str, error_message: str | None = None) -> tuple[str, str]:
    if playback_source == SPOTIFY_API_PLAYBACK_SOURCE:
        return "Open Settings and fill Spotify API credentials", error_message or "Then press Ctrl+R to retry"
    return "Open Spotify desktop and start playback", error_message or "Then press Ctrl+R to retry"


def set_windows_autostart(enabled: bool, start_hidden: bool) -> None:
    try:
        import winreg
    except ImportError:
        return
    command = f'"{sys.executable}"'
    if not getattr(sys, "frozen", False):
        command += f' "{Path(sys.argv[0]).resolve()}"'
    if start_hidden:
        command += f" {START_HIDDEN_ARG}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


class SettingsCoordinator:
    """One persistence/reconnection path shared by all settings tabs."""

    def __init__(self, overlay, controller, cinematic):
        self.overlay = overlay
        self.controller = controller
        self.cinematic = cinematic
        overlay.save_requested.connect(self.save)
        overlay.reconnect_requested.connect(self.reconnect)
        controller.playback_error.connect(overlay.playback_status.setText)

    def save(self, config):
        old = self.controller.config
        playback_fields = ("playback_source", "spotify_client_id", "spotify_client_secret", "spotify_redirect_uri", "poll_interval_ms")
        reconnect = any(getattr(old, name) != getattr(config, name) for name in playback_fields)
        try:
            if config.cinematic_enabled:
                self.cinematic.ensure_window()
            save_config(config)
        except (OSError, RuntimeError, ValueError) as exc:
            self.overlay.settings_feedback.setText(f"Could not save settings: {exc}")
            return
        set_windows_autostart(config.autostart_enabled, config.autostart_start_hidden)
        self.controller.config = config
        self.overlay.load_config_values(config)
        self.cinematic.sync_config(config)
        self.controller.lyrics_repository.set_lrclib_enabled(config.lrclib_enabled)
        self.controller.lyrics_repository.set_auto_save_fetched_lrc(config.auto_save_fetched_lrc)
        self.controller.refresh_album_cover()
        self.overlay.settings_feedback.setText("Settings saved")
        if reconnect:
            self.reconnect()
        if self.overlay._expanded:
            if config.cinematic_enabled:
                self.cinematic.ensure_window().show_from_tray()
            elif self.cinematic.window:
                self.cinematic.window.hide()
            self.overlay.raise_()

    def reconnect(self):
        config = self.controller.config
        self.overlay.playback_status.setText("Connecting to playback…")
        client, error = build_playback_client(config)
        self.controller.reconnect(client, config, unavailable_message=error)
        self.overlay.playback_status.setText(error or "Playback client ready — waiting for Spotify playback")


def create_tray_menu(overlay, controller, cinematic, quit_callback):
    menu = QMenu()
    menu.addAction("Show Overlay", cinematic.show)
    menu.addAction("Hide Overlay", cinematic.hide)
    menu.addAction("Reset Position", cinematic.snap_home)
    menu.addSeparator()
    presentation = QMenu("Presentation", menu)
    menu.addMenu(presentation)
    presentation_group = QActionGroup(presentation)
    presentation_group.setExclusive(True)
    presentation_actions = {}
    for enabled, label in ((False, "Classic"), (True, "Cinematic")):
        action = QAction(label, presentation_group)
        action.setCheckable(True)
        action.triggered.connect(lambda checked, value=enabled: cinematic.set_enabled(value) if checked else None)
        presentation.addAction(action)
        presentation_actions[enabled] = action
    startup = QMenu("Startup", menu)
    menu.addMenu(startup)
    auto = startup.addAction("Auto Start with Windows")
    auto.setCheckable(True)
    startup.addSeparator()
    startup_group = QActionGroup(startup)
    startup_group.setExclusive(True)
    startup_actions = {}

    def startup_changed(**updates):
        config = replace(controller.config, **updates)
        try:
            save_config(config)
        except OSError as exc:
            overlay.show_status(f"Could not save startup preferences: {exc}")
            sync()
            return
        set_windows_autostart(config.autostart_enabled, config.autostart_start_hidden)
        controller.config = config
        overlay.sync_external_preferences(**updates)
        sync()

    auto.triggered.connect(lambda checked: startup_changed(autostart_enabled=checked))
    for hidden, label in ((False, "Show Overlay"), (True, "Start Hidden")):
        action = QAction(label, startup_group)
        action.setCheckable(True)
        action.triggered.connect(lambda checked, value=hidden: startup_changed(autostart_start_hidden=value) if checked else None)
        startup.addAction(action)
        startup_actions[hidden] = action
    menu.addAction("Settings…", overlay.open_settings_from_tray)
    menu.addSeparator()
    version = menu.addAction(f"Lyricfy v{__version__}")
    version.setEnabled(False)
    menu.addSeparator()
    menu.addAction("Exit Lyricfy", quit_callback)

    def sync(*args):
        config = controller.config
        presentation_actions[config.cinematic_enabled].setChecked(True)
        auto.setChecked(config.autostart_enabled)
        startup_actions[config.autostart_start_hidden].setChecked(True)
        for action in startup_actions.values():
            action.setEnabled(config.autostart_enabled)

    menu.aboutToShow.connect(sync)
    cinematic.modeChanged.connect(sync)
    sync()
    return menu


def main() -> int:
    if "--cinematic-demo" in sys.argv:
        from lyric_overlay.cinematic.demo import run_demo
        return run_demo()
    qInstallMessageHandler(qt_message_handler)
    ensure_directories()
    ensure_env_file()
    config = load_config()
    set_windows_autostart(config.autostart_enabled, config.autostart_start_hidden)
    app = create_application()
    app.setApplicationName(APP_NAME)
    if ICON_FILE.exists():
        app.setWindowIcon(QIcon(str(ICON_FILE)))
    overlay = OverlayWindow()
    overlay.load_config_values(config)
    controller = AppController(None, LyricsRepository(
        lrclib_enabled=config.lrclib_enabled,
        auto_save_fetched_lrc=config.auto_save_fetched_lrc,
    ), overlay, config)
    from lyric_overlay.cinematic.manager import CinematicManager
    cinematic = CinematicManager(overlay, controller, app)
    coordinator = SettingsCoordinator(overlay, controller, cinematic)

    tray = None

    def quit_app():
        overlay.allow_exit()
        overlay.close()
        if tray:
            tray.hide()
        app.quit()

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(app)
        if ICON_FILE.exists():
            tray.setIcon(QIcon(str(ICON_FILE)))
        tray.setToolTip(APP_NAME)
        tray_menu = create_tray_menu(overlay, controller, cinematic, quit_app)
        tray.setContextMenu(tray_menu)
        tray.activated.connect(lambda reason: cinematic.show() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()

    def toggle_color(updated):
        config = replace(controller.config, lyric_text_color=updated.lyric_text_color)
        save_config(config)
        controller.config = config
        overlay.sync_external_preferences(lyric_text_color=config.lyric_text_color)

    def clear_cache():
        count = controller.lyrics_repository.clear_downloaded_cache()
        overlay.settings_feedback.setText(f"Cleared {count} downloaded lyric files" if count else "No downloaded lyric cache to clear")

    overlay.lyric_color_toggle_requested.connect(toggle_color)
    overlay.clear_lyrics_cache_requested.connect(clear_cache)
    overlay.overlay_hidden.connect(cinematic.pause_if_hidden)
    overlay.overlay_shown.connect(controller.resume_polling)
    app.aboutToQuit.connect(controller.stop)
    app.aboutToQuit.connect(cinematic.shutdown)
    overlay.set_track(None)
    overlay.set_lines("Starting Lyricfy…", "Connecting to Spotify playback")
    if START_HIDDEN_ARG in sys.argv and tray is not None:
        overlay.hide_to_tray()
    else:
        cinematic.show()
    QTimer.singleShot(0, coordinator.reconnect)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
