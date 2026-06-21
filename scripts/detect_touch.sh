#!/usr/bin/env bash
# Detect whether the PiTFT touch is capacitive (FT6206 @ I2C 0x38) or resistive (STMPE/SPI).
set -euo pipefail

SUDO=""
[[ "${EUID:-$(id -u)}" -ne 0 ]] && SUDO="sudo"

echo "=== Ensuring i2c-tools + I2C enabled ==="
command -v i2cdetect >/dev/null || $SUDO apt-get install -y i2c-tools
command -v raspi-config >/dev/null && $SUDO raspi-config nonint do_i2c 0 2>/dev/null || true

CAP=0
echo ""
echo "=== I2C scan (capacitive FT6206 = address 38) ==="
for bus in 1 0; do
  if [[ -e "/dev/i2c-$bus" ]]; then
    echo "bus $bus:"
    scan="$($SUDO i2cdetect -y "$bus" 2>/dev/null || true)"
    echo "$scan" | sed 's/^/  /'
    echo "$scan" | grep -qE '(^|[^0-9a-f])38([^0-9a-f]|$)' && CAP=1
  fi
done
[[ ! -e /dev/i2c-1 && ! -e /dev/i2c-0 ]] && echo "  (no I2C bus — reboot after enabling I2C, or capacitive overlay not loaded)"

echo ""
echo "=== Currently loaded overlay ==="
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && { grep -nE '^dtoverlay=pitft|^dtparam=(i2c|spi)' "$p" | sed 's/^/  /' || echo "  (no pitft overlay line)"; break; }
done

echo ""
echo "=== Kernel touch input devices ==="
$SUDO grep -A4 -iE 'Name=.*(touch|stmpe|ft6|ft5|edt|focal|goodix)' /proc/bus/input/devices 2>/dev/null | sed 's/^/  /' || echo "  none found"

echo ""
echo "=== dmesg touch hints ==="
$SUDO dmesg 2>/dev/null | grep -iE 'stmpe|ft6|ft5|edt-ft|pitft|touch' | tail -15 | sed 's/^/  /' || echo "  none"

echo ""
echo "=== VERDICT ==="
if [[ "$CAP" -eq 1 ]]; then
  echo "CAPACITIVE detected (FT6206 @ 0x38)."
  echo "Fix: sudo ./scripts/setup_pitft.sh 270 28c   (then reboot)"
else
  echo "No FT6206 at 0x38 → likely RESISTIVE (STMPE on SPI)."
  echo "Fix: sudo ./scripts/setup_pitft.sh 270 28r   (then reboot)"
  echo "(If you just enabled I2C, reboot first, then re-run this detector to be sure.)"
fi
