from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.config import (
        AppConfig,
        ICON_FILE,
        SPOTIFY_API_PLAYBACK_SOURCE,
        WINDOWS_PLAYBACK_SOURCE,
        ensure_directories,
        ensure_env_file,
        load_config,
        save_config,
    )
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.overlay import OverlayWindow, create_application
    from lyric_overlay.spotify_client import PlaybackClient, create_playback_client
else:
    from .app_controller import AppController
    from .config import (
        AppConfig,
        ICON_FILE,
        SPOTIFY_API_PLAYBACK_SOURCE,
        WINDOWS_PLAYBACK_SOURCE,
        ensure_directories,
        ensure_env_file,
        load_config,
        save_config,
    )
    from .lyrics import LyricsRepository
    from .overlay import OverlayWindow, create_application
    from .spotify_client import PlaybackClient, create_playback_client


def build_playback_client(config: AppConfig) -> tuple[PlaybackClient | None, str | None]:
    try:
        return (
            create_playback_client(
                playback_source=config.playback_source,
                client_id=config.spotify_client_id,
                client_secret=config.spotify_client_secret,
                redirect_uri=config.spotify_redirect_uri,
            ),
            None,
        )
    except (RuntimeError, ValueError) as exc:
        return None, str(exc)


def qt_message_handler(mode, context, message) -> None:
    del context
    if mode == QtMsgType.QtWarningMsg and "QWindowsWindow::setGeometry" in message:
        return
    print(message, flush=True)


def playback_startup_lines(playback_source: str, error_message: str | None = None) -> tuple[str, str]:
    if playback_source == SPOTIFY_API_PLAYBACK_SOURCE:
        return (
            "Open Settings and fill Spotify API credentials",
            error_message or "Then press Ctrl+R to retry",
        )
    return (
        "Open Spotify desktop and start playback",
        error_message or "Then press Ctrl+R to retry",
    )


