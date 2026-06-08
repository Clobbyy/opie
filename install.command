#!/bin/bash
# Opie installer — double-click this file in Finder.
# Sets up a private Python environment, creates your config (with a fresh token),
# and opens the Opie Control panel. Re-run any time to update.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SUPPORT="$HOME/Library/Application Support/Opie"
VENV="$APP_SUPPORT/venv"

echo "======================================================"
echo "  Installing Opie — voice control for ETC Eos/Nomad"
echo "======================================================"
echo

# 1. Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌  Python 3 is not installed."
  echo "    Run this in Terminal, then double-click install.command again:"
  echo "        xcode-select --install"
  echo
  read -r -p "Press Return to close."
  exit 1
fi
echo "✓  Found $(python3 --version)"

# 2. Tkinter (GUI toolkit) sanity check
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "⚠️   Your python3 has no Tk (the GUI won't open)."
  echo "    If you installed Python via Homebrew, run:  brew install python-tk"
  echo "    The relay itself will still work from the command line."
fi

# 3. Virtual environment + install
echo "•  Creating environment at: $VENV"
mkdir -p "$APP_SUPPORT"
python3 -m venv "$VENV"
echo "•  Installing Opie…"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install "$DIR"

# 4. First-run config (auto-generates a strong token)
"$VENV/bin/python" - <<'PY'
from opie import config
path, created = config.ensure_exists()
print(("•  Created config: " if created else "•  Config already exists: ") + path)
PY

# 5. Convenience launcher in the repo folder
cat > "$DIR/Opie Control.command" <<LAUNCH
#!/bin/bash
exec "$VENV/bin/opie-gui"
LAUNCH
chmod +x "$DIR/Opie Control.command"

echo
echo "✅  Done."
echo "   • Opening Opie Control now."
echo "   • Next time, double-click  'Opie Control.command'  (in this folder)."
echo "   • To remove Opie, double-click  uninstall.command"
echo
"$VENV/bin/opie-gui" >/dev/null 2>&1 &
sleep 1
