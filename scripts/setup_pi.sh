#!/usr/bin/env bash
# One-shot Raspberry Pi setup after a fresh SD card flash.
#
#   git clone <repo-url> ~/Desktop/vinyl
#   cd ~/Desktop/vinyl && bash scripts/setup_pi.sh
#
# Options:
#   --buttons     enable plate GPIO keys (optional)
#   --connect     install x11vnc + Raspberry Pi Connect mirror
#   --no-reboot   skip the reboot prompt at the end
#
# Override panel/rotation (defaults: resistive 28r, rotate 270):
#   PITFT_TYPE=28c PITFT_ROTATE=90 bash scripts/setup_pi.sh
#
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

INSTALL_BUTTONS=0
SETUP_CONNECT=0
PROMPT_REBOOT=1

usage() {
  cat <<EOF
Usage: bash scripts/setup_pi.sh [--buttons] [--connect] [--no-reboot]

Fresh Pi install: apt packages, Python venv, PiTFT (28r @ 270°), kiosk boot, .env, USB capture.

Env overrides: PITFT_TYPE=28r|28c   PITFT_ROTATE=0|90|180|270
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --buttons) INSTALL_BUTTONS=1; shift ;;
    --connect) SETUP_CONNECT=1; shift ;;
    --no-reboot) PROMPT_REBOOT=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as your normal user (not root): bash scripts/setup_pi.sh"
  exit 1
fi

export PITFT_TYPE="${PITFT_TYPE:-28r}"
export PITFT_ROTATE="${PITFT_ROTATE:-270}"

echo "=== vinyl setup_pi ==="
echo "App dir: $APP_DIR"
echo "PiTFT: ${PITFT_TYPE} rotate=${PITFT_ROTATE}"
echo ""

echo "=== apt packages ==="
sudo apt-get update
sudo apt-get install -y \
  python3-venv python3-tk ffmpeg portaudio19-dev fonts-roboto \
  xinit xserver-xorg x11-xserver-utils alsa-utils

echo ""
echo "=== Python venv ==="
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
pip install -U pip wheel
pip install -r "$APP_DIR/requirements.txt"

echo ""
echo "=== .env ==="
if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "  created .env from .env.example"
fi
if [[ "$PITFT_ROTATE" == "270" ]]; then
  if grep -qE '^PLATE_BUTTONS_SIDE=' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^PLATE_BUTTONS_SIDE=.*/PLATE_BUTTONS_SIDE=left/' "$APP_DIR/.env"
  else
    printf '\nPLATE_BUTTONS_SIDE=left\n' >>"$APP_DIR/.env"
  fi
elif [[ "$PITFT_ROTATE" == "90" ]]; then
  if grep -qE '^PLATE_BUTTONS_SIDE=' "$APP_DIR/.env" 2>/dev/null; then
    sed -i 's/^PLATE_BUTTONS_SIDE=.*/PLATE_BUTTONS_SIDE=right/' "$APP_DIR/.env"
  fi
fi

echo ""
echo "=== USB audio (turntable / line-in) ==="
if command -v arecord >/dev/null 2>&1; then
  arecord -l 2>/dev/null | sed 's/^/  /' || true
  echo "  Edit .env → USB_ALSA_DEVICE=hw:N,0 (card from arecord -l above), then re-run recover if needed."
else
  echo "  arecord not found — plug in USB interface and set USB_ALSA_DEVICE in .env"
fi

echo ""
echo "=== kiosk boot + PiTFT ==="
chmod +x "$APP_DIR/scripts/"*.sh
chmod +x "$APP_DIR/scripts/show_boot_error.py" 2>/dev/null || true
"$APP_DIR/scripts/install_service.sh"

echo ""
echo "=== recover (xinitrc, USB capture, SSH) ==="
_recover_args=()
[[ "$INSTALL_BUTTONS" -eq 1 ]] && _recover_args+=(--buttons)
bash "$APP_DIR/scripts/recover.sh" "${_recover_args[@]}"
unset _recover_args

if [[ "$SETUP_CONNECT" -eq 1 ]]; then
  echo ""
  echo "=== remote TFT mirror (x11vnc + Raspberry Pi Connect) ==="
  bash "$APP_DIR/scripts/setup_rpconnect.sh"
fi

echo ""
echo "=== setup complete ==="
echo "  Panel: ${PITFT_TYPE} @ ${PITFT_ROTATE}°"
echo "  Web UI: http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/ (after reboot)"
if [[ "$PROMPT_REBOOT" -eq 1 ]]; then
  echo ""
  read -r -p "Reboot now? [Y/n] " _ans
  if [[ -z "$_ans" || "$_ans" =~ ^[Yy]$ ]]; then
    sudo reboot
  else
    echo "Reboot when ready: sudo reboot"
  fi
else
  echo "Reboot when ready: sudo reboot"
fi
