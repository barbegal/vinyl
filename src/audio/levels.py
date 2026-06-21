from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AudioLevels:
    rms_linear: float
    peak_linear: float
    rms_db: float
    peak_db: float


def _linear_to_db(value: float) -> float:
    safe = max(float(value), 1e-12)
    return 20.0 * float(np.log10(safe))


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
