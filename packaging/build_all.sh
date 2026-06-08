#!/bin/bash
# Build both macOS installers (.pkg and .dmg) into <repo>/dist. macOS only.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$HERE/build_pkg.sh"
bash "$HERE/build_dmg.sh"
echo
echo "Artifacts:"
ls -1sh "$(cd "$HERE/.." && pwd)/dist"/*.pkg "$(cd "$HERE/.." && pwd)/dist"/*.dmg 2>/dev/null || true
