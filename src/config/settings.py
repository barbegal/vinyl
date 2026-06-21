from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppSettings:
    screen_width: int = 320
    screen_height: int = 240
    fullscreen: bool = True

    sample_rate: int = 48_000
    channels: int = 1
    block_size: int = 1024
    input_device_name: str = ""
    usb_alsa_device: str = "hw:1,0"

    hls_http_port: int = 9000
    ffmpeg_bin: str = "ffmpeg"
    hls_segment_seconds: int = 1
    hls_bitrate: str = "128k"

    groups_only: bool = True
    cast_discovery_timeout: float = 12.0
    cast_known_hosts: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "AppSettings":
        known_raw = os.getenv("CAST_KNOWN_HOSTS", "").strip()
        known_hosts = [h.strip() for h in known_raw.split(",") if h.strip()]
        return cls(
            screen_width=int(os.getenv("SCREEN_WIDTH", "320")),
            screen_height=int(os.getenv("SCREEN_HEIGHT", "240")),
            fullscreen=_env_bool("FULLSCREEN", True),
            sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "48000")),
            channels=int(os.getenv("AUDIO_CHANNELS", "1")),
            block_size=int(os.getenv("AUDIO_BLOCK_SIZE", "1024")),
            input_device_name=os.getenv("AUDIO_INPUT_DEVICE_NAME", "").strip(),
            usb_alsa_device=os.getenv("USB_ALSA_DEVICE", "hw:1,0").strip(),
            hls_http_port=int(os.getenv("HLS_HTTP_PORT", "9000")),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg").strip(),
            hls_segment_seconds=int(os.getenv("HLS_SEGMENT_SECONDS", "1")),
            hls_bitrate=os.getenv("HLS_BITRATE", "128k").strip(),
            groups_only=_env_bool("GOOGLE_GROUPS_ONLY", True),
            cast_discovery_timeout=float(os.getenv("CAST_DISCOVERY_TIMEOUT", "12")),
            cast_known_hosts=known_hosts,
        )
