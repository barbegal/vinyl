#!/usr/bin/env bash
# One-shot recovery when the TFT is black, start_app fails, or scripts won't run.
# Safe to run after every git pull.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

echo "=== vinyl recover ==="
echo "App dir: $APP_DIR"

chmod +x scripts/*.sh
echo "  fixed execute bits on scripts/*.sh"

bash scripts/fix_ssh.sh

./scripts/refresh_xinitrc.sh

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "  created .env from .env.example"
else
  echo "  .env already exists (not overwritten)"
fi

if command -v systemctl >/dev/null 2>&1; then
  echo ""
  echo "=== SSH (kiosk mode should keep this enabled) ==="
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
  echo "  Pi IP(s): $(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -3 | tr '\n' ' ')"
fi

echo ""
echo "=== quick test (optional) ==="
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "  venv: ok"
else
  echo "  WARN: no venv — run: python3 -m venv .venv && pip install -r requirements.txt"
fi

if pgrep -x Xorg >/dev/null 2>&1; then
  echo "  Xorg is running — try: DISPLAY=:0 bash scripts/start_app.sh"
else
  echo "  Xorg not running — reboot after recover: sudo reboot"
fi

echo ""
echo "=== next ==="
echo "  sudo reboot"
echo "  then: bash scripts/diagnose_boot.sh"
echo ""
echo "Still broken? Full desktop restore (undo kiosk): sudo ./scripts/restore_desktop.sh && sudo reboot"