def main() -> int:
    qInstallMessageHandler(qt_message_handler)
    ensure_directories()
    ensure_env_file()
    config = load_config()

    app = create_application()
    app.setApplicationName("Lyricfy")
    icon_path = ICON_FILE
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    overlay = OverlayWindow()
    if icon_path.exists():
        overlay.setWindowIcon(QIcon(str(icon_path)))
    overlay.load_config_values(config)

    def merge_config(base_config: AppConfig, updates: AppConfig) -> AppConfig:
        return AppConfig(
            playback_source=updates.playback_source,
            spotify_client_id=updates.spotify_client_id,
            spotify_client_secret=updates.spotify_client_secret,
            spotify_redirect_uri=updates.spotify_redirect_uri or "http://127.0.0.1:8888/callback",
            poll_interval_ms=base_config.poll_interval_ms,
            lrclib_enabled=base_config.lrclib_enabled,
            auto_save_fetched_lrc=updates.auto_save_fetched_lrc,
            lyric_offset_ms=updates.lyric_offset_ms,
            overlay_bg_color=updates.overlay_bg_color or base_config.overlay_bg_color,
            overlay_text_color=updates.overlay_text_color or base_config.overlay_text_color,
            lyric_text_color=updates.lyric_text_color or base_config.lyric_text_color,
            lyric_glow_color=updates.lyric_glow_color or base_config.lyric_glow_color,
            lyric_font_family=updates.lyric_font_family or base_config.lyric_font_family,
            lyric_font_size=updates.lyric_font_size or base_config.lyric_font_size,
            text_alignment=updates.text_alignment or base_config.text_alignment,
            show_settings_button=updates.show_settings_button,
            show_hide_button=updates.show_hide_button,
        )

    mode_windows_action = None
    mode_api_action = None
    show_settings_button_action = None
    show_hide_button_action = None

    def sync_mode_actions(playback_source: str) -> None:
        normalized = playback_source or WINDOWS_PLAYBACK_SOURCE
        if mode_windows_action is not None:
            mode_windows_action.setChecked(normalized == WINDOWS_PLAYBACK_SOURCE)
        if mode_api_action is not None:
            mode_api_action.setChecked(normalized == SPOTIFY_API_PLAYBACK_SOURCE)

    def sync_overlay_button_actions(config: AppConfig) -> None:
        if show_settings_button_action is not None:
            show_settings_button_action.setChecked(config.show_settings_button)
        if show_hide_button_action is not None:
            show_hide_button_action.setChecked(config.show_hide_button)

    tray_icon = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray_icon = QSystemTrayIcon(app)
        if icon_path.exists():
            tray_icon.setIcon(QIcon(str(icon_path)))
        tray_icon.setToolTip("Lyricfy")

        tray_menu = QMenu()
        show_action = QAction("Show Overlay", tray_menu)
        hide_action = QAction("Hide Overlay", tray_menu)
        settings_action = QAction("Open Settings", tray_menu)
        mode_menu = QMenu("Mode", tray_menu)
        overlay_buttons_menu = QMenu("Overlay Buttons", tray_menu)
        mode_group = QActionGroup(mode_menu)
        mode_group.setExclusive(True)
        mode_windows_action = QAction("Non-API", mode_group)
        mode_windows_action.setCheckable(True)
        mode_api_action = QAction("API", mode_group)
        mode_api_action.setCheckable(True)
        mode_menu.addAction(mode_windows_action)
        mode_menu.addAction(mode_api_action)
        show_settings_button_action = QAction("Show Settings Button", overlay_buttons_menu)
        show_settings_button_action.setCheckable(True)
        show_hide_button_action = QAction("Show Hide Button", overlay_buttons_menu)
        show_hide_button_action.setCheckable(True)
        overlay_buttons_menu.addAction(show_settings_button_action)
        overlay_buttons_menu.addAction(show_hide_button_action)
        exit_action = QAction("Exit", tray_menu)
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(settings_action)
        tray_menu.addMenu(mode_menu)
        tray_menu.addMenu(overlay_buttons_menu)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        tray_icon.setContextMenu(tray_menu)

        def show_overlay() -> None:
            overlay.show_from_tray()

        def hide_overlay() -> None:
            overlay.hide_to_tray()

        def open_settings() -> None:
            overlay.open_settings_from_tray()

        def apply_playback_source(playback_source: str) -> None:
            base_config = load_config()
            updated_config = AppConfig(
                playback_source=playback_source,
                spotify_client_id=base_config.spotify_client_id,
                spotify_client_secret=base_config.spotify_client_secret,
                spotify_redirect_uri=base_config.spotify_redirect_uri,
                poll_interval_ms=base_config.poll_interval_ms,
                lrclib_enabled=base_config.lrclib_enabled,
                auto_save_fetched_lrc=base_config.auto_save_fetched_lrc,
                lyric_offset_ms=base_config.lyric_offset_ms,
                overlay_bg_color=base_config.overlay_bg_color,
                overlay_text_color=base_config.overlay_text_color,
                lyric_text_color=base_config.lyric_text_color,
                lyric_glow_color=base_config.lyric_glow_color,
                lyric_font_family=base_config.lyric_font_family,
                lyric_font_size=base_config.lyric_font_size,
                text_alignment=base_config.text_alignment,
                show_settings_button=base_config.show_settings_button,
                show_hide_button=base_config.show_hide_button,
            )
            save_config(updated_config)
            overlay.load_config_values(updated_config)
            controller.config = updated_config
            sync_mode_actions(updated_config.playback_source)
            sync_overlay_button_actions(updated_config)
            overlay.show_status(
                "Mode changed to API playback"
                if playback_source == SPOTIFY_API_PLAYBACK_SOURCE
                else "Mode changed to non-API playback"
            )
            reconnect_spotify()

        def apply_overlay_button_visibility(
            *,
            show_settings_button: bool | None = None,
            show_hide_button: bool | None = None,
        ) -> None:
            base_config = load_config()
            updated_config = AppConfig(
                playback_source=base_config.playback_source,
                spotify_client_id=base_config.spotify_client_id,
                spotify_client_secret=base_config.spotify_client_secret,
                spotify_redirect_uri=base_config.spotify_redirect_uri,
                poll_interval_ms=base_config.poll_interval_ms,
                lrclib_enabled=base_config.lrclib_enabled,
                auto_save_fetched_lrc=base_config.auto_save_fetched_lrc,
                lyric_offset_ms=base_config.lyric_offset_ms,
                overlay_bg_color=base_config.overlay_bg_color,
                overlay_text_color=base_config.overlay_text_color,
                lyric_text_color=base_config.lyric_text_color,
                lyric_glow_color=base_config.lyric_glow_color,
                lyric_font_family=base_config.lyric_font_family,
                lyric_font_size=base_config.lyric_font_size,
                text_alignment=base_config.text_alignment,
                show_settings_button=(
                    base_config.show_settings_button
                    if show_settings_button is None
                    else show_settings_button
                ),
                show_hide_button=(
                    base_config.show_hide_button
                    if show_hide_button is None
                    else show_hide_button
                ),
            )
            save_config(updated_config)
            overlay.load_config_values(updated_config)
            controller.config = updated_config
            sync_overlay_button_actions(updated_config)

        def exit_app() -> None:
            overlay.allow_exit()
            overlay.close()
            if tray_icon is not None:
                tray_icon.hide()
            app.quit()

        show_action.triggered.connect(show_overlay)
        hide_action.triggered.connect(hide_overlay)
        settings_action.triggered.connect(open_settings)
        mode_windows_action.triggered.connect(
            lambda checked: apply_playback_source(WINDOWS_PLAYBACK_SOURCE) if checked else None
        )
        mode_api_action.triggered.connect(
            lambda checked: apply_playback_source(SPOTIFY_API_PLAYBACK_SOURCE) if checked else None
        )
        show_settings_button_action.triggered.connect(
            lambda checked: apply_overlay_button_visibility(show_settings_button=checked)
        )
        show_hide_button_action.triggered.connect(
            lambda checked: apply_overlay_button_visibility(show_hide_button=checked)
        )
        exit_action.triggered.connect(exit_app)
        tray_icon.activated.connect(
            lambda reason: show_overlay()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        sync_mode_actions(config.playback_source)
        sync_overlay_button_actions(config)
        tray_icon.show()

    controller = AppController(
        playback_client=None,
        lyrics_repository=LyricsRepository(
            lrclib_enabled=config.lrclib_enabled,
            auto_save_fetched_lrc=config.auto_save_fetched_lrc,
        ),
        overlay=overlay,
        config=config,
    )

    def save_settings(new_config: AppConfig) -> None:
        current_config = controller.config
        saved_config = merge_config(current_config, new_config)
        save_config(saved_config)
        overlay.load_config_values(saved_config)
        overlay.apply_config_theme(saved_config)
        overlay.show_status("Settings saved to .env")
        controller.config = saved_config
        controller.lyrics_repository.set_auto_save_fetched_lrc(saved_config.auto_save_fetched_lrc)
        sync_mode_actions(saved_config.playback_source)
        sync_overlay_button_actions(saved_config)

    def toggle_lyric_color(lyric_color: str) -> None:
        saved_config = AppConfig(
            playback_source=controller.config.playback_source,
            spotify_client_id=controller.config.spotify_client_id,
            spotify_client_secret=controller.config.spotify_client_secret,
            spotify_redirect_uri=controller.config.spotify_redirect_uri,
            poll_interval_ms=controller.config.poll_interval_ms,
            lrclib_enabled=controller.config.lrclib_enabled,
            auto_save_fetched_lrc=controller.config.auto_save_fetched_lrc,
            lyric_offset_ms=controller.config.lyric_offset_ms,
            overlay_bg_color=controller.config.overlay_bg_color,
            overlay_text_color=controller.config.overlay_text_color,
            lyric_text_color=lyric_color or controller.config.lyric_text_color,
            lyric_glow_color=controller.config.lyric_glow_color,
            lyric_font_family=controller.config.lyric_font_family,
            lyric_font_size=controller.config.lyric_font_size,
            text_alignment=controller.config.text_alignment,
            show_settings_button=controller.config.show_settings_button,
            show_hide_button=controller.config.show_hide_button,
        )
        save_config(saved_config)
        controller.config = saved_config

    def clear_downloaded_lyrics() -> None:
        removed = controller.lyrics_repository.clear_downloaded_cache()
        if removed == 0:
            overlay.show_status("No downloaded lyric cache to clear")
            return
        suffix = "file" if removed == 1 else "files"
        overlay.show_status(f"Cleared {removed} downloaded lyric {suffix}")

    def reconnect_spotify() -> None:
        latest = load_config()
        overlay.load_config_values(latest)
        sync_mode_actions(latest.playback_source)
        sync_overlay_button_actions(latest)
        controller.lyrics_repository.set_lrclib_enabled(latest.lrclib_enabled)
        controller.lyrics_repository.set_auto_save_fetched_lrc(latest.auto_save_fetched_lrc)
        new_client, error_message = build_playback_client(latest)
        if new_client is None:
            overlay.show_status(error_message or "Failed to connect to Spotify playback.")
            controller.reconnect(None, latest, unavailable_message=error_message)
            return
        controller.reconnect(new_client, latest)

    overlay.save_requested.connect(save_settings)
    overlay.reconnect_requested.connect(reconnect_spotify)
    overlay.lyric_color_toggle_requested.connect(toggle_lyric_color)
    overlay.clear_lyrics_cache_requested.connect(clear_downloaded_lyrics)
    overlay.overlay_hidden.connect(controller.pause_polling)
    overlay.overlay_shown.connect(controller.resume_polling)
    app.aboutToQuit.connect(controller.stop)

    def initialize_spotify() -> None:
        latest = load_config()
        playback_client, error_message = build_playback_client(latest)
        if playback_client is None:
            controller.reconnect(None, latest, unavailable_message=error_message)
            overlay.set_track(None)
            overlay.set_lines(*playback_startup_lines(latest.playback_source, error_message))
            return
        controller.reconnect(playback_client, latest)

    overlay.set_track(None)
    overlay.set_lines("Starting Lyricfy...", "Connecting to Spotify playback")
    overlay.show_status("Connecting to Spotify playback...")
    overlay.show()
    QTimer.singleShot(0, initialize_spotify)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
