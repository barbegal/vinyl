#!/usr/bin/env bash
# Disable Raspberry Pi Desktop and boot straight to multi-user + our app.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/enable_fast_boot.sh"
  exit 1
fi

echo "Setting default boot target to multi-user (no desktop)..."
systemctl set-default multi-user.target

echo "Stopping and disabling desktop session managers..."
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

# Do not use raspi-config B2 (console autologin) — it keeps getty@tty1 active on tty1.
# X runs on vt7 via the service; tty1 can stay for emergency console + SSH.

# Optional: skip waiting on boot splash (faster to usable screen).
if systemctl list-unit-files plymouth-quit-wait.service 2>/dev/null | grep -q plymouth; then
  systemctl disable --now plymouth-quit-wait.service 2>/dev/null || true
  echo "  disabled plymouth-quit-wait"
fi

# Allow the app user to start X without a desktop login session.
XWRAPPER="/etc/X11/Xwrapper.config"
if [[ -f "$XWRAPPER" ]] || [[ -d /etc/X11 ]]; then
  cat > "$XWRAPPER" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF
  echo "  configured $XWRAPPER"
fi

APP_USER="${SUDO_USER:-vinyl}"
if id "$APP_USER" &>/dev/null; then
  usermod -aG video,tty,input "$APP_USER" 2>/dev/null || true
  echo "  added $APP_USER to video,tty,input groups"
fi

echo ""
echo "Fast boot enabled. Default target is now: $(systemctl get-default)"
echo "Reboot to apply: sudo reboot"
