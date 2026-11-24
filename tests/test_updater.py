import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from lyric_overlay import updater


class Response:
    def __init__(self, data=b"", json_data=None):
        self.data, self.json_data = data, json_data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def json(self):
        return self.json_data

    def iter_content(self, size):
        yield self.data


def setup_release(monkeypatch, *, manifest_version="v1.6.3", corrupt=False):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    monkeypatch.setattr(updater, "PUBLIC_KEY_HEX", public)
    name = "Lyricfy.Setup.v1.6.3.exe"
    manifest = json.dumps({"version": manifest_version, "installer": name, "sha256": hashlib.sha256(b"installer").hexdigest()}).encode()
    signature = private.sign(manifest)
    if corrupt:
        manifest += b" "
    data = {updater.MANIFEST_NAME: manifest, updater.SIGNATURE_NAME: signature, name: b"installer"}
    base = f"https://github.com/{updater.REPOSITORY}/releases/download/v1.6.3/"
    release = {"tag_name": "v1.6.3", "assets": [{"name": n, "browser_download_url": base + n} for n in data]}
    def get(url, **kwargs):
        if url == updater.API_URL:
            return Response(json_data=release)
        return Response(data[url[len(base):]])
    monkeypatch.setattr(updater.requests, "get", get)
    return release


def test_signed_update_and_download(monkeypatch):
    setup_release(monkeypatch)
    update = updater.find_update("1.6.2")
    assert update["version"] == "v1.6.3"
    target = updater.download_installer(update)
    assert target.read_bytes() == b"installer"
    target.unlink()
    target.parent.rmdir()
    assert updater.find_update("1.6.3") is None


@pytest.mark.parametrize("kwargs", [{"corrupt": True}, {"manifest_version": "v1.6.4"}])
def test_rejects_invalid_manifest(monkeypatch, kwargs):
    setup_release(monkeypatch, **kwargs)
    with pytest.raises(updater.UpdateError):
        updater.find_update("1.6.2")


def test_rejects_wrong_installer_hash(monkeypatch):
    setup_release(monkeypatch)
    update = updater.find_update("1.6.2")
    update["sha256"] = "0" * 64
    with pytest.raises(updater.UpdateError, match="checksum"):
        updater.download_installer(update)


def test_missing_key_and_untrusted_url(monkeypatch):
    release = setup_release(monkeypatch)
    monkeypatch.setattr(updater, "PUBLIC_KEY_HEX", "")
    with pytest.raises(updater.UpdateError, match="not configured"):
        updater.find_update("1.6.2")
    release["assets"][0]["browser_download_url"] = "https://evil.example/file"
    with pytest.raises(updater.UpdateError, match="URL"):
        updater._asset(release, updater.MANIFEST_NAME)
