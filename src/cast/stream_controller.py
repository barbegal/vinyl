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


@dataclass(frozen=True)
class StreamFormat:
    path: str
    mime: str


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


def build_stream_audio_filter(settings: AppSettings) -> str:
    parts: list[str] = []
    gain = settings.stream_input_gain_db
    if gain != 0.0:
        parts.append(f"volume={gain:.1f}dB")
    mode = settings.cast_stereo_mode
    if mode in ("duplicate", "duplicate_l"):
        parts.append("pan=stereo|c0=c0|c1=c0")
    elif mode in ("duplicate_r", "right"):
        parts.append("pan=stereo|c0=c1|c1=c1")
    elif mode == "swap":
        parts.append("pan=stereo|c0=c1|c1=c0")
    elif mode == "sum":
        parts.append("pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1")
    if settings.cast_stream_eq:
        parts.append("highpass=f=40")
        if settings.stream_high_cut_hz > 0:
            parts.append(f"lowpass=f={settings.stream_high_cut_hz}")
    return ",".join(parts)


def stream_format_for_codec(codec: str) -> StreamFormat:
    if codec in ("wav", "pcm"):
        return StreamFormat("stream.wav", "audio/wav")
    if codec == "aac":
        return StreamFormat("stream.aac", "audio/aac")
    if codec == "flac":
        return StreamFormat("stream.flac", "audio/flac")
    return StreamFormat("stream.mp3", "audio/mpeg")


def cast_codec_fallback_chain(primary: str) -> list[str]:
    """Try lossless first, then step down if the speaker rejects the MIME type."""
    chain = [primary.strip().lower()]
    for codec in ("wav", "flac", "aac", "mp3"):
        if codec not in chain:
            chain.append(codec)
    return chain


def build_ffmpeg_stream_cmd(settings: AppSettings, port: int) -> list[str]:
    capture = resolve_capture_device(settings.usb_alsa_device)
    fmt = stream_format_for_codec(settings.cast_stream_codec)
    cmd: list[str] = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if settings.cast_low_latency:
        cmd.extend(
            [
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-probesize",
                "32",
                "-analyzeduration",
                "0",
            ]
        )
    cmd.extend(
        [
            "-f",
            "alsa",
            "-thread_queue_size",
            str(settings.cast_ffmpeg_queue_size),
        ]
    )
    if settings.cast_low_latency and settings.cast_rtbufsize:
        cmd.extend(["-rtbufsize", settings.cast_rtbufsize])
    cmd.extend(
        [
            "-channels",
            str(settings.channels),
            "-sample_rate",
            str(settings.sample_rate),
            "-i",
            capture,
        ]
    )
    audio_filter = build_stream_audio_filter(settings)
    if audio_filter:
        cmd.extend(["-af", audio_filter])
    cmd.extend(["-ac", "2"])
    codec = settings.cast_stream_codec
    if codec in ("wav", "pcm"):
        cmd.extend(["-c:a", "pcm_s16le", "-f", "wav"])
    elif codec == "aac":
        cmd.extend(
            [
                "-c:a",
                "aac",
                "-aac_coder",
                "fast",
                "-b:a",
                settings.hls_bitrate,
                "-f",
                "adts",
            ]
        )
    elif codec == "flac":
        cmd.extend(
            ["-c:a", "flac", "-compression_level", "0", "-sample_fmt", "s16", "-f", "flac"]
        )
    else:
        cmd.extend(
            [
                "-c:a",
                "libmp3lame",
                "-b:a",
                settings.hls_bitrate,
                "-compression_level",
                "0",
                "-reservoir",
                "0",
                "-f",
                "mp3",
            ]
        )
    if settings.cast_low_latency:
        cmd.extend(
            [
                "-flush_packets",
                "1",
                "-avioflags",
                "direct",
                "-muxdelay",
                "0",
                "-muxpreload",
                "0",
            ]
        )
    cmd.extend(
        [
            "-content_type",
            fmt.mime,
            "-listen",
            "1",
            f"http://0.0.0.0:{port}/{fmt.path}",
        ]
    )
    return cmd


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
        return build_ffmpeg_stream_cmd(self.settings, port)

    def _start_ffmpeg_listen(self, port: int, codec: str) -> tuple[bool, str]:
        settings = AppSettings(
            **{
                **self.settings.__dict__,
                "cast_stream_codec": codec,
            }
        )
        cmd = build_ffmpeg_stream_cmd(settings, port)
        self._ffmpeg_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if _wait_for_ffmpeg_listen(self._ffmpeg_proc):
            return True, ""
        err = _ffmpeg_error(self._ffmpeg_proc)
        if self._ffmpeg_proc.poll() is None:
            self._ffmpeg_proc.terminate()
            try:
                self._ffmpeg_proc.wait(timeout=2)
            except Exception:
                pass
        self._ffmpeg_proc = None
        return False, err

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

            codecs = cast_codec_fallback_chain(self.settings.cast_stream_codec)
            last_err = ""
            for codec in codecs:
                stream_fmt = stream_format_for_codec(codec)
                stream_url = f"http://{host_ip}:{port}/{stream_fmt.path}"
                if codec != self.settings.cast_stream_codec:
                    say(f"Retrying with {codec}…")

                ffmpeg_err = ""
                started = False
                for attempt in range(4):
                    say("Starting audio stream…")
                    ok, ffmpeg_err = self._start_ffmpeg_listen(port, codec)
                    if ok:
                        started = True
                        break
                    busy = "busy" in ffmpeg_err.lower() or "resource" in ffmpeg_err.lower()
                    if busy and attempt < 3:
                        say("Audio in use — retrying…")
                        time.sleep(1.0)
                        continue
                    break

                if not started:
                    last_err = ffmpeg_err or "ffmpeg did not start stream"
                    continue

                say("Sending to speaker…")
                media_controller = self._chromecast.media_controller
                try:
                    media_controller.play_media(stream_url, stream_fmt.mime, stream_type="LIVE")
                    media_controller.block_until_active(timeout=15)
                except Exception as exc:
                    last_err = str(exc)
                    self.stop_stream()
                    continue

                state = media_controller.status.player_state
                if state and state != "PLAYING":
                    media_controller.play()
                _ensure_cast_volume(self._chromecast, self.settings.cast_output_volume)

                if self._ffmpeg_proc is not None and self._ffmpeg_proc.poll() is not None:
                    last_err = _ffmpeg_error(self._ffmpeg_proc)
                    self.stop_stream()
                    continue

                self._set_status(True, target.name, "Streaming", stream_url)
                return True

            self._set_status(
                False,
                target.name,
                last_err if last_err else "Could not start cast stream",
            )
            self.stop_stream()
            return False
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
