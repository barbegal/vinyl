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
    channels: int = 2
    block_size: int = 1024
    input_device_name: str = ""
    usb_alsa_device: str = "hw:1,0"

    hls_http_port: int = 9000
    ffmpeg_bin: str = "ffmpeg"
    hls_segment_seconds: int = 1
    hls_bitrate: str = "192k"
    # Attenuate hot line-in before encoding (dB). Typical USB phono: -6 to -12.
    stream_input_gain_db: float = -9.0
    # Low-pass to reduce harsh/tinny highs (Hz). 0 = off.
    stream_high_cut_hz: int = 14_000
    # Chromecast playback level when a stream starts (0.0–1.0).
    cast_output_volume: float = 0.35
    # Level bar sensitivity — higher = bars move more at the same input.
    level_display_gain: float = 4.0

    cast_discovery_timeout: float = 12.0
    cast_refresh_interval: float = 6.0
    cast_known_hosts: list[str] = field(default_factory=list)
    plate_buttons_side: str = "left"

    web_ui_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # Speakers to auto-connect to on startup, in priority order. The app keeps
    # scanning until the first match appears, then streams USB audio to it.
    auto_cast_targets: list[str] = field(
        default_factory=lambda: ["Upper", "Living Room Speaker"]
    )

    @classmethod
    def from_env(cls) -> "AppSettings":
        known_raw = os.getenv("CAST_KNOWN_HOSTS", "").strip()
        known_hosts = [h.strip() for h in known_raw.split(",") if h.strip()]
        plate_side = os.getenv("PLATE_BUTTONS_SIDE", "left").strip().lower()
        if plate_side not in {"left", "right"}:
            plate_side = "left"

        # Unset → sensible default; empty string → feature disabled.
        auto_raw = os.getenv("VINYL_AUTO_CAST")
        if auto_raw is None:
            auto_targets = ["Upper", "Living Room Speaker"]
        else:
            auto_targets = [s.strip() for s in auto_raw.split(",") if s.strip()]
        return cls(
            screen_width=int(os.getenv("SCREEN_WIDTH", "320")),
            screen_height=int(os.getenv("SCREEN_HEIGHT", "240")),
            fullscreen=_env_bool("FULLSCREEN", True),
            sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "48000")),
            channels=int(os.getenv("AUDIO_CHANNELS", "2")),
            block_size=int(os.getenv("AUDIO_BLOCK_SIZE", "1024")),
            input_device_name=os.getenv("AUDIO_INPUT_DEVICE_NAME", "").strip(),
            usb_alsa_device=os.getenv("USB_ALSA_DEVICE", "hw:1,0").strip(),
            hls_http_port=int(os.getenv("HLS_HTTP_PORT", "9000")),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg").strip(),
            hls_segment_seconds=int(os.getenv("HLS_SEGMENT_SECONDS", "1")),
            hls_bitrate=os.getenv("HLS_BITRATE", "192k").strip(),
            stream_input_gain_db=float(os.getenv("CAST_INPUT_GAIN_DB", "-9")),
            stream_high_cut_hz=int(os.getenv("CAST_HIGH_CUT_HZ", "14000")),
            cast_output_volume=float(os.getenv("CAST_OUTPUT_VOLUME", "0.35")),
            level_display_gain=float(os.getenv("AUDIO_LEVEL_GAIN", "4.0")),
            cast_discovery_timeout=float(os.getenv("CAST_DISCOVERY_TIMEOUT", "12")),
            cast_refresh_interval=float(os.getenv("CAST_REFRESH_INTERVAL", "6")),
            cast_known_hosts=known_hosts,
            plate_buttons_side=plate_side,
            web_ui_enabled=_env_bool("VINYL_WEB_UI", True),
            web_host=os.getenv("VINYL_WEB_HOST", "0.0.0.0").strip(),
            web_port=int(os.getenv("VINYL_WEB_PORT", "8080")),
            auto_cast_targets=auto_targets,
        )
