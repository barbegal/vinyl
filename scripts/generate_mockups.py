"""Generate UI screenshots matching the redesigned layout (320x240)."""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 320, 240
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

GRAD_TOP = (10, 12, 18)
GRAD_BOTTOM = (20, 24, 34)
OVERLAY_BG = "#12161f"
SUBTITLE_FG = "#8b95a8"
REFRESH_FG = "#6b7a90"
TARGET_BG = "#181d28"
TARGET_FG = "#9aa6b8"
TARGET_ACTIVE_BG = "#2d6b4a"
TARGET_ACTIVE_FG = "#f2fff6"
ERROR_FG = "#c97a7a"
OK_FG = "#7ec99a"
EMPTY_FG = "#6b7a90"


def pick_font(size: int = 14, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def bar_color(value: float) -> str:
    value = max(0.0, min(1.0, value))
    if value < 0.05:
        return "#141a24"
    if value < 0.35:
        return "#1a2433"
    if value < 0.6:
        return "#243044"
    if value < 0.8:
        return "#2e3d55"
    return "#3a5068"


class ScreenRenderer:
    def __init__(self):
        self.image = Image.new("RGB", (W, H), "#0a0c12")
        self.draw = ImageDraw.Draw(self.image)

    def background_bars(self, levels: list[float]) -> None:
        top, bottom = GRAD_TOP, GRAD_BOTTOM
        for y in range(H):
            t = y / max(H - 1, 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            self.draw.line((0, y, W, y), fill=(r, g, b))

        bars = 24
        gap = 3
        margin_x = 8
        margin_bottom = 12
        draw_width = W - margin_x * 2
        total_gap = gap * (bars + 1)
        bar_width = max(2, (draw_width - total_gap) // bars)
        max_bar_height = H - margin_bottom - 8

        for index, value in enumerate(levels[:bars]):
            value = max(0.0, min(1.0, value))
            bar_height = max(2 if value > 0 else 0, int(max_bar_height * value))
            x0 = margin_x + gap + index * (bar_width + gap)
            y0 = H - margin_bottom - bar_height
            x1 = x0 + bar_width
            y1 = H - margin_bottom
            self.draw.rectangle((x0, y0, x1, y1), fill=bar_color(value))

    def overlay(
        self,
        subtitle: str,
        subtitle_color: str = SUBTITLE_FG,
        targets: list[tuple[str, bool]] | None = None,
        active_index: int | None = None,
        empty_message: str | None = None,
    ) -> None:
        row_count = len(targets) if targets else 0
        overlay_height = 28 + max(row_count, 1) * 28 + 8
        overlay_height = min(overlay_height, 130)
        y0 = H - overlay_height
        self.draw.rectangle((0, y0, W, H), fill=OVERLAY_BG)

        self.draw.text((10, y0 + 6), subtitle, fill=subtitle_color, font=pick_font(9))
        refresh_font = pick_font(9)
        refresh_text = "Refresh"
        bbox = self.draw.textbbox((0, 0), refresh_text, font=refresh_font)
        rw = bbox[2] - bbox[0]
        self.draw.text((W - rw - 10, y0 + 6), refresh_text, fill=REFRESH_FG, font=refresh_font)

        target_y = y0 + 22
        row_h = 28
        if targets:
            for idx, (name, is_group) in enumerate(targets[:4]):
                label = f"{name}  ·  group" if is_group else name
                row_y = target_y + idx * row_h
                if active_index == idx:
                    bg, fg = TARGET_ACTIVE_BG, TARGET_ACTIVE_FG
                else:
                    bg, fg = TARGET_BG, TARGET_FG
                self.draw.rectangle((10, row_y, W - 10, row_y + 24), fill=bg)
                self.draw.text((18, row_y + 5), label, fill=fg, font=pick_font(11))
        elif empty_message:
            self.draw.text((10, target_y + 2), empty_message, fill=EMPTY_FG, font=pick_font(10))

    def save(self, filename: str) -> Path:
        path = OUT / filename
        self.image.save(path)
        return path


def animated_levels(seed: int = 0) -> list[float]:
    random.seed(seed)
    levels = []
    for i in range(24):
        base = 0.12 + 0.58 * abs(math.sin(i / 3.5 + seed))
        levels.append(base + random.uniform(-0.04, 0.1))
    return levels


def flat_levels() -> list[float]:
    return [0.0] * 24


MOCK_TARGETS = [
    ("Bottom", True),
    ("Upper", True),
]


def main() -> None:
    saved: list[Path] = []

    r = ScreenRenderer()
    r.background_bars(flat_levels())
    r.overlay("Starting...")
    saved.append(r.save("01_boot.png"))

    r = ScreenRenderer()
    r.background_bars(flat_levels())
    r.overlay("No audio input", subtitle_color=ERROR_FG, empty_message="No speakers found")
    saved.append(r.save("02_no_audio_input.png"))

    r = ScreenRenderer()
    r.background_bars(animated_levels(1))
    r.overlay("Tap a speaker to play", targets=MOCK_TARGETS)
    saved.append(r.save("03_audio_bars_active.png"))

    r = ScreenRenderer()
    r.background_bars(animated_levels(2))
    r.overlay("Tap a speaker to play", targets=MOCK_TARGETS)
    saved.append(r.save("04_cast_targets.png"))

    r = ScreenRenderer()
    r.background_bars(animated_levels(3))
    r.overlay("Playing on Bottom", subtitle_color=OK_FG, targets=MOCK_TARGETS, active_index=0)
    saved.append(r.save("05_streaming_active.png"))

    r = ScreenRenderer()
    r.background_bars(flat_levels())
    r.overlay("Tap Refresh to find speakers", empty_message="No speakers found")
    saved.append(r.save("06_no_cast_targets.png"))

    r = ScreenRenderer()
    r.background_bars(flat_levels())
    r.overlay("Network unreachable", subtitle_color=ERROR_FG, empty_message="No speakers found")
    saved.append(r.save("07_discovery_error.png"))

    r = ScreenRenderer()
    r.background_bars(animated_levels(4))
    r.overlay("Could not connect to Chromecast", subtitle_color=ERROR_FG, targets=MOCK_TARGETS)
    saved.append(r.save("08_stream_failed.png"))

    print(f"Generated {len(saved)} screenshots in: {OUT}")
    for path in saved:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
