#!/bin/sh
# X session entry: launch the cast app on the PiTFT (/dev/fb1).
# Installed to ~/.xinitrc by install_service.sh.
APP_DIR="@APP_DIR@"
LOG="${HOME}/.vinyl-xsession.log"

echo "=== vinyl xsession $(date) ===" >>"$LOG"
if bash "$APP_DIR/scripts/start_app.sh" >>"$LOG" 2>&1; then
  exit 0
fi

echo "start_app.sh failed — see $LOG" >>"$LOG"
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  "$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/show_boot_error.py" >>"$LOG" 2>&1 || true
fi
# Keep X open for SSH debugging.
sleep 3600
