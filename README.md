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

**Something broken?** One recovery command (fixes permissions, stale `~/.xinitrc`, missing `.env`, re-enables SSH):

```bash
cd /home/vinyl/Desktop/vinyl
git pull
bash scripts/recover.sh
sudo reboot
```

**SSH stopped working?** `recover.sh` fixes SSH-safe login hooks and re-enables `sshd`:

```bash
cd /home/vinyl/Desktop/vinyl
git pull
bash scripts/recover.sh
```

If you cannot log in at all, mount the SD card on another computer and create an empty file `ssh` in the `boot` or `boot/firmware` partition, then boot the Pi and run `recover.sh`.

**Black TFT but app runs?** Also run: `bash scripts/recover.sh --display` (then reboot).

**How long should boot take?** With desktop disabled, expect a blank TFT for the first ~20–30s
(kernel/systemd). Before X starts you may see brief **console text** on the TFT (`Vinyl kiosk /
Starting X on PiTFT…`). Once X is up, a **boot debug panel** lists each startup step until the
main UI appears (~30–45s on Pi 4, ~22–35s on Pi 5). Set `VINYL_BOOT_DEBUG=0` in `.env` to hide
it. The speaker list keeps filling for another **6–20s** via auto-refresh. Milestones are logged
to `~/.vinyl-boot.log`; run `./scripts/diagnose_boot.sh` to review them.

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

## Mirror the TFT remotely (Raspberry Pi Connect / VNC)

The kiosk renders to an Xorg session on `:0` (the SPI framebuffer `/dev/fb1`). Raspberry Pi
Connect's **screen sharing only captures Wayland desktops**, so it can't show this X11/fbdev
session directly. To mirror the **exact TFT**, we attach `x11vnc` to `:0` and keep Raspberry Pi
Connect enabled for remote shell + device management (and to tunnel the VNC port).

```bash
cd /home/vinyl/Desktop/vinyl
sudo ./scripts/setup_rpconnect.sh
rpi-connect signin            # one time; approve at https://connect.raspberrypi.com
sudo reboot
```

This installs `x11vnc` + `rpi-connect`, enables the Connect user service, and sets
`VINYL_MIRROR_VNC=1` in `.env`. After reboot, the `~/.xinitrc` session starts the mirror.

View the exact TFT from another machine (localhost-only by default — tunnel it):

```bash
ssh -L 5900:localhost:5900 vinyl@<pi-host>
# then point any VNC viewer at localhost:5900
```

For direct LAN access instead, set in `.env` and reboot:

```bash
VINYL_VNC_LOCALHOST=0
VINYL_VNC_PASSWORD=yourpass   # recommended when exposed on the LAN
```

Check status (rp connect / vnc section): `./scripts/diagnose_boot.sh`. Mirror log: `~/.vinyl-vnc.log`.

**Paste diagnostics for help:** `bash scripts/diagnose_boot.sh --report` → `~/.vinyl-report.txt`

## Web interface (browser controls)

A lightweight browser UI mirrors the on-screen controls — the same speaker list,
cast/stop, refresh, status line, and live audio bars. The physical TFT stays the
single source of truth, so casting from the web reflects on the screen and vice
versa. It runs automatically alongside the app (stdlib only, no extra deps).

Open it from any device on the same LAN:

```
http://<pi-host>:8080/
```

It also works over the Raspberry Pi Connect tunnel (handy when you're remote).

### Install it to your phone (PWA)

The page is a Progressive Web App, so you can add it to your home screen and it
opens fullscreen like a native remote (its own icon, no browser chrome):

- **iPhone/iPad (Safari):** Share → *Add to Home Screen*
- **Android (Chrome):** ⋮ menu → *Install app* / *Add to Home screen*

A service worker caches the app shell so it launches instantly; speaker state and
controls always hit the Pi live.

Configure in `.env`:

```bash
VINYL_WEB_UI=1          # 0 to disable the web interface
VINYL_WEB_HOST=0.0.0.0  # 127.0.0.1 = localhost only (tunnel via Connect/SSH)
VINYL_WEB_PORT=8080
```

## Auto-connect on startup

By default the Pi tries to start streaming automatically as soon as a preferred
speaker is reachable — no tapping required. It keeps re-scanning the LAN until the
first match in your priority list shows up, then connects and streams the USB
audio to it. The TFT shows `Waiting for Upper / Living Room Speaker…` while it
waits, then `Playing on …` once connected.

Configure the priority list in `.env` (first match wins):

```bash
# Comma-separated names, highest priority first. Empty = disabled (manual only).
VINYL_AUTO_CAST="Upper,Living Room Speaker"
```

Names match case-insensitively (exact match preferred, then substring). Auto-connect
runs once per boot; if you manually pick a different speaker or stop the stream, the
Pi won't override your choice until the next restart.

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

Cast connection requires the full device record from mDNS (including dynamic ports for speaker groups). Older code that connected by IP alone could not reach groups like those on your network.
