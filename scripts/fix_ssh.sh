#!/usr/bin/env bash
# Fix SSH after boot/profile edits broke remote login.
# Common cause: exec startx in .profile without skipping SSH sessions.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$USER_NAME")"
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

echo "=== vinyl fix_ssh ==="

fix_profile_guards() {
  for PROFILE in "$USER_HOME/.profile" "$USER_HOME/.bash_profile"; do
    if [[ ! -f "$PROFILE" ]]; then
      continue
    fi
    if grep -qF "$MARKER" "$PROFILE"; then
      sed -i '/# >>> pi-audio-cast-display startx >>>/,/# <<< pi-audio-cast-display startx <<</d' "$PROFILE"
      printf '%s\n' "$SAFE_GUARD" >> "$PROFILE"
      echo "  replaced startx guard in $PROFILE (SSH-safe)"
    elif grep -qE 'exec startx|startx' "$PROFILE"; then
      echo "  WARN: $PROFILE contains startx but not our marker — review manually:"
      grep -n 'startx' "$PROFILE" | sed 's/^/    /'
    fi
  done
}

fix_profile_guards

if [[ -f /etc/profile.d/vinyl-kiosk.sh ]]; then
  if ! grep -q 'SSH_CONNECTION' /etc/profile.d/vinyl-kiosk.sh; then
    echo "  WARN: /etc/profile.d/vinyl-kiosk.sh missing SSH guard"
    echo "        Re-run: sudo $APP_DIR/scripts/enable_fast_boot.sh"
  else
    echo "  /etc/profile.d/vinyl-kiosk.sh: SSH guard ok"
  fi
fi

echo ""
echo "=== enabling SSH service ==="
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_ssh 0 2>/dev/null || true
  echo "  raspi-config: SSH enabled"
fi
for svc in ssh sshd; do
  if systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "${svc}.service"; then
    sudo systemctl enable "${svc}.service" 2>/dev/null || true
    sudo systemctl restart "${svc}.service" 2>/dev/null || true
    echo "  ${svc}: $(systemctl is-active "${svc}.service" 2>/dev/null || echo unknown)"
  fi
done

echo ""
echo "  Pi IP(s): $(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -5 | tr '\n' ' ')"
echo ""
echo "Try SSH from your laptop:"
echo "  ssh ${USER_NAME}@<pi-ip>"
echo ""
echo "If SSH still fails with no local login, on another PC mount the SD card and:"
echo "  touch boot/firmware/ssh   # or boot/ssh on older images"
echo "  then reboot the Pi"
