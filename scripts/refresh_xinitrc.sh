#!/usr/bin/env bash
# Re-install ~/.xinitrc from template and show the last app crash log.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_HOME="${HOME}"
TEMPLATE="$APP_DIR/scripts/kiosk_xinitrc.sh"

sed "s|@APP_DIR@|$APP_DIR|g" "$TEMPLATE" > "$USER_HOME/.xinitrc"
chmod +x "$USER_HOME/.xinitrc"
echo "Updated $USER_HOME/.xinitrc"

LOG="$USER_HOME/.vinyl-xsession.log"
if [[ -f "$LOG" ]]; then
  echo ""
  echo "=== last $LOG ==="
  tail -40 "$LOG"
else
  echo "No log yet at $LOG (run startx or reboot)"
fi
