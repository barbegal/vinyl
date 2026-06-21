#!/usr/bin/env bash
# Configure X + touch for the Adafruit 2.8" PiTFT on /dev/fb1.
# Supports resistive (28r, STMPE/SPI) and capacitive (28c, FT6206/I2C).
#
# Usage: sudo ./scripts/setup_pitft.sh [rotation] [panel] [user]
#   rotation: 0|90|180|270   (default 270 — matched your working display)
#   panel:    28c|28r        (default 28c, capacitive)
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/setup_pitft.sh [rotation] [panel] [user]"
  exit 1
fi

ROTATE="${1:-270}"
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
    raspi-config nonint do_i2c 0 2>/dev/null || true
    echo "  raspi-config: I2C enabled"
  fi
fi

CONFIG_TXT=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && { CONFIG_TXT="$p"; break; }
done

DESIRED_BASE="pitft28-capacitive"
[[ "$PANEL" == "28r" ]] && DESIRED_BASE="pitft28-resistive"

# Capacitive: touch mapping is done in the overlay (touch-swapxy etc.), NOT libinput matrices.
# Resistive: STMPE touch is on SPI with the same overlay.
build_overlay_line() {
  local line="dtoverlay=${DESIRED_BASE},rotate=${ROTATE},speed=64000000,fps=30"
  if [[ "$PANEL" == "28c" ]]; then
    case "$ROTATE" in
      90)  line="${line},touch-swapxy,touch-invx" ;;
      270) line="${line},touch-swapxy,touch-invy" ;;
      180) line="${line},touch-invx,touch-invy" ;;
      # 0: no extra touch flags
    esac
  fi
  echo "$line"
}

if [[ -n "$CONFIG_TXT" ]]; then
  cp -a "$CONFIG_TXT" "${CONFIG_TXT}.vinyl.bak"
  echo "  backup: ${CONFIG_TXT}.vinyl.bak"
  OVERLAY_LINE="$(build_overlay_line)"
  DTBO="/boot/firmware/overlays/${DESIRED_BASE}.dtbo"
  [[ -f "$DTBO" ]] && echo "  overlay file: $DTBO" || echo "  WARNING: $DTBO missing — try Adafruit pitft installer"

  sed -i '/^# vinyl pitft$/,/^# end vinyl pitft$/d' "$CONFIG_TXT"
  sed -i '/^dtoverlay=pitft28/d' "$CONFIG_TXT"
  sed -i '/^disable_splash=/d' "$CONFIG_TXT"
  sed -i '/^dtoverlay=pitft28/s/,drm//g; s/drm,//g' "$CONFIG_TXT" 2>/dev/null || true

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
  echo "  wrote config block: spi=on + $OVERLAY_LINE"
else
  echo "  WARNING: config.txt not found on /boot"
fi

echo ""
echo "=== After reboot ==="
echo "  ls -la /dev/fb1     # must exist"
echo "  dtoverlay -l        # should list pitft28"
echo "  sudo dmesg | grep -i pitft"

echo "=== Pointing Xorg at /dev/fb1 (fbdev) ==="
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/99-pitft.conf <<'EOF'
Section "ServerFlags"
  Option "BlankTime" "0"
  Option "StandbyTime" "0"
  Option "SuspendTime" "0"
  Option "OffTime" "0"
EndSection

Section "ServerLayout"
  Identifier "PiTFT"
  Screen 0 "Screen0" 0 0
EndSection

Section "Screen"
  Identifier "Screen0"
  Device "Device0"
  Monitor "Monitor0"
  DefaultDepth 16
  SubSection "Display"
    Depth 16
    Modes "320x240"
    Virtual 320 240
  EndSubSection
EndSection

Section "Monitor"
  Identifier "Monitor0"
  Option "DPMS" "false"
EndSection

Section "Device"
  Identifier "Device0"
  Driver "fbdev"
  Option "fbdev" "/dev/fb1"
  Option "ShadowFB" "true"
EndSection
EOF

# libinput CalibrationMatrix fights the capacitive overlay's touch-swapxy/invert flags.
rm -f /etc/X11/xorg.conf.d/99-pitft-calibration.conf

if [[ "$PANEL" == "28c" ]]; then
  cat > /etc/X11/xorg.conf.d/99-pitft-touch.conf <<'EOF'
Section "InputClass"
  Identifier "PiTFT capacitive touch"
  MatchIsTouchscreen "on"
  MatchDevicePath "/dev/input/event*"
  Driver "evdev"
EndSection
EOF
  echo "  touch: evdev (no libinput matrix — overlay handles rotation)"
else
  cat > /etc/X11/xorg.conf.d/99-pitft-touch.conf <<'EOF'
Section "InputClass"
  Identifier "PiTFT resistive touch"
  MatchProduct "stmpe"
  MatchDevicePath "/dev/input/event*"
  Driver "evdev"
EndSection
EOF
  echo "  touch: evdev + stmpe match"
fi

# Adafruit: 40-libinput.conf overrides evdev for touch — move it out of the way.
LIBINPUT_SNIP="/usr/share/X11/xorg.conf.d/40-libinput.conf"
if [[ -f "$LIBINPUT_SNIP" ]]; then
  mv -f "$LIBINPUT_SNIP" "${LIBINPUT_SNIP}.vinyl-disabled" 2>/dev/null || true
  echo "  disabled ${LIBINPUT_SNIP} (use evdev for PiTFT touch)"
fi

echo ""
echo "PiTFT (${PANEL}) rotate=${ROTATE} on /dev/fb1."
echo "If upside down, flip: sudo $0 90 $PANEL   (or 270)"
echo "Reboot to apply: sudo reboot"

if [[ -x "$APP_DIR/scripts/setup_pitft_buttons.sh" ]]; then
  "$APP_DIR/scripts/setup_pitft_buttons.sh"
fi
