#!/usr/bin/env bash
# Quick USB line-in check (turntable/interface). Run while playing a record.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=load_env.sh
  VINYL_ENV_FILE="$ENV_FILE" source "$APP_DIR/scripts/load_env.sh"
  set +a
fi

DEV="${USB_ALSA_DEVICE:-vinyl_in}"
CHANNELS="${AUDIO_CHANNELS:-2}"

echo "=== arecord -l ==="
arecord -l 2>/dev/null || true
echo
echo "=== capture test ($DEV, ${CHANNELS}ch, 2s) ==="
OUT="/tmp/vinyl-test-$$.wav"
if arecord -D "$DEV" -f S16_LE -r 48000 -c "$CHANNELS" -d 2 "$OUT"; then
  bytes=$(stat -c%s "$OUT" 2>/dev/null || stat -f%z "$OUT")
  echo "  recorded $bytes bytes → $OUT"
  if command -v python3 >/dev/null; then
    python3 - <<'PY' "$OUT"
import sys, wave, struct, math
path = sys.argv[1]
with wave.open(path, "rb") as w:
    frames = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(frames)//2}h", frames)
    peak = max(abs(s) for s in samples) if samples else 0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 0
    print(f"  peak={peak} rms={rms:.0f} (play a record — peak should rise above ~200)")
PY
  fi
else
  echo "  FAILED — try: bash scripts/setup_usb_capture.sh && grep USB_ALSA .env"
  exit 1
fi
