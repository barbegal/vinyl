"""Tests for audio level calculations and display mapping."""

from __future__ import annotations

import unittest

import numpy as np

from src.audio.levels import (
    LevelMeterState,
    calculate_audio_levels,
    combine_levels_for_display,
    map_linear_to_display,
    meter_display_value,
    trim_linear_levels,
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
        rms = 10 ** (-12 / 20)
        peak = 10 ** (-6 / 20)
        value = combine_levels_for_display(rms, peak, floor_db=-58, ceil_db=6, gain=1.0)
        self.assertGreater(value, 0.35)
        self.assertLess(value, 0.92)

    def test_auto_range_tracks_dynamics(self):
        state = LevelMeterState(auto_peak=0.08)
        loud = meter_display_value(
            10 ** (-8 / 20),
            10 ** (-5 / 20),
            floor_db=-58,
            ceil_db=6,
            gain=1.0,
            auto_range=True,
            auto_decay=0.993,
            state=state,
        )
        quiet = meter_display_value(
            10 ** (-22 / 20),
            10 ** (-18 / 20),
            floor_db=-58,
            ceil_db=6,
            gain=1.0,
            auto_range=True,
            auto_decay=0.993,
            state=state,
        )
        self.assertGreater(loud, quiet)
        self.assertLessEqual(loud, 1.0)

    def test_window_auto_range_uses_recent_span(self):
        state = LevelMeterState()
        values = []
        for rms_db, peak_db in [(-18, -14), (-18, -14), (-12, -8), (-12, -8), (-20, -16)] * 4:
            values.append(
                meter_display_value(
                    10 ** (rms_db / 20),
                    10 ** (peak_db / 20),
                    floor_db=-58,
                    ceil_db=6,
                    gain=1.0,
                    auto_range=True,
                    auto_decay=0.993,
                    state=state,
                )
            )
        self.assertGreater(max(values), min(values))
        self.assertLessEqual(max(values), 1.0)

    def test_trim_linear_levels_matches_cast_gain(self):
        rms, peak = trim_linear_levels(1.0, 1.0, -21.0)
        self.assertAlmostEqual(peak, 10 ** (-21 / 20), places=3)
        self.assertAlmostEqual(rms, peak, places=3)

    def test_stereo_peak_uses_loudest_channel(self):
        samples = np.zeros((1024, 2), dtype=np.float32)
        samples[:, 0] = 0.05
        samples[:, 1] = 0.9
        levels = calculate_audio_levels(samples)
        self.assertAlmostEqual(levels.peak_linear, 0.9, places=2)
        self.assertGreater(levels.rms_linear, 0.05)

    def test_display_mapping_silence_is_zero(self):
        self.assertEqual(map_linear_to_display(0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
