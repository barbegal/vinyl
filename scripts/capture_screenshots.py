#!/usr/bin/env python3
"""Capture real Tkinter UI screenshots for each app screen state."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from src.audio.input_listener import AudioSnapshot
from src.audio.levels import AudioLevels
from src.cast.group_discovery import CastTarget
from src.cast.stream_controller import StreamStatus
from src.config.settings import AppSettings
from src.display.fullscreen_ui import FullscreenApp

OUT = ROOT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

MOCK_TARGETS = [
    CastTarget("1", "Whole House", "10.0.0.2", 8009, True, "Google Cast Group"),
    CastTarget("2", "Living Room", "10.0.0.1", 8009, False, "Nest Audio"),
    CastTarget("3", "Kitchen", "10.0.0.3", 8009, False, "Nest Mini"),
]


def _snapshot(rms_db: float, peak_db: float) -> AudioSnapshot:
    rms_linear = 10 ** (rms_db / 20.0) if rms_db > -120 else 0.0
    peak_linear = 10 ** (peak_db / 20.0) if peak_db > -120 else 0.0
    levels = AudioLevels(rms_linear, peak_linear, rms_db, peak_db)
    return AudioSnapshot(time.time(), levels, peak_linear > 0.001)


def capture(root, filename: str) -> Path:
    root.update_idletasks()
    root.update()
    time.sleep(0.2)
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = max(root.winfo_width(), 1)
    h = max(root.winfo_height(), 1)
    path = OUT / filename
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
    return path


def populate_targets(app: FullscreenApp, targets: list[CastTarget], status: str) -> None:
    app.targets = targets
    app.listbox.delete(0, "end")
    for target in targets:
        suffix = " [Group]" if target.is_group else ""
        app.listbox.insert("end", f"{target.name}{suffix}")
    app.status_var.set(status)
    if targets:
        app.listbox.selection_set(0)


def set_audio_levels(app: FullscreenApp, rms_db: float, peak_db: float) -> None:
    snap = _snapshot(rms_db, peak_db)
    app.bars.update_levels(snap.levels.rms_linear, snap.levels.peak_linear)
    app.input_var.set(
        f"Input: RMS {snap.levels.rms_db:5.1f} dB | Peak {snap.levels.peak_db:5.1f} dB"
    )


def animate_bars(app: FullscreenApp, frames: int = 30) -> None:
    for i in range(frames):
        t = i / frames
        rms_db = -18.0 + 10.0 * math.sin(t * math.pi * 5)
        peak_db = rms_db + 8.0
        set_audio_levels(app, rms_db, peak_db)
        app.root.update_idletasks()


def main() -> None:
    settings = AppSettings(fullscreen=False, screen_width=320, screen_height=240)
    app = FullscreenApp(settings=settings)
    app.root.geometry(f"{settings.screen_width}x{settings.screen_height}")
    app.root.resizable(False, False)

    saved: list[Path] = []

    # 01 — boot / starting
    app.status_var.set("Booting...")
    app.input_var.set("Input: checking")
    app.cast_var.set("Cast: idle")
    set_audio_levels(app, -120.0, -120.0)
    populate_targets(app, [], "Starting services...")
    saved.append(capture(app.root, "01_boot.png"))

    # 02 — no USB / audio input unavailable
    app.status_var.set("Audio input unavailable")
    app.input_var.set("Input: error - No input device found")
    set_audio_levels(app, -120.0, -120.0)
    populate_targets(app, [], "Audio input unavailable")
    saved.append(capture(app.root, "02_no_audio_input.png"))

    # 03 — audio bars active (silence then animated levels)
    app.status_var.set("Audio input active")
    animate_bars(app)
    populate_targets(app, MOCK_TARGETS, f"Found {len(MOCK_TARGETS)} target(s)")
    app.cast_var.set("Cast: idle")
    saved.append(capture(app.root, "03_audio_bars_active.png"))

    # 04 — cast targets list with group selected
    set_audio_levels(app, -22.0, -12.0)
    populate_targets(app, MOCK_TARGETS, f"Found {len(MOCK_TARGETS)} target(s)")
    app.listbox.selection_clear(0, "end")
    app.listbox.selection_set(0)
    app.cast_var.set("Cast: idle")
    saved.append(capture(app.root, "04_cast_targets.png"))

    # 05 — streaming active
    app.controller._status = StreamStatus(
        active=True,
        target_name="Whole House",
        message="Streaming",
        stream_url="http://192.168.1.42:9000/live.m3u8",
    )
    app.status_var.set("Streaming")
    app.cast_var.set("Cast: streaming to Whole House")
    set_audio_levels(app, -16.0, -6.0)
    animate_bars(app, frames=20)
    saved.append(capture(app.root, "05_streaming_active.png"))

    # 06 — no cast targets
    app.controller._status = StreamStatus(False, "", "Idle", "")
    populate_targets(app, [], "No cast targets found")
    app.cast_var.set("Cast: idle")
    set_audio_levels(app, -120.0, -120.0)
    saved.append(capture(app.root, "06_no_cast_targets.png"))

    # 07 — discovery error
    app.discovery.last_error = "Network unreachable"
    populate_targets(app, [], "Discovery error: Network unreachable")
    app.input_var.set("Input: error - No input device found")
    saved.append(capture(app.root, "07_discovery_error.png"))

    # 08 — stream failed
    app.discovery.last_error = None
    populate_targets(app, MOCK_TARGETS, "Stream failed")
    app.cast_var.set("Cast: Could not connect to Chromecast")
    set_audio_levels(app, -24.0, -14.0)
    saved.append(capture(app.root, "08_stream_failed.png"))

    app.shutdown()

    print(f"Saved {len(saved)} screenshots to: {OUT}")
    for path in saved:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
