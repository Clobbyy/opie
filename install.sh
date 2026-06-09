#!/bin/bash
# Opie — one-command installer for macOS.
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/install.sh)"
#
# That single line does everything: downloads Opie, sets it up, starts the relay,
# and makes it run automatically at login. No Apple Developer ID, no Gatekeeper
# prompt (files fetched by curl/git aren't quarantined), and the core runs on the
# Mac's built-in Python 3 — nothing else to install. Re-run it any time to update.
set -euo pipefail

REPO="${OPIE_REPO:-https://github.com/Clobbyy/opie.git}"
BRANCH="${OPIE_REF:-main}"
SRC="${OPIE_SRC:-$HOME/Library/Application Support/Opie/src}"
APP="$HOME/Applications/Opie.app"
PYORG="https://www.python.org/downloads/macos/"

say()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
warn() { printf '  ⚠️  %s\n' "$*"; }
die()  { printf '\n❌  %s\n' "$*" >&2; exit 1; }

say "======================================================"
say "  Installing Opie — Siri voice control for ETC Eos/Nomad"
say "======================================================"

[ "$(uname -s)" = "Darwin" ] || die "Opie installs on macOS only."

# 1) git (ships with Apple's Command Line Tools).
step "Checking for git"
if ! command -v git >/dev/null 2>&1; then
  warn "git isn't installed. A one-time Apple download provides it."
  say  "    Run:  xcode-select --install"
  say  "    Click Install, let it finish, then paste the Opie command again."
  die  "git is required."
fi
say "  ✓ git present"

# 2) Download (or update) the code. git clones are never quarantined by macOS.
step "Downloading Opie"
mkdir -p "$(dirname "$SRC")"
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" pull --ff-only --quiet && say "  ✓ updated to the latest version" \
    || warn "couldn't fast-forward; keeping the current copy"
else
  git clone --branch "$BRANCH" --single-branch --quiet "$REPO" "$SRC" \
    || die "download failed. If the repo is private, make it public (Settings → General → Change visibility) so this command works for everyone."
  say "  ✓ downloaded to: $SRC"
fi
xattr -dr com.apple.quarantine "$SRC" >/dev/null 2>&1 || true

# 3) Find a Python 3. The relay needs only the standard library, so the Mac's
#    built-in python3 is fine. (The optional control panel wants Tk 8.6+, but the
#    voice relay — the part that matters — runs on any python3.)
step "Checking Python"
PY=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
  if [ -n "$c" ] && [ -x "$c" ] && "$c" -c 'import sys' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  warn "No python3 found. Apple's Command Line Tools include it."
  say  "    Run:  xcode-select --install   (then paste the Opie command again)"
  die  "python3 is required."
fi
say "  ✓ using $("$PY" --version 2>&1)  ($PY)"
PYTHONPATH="$SRC" "$PY" -c "import opie" >/dev/null 2>&1 || die "couldn't load the Opie code."

# 4) Optionally set the console IP now (works even via curl|bash, via /dev/tty).
NOMAD_IP=""
if { : >/dev/tty; } 2>/dev/null; then
  printf '\n  Console (Nomad/Eos) IP on the lighting network\n  [press Return to set it later in the app]: ' >/dev/tty
  read -r NOMAD_IP </dev/tty || NOMAD_IP=""
fi

# 5) Create the config (with a fresh token), record where the code lives, set IP.
step "Configuring"
INFO="$(PYTHONPATH="$SRC" "$PY" - "$SRC" "$NOMAD_IP" <<'PYEOF'
import sys
from opie import config
root, ip = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "").strip()
config.set_install_root(root)
path, created = config.ensure_exists()
cfg = config.load(path)
if ip:
    cfg["NOMAD_IP"] = ip
