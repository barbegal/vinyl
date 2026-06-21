"""Material Design 3–inspired widgets for Tkinter."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from pathlib import Path
from typing import Optional

# MD3 dark palette
PANEL_BG = "#12161f"
SURFACE = "#1a2030"
SURFACE_HIGH = "#232a3a"
ON_SURFACE = "#eef2f8"
ON_SURFACE_VARIANT = "#9aa6b8"
PRIMARY = "#3d8f62"
PRIMARY_CONTAINER = "#2d6b4a"
ON_PRIMARY = "#ffffff"
SUCCESS_FG = "#6ecf94"
OUTLINE = "#3d4658"
ERROR = "#e07b7b"
ON_ERROR_CONTAINER = "#c97a7a"
ICON_FG = "#8b95a8"
ICON_HOVER = "#c8d0de"

_FONT_FILES_REGULAR = [
    "/usr/share/fonts/truetype/roboto/unhinted/Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Roboto-Regular.ttf",
    "/Library/Fonts/Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

_FONT_FILES_BOLD = [
    "/usr/share/fonts/truetype/roboto/unhinted/Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Roboto-Bold.ttf",
    "/Library/Fonts/Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

_FONT_FAMILIES_REGULAR = ("Roboto", "Inter", "Segoe UI", "DejaVu Sans", "Helvetica Neue", "Arial")
_FONT_FAMILIES_BOLD = ("Roboto", "Inter", "Segoe UI Semibold", "DejaVu Sans", "Helvetica Neue", "Arial")


def material_font(size: int, weight: str = "normal") -> tkfont.Font:
    bold = weight in ("medium", "bold")
    file_candidates = _FONT_FILES_BOLD if bold else _FONT_FILES_REGULAR
    for path in file_candidates:
        if Path(path).is_file():
            try:
                return tkfont.Font(file=path, size=size)
            except tk.TclError:
                continue

    tk_weight = "bold" if bold else "normal"
    families = _FONT_FAMILIES_BOLD if bold else _FONT_FAMILIES_REGULAR
    for family in families:
        try:
            font = tkfont.Font(family=family, size=size, weight=tk_weight)
            actual = font.actual("family").lower()
            if family.lower().split()[0] in actual or actual not in ("tkdefaultfont", "fixed"):
                return font
        except tk.TclError:
            continue
    return tkfont.Font(size=size, weight=tk_weight)


def _draw_round_rect(
    canvas: tk.Canvas,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    radius: int,
    fill: str,
) -> None:
    r = min(radius, (x1 - x0) // 2, (y1 - y0) // 2)
    if r <= 0:
        canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="")
        return
    canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline="")
    canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline="")
    canvas.create_arc(x0, y0, x0 + 2 * r, y0 + 2 * r, start=90, extent=90, fill=fill, outline="")
    canvas.create_arc(x1 - 2 * r, y0, x1, y0 + 2 * r, start=0, extent=90, fill=fill, outline="")
    canvas.create_arc(x0, y1 - 2 * r, x0 + 2 * r, y1, start=180, extent=90, fill=fill, outline="")
    canvas.create_arc(x1 - 2 * r, y1 - 2 * r, x1, y1, start=270, extent=90, fill=fill, outline="")


class MaterialButton(tk.Canvas):
    """Rounded button with centered bold label."""

    def __init__(
        self,
        master,
        text: str = "",
        command: Optional[Callable[[], None]] = None,
        parent_bg: str = PANEL_BG,
        fill_color: str = SURFACE,
        text_color: str = ON_SURFACE,
        hover_color: str = SURFACE_HIGH,
        active_fill: str = PRIMARY_CONTAINER,
        active_text: str = ON_PRIMARY,
        radius: int = 12,
        font_size: int = 11,
        font_weight: str = "bold",
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            highlightthickness=0,
            bd=0,
            bg=parent_bg,
            **kwargs,
        )
        self._text = text
        self._command = command
        self._fill = fill_color
        self._text_color = text_color
        self._hover = hover_color
        self._active_fill = active_fill
        self._active_text = active_text
        self._radius = radius
        self._font = material_font(font_size, weight=font_weight)
        self._is_active = False
        self._hovering = False

        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.configure(cursor="hand2")

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._redraw()

    def set_text(self, text: str) -> None:
        self._text = text
        self._redraw()

    def _current_fill(self) -> str:
        if self._is_active:
            return self._active_fill
        if self._hovering:
            return self._hover
        return self._fill

    def _current_text_color(self) -> str:
        return self._active_text if self._is_active else self._text_color

    def _on_configure(self, _event=None) -> None:
        self._redraw()

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _on_enter(self, _event=None) -> None:
        self._hovering = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hovering = False
        self._redraw()

    def _redraw(self) -> None:
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        self.delete("all")
        margin = 1
        _draw_round_rect(
            self,
            margin,
            margin,
            w - margin,
            h - margin,
            self._radius,
            self._current_fill(),
        )
        self.create_text(
            w // 2,
            h // 2,
            text=self._text,
            fill=self._current_text_color(),
            font=self._font,
            anchor="center",
        )


class MaterialIconButton(tk.Canvas):
    """Small rounded icon button (refresh, close)."""

    def __init__(
        self,
        master,
        text: str,
        command: Optional[Callable[[], None]] = None,
        size: int = 26,
        parent_bg: str = PANEL_BG,
        fill_color: str = SURFACE,
        text_color: str = ICON_FG,
        hover_color: str = SURFACE_HIGH,
        hover_text: str = ICON_HOVER,
        danger_hover: str = "#4a2830",
        danger_text: str = ERROR,
        radius: int = 8,
        font_size: int = 12,
        is_danger: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            bg=parent_bg,
            **kwargs,
        )
        self._text = text
        self._command = command
        self._size = size
        self._fill = fill_color
        self._text_color = text_color
        self._hover = hover_color
        self._hover_text = hover_text
        self._danger_hover = danger_hover
        self._danger_text = danger_text
        self._radius = radius
        self._font = material_font(font_size, weight="bold")
        self._is_danger = is_danger
        self._hovering = False

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.configure(cursor="hand2")
        self._redraw()

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _on_enter(self, _event=None) -> None:
        self._hovering = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hovering = False
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        s = self._size
        if self._hovering:
            fill = self._danger_hover if self._is_danger else self._hover
            fg = self._danger_text if self._is_danger else self._hover_text
        else:
            fill = self._fill
            fg = self._text_color
        _draw_round_rect(self, 1, 1, s - 1, s - 1, self._radius, fill)
        self.create_text(s // 2, s // 2, text=self._text, fill=fg, font=self._font, anchor="center")
