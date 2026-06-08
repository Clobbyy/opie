#!/bin/bash
# Build a drag-to-install disk image: Opie-<version>.dmg
#
# The .dmg opens to show Opie.app next to an Applications shortcut — the user
# drags one onto the other. First launch of the app self-configures (token +
# code location), so no installer script is needed.
#
# macOS only (uses hdiutil). Run from anywhere:
#   packaging/build_dmg.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIST="$ROOT/dist"
WORK="$DIST/_dmg"

command -v hdiutil >/dev/null 2>&1 || {
  echo "❌  'hdiutil' not found — build the .dmg on macOS." >&2; exit 1; }

# 1) Assemble the app into a clean staging folder that becomes the disk contents.
rm -rf "$WORK"; mkdir -p "$WORK/stage"
VERSION="$(bash "$HERE/build_app.sh" "$WORK/stage" | sed -n 's/^VERSION=//p')"
[ -n "$VERSION" ] || { echo "could not determine version" >&2; exit 1; }

# 2) Drag-install affordances: an Applications shortcut and a short note.
ln -s /Applications "$WORK/stage/Applications"
cat > "$WORK/stage/Drag Opie to Applications.txt" <<EOF
To install: drag the Opie icon onto the Applications folder shown here.

Then open Opie from Applications. (First open: right-click Opie → Open → Open,
because the app isn't signed by an Apple Developer ID yet.)
EOF

# 3) Compressed image.
mkdir -p "$DIST"
OUT="$DIST/Opie-$VERSION.dmg"
rm -f "$OUT"
hdiutil create \
  -volname "Opie $VERSION" \
  -srcfolder "$WORK/stage" \
  -fs HFS+ \
  -format UDZO \
  -ov \
  "$OUT"

rm -rf "$WORK"
echo
echo "✅  Built $OUT"
echo "   (Unsigned: first open needs right-click → Open. Sign + notarize for a"
echo "    one-click experience.)"
