from __future__ import annotations

import tkinter as tk

from src.audio.input_listener import AudioInputListener
from src.cast.group_discovery import CastGroupDiscovery, CastTarget
from src.cast.stream_controller import ChromecastStreamController
from src.config.settings import AppSettings
from src.display.bars_widget import AudioBarsWidget

# Source row colors
TARGET_BG = "#181d28"
TARGET_FG = "#9aa6b8"
TARGET_ACTIVE_BG = "#2d6b4a"
TARGET_ACTIVE_FG = "#f2fff6"


class FullscreenApp:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.root = tk.Tk()
        self.root.title("Pi Audio Cast Display")
        self.root.configure(bg="#0a0c12")
        self.root.geometry(f"{settings.screen_width}x{settings.screen_height}")
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
        self._target_buttons: list[tk.Button] = []
        self._active_index: int | None = None

        self.subtitle_var = tk.StringVar(value="Starting...")

        self._build_layout()
        self._bind_events()

    def _build_layout(self) -> None:
        self.bars = AudioBarsWidget(
            self.root,
            width=self.settings.screen_width,
            height=self.settings.screen_height,
        )
        self.bars.place(x=0, y=0, relwidth=1, relheight=1)

        self.overlay = tk.Frame(self.root, bg="#12161f", highlightthickness=0)
        self.overlay.place(x=0, rely=1, anchor="sw", width=self.settings.screen_width)

        header = tk.Frame(self.overlay, bg="#12161f")
        header.pack(fill=tk.X, padx=10, pady=(6, 2))

        self.subtitle_label = tk.Label(
            header,
            textvariable=self.subtitle_var,
            fg="#8b95a8",
            bg="#12161f",
            anchor="w",
            font=("Helvetica", 9),
        )
        self.subtitle_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.refresh_btn = tk.Button(
            header,
            text="Refresh",
            command=self.refresh_targets,
            bg="#12161f",
            fg="#6b7a90",
            activebackground="#1a2030",
            activeforeground="#c8d0de",
            relief=tk.FLAT,
            borderwidth=0,
            font=("Helvetica", 9),
            cursor="hand2",
        )
        self.refresh_btn.pack(side=tk.RIGHT)

        self.targets_frame = tk.Frame(self.overlay, bg="#12161f")
        self.targets_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

    def _bind_events(self) -> None:
        self.root.bind("<Escape>", lambda _e: self.shutdown())
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    def _apply_target_styles(self) -> None:
        for idx, btn in enumerate(self._target_buttons):
            if self._active_index is not None and idx == self._active_index:
                btn.configure(bg=TARGET_ACTIVE_BG, fg=TARGET_ACTIVE_FG)
            else:
                btn.configure(bg=TARGET_BG, fg=TARGET_FG)

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
                fg="#6b7a90",
                bg="#12161f",
                font=("Helvetica", 10),
            ).pack(fill=tk.X, pady=4)
            return

        for index, target in enumerate(self.targets[:4]):
            label = target.name
            if target.is_group:
                label = f"{label}  ·  group"
            btn = tk.Button(
                self.targets_frame,
                text=label,
                command=lambda i=index: self._on_target_tap(i),
                bg=TARGET_BG,
                fg=TARGET_FG,
                activebackground=TARGET_ACTIVE_BG,
                activeforeground=TARGET_ACTIVE_FG,
                relief=tk.FLAT,
                borderwidth=0,
                font=("Helvetica", 11),
                anchor="w",
                padx=10,
                pady=8,
                cursor="hand2",
            )
            btn.pack(fill=tk.X, pady=2)
            self._target_buttons.append(btn)

        self._apply_target_styles()

    def refresh_targets(self) -> None:
        was_active = self._active_index
        self.subtitle_var.set("Scanning network...")
        self.subtitle_label.configure(fg="#8b95a8")
        self.root.update_idletasks()

        self.targets = self.discovery.discover()
        self._rebuild_target_buttons()

        if self.discovery.last_error:
            self.subtitle_var.set(self.discovery.last_error)
            self.subtitle_label.configure(fg="#c97a7a")
            self._active_index = None
        elif self.targets:
            if was_active is not None and was_active < len(self.targets):
                self._active_index = was_active
            self._apply_target_styles()
            if self._active_index is not None:
                self.subtitle_label.configure(fg="#7ec99a")
                self.subtitle_var.set(f"Playing on {self.targets[self._active_index].name}")
            else:
                self.subtitle_label.configure(fg="#8b95a8")
                self.subtitle_var.set("Tap a speaker to play")
        else:
            self.subtitle_label.configure(fg="#8b95a8")
            self.subtitle_var.set("Tap Refresh to find speakers")
            self._active_index = None

    def _start_cast_to(self, index: int) -> None:
        if index >= len(self.targets):
            return

        target = self.targets[index]
        self.subtitle_var.set(f"Connecting to {target.name}...")
        self.subtitle_label.configure(fg="#8b95a8")
        self.root.update_idletasks()

        ok = self.controller.start_stream(target, zconf=self.discovery.zconf)
        status = self.controller.status
        if ok:
            self._active_index = index
            self._apply_target_styles()
            self.subtitle_label.configure(fg="#7ec99a")
            self.subtitle_var.set(f"Playing on {status.target_name}")
        else:
            self._active_index = None
            self._apply_target_styles()
            self.subtitle_label.configure(fg="#c97a7a")
            self.subtitle_var.set(status.message)

    def stop_cast(self) -> None:
        self.controller.stop_stream()
        self._active_index = None
        self._apply_target_styles()
        self.subtitle_label.configure(fg="#8b95a8")
        if self.targets:
            self.subtitle_var.set("Tap a speaker to play")
        else:
            self.subtitle_var.set("Stopped")

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
            self.subtitle_label.configure(fg="#c97a7a")
            self.subtitle_var.set("No audio input")

        self.refresh_targets()
        self._update_audio_ui()
        self.root.mainloop()

    def shutdown(self) -> None:
        self.controller.stop_stream()
        self.listener.stop()
        self.discovery.shutdown()
        self.root.destroy()
