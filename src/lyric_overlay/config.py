from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _repo_base_dir() -> Path:
    # Root proyek saat dijalankan dari source code.
    return Path(__file__).resolve().parents[2]


def _runtime_base_dir() -> Path:
    # Saat build .exe, file runtime mengikuti lokasi executable.
    # Saat mode development, gunakan root repository.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _repo_base_dir()


def _resource_dir() -> Path:
    # PyInstaller mengekstrak resource sementara ke _MEIPASS.
    # Jika tidak ada, resource diambil langsung dari repository.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return _repo_base_dir()


def _user_data_dir() -> Path:
    # Data user disimpan di APPDATA pada Windows, dengan fallback ke home.
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "Lyricfy"
    return Path.home() / ".lyricfy"


REPO_BASE_DIR = _repo_base_dir()
BASE_DIR = _runtime_base_dir()
RESOURCE_DIR = _resource_dir()
# Pada build .exe, data writable dipisah ke folder user.
# Saat development, data tetap berada di folder proyek.
APP_DATA_DIR = _user_data_dir() if getattr(sys, "frozen", False) else BASE_DIR
ASSETS_DIR = APP_DATA_DIR / "assets"
LRC_DIR = ASSETS_DIR / "lrc"
FETCHED_LRC_DIR = LRC_DIR / "downloaded"
TOKEN_CACHE = APP_DATA_DIR / ".spotify_cache"
ENV_FILE = APP_DATA_DIR / ".env"
FALLBACK_ENV_FILE = BASE_DIR / ".env"
ICON_FILE = RESOURCE_DIR / "icon.ico"
WINDOWS_PLAYBACK_SOURCE = "windows"
SPOTIFY_API_PLAYBACK_SOURCE = "spotify_api"
PLAYBACK_SOURCES = {WINDOWS_PLAYBACK_SOURCE, SPOTIFY_API_PLAYBACK_SOURCE}
TEXT_ALIGNMENTS = {"left", "center", "right"}
CARD_DISPLAY_STYLE = "card"
FLOATING_DISPLAY_STYLE = "floating"
DISPLAY_STYLES = {CARD_DISPLAY_STYLE, FLOATING_DISPLAY_STYLE}
SINGLE_LYRIC_LINES = "single"
CURRENT_NEXT_LYRIC_LINES = "current_next"
LYRIC_LINES_MODES = {SINGLE_LYRIC_LINES, CURRENT_NEXT_LYRIC_LINES}
TRACK_CHANGE_INFO_MODE = "track_change"
ALWAYS_TRACK_INFO_MODE = "always"
NEVER_TRACK_INFO_MODE = "never"
TRACK_INFO_MODES = {TRACK_CHANGE_INFO_MODE, ALWAYS_TRACK_INFO_MODE, NEVER_TRACK_INFO_MODE}
CARD_DEFAULT_PRESET = "card_default"
FLOATING_MINIMAL_PRESET = "floating_minimal"
FLOATING_CONTEXT_PRESET = "floating_context"
CUSTOM_DISPLAY_PRESET = "custom"
DISPLAY_PRESETS = {
    CARD_DEFAULT_PRESET: (CARD_DISPLAY_STYLE, SINGLE_LYRIC_LINES, TRACK_CHANGE_INFO_MODE),
    FLOATING_MINIMAL_PRESET: (FLOATING_DISPLAY_STYLE, SINGLE_LYRIC_LINES, NEVER_TRACK_INFO_MODE),
    FLOATING_CONTEXT_PRESET: (
        FLOATING_DISPLAY_STYLE,
        CURRENT_NEXT_LYRIC_LINES,
        TRACK_CHANGE_INFO_MODE,
    ),
}


@dataclass(slots=True)
class AppConfig:
    # Seluruh konfigurasi aplikasi yang dibaca dari / ditulis ke .env.
    playback_source: str
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    poll_interval_ms: int = 1000
    lrclib_enabled: bool = True
    auto_save_fetched_lrc: bool = True
    lyric_offset_ms: int = 0
    overlay_bg_color: str = "#0A0A0AEB"
    overlay_text_color: str = "#F4F4F4"
    lyric_text_color: str = "#F4F4F4"
    lyric_glow_color: str = "#66CCFFFF"
    lyric_toggle_color: str = "#1A1A1A"
    lyric_font_family: str = "Segoe UI"
    lyric_font_size: int = 11
    text_alignment: str = "left"
    display_style: str = CARD_DISPLAY_STYLE
    lyric_lines: str = SINGLE_LYRIC_LINES
    track_info_mode: str = TRACK_CHANGE_INFO_MODE
    show_album_cover: bool = False
    show_settings_button: bool = True
    show_hide_button: bool = True
    hover_buttons_enabled: bool = False
    autostart_enabled: bool = False
    autostart_start_hidden: bool = False


