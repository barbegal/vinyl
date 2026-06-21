from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Optional

from src.boot_timing import log_milestone
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

if TYPE_CHECKING:
    from src.audio.input_listener import AudioInputListener
    from src.boot_debug_ui import BootDebugPanel
    from src.cast.group_discovery import CastGroupDiscovery, CastTarget
    from src.cast.stream_controller import ChromecastStreamController


class FullscreenApp:
    def __init__(
        self,
        settings: AppSettings,
        root: Optional[tk.Tk] = None,
        boot_debug: Optional["BootDebugPanel"] = None,
    ) -> None:
        self.settings = settings
        self._screen_w = settings.screen_width
        self._screen_h = settings.screen_height
        self._list_width = self._screen_w // 2

        self.root = root or tk.Tk()

        self.listener: Optional[AudioInputListener] = None
        self.discovery: Optional[CastGroupDiscovery] = None
        self.controller: Optional[ChromecastStreamController] = None
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
        # Plate button hint strip — aligned with the physical shield column.
        # 4 buttons (GPIO 17/22/23/27) → 4 evenly spaced icons, top to bottom.
        self._hint_strip_w = 26
        self._plate_hint_slots = (0, 1, 2, 3)
        self._plate_hint_labels = ("↑", "↓", "↻", "OK")
        self._plate_on_left = settings.plate_buttons_side == "left"

        self._boot_debug = boot_debug
        self._network_poll_id: str | None = None
        self._startup_done = False

        self.root.title("Pi Audio Cast Display")
        self.root.configure(bg="#0a0c12")
        self._apply_fullscreen_window()

        self._build_layout()
        self._bind_events()
        self._show_main_ui()
        log_milestone("tk window built")

    def _apply_fullscreen_window(self) -> None:
        """Pin the Tk root to the full PiTFT — bare startx has no window manager."""
        self.root.geometry(f"{self._screen_w}x{self._screen_h}+0+0")
        self.root.minsize(self._screen_w, self._screen_h)
        self.root.maxsize(self._screen_w, self._screen_h)
        if self.settings.fullscreen:
            self.root.attributes("-fullscreen", True)
        self.root.overrideredirect(True)
        self.root.update_idletasks()
        self.root.geometry(f"{self._screen_w}x{self._screen_h}+0+0")

    def _ensure_input_focus(self) -> None:
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.focus_set()
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass

    def _show_main_ui(self) -> None:
        """Drop boot overlay and show the cast shell immediately."""
        if self._boot_debug is not None:
            self._boot_debug.log("Main UI visible")
            self._boot_debug.detach()
            self._boot_debug = None
        self._set_subtitle("Starting…")
        self.root.update_idletasks()
        self.root.update()
        self._ensure_input_focus()

    def _ensure_audio(self) -> None:
        if self.listener is not None:
            return

        from src.audio.input_listener import AudioInputListener

        self.listener = AudioInputListener(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            block_size=self.settings.block_size,
            preferred_device_name=self.settings.input_device_name,
        )

    def _ensure_cast(self) -> None:
        if self.discovery is not None and self.controller is not None:
            return

        from src.cast.group_discovery import CastGroupDiscovery
        from src.cast.stream_controller import ChromecastStreamController

        if self.discovery is None:
            self.discovery = CastGroupDiscovery(
                groups_only=self.settings.groups_only,
                discovery_timeout=self.settings.cast_discovery_timeout,
                known_hosts=self.settings.cast_known_hosts,
            )
        if self.controller is None:
            self.controller = ChromecastStreamController(settings=self.settings)

    def _ensure_cast_stack(self) -> None:
        self._ensure_audio()
        self._ensure_cast()

    def _content_layout(self) -> dict[str, int]:
        """Speaker list, bars, and plate hints — mirrored when buttons are on the left."""
        hint_w = self._hint_strip_w
        list_w = self._list_width
        bars_w = self._screen_w - list_w - hint_w
        if self._plate_on_left:
            return {
                "hint_x": 0,
                "bars_x": hint_w,
                "bars_w": bars_w,
                "list_x": hint_w + bars_w,
                "list_w": list_w,
            }
        return {
            "hint_x": self._screen_w - hint_w,
            "bars_x": list_w,
            "bars_w": bars_w,
            "list_x": 0,
            "list_w": list_w,
        }

    def _build_layout(self) -> None:
        content_h = self._screen_h - self._header_h
        layout = self._content_layout()

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

        self.list_panel = tk.Frame(
            self.root,
            bg=PANEL_BG,
            width=layout["list_w"],
            height=content_h,
            highlightthickness=0,
        )
        self.list_panel.place(
            x=layout["list_x"],
            y=self._header_h,
            width=layout["list_w"],
            height=content_h,
        )
        self.list_panel.pack_propagate(False)

        self.targets_frame = tk.Frame(self.list_panel, bg=PANEL_BG)
        self.targets_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.bars = AudioBarsWidget(
            self.root,
            width=layout["bars_w"],
            height=content_h,
        )
        self.bars.place(
            x=layout["bars_x"],
            y=self._header_h,
            width=layout["bars_w"],
            height=content_h,
        )

        self._build_plate_button_hints(content_h, layout["hint_x"])

    def _build_plate_button_hints(self, content_h: int, hint_x: int) -> None:
        """Labels along the plate button column (left or right per rotation)."""
        hint_font = material_font(11, weight="bold")
        slot_count = len(self._plate_hint_slots)  # Adafruit plate: 4 buttons
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
            ).place(
                x=hint_x,
                y=y,
                width=self._hint_strip_w,
                height=int(slot_h),
            )

    def _bind_events(self) -> None:
        self.root.bind("<Escape>", lambda _e: self.shutdown())
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._bind_pitft_keys()

    def _bind_pitft_keys(self) -> None:
        """PiTFT plate buttons (gpio-keys) and keyboard equivalents."""
        bindings = {
            "<Up>": lambda _e: self._scroll_focus(-1),
            "<Down>": lambda _e: self._scroll_focus(1),
            "<Return>": lambda _e: self._select_focused(),
            "<KP_Enter>": lambda _e: self._select_focused(),
            "<Left>": lambda _e: self.refresh_targets(),
            "<KP_Left>": lambda _e: self.refresh_targets(),
            "<F5>": lambda _e: self.refresh_targets(),
        }
        for seq, handler in bindings.items():
            self.root.bind_all(seq, handler, add="+")

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

        self._ensure_cast_stack()

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
        if (
            self.discovery is not None
            and self.discovery.last_error
            and not self.targets
        ):
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
        from src.network_status import is_lan_ready, network_status_line

        if not is_lan_ready():
            self._set_subtitle(network_status_line())
            return

        self._ensure_cast()
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

        self._ensure_cast_stack()
        self._set_subtitle("Connecting...")
        self.root.update_idletasks()

        import threading

        threading.Thread(
            target=self._start_cast_worker,
            args=(index,),
            daemon=True,
        ).start()

    def _start_cast_worker(self, index: int) -> None:
        target = self.targets[index]
        try:
            fresh_info = self.discovery.fresh_cast_info(target)
            ok = self.controller.start_stream(
                target,
                zconf=self.discovery.zconf,
                cast_info=fresh_info,
            )
            status = self.controller.status
        except Exception as exc:
            ok = False
            status = None
            err = str(exc)

            def _fail() -> None:
                self._active_uuid = None
                self._apply_target_styles()
                self._set_subtitle(err, ERROR)

            self.root.after(0, _fail)
            return

        def _done() -> None:
            if ok:
                self._active_uuid = target.uuid
                self._apply_target_styles()
                self._set_subtitle(f"Playing on {status.target_name}", SUCCESS_FG)
            else:
                self._active_uuid = None
                self._apply_target_styles()
                self._set_subtitle(status.message, ERROR)

        self.root.after(0, _done)

    def stop_cast(self) -> None:
        if self.controller is not None:
            self.controller.stop_stream()
        self._active_uuid = None
        self._apply_target_styles()
        if self.targets:
            self._set_subtitle("Tap to play · ↑↓ scroll · ← refresh · Enter select")
        else:
            self._set_subtitle("Stopped")

    def _update_audio_ui(self) -> None:
        rms_linear = 0.0
        peak_linear = 0.0
        if self.listener is not None:
            snapshot = self.listener.get_latest_snapshot()
            rms_linear = snapshot.levels.rms_linear
            peak_linear = snapshot.levels.peak_linear
        self.bars.update_levels(
            rms_linear=rms_linear,
            peak_linear=peak_linear,
        )
        self.root.after(80, self._update_audio_ui)

    def run(self) -> None:
        log_milestone("ui visible on tft")
        self._update_audio_ui()
        self.root.after(50, self._begin_background_startup)
        self.root.after(150, self._ensure_input_focus)
        self.root.mainloop()

    def _begin_background_startup(self) -> None:
        import threading

        self._set_subtitle("Loading audio…")
        threading.Thread(target=self._load_audio_worker, daemon=True).start()

    def _load_audio_worker(self) -> None:
        try:
            self._ensure_audio()
            input_ok = self.listener.start()
            error = self.listener.last_error
        except Exception as exc:
            input_ok = False
            error = str(exc)

        self.root.after(
            0,
            lambda: self._audio_startup_done(input_ok, error),
        )

    def _audio_startup_done(
        self,
        input_ok: bool,
        error: str | None,
    ) -> None:
        if error:
            self._set_subtitle(error, ERROR)
            log_milestone(f"audio err: {error}")
        elif not input_ok:
            self._set_subtitle("No audio input", ERROR)
            log_milestone("audio input unavailable")
        else:
            log_milestone("audio input ready")

        self._poll_network(0)

    def _poll_network(self, attempt: int) -> None:
        from src.network_status import is_lan_ready, network_status_line

        if self._network_poll_id is not None:
            try:
                self.root.after_cancel(self._network_poll_id)
            except Exception:
                pass
            self._network_poll_id = None

        if is_lan_ready():
            self._set_subtitle("Loading Cast…")
            import threading

            threading.Thread(target=self._load_cast_worker, daemon=True).start()
            return

        self._set_subtitle(network_status_line())
        if attempt >= 120:
            self._set_subtitle("No network — check Wi‑Fi", ERROR)
            log_milestone("network timeout")
            self._schedule_network_retry()
            return

        self._network_poll_id = self.root.after(
            1000,
            lambda: self._poll_network(attempt + 1),
        )

    def _schedule_network_retry(self) -> None:
        if self._auto_after_id is not None:
            try:
                self.root.after_cancel(self._auto_after_id)
            except Exception:
                pass
        self._auto_after_id = self.root.after(
            self._refresh_ms,
            self._retry_network_and_cast,
        )

    def _retry_network_and_cast(self) -> None:
        from src.network_status import is_lan_ready

        if is_lan_ready() and not self._startup_done:
            self._set_subtitle("Loading Cast…")
            import threading

            threading.Thread(target=self._load_cast_worker, daemon=True).start()
        else:
            self._auto_after_id = self.root.after(
                self._refresh_ms,
                self._retry_network_and_cast,
            )

    def _load_cast_worker(self) -> None:
        try:
            self._ensure_cast()
            targets = self.discovery.discover()
            error = self.discovery.last_error
        except Exception as exc:
            targets = []
            error = str(exc)

        self.root.after(
            0,
            lambda: self._cast_startup_done(targets, error),
        )

    def _cast_startup_done(
        self,
        targets: list["CastTarget"],
        error: str | None,
    ) -> None:
        self.targets = targets
        signature = self._signature(self.targets)

        if signature != self._targets_signature:
            self._targets_signature = signature
            self._rebuild_target_buttons()
            if self.targets:
                if self._focus_index is None or self._focus_index >= len(self.targets):
                    self._focus_index = 0
            else:
                self._focus_index = None

        if error:
            self._set_subtitle(error, ERROR)
            log_milestone(f"cast err: {error}")
        else:
            log_milestone(f"first cast scan ({len(self.targets)} target(s))")

        self._update_status_text()
        self._startup_done = True
        self._auto_after_id = self.root.after(self._refresh_ms, self._auto_refresh)

    def shutdown(self) -> None:
        if self._network_poll_id is not None:
            try:
                self.root.after_cancel(self._network_poll_id)
            except Exception:
                pass
            self._network_poll_id = None
        if self._auto_after_id is not None:
            try:
                self.root.after_cancel(self._auto_after_id)
            except Exception:
                pass
            self._auto_after_id = None
        if self.controller is not None:
            self.controller.stop_stream()
        if self.listener is not None:
            self.listener.stop()
        if self.discovery is not None:
            self.discovery.shutdown()
        self.root.destroy()
