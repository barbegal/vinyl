#!/usr/bin/env python3
"""Show startup errors on the PiTFT when the main app fails."""

from __future__ import annotations

import sys
from pathlib import Path

from src.boot_debug_ui import show_error_screen


def main() -> None:
    extra = sys.argv[1] if len(sys.argv) > 1 else ""
    home = Path.home()
    show_error_screen(
        message=extra,
        log_paths=(
            home / ".vinyl-xsession.log",
            home / ".vinyl-boot.log",
            home / ".local/share/xorg/Xorg.0.log",
        ),
    )


if __name__ == "__main__":
    main()
