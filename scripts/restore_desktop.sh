#!/usr/bin/env bash
# Restore normal Raspberry Pi Desktop boot.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/restore_desktop.sh"
  exit 1
fi

echo "Stopping cast app service..."
systemctl disable --now pi-audio-cast-display.service 2>/dev/null || true

echo "Re-enabling desktop boot..."
systemctl set-default graphical.target

for svc in lightdm.service display-manager.service; do
  if systemctl list-unit-files "$svc" 2>/dev/null | grep -q "$svc"; then
    systemctl enable "$svc" 2>/dev/null || true
    echo "  enabled $svc"
  fi
done

if command -v raspi-config >/dev/null; then
  echo "Setting boot behaviour to desktop autologin (raspi-config)..."
  raspi-config nonint do_boot_behaviour B1 2>/dev/null || true
fi

systemctl enable --now display-manager.service 2>/dev/null || \
  systemctl enable --now lightdm.service 2>/dev/null || true

echo ""
echo "Desktop restore configured. Reboot: sudo reboot"
