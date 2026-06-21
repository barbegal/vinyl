#!/usr/bin/env bash
# One-shot recovery: permissions, SSH-safe login hooks, xinitrc, .env.
#   bash scripts/recover.sh              — usual fix after git pull
#   bash scripts/recover.sh --repair-config [rotation] [28r|28c] — nuclear config.txt fix
#   bash scripts/recover.sh --display 270 28c
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
USER_NAME="${USER:-$(whoami)}"
USER_HOME="${HOME}"

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
fi

if command -v systemctl >/dev/null 2>&1; then
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
