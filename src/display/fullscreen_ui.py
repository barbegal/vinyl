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
    ON_ERROR_CONTAINER,
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
        self._active_index: int | None = None

        self.subtitle_var = tk.StringVar(value="Starting...")

        self._build_layout()
        self._bind_events()

    def _build_layout(self) -> None:
        self.left_panel = tk.Frame(
            self.root,
            bg=PANEL_BG,
            width=self._list_width,
            height=self._screen_h,
            highlightthickness=0,
        )
        self.left_panel.place(x=0, y=0, width=self._list_width, height=self._screen_h)
        self.left_panel.pack_propagate(False)

        header = tk.Frame(self.left_panel, bg=PANEL_BG, height=30)
        header.pack(fill=tk.X, padx=4, pady=(6, 4))
        header.pack_propagate(False)

        self.subtitle_label = tk.Label(
            header,
            textvariable=self.subtitle_var,
            fg=ON_SURFACE_VARIANT,
            bg=PANEL_BG,
            anchor="center",
            justify="center",
            font=material_font(9, weight="bold"),
        )
        self.subtitle_label.place(relx=0.5, rely=0.5, anchor="center")

        self.refresh_btn = MaterialIconButton(
            header,
            text="↻",
            command=self.refresh_targets,
            parent_bg=PANEL_BG,
            font_size=13,
        )
        self.refresh_btn.place(x=self._list_width - 36, y=2)

        self.targets_frame = tk.Frame(self.left_panel, bg=PANEL_BG)
        self.targets_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        bars_w = self._screen_w - self._list_width
        self.bars = AudioBarsWidget(self.root, width=bars_w, height=self._screen_h)
        self.bars.place(
            x=self._list_width,
            y=0,
            width=bars_w,
            height=self._screen_h,
        )

        self.exit_btn = MaterialIconButton(
            self.root,
            text="✕",
            command=self.shutdown,
            parent_bg="#0a0c12",
            fill_color="#141820",
            text_color=ICON_FG,
            size=26,
            font_size=11,
            is_danger=True,
        )
        self.exit_btn.place(x=self._screen_w - 28, y=4)

    def _bind_events(self) -> None:
        self.root.bind("<Escape>", lambda _e: self.shutdown())
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    def _apply_target_styles(self) -> None:
        for idx, btn in enumerate(self._target_buttons):
            btn.set_active(self._active_index is not None and idx == self._active_index)

    def _on_target_tap(self, index: int) -> None:
        if index >= len(self.targets):
            return

        if self._active_index is not None and index == self._active_index:
            self.stop_cast()
            return

        if self._active_index is not None:
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

    def refresh_targets(self) -> None:
        was_active = self._active_index
        self._set_subtitle("Scanning...")

        self.targets = self.discovery.discover()
        self._rebuild_target_buttons()

        if self.discovery.last_error:
            self._set_subtitle(self.discovery.last_error, ON_ERROR_CONTAINER)
            self._active_index = None
        elif self.targets:
            if was_active is not None and was_active < len(self.targets):
                self._active_index = was_active
            self._apply_target_styles()
            if self._active_index is not None:
                self._set_subtitle(
                    f"Playing on {self.targets[self._active_index].name}",
                    SUCCESS_FG,
                )
            else:
                self._set_subtitle("Tap to play")
        else:
            self._set_subtitle("Tap ↻ to scan")
            self._active_index = None

    def _start_cast_to(self, index: int) -> None:
        if index >= len(self.targets):
            return

        self._set_subtitle("Connecting...")
        self.root.update_idletasks()

        target = self.targets[index]
        ok = self.controller.start_stream(target, zconf=self.discovery.zconf)
        status = self.controller.status
        if ok:
            self._active_index = index
            self._apply_target_styles()
            self._set_subtitle(f"Playing on {status.target_name}", SUCCESS_FG)
        else:
            self._active_index = None
            self._apply_target_styles()
            self._set_subtitle(status.message, ON_ERROR_CONTAINER)

    def stop_cast(self) -> None:
        self.controller.stop_stream()
        self._active_index = None
        self._apply_target_styles()
        if self.targets:
            self._set_subtitle("Tap to play")
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
            self._set_subtitle("No audio input", ON_ERROR_CONTAINER)

        self.refresh_targets()
        self._update_audio_ui()
        self.root.mainloop()

    def shutdown(self) -> None:
        self.controller.stop_stream()
        self.listener.stop()
        self.discovery.shutdown()
        self.root.destroy()
