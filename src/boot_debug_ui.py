"""Fullscreen boot progress panel — paints before slow imports on the PiTFT."""

from __future__ import annotations

import os
import re
import sys
import tkinter as tk
import warnings
from pathlib import Path
from typing import IO, Optional

from src.boot_timing import log_milestone

_BG = "#12161f"
_FG = "#c8d0de"
_OK = "#7ec99a"
_ERR = "#e07b7b"
_TITLE = "#f0f3ff"
_FONT = ("DejaVu Sans", 8)
_TITLE_FONT = ("DejaVu Sans", 9, "bold")
_MAX_LINES = 16


class BootDebugPanel:
    """Overlay on an existing Tk root; shows scrolling startup lines and errors."""

    def __init__(self, root: tk.Tk, width: int = 320, height: int = 240) -> None:
        self.root = root
        self._entries: list[tuple[str, bool]] = []
        self._detached = False
        self._stderr_original: Optional[IO[str]] = None
        self._warn_handler_original = warnings.showwarning

        root.title("Vinyl — boot")
        root.configure(bg=_BG)
        root.geometry(f"{width}x{height}")
        root.attributes("-fullscreen", True)

        self._frame = tk.Frame(root, bg=_BG)
        self._frame.place(x=0, y=0, relwidth=1, relheight=1)

        tk.Label(
            self._frame,
            text="Vinyl boot",
            fg=_TITLE,
            bg=_BG,
            font=_TITLE_FONT,
            anchor="w",
        ).pack(fill=tk.X, padx=6, pady=(6, 2))

        self._uptime_label = tk.Label(
            self._frame,
            text="",
            fg=_OK,
            bg=_BG,
            font=_FONT,
            anchor="w",
        )
        self._uptime_label.pack(fill=tk.X, padx=6, pady=(0, 4))

        self._text = tk.Text(
            self._frame,
            fg=_FG,
            bg="#0a0c12",
            font=_FONT,
            wrap=tk.WORD,
            height=12,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#2a3344",
            state=tk.DISABLED,
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self._text.tag_configure("info", foreground=_FG)
        self._text.tag_configure("err", foreground=_ERR)

        self._paint()
        self.log("Tk window created")
        log_milestone("boot debug visible")

    def _uptime_str(self) -> str:
        try:
            uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
            return f"kernel uptime {uptime:.1f}s"
        except OSError:
            return ""

    def _has_errors(self) -> bool:
        return any(is_err for _, is_err in self._entries)

    def _refresh_text(self) -> None:
        if self._detached:
            return
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        for line, is_err in self._entries[-_MAX_LINES:]:
            tag = "err" if is_err else "info"
            self._text.insert(tk.END, line + "\n", tag)
        self._text.configure(state=tk.DISABLED)
        if self._has_errors():
            self._uptime_label.configure(fg=_ERR, text=self._uptime_str() + " · errors")

    def _paint(self) -> None:
        if self._detached:
            return
        if not self._has_errors():
            self._uptime_label.configure(text=self._uptime_str(), fg=_OK)
        self._refresh_text()
        self.root.update_idletasks()
        self.root.update()

    def log(self, message: str) -> None:
        for line in message.strip().splitlines():
            text = line.strip()
            if text:
                self._entries.append((text, False))
                log_milestone(f"boot: {text}")
        self._paint()

    def log_error(self, message: str) -> None:
        for line in message.strip().splitlines():
            text = line.strip()
            if not text:
                continue
            if not text.upper().startswith("ERR"):
                text = f"ERR: {text}"
            self._entries.append((text, True))
            log_milestone(f"boot err: {text}")
        self._paint()

    def log_env(self) -> None:
        self.log(f"DISPLAY={os.environ.get('DISPLAY', 'unset')}")
        self.log(f"FRAMEBUFFER={os.environ.get('FRAMEBUFFER', 'unset')}")
        fb = os.environ.get("FRAMEBUFFER", "").strip()
        if fb and os.path.exists(fb):
            self.log(f"{fb}=yes")
        elif os.path.exists("/dev/fb1"):
            self.log("/dev/fb1=yes")
        elif os.path.exists("/dev/fb0"):
            self.log("/dev/fb0=yes")
        else:
            self.log_error("No framebuffer — run setup_pitft.sh")

    def log_xorg_errors(self, max_lines: int = 5) -> None:
        for line in read_xorg_error_lines(max_lines=max_lines):
            self.log_error(line)

    def log_file_tail(
        self,
        path: Path,
        label: str,
        max_chars: int = 1200,
        max_lines: int = 6,
    ) -> None:
        if not path.is_file():
            return
        try:
            body = path.read_text(encoding="utf-8", errors="replace")[-max_chars:]
        except OSError:
            return
        interesting = [
            ln.strip()
            for ln in body.splitlines()
            if re.search(
                r"(error|failed|denied|traceback|exception|EE\)|fatal)",
                ln,
                re.I,
            )
        ]
        if not interesting:
            interesting = [ln.strip() for ln in body.splitlines() if ln.strip()][-6:]
        if interesting:
            self.log_error(f"{label}:")
            for ln in interesting[-max_lines:]:
                self.log_error(ln)

    def detach(self) -> None:
        if self._detached:
            return
        self._detached = True
        if isinstance(sys.stderr, StderrBootLogger) and sys.stderr._debug is self:
            sys.stderr = sys.stderr._original
        if warnings.showwarning is not self._warn_handler_original:
            warnings.showwarning = self._warn_handler_original
        self._frame.destroy()
        self.root.update_idletasks()
        self.root.update()

    def show_fatal(self, message: str) -> None:
        self.log_error("STARTUP FAILED")
        for chunk in message.strip().splitlines():
            if chunk.strip():
                self.log_error(chunk)
        self.log_file_tail(Path.home() / ".vinyl-xsession.log", "xsession log")
        self._paint()
        self.root.mainloop()


class StderrBootLogger(IO[str]):
    """Tee stderr to the boot debug panel."""

    def __init__(self, debug: BootDebugPanel, original: IO[str]) -> None:
        self._debug = debug
        self._original = original
        self._buf = ""

    def write(self, s: str) -> int:
        try:
            self._original.write(s)
        except OSError:
            pass
        if not s or self._debug._detached:
            return len(s)
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._debug.log_error(line.strip())
        return len(s)

    def flush(self) -> None:
        try:
            self._original.flush()
        except OSError:
            pass
        if self._buf.strip() and not self._debug._detached:
            self._debug.log_error(self._buf.strip())
            self._buf = ""

    def isatty(self) -> bool:
        try:
            return self._original.isatty()
        except OSError:
            return False


def read_xorg_error_lines(max_lines: int = 5) -> list[str]:
    candidates = [
        Path.home() / ".local/share/xorg/Xorg.0.log",
        Path("/var/log/Xorg.0.log"),
    ]
    lines: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
        except OSError:
            continue
        for ln in tail:
            if "(EE)" in ln or "(WW)" in ln:
                cleaned = ln.strip()
                if cleaned and cleaned not in lines:
                    lines.append(cleaned)
        if lines:
            break
    return lines[-max_lines:]


def attach_boot_logging(debug: BootDebugPanel) -> IO[str]:
    """Wire stderr + warnings into the on-screen boot panel."""
    original_stderr = sys.stderr
    debug._stderr_original = original_stderr
    sys.stderr = StderrBootLogger(debug, original_stderr)

    def _warn_handler(
        message: object,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: Optional[IO[str]] = None,
        line: Optional[str] = None,
    ) -> None:
        if not debug._detached:
            debug.log_error(f"{category.__name__}: {message}")

    debug._warn_handler_original = warnings.showwarning
    warnings.showwarning = _warn_handler
    return original_stderr


def show_error_screen(
    title: str = "Vinyl — error",
    message: str = "",
    log_paths: tuple[Path, ...] = (),
) -> None:
    """Fullscreen red error view (used when the app never reached Python boot UI)."""
    root = tk.Tk()
    root.title(title)
    root.configure(bg=_BG)
    root.geometry("320x240")
    root.attributes("-fullscreen", True)

    panel = BootDebugPanel(root)
    if message.strip():
        panel.log_error(message.strip())
    for path in log_paths:
        panel.log_file_tail(path, path.name)
    if not panel._has_errors():
        panel.log_error("App failed to start — see ~/.vinyl-xsession.log")
    panel.root.mainloop()
