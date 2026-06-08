#!/bin/bash
# Opie one-paste installer — no Apple Developer ID, no Gatekeeper prompt.
#
# Files fetched with `git` are NOT quarantined by macOS, so nothing here ever
# trips the "unidentified developer" block — unlike a .pkg/.dmg downloaded in a
# browser. This clones (or updates) Opie and runs its installer, which opens the
# control panel. You also get automatic updates (the clone self-updates on start).
#
# Run in Terminal (paste the whole line):
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/bootstrap.sh)"
# …or, after cloning the repo yourself:
#   bash bootstrap.sh
#
# Override defaults with env vars:  OPIE_REPO=…  OPIE_DEST=…
set -euo pipefail

REPO="${OPIE_REPO:-https://github.com/Clobbyy/opie.git}"
DEST="${OPIE_DEST:-$HOME/Applications/Opie}"

echo "Installing Opie into: $DEST"

if ! command -v git >/dev/null 2>&1; then
  echo "Git isn't installed yet. A small Apple tool provides it — run:"
  echo "    xcode-select --install"
  echo "…click Install, wait for it to finish, then paste this command again."
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  echo "Found an existing copy — updating it…"
  git -C "$DEST" pull --ff-only || echo "(couldn't fast-forward; using current copy)"
else
  mkdir -p "$(dirname "$DEST")"
  echo "Downloading Opie (you may be asked to sign in to GitHub)…"
  git clone "$REPO" "$DEST"
fi

# Belt and suspenders: make sure nothing is quarantined (e.g. if DEST was once a
# ZIP). git clones aren't, but this keeps re-runs from any source clean.
xattr -dr com.apple.quarantine "$DEST" >/dev/null 2>&1 || true

echo
exec bash "$DEST/install.command"
