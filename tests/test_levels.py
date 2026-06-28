"""Tests for audio level calculations and display mapping."""

from __future__ import annotations

import unittest

import numpy as np

from src.audio.levels import (
    calculate_audio_levels,
    combine_levels_for_display,
    map_linear_to_display,
)


class TestAudioLevels(unittest.TestCase):
    def test_silence_levels(self):
        samples = np.zeros((1024,), dtype=np.float32)
        levels = calculate_audio_levels(samples)
        self.assertLess(levels.rms_db, -100.0)
        self.assertLess(levels.peak_db, -100.0)

    def test_nonzero_levels(self):
        t = np.linspace(0, 1, 1024, endpoint=False)
        samples = (0.5 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
        levels = calculate_audio_levels(samples)
        self.assertGreater(levels.rms_linear, 0.0)
        self.assertGreater(levels.peak_linear, 0.0)

    def test_display_mapping_hot_line_in_not_always_max(self):
        # ~-12 dB RMS — should sit around mid/high bars, not pegged at 1.0
        rms = 10 ** (-12 / 20)
        peak = 10 ** (-6 / 20)
        value = combine_levels_for_display(rms, peak, floor_db=-50, ceil_db=0, gain=1.0)
        self.assertGreater(value, 0.4)
        self.assertLess(value, 0.95)

    def test_display_mapping_silence_is_zero(self):
        self.assertEqual(map_linear_to_display(0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
