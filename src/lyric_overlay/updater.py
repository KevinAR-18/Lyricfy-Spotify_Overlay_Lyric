"""GitHub release discovery and signed installer verification."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, QTimer
from PySide6.QtWidgets import QMessageBox

from . import __version__
from .update_key import PUBLIC_KEY_HEX

REPOSITORY = "KevinAR-18/Lyricfy-Spotify_Overlay_Lyric"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases/latest"
MANIFEST_NAME = "update-manifest.json"
SIGNATURE_NAME = "update-manifest.sig"
MAX_INSTALLER_SIZE = 300 * 1024 * 1024


class UpdateError(Exception):
    pass


def _version(value):
    try:
        result = Version(value.removeprefix("v"))
    except (InvalidVersion, AttributeError) as exc:
        raise UpdateError("Invalid release version") from exc
    if result.is_prerelease or result.is_devrelease or result.local is not None:
        raise UpdateError("Not a stable release")
    return result


def _asset(release, name):
    matches = [a for a in release.get("assets", []) if a.get("name") == name]
    if len(matches) != 1:
        raise UpdateError(f"Release asset missing or duplicated: {name}")
    url = matches[0].get("browser_download_url", "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or not parsed.path.startswith(f"/{REPOSITORY}/releases/download/"):
        raise UpdateError("Invalid release asset URL")
    return url


def _download_small(url, limit):
    with requests.get(url, timeout=(10, 30), stream=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(8192):
            data.extend(chunk)
            if len(data) > limit:
                raise UpdateError("Release metadata is too large")
        return bytes(data)


def find_update(current_version=__version__):
    response = requests.get(API_URL, timeout=(10, 20), headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    release = response.json()
    if release.get("draft") or release.get("prerelease"):
        raise UpdateError("Latest release is not stable")
    tag = release.get("tag_name", "")
    if _version(tag) <= _version(current_version):
        return None
    if not PUBLIC_KEY_HEX:
        raise UpdateError("Update signing key is not configured in this build")
    manifest_bytes = _download_small(_asset(release, MANIFEST_NAME), 16384)
    signature = _download_small(_asset(release, SIGNATURE_NAME), 128)
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX)).verify(signature, manifest_bytes)
        manifest = json.loads(manifest_bytes)
        name, digest = manifest["installer"], manifest["sha256"]
        if manifest["version"] != tag or not isinstance(name, str) or name != f"Lyricfy.Setup.{tag}.exe":
            raise UpdateError("Signed manifest does not match the release")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise UpdateError("Invalid installer checksum")
    except (InvalidSignature, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise UpdateError("Invalid signed update manifest") from exc
    return {"version": tag, "url": _asset(release, name), "sha256": digest, "name": name}


def download_installer(update):
    # Keep the installer outside the application directory so Windows can replace it.
    folder = Path(tempfile.mkdtemp(prefix="lyricfy-update-"))
    target = folder / update["name"]
    try:
        digest = hashlib.sha256()
        size = 0
        with requests.get(update["url"], timeout=(10, 60), stream=True) as response:
            response.raise_for_status()
            with target.open("xb") as file:
                for chunk in response.iter_content(1024 * 128):
                    size += len(chunk)
                    if size > MAX_INSTALLER_SIZE:
                        raise UpdateError("Installer exceeds size limit")
                    digest.update(chunk)
                    file.write(chunk)
        if digest.hexdigest() != update["sha256"]:
            raise UpdateError("Installer checksum does not match the signed manifest")
        return target
    except Exception:
        target.unlink(missing_ok=True)
        folder.rmdir()
        raise


class WorkerSignals(QObject):
    finished = Signal(object, object)


class Worker(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.finished.emit(self.operation(), None)
        except Exception as exc:
            self.signals.finished.emit(None, str(exc))


class UpdateCoordinator(QObject):
    def __init__(self, quit_callback, parent=None):
        super().__init__(parent)
        self.quit_callback = quit_callback
        self.busy = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.worker = None

    def _run(self, operation, callback):
        self.busy = True
        self.worker = Worker(operation)
        self.worker.signals.finished.connect(callback)
        self.pool.start(self.worker)

    def check(self, manual=False):
        if self.busy:
            if manual:
                QMessageBox.information(None, "Lyricfy Update", "An update check or download is already in progress.")
            return
        self._run(find_update, lambda update, error: self._checked(update, error, manual))

    def _checked(self, update, error, manual):
        self.busy = False
        if error:
            if manual:
                QMessageBox.warning(None, "Lyricfy Update", f"Could not check for updates: {error}\n\nVisit {RELEASES_URL}")
            return
        if not update:
            if manual:
                QMessageBox.information(None, "Lyricfy Update", "Lyricfy is up to date.")
            return
        answer = QMessageBox.question(None, "Lyricfy Update", f"Lyricfy {update['version']} is available. Download and start the installer?\n\nLyricfy will close before installation. Windows may ask for permission.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._run(lambda: download_installer(update), self._downloaded)

    def _downloaded(self, path, error):
        self.busy = False
        if error:
            QMessageBox.warning(None, "Lyricfy Update", f"Update download failed: {error}\n\nVisit {RELEASES_URL}")
            return
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            QMessageBox.information(None, "Lyricfy Update", f"Verified installer downloaded to:\n{path}\n\nAutomatic installation is available only in the Windows packaged application.")
            return
        try:
            # Launch the normal InstallForge wizard. It handles UAC and restarts the app
            # if the user selects its launch option; no undocumented silent flags are used.
            os.startfile(str(path))
        except OSError as exc:
            QMessageBox.warning(None, "Lyricfy Update", f"Could not start installer: {exc}")
            return
        QTimer.singleShot(0, self.quit_callback)
