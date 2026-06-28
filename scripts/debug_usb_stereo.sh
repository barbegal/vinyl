#!/usr/bin/env bash
# Deep USB line-in stereo debug — run while playing a record.
# Captures via ALSA + PortAudio, prints per-channel stats, writes mono audition files.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/.env"
SECS="${1:-4}"
OUT="/tmp/vinyl-stereo-debug.wav"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=load_env.sh
  VINYL_ENV_FILE="$ENV_FILE" source "$APP_DIR/scripts/load_env.sh"
  set +a
fi

DEV="${USB_ALSA_DEVICE:-vinyl_in}"
PY="${APP_DIR}/.venv/bin/python3"
[[ -x "$PY" ]] || PY="python3"

echo "=== vinyl USB stereo debug ==="
echo "Capture device: $DEV (${SECS}s — play a record now)"
echo ""

arecord -l 2>/dev/null | sed 's/^/  /' || true
echo ""

CARD=""
if [[ -f "${HOME}/.asoundrc" ]]; then
  CARD="$(grep -oE 'pcm "hw:[0-9]+' "${HOME}/.asoundrc" | head -1 | tr -dc '0-9' || true)"
fi
if [[ -n "$CARD" ]]; then
  echo "ALSA mixer (card $CARD):"
  amixer -c "$CARD" sget "Mic Capture Switch" 2>/dev/null | sed 's/^/  /' || true
  amixer -c "$CARD" sget "Mic Capture Volume" 2>/dev/null | sed 's/^/  /' || true
  amixer -c "$CARD" cget numid=1 2>/dev/null | sed 's/^/  /' || true
  echo ""
fi

if ! arecord -D "$DEV" -f S16_LE -r 48000 -c 2 -d "$SECS" "$OUT" 2>/dev/null; then
  echo "ERROR: arecord failed on $DEV (device busy? stop cast or use vinyl_in dsnoop)"
  exit 1
fi

export VINYL_DEBUG_WAV="$OUT"
export VINYL_DEBUG_APP_DIR="$APP_DIR"
"$PY" <<'PY'
from __future__ import annotations

import math
import os
import struct
import sys
import wave
from pathlib import Path

import numpy as np

wav_path = Path(os.environ["VINYL_DEBUG_WAV"])
app_dir = Path(os.environ["VINYL_DEBUG_APP_DIR"])
sys.path.insert(0, str(app_dir))

from src.audio.alsa_device import portaudio_device_hint
from src.audio.input_listener import AudioInputListener


def load_lr(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    samples = np.array(struct.unpack(f"<{len(raw)//2}h", raw), dtype=np.float64)
    return samples[0::2], samples[1::2]


def analyze(label: str, L: np.ndarray, R: np.ndarray) -> None:
    lr = math.sqrt(float(np.mean(L * L)))
    rr = math.sqrt(float(np.mean(R * R)))
    diff = L - R
    dr = math.sqrt(float(np.mean(diff * diff)))
    corr = float(np.sum(L * R) / max(math.sqrt(float(np.sum(L * L) * np.sum(R * R))), 1.0))
    l_peak = int(np.max(np.abs(L)))
    r_peak = int(np.max(np.abs(R)))
    l_act = 100.0 * float(np.mean(np.abs(L) > 500))
    r_act = 100.0 * float(np.mean(np.abs(R) > 500))
    l_db = 20 * math.log10(max(lr, 1) / 32768.0)
    r_db = 20 * math.log10(max(rr, 1) / 32768.0)

    print(f"{label}")
    print(f"  L: peak={l_peak:5d}  rms={lr:8.1f}  ({l_db:+.1f} dBFS)  active={l_act:.1f}%")
    print(f"  R: peak={r_peak:5d}  rms={rr:8.1f}  ({r_db:+.1f} dBFS)  active={r_act:.1f}%")
    print(f"  corr={corr:.3f}  channel-diff/rmsR={dr / max(rr, 1):.3f}")

    if l_peak < 500 and r_peak > 2000:
        print("  → LEFT input dead/silent — check white RCA / interface L jack")
    elif r_peak < 500 and l_peak > 2000:
        print("  → RIGHT input dead/silent — check red RCA / interface R jack")
    elif l_act > 5 and r_act > 5 and corr < 0.98:
        print("  → both channels live with stereo content")
    elif l_act > 5 and r_act > 5:
        print("  → dual-mono (L≈R) — turntable mono or summed upstream")


L, R = load_lr(wav_path)
print("arecord", wav_path.name)
analyze("", L, R)
print("")

# Mono audition files (scp these back to your laptop and listen)
for name, data in (("L", L), ("R", R)):
    mono_path = Path(f"/tmp/vinyl-channel-{name}.wav")
    with wave.open(str(mono_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        clipped = np.clip(data, -32768, 32767).astype(np.int16)
        w.writeframes(clipped.tobytes())
    print(f"Wrote {mono_path} — audition this file to hear the {name} channel alone")

print("")
print("PortAudio devices (same path as level bars):")
try:
    import sounddevice as sd
except ImportError:
    print("  sounddevice not installed — skip")
    sd = None

if sd is not None:
    hints = []
    for name in ("vinyl_dsnoop", "vinyl_in"):
        hints.append(name)
    hint = portaudio_device_hint(os.environ.get("USB_ALSA_DEVICE", "vinyl_in"))
    if hint and hint.lower() not in hints:
        hints.append(hint.lower())

    chosen = None
    for h in hints:
        for idx, dev in enumerate(sd.query_devices()):
            name = str(dev.get("name", "")).lower()
            if dev.get("max_input_channels", 0) > 0 and h in name:
                chosen = idx
                break
        if chosen is not None:
            break

    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) <= 0:
            continue
        mark = " ← app picks this" if idx == chosen else ""
        print(f"  [{idx}] {dev.get('name')} in={dev.get('max_input_channels')}{mark}")

    if chosen is not None:
        try:
            rec = sd.rec(int(48000 * 2), samplerate=48000, channels=2, device=chosen, dtype="float32")
            sd.wait()
            L2 = rec[:, 0].astype(np.float64) * 32768.0
            R2 = rec[:, 1].astype(np.float64) * 32768.0
            print("")
            analyze(f"sounddevice [{chosen}]", L2, R2)
        except Exception as exc:
            print(f"  sounddevice capture failed: {exc}")

print("")
print("Suggested .env:")
if np.max(np.abs(L)) < 500 and np.max(np.abs(R)) > 2000:
    print("  CAST_STEREO_MODE=duplicate_r   # only R has signal")
elif np.max(np.abs(R)) < 500 and np.max(np.abs(L)) > 2000:
    print("  CAST_STEREO_MODE=duplicate     # only L has signal")
else:
    print("  CAST_STEREO_MODE=stereo        # both channels live")
    if float(np.sum(L * R)) < 0:
        print("  # or CAST_STEREO_MODE=swap if L/R seem reversed on speakers")
PY

echo ""
echo "Full stereo wav: $OUT"
echo "Re-run: bash scripts/debug_usb_stereo.sh 5"
