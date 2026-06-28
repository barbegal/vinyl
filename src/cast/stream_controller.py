from __future__ import annotations

import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

from src.audio.alsa_device import resolve_capture_device
from src.cast.errors import friendly_cast_error
from src.cast.group_discovery import CastTarget
from src.config.settings import AppSettings

try:
    import pychromecast
    from pychromecast import get_chromecast_from_cast_info
except Exception:
    pychromecast = None
    get_chromecast_from_cast_info = None


@dataclass(frozen=True)
class StreamStatus:
    active: bool
    target_name: str
    message: str
    stream_url: str


def _local_ip_for_lan() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = str(sock.getsockname()[0])
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass
    finally:
        sock.close()

    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass

    return "127.0.0.1"


def _ffmpeg_error(proc: subprocess.Popen) -> str:
    if proc.stderr is None:
        return "ffmpeg failed"
    try:
        err = proc.stderr.read().strip()
        return err or "ffmpeg failed"
    except Exception:
        return "ffmpeg failed"


def _wait_for_ffmpeg_listen(proc: subprocess.Popen, timeout: float = 8.0) -> bool:
    """Wait for ffmpeg -listen to bind without connecting (that would steal the client)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        time.sleep(0.25)
    return proc.poll() is None


def _ensure_cast_volume(chromecast, level: float) -> None:
    try:
        if chromecast.status.volume_muted:
            chromecast.set_volume_muted(False)
        chromecast.set_volume(max(0.0, min(1.0, level)))
    except Exception:
        pass


def _stream_audio_filter(settings: AppSettings) -> str:
    parts: list[str] = []
    gain = settings.stream_input_gain_db
    if gain != 0.0:
        parts.append(f"volume={gain:.1f}dB")
    parts.append("highpass=f=40")
    if settings.stream_high_cut_hz > 0:
        parts.append(f"lowpass=f={settings.stream_high_cut_hz}")
    return ",".join(parts)


class ChromecastStreamController:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._chromecast = None
        self._status = StreamStatus(False, "", "Idle", "")

    @property
    def status(self) -> StreamStatus:
        return self._status

    def _set_status(self, active: bool, target: str, message: str, url: str = "") -> None:
        self._status = StreamStatus(active, target, message, url)

    def _build_ffmpeg_cmd(self, port: int) -> list[str]:
        capture = resolve_capture_device(self.settings.usb_alsa_device)
        return [
            self.settings.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "alsa",
            "-thread_queue_size",
            "1024",
            "-channels",
            str(self.settings.channels),
            "-sample_rate",
            str(self.settings.sample_rate),
            "-i",
            capture,
            "-af",
            _stream_audio_filter(self.settings),
            "-ac",
            "2",
            "-c:a",
            "libmp3lame",
            "-b:a",
            self.settings.hls_bitrate,
            "-compression_level",
            "0",
            "-f",
            "mp3",
            "-content_type",
            "audio/mpeg",
            "-listen",
            "1",
            f"http://0.0.0.0:{port}/stream.mp3",
        ]

    def start_stream(
        self,
        target: CastTarget,
        zconf=None,
        cast_info=None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> bool:
        def say(message: str) -> None:
            if on_status is not None:
                on_status(message)

        self.stop_stream()

        if pychromecast is None or get_chromecast_from_cast_info is None:
            self._set_status(False, target.name, "Run: pip install -r requirements.txt")
            return False

        ffmpeg_path = shutil.which(self.settings.ffmpeg_bin)
        if ffmpeg_path is None:
            self._set_status(False, target.name, f"Could not find {self.settings.ffmpeg_bin}")
            return False

        info = cast_info or target.cast_info
        host_ip = _local_ip_for_lan()
        if host_ip.startswith("127."):
            self._set_status(False, target.name, "Pi has no LAN IP — check Wi-Fi")
            return False

        port = self.settings.hls_http_port
        stream_url = f"http://{host_ip}:{port}/stream.mp3"

        try:
            say(f"Connecting to {target.name}…")
            self._chromecast = get_chromecast_from_cast_info(
                info,
                zconf=zconf,
                tries=2,
                timeout=12.0,
                retry_wait=1.5,
            )
            say("Waiting for speaker…")
            self._chromecast.wait(timeout=12.0)

            say("Starting audio stream…")
            cmd = self._build_ffmpeg_cmd(port)
            ffmpeg_err = ""
            for attempt in range(4):
                self._ffmpeg_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if _wait_for_ffmpeg_listen(self._ffmpeg_proc):
                    break
                ffmpeg_err = _ffmpeg_error(self._ffmpeg_proc)
                busy = "busy" in ffmpeg_err.lower() or "resource" in ffmpeg_err.lower()
                if self._ffmpeg_proc.poll() is None:
                    self._ffmpeg_proc.terminate()
                    try:
                        self._ffmpeg_proc.wait(timeout=2)
                    except Exception:
                        pass
                self._ffmpeg_proc = None
                if busy and attempt < 3:
                    say("Audio in use — retrying…")
                    time.sleep(1.0)
                    continue
                self._set_status(
                    False,
                    target.name,
                    ffmpeg_err if ffmpeg_err else "ffmpeg did not start stream",
                )
                self.stop_stream()
                return False

            say("Sending to speaker…")
            media_controller = self._chromecast.media_controller
            media_controller.play_media(stream_url, "audio/mp3", stream_type="LIVE")
            media_controller.block_until_active(timeout=20)
            state = media_controller.status.player_state
            if state and state != "PLAYING":
                media_controller.play()
                time.sleep(0.5)
            _ensure_cast_volume(self._chromecast, self.settings.cast_output_volume)

            if self._ffmpeg_proc is not None and self._ffmpeg_proc.poll() is not None:
                self._set_status(False, target.name, _ffmpeg_error(self._ffmpeg_proc))
                self.stop_stream()
                return False

            self._set_status(True, target.name, "Streaming", stream_url)
            return True
        except Exception as exc:
            self._set_status(False, target.name, friendly_cast_error(exc))
            self.stop_stream()
            return False

    def stop_stream(self) -> None:
        if self._chromecast is not None:
            try:
                self._chromecast.media_controller.stop()
                self._chromecast.quit_app()
            except Exception:
                pass
        self._chromecast = None

        if self._ffmpeg_proc is not None:
            try:
                self._ffmpeg_proc.terminate()
                self._ffmpeg_proc.wait(timeout=2)
            except Exception:
                try:
                    self._ffmpeg_proc.kill()
                except Exception:
                    pass
        self._ffmpeg_proc = None

        # Do not set status here — callers set success/error messages after cleanup.
