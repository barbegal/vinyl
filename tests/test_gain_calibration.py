"""Tests for USB gain calibration helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.audio.gain_calibration import (
    AudioCalibration,
    merge_calibration,
    percent_to_capture_value,
    recommend_gain_db,
    save_calibration,
)
from src.config.settings import AppSettings


class TestGainCalibration(unittest.TestCase):
    def test_recommend_gain_db_from_peak(self) -> None:
        self.assertEqual(recommend_gain_db(0), -9.0)
        self.assertEqual(recommend_gain_db(32768), -15.0)
        self.assertEqual(recommend_gain_db(15000), -9.0)
        self.assertEqual(recommend_gain_db(8000), -6.0)

    def test_percent_to_capture_value(self) -> None:
        self.assertEqual(percent_to_capture_value(50), 31)
        self.assertEqual(percent_to_capture_value(45), 27)

    def test_merge_calibration_respects_env_override(self) -> None:
        base = AppSettings(stream_input_gain_db=-6.0, level_input_trim_db=-6.0)
        cal = AudioCalibration(cast_input_gain_db=-12.0)
        with patch.dict(os.environ, {"CAST_INPUT_GAIN_DB": "-18"}, clear=False):
            merged = merge_calibration(base, cal)
        self.assertEqual(merged.stream_input_gain_db, -6.0)

    def test_merge_calibration_applies_saved_gain(self) -> None:
        base = AppSettings(stream_input_gain_db=-6.0, level_input_trim_db=-6.0)
        cal = AudioCalibration(
            cast_input_gain_db=-12.0,
            cast_output_volume=0.4,
            cast_stereo_mode="stereo",
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "CAST_INPUT_GAIN_DB",
                "AUDIO_LEVEL_INPUT_TRIM_DB",
                "CAST_OUTPUT_VOLUME",
                "CAST_HIGH_CUT_HZ",
                "CAST_STEREO_MODE",
            }
        }
        with patch.dict(os.environ, env, clear=True):
            merged = merge_calibration(base, cal)
        self.assertEqual(merged.stream_input_gain_db, -12.0)
        self.assertEqual(merged.level_input_trim_db, -12.0)
        self.assertEqual(merged.cast_output_volume, 0.4)

    def test_save_and_load_roundtrip(self) -> None:
        cal = AudioCalibration(
            capture_percent=45,
            cast_input_gain_db=-9.0,
            measured_peak=12000,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            with patch("src.audio.gain_calibration.calibration_path", return_value=path):
                save_calibration(cal)
                from src.audio.gain_calibration import load_calibration

                loaded = load_calibration()
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.capture_percent, 45)
            self.assertEqual(loaded.cast_input_gain_db, -9.0)


if __name__ == "__main__":
    unittest.main()
