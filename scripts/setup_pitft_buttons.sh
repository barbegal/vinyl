#!/usr/bin/env bash
# Map Adafruit PiTFT plate buttons to Linux keycodes (gpio-keys overlays).
# Standard 2.8" plate has 4 buttons: GPIO 17/22/23/27.
#   Up=GPIO17, Down=GPIO22, Left/refresh=GPIO27, Enter/select=GPIO23
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

# Remove prior vinyl gpio-key lines.
sed -i '/^# vinyl pitft plate buttons$/,/^# end vinyl pitft plate buttons$/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=17,.*label=pitft-/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=22,.*label=pitft-/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=23,.*label=pitft-/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=27,.*label=pitft-/d' "$CONFIG_TXT"
sed -i '/^dtoverlay=gpio-key,gpio=25,.*label=pitft-/d' "$CONFIG_TXT"

{
  echo "# vinyl pitft plate buttons"
  echo "dtoverlay=gpio-key,gpio=17,active_low=1,gpio_pull=up,keycode=103,label=pitft-up"
  echo "dtoverlay=gpio-key,gpio=22,active_low=1,gpio_pull=up,keycode=108,label=pitft-down"
  echo "dtoverlay=gpio-key,gpio=27,active_low=1,gpio_pull=up,keycode=105,label=pitft-left"
  echo "dtoverlay=gpio-key,gpio=23,active_low=1,gpio_pull=up,keycode=28,label=pitft-enter"
  echo "# end vinyl pitft plate buttons"
} >>"$CONFIG_TXT"

echo "  Up/Down/Left/Enter mapped to GPIO 17/22/27/23"
echo "  In the app: Up/Down scroll, Enter select, Left refresh"
echo "  (GPIO25 left free for the PiTFT display DC pin)"
echo "Reboot to apply: sudo reboot"
