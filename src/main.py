from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _boot_debug_enabled() -> bool:
    raw = os.getenv("VINYL_BOOT_DEBUG", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _x11_display_ready() -> bool:
    """True when DISPLAY points at a running local X server (e.g. :0 from startx)."""
    display = os.environ.get("DISPLAY", "").strip()
    if not display.startswith(":"):
        return False
    try:
        num = display[1:].split(".", 1)[0]
        return os.path.exists(f"/tmp/.X11-unix/X{num}")
    except (ValueError, IndexError):
        return False


def _print_no_display_help() -> None:
    print(
        "\nNo X server on DISPLAY — Tk cannot open the PiTFT.\n"
        "  Do not run: python -m src.main   (from SSH alone)\n"
        "  Instead:    sudo pkill -x Xorg   (autologin restarts startx)\n"
        "  Or check:   pgrep -a Xorg\n",
        file=sys.stderr,
    )


def main() -> None:
    use_debug = _boot_debug_enabled()
    root = None
    debug = None

    if not _x11_display_ready():
        _print_no_display_help()
        return

    try:
        import tkinter as tk

        from src.boot_debug_ui import BootDebugPanel, attach_boot_logging

        root = tk.Tk()
        if use_debug:
            debug = BootDebugPanel(root)
            attach_boot_logging(debug)
            debug.log("Python started")
            debug.log_env()
            debug.log_xorg_errors()

        from src.config.settings import load_settings

        if debug:
            debug.log("Loading settings…")

        settings = load_settings()

        if debug:
            debug.log("Opening main UI shell…")

        from src.display.fullscreen_ui import FullscreenApp

        app = FullscreenApp(
            settings=settings,
            root=root,
            boot_debug=debug,
        )
        app.run()
    except Exception:
        traceback.print_exc()
        message = traceback.format_exc()
        if "couldn't connect to display" in message.lower():
            _print_no_display_help()
            return
        if debug is not None:
            debug.show_fatal(message)
        else:
            _show_fatal_error(message)
        return


def _show_fatal_error(message: str) -> None:
    if not _x11_display_ready():
        print(message, file=sys.stderr)
        _print_no_display_help()
        return

    from src.boot_debug_ui import show_error_screen

    show_error_screen(
        message=message,
        log_paths=(
            Path.home() / ".vinyl-xsession.log",
            Path.home() / ".vinyl-boot.log",
        ),
    )


if __name__ == "__main__":
    main()
