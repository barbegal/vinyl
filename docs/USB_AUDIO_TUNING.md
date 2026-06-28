# USB line-in → Chromecast gain staging

Findings from tuning a **USB PnP Audio Device** (turntable / phono → Pi → Cast). Applies to
most cheap USB line-in interfaces on this project.

## Signal chain

| Stage | Control | Purpose |
|--------|---------|---------|
| 1. Analog | Phono / interface knob | Level **into** the USB ADC |
| 2. ALSA capture | `Mic Capture Volume` (card-specific) | USB device digital gain **before** capture |
| 3. ffmpeg | `CAST_INPUT_GAIN_DB` in `.env` | Small digital trim before encode (not a fix for clip) |
| 4. ffmpeg EQ | `CAST_STREAM_EQ`, `CAST_HIGH_CUT_HZ` | Rumble + harsh USB hash |
| 5. Encode | `CAST_STREAM_CODEC=wav` (default) | Lossless LAN stream |
| 6. Chromecast | `CAST_OUTPUT_VOLUME` | **Listening level only** — does not improve clipped tone |

**Richest tone:** fix headroom at stage **1–2**. Stages 3–6 shape and level what is already
captured; they cannot restore waveform flattened by ADC clipping.

## Targets ( loud passage on a record )

| Point | Target |
|--------|--------|
| USB ADC peak (`introspect_audio.sh`) | **-12 to -6 dBFS** (peak ≈ 8k–18k, **not** 32768) |
| After `CAST_INPUT_GAIN_DB` | **-18 to -12 dBFS** internal headroom |
| `CAST_OUTPUT_VOLUME` | **0.28–0.40** by ear (default **0.32**) |

Quiet grooves at **-40 dBFS** or lower are normal; bar meters use auto-range for display.

## Pi findings (USB PnP, card 3)

- **Device:** `card 3: Device [USB PnP Audio Device]` → `USB_ALSA_DEVICE=vinyl_in` (dsnoop on `hw:3,0`)
- **Default trap:** `Mic Capture Volume` shipped at **max (62/62)** → **peak=32768** (hard clip), RMS ≈ **-1 dBFS**
- **`CAST_INPUT_GAIN_DB=-21`** only attenuated **after** clip — bars and cast sounded maxed / thin
- **Stereo:** both L/R live at USB (`debug_usb_stereo.sh`); use `CAST_STEREO_MODE=stereo`. `duplicate_r` was a mistaken workaround when L appeared dead on cast
- **EQ:** `CAST_HIGH_CUT_HZ=14000` keeps more air than 12 kHz; `CAST_STREAM_EQ=1` high-pass 40 Hz

### ALSA mixer quirk

On this interface, **`amixer sset 'Mic Capture Volume'` fails** even though the control exists.
Use **`cset`** on **numid=3** (range 0–62):

```bash
# ~45% capture (val 28/62) — starting point; tune while playing
amixer -c 3 cset numid=3 28
amixer -c 3 cget numid=3
```

Verify with:

```bash
bash scripts/introspect_audio.sh 3      # peaks must not be 32768
bash scripts/debug_usb_stereo.sh 5      # L/R + PortAudio path
```

## One-shot auto-tune

While playing a **loud** passage:

```bash
bash scripts/tune_usb_gain.sh 3
# or: python -m src.audio.gain_calibration 3
```

This writes **`~/.vinyl/calibration.json`** (not `.env`):

- ALSA Mic Capture level (`cset numid=3`)
- `cast_input_gain_db`, `cast_output_volume`, `cast_stereo_mode`, etc.

On boot, Python loads calibration automatically (`VINYL_AUTO_CALIBRATE=1` in `.env`).
Re-calibrates when the saved capture was still clipping (peak=32768).

**.env overrides:** set `CAST_INPUT_GAIN_DB=…` explicitly to force a value and skip
calibration for that key.

## Recommended calibration targets

| Script | Role |
|--------|------|
| `scripts/tune_usb_gain.sh` | Wrapper → `python -m src.audio.gain_calibration` |
| `src/audio/gain_calibration.py` | Core logic + `~/.vinyl/calibration.json` |
| `scripts/introspect_audio.sh` | Quick L/R levels + clip / stereo hints |
| `scripts/debug_usb_stereo.sh` | Deep L/R + sounddevice; writes `/tmp/vinyl-channel-L.wav` |
| `scripts/test_usb_audio.sh` | Short capture smoke test |
| `scripts/setup_usb_capture.sh` | `~/.asoundrc` dsnoop → `vinyl_in` |
