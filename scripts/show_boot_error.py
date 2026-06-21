#!/usr/bin/env python3
"""Show startup errors on the PiTFT when the main app fails."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path


def main() -> None:
    lines = []
    if len(sys.argv) > 1:
        lines.append(sys.argv[1])
    log = Path.home() / ".vinyl-xsession.log"
    if log.is_file():
        lines.append(log.read_text(encoding="utf-8", errors="replace")[-1800:])
    text = "\n".join(lines).strip() or "App failed to start.\nSee ~/.vinyl-xsession.log"

    root = tk.Tk()
    root.title("Vinyl — error")
    root.configure(bg="#12161f")
    root.geometry("320x240")
    root.attributes("-fullscreen", True)
    tk.Label(
        root,
        text=text,
        fg="#e07b7b",
        bg="#12161f",
        font=("DejaVu Sans", 8),
        wraplength=310,
        justify="left",
        anchor="nw",
    ).pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    root.mainloop()


if __name__ == "__main__":
    main()
