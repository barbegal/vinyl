"""Tests for Chromecast ffmpeg stream command building."""

from __future__ import annotations

import os
import unittest

from src.cast.stream_controller import (
    build_ffmpeg_stream_cmd,
    build_stream_audio_filter,
    build_stream_dynamics_filter,
    cast_codec_fallback_chain,
)
from src.config.settings import AppSettings


class TestStreamController(unittest.TestCase):
    def _settings(self, **overrides) -> AppSettings:
        base = AppSettings(usb_alsa_device="hw:2,0")
        return AppSettings(**{**base.__dict__, **overrides})

    def test_live_wav_skips_eq_and_uses_pcm(self) -> None:
        cmd = build_ffmpeg_stream_cmd(
            self._settings(cast_stream_codec="wav", cast_stream_eq=False), 9000
        )
        joined = " ".join(cmd)
        self.assertIn("pcm_s16le", joined)
        self.assertIn("stream.wav", joined)
        self.assertNotIn("highpass", joined)
        self.assertIn("-muxdelay 0", joined)

    def test_hifi_flac_includes_eq_when_enabled(self) -> None:
        filt = build_stream_audio_filter(
            self._settings(
                cast_stream_eq=True,
                stream_high_cut_hz=18000,
                cast_eq_bass_db=4.0,
                cast_eq_treble_db=2.5,
            )
        )
        self.assertIn("highpass=f=40", filt)
        self.assertIn("equalizer=f=100", filt)
        self.assertIn("equalizer=f=10000", filt)
        self.assertIn("lowpass=f=18000", filt)

    def test_eq_bass_treble_off_when_zero(self) -> None:
        filt = build_stream_audio_filter(
            self._settings(
                cast_stream_eq=True,
                stream_high_cut_hz=16000,
                cast_eq_bass_db=0,
                cast_eq_treble_db=0,
            )
        )
        self.assertIn("highpass=f=40", filt)
        self.assertNotIn("equalizer", filt)

    def test_dynamics_after_eq_when_enabled(self) -> None:
        filt = build_stream_audio_filter(
            self._settings(cast_stream_eq=True, cast_dynamics=True, stream_high_cut_hz=16000)
        )
        self.assertIn("highpass=f=40", filt)
        self.assertIn("acompressor", filt)
        self.assertIn("alimiter", filt)
        self.assertLess(filt.index("highpass"), filt.index("acompressor"))

    def test_dynamics_off_when_disabled(self) -> None:
        filt = build_stream_dynamics_filter(self._settings(cast_dynamics=False))
        self.assertEqual(filt, "")

    def test_codec_fallback_chain(self) -> None:
        chain = cast_codec_fallback_chain("wav")
        self.assertEqual(chain[0], "wav")
        self.assertIn("flac", chain)
        self.assertIn("mp3", chain)

    def test_duplicate_r_pan(self) -> None:
        filt = build_stream_audio_filter(self._settings(cast_stereo_mode="duplicate_r"))
        self.assertIn("pan=stereo|c0=c1|c1=c1", filt)

    def test_profile_live_from_env(self) -> None:
        os.environ["CAST_STREAM_PROFILE"] = "live"
        try:
            s = AppSettings.from_env()
            self.assertEqual(s.cast_stream_codec, "wav")
            self.assertTrue(s.cast_stream_eq)
            self.assertEqual(s.stream_high_cut_hz, 16000)
            self.assertEqual(s.cast_ffmpeg_queue_size, 64)
        finally:
            os.environ.pop("CAST_STREAM_PROFILE", None)


if __name__ == "__main__":
    unittest.main()
