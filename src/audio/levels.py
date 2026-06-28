from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class AudioLevels:
    rms_linear: float
    peak_linear: float
    rms_db: float
    peak_db: float


@dataclass
class LevelMeterState:
    """Rolling window for auto-ranging bar meters (min–max over recent samples)."""

    auto_peak: float = 0.06
    window: deque = field(default_factory=lambda: deque(maxlen=90))


def _linear_to_db(value: float) -> float:
    safe = max(float(value), 1e-12)
    return 20.0 * float(np.log10(safe))


def map_linear_to_display(
    linear: float,
    floor_db: float = -58.0,
    ceil_db: float = 6.0,
    gain: float = 1.0,
) -> float:
    """Map linear amplitude (~0–1) to a 0–1 bar height using a dB window."""
    if linear <= 1e-8:
        return 0.0
    db = _linear_to_db(linear)
    span = ceil_db - floor_db
    if span <= 1e-6:
        return 0.0
    normalized = (db - floor_db) / span
    return max(0.0, min(1.0, normalized * gain))


def combine_levels_for_display(
    rms_linear: float,
    peak_linear: float,
    floor_db: float = -58.0,
    ceil_db: float = 6.0,
    gain: float = 1.0,
) -> float:
    """Blend RMS (body) and peak (transients) for a responsive meter."""
    rms_v = map_linear_to_display(rms_linear, floor_db, ceil_db, gain)
    peak_v = map_linear_to_display(peak_linear, floor_db, ceil_db, gain)
    return max(0.0, min(1.0, rms_v * 0.68 + peak_v * 0.32))


def trim_linear_levels(
    rms_linear: float,
    peak_linear: float,
    trim_db: float,
) -> tuple[float, float]:
    """Apply the same dB trim used for cast gain so meters match audible level."""
    if trim_db == 0.0:
        return rms_linear, peak_linear
    gain = 10 ** (trim_db / 20.0)
    return (
        min(1.0, rms_linear * gain),
        min(1.0, peak_linear * gain),
    )


def meter_display_value(
    rms_linear: float,
    peak_linear: float,
    *,
    floor_db: float,
    ceil_db: float,
    gain: float,
    auto_range: bool,
    auto_decay: float,
    state: LevelMeterState | None,
) -> float:
    """Apply dB mapping plus optional rolling min–max auto-range (VU-style dynamics)."""
    raw = combine_levels_for_display(
        rms_linear, peak_linear, floor_db=floor_db, ceil_db=ceil_db, gain=gain
    )
    if not auto_range or state is None:
        return raw

    state.window.append(raw)
    count = len(state.window)
    if count < 12:
        if raw > state.auto_peak:
            state.auto_peak = raw
        span = max(state.auto_peak, 0.08)
        return max(0.0, min(1.0, raw / span))

    lo = min(state.window)
    hi = max(state.window)
    span = max(hi - lo, 0.04)
    return max(0.0, min(1.0, (raw - lo) / span))


def calculate_audio_levels(samples: np.ndarray) -> AudioLevels:
    if samples.size == 0:
        return AudioLevels(0.0, 0.0, -120.0, -120.0)

    mono = samples.astype(np.float32)
    if mono.ndim > 1:
        peak = float(np.max(np.abs(mono)))
        mono = mono.mean(axis=1)
    else:
        peak = None

    abs_values = np.abs(mono)
    rms = float(np.sqrt(np.mean(np.square(abs_values))))
    if peak is None:
        peak = float(np.max(abs_values))

    return AudioLevels(
        rms_linear=rms,
        peak_linear=peak,
        rms_db=_linear_to_db(rms),
        peak_db=_linear_to_db(peak),
    )
