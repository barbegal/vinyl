#!/usr/bin/env bash
# Inspect USB line-in: stereo channels, levels, and suggested .env fixes.
# Run while playing a record: bash scripts/introspect_audio.sh
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
SECS="${1:-3}"
OUT="/tmp/vinyl-introspect-$$.wav"

echo "=== vinyl audio introspect ==="
echo "Device: $DEV (${SECS}s capture — play a record now)"
echo ""

arecord -l 2>/dev/null | sed 's/^/  /' || true
echo ""

if ! arecord -D "$DEV" -f S16_LE -r 48000 -c 2 -d "$SECS" "$OUT" 2>/dev/null; then
  echo "ERROR: capture failed (device busy? stop cast or use vinyl_in via dsnoop)"
  exit 1
fi

python3 - "$OUT" <<'PY'
import struct, sys, wave, math

path = sys.argv[1]
with wave.open(path, "rb") as w:
    ch = w.getnchannels()
    rate = w.getframerate()
    frames = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(frames)//2}h", frames)

if ch >= 2:
    L = samples[0::2]
    R = samples[1::2]
else:
    L = R = samples

def stats(name, arr):
    if not arr:
        return None
    peak = max(abs(x) for x in arr)
    rms = math.sqrt(sum(x * x for x in arr) / len(arr))
    db = 20 * math.log10(max(rms, 1) / 32768.0)
    return peak, rms, db

print(f"Captured: {ch}ch @ {rate} Hz, {len(L)} frames/channel")
for name, arr in (("L", L), ("R", R)):
    s = stats(name, arr)
    if s:
        peak, rms, db = s
        print(f"  {name}: peak={peak:5d}  rms={rms:8.1f}  ({db:+.1f} dBFS)")

if ch >= 2 and L and R:
    l_peak = max(abs(x) for x in L)
    r_peak = max(abs(x) for x in R)
    lr = sum(a * b for a, b in zip(L, R))
    ll = sum(a * a for a in L) or 1
    rr = sum(b * b for b in R) or 1
    corr = lr / math.sqrt(ll * rr)
    l_rms = math.sqrt(ll / len(L))
    r_rms = math.sqrt(rr / len(R))
    diff_rms = math.sqrt(sum((a - b) ** 2 for a, b in zip(L, R)) / len(L))
    print(f"  L/R correlation: {corr:.3f}")
    print(f"  L/R rms ratio: {l_rms / max(r_rms, 1):.3f}  diff/rmsR: {diff_rms / max(r_rms, 1):.3f}")
    print("")
    if l_peak < 500 and r_peak > 2000:
        print("DIAG: signal mostly on RIGHT — set CAST_STEREO_MODE=duplicate_r")
    elif r_peak < 500 and l_peak > 2000:
        print("DIAG: signal mostly on LEFT — set CAST_STEREO_MODE=duplicate")
    elif corr > 0.98 and abs(l_peak - r_peak) < max(l_peak, r_peak) * 0.05:
        print("DIAG: dual-mono / identical channels")
    else:
        print("DIAG: stereo — set CAST_STEREO_MODE=stereo")
        print("      run: bash scripts/debug_usb_stereo.sh 5")

l_stats = stats("L", L)
if l_stats and l_stats[0] >= 32760:
    print("")
    print("DIAG: ADC clipping (peak=32768) — lower capture volume:")
    print("      amixer -c <card> sset Capture 80%   # or reduce phono/interface gain")
if l_stats and l_stats[2] > -6:
    print("")
    print("DIAG: input very hot — try CAST_INPUT_GAIN_DB=-24 in .env")
    print("      (meters inherit CAST_INPUT_GAIN_DB via AUDIO_LEVEL_INPUT_TRIM_DB)")
if l_stats and l_stats[2] > -12:
    print("DIAG: tinny USB interfaces — enable CAST_STREAM_EQ=1 CAST_HIGH_CUT_HZ=12000")
PY

echo ""
echo "Wav saved: $OUT"
echo "Meter tuning: AUDIO_LEVEL_AUTO_RANGE=1  AUDIO_LEVEL_INPUT_TRIM_DB=<same as CAST_INPUT_GAIN_DB>"
