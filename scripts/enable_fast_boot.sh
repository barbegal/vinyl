#!/usr/bin/env bash
# Configure fast, desktop-free boot: multi-user target + tty1 autologin.
# X is started from the login session (startx), so the user owns the VT.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/enable_fast_boot.sh"
  exit 1
fi

APP_USER="${1:-${SUDO_USER:-vinyl}}"

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
)
for svc in "${DESKTOP_SERVICES[@]}"; do
  if systemctl list-unit-files "$svc" 2>/dev/null | grep -q "$svc"; then
    systemctl disable --now "$svc" 2>/dev/null || true
    echo "  disabled $svc"
  fi
done

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

# Let console users start X (default on Pi; ensure it).
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

# Optional: skip waiting on boot splash (faster to usable screen).
if systemctl list-unit-files plymouth-quit-wait.service 2>/dev/null | grep -q plymouth; then
  systemctl disable --now plymouth-quit-wait.service 2>/dev/null || true
  echo "  disabled plymouth-quit-wait"
fi

systemctl daemon-reload

echo ""
echo "Fast boot configured. Default target: $(systemctl get-default)"
echo "Reboot to apply: sudo reboot"
