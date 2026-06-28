#!/usr/bin/env bash
# Set up desktop-free kiosk boot: tty1 autologin -> startx -> cast app.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$USER_NAME")"
XINITRC_TEMPLATE="$APP_DIR/scripts/kiosk_xinitrc.sh"

if [[ "$USER_NAME" == "root" ]]; then
  echo "Run as your normal user (not root): ./scripts/install_service.sh"
  exit 1
fi

echo "=== Installing X packages (xinit, Xorg) ==="
sudo apt-get install -y xinit xserver-xorg x11-xserver-utils

for cmd in xinit startx Xorg; do
  if ! command -v "$cmd" >/dev/null; then
    echo "ERROR: $cmd not found after apt install"
    exit 1
  fi
done

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "ERROR: venv missing at $APP_DIR/.venv"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

chmod +x "$APP_DIR/scripts/"*.sh
chmod +x "$APP_DIR/scripts/show_boot_error.py" 2>/dev/null || true

echo "=== Removing any old systemd unit ==="
sudo systemctl disable --now pi-audio-cast-display.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/pi-audio-cast-display.service
sudo systemctl daemon-reload 2>/dev/null || true

echo "=== Configuring fast boot + tty1 autologin + profile.d startx ==="
sudo "$APP_DIR/scripts/enable_fast_boot.sh" "$USER_NAME" "$APP_DIR"

echo "=== Writing $USER_HOME/.xinitrc ==="
./scripts/refresh_xinitrc.sh
chmod +x "$USER_HOME/.xinitrc"

STARTX_GUARD='
# >>> pi-audio-cast-display startx >>>
# Only local tty1 — never SSH (SSH_CONNECTION is set for remote logins).
if [ -z "${DISPLAY:-}" ] \
   && [ -z "${SSH_CONNECTION:-}" ] \
   && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
  [ -e /dev/fb1 ] && export FRAMEBUFFER=/dev/fb1
  exec startx
fi
# <<< pi-audio-cast-display startx <<<
'
MARKER="# >>> pi-audio-cast-display startx >>>"

for PROFILE in "$USER_HOME/.profile" "$USER_HOME/.bash_profile"; do
  if ! grep -qF "$MARKER" "$PROFILE" 2>/dev/null; then
    printf '\n%s\n' "$STARTX_GUARD" >> "$PROFILE"
    echo "  appended startx guard to $PROFILE"
  else
    echo "  startx guard already in $PROFILE"
  fi
done

echo ""
echo "=== Kiosk boot configured ==="
echo "Default target: $(systemctl get-default)"
echo "tty1 autologin: $USER_NAME"
echo "startx hooks:   /etc/profile.d/vinyl-kiosk.sh + ~/.profile (FRAMEBUFFER=/dev/fb1)"
echo "App entry:      $USER_HOME/.xinitrc"
echo "PiTFT/X:        /etc/X11/xorg.conf.d/99-pitft.conf (fbdev -> /dev/fb1)"
echo ""
echo "Reboot to test: sudo reboot"
echo "If panel is upside down: sudo $APP_DIR/scripts/setup_pitft.sh 90 28r   # or 270, then reboot"
echo "Restore desktop: sudo $APP_DIR/scripts/restore_desktop.sh"
