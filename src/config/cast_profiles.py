from __future__ import annotations

import os
from typing import Any

# Presets for CAST_STREAM_PROFILE. Explicit .env keys always override these.
CAST_STREAM_PROFILES: dict[str, dict[str, Any]] = {
    # Uncompressed PCM over HTTP — lowest Pi-side delay, highest quality on LAN.
    "live": {
        "cast_stream_codec": "wav",
        "cast_stream_eq": True,
        "cast_ffmpeg_queue_size": 64,
        "cast_rtbufsize": "16k",
        "cast_low_latency": True,
        "stream_high_cut_hz": 16000,
        "vinyl_alsa_period_size": 128,
        "vinyl_alsa_buffer_size": 512,
    },
    # Lossless FLAC — excellent quality, still much faster than MP3 encode.
    "hifi": {
        "cast_stream_codec": "flac",
        "cast_stream_eq": True,
        "cast_ffmpeg_queue_size": 128,
        "cast_rtbufsize": "32k",
        "cast_low_latency": True,
        "stream_high_cut_hz": 18000,
        "vinyl_alsa_period_size": 128,
        "vinyl_alsa_buffer_size": 512,
    },
    # Lossy fallback if a speaker rejects lossless MIME types.
    "compatible": {
        "cast_stream_codec": "mp3",
        "cast_stream_eq": True,
        "cast_ffmpeg_queue_size": 256,
        "cast_rtbufsize": "64k",
        "cast_low_latency": True,
        "stream_high_cut_hz": 14000,
        "hls_bitrate": "192k",
        "vinyl_alsa_period_size": 256,
        "vinyl_alsa_buffer_size": 1024,
    },
}


def profile_value(profile: str, key: str, fallback: Any) -> Any:
    preset = CAST_STREAM_PROFILES.get(profile.strip().lower(), CAST_STREAM_PROFILES["live"])
    return preset.get(key, fallback)


def env_or_profile(name: str, profile: str, profile_key: str, default: Any, cast: Any) -> Any:
    raw = os.getenv(name)
    if raw is not None and str(raw).strip() != "":
        return cast(raw)
    return profile_value(profile, profile_key, default)
