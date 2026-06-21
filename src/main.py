from __future__ import annotations

import sys
import traceback

from src.config.settings import AppSettings


def main() -> None:
    try:
        from src.display.fullscreen_ui import FullscreenApp

        settings = AppSettings.from_env()
        app = FullscreenApp(settings=settings)
        app.run()
    except Exception as exc:
        traceback.print_exc()
        _show_fatal_error(str(exc))
        raise


def _show_fatal_error(message: str) -> None:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.title("Vinyl — error")
        root.configure(bg="#12161f")
        root.geometry("320x240")
        root.attributes("-fullscreen", True)
        tk.Label(
            root,
            text=f"Startup failed:\n{message}",
            fg="#e07b7b",
            bg="#12161f",
            font=("DejaVu Sans", 9),
            wraplength=300,
            justify="left",
        ).pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        root.update()
        root.mainloop()
    except Exception:
        pass


if __name__ == "__main__":
    main()