def default_config() -> AppConfig:
    # Nilai default dipakai saat .env belum ada.
    return AppConfig(
        playback_source=WINDOWS_PLAYBACK_SOURCE,
        spotify_client_id="",
        spotify_client_secret="",
        spotify_redirect_uri="http://127.0.0.1:8888/callback",
        poll_interval_ms=1000,
        lrclib_enabled=True,
        auto_save_fetched_lrc=True,
        lyric_offset_ms=0,
        overlay_bg_color="#0A0A0AEB",
        overlay_text_color="#F4F4F4",
        lyric_text_color="#F4F4F4",
        lyric_glow_color="#66CCFFFF",
        lyric_toggle_color="#1A1A1A",
        lyric_font_family="Segoe UI",
        lyric_font_size=11,
        text_alignment="left",
        display_style=CARD_DISPLAY_STYLE,
        lyric_lines=SINGLE_LYRIC_LINES,
        track_info_mode=TRACK_CHANGE_INFO_MODE,
        show_album_cover=False,
        show_settings_button=True,
        show_hide_button=True,
        hover_buttons_enabled=False,
        autostart_enabled=False,
        autostart_start_hidden=False,
    )


def load_config() -> AppConfig:
    # Prioritas utama adalah .env di folder runtime/app data.
    # Jika belum ada, fallback ke .env di base directory.
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    elif FALLBACK_ENV_FILE.exists():
        load_dotenv(FALLBACK_ENV_FILE, override=True)

    # Semua nilai environment dikonversi ke AppConfig agar mudah dipakai modul lain.
    return AppConfig(
        playback_source=_normalize_playback_source(
            os.getenv("PLAYBACK_SOURCE", WINDOWS_PLAYBACK_SOURCE).strip().lower()
        ),
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", "").strip(),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "").strip(),
        spotify_redirect_uri=os.getenv(
            "SPOTIFY_REDIRECT_URI",
            "http://127.0.0.1:8888/callback",
        ).strip(),
        poll_interval_ms=int(os.getenv("POLL_INTERVAL_MS", "1000")),
        lrclib_enabled=os.getenv("LRCLIB_ENABLED", "true").lower() == "true",
        auto_save_fetched_lrc=os.getenv("AUTO_SAVE_FETCHED_LRC", "true").lower() == "true",
        lyric_offset_ms=int(os.getenv("LYRIC_OFFSET_MS", "0")),
        overlay_bg_color=os.getenv("OVERLAY_BG_COLOR", "#0A0A0AEB").strip() or "#0A0A0AEB",
        overlay_text_color=os.getenv("OVERLAY_TEXT_COLOR", "#F4F4F4").strip() or "#F4F4F4",
        lyric_text_color=os.getenv("LYRIC_TEXT_COLOR", "#F4F4F4").strip() or "#F4F4F4",
        lyric_glow_color=os.getenv("LYRIC_GLOW_COLOR", "#66CCFFFF").strip() or "#66CCFFFF",
        lyric_toggle_color=os.getenv("LYRIC_TOGGLE_COLOR", "#1A1A1A").strip() or "#1A1A1A",
        lyric_font_family=os.getenv("LYRIC_FONT_FAMILY", "Segoe UI").strip() or "Segoe UI",
        lyric_font_size=int(os.getenv("LYRIC_FONT_SIZE", "11")),
        text_alignment=_normalize_text_alignment(os.getenv("TEXT_ALIGNMENT", "left")),
        display_style=_normalize_display_style(os.getenv("DISPLAY_STYLE", CARD_DISPLAY_STYLE)),
        lyric_lines=_normalize_lyric_lines(os.getenv("LYRIC_LINES", SINGLE_LYRIC_LINES)),
        track_info_mode=_normalize_track_info_mode(
            os.getenv("TRACK_INFO_MODE", TRACK_CHANGE_INFO_MODE)
        ),
        show_album_cover=os.getenv("SHOW_ALBUM_COVER", "false").lower() == "true",
        show_settings_button=os.getenv("SHOW_SETTINGS_BUTTON", "true").lower() == "true",
        show_hide_button=os.getenv("SHOW_HIDE_BUTTON", "true").lower() == "true",
        hover_buttons_enabled=os.getenv("HOVER_BUTTONS_ENABLED", "false").lower() == "true",
        autostart_enabled=os.getenv("AUTOSTART_ENABLED", "false").lower() == "true",
        autostart_start_hidden=os.getenv("AUTOSTART_START_HIDDEN", "false").lower() == "true",
    )


