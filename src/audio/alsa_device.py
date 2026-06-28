from __future__ import annotations

import re
from pathlib import Path


_HW_RE = re.compile(r"^hw:(\d+),(\d+)$")


def parse_hw_device(device: str) -> tuple[int, int] | None:
    match = _HW_RE.match(device.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def portaudio_device_hint(alsa_device: str) -> str:
    """Substring to match a PortAudio input device to an ALSA device string."""
    device = alsa_device.strip()
    if not device:
        return ""
    card = parse_hw_device(device)
    if card is not None:
        return f"(hw:{card[0]},{card[1]})"
    if device.startswith("plughw:"):
        card = parse_hw_device("hw:" + device[7:])
        if card is not None:
            return f"(hw:{card[0]},{card[1]})"
    return device.lower()


def shared_capture_available() -> bool:
    asoundrc = Path.home() / ".asoundrc"
    if not asoundrc.is_file():
        return False
    try:
        return "pcm.vinyl_in" in asoundrc.read_text(encoding="utf-8")
    except OSError:
        return False


def resolve_capture_device(raw: str) -> str:
    """Pick the ALSA device used for live capture (ffmpeg + level monitor)."""
    device = raw.strip() or "hw:1,0"
    if device == "vinyl_in" or shared_capture_available():
        return "vinyl_in"
    if device.startswith("hw:"):
        return f"plughw:{device[3:]}"
    return device


def capture_is_shared(device: str) -> bool:
    return device.strip() == "vinyl_in" or shared_capture_available()
