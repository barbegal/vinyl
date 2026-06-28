#!/bin/sh
# X session entry: launch the cast app on the PiTFT (/dev/fb1).
# Installed to ~/.xinitrc by install_service.sh.
APP_DIR="@APP_DIR@"
LOG="${HOME}/.vinyl-xsession.log"
# shellcheck source=boot_milestone.sh
. "$APP_DIR/scripts/boot_milestone.sh"

# Load .env so remote-mirror settings (VINYL_MIRROR_VNC etc.) are available here.
if [ -f "$APP_DIR/.env" ]; then
  set -a
  # shellcheck source=load_env.sh
  VINYL_ENV_FILE="$APP_DIR/.env" . "$APP_DIR/scripts/load_env.sh"
  set +a
fi

boot_milestone_reset
boot_milestone "xsession start"
echo "=== vinyl xsession $(date) ===" >>"$LOG"
boot_milestone "startx invoked xinitrc"
echo "Vinyl: X session starting…" >/dev/tty1 2>/dev/null || true

# Optional: mirror this TFT X session (:0) for remote viewing via Raspberry Pi
# Connect / VNC. Enable with scripts/setup_rpconnect.sh (sets VINYL_MIRROR_VNC=1).
if [ "${VINYL_MIRROR_VNC:-0}" = "1" ] && command -v x11vnc >/dev/null 2>&1; then
  boot_milestone "starting x11vnc mirror"
  VNC_ARGS="-display :0 -forever -shared -noxdamage -repeat -bg -rfbport ${VINYL_VNC_PORT:-5900} -o ${HOME}/.vinyl-vnc.log"
  [ "${VINYL_VNC_LOCALHOST:-1}" = "1" ] && VNC_ARGS="$VNC_ARGS -localhost"
  if [ -n "${VINYL_VNC_PASSWORD:-}" ]; then
    VNC_ARGS="$VNC_ARGS -passwd ${VINYL_VNC_PASSWORD}"
  else
    VNC_ARGS="$VNC_ARGS -nopw"
  fi
  # shellcheck disable=SC2086
  x11vnc $VNC_ARGS >>"$LOG" 2>&1 || echo "x11vnc mirror failed to start" >>"$LOG"
fi

if bash "$APP_DIR/scripts/start_app.sh" >>"$LOG" 2>&1; then
  exit 0
fi

echo "start_app.sh failed — see $LOG" >>"$LOG"
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  "$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/show_boot_error.py" "start_app.sh failed" >>"$LOG" 2>&1 || true
fi
# Keep X open for SSH debugging.
sleep 3600
