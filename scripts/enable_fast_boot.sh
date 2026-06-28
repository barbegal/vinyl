#!/usr/bin/env bash
# Configure fast, desktop-free boot: multi-user target + tty1 autologin + startx.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/enable_fast_boot.sh"
  exit 1
fi

APP_USER="${1:-${SUDO_USER:-vinyl}}"
APP_DIR="${2:-/home/$APP_USER/Desktop/vinyl}"

echo "Setting default boot target to multi-user (no desktop)..."
systemctl set-default multi-user.target

echo "Disabling desktop session managers..."
DESKTOP_SERVICES=(
  display-manager.service
  lightdm.service
  gdm3.service
  sddm.service
  wayvnc.service
  rpd-x.service
  rpd-wayland.service
  labwc.service
  graphical.service
  splash.service
)
for svc in "${DESKTOP_SERVICES[@]}"; do
  if systemctl list-unit-files "$svc" 2>/dev/null | grep -q "$svc"; then
    systemctl disable --now "$svc" 2>/dev/null || true
    echo "  disabled $svc"
  fi
done

# Prevent desktop from being pulled in on next enable attempt.
for svc in lightdm.service display-manager.service; do
  if systemctl list-unit-files "$svc" 2>/dev/null | grep -q "$svc"; then
    systemctl mask "$svc" 2>/dev/null || true
    echo "  masked $svc"
  fi
done

echo "Disabling Plymouth boot splash (\"Welcome to Raspberry Pi Desktop\")..."
PLYMOUTH_SERVICES=(
  plymouth-start.service
  plymouth-read-write.service
  plymouth-quit.service
  plymouth-quit-wait.service
)
for svc in "${PLYMOUTH_SERVICES[@]}"; do
  if systemctl list-unit-files "$svc" 2>/dev/null | grep -q "$svc"; then
    systemctl disable --now "$svc" 2>/dev/null || true
    echo "  disabled $svc"
  fi
done

if command -v raspi-config >/dev/null; then
  raspi-config nonint do_boot_splash 1 2>/dev/null || true
  raspi-config nonint do_boot_behaviour B2 2>/dev/null || true
  echo "  raspi-config: splash off, console autologin"
fi

echo "Enabling tty1 autologin for $APP_USER..."
OVERRIDE_DIR="/etc/systemd/system/getty@tty1.service.d"
mkdir -p "$OVERRIDE_DIR"
cat > "$OVERRIDE_DIR/autologin.conf" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $APP_USER --noclear %I \$TERM
EOF
systemctl enable getty@tty1.service 2>/dev/null || true
echo "  wrote $OVERRIDE_DIR/autologin.conf"

echo "Installing /etc/profile.d/vinyl-kiosk.sh (startx on tty1 login)..."
cat > /etc/profile.d/vinyl-kiosk.sh <<EOF
# Auto-start cast app X session on tty1 only — never on SSH.
if [ -z "\${SSH_CONNECTION:-}" ] \\
   && [ "\$(tty 2>/dev/null)" = "/dev/tty1" ] \\
   && [ -z "\${DISPLAY:-}" ] \\
   && [ "\$(id -un)" = "$APP_USER" ] \\
   && [ -f "$APP_DIR/scripts/start_app.sh" ]; then
  printf '\nVinyl kiosk\nStarting X on PiTFT…\n' > /dev/tty1 2>/dev/null || true
  # PiTFT is an SPI framebuffer; tell Xorg to render to it.
  [ -e /dev/fb1 ] && export FRAMEBUFFER=/dev/fb1
  exec startx
fi
EOF
chmod 644 /etc/profile.d/vinyl-kiosk.sh

XWRAPPER="/etc/X11/Xwrapper.config"
if [[ -d /etc/X11 ]]; then
  cat > "$XWRAPPER" <<'EOF'
allowed_users=console
needs_root_rights=yes
EOF
  echo "  configured $XWRAPPER"
fi

if id "$APP_USER" &>/dev/null; then
  usermod -aG video,render,tty,input,audio "$APP_USER" 2>/dev/null || true
  echo "  added $APP_USER to video,render,tty,input,audio groups"
fi

if [[ -x "$APP_DIR/scripts/setup_pitft.sh" ]]; then
  echo "Configuring Adafruit PiTFT (fb1 + rotation + touch)..."
  "$APP_DIR/scripts/setup_pitft.sh" "${PITFT_ROTATE:-270}" "${PITFT_TYPE:-28r}" "$APP_USER" || true
fi

systemctl daemon-reload

echo ""
echo "Fast boot configured. Default target: $(systemctl get-default)"
echo "Reboot to apply: sudo reboot"
