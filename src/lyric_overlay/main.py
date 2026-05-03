from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lyric_overlay.app_controller import AppController
    from lyric_overlay.config import AppConfig, ICON_FILE, ensure_directories, ensure_env_file, load_config, save_config
    from lyric_overlay.lyrics import LyricsRepository
    from lyric_overlay.overlay import OverlayWindow, create_application
    from lyric_overlay.spotify_client import SpotifyClient
else:
    from .app_controller import AppController
    from .config import AppConfig, ICON_FILE, ensure_directories, ensure_env_file, load_config, save_config
    from .lyrics import LyricsRepository
    from .overlay import OverlayWindow, create_application
    from .spotify_client import SpotifyClient


def build_spotify_client(config: AppConfig) -> SpotifyClient | None:
    try:
        return SpotifyClient(
            client_id=config.spotify_client_id,
            client_secret=config.spotify_client_secret,
            redirect_uri=config.spotify_redirect_uri,
        )
    except ValueError:
        return None


def main() -> int:
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
        exit_action = QAction("Exit", tray_menu)
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        tray_icon.setContextMenu(tray_menu)

        def show_overlay() -> None:
            overlay.show_from_tray()

        def hide_overlay() -> None:
            overlay.hide_to_tray()

        def open_settings() -> None:
            overlay.open_settings_from_tray()

        def exit_app() -> None:
            overlay.allow_exit()
            overlay.close()
            if tray_icon is not None:
                tray_icon.hide()
            app.quit()

        show_action.triggered.connect(show_overlay)
        hide_action.triggered.connect(hide_overlay)
        settings_action.triggered.connect(open_settings)
        exit_action.triggered.connect(exit_app)
        tray_icon.activated.connect(
            lambda reason: show_overlay()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        tray_icon.show()

    spotify_client = build_spotify_client(config)
    if spotify_client is None:
        overlay.set_track(None)
        overlay.set_lines("Open Settings to add Spotify credentials", "Then click Save and Reload Spotify")

    controller = AppController(
        spotify_client=spotify_client,
        lyrics_repository=LyricsRepository(
            lrclib_enabled=config.lrclib_enabled,
            auto_save_fetched_lrc=config.auto_save_fetched_lrc,
        ),
        overlay=overlay,
        config=config,
    )

    def save_settings(new_config: AppConfig) -> None:
        current_config = controller.config
        saved_config = AppConfig(
            spotify_client_id=new_config.spotify_client_id,
            spotify_client_secret=new_config.spotify_client_secret,
            spotify_redirect_uri=new_config.spotify_redirect_uri or "http://127.0.0.1:8888/callback",
            poll_interval_ms=current_config.poll_interval_ms,
            lrclib_enabled=current_config.lrclib_enabled,
            auto_save_fetched_lrc=new_config.auto_save_fetched_lrc,
            lyric_offset_ms=new_config.lyric_offset_ms,
            overlay_bg_color=new_config.overlay_bg_color or current_config.overlay_bg_color,
            overlay_text_color=new_config.overlay_text_color or current_config.overlay_text_color,
            lyric_text_color=new_config.lyric_text_color or current_config.lyric_text_color,
            lyric_glow_color=new_config.lyric_glow_color or current_config.lyric_glow_color,
        )
        save_config(saved_config)
        overlay.apply_config_theme(saved_config)
        overlay.show_status("Settings saved to .env")
        controller.config = saved_config
        controller.lyrics_repository.set_auto_save_fetched_lrc(saved_config.auto_save_fetched_lrc)

    def toggle_lyric_color(lyric_color: str) -> None:
        saved_config = AppConfig(
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
        controller.lyrics_repository.set_lrclib_enabled(latest.lrclib_enabled)
        controller.lyrics_repository.set_auto_save_fetched_lrc(latest.auto_save_fetched_lrc)
        new_client = build_spotify_client(latest)
        if new_client is None:
            overlay.show_status("Spotify credentials are incomplete")
            controller.reconnect(None, latest)
            return
        controller.reconnect(new_client, latest)

    overlay.save_requested.connect(save_settings)
    overlay.reconnect_requested.connect(reconnect_spotify)
    overlay.lyric_color_toggle_requested.connect(toggle_lyric_color)
    overlay.clear_lyrics_cache_requested.connect(clear_downloaded_lyrics)
    overlay.overlay_hidden.connect(controller.pause_polling)
    overlay.overlay_shown.connect(controller.resume_polling)
    app.aboutToQuit.connect(controller.stop)
    overlay.show()
    QTimer.singleShot(0, controller.start)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
