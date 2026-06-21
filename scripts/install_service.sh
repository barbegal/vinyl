#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_TEMPLATE="$APP_DIR/services/pi-audio-cast-display.service"
SERVICE_PATH="/etc/systemd/system/pi-audio-cast-display.service"
USER_NAME="${SUDO_USER:-$USER}"

if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
  echo "Missing service template: $SERVICE_TEMPLATE"
  exit 1
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

sed \
  -e "s|@APP_DIR@|$APP_DIR|g" \
  -e "s|@RUN_USER@|$USER_NAME|g" \
  "$SERVICE_TEMPLATE" > "$TMP_FILE"

sudo cp "$TMP_FILE" "$SERVICE_PATH"
sudo chmod 644 "$SERVICE_PATH"
sudo systemctl daemon-reload
sudo systemctl enable pi-audio-cast-display.service
sudo systemctl restart pi-audio-cast-display.service

echo "Installed and started pi-audio-cast-display.service"
echo "Check status with: sudo systemctl status pi-audio-cast-display.service"
