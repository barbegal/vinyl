from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional

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


class _HlsServer:
    def __init__(self, root: Path, host: str, port: int) -> None:
        self.root = root
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.root))
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None


def _wait_for_hls(playlist: Path, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if playlist.exists() and playlist.stat().st_size > 0:
            segment = playlist.parent / "live0.ts"
            if segment.exists() or any(playlist.parent.glob("*.ts")):
                return True
        time.sleep(0.25)
    return playlist.exists() and playlist.stat().st_size > 0


def _ffmpeg_error(proc: subprocess.Popen) -> str:
    if proc.stderr is None:
        return "ffmpeg failed"
    try:
        err = proc.stderr.read().strip()
        return err or "ffmpeg failed"
    except Exception:
        return "ffmpeg failed"


class ChromecastStreamController:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._server: Optional[_HlsServer] = None
        self._hls_root: Optional[Path] = None
        self._chromecast = None
        self._status = StreamStatus(False, "", "Idle", "")

    @property
    def status(self) -> StreamStatus:
        return self._status

    def _set_status(self, active: bool, target: str, message: str, url: str = "") -> None:
        self._status = StreamStatus(active, target, message, url)

    def _build_ffmpeg_cmd(self, playlist_path: Path) -> list[str]:
        return [
            self.settings.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "alsa",
            "-thread_queue_size",
            "1024",
            "-ac",
            "2",
            "-ar",
            str(self.settings.sample_rate),
            "-i",
            self.settings.usb_alsa_device,
            "-c:a",
            "aac",
            "-b:a",
            self.settings.hls_bitrate,
            "-f",
            "hls",
            "-hls_time",
            str(self.settings.hls_segment_seconds),
            "-hls_list_size",
            "6",
            "-hls_flags",
            "delete_segments+append_list",
            "-hls_allow_cache",
            "0",
            str(playlist_path),
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

            self._hls_root = Path(tempfile.mkdtemp(prefix="pi-audio-hls-"))
            playlist = self._hls_root / "live.m3u8"

            say("Starting audio stream…")
            cmd = self._build_ffmpeg_cmd(playlist)
            self._ffmpeg_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

            if not _wait_for_hls(playlist):
                if self._ffmpeg_proc.poll() is not None:
                    self._set_status(False, target.name, _ffmpeg_error(self._ffmpeg_proc))
                else:
                    self._set_status(False, target.name, "ffmpeg did not produce HLS stream")
                self.stop_stream()
                return False

            self._server = _HlsServer(self._hls_root, host_ip, self.settings.hls_http_port)
            self._server.start()

            stream_url = f"http://{host_ip}:{self.settings.hls_http_port}/live.m3u8"

            say("Sending to speaker…")
            media_controller = self._chromecast.media_controller
            media_controller.play_media(stream_url, "application/vnd.apple.mpegurl")
            media_controller.block_until_active(timeout=12)

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

        if self._server is not None:
            try:
                self._server.stop()
            except Exception:
                pass
        self._server = None

        if self._hls_root is not None and self._hls_root.exists():
            try:
                for child in self._hls_root.iterdir():
                    if child.is_file():
                        child.unlink(missing_ok=True)
                os.rmdir(self._hls_root)
            except Exception:
                pass
        self._hls_root = None

        # Do not set status here — callers set success/error messages after cleanup.
