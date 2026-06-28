from __future__ import annotations

import tkinter as tk

from src.audio.levels import LevelMeterState, meter_display_value


class AudioBarsWidget(tk.Canvas):
    """Full-screen ambient audio visualizer with a dark gradient background."""

    def __init__(
        self,
        master,
        width: int,
        height: int,
        bars: int = 24,
        level_gain: float = 1.0,
        level_floor_db: float = -58.0,
        level_ceil_db: float = 6.0,
        level_auto_range: bool = True,
        level_auto_decay: float = 0.993,
        meter_state: LevelMeterState | None = None,
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
        self._level_auto_range = level_auto_range
        self._level_auto_decay = level_auto_decay
        self._meter_state = meter_state if meter_state is not None else LevelMeterState()
        self._history = [0.0 for _ in range(bars)]
        self._gradient_top = (10, 12, 18)
        self._gradient_bottom = (20, 24, 34)

    @property
    def meter_state(self) -> LevelMeterState:
        return self._meter_state

    def display_level(self, rms_linear: float, peak_linear: float) -> float:
        return meter_display_value(
            rms_linear,
            peak_linear,
            floor_db=self._level_floor_db,
            ceil_db=self._level_ceil_db,
            gain=self._level_gain,
            auto_range=self._level_auto_range,
            auto_decay=self._level_auto_decay,
            state=self._meter_state,
        )

    def update_levels(self, rms_linear: float, peak_linear: float) -> None:
        value = self.display_level(rms_linear, peak_linear)
        self._history.pop(0)
        self._history.append(value)
        self._redraw()
