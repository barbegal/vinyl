#!/usr/bin/env bash
# Restore normal Raspberry Pi Desktop boot (undo kiosk autologin + startx).
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/restore_desktop.sh"
  exit 1
fi

APP_USER="${1:-${SUDO_USER:-vinyl}}"
USER_HOME="$(eval echo "~$APP_USER")"

echo "Removing any cast app systemd unit..."
systemctl disable --now pi-audio-cast-display.service 2>/dev/null || true
rm -f /etc/systemd/system/pi-audio-cast-display.service

echo "Removing tty1 autologin override..."
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
rmdir /etc/systemd/system/getty@tty1.service.d 2>/dev/null || true

echo "Removing startx guard from $USER_HOME/.bash_profile..."
PROFILE="$USER_HOME/.bash_profile"
if [[ -f "$PROFILE" ]]; then
  sed -i '/# >>> pi-audio-cast-display startx >>>/,/# <<< pi-audio-cast-display startx <<</d' "$PROFILE"
fi

echo "Re-enabling desktop boot..."
systemctl set-default graphical.target
for svc in lightdm.service display-manager.service; do
  if systemctl list-unit-files "$svc" 2>/dev/null | grep -q "$svc"; then
    systemctl enable "$svc" 2>/dev/null || true
    echo "  enabled $svc"
  fi
done
if command -v raspi-config >/dev/null; then
  raspi-config nonint do_boot_behaviour B1 2>/dev/null || true
fi
systemctl enable --now display-manager.service 2>/dev/null || \
  systemctl enable --now lightdm.service 2>/dev/null || true

systemctl daemon-reload

echo ""
echo "Desktop restore configured. Reboot: sudo reboot"
