from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> None:
    if sys.platform != "darwin":
        return
    logger = logging.getLogger("lyric_overlay")
    if logger.handlers:
        return
    directory = Path.home() / "Library" / "Logs" / "Lyricfy"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "lyricfy.log", maxBytes=1024 * 1024,
                                      backupCount=2, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
