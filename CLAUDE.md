# CLAUDE.md — Pi Audio Cast Display (vinyl)

Context for AI assistants working on this repo.

## What this project is

Fullscreen Raspberry Pi kiosk app (`320×240`) that:

- Monitors USB audio input and draws live level bars
- Discovers Google Cast speakers/groups on the LAN
- Streams live USB audio to a selected Cast target via local HLS + ffmpeg

Entry point: `python -m src.main` (`src/main.py`).

## Hardware & display goals

### Primary: Adafruit 2.8" PiTFT

The user runs the app on an **Adafruit 2.8" PiTFT** attached to the Pi:

| Detail | Value |
|--------|--------|
| Panel | **28c** (capacitive, FT6206 touch on I²C `0x38`) — not 28r unless explicitly switched |
| Resolution | 320×240 |
| Framebuffer | SPI → **`/dev/fb1`** (HDMI is typically `/dev/fb0`) |
| Overlay | `dtoverlay=pitft28-capacitive,rotate=…` in `config.txt` |
| Rotation | Set in overlay (`rotate=90` or `270`), **not** via `xrandr` or `display_rotate` |
| Touch | Capacitive: overlay touch flags (`touch-swapxy`, `touch-invx/y`). Use evdev in X (`99-pitft-touch.conf`). **Do not** add libinput `CalibrationMatrix` for 28c — it conflicts with overlay flags. |

Xorg is configured to render to the PiTFT via fbdev (`/etc/X11/xorg.conf.d/99-pitft.conf`). Boot sets `FRAMEBUFFER=/dev/fb1` before `startx`.

Plate buttons (after `setup_pitft_buttons.sh`): GPIO → keys — ↑ scroll, ↓ scroll, ← refresh, Enter select.
On-screen hints align with the physical column (**left** at `rotate=270`, **right** at `rotate=90`).
Set `PLATE_BUTTONS_SIDE=left|right` in `.env` to match your rotation.

### Secondary: mirror to Raspberry Pi Connect

