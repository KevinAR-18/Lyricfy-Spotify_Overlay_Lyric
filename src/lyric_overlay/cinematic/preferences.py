from __future__ import annotations

import json


DEFAULTS = {
    "font_family": "Segoe UI", "font_size": 36, "bold": True,
    "alignment": "center", "active_color": "#FFF6E8",
    "previous_color": "#C4BFCE", "next_color": "#D6D1DF",
    "context_opacity": 40, "text_width": 640, "padding": 32, "gap": 28,
    "background": "transparent", "background_color": "#111018",
    "gradient_color": "#46304F", "background_motion": True,
    "glow_color": "#DAC5FF", "glow_strength": 12, "vignette": 25,
    "duration": 400, "motion": 100, "show_info": True, "show_cover": False,
    "ambient_effect": "none", "ambient_intensity": 50,
}
RANGES = {
    "font_size": (16, 100), "context_opacity": (0, 100),
    "text_width": (200, 1600), "padding": (8, 120), "gap": (4, 100),
    "glow_strength": (0, 100), "vignette": (0, 100),
    "duration": (100, 1000), "motion": (0, 100),
    "ambient_intensity": (10, 100),
}
CHOICES = {
    "alignment": ("left", "center", "right"),
    "background": ("transparent", "solid", "gradient", "album"),
    "ambient_effect": (
        "none", "leaves", "snowfall", "rain", "fireflies", "blobs", "stardust",
        "sakura", "bubbles", "underwater", "shooting_stars", "embers", "light_beams",
    ),
}


def needs_artwork(options: dict) -> bool:
    return bool(options.get("show_cover") or options.get("background") == "album"
                or options.get("ambient_effect") in (
                    "leaves", "rain", "fireflies", "blobs", "stardust", "light_beams",
                ))


def normalize_options(value: object) -> dict:
    from PySide6.QtGui import QColor

    result = dict(DEFAULTS)
    if not isinstance(value, dict):
        return result
    for key, default in DEFAULTS.items():
        item = value.get(key, default)
        if key in RANGES:
            try:
                result[key] = max(RANGES[key][0], min(RANGES[key][1], int(item)))
            except (TypeError, ValueError, OverflowError):
                pass
        elif isinstance(default, bool):
            if isinstance(item, bool):
                result[key] = item
        elif key in CHOICES:
            if item in CHOICES[key]:
                result[key] = item
        elif key.endswith("color"):
            if isinstance(item, str) and QColor(item).isValid():
                result[key] = QColor(item).name(QColor.NameFormat.HexArgb)
        elif isinstance(item, str) and item.strip():
            result[key] = item.strip().replace("\n", " ").replace("\r", " ")[:100]
    return result


def decode_options(value: str) -> dict:
    try:
        return normalize_options(json.loads(value))
    except (ValueError, TypeError):
        return dict(DEFAULTS)


def encode_options(value: dict) -> str:
    # Single-quoted dotenv value; keep font names containing apostrophes safe.
    payload = json.dumps(normalize_options(value), ensure_ascii=True, separators=(",", ":")).replace("'", "\\u0027").replace("$", "\\u0024")
    return payload.replace("\\", "\\\\")
