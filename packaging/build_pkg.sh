#!/bin/bash
# Build a double-clickable macOS installer: Opie-<version>.pkg
#
# The .pkg installs Opie.app into /Applications via a guided installer (shows the
# license, then "Install"). First launch of the app creates the user's config
# (with a fresh token) and records where the code lives — so there's no
# root-owned-config footgun from a postinstall script.
#
# macOS only (uses pkgbuild + productbuild). Run from anywhere:
#   packaging/build_pkg.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIST="$ROOT/dist"
WORK="$DIST/_pkg"
IDENTIFIER="com.opie.control"

for tool in pkgbuild productbuild; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "❌  '$tool' not found — build the .pkg on macOS." >&2; exit 1; }
done

# 1) Assemble the app into a clean staging root (so the pkg payload is just the app).
rm -rf "$WORK"; mkdir -p "$WORK/root"
VERSION="$(bash "$HERE/build_app.sh" "$WORK/root" | sed -n 's/^VERSION=//p')"
[ -n "$VERSION" ] || { echo "could not determine version" >&2; exit 1; }

# 2) Component package: payload = /Applications/Opie.app
pkgbuild \
  --root "$WORK/root" \
  --identifier "$IDENTIFIER" \
  --version "$VERSION" \
  --install-location /Applications \
  "$WORK/Opie-component.pkg"

# 3) Distribution wrapper (title + license + welcome screens).
RES="$WORK/resources"; mkdir -p "$RES"
cp "$ROOT/LICENSE" "$RES/LICENSE.txt"
cat > "$RES/welcome.txt" <<EOF
Opie — speak to Siri to control an ETC Eos / Nomad lighting console.

This installs the Opie control panel into your Applications folder. The first
time you open it, Opie creates its settings (including a private security token)
and walks you through connecting your console and iPhone.

Requires Python 3 with Tk 8.6+ (free from python.org if you don't have it; Opie
will point you there).
EOF
cat > "$RES/conclusion.txt" <<EOF
Opie is installed in your Applications folder.

Open "Opie" to set your Console IP and token, then build the iPhone Shortcut
from the Test & Help tab.
EOF

cat > "$WORK/distribution.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Opie $VERSION</title>
    <welcome file="welcome.txt"/>
    <license file="LICENSE.txt"/>
    <conclusion file="conclusion.txt"/>
    <options customize="never" require-scripts="false" hostArchitectures="arm64,x86_64"/>
    <pkg-ref id="$IDENTIFIER"/>
    <choices-outline>
        <line choice="default">
            <line choice="$IDENTIFIER"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="$IDENTIFIER" visible="false">
        <pkg-ref id="$IDENTIFIER"/>
    </choice>
    <pkg-ref id="$IDENTIFIER" version="$VERSION" onConclusion="none">Opie-component.pkg</pkg-ref>
</installer-gui-script>
EOF

# 4) Final product archive.
mkdir -p "$DIST"
OUT="$DIST/Opie-$VERSION.pkg"
productbuild \
  --distribution "$WORK/distribution.xml" \
  --package-path "$WORK" \
  --resources "$RES" \
  "$OUT"

rm -rf "$WORK"
echo
echo "✅  Built $OUT"
echo "   (Unsigned: first open needs right-click → Open, or System Settings →"
echo "    Privacy & Security → Open Anyway. Sign + notarize for a clean install.)"
