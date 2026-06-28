from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.config.cast_profiles import env_or_profile, profile_value


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
    block_size: int = 256
    input_device_name: str = ""
    usb_alsa_device: str = "hw:1,0"

    hls_http_port: int = 9000
    ffmpeg_bin: str = "ffmpeg"
    hls_segment_seconds: int = 1
    hls_bitrate: str = "192k"
    stream_input_gain_db: float = -9.0
    stream_high_cut_hz: int = 0
    cast_output_volume: float = 1.0
    cast_ffmpeg_queue_size: int = 64
    cast_rtbufsize: str = "16k"
    cast_low_latency: bool = True
    cast_stream_codec: str = "wav"
    cast_stream_eq: bool = False
    cast_eq_bass_db: float = 4.0
    cast_eq_treble_db: float = 2.5
    cast_dynamics: bool = True
    cast_compressor_threshold_db: float = -14.0
    cast_compressor_ratio: float = 2.5
    cast_compressor_makeup_db: float = 2.5
    cast_limiter_ceiling_db: float = -0.8
    cast_stream_profile: str = "live"
    cast_stereo_mode: str = "stereo"
    vinyl_alsa_period_size: int = 128
    vinyl_alsa_buffer_size: int = 512
    level_display_gain: float = 1.0
    level_floor_db: float = -58.0
    level_ceil_db: float = 6.0
    level_auto_range: bool = True
    level_auto_decay: float = 0.993
    level_input_trim_db: float = -9.0

    cast_discovery_timeout: float = 12.0
    cast_refresh_interval: float = 6.0
    cast_known_hosts: list[str] = field(default_factory=list)
    plate_buttons_side: str = "left"

    web_ui_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    auto_cast_targets: list[str] = field(
        default_factory=lambda: ["Living Room pair"]
    )

    @classmethod
    def from_env(cls) -> "AppSettings":
        known_raw = os.getenv("CAST_KNOWN_HOSTS", "").strip()
        known_hosts = [h.strip() for h in known_raw.split(",") if h.strip()]
        plate_side = os.getenv("PLATE_BUTTONS_SIDE", "left").strip().lower()
        if plate_side not in {"left", "right"}:
            plate_side = "left"

        auto_raw = os.getenv("VINYL_AUTO_CAST")
        if auto_raw is None:
            auto_targets = ["Living Room pair"]
        else:
            auto_targets = [s.strip() for s in auto_raw.split(",") if s.strip()]

        profile = os.getenv("CAST_STREAM_PROFILE", "live").strip().lower()

        return cls(
            screen_width=int(os.getenv("SCREEN_WIDTH", "320")),
            screen_height=int(os.getenv("SCREEN_HEIGHT", "240")),
            fullscreen=_env_bool("FULLSCREEN", True),
            sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "48000")),
            channels=int(os.getenv("AUDIO_CHANNELS", "2")),
            block_size=int(os.getenv("AUDIO_BLOCK_SIZE", "256")),
            input_device_name=os.getenv("AUDIO_INPUT_DEVICE_NAME", "").strip(),
            usb_alsa_device=os.getenv("USB_ALSA_DEVICE", "hw:1,0").strip(),
            hls_http_port=int(os.getenv("HLS_HTTP_PORT", "9000")),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg").strip(),
            hls_segment_seconds=int(os.getenv("HLS_SEGMENT_SECONDS", "1")),
            hls_bitrate=str(
                env_or_profile("HLS_BITRATE", profile, "hls_bitrate", "192k", str)
            ),
            stream_input_gain_db=float(os.getenv("CAST_INPUT_GAIN_DB", "-9")),
            stream_high_cut_hz=int(
                env_or_profile(
                    "CAST_HIGH_CUT_HZ", profile, "stream_high_cut_hz", 0, int
                )
            ),
            cast_output_volume=float(os.getenv("CAST_OUTPUT_VOLUME", "1.0")),
            cast_ffmpeg_queue_size=int(
                env_or_profile(
                    "CAST_FFMPEG_QUEUE_SIZE", profile, "cast_ffmpeg_queue_size", 64, int
                )
            ),
            cast_rtbufsize=str(
                env_or_profile("CAST_RTBUFSIZE", profile, "cast_rtbufsize", "16k", str)
            ),
            cast_low_latency=_env_bool(
                "CAST_LOW_LATENCY",
                bool(profile_value(profile, "cast_low_latency", True)),
            )
            if os.getenv("CAST_LOW_LATENCY") is None
            else _env_bool("CAST_LOW_LATENCY", True),
            cast_stream_codec=str(
                env_or_profile("CAST_STREAM_CODEC", profile, "cast_stream_codec", "wav", str)
            ).lower(),
            cast_stream_eq=_env_bool(
                "CAST_STREAM_EQ",
                bool(profile_value(profile, "cast_stream_eq", False)),
            )
            if os.getenv("CAST_STREAM_EQ") is None
            else _env_bool("CAST_STREAM_EQ", False),
            cast_eq_bass_db=float(os.getenv("CAST_EQ_BASS_DB", "4")),
            cast_eq_treble_db=float(os.getenv("CAST_EQ_TREBLE_DB", "2.5")),
            cast_dynamics=_env_bool(
                "CAST_DYNAMICS",
                bool(profile_value(profile, "cast_dynamics", True)),
            )
            if os.getenv("CAST_DYNAMICS") is None
            else _env_bool("CAST_DYNAMICS", True),
            cast_compressor_threshold_db=float(
                os.getenv("CAST_COMPRESSOR_THRESHOLD_DB", "-14")
            ),
            cast_compressor_ratio=float(os.getenv("CAST_COMPRESSOR_RATIO", "2.5")),
            cast_compressor_makeup_db=float(os.getenv("CAST_COMPRESSOR_MAKEUP_DB", "2.5")),
            cast_limiter_ceiling_db=float(os.getenv("CAST_LIMITER_CEILING_DB", "-0.8")),
            cast_stream_profile=profile,
            cast_stereo_mode=os.getenv("CAST_STEREO_MODE", "stereo").strip().lower(),
            vinyl_alsa_period_size=int(
                env_or_profile(
                    "VINYL_ALSA_PERIOD_SIZE", profile, "vinyl_alsa_period_size", 128, int
                )
            ),
            vinyl_alsa_buffer_size=int(
                env_or_profile(
                    "VINYL_ALSA_BUFFER_SIZE", profile, "vinyl_alsa_buffer_size", 512, int
                )
            ),
            level_display_gain=float(os.getenv("AUDIO_LEVEL_GAIN", "1.0")),
            level_floor_db=float(os.getenv("AUDIO_LEVEL_FLOOR_DB", "-58")),
            level_ceil_db=float(os.getenv("AUDIO_LEVEL_CEIL_DB", "6")),
            level_auto_range=_env_bool("AUDIO_LEVEL_AUTO_RANGE", True),
            level_auto_decay=float(os.getenv("AUDIO_LEVEL_AUTO_DECAY", "0.993")),
            level_input_trim_db=float(
                os.getenv("AUDIO_LEVEL_INPUT_TRIM_DB", "").strip()
                or os.getenv("CAST_INPUT_GAIN_DB", "-9")
            ),
            cast_discovery_timeout=float(os.getenv("CAST_DISCOVERY_TIMEOUT", "12")),
            cast_refresh_interval=float(os.getenv("CAST_REFRESH_INTERVAL", "6")),
            cast_known_hosts=known_hosts,
            plate_buttons_side=plate_side,
            web_ui_enabled=_env_bool("VINYL_WEB_UI", True),
            web_host=os.getenv("VINYL_WEB_HOST", "0.0.0.0").strip(),
            web_port=int(os.getenv("VINYL_WEB_PORT", "8080")),
            auto_cast_targets=auto_targets,
        )


def load_settings() -> AppSettings:
    """Load .env defaults, then apply ~/.vinyl/calibration.json for audio (unless .env overrides)."""
    from src.audio.gain_calibration import load_settings_with_calibration

    return load_settings_with_calibration()
