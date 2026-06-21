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

# Console autologin (no desktop) via raspi-config when available.
if command -v raspi-config >/dev/null; then
  echo "Setting boot behaviour to console autologin (raspi-config)..."
  raspi-config nonint do_boot_behaviour B2 2>/dev/null || \
    raspi-config nonint do_boot_behaviour B4 2>/dev/null || true
fi

# Optional: skip waiting on boot splash (faster to usable screen).
if systemctl list-unit-files plymouth-quit-wait.service 2>/dev/null | grep -q plymouth; then
  systemctl disable --now plymouth-quit-wait.service 2>/dev/null || true
  echo "  disabled plymouth-quit-wait"
fi

# Our xinit owns tty1 — getty on tty1 causes SIGHUP / VT fights.
if systemctl list-unit-files getty@tty1.service 2>/dev/null | grep -q getty; then
  systemctl disable --now getty@tty1.service 2>/dev/null || true
  echo "  disabled getty@tty1 (cast app uses tty1)"
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
