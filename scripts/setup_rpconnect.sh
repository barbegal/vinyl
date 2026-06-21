#!/usr/bin/env bash
# Mirror the PiTFT X session for remote viewing via Raspberry Pi Connect + VNC.
#
# Why VNC: the kiosk renders to an Xorg session on :0 (SPI framebuffer /dev/fb1).
# Raspberry Pi Connect "Screen sharing" only captures *Wayland* desktops, so it
# cannot show this X11/fbdev session directly. To mirror the *exact* TFT we attach
# x11vnc to :0. Raspberry Pi Connect stays enabled for remote shell + device
# management (and you can tunnel the VNC port through it).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-$USER}"
APP_UID="$(id -u "$APP_USER")"
ENV_FILE="$APP_DIR/.env"

echo "=== Installing packages (x11vnc, rpi-connect) ==="
sudo apt-get update -y || true
sudo apt-get install -y x11vnc || echo "WARN: x11vnc install failed"
# rpi-connect-lite = remote shell without the desktop dependency; fall back to full.
if ! sudo apt-get install -y rpi-connect-lite 2>/dev/null; then
  sudo apt-get install -y rpi-connect || echo "WARN: rpi-connect install failed"
fi

echo "=== Enabling Raspberry Pi Connect (user service for $APP_USER) ==="
# rpi-connect is a per-user service; linger keeps it running without an active login.
sudo loginctl enable-linger "$APP_USER" 2>/dev/null || true
if sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$APP_UID" \
     systemctl --user enable --now rpi-connect 2>/dev/null; then
  echo "  rpi-connect user service enabled"
else
  echo "  enable manually as $APP_USER: systemctl --user enable --now rpi-connect"
fi

echo "=== Enabling VNC mirror of the TFT (:0) in $ENV_FILE ==="
touch "$ENV_FILE"
set_env() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}
default_env() { grep -qE "^$1=" "$ENV_FILE" || set_env "$1" "$2"; }

set_env VINYL_MIRROR_VNC 1
default_env VINYL_VNC_PORT 5900
default_env VINYL_VNC_LOCALHOST 1
default_env VINYL_VNC_PASSWORD ""

# Refresh ~/.xinitrc so the mirror-launch block is present.
"$APP_DIR/scripts/refresh_xinitrc.sh" >/dev/null 2>&1 || true

VNC_PORT="$(grep -E '^VINYL_VNC_PORT=' "$ENV_FILE" | cut -d= -f2)"
VNC_PORT="${VNC_PORT:-5900}"

cat <<EOF

=== Done. Next steps ===
1) Sign in to Raspberry Pi Connect (one time), then approve the device:
     rpi-connect signin
     # browser: https://connect.raspberrypi.com

2) Reboot (or restart X) to start the TFT mirror:
     sudo reboot

3) View the exact TFT remotely (x11vnc on :0):
   - Tunnel the VNC port (localhost-only by default) and open any VNC viewer:
       ssh -L ${VNC_PORT}:localhost:${VNC_PORT} ${APP_USER}@<pi-host>
       # then connect your VNC client to localhost:${VNC_PORT}
   - Or, for direct LAN access, set in $ENV_FILE:
       VINYL_VNC_LOCALHOST=0
       VINYL_VNC_PASSWORD=<simple-password>   # recommended when on LAN
     then reboot.

Notes:
- Raspberry Pi Connect screen-sharing needs a Wayland desktop; this kiosk is X11
  on /dev/fb1, so we mirror with x11vnc (shows precisely what's on the TFT).
- Connect remote shell still works for SSH-less access and tunneling.
- Check status any time: ./scripts/diagnose_boot.sh
EOF
