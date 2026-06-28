#!/usr/bin/env bash
# Diagnose kiosk boot. Use --report for a full paste-friendly log file.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$USER_NAME")"
REPORT_MODE=0
REPORT_FILE="${USER_HOME}/.vinyl-report.txt"

for arg in "$@"; do
  case "$arg" in
    --report|-r) REPORT_MODE=1 ;;
    -h|--help)
      echo "Usage: bash scripts/diagnose_boot.sh [--report]"
      echo "  default   summary on screen"
      echo "  --report  also save full report to ~/.vinyl-report.txt (paste in chat)"
      exit 0
      ;;
  esac
done

run_diagnosis() {
  echo "=== boot config ==="
  echo "default target: $(systemctl get-default 2>/dev/null || echo unknown)"
  echo "getty@tty1:     $(systemctl is-enabled getty@tty1.service 2>/dev/null || echo unknown) / $(systemctl is-active getty@tty1.service 2>/dev/null || echo unknown)"
  if systemctl is-failed getty@tty1.service 2>/dev/null | grep -q failed; then
    echo "  WARNING: getty@tty1 failed — try: sudo systemctl reset-failed getty@tty1 && sudo systemctl start getty@tty1"
  fi
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
  echo "=== user session ==="
  [[ -f "$USER_HOME/.xinitrc" ]] && echo ".xinitrc: present" || echo ".xinitrc: MISSING"
  grep -qF "pi-audio-cast-display startx" "$USER_HOME/.profile" 2>/dev/null && echo ".profile startx guard: present" || echo ".profile startx guard: MISSING"
  grep -qF "pi-audio-cast-display startx" "$USER_HOME/.bash_profile" 2>/dev/null && echo ".bash_profile startx guard: present" || echo ".bash_profile startx guard: missing (ok if profile.d present)"

  echo ""
  echo "=== tools ==="
  command -v xinit  >/dev/null && echo "xinit:  ok" || echo "xinit:  NOT INSTALLED"
  command -v startx >/dev/null && echo "startx: ok" || echo "startx: NOT INSTALLED"
  command -v Xorg   >/dev/null && echo "Xorg:   ok" || echo "Xorg:   NOT INSTALLED"
  [[ -x "$APP_DIR/.venv/bin/python" ]] && echo "venv: ok" || echo "venv: MISSING"

  echo ""
  echo "=== audio / cast ==="
  if [[ -f "$APP_DIR/.env" ]]; then
    grep -E '^USB_ALSA_DEVICE=|^CAST_DISCOVERY|^VINYL_AUTO_CAST=' "$APP_DIR/.env" 2>/dev/null | sed 's/^/  /' || true
    head -1 "$APP_DIR/.env" | grep -qE '^@' && \
      echo "  ERROR: .env line 1 starts with @ — run: bash scripts/recover.sh"
    grep -qE '^GOOGLE_GROUPS_ONLY=' "$APP_DIR/.env" 2>/dev/null && \
      echo "  NOTE: obsolete GOOGLE_GROUPS_ONLY in .env — run: bash scripts/recover.sh"
    grep -qE '^VINYL_AUTO_CAST=[^"].*[[:space:]]' "$APP_DIR/.env" 2>/dev/null && \
      echo "  ERROR: VINYL_AUTO_CAST needs quotes — run: bash scripts/recover.sh"
  fi
  if command -v arecord >/dev/null; then
    arecord -l 2>/dev/null | grep -E '^card |USB' | sed 's/^/  /' || echo "  (no arecord devices)"
  fi
  command -v ffmpeg >/dev/null && echo "ffmpeg: ok" || echo "ffmpeg: MISSING (apt install ffmpeg)"

  ls -la /dev/fb* /dev/dri/* 2>/dev/null | sed 's/^/  /' || echo "  (no /dev/fb* or /dev/dri/*)"
  [[ -e /dev/fb1 ]] && echo "/dev/fb1: present" || echo "/dev/fb1: MISSING — overlay not binding (see dmesg below)"
  for p in /boot/firmware/config.txt /boot/config.txt; do
    if [[ -f "$p" ]]; then
      echo "$p:"
      grep -E '^(dtoverlay=pitft|dtparam=spi|dtparam=i2c|dtoverlay=vc4|disable_splash)' "$p" 2>/dev/null | sed 's/^/  /' || echo "  (no pitft line)"
      if grep -qE '^dtoverlay=pitft28-resistive' "$p" 2>/dev/null; then
        echo "  WARNING: pitft28-resistive — capacitive panel needs 28c: sudo bash scripts/recover.sh --display 270 28c"
      fi
      grep -qE '^dtparam=spi=on' "$p" 2>/dev/null || echo "  WARNING: no 'dtparam=spi=on' — pitft overlay CANNOT bind → no /dev/fb1"
      if grep -qE '^dtoverlay=pitft28.*drm' "$p" 2>/dev/null; then
        echo "  WARNING: overlay has ,drm — black TFT. Run: bash scripts/recover.sh --display"
      fi
      if grep -qE '^dtoverlay=vc4-kms-v3d' "$p" 2>/dev/null; then
        echo "  NOTE: vc4-kms-v3d (full KMS) is on — can fight SPI fbdev (FBIOPUTCMAP busy / black TFT even when fb1 exists)."
        echo "        If fb1 exists but TFT is black, try 'vc4-fkms-v3d' instead, or add 'fbcon=map:10' to cmdline.txt."
      fi
      dup="$(grep -c '^disable_splash=' "$p" 2>/dev/null || echo 0)"
      [[ "$dup" -gt 1 ]] && echo "  WARNING: duplicate disable_splash lines — run: sudo ./scripts/setup_pitft.sh 270 28c"
      btn="$(grep -c '^dtoverlay=gpio-key,gpio=' "$p" 2>/dev/null || echo 0)"
      if [[ "$btn" -eq 0 ]]; then
        echo "  WARNING: no plate button overlays — run: sudo ./scripts/setup_pitft_buttons.sh"
      else
        echo "  plate buttons: $btn gpio-key overlay(s)"
        grep '^dtoverlay=gpio-key,gpio=' "$p" 2>/dev/null | sed 's/^/    /'
      fi
      break
    fi
  done
  [[ -f /etc/X11/xorg.conf.d/99-pitft.conf ]] && echo "Xorg fbdev conf: present" || echo "Xorg fbdev conf: MISSING"
  echo "kernel (pitft / fb / bind):"
  dmesg 2>/dev/null | grep -iE 'pitft|fb1|stmpe|fbtft|spi0|gpio-key|bind|pinctrl|cannot claim' | tail -12 | sed 's/^/  /' || echo "  (run: sudo dmesg | grep -iE 'bind|gpio|pitft')"

  echo ""
  echo "=== runtime ==="
  echo "DISPLAY: ${DISPLAY:-not set}  tty: $(tty 2>/dev/null || echo unknown)"
  pgrep -a Xorg 2>/dev/null | sed 's/^/  /' || echo "  Xorg: not running"
  pgrep -af 'src.main' 2>/dev/null | sed 's/^/  /' || echo "  cast app: not running"

  echo ""
  echo "=== boot timing ==="
  if [[ -f "$USER_HOME/.vinyl-boot.log" ]]; then
    sed 's/^/  /' "$USER_HOME/.vinyl-boot.log"
  else
    echo "  (no ~/.vinyl-boot.log yet)"
  fi

  echo ""
  echo "=== remote mirror ==="
  command -v rpi-connect >/dev/null && echo "rpi-connect: installed" || echo "rpi-connect: not installed"
  command -v x11vnc >/dev/null && echo "x11vnc: installed" || echo "x11vnc: not installed"
  pgrep -a x11vnc 2>/dev/null | sed 's/^/  /' || true

  if [[ "$REPORT_MODE" -eq 1 ]]; then
    echo ""
    echo "=== ~/.xinitrc (head) ==="
    head -20 "$USER_HOME/.xinitrc" 2>/dev/null | sed 's/^/  /' || echo "  missing"
    echo ""
    echo "=== start_app.sh ==="
    ls -la "$APP_DIR/scripts/start_app.sh" 2>/dev/null | sed 's/^/  /' || echo "  missing"
    echo ""
    echo "=== ~/.vinyl-xsession.log (tail) ==="
    tail -40 "$USER_HOME/.vinyl-xsession.log" 2>/dev/null | sed 's/^/  /' || echo "  (none)"
    echo ""
    echo "=== Xorg log (fbdev / errors) ==="
    XLOG="$USER_HOME/.local/share/xorg/Xorg.0.log"
    if [[ -f "$XLOG" ]]; then
      grep -iE 'fbdev|fb1|dimensions|EE\)|WW\)' "$XLOG" 2>/dev/null | tail -25 | sed 's/^/  /' || echo "  (no matches)"
    fi
    echo ""
    echo "=== xdpyinfo ==="
    if DISPLAY=:0 xdpyinfo >/dev/null 2>&1; then
      DISPLAY=:0 xdpyinfo 2>/dev/null | grep -E 'name of display|dimensions' | sed 's/^/  /'
    else
      echo "  (xdpyinfo failed)"
    fi
    echo ""
    echo "=== git ==="
    git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null | sed 's/^/  commit: /' || true
    git -C "$APP_DIR" status -sb 2>/dev/null | sed 's/^/  /' || true
  fi
}

if [[ "$REPORT_MODE" -eq 1 ]]; then
  {
    echo "vinyl report — $(date -Is 2>/dev/null || date)"
    echo "host: $(hostname 2>/dev/null)  ip: $(hostname -I 2>/dev/null)"
    echo ""
    run_diagnosis
  } | tee "$REPORT_FILE"
  echo ""
  echo "Saved: $REPORT_FILE"
else
  run_diagnosis
  echo ""
  echo "Full report: bash scripts/diagnose_boot.sh --report"
  echo "Fix issues:  bash scripts/recover.sh"
fi
