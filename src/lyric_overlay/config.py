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


@dataclass(slots=True)
class AppConfig:
    # Seluruh konfigurasi aplikasi yang dibaca dari / ditulis ke .env.
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


def default_config() -> AppConfig:
    # Nilai default dipakai saat .env belum ada.
    return AppConfig(
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


def save_config(config: AppConfig) -> None:
    # Simpan ulang seluruh konfigurasi ke format .env sederhana key=value.
    lines = [
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
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
