#!/bin/bash
# Opie installer — double-click this file in Finder. No internet required.
# Runs the app straight from this folder using the Mac's built-in Python 3.
# Keep this folder where it is afterward; the app runs from here.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="$HOME/Library/Logs/Opie"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/install.log"
PYORG="https://www.python.org/downloads/macos/"

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

# 1. Need *some* python3 just to run the checks (Command Line Tools is fine here).
if ! command -v python3 >/dev/null 2>&1 || ! python3 --version >/dev/null 2>&1; then
  echo "Python 3 isn't ready yet. In Terminal run:"
  echo "    xcode-select --install"
  fail "Install the developer tools, then double-click install.command again."
fi

# 2. The control panel needs a Python whose Tk is >= 8.6. The macOS system Tk is
#    8.5 and crashes on recent macOS, so we hunt for a good one (python.org / brew).
tk_ok() { "$1" -c 'import sys,tkinter; sys.exit(0 if tkinter.TkVersion>=8.6 else 1)' >/dev/null 2>&1; }
pick_python() {
  local c
  for c in \
      /Library/Frameworks/Python.framework/Versions/3.1[0-9]/bin/python3 \
      /opt/homebrew/bin/python3 \
      /opt/homebrew/bin/python3.1[0-9] \
      /usr/local/bin/python3 \
      "$(command -v python3 2>/dev/null)"; do
    [ -n "$c" ] && [ -x "$c" ] || continue
    if tk_ok "$c"; then echo "$c"; return 0; fi
  done
  return 1
}

PY="$(pick_python || true)"
if [ -z "$PY" ]; then
  echo "⚠️   The control panel needs Tk 8.6+, which the Mac's built-in Python lacks"
  echo "    (its Tk 8.5 crashes on recent macOS)."
  echo
  if command -v brew >/dev/null 2>&1; then
    read -r -p "Homebrew is installed — install a compatible Python now (brew install python-tk)? [Y/n] " ans
    case "$ans" in
      [nN]*) ;;
      *) echo "Installing (a few minutes)…"; brew install python-tk && PY="$(pick_python || true)" ;;
    esac
  fi
fi
if [ -z "$PY" ]; then
  echo
  echo "Install Python 3 from python.org (free, one download):"
  echo "    $PYORG"
  read -r -p "Open that page now? [Y/n] " ans
  case "$ans" in [nN]*) ;; *) open "$PYORG" ;; esac
  echo "After installing it, double-click install.command again."
  fail "No Python with a working Tk found yet."
fi
echo "✓  Using $("$PY" --version 2>&1)  ($PY)  — Tk OK"

# 3. If this folder is a Git clone, grab the latest code now (so re-running this
#    installer also updates Opie). Best-effort: offline / non-clone just skips.
if [ -d "$DIR/.git" ] && command -v git >/dev/null 2>&1; then
  echo "Checking for the latest Opie…"
  if git -C "$DIR" pull --ff-only --quiet 2>/dev/null; then
    echo "✓  Up to date ($(git -C "$DIR" rev-parse --short HEAD 2>/dev/null))"
    GIT_CLONE=1
  else
    echo "•  Couldn't auto-pull (offline or local changes) — using this copy."
    GIT_CLONE=1
  fi
else
  echo "•  Not a Git clone — automatic updates won't be available."
  echo "   (Clone with Git instead of downloading a ZIP to get auto-updates.)"
  GIT_CLONE=0
fi

# 4. The opie package must import from this folder.
if ! PYTHONPATH="$DIR" "$PY" -c "import opie" >/dev/null 2>&1; then
  fail "Couldn't load the Opie code from this folder."
fi
echo "✓  Opie code loads"

# 5. Create the config (with a strong token) and record where the code lives.
if ! PYTHONPATH="$DIR" "$PY" - "$DIR" <<'PYEOF'
import sys
from opie import config
config.set_install_root(sys.argv[1])
path, created = config.ensure_exists()
print(("•  Created config: " if created else "•  Config exists:  ") + path)
print("•  Recorded code location for autostart + auto-update")
PYEOF
then
  fail "Could not write the config."
fi

# 6. Double-clickable launcher in this folder.
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
if [ "${GIT_CLONE:-0}" = "1" ]; then
  echo "   • Auto-update is ON: Opie keeps itself current from GitHub."
fi
echo "   • To remove Opie later, double-click uninstall.command"
cd "$DIR"
nohup "$PY" -m opie.gui >/dev/null 2>&1 &
disown 2>/dev/null || true
sleep 1
pause
