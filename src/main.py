from __future__ import annotations

import os
import traceback
from pathlib import Path


def _boot_debug_enabled() -> bool:
    raw = os.getenv("VINYL_BOOT_DEBUG", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def main() -> None:
    use_debug = _boot_debug_enabled()
    root = None
    debug = None

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

        from src.config.settings import AppSettings

        if debug:
            debug.log("Loading settings…")

        settings = AppSettings.from_env()

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
        if debug is not None:
            debug.show_fatal(message)
        else:
            _show_fatal_error(message)
        return


def _show_fatal_error(message: str) -> None:
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
