#!/bin/bash
# Opie uninstaller for macOS.
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/uninstall.sh)"
#
# Stops the relay, removes the autostart agent, the Opie app, and the downloaded
# code. Asks before deleting your settings (token/config) and logs.
set -euo pipefail

SRC="${OPIE_SRC:-$HOME/Library/Application Support/Opie/src}"
APP="$HOME/Applications/Opie.app"
SUPPORT="$HOME/Library/Application Support/Opie"
LOGS="$HOME/Library/Logs/Opie"
PLIST="$HOME/Library/LaunchAgents/com.opie.relay.plist"

say() { printf '%s\n' "$*"; }

say "==============================="
say "  Uninstalling Opie"
say "==============================="

# Stop + remove the autostart agent (use Opie's own code if it's still present).
PY="$(command -v python3 || true)"
if [ -n "$PY" ] && [ -d "$SRC" ] && PYTHONPATH="$SRC" "$PY" -c "import opie" >/dev/null 2>&1; then
  PYTHONPATH="$SRC" "$PY" -c "from opie import service; service.disable()" >/dev/null 2>&1 || true
fi
launchctl unload -w "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
say "  ✓ relay stopped and autostart removed"

rm -rf "$APP";  say "  ✓ removed the Opie app"
rm -rf "$SRC";  say "  ✓ removed the downloaded code"

ANS="N"
if { : >/dev/tty; } 2>/dev/null; then
  printf '\n  Also delete your settings (token + config) and logs? [y/N]: ' >/dev/tty
  read -r ANS </dev/tty || ANS="N"
fi
case "$ANS" in
  [yY]*) rm -rf "$SUPPORT" "$LOGS"; say "  ✓ settings and logs deleted" ;;
  *)     say "  • kept your settings: $SUPPORT/config.json" ;;
esac

say ""
say "✅  Opie uninstalled."
