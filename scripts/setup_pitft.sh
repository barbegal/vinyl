#!/usr/bin/env bash
# Configure X + touch for the Adafruit 2.8" PiTFT on /dev/fb1.
# Supports resistive (28r, STMPE/SPI) and capacitive (28c, FT6206/I2C).
# Rotation is set in the config.txt overlay (rotate=), NOT xrandr/display_rotate.
#
# Usage: sudo ./scripts/setup_pitft.sh [rotation] [panel] [user]
#   rotation: 0|90|180|270   (default 270; use 90/270 for 320x240 landscape)
#   panel:    28c|28r        (default 28c, capacitive)
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/setup_pitft.sh [rotation] [panel] [user]"
  exit 1
fi

ROTATE="${1:-90}"
PANEL="${2:-28c}"
APP_USER="${3:-${SUDO_USER:-vinyl}}"

case "$ROTATE" in
  0|90|180|270) ;;
  *) echo "ERROR: rotation must be 0, 90, 180, or 270"; exit 1 ;;
esac
case "$PANEL" in
  28c|28r) ;;
  *) echo "ERROR: panel must be 28c (capacitive) or 28r (resistive)"; exit 1 ;;
esac

echo "=== Installing fbdev + evdev X drivers ==="
apt-get install -y xserver-xorg-video-fbdev xserver-xorg-input-evdev

if [[ "$PANEL" == "28c" ]]; then
  echo "=== Enabling I2C (capacitive FT6206 touch is on I2C) ==="
  if command -v raspi-config >/dev/null; then
    raspi-config nonint do_i2c 0 2>/dev/null || true   # 0 = enable
    echo "  raspi-config: I2C enabled"
  fi
fi

CONFIG_TXT=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && { CONFIG_TXT="$p"; break; }
done

DESIRED_BASE="pitft28-capacitive"
[[ "$PANEL" == "28r" ]] && DESIRED_BASE="pitft28-resistive"

build_overlay_line() {
  local line="dtoverlay=${DESIRED_BASE},rotate=${ROTATE},speed=64000000,fps=30"
  if [[ "$PANEL" == "28c" ]]; then
    line="${line},touch-swapxy,touch-invx"
  fi
  echo "$line"
}

if [[ -n "$CONFIG_TXT" ]]; then
  cp -a "$CONFIG_TXT" "${CONFIG_TXT}.vinyl.bak"
  echo "  backup: ${CONFIG_TXT}.vinyl.bak"
  OVERLAY_LINE="$(build_overlay_line)"
  # Replace any active pitft28 overlay line with one canonical line (Adafruit-style).
  if grep -qE '^dtoverlay=pitft28' "$CONFIG_TXT"; then
    sed -i '/^dtoverlay=pitft28/d' "$CONFIG_TXT"
    echo "  removed old pitft28 overlay line(s)"
  fi
  echo "$OVERLAY_LINE" >>"$CONFIG_TXT"
  echo "  set overlay: $OVERLAY_LINE"
  if grep -qE '^disable_splash=' "$CONFIG_TXT"; then
    sed -i 's/^disable_splash=.*/disable_splash=1/' "$CONFIG_TXT"
  else
    echo 'disable_splash=1' >>"$CONFIG_TXT"
  fi
  echo "  set disable_splash=1"
else
  echo "  WARNING: config.txt not found on /boot"
fi

echo "=== Pointing Xorg at /dev/fb1 (fbdev) ==="
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/99-pitft.conf <<'EOF'
Section "Device"
  Identifier "Adafruit PiTFT"
  Driver "fbdev"
  Option "fbdev" "/dev/fb1"
EndSection
EOF
echo "  wrote /etc/X11/xorg.conf.d/99-pitft.conf"

echo "=== Touch calibration matrix (best-effort for rotate=${ROTATE}) ==="
# MatchIsTouchscreen matches the panel's touch regardless of controller
# (STMPE resistive or FT6206 capacitive) without hardcoding a device name.
case "$ROTATE" in
  0)   MATRIX="1 0 0 0 1 0 0 0 1" ;;
  90)  MATRIX="0 -1 1 1 0 0 0 0 1" ;;
  180) MATRIX="-1 0 1 0 -1 1 0 0 1" ;;
  270) MATRIX="0 1 0 -1 0 1 0 0 1" ;;
esac
cat > /etc/X11/xorg.conf.d/99-pitft-calibration.conf <<EOF
Section "InputClass"
  Identifier "PiTFT touch"
  MatchIsTouchscreen "on"
  MatchDevicePath "/dev/input/event*"
  Driver "libinput"
  Option "CalibrationMatrix" "${MATRIX}"
EndSection
EOF
echo "  wrote /etc/X11/xorg.conf.d/99-pitft-calibration.conf (matrix: ${MATRIX})"
echo "  NOTE: if taps land in the wrong spot, run 'xinput list' to confirm the touch"
echo "        device, or run the Adafruit installer: --display=${PANEL} --rotation=${ROTATE}"

echo ""
echo "PiTFT (${PANEL}) configured for rotate=${ROTATE} on /dev/fb1."
echo "If the image is upside down after reboot, re-run with the opposite rotation:"
if [[ "$ROTATE" == "270" ]]; then echo "  sudo $0 90 $PANEL"; else echo "  sudo $0 270 $PANEL"; fi
echo "Reboot to apply: sudo reboot"
