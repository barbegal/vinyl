#!/usr/bin/env bash
# Set USB capture level + cast gain for headroom and tone. Run while playing a record.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=load_env.sh
  VINYL_ENV_FILE="$ENV_FILE" source "$APP_DIR/scripts/load_env.sh"
  set +a
fi

CARD=""
if [[ -f "${HOME}/.asoundrc" ]]; then
  CARD="$(grep -oE 'pcm "hw:[0-9]+' "${HOME}/.asoundrc" | head -1 | tr -dc '0-9' || true)"
fi
if [[ -z "$CARD" ]] && [[ -f "$ENV_FILE" ]]; then
  _hw="$(grep -E '^USB_ALSA_DEVICE=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  CARD="$(echo "$_hw" | grep -oE '[0-9]+' | head -1 || true)"
fi
CARD="${CARD:-3}"

CAP_CTL="Mic Capture Volume"
SECS="${1:-2}"

echo "=== tune USB gain (card $CARD) ==="
echo "Play a loud passage on the record now…"
echo ""

set_env() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >>"$ENV_FILE"
  fi
}

best_pct=50
best_peak=32768
best_rms_db=0

for pct in 60 55 50 45 40 35; do
  if amixer -c "$CARD" sget "$CAP_CTL" >/dev/null 2>&1; then
    amixer -c "$CARD" sset "$CAP_CTL" "${pct}%" >/dev/null
    echo "  Mic Capture Volume → ${pct}%"
  else
    echo "  WARN: no '$CAP_CTL' on card $CARD — set interface gain by hand"
    break
  fi

  OUT="/tmp/vinyl-tune-$$.wav"
  if ! arecord -D "${USB_ALSA_DEVICE:-vinyl_in}" -f S16_LE -r 48000 -c 2 -d "$SECS" "$OUT" 2>/dev/null; then
    echo "  capture failed (cast running? stop cast and retry)"
    rm -f "$OUT"
    continue
  fi

  read -r peak rms_db <<<"$(python3 - "$OUT" <<'PY'
import struct, sys, wave, math
path = sys.argv[1]
with wave.open(path, "rb") as w:
    raw = w.readframes(w.getnframes())
s = struct.unpack(f"<{len(raw)//2}h", raw)
peak = max(abs(x) for x in s)
rms = math.sqrt(sum(x * x for x in s) / max(len(s), 1))
db = 20 * math.log10(max(rms, 1) / 32768.0)
print(peak, f"{db:.1f}")
PY
)"
  rm -f "$OUT"
  echo "    peak=$peak  rms=${rms_db} dBFS"

  best_pct="$pct"
  best_peak="$peak"
  best_rms_db="$rms_db"

  if [[ "$peak" -lt 32760 ]] && [[ "$peak" -gt 3000 ]]; then
    echo "  OK: headroom at ${pct}%"
    break
  fi
  if [[ "$peak" -lt 3000 ]]; then
    echo "  very quiet — try ${pct}% or raise phono gain slightly"
    break
  fi
done

# Digital trim: land peaks ~-12 to -18 dBFS after ffmpeg (only if ADC not clipping)
if [[ "$best_peak" -ge 32760 ]]; then
  gain=-15
  echo ""
  echo "  still clipping — using CAST_INPUT_GAIN_DB=${gain} (lower Mic Capture more)"
elif [[ "$best_peak" -gt 20000 ]]; then
  gain=-12
elif [[ "$best_peak" -gt 12000 ]]; then
  gain=-9
else
  gain=-6
fi

if [[ -f "$ENV_FILE" ]]; then
  set_env CAST_INPUT_GAIN_DB "$gain"
  set_env CAST_HIGH_CUT_HZ 14000
  set_env CAST_OUTPUT_VOLUME 0.32
  set_env CAST_STREAM_EQ 1
  set_env CAST_STEREO_MODE stereo
  if grep -qE '^AUDIO_LEVEL_INPUT_TRIM_DB=' "$ENV_FILE" 2>/dev/null; then
    sed -i 's|^AUDIO_LEVEL_INPUT_TRIM_DB=.*|AUDIO_LEVEL_INPUT_TRIM_DB=|' "$ENV_FILE"
  fi
  echo ""
  echo "Updated $ENV_FILE:"
  grep -E '^(CAST_INPUT_GAIN_DB|CAST_HIGH_CUT_HZ|CAST_OUTPUT_VOLUME|CAST_STEREO_MODE)=' "$ENV_FILE" \
    | sed 's/^/  /'
fi

echo ""
echo "Mic Capture: ${best_pct}%  ADC peak≈$best_peak  rms≈${best_rms_db} dBFS"
echo "Reboot or restart cast for ffmpeg to pick up .env changes."
