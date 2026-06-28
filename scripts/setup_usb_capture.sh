#!/usr/bin/env bash
# Shared USB line-in capture — level bars (sounddevice) and ffmpeg can open input together.
# the same input at once via ALSA dsnoop. Run from recover.sh or after USB card changes.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=load_env.sh
  VINYL_ENV_FILE="$ENV_FILE" source "$APP_DIR/scripts/load_env.sh"
  set +a
fi

HW="${USB_ALSA_DEVICE:-hw:2,0}"
PERIOD="${VINYL_ALSA_PERIOD_SIZE:-128}"
BUFFER="${VINYL_ALSA_BUFFER_SIZE:-512}"
if [[ "$HW" == "vinyl_in" ]]; then
  echo "  USB capture: already using vinyl_in"
  exit 0
fi

if [[ ! "$HW" =~ ^hw:[0-9]+,[0-9]+$ ]]; then
  echo "  USB capture: skip dsnoop (USB_ALSA_DEVICE=$HW — expected hw:N,M)"
  exit 0
fi

CARD="${HW#hw:}"
CARD="${CARD%%,*}"

if ! command -v arecord >/dev/null 2>&1; then
  echo "  USB capture: arecord missing — skip dsnoop"
  exit 0
fi

if ! arecord -l 2>/dev/null | grep -qE "^card ${CARD}:"; then
  echo "  USB capture: WARN — $HW not in arecord -l (check USB cable)"
fi

ASOUNDRC="${HOME}/.asoundrc"
BACKUP="${ASOUNDRC}.vinyl.bak"
if [[ -f "$ASOUNDRC" ]] && ! grep -q "pcm.vinyl_in" "$ASOUNDRC" 2>/dev/null; then
  cp -a "$ASOUNDRC" "$BACKUP"
  echo "  backed up $ASOUNDRC → $BACKUP"
fi

if [[ -f "$ASOUNDRC" ]] && grep -q "pcm.vinyl_in" "$ASOUNDRC" 2>/dev/null; then
  sed -i '/# vinyl — shared USB capture/,/^}/d' "$ASOUNDRC" 2>/dev/null || true
  sed -i '/^pcm\.vinyl_in {/,/^}/d' "$ASOUNDRC" 2>/dev/null || true
fi

cat >>"$ASOUNDRC" <<EOF

# vinyl — shared USB capture (level bars + ffmpeg cast stream)
pcm.vinyl_dsnoop {
  type dsnoop
  ipc_key 591237
  slave {
    pcm "$HW"
    channels 2
    period_size $PERIOD
    buffer_size $BUFFER
  }
}
pcm.vinyl_in {
  type plug
  slave.pcm "vinyl_dsnoop"
}
EOF

if [[ -f "$ENV_FILE" ]] && grep -q "^USB_ALSA_DEVICE=" "$ENV_FILE"; then
  sed -i "s|^USB_ALSA_DEVICE=.*|USB_ALSA_DEVICE=vinyl_in|" "$ENV_FILE"
fi

echo "  USB capture: ~/.asoundrc → vinyl_in (dsnoop on $HW)"
echo "  test: arecord -D vinyl_in -f S16_LE -r 48000 -c 2 -d 2 /tmp/vinyl-test.wav"