config.save(cfg, path)
print("CONFIG=" + path)
print("TOKEN=" + str(cfg.get("TOKEN", "")))
print("PORT=" + str(cfg.get("HTTP_PORT", 8765)))
print("IP=" + str(cfg.get("NOMAD_IP", "")))
print("NEW=" + ("1" if created else "0"))
PYEOF
)"
CONFIG="$(printf '%s\n' "$INFO" | sed -n 's/^CONFIG=//p')"
TOKEN="$(printf '%s\n'  "$INFO" | sed -n 's/^TOKEN=//p')"
PORT="$(printf '%s\n'   "$INFO" | sed -n 's/^PORT=//p')"
IPSET="$(printf '%s\n'  "$INFO" | sed -n 's/^IP=//p')"
[ -n "$CONFIG" ] || die "could not write the config."
say "  ✓ config: $CONFIG"
say "  ✓ console IP: ${IPSET:-not set yet}"

# 6) Run automatically at login (and start it now) via a launchd agent.
step "Starting Opie (now and at every login)"
if PYTHONPATH="$SRC" "$PY" - "$PY" "$CONFIG" <<'PYEOF' >/dev/null 2>&1
import sys
from opie import service
service.enable(python_exe=sys.argv[1], config_path=sys.argv[2])
PYEOF
then
  say "  ✓ relay running on http://localhost:$PORT  → OSC to ${IPSET:-127.0.0.1}:8000"
else
  warn "couldn't enable autostart automatically — open the app and click Start."
fi

# 7) A clickable "Opie" app to open the control panel (locally generated, so no
#    Gatekeeper prompt). It auto-finds a Tk-8.6+ Python; if none, it points the
#    user to python.org. The relay itself doesn't need it.
step "Adding the Opie app to your Applications"
mkdir -p "$APP/Contents/MacOS"
{
  cat <<'LSTART'
#!/bin/bash
tk_ok() { "$1" -c 'import sys,tkinter; sys.exit(0 if tkinter.TkVersion>=8.6 else 1)' >/dev/null 2>&1; }
PY=""
for c in /Library/Frameworks/Python.framework/Versions/3.1[0-9]/bin/python3 \
         /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.1[0-9] \
         /usr/local/bin/python3 "$(command -v python3 2>/dev/null)"; do
  [ -n "$c" ] && [ -x "$c" ] && tk_ok "$c" && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  osascript >/dev/null 2>&1 \
    -e 'set r to display dialog "Opie'"'"'s control panel needs Python 3 with Tk 8.6+ (the macOS built-in Python uses the old Tk 8.5). Install Python 3 from python.org (free), then open Opie again.\n\nThe voice relay keeps working without it." with title "Opie" buttons {"Open python.org","OK"} default button "OK" with icon caution' \
    -e 'if button returned of r is "Open python.org" then do shell script "open https://www.python.org/downloads/macos/"'
  exit 1
fi
LSTART
  printf 'export PYTHONPATH=%q\n' "$SRC"
  printf 'exec "$PY" -m opie.gui\n'
} > "$APP/Contents/MacOS/Opie"
chmod +x "$APP/Contents/MacOS/Opie"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Opie</string>
  <key>CFBundleDisplayName</key><string>Opie</string>
  <key>CFBundleIdentifier</key><string>com.opie.control</string>
  <key>CFBundleExecutable</key><string>Opie</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$(PYTHONPATH="$SRC" "$PY" -c 'import opie;print(opie.__version__)' 2>/dev/null || echo 0)</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
xattr -dr com.apple.quarantine "$APP" >/dev/null 2>&1 || true
say "  ✓ open it any time from Applications (or Spotlight: “Opie”)"

# 8) Open the control panel so the user can finish setup, then summarize.
open "$APP" >/dev/null 2>&1 || true

say ""
say "======================================================"
say "✅  Opie is installed and running."
say "======================================================"
say "  • Control panel: Applications → Opie (or Spotlight “Opie”)"
say "  • Relay URL:     http://localhost:$PORT/command"
say "  • Your token:    $TOKEN"
say ""
say "  Next: set your Console IP (if you skipped it) in the app, then build the"
say "  iPhone Shortcut from the app's “Test & Help → Phone setup info” — that"
say "  shows the exact URL + token for Siri."
say ""
say "  Update later:  re-paste the same install command."
say "  Uninstall:     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/uninstall.sh)\""
say ""
