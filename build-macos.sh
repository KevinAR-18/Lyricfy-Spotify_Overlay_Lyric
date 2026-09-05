#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
    echo "Build Lyricfy.app on macOS, or use the macOS GitHub Actions job." >&2
    exit 1
fi
cd -- "$(dirname -- "$0")"
ROOT="$PWD"
PYTHON="${LYRICFY_PYTHON:-python3}"
export LYRICFY_TARGET_ARCH="${LYRICFY_TARGET_ARCH:-$(uname -m)}"
RELEASE=false
if [[ "${1:-}" == --release ]]; then
    RELEASE=true
elif [[ $# -ne 0 ]]; then
    echo "Usage: bash build-macos.sh [--release]" >&2
    exit 1
fi
if $RELEASE; then
    : "${LYRICFY_CODESIGN_IDENTITY:?Set a Developer ID Application signing identity}"
    : "${LYRICFY_NOTARY_PROFILE:?Set a notarytool keychain profile}"
fi
case "$LYRICFY_TARGET_ARCH" in arm64|x86_64) ;; *) echo "Unsupported target architecture" >&2; exit 1 ;; esac
"$PYTHON" -c 'import os, platform; assert platform.machine() == os.environ["LYRICFY_TARGET_ARCH"], "Use native Python for the selected architecture"'
"$PYTHON" -m pip check
VERSION="$("$PYTHON" -c 'import sys; sys.path.insert(0, "src"); from lyric_overlay import __version__; print(__version__)')"
WORK="$ROOT/build/macos-$LYRICFY_TARGET_ARCH"
DEST="$ROOT/dist/macos-$LYRICFY_TARGET_ARCH"
ICONSET="$ROOT/build/macos-icons/Lyricfy.iconset"
mkdir -p "$WORK" "$DEST" "$ICONSET"
# Format conversion uses Apple's own tools; the original artwork stays intact.
for SIZE in 16 32 128 256 512; do
    sips -z "$SIZE" "$SIZE" "$ROOT/icon.png" --out "$ICONSET/icon_${SIZE}x${SIZE}.png" >/dev/null
    DOUBLE=$((SIZE * 2))
    sips -z "$DOUBLE" "$DOUBLE" "$ROOT/icon.png" --out "$ICONSET/icon_${SIZE}x${SIZE}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ROOT/build/macos-icons/Lyricfy.icns"
"$PYTHON" -m PyInstaller --noconfirm --clean --workpath "$WORK" --distpath "$DEST" Lyricfy-macos.spec
APP="$DEST/Lyricfy.app"
codesign --verify --deep --strict "$APP"
QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/Lyricfy" --smoke-test

SUFFIX=preview
if $RELEASE; then SUFFIX=release; fi
ZIP="$DEST/Lyricfy-$VERSION-macos-$LYRICFY_TARGET_ARCH-$SUFFIX.zip"
DMG="$DEST/Lyricfy-$VERSION-macos-$LYRICFY_TARGET_ARCH-$SUFFIX.dmg"
notarize() {
    xcrun notarytool submit "$1" --keychain-profile "$LYRICFY_NOTARY_PROFILE" --wait --output-format json > "$2"
    "$PYTHON" -c 'import json, sys; data=json.load(open(sys.argv[1])); print("Notarization:", data.get("status")); sys.exit(0 if data.get("status") == "Accepted" else 1)' "$2"
}
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
if $RELEASE; then
    notarize "$ZIP" "$WORK/notary-app.json"
    xcrun stapler staple "$APP"
    xcrun stapler validate "$APP"
    spctl --assess --type execute --verbose=2 "$APP"
    ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
fi
STAGE="$(mktemp -d "$WORK/dmg-stage.XXXXXX")"
trap 'rm -rf -- "$STAGE"' EXIT
ditto "$APP" "$STAGE/Lyricfy.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname Lyricfy -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
if $RELEASE; then
    codesign --force --timestamp --sign "$LYRICFY_CODESIGN_IDENTITY" "$DMG"
    notarize "$DMG" "$WORK/notary-dmg.json"
    xcrun stapler staple "$DMG"
    xcrun stapler validate "$DMG"
    spctl --assess --type open --context context:primary-signature "$DMG"
fi
shasum -a 256 "$ZIP" "$DMG" > "$DEST/SHA256SUMS.txt"
echo "Built $ZIP and $DMG"