The user also wants the **same UI visible remotely** (alongside [Raspberry Pi Connect](https://www.raspberrypi.com/software/connect/) / `rpi-connect`), not only on the physical TFT.

**How it works here:** the kiosk renders to an **Xorg `:0` session on `/dev/fb1`**. Raspberry Pi
Connect's *screen sharing* only captures **Wayland** desktops, so it cannot show this X11/fbdev
session directly. Instead we **mirror the exact TFT with `x11vnc` attached to `:0`**, and keep
`rpi-connect` enabled for remote shell + device management (and to tunnel the VNC port).

Set up with `scripts/setup_rpconnect.sh` (installs `x11vnc` + `rpi-connect`, enables the Connect
user service, sets `VINYL_MIRROR_VNC=1`). The mirror is launched from `~/.xinitrc` after X starts.

**Implications for changes:**

- The local display is a small SPI framebuffer X session, not the normal Pi desktop or HDMI KMS stack.
- Fast-boot kiosk mode disables the desktop (`multi-user.target`, lightdm masked); the mirror is `x11vnc` on `:0`, **not** Connect's Wayland screen-share.
- When proposing display or boot changes, consider **both** outputs: PiTFT must keep working on `/dev/fb1`, and `x11vnc`/Connect must still be able to mirror that `:0` session.
- Avoid solutions that only work on HDMI or that require re-enabling the full Raspberry Pi Desktop unless the user asks.
- `.env`: `VINYL_MIRROR_VNC`, `VINYL_VNC_PORT`, `VINYL_VNC_LOCALHOST`, `VINYL_VNC_PASSWORD`.

If mirroring is broken, check: `./scripts/diagnose_boot.sh` (rp connect / vnc section), `systemctl --user status rpi-connect`, whether X is on `:0`, and `~/.vinyl-vnc.log`.

## Boot architecture (current)

No systemd X service — that path failed (VT ownership, permission errors).

1. `multi-user.target` — desktop/lightdm masked/disabled, Plymouth off
2. tty1 autologin → `/etc/profile.d/vinyl-kiosk.sh` → `export FRAMEBUFFER=/dev/fb1` + `exec startx`
3. `~/.xinitrc` (from `scripts/kiosk_xinitrc.sh`) → `scripts/start_app.sh` → `python -m src.main`
4. Logs: `~/.vinyl-xsession.log`; on failure `scripts/show_boot_error.py` shows errors on the TFT

Install / refresh: `scripts/install_service.sh`, `scripts/enable_fast_boot.sh`, `scripts/refresh_xinitrc.sh`.

## Boot timing (design targets)

Kiosk mode skips the Raspberry Pi Desktop, Plymouth splash, and display manager. Expect a **blank TFT during early boot** (kernel + systemd on console) — that is normal; the UI appears when X + Python start.

### Estimated timeline (power → milestone)

Times use **kernel uptime** (`/proc/uptime`) — seconds since the kernel started, not wall clock.

| Milestone | Pi 4 (SD, Wi‑Fi) | Pi 5 (SD, Wi‑Fi) | Notes |
|-----------|------------------|------------------|-------|
| `multi-user.target` (SSH up) | ~20–35s | ~15–25s | No desktop; faster than graphical boot |
| `xsession start` / Xorg on fb1 | +2–5s | +2–4s | After tty1 autologin + `startx` |
| **`ui visible on tft`** | **~30–45s** | **~22–35s** | Split layout + “Searching for speakers…” |
| `audio input ready` | +0–2s after UI | +0–2s | USB sound card enumerate can lag |
| `first cast scan` | +1–8s after UI | +1–6s | mDNS; may show 0–1 targets initially |
| Full speaker list | +6–20s after UI | +6–15s | Auto-refresh every `CAST_REFRESH_INTERVAL` (default 6s) |

**Rough totals from power:**

- **Interactive UI on TFT** — target **≤45s** (Pi 4), **≤35s** (Pi 5). This is the primary SLO.
- **Cast list “useful”** (most speakers listed) — target **≤60s** (Pi 4), **≤45s** (Pi 5). Non-blocking; UI is already tappable.
- **Compared to full desktop** — previously ~90–120s+ to a usable desktop; kiosk path is materially faster.

Cast discovery and Wi‑Fi association run **after** the first paint and must not block the TFT.
The main shell (speaker list + bars) appears immediately; the top subtitle shows phased status:
`Starting…` → `Loading audio…` → `Wi‑Fi connecting…` → `Loading Cast…` → `Searching for speakers…`.
Heavy imports (numpy, sounddevice, pychromecast) load in background threads.

### Measuring on the Pi

Boot progress appears on the TFT by default (`VINYL_BOOT_DEBUG=1` in `.env`). Errors show in **red**
(`ERR:` lines): stderr/tracebacks, missing `/dev/fb1`, Xorg `(EE)` lines, audio/Cast failures, and
log tails from `~/.vinyl-xsession.log`. Set `VINYL_BOOT_DEBUG=0` to hide once boot is stable.

After each boot, milestones are appended to `~/.vinyl-boot.log`:

```bash
cat ~/.vinyl-boot.log
./scripts/diagnose_boot.sh   # includes timing summary
```

Example log:

```text
  28.40s  xsession start
  28.42s  startx invoked xinitrc
  29.10s  start_app.sh
  32.55s  tk window built
  33.02s  ui visible on tft
  33.80s  audio input ready
  38.20s  first cast scan (2 target(s))
```

If `ui visible on tft` exceeds the SLO, check: slow SD card, extra `systemd` units, Wi‑Fi driver delay, Xorg errors, or Python import time (venv on SD).

## Key scripts (Pi)

| Script | When to use |
|--------|-------------|
| **`recover.sh`** | Broken boot / black TFT / after `git pull` (`--display` for panel fix) |
| **`diagnose_boot.sh`** | Health check (`--report` → paste `~/.vinyl-report.txt`) |
| **`install_service.sh`** | First-time kiosk install |
| **`restore_desktop.sh`** | Undo kiosk → normal Pi desktop |
| **`setup_pitft.sh`** | Panel overlay + Xorg (`270 28r` or `28c`) |
| **`detect_touch.sh`** | Capacitive vs resistive panel |
| **`setup_rpconnect.sh`** | Optional remote TFT mirror (x11vnc) |
| **`discover_cast.py`** | Test Cast discovery only |

Internal / dev: `kiosk_xinitrc.sh` (template), `boot_milestone.sh`, `generate_mockups.py`, `flip_display.sh` (calls `setup_pitft.sh`).

Pi recovery after pull:

```bash
cd /home/vinyl/Desktop/vinyl && git pull && bash scripts/recover.sh && sudo reboot
```

## Code layout

- `src/display/fullscreen_ui.py` — Tkinter UI, focus nav, auto-refresh
- `src/display/material_widgets.py` — MD3-style widgets, focus outline
- `src/display/bars_widget.py` — audio bars
- `src/cast/group_discovery.py` — persistent `CastBrowser` + Zeroconf
- `src/cast/stream_controller.py` — HLS ffmpeg + Chromecast
- `src/web/server.py` — optional browser UI mirroring the TFT controls (stdlib http.server; Tk app stays source of truth via `after()`-scheduled actions)
- `src/audio/` — sounddevice input + levels
- `src/config/settings.py` — env-based settings (see `.env.example`)
- `tests/` — unittest (`python -m unittest discover -s tests`)

## Cast / network notes

- pychromecast 14 needs full `CastInfo` from mDNS — not raw IP/port
- Speaker **groups** use dynamic ports; connecting by IP alone fails
- Pi must be on same LAN/subnet as speakers (not guest Wi-Fi)
- `.env`: `CAST_DISCOVERY_TIMEOUT`, `CAST_REFRESH_INTERVAL`, `CAST_KNOWN_HOSTS`

## Common pitfalls (recent history)

1. **Black screen on boot** — UI blocked before `mainloop()` (fixed: defer discovery/audio via `after()`); or `start_app.sh` not executable; or stale `~/.xinitrc` with literal `@APP_DIR@`
2. **Wrong overlay `28r` on capacitive panel** — blank/broken display; use `28c`
3. **Upside-down image** — flip with `setup_pitft.sh 90 28c` or `270 28c`
4. **Touch wrong/missing** — run `detect_touch.sh`; confirm overlay touch flags match rotation; disable conflicting libinput calibration
5. **Profile.d bug** — `[ -n DISPLAY ]` without `$` caused early exit (fixed in installer)
6. **Only one speaker on first load** — normal until auto-refresh runs; `CastBrowser` warms up over several seconds

## Development conventions

- Minimize diff scope; match existing style
- UI target is 320×240 — test layout constraints
- Regenerate screenshots with `python scripts/generate_mockups.py` when UI changes materially
- Do not commit unless asked
- Pi path: `/home/vinyl/Desktop/vinyl`; dev Mac path may differ

## Tests

```bash
python -m unittest discover -s tests -q
```
