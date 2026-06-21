import unittest

import numpy as np

from src.audio.levels import calculate_audio_levels


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


if __name__ == "__main__":
    unittest.main()
