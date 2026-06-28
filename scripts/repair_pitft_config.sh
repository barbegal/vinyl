#!/usr/bin/env bash
# Reset PiTFT lines in config.txt to a single known-good block (fixes kernel bind / overlay stack).
# Strips ALL gpio-key overlays and duplicate pitft lines, then writes one vinyl block.
#
# Usage: sudo bash scripts/repair_pitft_config.sh [rotation] [28r|28c]
set -euo pipefail

ROTATE="${1:-270}"
PANEL="${2:-28r}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/repair_pitft_config.sh [rotation] [28r|28c]"
  exit 1
fi

case "$ROTATE" in
  0|90|180|270) ;;
  *) echo "ERROR: rotation must be 0, 90, 180, or 270"; exit 1 ;;
esac
case "$PANEL" in
  28c|28r) ;;
  *) echo "ERROR: panel must be 28c or 28r"; exit 1 ;;
esac

CONFIG_TXT=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && { CONFIG_TXT="$p"; break; }
done

if [[ -z "$CONFIG_TXT" ]]; then
  echo "ERROR: config.txt not found"
  exit 1
fi

DESIRED_BASE="pitft28-capacitive"
[[ "$PANEL" == "28r" ]] && DESIRED_BASE="pitft28-resistive"

OVERLAY_LINE="dtoverlay=${DESIRED_BASE},rotate=${ROTATE},speed=64000000,fps=30"
if [[ "$PANEL" == "28c" ]]; then
  case "$ROTATE" in
    90)  OVERLAY_LINE="${OVERLAY_LINE},touch-swapxy,touch-invx" ;;
    270) OVERLAY_LINE="${OVERLAY_LINE},touch-swapxy,touch-invy" ;;
    180) OVERLAY_LINE="${OVERLAY_LINE},touch-invx,touch-invy" ;;
  esac
fi

STAMP="$(date +%Y%m%d%H%M%S)"
cp -a "$CONFIG_TXT" "${CONFIG_TXT}.vinyl.repair.${STAMP}"
echo "Repairing $CONFIG_TXT"
echo "  backup: ${CONFIG_TXT}.vinyl.repair.${STAMP}"

# Remove vinyl blocks (comment markers may vary slightly).
sed -i '/^# vinyl pitft/,/^# end vinyl pitft/d' "$CONFIG_TXT"
sed -i '/^# vinyl pitft plate buttons/,/^# end vinyl pitft plate buttons/d' "$CONFIG_TXT"

# Remove every pitft / gpio-key / splash line anywhere in the file.
sed -i '/^dtoverlay=pitft28/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,/d' "$CONFIG_TXT"
sed -i '/^disable_splash=/d' "$CONFIG_TXT"
sed -i '/^dtparam=spi=on$/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=pitft28/s/,drm//g; s/drm,//g' "$CONFIG_TXT" 2>/dev/null || true

DTBO="/boot/firmware/overlays/${DESIRED_BASE}.dtbo"
[[ -f "$DTBO" ]] && echo "  overlay file: $DTBO" || echo "  WARNING: $DTBO missing"

{
  echo ""
  echo "# vinyl pitft"
  echo "dtparam=spi=on"
  if [[ "$PANEL" == "28c" ]]; then
    echo "dtparam=i2c_arm=on"
  fi
  echo "$OVERLAY_LINE"
  echo "disable_splash=1"
  echo "# end vinyl pitft"
} >>"$CONFIG_TXT"

echo ""
echo "=== config.txt (pitft / gpio / splash) ==="
grep -E '^(dtoverlay=pitft|dtoverlay=gpio-key|dtparam=spi|disable_splash)' "$CONFIG_TXT" | sed 's/^/  /' || true

gpio_left="$(grep -c '^dtoverlay=gpio-key,' "$CONFIG_TXT" 2>/dev/null || echo 0)"
pitft_count="$(grep -c '^dtoverlay=pitft28' "$CONFIG_TXT" 2>/dev/null || echo 0)"
echo ""
echo "  gpio-key overlays: $gpio_left (should be 0)"
echo "  pitft28 overlays:  $pitft_count (should be 1)"
echo ""
echo "Reboot: sudo reboot"
echo "Then: ls -la /dev/fb1 && bash scripts/diagnose_boot.sh"
