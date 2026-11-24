"""Generate an Ed25519 release key or sign an installer; see RELEASE_GUIDE.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate-key")
    generate.add_argument("private_key", type=Path, help="Path OUTSIDE the repository")
    sign = commands.add_parser("sign")
    sign.add_argument("private_key", type=Path)
    sign.add_argument("version", help="Stable tag, e.g. v1.6.3")
    sign.add_argument("installer", type=Path)
    args = parser.parse_args()
    if args.command == "generate-key":
        repo = Path(__file__).resolve().parents[1]
        if args.private_key.resolve().is_relative_to(repo):
            parser.error("Save the private key outside the repository")
        private = Ed25519PrivateKey.generate()
        data = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with args.private_key.open("xb") as file:
            file.write(data)
        public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        print(f"Private key saved to {args.private_key}. Keep it secret and backed up.\nSet PUBLIC_KEY_HEX in src/lyric_overlay/update_key.py to:\n{public}")
        return
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.version):
        parser.error("Version must look like v1.6.3")
    if args.installer.name != f"Lyricfy Setup {args.version}.exe":
        parser.error("Installer name must match Lyricfy Setup <version>.exe")
    private = serialization.load_pem_private_key(args.private_key.read_bytes(), password=None)
    if not isinstance(private, Ed25519PrivateKey):
        parser.error("Private key must be Ed25519")
    with args.installer.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    # GitHub normalizes spaces in uploaded asset names to dots.
    asset_name = f"Lyricfy.Setup.{args.version}.exe"
    manifest = (json.dumps({"version": args.version, "installer": asset_name, "sha256": digest}, indent=2) + "\n").encode("utf-8")
    (args.installer.parent / "update-manifest.json").write_bytes(manifest)
    (args.installer.parent / "update-manifest.sig").write_bytes(private.sign(manifest))
    print("Created update-manifest.json and update-manifest.sig alongside the installer.")


if __name__ == "__main__":
    main()
