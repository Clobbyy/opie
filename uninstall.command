#!/bin/bash
# Opie uninstaller — double-click in Finder.
# Removes the autostart agent and the launcher. Your config + logs are kept
# unless you choose to delete them.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SUPPORT="$HOME/Library/Application Support/Opie"
LOGS="$HOME/Library/Logs/Opie"
PLIST="$HOME/Library/LaunchAgents/com.opie.relay.plist"
PY="$(command -v python3 || true)"

echo "==============================="
echo "  Uninstalling Opie"
echo "==============================="
echo

# 1. Stop + remove the autostart agent.
if [ -n "$PY" ] && PYTHONPATH="$DIR" "$PY" -c "import opie" >/dev/null 2>&1; then
  PYTHONPATH="$DIR" "$PY" -c "from opie import service; service.disable()" 2>/dev/null || true
else
  launchctl unload -w "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
fi
echo "✓  Autostart agent removed."

# 2. Remove the launcher.
rm -f "$DIR/Opie Control.command"
echo "✓  Launcher removed."

# 3. Optionally delete config + logs.
echo
read -r -p "Also delete your config and logs (token, settings)? [y/N] " ans
case "$ans" in
  [yY]*)
    rm -rf "$APP_SUPPORT" "$LOGS"
    echo "✓  Config and logs deleted."
    ;;
  *)
    echo "•  Kept your config: $APP_SUPPORT/config.json"
    ;;
esac

echo
echo "✅  Opie uninstalled. (You can delete this folder too.)"
read -r -p "Press Return to close."
