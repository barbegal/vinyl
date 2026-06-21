from __future__ import annotations

import tkinter as tk

from src.audio.input_listener import AudioInputListener
from src.cast.group_discovery import CastGroupDiscovery, CastTarget
from src.cast.stream_controller import ChromecastStreamController
from src.config.settings import AppSettings
from src.display.bars_widget import AudioBarsWidget
from src.display.material_widgets import (
    ICON_FG,
    MaterialButton,
    MaterialIconButton,
    ERROR,
    ON_SURFACE_VARIANT,
    PANEL_BG,
    SUCCESS_FG,
    material_font,
)


class FullscreenApp:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._screen_w = settings.screen_width
        self._screen_h = settings.screen_height
        self._list_width = self._screen_w // 2

        self.root = tk.Tk()
        self.root.title("Pi Audio Cast Display")
        self.root.configure(bg="#0a0c12")
        self.root.geometry(f"{self._screen_w}x{self._screen_h}")
        if settings.fullscreen:
            self.root.attributes("-fullscreen", True)

        self.listener = AudioInputListener(
            sample_rate=settings.sample_rate,
            channels=settings.channels,
            block_size=settings.block_size,
            preferred_device_name=settings.input_device_name,
        )
        self.discovery = CastGroupDiscovery(
            groups_only=settings.groups_only,
            discovery_timeout=settings.cast_discovery_timeout,
            known_hosts=settings.cast_known_hosts,
        )
        self.controller = ChromecastStreamController(settings=settings)
        self.targets: list[CastTarget] = []
        self._target_buttons: list[MaterialButton] = []
        self._active_uuid: str | None = None
        self._focus_index: int | None = None
        self._targets_signature: tuple | None = None
        self._auto_after_id: str | None = None
        self._refresh_ms = max(2000, int(settings.cast_refresh_interval * 1000))

        self.subtitle_var = tk.StringVar(value="Searching for speakers…")
        self._header_h = 34
        self._top_btn_slot = 58
        # Right-edge strip aligned with PiTFT plate buttons (5 slots; 4 labeled).
        self._hint_strip_w = 26
        self._plate_hint_slots = (0, 1, 3, 4)  # skip middle (unused Right)
        self._plate_hint_labels = ("↑", "↓", "↻", "OK")

        self._build_layout()
        self._bind_events()

    def _build_layout(self) -> None:
        content_h = self._screen_h - self._header_h

        self.top_bar = tk.Frame(
            self.root,
            bg=PANEL_BG,
            width=self._screen_w,
            height=self._header_h,
            highlightthickness=0,
        )
        self.top_bar.place(x=0, y=0, width=self._screen_w, height=self._header_h)
        self.top_bar.pack_propagate(False)

        text_w = self._screen_w - self._top_btn_slot
        self.subtitle_label = tk.Label(
            self.top_bar,
            textvariable=self.subtitle_var,
            fg=ON_SURFACE_VARIANT,
            bg=PANEL_BG,
            anchor="center",
            justify="center",
            font=material_font(10, weight="bold"),
            wraplength=max(80, text_w - 8),
        )
        self.subtitle_label.place(x=4, y=0, width=text_w, height=self._header_h)

        self.refresh_btn = MaterialIconButton(
            self.top_bar,
            text="↻",
            command=self.refresh_targets,
            parent_bg=PANEL_BG,
            font_size=13,
        )
        self.refresh_btn.place(x=self._screen_w - self._top_btn_slot, y=4)

        self.exit_btn = MaterialIconButton(
            self.top_bar,
            text="✕",
            command=self.shutdown,
            parent_bg=PANEL_BG,
            fill_color="#1a2030",
            text_color=ICON_FG,
            size=26,
            font_size=11,
            is_danger=True,
        )
        self.exit_btn.place(x=self._screen_w - 30, y=4)

        self.left_panel = tk.Frame(
            self.root,
            bg=PANEL_BG,
            width=self._list_width,
            height=content_h,
            highlightthickness=0,
        )
        self.left_panel.place(x=0, y=self._header_h, width=self._list_width, height=content_h)
        self.left_panel.pack_propagate(False)

        self.targets_frame = tk.Frame(self.left_panel, bg=PANEL_BG)
        self.targets_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        bars_w = self._screen_w - self._list_width - self._hint_strip_w
        self.bars = AudioBarsWidget(self.root, width=bars_w, height=content_h)
        self.bars.place(
            x=self._list_width,
            y=self._header_h,
            width=bars_w,
            height=content_h,
        )

        self._build_plate_button_hints(content_h)

    def _build_plate_button_hints(self, content_h: int) -> None:
        """Labels on the right edge, aligned with the physical plate button column."""
        hint_font = material_font(11, weight="bold")
        slot_count = 5  # Adafruit plate: 5 buttons top-to-bottom
        x = self._screen_w - self._hint_strip_w
        slot_h = content_h / slot_count

        for slot, label in zip(self._plate_hint_slots, self._plate_hint_labels):
            y = self._header_h + int(slot * slot_h)
            tk.Label(
                self.root,
                text=label,
                fg=ON_SURFACE_VARIANT,
                bg=PANEL_BG,
                font=hint_font,
                width=2,
                anchor="center",
            ).place(x=x, y=y, width=self._hint_strip_w, height=int(slot_h))

    def _bind_events(self) -> None:
        self.root.bind("<Escape>", lambda _e: self.shutdown())
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._bind_pitft_keys()

    def _bind_pitft_keys(self) -> None:
        """PiTFT plate buttons (gpio-keys) and keyboard equivalents."""
        self.root.bind("<Up>", lambda _e: self._scroll_focus(-1))
        self.root.bind("<Down>", lambda _e: self._scroll_focus(1))
        self.root.bind("<Return>", lambda _e: self._select_focused())
        self.root.bind("<KP_Enter>", lambda _e: self._select_focused())
        self.root.bind("<Left>", lambda _e: self.refresh_targets())
        self.root.bind("<KP_Left>", lambda _e: self.refresh_targets())
        # Plate button #1 is sometimes wired differently on clones — keep F5 as refresh too.
        self.root.bind("<F5>", lambda _e: self.refresh_targets())

    def _scroll_focus(self, delta: int) -> None:
        if not self.targets:
            return
        if self._focus_index is None:
            self._focus_index = 0
        else:
            self._focus_index = max(0, min(len(self.targets) - 1, self._focus_index + delta))
        self._apply_target_styles()

    def _select_focused(self) -> None:
        if self._focus_index is not None and self._focus_index < len(self.targets):
            self._on_target_tap(self._focus_index)

    def _apply_target_styles(self) -> None:
        for idx, btn in enumerate(self._target_buttons):
            is_active = (
                self._active_uuid is not None
                and idx < len(self.targets)
                and self.targets[idx].uuid == self._active_uuid
            )
            is_focused = (
                self._focus_index is not None
                and idx == self._focus_index
            )
            btn.set_active(is_active)
            btn.set_focused(is_focused)

    def _on_target_tap(self, index: int) -> None:
        if index >= len(self.targets):
            return

        tapped_uuid = self.targets[index].uuid
        if self._active_uuid is not None and tapped_uuid == self._active_uuid:
            self.stop_cast()
            return

        if self._active_uuid is not None:
            self.controller.stop_stream()

        self._start_cast_to(index)

    def _rebuild_target_buttons(self) -> None:
        for child in self.targets_frame.winfo_children():
            child.destroy()
        self._target_buttons = []

        if not self.targets:
            tk.Label(
                self.targets_frame,
                text="No speakers found",
                fg=ON_SURFACE_VARIANT,
                bg=PANEL_BG,
                font=material_font(10, weight="bold"),
                anchor="center",
                justify="center",
            ).pack(fill=tk.BOTH, expand=True)
            return

        for index, target in enumerate(self.targets):
            label = target.name
            if target.is_group:
                label = f"{label}  ·  group"
            btn = MaterialButton(
                self.targets_frame,
                text=label,
                command=lambda i=index: self._on_target_tap(i),
                parent_bg=PANEL_BG,
                font_size=11,
                radius=12,
            )
            btn.pack(fill=tk.BOTH, expand=True, pady=2)
            self._target_buttons.append(btn)

        self._apply_target_styles()

    def _set_subtitle(self, text: str, color: str = ON_SURFACE_VARIANT) -> None:
        self.subtitle_var.set(text)
        self.subtitle_label.configure(fg=color)

    @staticmethod
    def _signature(targets: list[CastTarget]) -> tuple:
        return tuple((t.uuid, t.name, t.is_group) for t in targets)

    def _active_target_name(self) -> str | None:
        for target in self.targets:
            if target.uuid == self._active_uuid:
                return target.name
        return None

    def _update_status_text(self) -> None:
        if self.discovery.last_error and not self.targets:
            self._set_subtitle(self.discovery.last_error, ERROR)
            return
        active_name = self._active_target_name()
        if active_name is not None:
            self._set_subtitle(f"Playing on {active_name}", SUCCESS_FG)
        elif self.targets:
            self._set_subtitle("Tap or plate buttons")
        else:
            self._set_subtitle("Searching for speakers…")

    def refresh_targets(self, announce: bool = True) -> None:
        if announce:
            self._set_subtitle("Scanning…")

        self.targets = self.discovery.discover()
        signature = self._signature(self.targets)

        if signature != self._targets_signature:
            self._targets_signature = signature
            self._rebuild_target_buttons()
            if self.targets:
                if self._focus_index is None or self._focus_index >= len(self.targets):
                    self._focus_index = 0
            else:
                self._focus_index = None
        elif self.targets and self._focus_index is not None:
            self._focus_index = min(self._focus_index, len(self.targets) - 1)

        # Drop active highlight if that speaker disappeared from the network.
        if self._active_uuid is not None and self._active_target_name() is None:
            self._active_uuid = None

        self._apply_target_styles()
        self._update_status_text()

    def _auto_refresh(self) -> None:
        self.refresh_targets(announce=False)
        self._auto_after_id = self.root.after(self._refresh_ms, self._auto_refresh)

    def _start_cast_to(self, index: int) -> None:
        if index >= len(self.targets):
            return

        self._set_subtitle("Connecting...")
        self.root.update_idletasks()

        target = self.targets[index]
        fresh_info = self.discovery.fresh_cast_info(target)
        ok = self.controller.start_stream(
            target,
            zconf=self.discovery.zconf,
            cast_info=fresh_info,
        )
        status = self.controller.status
        if ok:
            self._active_uuid = target.uuid
            self._apply_target_styles()
            self._set_subtitle(f"Playing on {status.target_name}", SUCCESS_FG)
        else:
            self._active_uuid = None
            self._apply_target_styles()
            self._set_subtitle(status.message, ERROR)

    def stop_cast(self) -> None:
        self.controller.stop_stream()
        self._active_uuid = None
        self._apply_target_styles()
        if self.targets:
            self._set_subtitle("Tap to play · ↑↓ scroll · ← refresh · Enter select")
        else:
            self._set_subtitle("Stopped")

    def _update_audio_ui(self) -> None:
        snapshot = self.listener.get_latest_snapshot()
        self.bars.update_levels(
            rms_linear=snapshot.levels.rms_linear,
            peak_linear=snapshot.levels.peak_linear,
        )
        self.root.after(80, self._update_audio_ui)

    def run(self) -> None:
        input_ok = self.listener.start()
        if not input_ok and not self.listener.last_error:
            self._set_subtitle("No audio input", ERROR)

        # First scan is quick (the browser is still warming up); the periodic
        # auto-refresh keeps filling the list as more speakers respond.
        self.refresh_targets(announce=False)
        self._auto_after_id = self.root.after(self._refresh_ms, self._auto_refresh)
        self._update_audio_ui()
        self.root.mainloop()

    def shutdown(self) -> None:
        if self._auto_after_id is not None:
            try:
                self.root.after_cancel(self._auto_after_id)
            except Exception:
                pass
            self._auto_after_id = None
        self.controller.stop_stream()
        self.listener.stop()
        self.discovery.shutdown()
        self.root.destroy()
