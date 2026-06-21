#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_TEMPLATE="$APP_DIR/services/pi-audio-cast-display.service"
SERVICE_PATH="/etc/systemd/system/pi-audio-cast-display.service"
USER_NAME="${SUDO_USER:-$USER}"

if [[ "$USER_NAME" == "root" ]]; then
  echo "Run as your normal user (not root): ./scripts/install_service.sh"
  exit 1
fi

if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
  echo "Missing service template: $SERVICE_TEMPLATE"
  exit 1
fi

echo "=== Installing X packages (xinit, Xorg) ==="
sudo apt-get install -y xinit xserver-xorg

for cmd in xinit Xorg; do
  if ! command -v "$cmd" >/dev/null; then
    echo "ERROR: $cmd not found after apt install"
    exit 1
  fi
done

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "ERROR: venv missing at $APP_DIR/.venv"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

chmod +x "$APP_DIR/scripts/start_app.sh" "$APP_DIR/scripts/xinitrc"
chmod +x "$APP_DIR/scripts/enable_fast_boot.sh" "$APP_DIR/scripts/restore_desktop.sh" "$APP_DIR/scripts/diagnose_boot.sh"

echo "=== Fast boot: disabling Raspberry Pi Desktop ==="
sudo "$APP_DIR/scripts/enable_fast_boot.sh"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

sed \
  -e "s|@APP_DIR@|$APP_DIR|g" \
  -e "s|@RUN_USER@|$USER_NAME|g" \
  "$SERVICE_TEMPLATE" > "$TMP_FILE"

sudo cp "$TMP_FILE" "$SERVICE_PATH"
sudo chmod 644 "$SERVICE_PATH"

if grep -q openvt "$SERVICE_PATH"; then
  echo "ERROR: service still references openvt — git pull and retry"
  exit 1
fi

sudo systemctl daemon-reload
sudo systemctl enable pi-audio-cast-display.service
sudo systemctl restart pi-audio-cast-display.service

sleep 3

echo ""
echo "=== Installed service ==="
grep -E '^(ExecStart|ExecStartPre|User)=' "$SERVICE_PATH"

echo ""
if systemctl is-active --quiet pi-audio-cast-display.service; then
  echo "Status: active (running)"
else
  echo "Status: NOT running"
  sudo journalctl -u pi-audio-cast-display.service -n 25 --no-pager
  exit 1
fi

echo "Default boot target: $(systemctl get-default)"
echo "Reboot for clean boot test: sudo reboot"
