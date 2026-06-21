#!/usr/bin/env bash
# Emergency recovery when the PiTFT is blank after a bad overlay/rotation change.
# Restores the capacitive overlay (display was working before 28r was tried).
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/recover_display.sh"
  exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROTATE="${1:-90}"

echo "=== PiTFT display recovery (capacitive 28c, rotate=${ROTATE}) ==="
echo "If you have resistive hardware, use: sudo $0 ${ROTATE} 28r"

PANEL="${2:-28c}"
if [[ -x "$APP_DIR/scripts/setup_pitft.sh" ]]; then
  "$APP_DIR/scripts/setup_pitft.sh" "$ROTATE" "$PANEL" "${SUDO_USER:-vinyl}"
else
  echo "ERROR: setup_pitft.sh not found at $APP_DIR"
  exit 1
fi

echo ""
echo "=== Quick checks ==="
[[ -e /dev/fb1 ]] && echo "/dev/fb1: OK" || echo "/dev/fb1: MISSING — overlay did not load; check config.txt on next boot"
ls -la /dev/fb* 2>/dev/null | sed 's/^/  /' || true

echo ""
echo "Reboot now: sudo reboot"
echo "If still blank after reboot, SSH in and paste:"
echo "  ls -la /dev/fb*"
echo "  grep pitft /boot/firmware/config.txt /boot/config.txt 2>/dev/null"
