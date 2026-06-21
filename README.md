# Pi Audio Cast Display

Fullscreen Raspberry Pi app that:

- starts on boot with `systemd`
- monitors USB audio input and renders live audio bars on a 320x240 touchscreen
- discovers Google Cast devices (prefers speaker groups)
- streams live USB input to selected target via Chromecast using local HLS

## Project layout

- `src/main.py`: app entrypoint
- `src/audio/`: audio input listener + level calculations
- `src/display/`: Tkinter fullscreen touchscreen UI + bar widget
- `src/cast/`: cast discovery + stream controller
- `services/`: `systemd` service template
- `scripts/`: service installer + mockup generator
- `tests/`: lightweight unit tests

## Requirements

### Raspberry Pi OS packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-tk ffmpeg portaudio19-dev
```

## Setup

```bash
cd /Users/danthony/Documents/GitHub/vinyl
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` as needed, especially `USB_ALSA_DEVICE` and optionally `AUDIO_INPUT_DEVICE_NAME`.

## Run locally

```bash
cd /Users/danthony/Documents/GitHub/vinyl
source .venv/bin/activate
python -m src.main
```

Controls:

- `Refresh`: rescan Cast targets/groups
- tap a speaker/group to start casting (highlighted green while playing)
- tap the active (green) speaker again to stop
- `Esc`: exit app

## Install boot service

```bash
cd /Users/danthony/Documents/GitHub/vinyl
chmod +x scripts/install_service.sh
./scripts/install_service.sh
```

Check logs:

```bash
sudo journalctl -u pi-audio-cast-display.service -f
```

## Generate UI screenshots

```bash
cd /Users/danthony/Documents/GitHub/vinyl
source .venv/bin/activate
python scripts/generate_mockups.py
```

Images are written to `screenshots/`. For live Tkinter captures (requires `python-tk` on your Python build), use `scripts/capture_screenshots.py`.

## Troubleshooting Cast discovery

If speakers show in Google Home but not in this app:

1. Run a standalone scan on the Pi:
   ```bash
   source .venv/bin/activate
   python scripts/discover_cast.py
   ```
2. Ensure the Pi is on the **same Wi-Fi subnet** as your speakers (not guest/isolated Wi-Fi).
3. Increase scan time in `.env`: `CAST_DISCOVERY_TIMEOUT=20`
4. If mDNS is blocked on your router, set speaker IPs in `.env`:
   `CAST_KNOWN_HOSTS=192.168.1.50,192.168.1.51`
5. To list individual speakers instead of only groups: `GOOGLE_GROUPS_ONLY=false`

Cast connection requires the full device record from mDNS (including dynamic ports for speaker groups). Older code that connected by IP alone could not reach groups like those on your network.
