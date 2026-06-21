#!/usr/bin/env bash
# Flip PiTFT 90° ↔ 270° (common fix when the image is upside down).
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PANEL="${1:-28c}"
CONFIG=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && CONFIG="$p" && break
done
CURRENT=""
if [[ -n "$CONFIG" ]]; then
  CURRENT="$(grep -oE 'rotate=[0-9]+' "$CONFIG" | head -1 | cut -d= -f2 || true)"
fi
if [[ "$CURRENT" == "90" ]]; then
  NEW=270
else
  NEW=90
fi
echo "Current rotate=${CURRENT:-unknown} → switching to rotate=${NEW}"
sudo "$APP_DIR/scripts/setup_pitft.sh" "$NEW" "$PANEL"
echo "Reboot: sudo reboot"
