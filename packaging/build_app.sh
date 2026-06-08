#!/bin/bash
# Assemble Opie.app from the repo. Pure file ops (cp/mkdir/sed/chmod), so it runs
# on any OS — handy for testing the bundle layout. The .pkg/.dmg wrappers
# (build_pkg.sh / build_dmg.sh) call this first, then use macOS-only tools.
#
# Usage:  packaging/build_app.sh [OUTPUT_DIR]
#   OUTPUT_DIR defaults to <repo>/dist . The app is written to OUTPUT_DIR/Opie.app.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${1:-$ROOT/dist}"
APP="$OUT/Opie.app"

# Version comes from the single source of truth: opie/__init__.py.
VERSION="$(sed -n 's/^__version__ *= *"\(.*\)".*/\1/p' "$ROOT/opie/__init__.py")"
[ -n "$VERSION" ] || { echo "Could not read __version__ from opie/__init__.py" >&2; exit 1; }

echo "Building Opie.app  (version $VERSION)"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# 1) The Python package + its bundled resources (config example, plist template).
cp -R "$ROOT/opie" "$APP/Contents/Resources/opie"
# Don't ship compiled caches.
find "$APP/Contents/Resources/opie" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$APP/Contents/Resources/opie" -name '*.pyc' -delete 2>/dev/null || true

# 2) The launcher (the app's executable).
cp "$HERE/app/launcher" "$APP/Contents/MacOS/Opie"
chmod +x "$APP/Contents/MacOS/Opie"

# 3) Info.plist with the version stamped in.
sed "s/@VERSION@/$VERSION/g" "$HERE/app/Info.plist.in" > "$APP/Contents/Info.plist"

# 4) Optional icon (drop packaging/app/AppIcon.icns to brand it).
if [ -f "$HERE/app/AppIcon.icns" ]; then
  cp "$HERE/app/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
fi

# Mark the bundle so Finder treats it as an application (best-effort; macOS only).
command -v SetFile >/dev/null 2>&1 && SetFile -a B "$APP" 2>/dev/null || true

echo "✓  $APP"
echo "VERSION=$VERSION"   # handy for callers:  eval "$(... | tail -1)"
