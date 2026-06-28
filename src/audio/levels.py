from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AudioLevels:
    rms_linear: float
    peak_linear: float
    rms_db: float
    peak_db: float


@dataclass
class LevelMeterState:
    """Rolling peak reference for auto-ranging bar meters."""

    auto_peak: float = 0.06


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
    return max(0.0, min(1.0, rms_v * 0.55 + peak_v * 0.45))


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
    """Apply dB mapping plus optional rolling auto-range (VU-style dynamics)."""
    raw = combine_levels_for_display(
        rms_linear, peak_linear, floor_db=floor_db, ceil_db=ceil_db, gain=gain
    )
    if not auto_range or state is None:
        return raw
    decay = max(0.9, min(0.999, auto_decay))
    if raw > state.auto_peak:
        state.auto_peak = min(1.0, max(raw, state.auto_peak * 0.98 + raw * 0.02))
    else:
        state.auto_peak = max(0.035, state.auto_peak * decay)
    return max(0.0, min(1.0, raw / state.auto_peak))


def calculate_audio_levels(samples: np.ndarray) -> AudioLevels:
    if samples.size == 0:
        return AudioLevels(0.0, 0.0, -120.0, -120.0)

    mono = samples.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)

    abs_values = np.abs(mono)
    rms = float(np.sqrt(np.mean(np.square(abs_values))))
    peak = float(np.max(abs_values))

    return AudioLevels(
        rms_linear=rms,
        peak_linear=peak,
        rms_db=_linear_to_db(rms),
        peak_db=_linear_to_db(peak),
    )
