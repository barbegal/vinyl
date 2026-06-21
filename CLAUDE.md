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

### Secondary: mirror to Raspberry Pi Connect

The user also wants the **same UI visible remotely via [Raspberry Pi Connect](https://www.raspberrypi.com/software/connect/)** (rp connect / `rpi-connect`), not only on the physical TFT.

**Implications for changes:**

- The local display is a small SPI framebuffer X session, not the normal Pi desktop or HDMI KMS stack.
- Fast-boot kiosk mode disables the desktop (`multi-user.target`, lightdm masked) — Pi Connect screen sharing may not see the TFT session unless `rpi-connect` is enabled and pointed at the running X display (`DISPLAY=:0` on fb1).
- When proposing display or boot changes, consider **both** outputs: PiTFT must keep working on `/dev/fb1`, and Pi Connect should still be able to mirror or share that session for remote debugging.
- Avoid solutions that only work on HDMI or that require re-enabling the full Raspberry Pi Desktop unless the user asks.
- Prefer keeping `rpi-connect` / `rpi-connect-wayvnc` (or equivalent) available alongside the kiosk path when adding mirroring support.

If mirroring is broken, check: `systemctl status rpi-connect`, whether X is on `:0`, and whether Connect is sharing the correct display (not a blank desktop that was disabled).

## Boot architecture (current)

No systemd X service — that path failed (VT ownership, permission errors).

1. `multi-user.target` — desktop/lightdm masked/disabled, Plymouth off
2. tty1 autologin → `/etc/profile.d/vinyl-kiosk.sh` → `export FRAMEBUFFER=/dev/fb1` + `exec startx`
3. `~/.xinitrc` (from `scripts/kiosk_xinitrc.sh`) → `scripts/start_app.sh` → `python -m src.main`
4. Logs: `~/.vinyl-xsession.log`; on failure `scripts/show_boot_error.py` shows errors on the TFT

Install / refresh: `scripts/install_service.sh`, `scripts/enable_fast_boot.sh`, `scripts/refresh_xinitrc.sh`.

## Key scripts

| Script | Purpose |
|--------|---------|
| `scripts/install_service.sh` | Full kiosk install (name is legacy — no systemd app unit) |
| `scripts/setup_pitft.sh` | Overlay, fbdev X, evdev touch, splash off |
| `scripts/setup_pitft_buttons.sh` | GPIO plate buttons |
| `scripts/enable_fast_boot.sh` | Desktop off, autologin, profile.d, calls setup_pitft |
| `scripts/recover_display.sh` | Recovery → capacitive overlay |
| `scripts/flip_display.sh` | Toggle rotation 90 ↔ 270 |
| `scripts/diagnose_boot.sh` | Boot/display/runtime checks |
| `scripts/detect_touch.sh` | I²C scan for FT6206 at 0x38 |
| `scripts/discover_cast.py` | Standalone Cast mDNS scan |
| `scripts/generate_mockups.py` | Regenerate `screenshots/` PNGs |

Pi recovery one-liner after pull:

```bash
cd /home/vinyl/Desktop/vinyl && git pull && chmod +x scripts/*.sh && ./scripts/refresh_xinitrc.sh
```

## Code layout

- `src/display/fullscreen_ui.py` — Tkinter UI, focus nav, auto-refresh
- `src/display/material_widgets.py` — MD3-style widgets, focus outline
- `src/display/bars_widget.py` — audio bars
- `src/cast/group_discovery.py` — persistent `CastBrowser` + Zeroconf
- `src/cast/stream_controller.py` — HLS ffmpeg + Chromecast
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
