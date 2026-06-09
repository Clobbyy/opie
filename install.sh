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

# 3) Find a Python 3. Both the relay AND the browser control panel use only the
#    standard library, so the Mac's built-in python3 is all you need — nothing to
#    install (no Tk, no python.org, no Homebrew).
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

# 6) Start the relay now. It runs as a detached, log-captured background process
#    managed by the panel — reliable and visible, no fragile launchd dependency.
#    (Any old/broken launchd agent from a previous install is cleared first.
#    Boot-persistence is an opt-in "Autostart at login" toggle in the panel.)
step "Starting the relay"
PYTHONPATH="$SRC" "$PY" - "$CONFIG" <<'PYEOF' >/dev/null 2>&1 || true
import sys
try:
    from opie import service
    service.disable()      # clear any prior launchd agent so it can't conflict
except Exception:
    pass
from opie.panel import Controller
Controller(sys.argv[1]).ensure_running()
PYEOF
sleep 2
if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
  say "  ✓ relay running on http://localhost:$PORT  → OSC to ${IPSET:-127.0.0.1}:8000"
else
  warn "relay didn't answer yet — open Opie and click Start; the panel shows any error."
fi

# 7) A clickable "Opie" app that opens the control panel in your browser. The
#    panel is pure standard library, so it runs on ANY python3 — no Tk needed.
#    Generated locally, so it carries no quarantine flag (no Gatekeeper prompt).
step "Adding the Opie app to your Applications"
mkdir -p "$APP/Contents/MacOS"
{
  cat <<'LSTART'
#!/bin/bash
# Opie.app — opens the browser control panel (Tk not required).
PY=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
  [ -n "$c" ] && [ -x "$c" ] && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  osascript >/dev/null 2>&1 \
    -e 'display dialog "Opie needs Python 3, which comes with Apple'"'"'s Command Line Tools.\n\nOpen Terminal and run:  xcode-select --install" with title "Opie" buttons {"OK"} default button "OK" with icon caution'
  exit 1
fi
LSTART
  printf 'export PYTHONPATH=%q\n' "$SRC"
  # Launch the panel detached so the .app itself doesn't linger in the Dock.
  printf 'nohup "$PY" -m opie.panel >/dev/null 2>&1 &\n'
  printf 'exit 0\n'
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
say "  • Control panel: open “Opie” (Applications / Spotlight) — it opens in your browser"
say "  • Relay URL:     http://localhost:$PORT/command"
say "  • Your token:    $TOKEN"
say ""
say "  Next: in the panel, set your Console IP (if you skipped it), then build the"
say "  iPhone Shortcut using the URL + token shown under “Test & phone setup”."
say "  Tip:  turn on “Autostart at login” in the panel to keep the relay running"
say "        after a reboot."
say ""
say "  Update later:  re-paste the same install command."
say "  Uninstall:     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/uninstall.sh)\""
say ""