def ensure_directories() -> None:
    # Pastikan semua folder runtime tersedia sebelum aplikasi berjalan.
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    LRC_DIR.mkdir(parents=True, exist_ok=True)
    FETCHED_LRC_DIR.mkdir(parents=True, exist_ok=True)


def ensure_env_file() -> None:
    # Jika file config sudah ada, tidak perlu membuat ulang.
    if ENV_FILE.exists():
        return

    # Saat development, salin .env dari base directory jika tersedia.
    if FALLBACK_ENV_FILE.exists() and FALLBACK_ENV_FILE != ENV_FILE:
        ENV_FILE.write_text(FALLBACK_ENV_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        return

    # Jika tidak ada sumber config sama sekali, buat file dengan nilai default.
    save_config(default_config())


def _normalize_playback_source(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in PLAYBACK_SOURCES:
        return normalized
    return WINDOWS_PLAYBACK_SOURCE


def _normalize_text_alignment(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in TEXT_ALIGNMENTS:
        return normalized
    return "left"


def _normalize_display_style(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in DISPLAY_STYLES:
        return normalized
    return CARD_DISPLAY_STYLE


def _normalize_lyric_lines(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in LYRIC_LINES_MODES:
        return normalized
    return SINGLE_LYRIC_LINES


def _normalize_track_info_mode(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in TRACK_INFO_MODES:
        return normalized
    return TRACK_CHANGE_INFO_MODE


def display_preset_for(config: AppConfig) -> str:
    values = (
        _normalize_display_style(config.display_style),
        _normalize_lyric_lines(config.lyric_lines),
        _normalize_track_info_mode(config.track_info_mode),
    )
    for preset, preset_values in DISPLAY_PRESETS.items():
        if values == preset_values:
            return preset
    return CUSTOM_DISPLAY_PRESET


def display_preset_values(preset: str) -> tuple[str, str, str] | None:
    return DISPLAY_PRESETS.get((preset or "").strip().lower())


def save_config(config: AppConfig) -> None:
    # Simpan ulang seluruh konfigurasi ke format .env sederhana key=value.
    lines = [
        f"PLAYBACK_SOURCE={_normalize_playback_source(config.playback_source)}",
        f"SPOTIFY_CLIENT_ID={config.spotify_client_id}",
        f"SPOTIFY_CLIENT_SECRET={config.spotify_client_secret}",
        f"SPOTIFY_REDIRECT_URI={config.spotify_redirect_uri}",
        f"POLL_INTERVAL_MS={config.poll_interval_ms}",
        f"LRCLIB_ENABLED={'true' if config.lrclib_enabled else 'false'}",
        f"AUTO_SAVE_FETCHED_LRC={'true' if config.auto_save_fetched_lrc else 'false'}",
        f"LYRIC_OFFSET_MS={config.lyric_offset_ms}",
        f"OVERLAY_BG_COLOR={config.overlay_bg_color}",
        f"OVERLAY_TEXT_COLOR={config.overlay_text_color}",
        f"LYRIC_TEXT_COLOR={config.lyric_text_color}",
        f"LYRIC_GLOW_COLOR={config.lyric_glow_color}",
        f"LYRIC_TOGGLE_COLOR={config.lyric_toggle_color}",
        f"LYRIC_FONT_FAMILY={config.lyric_font_family}",
        f"LYRIC_FONT_SIZE={config.lyric_font_size}",
        f"TEXT_ALIGNMENT={_normalize_text_alignment(config.text_alignment)}",
        f"DISPLAY_STYLE={_normalize_display_style(config.display_style)}",
        f"LYRIC_LINES={_normalize_lyric_lines(config.lyric_lines)}",
        f"TRACK_INFO_MODE={_normalize_track_info_mode(config.track_info_mode)}",
        f"SHOW_ALBUM_COVER={'true' if config.show_album_cover else 'false'}",
        f"SHOW_SETTINGS_BUTTON={'true' if config.show_settings_button else 'false'}",
        f"SHOW_HIDE_BUTTON={'true' if config.show_hide_button else 'false'}",
        f"HOVER_BUTTONS_ENABLED={'true' if config.hover_buttons_enabled else 'false'}",
        f"AUTOSTART_ENABLED={'true' if config.autostart_enabled else 'false'}",
        f"AUTOSTART_START_HIDDEN={'true' if config.autostart_start_hidden else 'false'}",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
