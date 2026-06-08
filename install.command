#!/bin/bash
# Opie installer — double-click this file in Finder. No internet required.
# Runs the app straight from this folder using the Mac's built-in Python 3.
# Keep this folder where it is afterward; the app runs from here.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="$HOME/Library/Logs/Opie"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/install.log"

# Mirror all output to a log file AND always pause, so the window never just
# vanishes on an error.
exec > >(tee -a "$LOG") 2>&1
pause() { echo; echo "—— Press Return to close ——"; read -r _ 2>/dev/null || true; }
fail() { echo; echo "❌  $1"; echo "    Full log: $LOG"; pause; exit 1; }

echo "======================================================"
echo "  Installing Opie — voice control for ETC Eos/Nomad"
echo "  $(date)"
echo "======================================================"
echo "Folder: $DIR"
echo

# 1. Python 3 must be present and runnable (Command Line Tools).
if ! command -v python3 >/dev/null 2>&1 || ! python3 --version >/dev/null 2>&1; then
  echo "Python 3 isn't ready yet. In Terminal run:"
  echo "    xcode-select --install"
  fail "Install the developer tools, then double-click install.command again."
fi
PY="$(command -v python3)"
echo "✓  $("$PY" --version)   ($PY)"

# 2. Tkinter (the GUI toolkit) must work.
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
  echo "This python3 has no Tk, so the control panel can't open."
  echo "Fix it with either:"
  echo "   • install Python 3 from python.org   (recommended), or"
  echo "   • brew install python-tk"
  echo "The relay still works headless:  PYTHONPATH=\"$DIR\" \"$PY\" -m opie"
  fail "Tk (Tkinter) is missing from this Python."
fi
echo "✓  Tkinter present"

# 3. The opie package must import from this folder.
if ! PYTHONPATH="$DIR" "$PY" -c "import opie" >/dev/null 2>&1; then
  fail "Couldn't load the Opie code from this folder."
fi
echo "✓  Opie code loads"

# 4. Create the config (with a strong token) and record where the code lives.
if ! PYTHONPATH="$DIR" "$PY" - "$DIR" <<'PYEOF'
import sys
from opie import config
config.set_install_root(sys.argv[1])
path, created = config.ensure_exists()
print(("•  Created config: " if created else "•  Config exists:  ") + path)
print("•  Recorded code location for autostart")
PYEOF
then
  fail "Could not write the config."
fi

# 5. Double-clickable launcher in this folder.
LAUNCH="$DIR/Opie Control.command"
cat > "$LAUNCH" <<LEOF
#!/bin/bash
cd "$DIR" && exec "$PY" -m opie.gui
LEOF
chmod +x "$LAUNCH"
echo "✓  Created 'Opie Control.command' (your shortcut)"

echo
echo "✅  Done — opening Opie Control now."
echo "   • Re-open any time with 'Opie Control.command' in this folder."
echo "   • Keep this folder where it is; the app runs from here."
echo "   • To remove Opie later, double-click uninstall.command"
cd "$DIR"
nohup "$PY" -m opie.gui >/dev/null 2>&1 &
disown 2>/dev/null || true
sleep 1
pause
