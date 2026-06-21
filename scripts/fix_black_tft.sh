#!/usr/bin/env bash
# Fix black PiTFT when X + app run but the panel stays blank.
# Common cause: dtoverlay=...,drm in config.txt (breaks Xorg fbdev).
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/fix_black_tft.sh [rotation] [28c|28r]"
  exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROTATE="${1:-270}"
PANEL="${2:-28r}"

CONFIG=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && CONFIG="$p" && break
done

echo "=== vinyl fix_black_tft (rotate=${ROTATE} panel=${PANEL}) ==="

if [[ -n "$CONFIG" ]]; then
  if grep -qE '^dtoverlay=pitft28.*drm' "$CONFIG"; then
    echo "  removing ,drm from pitft overlay in $CONFIG (incompatible with X fbdev)"
    sed -i '/^dtoverlay=pitft28/s/,drm//g; s/drm,//g' "$CONFIG"
  fi
  echo "  overlay line:"
  grep '^dtoverlay=pitft28' "$CONFIG" | sed 's/^/    /' || echo "    (none — setup_pitft will add one)"
fi

"$APP_DIR/scripts/setup_pitft.sh" "$ROTATE" "$PANEL" "${SUDO_USER:-vinyl}"

ENV_FILE="$APP_DIR/.env"
if [[ -f "$ENV_FILE" ]] && grep -qE '^VINYL_BOOT_DEBUG=1' "$ENV_FILE"; then
  echo ""
  echo "  Tip: set VINYL_BOOT_DEBUG=0 in .env if the panel flickers or stays black"
  echo "       (boot debug + fbdev can fight over the framebuffer colormap)."
fi

echo ""
echo "Reboot: sudo reboot"
echo ""
echo "After reboot, if still black:"
echo "  DISPLAY=:0 xdpyinfo | grep dimensions   # expect 320x240"
echo "  grep fbdev ~/.local/share/xorg/Xorg.0.log | tail -5"
echo "  Plug in HDMI — if UI appears there, X is on the wrong framebuffer."
