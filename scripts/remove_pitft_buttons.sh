#!/usr/bin/env bash
# Remove PiTFT plate gpio-key overlays from config.txt (fixes kernel bind / GPIO conflicts).
# Usage: sudo bash scripts/remove_pitft_buttons.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/remove_pitft_buttons.sh"
  exit 1
fi

CONFIG_TXT=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && { CONFIG_TXT="$p"; break; }
done

if [[ -z "$CONFIG_TXT" ]]; then
  echo "ERROR: config.txt not found"
  exit 1
fi

cp -a "$CONFIG_TXT" "${CONFIG_TXT}.vinyl.nobtn.bak"
echo "Removing plate button overlays from $CONFIG_TXT"
echo "  backup: ${CONFIG_TXT}.vinyl.nobtn.bak"

sed -i '/^# vinyl pitft plate buttons$/,/^# end vinyl pitft plate buttons$/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=17,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=22,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=23,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=27,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=25,.*label=pitft-/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,.*label=pitft-/d' "$CONFIG_TXT"

remaining="$(grep -c '^dtoverlay=gpio-key,' "$CONFIG_TXT" 2>/dev/null || echo 0)"
if [[ "$remaining" -gt 0 ]]; then
  echo "  removing $remaining remaining gpio-key line(s)"
  sed -i '/^dtoverlay=gpio-key,/d' "$CONFIG_TXT"
fi
echo "  gpio-key overlays left: $(grep -c '^dtoverlay=gpio-key,' "$CONFIG_TXT" 2>/dev/null || echo 0)"
echo "Reboot to apply: sudo reboot"
