from __future__ import annotations

import tkinter as tk

from src.audio.levels import combine_levels_for_display


class AudioBarsWidget(tk.Canvas):
    """Full-screen ambient audio visualizer with a dark gradient background."""

    def __init__(
        self,
        master,
        width: int,
        height: int,
        bars: int = 24,
        level_gain: float = 1.0,
        level_floor_db: float = -50.0,
        level_ceil_db: float = 0.0,
        **kwargs,
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            bg="#0a0c12",
            highlightthickness=0,
            **kwargs,
        )
        self._bars = bars
        self._level_gain = level_gain
        self._level_floor_db = level_floor_db
        self._level_ceil_db = level_ceil_db
        self._history = [0.0 for _ in range(bars)]
        self._gradient_top = (10, 12, 18)
        self._gradient_bottom = (20, 24, 34)

    def update_levels(self, rms_linear: float, peak_linear: float) -> None:
        value = combine_levels_for_display(
            rms_linear,
            peak_linear,
            floor_db=self._level_floor_db,
            ceil_db=self._level_ceil_db,
            gain=self._level_gain,
        )
        self._history.pop(0)
        self._history.append(value)
        self._redraw()

    def _bar_color(self, value: float) -> str:
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

    def _draw_gradient(self, width: int, height: int) -> None:
        top = self._gradient_top
        bottom = self._gradient_bottom
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.create_line(0, y, width, y, fill=color)

    def _redraw(self) -> None:
        self.delete("all")
        width = max(1, int(self.winfo_width() or self["width"]))
        height = max(1, int(self.winfo_height() or self["height"]))
        self._draw_gradient(width, height)

        gap = 3
        margin_x = 8
        margin_bottom = 12
        draw_width = width - margin_x * 2
        total_gap = gap * (self._bars + 1)
        bar_width = max(2, (draw_width - total_gap) // self._bars)
        max_bar_height = height - margin_bottom - 8

        for index, value in enumerate(self._history):
            bar_height = int(max_bar_height * value)
            if bar_height < 2 and value > 0:
                bar_height = 2
            x0 = margin_x + gap + index * (bar_width + gap)
            y0 = height - margin_bottom - bar_height
            x1 = x0 + bar_width
            y1 = height - margin_bottom
            self.create_rectangle(x0, y0, x1, y1, fill=self._bar_color(value), outline="")
