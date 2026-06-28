#!/usr/bin/env bash
# One-shot recovery: permissions, SSH-safe login hooks, xinitrc, .env.
#   bash scripts/recover.sh              — usual fix after git pull
#   bash scripts/recover.sh --repair-config [rotation] [28r|28c] — nuclear config.txt fix
#   bash scripts/recover.sh --display 270 28r
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
USER_NAME="${USER:-$(whoami)}"
USER_HOME="${HOME}"

INSTALL_BUTTONS=0
DISPLAY_FIX=0
STRIP_BUTTONS=0
REPAIR_CONFIG=0
ROTATE=270
PANEL=28r

usage() {
  cat <<EOF
Usage: bash scripts/recover.sh [--display [rotation] [28c|28r]]

  default     chmod scripts, SSH-safe profile guards, refresh ~/.xinitrc, .env
  --display   also remove ,drm from overlay and re-run setup_pitft (needs sudo)
  --strip-buttons  remove plate gpio-key overlays only
  --repair-config  strip ALL gpio-key + duplicate pitft; write one clean block (bind errors)
  --buttons        re-enable plate gpio-key overlays (no GPIO25 — safe for display)

Then: sudo reboot
Desktop undo: sudo ./scripts/restore_desktop.sh
Full report:  bash scripts/diagnose_boot.sh --report
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --display)
      DISPLAY_FIX=1
      shift
      [[ $# -gt 0 && "$1" =~ ^[0-9]+$ ]] && { ROTATE="$1"; shift; }
      [[ $# -gt 0 && "$1" =~ ^28[cr]$ ]] && { PANEL="$1"; shift; }
      ;;
    --strip-buttons)
      STRIP_BUTTONS=1
      shift
      ;;
    --repair-config)
      REPAIR_CONFIG=1
      shift
      [[ $# -gt 0 && "$1" =~ ^[0-9]+$ ]] && { ROTATE="$1"; shift; }
      [[ $# -gt 0 && "$1" =~ ^28[cr]$ ]] && { PANEL="$1"; shift; }
      ;;
    --buttons)
      INSTALL_BUTTONS=1
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

MARKER="# >>> pi-audio-cast-display startx >>>"
SAFE_GUARD='
# >>> pi-audio-cast-display startx >>>
# Only local tty1 — never SSH (SSH_CONNECTION is set for remote logins).
if [ -z "${DISPLAY:-}" ] \
   && [ -z "${SSH_CONNECTION:-}" ] \
   && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
  [ -e /dev/fb1 ] && export FRAMEBUFFER=/dev/fb1
  exec startx
fi
# <<< pi-audio-cast-display startx <<<
'

echo "=== vinyl recover ==="
echo "App dir: $APP_DIR"

chmod +x scripts/*.sh
echo "  fixed execute bits on scripts/*.sh"

for PROFILE in "$USER_HOME/.profile" "$USER_HOME/.bash_profile"; do
  if [[ -f "$PROFILE" ]] && grep -qF "$MARKER" "$PROFILE"; then
    sed -i '/# >>> pi-audio-cast-display startx >>>/,/# <<< pi-audio-cast-display startx <<</d' "$PROFILE"
    printf '%s\n' "$SAFE_GUARD" >> "$PROFILE"
    echo "  SSH-safe startx guard in $PROFILE"
  elif [[ -f "$PROFILE" ]] && grep -qE 'exec startx' "$PROFILE"; then
    echo "  WARN: $PROFILE has exec startx outside our guard — review manually"
  fi
done

if [[ -f /etc/profile.d/vinyl-kiosk.sh ]] && ! grep -q 'SSH_CONNECTION' /etc/profile.d/vinyl-kiosk.sh; then
  echo "  WARN: re-run sudo ./scripts/enable_fast_boot.sh (profile.d missing SSH guard)"
fi

./scripts/refresh_xinitrc.sh

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "  created .env from .env.example"
else
  _env_changed=0
  if head -1 "$APP_DIR/.env" | grep -qE '^@'; then
    sed -i '1{/^@/d;}' "$APP_DIR/.env"
    echo "  removed invalid first line from .env (git diff header)"
    _env_changed=1
  fi
  if grep -qE '^GOOGLE_GROUPS_ONLY=' "$APP_DIR/.env" 2>/dev/null; then
    sed -i '/^GOOGLE_GROUPS_ONLY=/d' "$APP_DIR/.env"
    echo "  removed obsolete GOOGLE_GROUPS_ONLY from .env"
    _env_changed=1
  fi
  if grep -qE '^VINYL_AUTO_CAST=' "$APP_DIR/.env" 2>/dev/null \
     && grep -qE '^VINYL_AUTO_CAST=[^"].*[[:space:]]' "$APP_DIR/.env" 2>/dev/null; then
    _auto_val="$(grep -E '^VINYL_AUTO_CAST=' "$APP_DIR/.env" | head -1 | cut -d= -f2-)"
    sed -i "s|^VINYL_AUTO_CAST=.*|VINYL_AUTO_CAST=\"${_auto_val}\"|" "$APP_DIR/.env"
    echo "  quoted VINYL_AUTO_CAST in .env (unquoted spaces break boot)"
    _env_changed=1
  fi
  if grep -qE '^AUDIO_CHANNELS=1' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^AUDIO_CHANNELS=1/AUDIO_CHANNELS=2/' "$APP_DIR/.env"
    echo "  set AUDIO_CHANNELS=2 (USB line-in is usually stereo)"
    _env_changed=1
  fi
  if grep -qE '^AUDIO_LEVEL_GAIN=4(\.0)?$' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^AUDIO_LEVEL_GAIN=.*/AUDIO_LEVEL_GAIN=1.0/' "$APP_DIR/.env"
    echo "  set AUDIO_LEVEL_GAIN=1.0 (old ×4 gain pegged bars — use AUDIO_LEVEL_FLOOR_DB/CEIL_DB)"
    _env_changed=1
  fi
  if ! grep -qE '^AUDIO_LEVEL_FLOOR_DB=' "$APP_DIR/.env" 2>/dev/null; then
    printf 'AUDIO_LEVEL_FLOOR_DB=-58\nAUDIO_LEVEL_CEIL_DB=6\n' >>"$APP_DIR/.env"
    echo "  added AUDIO_LEVEL_FLOOR_DB / AUDIO_LEVEL_CEIL_DB for bar meter scaling"
    _env_changed=1
  fi
  if grep -qE '^AUDIO_LEVEL_CEIL_DB=0(\.0)?$' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^AUDIO_LEVEL_CEIL_DB=.*/AUDIO_LEVEL_CEIL_DB=6/' "$APP_DIR/.env"
    echo "  set AUDIO_LEVEL_CEIL_DB=6 (wider meter headroom)"
    _env_changed=1
  fi
  if ! grep -qE '^AUDIO_LEVEL_AUTO_RANGE=' "$APP_DIR/.env" 2>/dev/null; then
    printf 'AUDIO_LEVEL_AUTO_RANGE=1\nAUDIO_LEVEL_AUTO_DECAY=0.993\n' >>"$APP_DIR/.env"
    echo "  added AUDIO_LEVEL_AUTO_RANGE for VU-style bar dynamics"
    _env_changed=1
  fi
  if ! grep -qE '^CAST_STREAM_EQ=' "$APP_DIR/.env" 2>/dev/null; then
    printf 'CAST_STREAM_EQ=1\n' >>"$APP_DIR/.env"
    echo "  enabled CAST_STREAM_EQ (tames tinny USB line-in)"
    _env_changed=1
  fi
  if grep -qE '^CAST_HIGH_CUT_HZ=(0|12000)$' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^CAST_HIGH_CUT_HZ=.*/CAST_HIGH_CUT_HZ=14000/' "$APP_DIR/.env"
    echo "  set CAST_HIGH_CUT_HZ=14000 (richer air than 12 kHz)"
    _env_changed=1
  fi
  if ! grep -qE '^CAST_STEREO_MODE=' "$APP_DIR/.env" 2>/dev/null; then
    printf 'CAST_STEREO_MODE=stereo\n' >>"$APP_DIR/.env"
    echo "  set CAST_STEREO_MODE=stereo (run scripts/debug_usb_stereo.sh to verify)"
    _env_changed=1
  fi
  if grep -qE '^VINYL_AUTO_CAST="Upper,Living Room Speaker"$' "$APP_DIR/.env" 2>/dev/null \
     || grep -qE "^VINYL_AUTO_CAST=Upper,Living Room Speaker$" "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's|^VINYL_AUTO_CAST=.*|VINYL_AUTO_CAST="Living Room pair"|' "$APP_DIR/.env"
    echo "  set VINYL_AUTO_CAST=\"Living Room pair\" (primary speaker)"
    _env_changed=1
  fi
  if grep -qE '^CAST_INPUT_GAIN_DB=-21(\.0)?$' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^CAST_INPUT_GAIN_DB=.*/CAST_INPUT_GAIN_DB=-9/' "$APP_DIR/.env"
    echo "  set CAST_INPUT_GAIN_DB=-9 (run scripts/tune_usb_gain.sh after lowering Mic Capture)"
    _env_changed=1
  fi
  if grep -qE '^CAST_OUTPUT_VOLUME=0\.(22|32|40|50)$' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^CAST_OUTPUT_VOLUME=.*/CAST_OUTPUT_VOLUME=1.0/' "$APP_DIR/.env"
    echo "  set CAST_OUTPUT_VOLUME=1.0"
    _env_changed=1
  fi
  if grep -qE '^CAST_KNOWN_HOSTS=CAST_' "$APP_DIR/.env" 2>/dev/null; then
    _gain="$(sed -n 's/^CAST_KNOWN_HOSTS=CAST_INPUT_GAIN_DB=//p' "$APP_DIR/.env" | head -1)"
    sed -i '/^CAST_KNOWN_HOSTS=CAST_/d' "$APP_DIR/.env"
    printf 'CAST_KNOWN_HOSTS=\nCAST_INPUT_GAIN_DB=%s\n' "${_gain:--9}" >>"$APP_DIR/.env"
    echo "  fixed merged CAST_KNOWN_HOSTS / CAST_INPUT_GAIN_DB line in .env"
    _env_changed=1
  fi
  if [[ "$_env_changed" -eq 1 ]]; then
    echo "  .env sanitized — if boot still fails, compare with .env.example"
  fi
  unset _env_changed _auto_val
  echo ""
  echo "=== sync missing .env keys from .env.example ==="
  bash "$APP_DIR/scripts/sync_env.sh"
fi

echo ""
echo "=== USB capture (turntable / line-in for bars + cast) ==="
bash "$APP_DIR/scripts/setup_usb_capture.sh"

if [[ -f "$APP_DIR/.env" ]] && [[ -x "$APP_DIR/scripts/tune_usb_gain.sh" ]]; then
  echo ""
  echo "=== USB gain (~/.vinyl/calibration.json) ==="
  if [[ -f "$HOME/.vinyl/calibration.json" ]]; then
    echo "  calibration: $HOME/.vinyl/calibration.json"
  else
    echo "  no calibration yet — while playing a record:"
    echo "  bash scripts/tune_usb_gain.sh 3"
  fi
fi

if command -v systemctl >/dev/null 2>&1; then
  echo ""
  echo "=== getty / autologin ==="
  if systemctl is-failed getty@tty1.service 2>/dev/null | grep -q failed; then
    sudo systemctl reset-failed getty@tty1.service 2>/dev/null || true
    sudo systemctl start getty@tty1.service 2>/dev/null || true
    echo "  reset failed getty@tty1 (was blocking startx on tty1)"
  else
    echo "  getty@tty1: $(systemctl is-active getty@tty1.service 2>/dev/null || echo unknown)"
  fi

  echo ""
  echo "=== SSH ==="
  if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_ssh 0 2>/dev/null || true
  fi
  for svc in ssh sshd; do
    if systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "${svc}.service"; then
      sudo systemctl enable "${svc}.service" 2>/dev/null || true
      sudo systemctl start "${svc}.service" 2>/dev/null || true
      echo "  ${svc}: $(systemctl is-active "${svc}.service" 2>/dev/null || echo unknown)"
    fi
  done
  echo "  IP: $(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -3 | tr '\n' ' ')"
fi

if [[ "$REPAIR_CONFIG" -eq 1 ]]; then
  echo ""
  echo "=== repair config.txt (rotate=${ROTATE} panel=${PANEL}) ==="
  sudo bash "$APP_DIR/scripts/repair_pitft_config.sh" "$ROTATE" "$PANEL"
fi

if [[ "$DISPLAY_FIX" -eq 1 ]]; then
  echo ""
  echo "=== display fix (rotate=${ROTATE} panel=${PANEL}) ==="
  for p in /boot/firmware/config.txt /boot/config.txt; do
    if [[ -f "$p" ]] && grep -qE '^dtoverlay=pitft28.*drm' "$p"; then
      echo "  removing ,drm from $p (breaks X fbdev → black TFT)"
      sudo sed -i '/^dtoverlay=pitft28/s/,drm//g; s/drm,//g' "$p"
    fi
  done
  sudo bash "$APP_DIR/scripts/setup_pitft.sh" "$ROTATE" "$PANEL" "$USER_NAME"
fi

if [[ "$STRIP_BUTTONS" -eq 1 ]]; then
  echo ""
  echo "=== strip plate button overlays ==="
  sudo bash "$APP_DIR/scripts/remove_pitft_buttons.sh"
fi

if [[ "$INSTALL_BUTTONS" -eq 1 ]]; then
  echo ""
  echo "=== plate buttons (GPIO 17/22/23/27 — NOT 25) ==="
  sudo bash "$APP_DIR/scripts/setup_pitft_buttons.sh"
fi

echo ""
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "  venv: ok"
else
  echo "  WARN: no venv — python3 -m venv .venv && pip install -r requirements.txt"
fi

if pgrep -x Xorg >/dev/null 2>&1; then
  echo "  Xorg running — test: DISPLAY=:0 bash scripts/start_app.sh"
else
  echo "  Xorg not running — reboot after recover"
fi

echo ""
echo "Next: sudo reboot"
echo "Report: bash scripts/diagnose_boot.sh --report"
echo "Undo kiosk: sudo ./scripts/restore_desktop.sh"
