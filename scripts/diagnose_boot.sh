#!/usr/bin/env bash
# Print recent boot failures for the cast display service.
set -euo pipefail

echo "=== pi-audio-cast-display status ==="
systemctl status pi-audio-cast-display.service --no-pager -l 2>/dev/null || true

echo ""
echo "=== last 40 log lines ==="
journalctl -u pi-audio-cast-display.service -n 40 --no-pager 2>/dev/null || true

echo ""
echo "=== X / VT checks ==="
echo "getty@tty1: $(systemctl is-active getty@tty1.service 2>/dev/null || echo unknown)"
echo "default target: $(systemctl get-default 2>/dev/null || echo unknown)"
command -v xinit >/dev/null && echo "xinit: $(command -v xinit)" || echo "xinit: NOT INSTALLED"
command -v Xorg >/dev/null && echo "Xorg: $(command -v Xorg)" || echo "Xorg: NOT INSTALLED"
[[ -f /etc/X11/Xwrapper.config ]] && cat /etc/X11/Xwrapper.config || echo "no Xwrapper.config"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -x "$APP_DIR/.venv/bin/python" ]] && echo "venv: ok" || echo "venv: MISSING at $APP_DIR/.venv"
