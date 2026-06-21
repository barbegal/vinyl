#!/bin/sh
# X session entry: launch the cast app on the PiTFT (/dev/fb1).
# Installed to ~/.xinitrc by install_service.sh.
APP_DIR="@APP_DIR@"
LOG="${HOME}/.vinyl-xsession.log"

echo "=== vinyl xsession $(date) ===" >>"$LOG"
if "$APP_DIR/scripts/start_app.sh" >>"$LOG" 2>&1; then
  exit 0
fi

echo "start_app.sh failed — see $LOG" >>"$LOG"
# Keep X open so the panel isn't blank-black while you SSH in to read the log.
sleep 3600
