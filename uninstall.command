#!/bin/bash
# Opie uninstaller — double-click this file in Finder.
# Removes the autostart agent and the private environment.
# Your config + logs are kept unless you choose to delete them.
set -uo pipefail

APP_SUPPORT="$HOME/Library/Application Support/Opie"
LOGS="$HOME/Library/Logs/Opie"
VENV="$APP_SUPPORT/venv"
PLIST="$HOME/Library/LaunchAgents/com.opie.relay.plist"

echo "==============================="
echo "  Uninstalling Opie"
echo "==============================="
echo

# 1. Stop + remove the autostart agent (use the venv if it's still there)
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" -c "from opie import service; service.disable()" 2>/dev/null || true
else
  launchctl unload -w "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
fi
echo "✓  Autostart agent removed."

# 2. Remove the environment + launcher
rm -rf "$VENV"
rm -f "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/Opie Control.command"
echo "✓  Environment removed."

# 3. Optionally delete config + logs
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
echo "✅  Opie uninstalled. (You can delete this project folder too.)"
read -r -p "Press Return to close."
