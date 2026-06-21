#!/usr/bin/env bash
# Map Adafruit PiTFT plate buttons to Linux keycodes (gpio-keys overlays).
# Standard 2.8" plate has 4 buttons in physical order: GPIO 17, 22, 23, 27.
# To align with the on-screen icons (top→bottom: ↑ ↓ ↻ OK):
#   GPIO17=Up  GPIO22=Down  GPIO23=Left/refresh  GPIO27=Enter/select
# NOTE: GPIO25 is the PiTFT DC pin (used by fb_ili9340). It must NOT be mapped
#   to a button or the display fails to bind and /dev/fb1 never appears.
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/setup_pitft_buttons.sh"
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

echo "Configuring PiTFT plate buttons in $CONFIG_TXT"

# Remove prior vinyl gpio-key lines (any pitft label or plate GPIO).
sed -i '/^# vinyl pitft plate buttons$/,/^# end vinyl pitft plate buttons$/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=17,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=22,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=23,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=27,/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=25,.*label=pitft-/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,.*label=pitft-/d' "$CONFIG_TXT"

before="$(grep -c '^dtoverlay=gpio-key,' "$CONFIG_TXT" 2>/dev/null || echo 0)"
if [[ "$before" -gt 0 ]]; then
  echo "  WARNING: $before other gpio-key line(s) still in config — may conflict with plate GPIO"
  grep '^dtoverlay=gpio-key,' "$CONFIG_TXT" | sed 's/^/    /'
fi

{
  echo "# vinyl pitft plate buttons"
  echo "dtoverlay=gpio-key,gpio=17,active_low=1,gpio_pull=up,keycode=103,label=pitft-up"
  echo "dtoverlay=gpio-key,gpio=22,active_low=1,gpio_pull=up,keycode=108,label=pitft-down"
  echo "dtoverlay=gpio-key,gpio=23,active_low=1,gpio_pull=up,keycode=105,label=pitft-left"
  echo "dtoverlay=gpio-key,gpio=27,active_low=1,gpio_pull=up,keycode=28,label=pitft-enter"
  echo "# end vinyl pitft plate buttons"
} >>"$CONFIG_TXT"

echo "  GPIO 17/22/23/27 -> Up/Down/Refresh/Enter (top→bottom: ↑ ↓ ↻ OK)"
echo "  In the app: Up/Down scroll, Refresh re-scan, Enter select"
echo "  (GPIO25 left free for the PiTFT display DC pin)"
echo "Reboot to apply: sudo reboot"
