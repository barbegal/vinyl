# Pi Audio Cast Display

Fullscreen Raspberry Pi app that:

- starts on boot with `systemd`
- monitors USB audio input and renders live audio bars on a 320x240 touchscreen
- discovers Google Cast speaker groups and individual speakers
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
sudo apt install -y python3-venv python3-tk ffmpeg portaudio19-dev fonts-roboto xinit xserver-xorg
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

- `Refresh`: rescan Cast targets/groups (on-screen ↻, **plate Left**, or **F5**)
- tap a speaker/group to start casting (highlighted green while playing)
- tap the active (green) speaker again to stop
- **PiTFT plate buttons** (after `setup_pitft_buttons.sh`): **↑/↓** scroll, **Enter** select, **←** refresh
- `Esc`: exit app

## Fast boot — no Raspberry Pi Desktop (kiosk mode)

Instead of a desktop or a systemd-launched X (which can't own a virtual console),
this boots to **console, autologs in on tty1, and runs `startx`** with only the cast app.
The login session owns the VT, so X starts cleanly and fast.

```bash
cd /home/vinyl/Desktop/vinyl
chmod +x scripts/install_service.sh
./scripts/install_service.sh
sudo reboot
```

The installer:

- installs `xinit` / `xserver-xorg` (+ `fbdev`/`evdev` for the PiTFT)
- sets the boot target to `multi-user.target` and disables the desktop
- enables **tty1 autologin** for your user
- writes `~/.xinitrc` (runs the app) and `startx` guards in `~/.profile` / `~/.bash_profile`
- points Xorg at the PiTFT (`/etc/X11/xorg.conf.d/99-pitft.conf` → `/dev/fb1`) and exports `FRAMEBUFFER=/dev/fb1`
- sets the PiTFT overlay rotation + touch calibration via `scripts/setup_pitft.sh`
- removes any old `pi-audio-cast-display.service`

After reboot you should see only the cast UI on the touchscreen — no desktop.

**How long should boot take?** With desktop disabled, expect a blank TFT for the first ~20–30s
(kernel/systemd). The cast UI should appear in about **30–45s on a Pi 4** or **22–35s on a Pi 5**
(power → interactive touchscreen). The speaker list keeps filling for another **6–20s** via
auto-refresh — that does not block the UI. Milestones are logged to `~/.vinyl-boot.log`; run
`./scripts/diagnose_boot.sh` to review them.

### Adafruit 2.8" PiTFT notes (capacitive 28c / resistive 28r)

The PiTFT is an **SPI framebuffer** (`/dev/fb1`), not HDMI/KMS. Rotation lives in the
`config.txt` overlay (`dtoverlay=pitft28-…,rotate=…`), not `xrandr`. The display setup is
the same for both panels; only the touch controller differs:

- **Capacitive (28c)** — FT6206 over **I²C** (installer enables I²C automatically)
- **Resistive (28r)** — STMPE over SPI

The installer defaults to capacitive. To force a panel/rotation, set env vars:

```bash
PITFT_TYPE=28c PITFT_ROTATE=270 ./scripts/install_service.sh
```

If `/dev/fb1` is missing, run the official Adafruit installer once to add the overlay,
console mapping, and touch driver, then re-run ours:

```bash
# In a venv per Bookworm; see Adafruit's guide
sudo -E env PATH=$PATH python3 adafruit-pitft.py --display=28c --rotation=270 --install-type=console
```

If the image is upside down, flip the rotation and reboot:

```bash
sudo ./scripts/setup_pitft.sh 90 28c    # rotation then panel
sudo reboot
```

Touch uses a rotation-aware `CalibrationMatrix` matched via `MatchIsTouchscreen` (works for
either controller). If taps land in the wrong place, confirm the device with `xinput list`,
re-run `setup_pitft.sh` with the matching rotation, or use the Adafruit installer.

**Touch not working / unsure which controller?** Detect the actual hardware:

```bash
sudo ./scripts/detect_touch.sh
```

It scans I²C (capacitive FT6206 sits at `0x38`), checks the loaded overlay and kernel input
devices, and prints the exact fix command. Then apply it, e.g.:

```bash
sudo ./scripts/setup_pitft.sh 270 28c   # capacitive  (or 28r for resistive)
sudo reboot
```

`setup_pitft.sh` switches the overlay touch variant (`pitft28-capacitive` ↔
`pitft28-resistive`) to match — the display is identical either way, so this is safe.

**Run manually** (over SSH, on the Pi display):

```bash
cd /home/vinyl/Desktop/vinyl
DISPLAY=:0 ./scripts/start_app.sh   # if X already running
# or start a fresh X session:
startx
```

**Restore the normal Pi desktop:**

```bash
sudo /home/vinyl/Desktop/vinyl/scripts/restore_desktop.sh
sudo reboot
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
5. To hide individual speakers and show only groups: `GOOGLE_GROUPS_ONLY=true`

Cast connection requires the full device record from mDNS (including dynamic ports for speaker groups). Older code that connected by IP alone could not reach groups like those on your network.
