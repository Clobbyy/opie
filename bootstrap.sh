#!/bin/bash
# Opie one-paste installer — no Apple Developer ID, no Gatekeeper prompt.
#
# Files fetched with `git` are NOT quarantined by macOS, so nothing here ever
# trips the "unidentified developer" block — unlike a .pkg/.dmg downloaded in a
# browser. This clones (or updates) Opie and runs its installer, which opens the
# control panel. You also get automatic updates (the clone self-updates on start).
#
# Run in Terminal (paste the whole line). The script can be served from a public
# Gist while the code repo stays private (see packaging/README.md):
#   /bin/bash -c "$(curl -fsSL <raw-bootstrap-url>)"
# …or, after cloning the repo yourself:
#   bash bootstrap.sh
#
# Override defaults with env vars:
#   OPIE_REPO=…  repo URL (default: the HTTPS clone of Clobbyy/opie)
#   OPIE_DEST=…  install folder (default: ~/Applications/Opie)
#   OPIE_REF=…   branch or tag to pin (default: the repo's default branch)
set -euo pipefail

REPO="${OPIE_REPO:-https://github.com/Clobbyy/opie.git}"
DEST="${OPIE_DEST:-$HOME/Applications/Opie}"
REF="${OPIE_REF:-}"

echo "Installing Opie into: $DEST"

if ! command -v git >/dev/null 2>&1; then
  echo
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
  echo "Downloading Opie (sign in to GitHub if you're asked)…"
  if [ -n "$REF" ]; then
    clone_ok() { git clone --branch "$REF" --single-branch "$REPO" "$DEST"; }
  else
    clone_ok() { git clone "$REPO" "$DEST"; }
  fi
  if ! clone_ok; then
    echo
    echo "❌  Couldn't download Opie."
    echo "    If this is a private repo, make sure your GitHub account has access"
    echo "    and is signed in. The simplest fix: install GitHub Desktop"
    echo "    (https://desktop.github.com), sign in, then paste this command again."
    exit 1
  fi
fi

# Belt and suspenders: make sure nothing is quarantined (e.g. if DEST was once a
# ZIP). git clones aren't, but this keeps re-runs from any source clean.
xattr -dr com.apple.quarantine "$DEST" >/dev/null 2>&1 || true

echo
exec bash "$DEST/install.command"
