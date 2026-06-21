#!/usr/bin/env bash
# Diagnose kiosk boot (tty1 autologin -> startx -> cast app).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$USER_NAME")"

echo "=== boot config ==="
echo "default target: $(systemctl get-default 2>/dev/null || echo unknown)"
echo "getty@tty1:     $(systemctl is-enabled getty@tty1.service 2>/dev/null || echo unknown) / $(systemctl is-active getty@tty1.service 2>/dev/null || echo unknown)"

AUTLOGIN="/etc/systemd/system/getty@tty1.service.d/autologin.conf"
if [[ -f "$AUTLOGIN" ]]; then
  echo "autologin override:"
  grep -E '^ExecStart' "$AUTLOGIN" | sed 's/^/  /'
else
  echo "autologin override: MISSING — run ./scripts/install_service.sh"
fi

echo ""
echo "=== old systemd unit (should be gone) ==="
if [[ -f /etc/systemd/system/pi-audio-cast-display.service ]]; then
  echo "WARNING: old service still present — run ./scripts/install_service.sh to remove it"
else
  echo "none (good)"
fi

echo ""
echo "=== user session files ==="
[[ -f "$USER_HOME/.xinitrc" ]] && echo ".xinitrc: present" || echo ".xinitrc: MISSING"
if grep -qF "pi-audio-cast-display startx" "$USER_HOME/.bash_profile" 2>/dev/null; then
  echo ".bash_profile startx guard: present"
else
  echo ".bash_profile startx guard: MISSING"
fi

echo ""
echo "=== tools ==="
command -v xinit  >/dev/null && echo "xinit:  $(command -v xinit)"  || echo "xinit:  NOT INSTALLED"
command -v startx >/dev/null && echo "startx: $(command -v startx)" || echo "startx: NOT INSTALLED"
command -v Xorg   >/dev/null && echo "Xorg:   $(command -v Xorg)"   || echo "Xorg:   NOT INSTALLED"
[[ -f /etc/X11/Xwrapper.config ]] && { echo "Xwrapper.config:"; sed 's/^/  /' /etc/X11/Xwrapper.config; } || echo "Xwrapper.config: none"
[[ -x "$APP_DIR/.venv/bin/python" ]] && echo "venv: ok" || echo "venv: MISSING at $APP_DIR/.venv"

echo ""
echo "=== last X errors ==="
tail -n 20 "$USER_HOME/.local/share/xorg/Xorg.0.log" 2>/dev/null | grep -E '\(EE\)|\(WW\)' || echo "(no recent EE/WW lines)"
