from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.audio.levels import AudioLevels, calculate_audio_levels

try:
    import sounddevice as sd
except Exception:
    sd = None


@dataclass(frozen=True)
class AudioSnapshot:
    timestamp: float
    levels: AudioLevels
    active: bool


class AudioInputListener:
    def __init__(
        self,
        sample_rate: int,
        channels: int,
        block_size: int,
        preferred_device_name: str = "",
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.preferred_device_name = preferred_device_name

        self._stream = None
        self._running = False
        self._lock = threading.Lock()
        self._latest = AudioSnapshot(
            timestamp=time.time(),
            levels=AudioLevels(0.0, 0.0, -120.0, -120.0),
            active=False,
        )
        self._last_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return sd is not None

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def list_input_devices(self) -> list[dict]:
        if sd is None:
            return []
        devices = sd.query_devices()
        return [
            {
                "index": idx,
                "name": d.get("name", ""),
                "max_input_channels": d.get("max_input_channels", 0),
                "default_samplerate": d.get("default_samplerate", 0),
            }
            for idx, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]

    def _choose_device(self) -> Optional[int]:
        if sd is None:
            return None
        if not self.preferred_device_name:
            return None

        target = self.preferred_device_name.lower()
        for idx, dev in enumerate(sd.query_devices()):
            name = str(dev.get("name", "")).lower()
            max_in = int(dev.get("max_input_channels", 0))
            if max_in > 0 and target in name:
                return idx
        return None

    def start(self) -> bool:
        if sd is None:
            self._last_error = "python-sounddevice is not installed"
            return False
        if self._running:
            return True

        def callback(indata, frames, time_info, status):
            del frames, time_info
            if status:
                self._last_error = str(status)
            levels = calculate_audio_levels(np.array(indata, copy=False))
            snapshot = AudioSnapshot(
                timestamp=time.time(),
                levels=levels,
                active=levels.peak_linear > 0.001,
            )
            with self._lock:
                self._latest = snapshot

        try:
            last_exc: Exception | None = None
            channel_attempts = [self.channels]
            if self.channels == 1:
                channel_attempts.append(2)

            for attempt_channels in channel_attempts:
                try:
                    self._stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=attempt_channels,
                        blocksize=self.block_size,
                        device=self._choose_device(),
                        dtype="float32",
                        callback=callback,
                    )
                    self._stream.start()
                    self._running = True
                    self._last_error = None
                    return True
                except Exception as exc:
                    last_exc = exc
                    self._stream = None
                    self._running = False

            self._last_error = str(last_exc) if last_exc else "audio input unavailable"
            return False
        except Exception as exc:
            self._last_error = str(exc)
            self._stream = None
            self._running = False
            return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._stream = None
        self._running = False

    def get_latest_snapshot(self) -> AudioSnapshot:
        with self._lock:
            return self._latest
