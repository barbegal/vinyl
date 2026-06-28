"""Tests for ALSA capture device resolution."""

from __future__ import annotations

import unittest

from src.audio.alsa_device import (
    parse_hw_device,
    portaudio_device_hint,
    resolve_capture_device,
)


class TestAlsaDevice(unittest.TestCase):
    def test_parse_hw(self) -> None:
        self.assertEqual(parse_hw_device("hw:2,0"), (2, 0))
        self.assertIsNone(parse_hw_device("vinyl_in"))

    def test_portaudio_hint_hw(self) -> None:
        self.assertEqual(portaudio_device_hint("hw:2,0"), "(hw:2,0)")

    def test_portaudio_hint_plughw(self) -> None:
        self.assertEqual(portaudio_device_hint("plughw:2,0"), "(hw:2,0)")

    def test_resolve_plughw_fallback(self) -> None:
        self.assertEqual(resolve_capture_device("hw:1,0"), "plughw:1,0")

    def test_resolve_passthrough_named(self) -> None:
        self.assertEqual(resolve_capture_device("vinyl_in"), "vinyl_in")


if __name__ == "__main__":
    unittest.main()
