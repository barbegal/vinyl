"""Generate UI screenshots matching the split Material layout (320x240)."""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 320, 240
LIST_W = W // 2
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

GRAD_TOP = (10, 12, 18)
GRAD_BOTTOM = (20, 24, 34)
PANEL_BG = "#12161f"
SUBTITLE_FG = "#9aa6b8"
ICON_FG = "#8b95a8"
SURFACE = "#1a2030"
TARGET_FG = "#eef2f8"
TARGET_ACTIVE_BG = "#2d6b4a"
TARGET_ACTIVE_FG = "#f2fff6"
ERROR_FG = "#c97a7a"
OK_FG = "#6ecf94"
EMPTY_FG = "#6b7a90"
BTN_RADIUS = 10
ICON_BTN_RADIUS = 8


def pick_font(size: int = 14, bold: bool = False):
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Roboto-Bold.ttf",
            "/Library/Fonts/Roboto-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Roboto-Regular.ttf",
            "/Library/Fonts/Roboto-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centered_text(draw, box: tuple[int, int, int, int], text: str, fill: str, font) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x0 + (x1 - x0 - tw) // 2
    ty = y0 + (y1 - y0 - th) // 2 - 1
    draw.text((tx, ty), text, fill=fill, font=font)


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


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


class ScreenRenderer:
    def __init__(self):
        self.image = Image.new("RGB", (W, H), "#0a0c12")
        self.draw = ImageDraw.Draw(self.image)

    def _draw_icon_btn(self, x: int, y: int, size: int, label: str, fill: str = SURFACE) -> None:
        _rounded(self.draw, (x, y, x + size, y + size), ICON_BTN_RADIUS, fill)
        _centered_text(self.draw, (x, y, x + size, y + size), label, ICON_FG, pick_font(11, bold=True))

    def _draw_bars_right(self, levels: list[float]) -> None:
        x0, bars_w = LIST_W, W - LIST_W
        self._draw_icon_btn(W - 30, 4, 26, "✕", "#141820")

        top, bottom = GRAD_TOP, GRAD_BOTTOM
        for y in range(H):
            t = y / max(H - 1, 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            self.draw.line((x0, y, W, y), fill=(r, g, b))

        bars = 16
        gap = 2
        margin_x = 6
        margin_bottom = 12
        draw_width = bars_w - margin_x * 2
        total_gap = gap * (bars + 1)
        bar_width = max(2, (draw_width - total_gap) // bars)
        max_bar_height = H - margin_bottom - 8

        for index, value in enumerate(levels[:bars]):
            value = max(0.0, min(1.0, value))
            bar_height = max(2 if value > 0 else 0, int(max_bar_height * value))
            bx0 = x0 + margin_x + gap + index * (bar_width + gap)
            by0 = H - margin_bottom - bar_height
            bx1 = bx0 + bar_width
            by1 = H - margin_bottom
            self.draw.rectangle((bx0, by0, bx1, by1), fill=bar_color(value))

    def _draw_list_panel(
        self,
        subtitle: str,
        subtitle_color: str,
        targets: list[tuple[str, bool]] | None = None,
        active_index: int | None = None,
        empty_message: str | None = None,
    ) -> None:
        self.draw.rectangle((0, 0, LIST_W, H), fill=PANEL_BG)
        subtitle_font = pick_font(9, bold=True)
        bbox = self.draw.textbbox((0, 0), subtitle, font=subtitle_font)
        tw = bbox[2] - bbox[0]
        self.draw.text(((LIST_W - tw) // 2, 8), subtitle, fill=subtitle_color, font=subtitle_font)
        self._draw_icon_btn(LIST_W - 32, 4, 26, "↻")

        header_h = 24
        list_top = header_h
        list_bottom = H - 4
        list_h = list_bottom - list_top
        gap = 3

        if targets:
            row_h = max(20, (list_h - gap * len(targets)) // len(targets))
            for idx, (name, is_group) in enumerate(targets):
                label = f"{name}  ·  group" if is_group else name
                row_y = list_top + idx * (row_h + gap)
                if active_index == idx:
                    bg, fg = TARGET_ACTIVE_BG, TARGET_ACTIVE_FG
                else:
                    bg, fg = SURFACE, TARGET_FG
                box = (4, row_y, LIST_W - 4, row_y + row_h)
                _rounded(self.draw, box, BTN_RADIUS, bg)
                _centered_text(self.draw, box, label, fg, pick_font(10, bold=True))
        elif empty_message:
            box = (4, list_top, LIST_W - 4, list_top + 24)
            _centered_text(self.draw, box, empty_message, EMPTY_FG, pick_font(9, bold=True))

    def split_layout(
        self,
        subtitle: str,
        levels: list[float],
        subtitle_color: str = SUBTITLE_FG,
        targets: list[tuple[str, bool]] | None = None,
        active_index: int | None = None,
        empty_message: str | None = None,
    ) -> None:
        self._draw_list_panel(subtitle, subtitle_color, targets, active_index, empty_message)
        self._draw_bars_right(levels)

    def save(self, filename: str) -> Path:
        path = OUT / filename
        self.image.save(path)
        return path


def animated_levels(seed: int = 0) -> list[float]:
    random.seed(seed)
    levels = []
    for i in range(16):
        base = 0.12 + 0.58 * abs(math.sin(i / 3.5 + seed))
        levels.append(base + random.uniform(-0.04, 0.1))
    return levels


def flat_levels() -> list[float]:
    return [0.0] * 16


MOCK_TARGETS = [
    ("Bottom", True),
    ("Upper", True),
    ("Living Room pair", False),
    ("Bathroom speaker", False),
    ("Guest Bedroom speaker", False),
    ("Guest Bedroom TV", False),
    ("TV Ultra CC", False),
]


def main() -> None:
    saved: list[Path] = []

    r = ScreenRenderer()
    r.split_layout("Starting...", flat_levels())
    saved.append(r.save("01_boot.png"))

    r = ScreenRenderer()
    r.split_layout("No audio input", flat_levels(), ERROR_FG, empty_message="No speakers")
    saved.append(r.save("02_no_audio_input.png"))

    r = ScreenRenderer()
    r.split_layout("Tap to play", animated_levels(1), targets=MOCK_TARGETS)
    saved.append(r.save("03_audio_bars_active.png"))

    r = ScreenRenderer()
    r.split_layout("Tap to play", animated_levels(2), targets=MOCK_TARGETS)
    saved.append(r.save("04_cast_targets.png"))

    r = ScreenRenderer()
    r.split_layout(
        "Playing on Bottom",
        animated_levels(3),
        OK_FG,
        targets=MOCK_TARGETS,
        active_index=0,
    )
    saved.append(r.save("05_streaming_active.png"))

    r = ScreenRenderer()
    r.split_layout("Tap ↻ to scan", flat_levels(), empty_message="No speakers")
    saved.append(r.save("06_no_cast_targets.png"))

    r = ScreenRenderer()
    r.split_layout("Network unreachable", flat_levels(), ERROR_FG, empty_message="No speakers")
    saved.append(r.save("07_discovery_error.png"))

    r = ScreenRenderer()
    r.split_layout(
        "Could not connect",
        animated_levels(4),
        ERROR_FG,
        targets=MOCK_TARGETS,
    )
    saved.append(r.save("08_stream_failed.png"))

    print(f"Generated {len(saved)} screenshots in: {OUT}")
    for path in saved:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
