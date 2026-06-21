#!/usr/bin/env bash
# Diagnose kiosk boot (tty1 autologin -> startx -> cast app).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$USER_NAME")"

echo "=== boot config ==="
echo "default target: $(systemctl get-default 2>/dev/null || echo unknown)"
echo "getty@tty1:     $(systemctl is-enabled getty@tty1.service 2>/dev/null || echo unknown) / $(systemctl is-active getty@tty1.service 2>/dev/null || echo unknown)"
echo "lightdm:        $(systemctl is-enabled lightdm.service 2>/dev/null || echo not-found) / $(systemctl is-active lightdm.service 2>/dev/null || echo not-found)"

AUTLOGIN="/etc/systemd/system/getty@tty1.service.d/autologin.conf"
if [[ -f "$AUTLOGIN" ]]; then
  echo "autologin override:"
  grep -E '^ExecStart' "$AUTLOGIN" | sed 's/^/  /'
else
  echo "autologin override: MISSING"
fi

if [[ -f /etc/profile.d/vinyl-kiosk.sh ]]; then
  echo "profile.d kiosk hook: present"
else
  echo "profile.d kiosk hook: MISSING — run ./scripts/install_service.sh"
fi

echo ""
echo "=== old systemd unit (should be gone) ==="
if [[ -f /etc/systemd/system/pi-audio-cast-display.service ]]; then
  echo "WARNING: old service still present"
else
  echo "none (good)"
fi

echo ""
echo "=== user session files ==="
[[ -f "$USER_HOME/.xinitrc" ]] && echo ".xinitrc: present" || echo ".xinitrc: MISSING"
if grep -qF "pi-audio-cast-display startx" "$USER_HOME/.profile" 2>/dev/null; then
  echo ".profile startx guard: present"
else
  echo ".profile startx guard: MISSING"
fi
if grep -qF "pi-audio-cast-display startx" "$USER_HOME/.bash_profile" 2>/dev/null; then
  echo ".bash_profile startx guard: present"
else
  echo ".bash_profile startx guard: missing (ok if profile.d hook present)"
fi
echo "login shell: $(getent passwd "$USER_NAME" | cut -d: -f7)"

echo ""
echo "=== tools ==="
command -v xinit  >/dev/null && echo "xinit:  $(command -v xinit)"  || echo "xinit:  NOT INSTALLED"
command -v startx >/dev/null && echo "startx: $(command -v startx)" || echo "startx: NOT INSTALLED"
command -v Xorg   >/dev/null && echo "Xorg:   $(command -v Xorg)"   || echo "Xorg:   NOT INSTALLED"
[[ -f /etc/X11/Xwrapper.config ]] && { echo "Xwrapper.config:"; sed 's/^/  /' /etc/X11/Xwrapper.config; } || echo "Xwrapper.config: none"
[[ -x "$APP_DIR/.venv/bin/python" ]] && echo "venv: ok" || echo "venv: MISSING at $APP_DIR/.venv"

echo ""
echo "=== PiTFT / display ==="
[[ -e /dev/fb1 ]] && echo "/dev/fb1: present (PiTFT)" || echo "/dev/fb1: MISSING — overlay not loaded (run Adafruit installer)"
for p in /boot/firmware/config.txt /boot/config.txt; do
  if [[ -f "$p" ]]; then
    echo "$p:"
    grep -E '^(dtoverlay=pitft|disable_splash)=?' "$p" 2>/dev/null | sed 's/^/  /' || echo "  (no pitft overlay line)"
    if grep -qE '^dtoverlay=pitft28.*drm' "$p" 2>/dev/null; then
      echo "  WARNING: overlay has ,drm — causes black TFT with X fbdev. Run: sudo ./scripts/fix_black_tft.sh"
    fi
    break
  fi
done
[[ -f /etc/X11/xorg.conf.d/99-pitft.conf ]] && echo "Xorg fbdev conf: present" || echo "Xorg fbdev conf: MISSING — run ./scripts/setup_pitft.sh"
[[ -f /etc/X11/xorg.conf.d/99-pitft-touch.conf ]] && echo "Xorg touch conf: present (evdev)" || echo "Xorg touch conf: MISSING"
[[ -f /etc/X11/xorg.conf.d/99-pitft-calibration.conf ]] && echo "WARNING: old libinput calibration still present — run setup_pitft.sh"
echo "FRAMEBUFFER: ${FRAMEBUFFER:-not set (set before startx via profile hook)}"
echo "I2C (capacitive touch): $(ls /dev/i2c-* 2>/dev/null | tr '\n' ' ' || echo 'none — enable for 28c')"
if command -v xinput >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
  echo "touch devices:"
  xinput list --name-only 2>/dev/null | grep -iE 'touch|stmpe|ft6|ft5|focal|goodix|ep0110' | sed 's/^/  /' || echo "  (none detected)"
fi

echo ""
echo "=== runtime ==="
echo "DISPLAY: ${DISPLAY:-not set}"
echo "tty:     $(tty 2>/dev/null || echo unknown)"
pgrep -a Xorg 2>/dev/null | sed 's/^/  /' || echo "  Xorg: not running"
pgrep -af 'src.main' 2>/dev/null | sed 's/^/  /' || echo "  cast app: not running"

echo ""
echo "=== boot timing (last reboot) ==="
BOOT_LOG="$USER_HOME/.vinyl-boot.log"
if [[ -f "$BOOT_LOG" ]]; then
  sed 's/^/  /' "$BOOT_LOG"
  ui_line="$(grep 'ui visible on tft' "$BOOT_LOG" | tail -1)"
  if [[ -n "$ui_line" ]]; then
    ui_s="${ui_line%%s*}"
    if awk "BEGIN {exit !($ui_s <= 35)}"; then
      echo "  → UI target met (≤35s on Pi 5 class)"
    elif awk "BEGIN {exit !($ui_s <= 45)}"; then
      echo "  → UI within Pi 4 target (≤45s)"
    else
      echo "  → UI slower than 45s target — check SD card, Wi-Fi, services"
    fi
  fi
else
  echo "  no $BOOT_LOG yet (reboot once after install)"
fi

echo ""
echo "=== remote mirror (rp connect / vnc) ==="
if command -v rpi-connect >/dev/null 2>&1; then
  echo "rpi-connect: installed"
  rpi-connect status 2>/dev/null | sed 's/^/  /' || echo "  (run: rpi-connect status / rpi-connect signin)"
else
  echo "rpi-connect: NOT installed — run ./scripts/setup_rpconnect.sh"
fi
if command -v x11vnc >/dev/null 2>&1; then
  echo "x11vnc: installed (VINYL_MIRROR_VNC=${VINYL_MIRROR_VNC:-unset})"
else
  echo "x11vnc: NOT installed — run ./scripts/setup_rpconnect.sh"
fi
pgrep -a x11vnc 2>/dev/null | sed 's/^/  /' || echo "  x11vnc: not running"

echo ""
echo "=== last X errors ==="
tail -n 25 "$USER_HOME/.local/share/xorg/Xorg.0.log" 2>/dev/null | grep -E '\(EE\)|\(WW\)' || echo "(no recent EE/WW lines)"
