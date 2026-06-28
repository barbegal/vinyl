from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable, Optional

from src.boot_timing import log_milestone
from src.config.settings import AppSettings
from src.display.bars_widget import AudioBarsWidget
from src.display.material_widgets import (
    ICON_FG,
    PRIMARY,
    PRIMARY_CONTAINER,
    ON_PRIMARY,
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
        self._list_row_h = 36
        self._auto_after_id: str | None = None
        self._refresh_ms = max(2000, int(settings.cast_refresh_interval * 1000))

        self.subtitle_var = tk.StringVar(value="Select source")
        # Plain mirrors of the status line so the web server can read it off-thread
        # (Tk variables are not safe to touch from the HTTP worker threads).
        self._status_text = "Select source"
        self._status_color = ON_SURFACE_VARIANT
        self.web = None
        self._header_h = 34
        self._top_btn_slot = 58
        self._idle_subtitle = "Select source"
        # Plate button hint strip — aligned with the physical shield column.
        # 4 buttons (GPIO 17/22/23/27) → 4 evenly spaced icons, top to bottom.
        self._hint_strip_w = 26
        self._plate_hint_slots = (0, 1, 2, 3)
        self._plate_hint_labels = ("↑", "↓", "↻", "OK")
        self._plate_on_left = settings.plate_buttons_side == "left"
        self._plate_hint_widgets: list[tk.Label] = []
        self._pitft_keys_bound = False
        self._cast_busy = False
        self._scan_busy = False
        self._auto_cast_done = False

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
                discovery_timeout=self.settings.cast_discovery_timeout,
                known_hosts=self.settings.cast_known_hosts,
            )
        if self.controller is None:
            self.controller = ChromecastStreamController(settings=self.settings)

    def _release_audio_for_stream(self) -> None:
        """Free the USB mic so ffmpeg can capture via ALSA (one client at a time)."""
        import time

        if self.listener is not None:
            self.listener.stop()
            # PortAudio can hold /dev/snd briefly after close on Linux.
            time.sleep(0.4)

    def _resume_audio_monitor(self) -> None:
        """Restart level monitoring after cast stops."""
        if (
            self.settings.auto_cast_targets
            and not self._auto_cast_done
            and self._active_uuid is None
        ):
            # Auto-cast will retry — keep ALSA free for ffmpeg.
            return
        if self.listener is None:
            return
        if self.listener.start():
            return
        err = self.listener.last_error
        if err and self._active_uuid is None and not self._cast_busy:
            self._set_subtitle(err, ERROR)

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

        self._list_canvas = tk.Canvas(
            self.list_panel,
            bg=PANEL_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        self._list_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.targets_frame = tk.Frame(self._list_canvas, bg=PANEL_BG)
        self._list_canvas.create_window(
            (0, 0),
            window=self.targets_frame,
            anchor="nw",
            width=max(80, layout["list_w"] - 8),
        )
        self.targets_frame.bind(
            "<Configure>",
            lambda _e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all"),
            ),
        )

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
        self._plate_hint_widgets = []
        hint_font = material_font(11, weight="bold")
        slot_count = len(self._plate_hint_slots)  # Adafruit plate: 4 buttons
        slot_h = content_h / slot_count

        for slot, label in zip(self._plate_hint_slots, self._plate_hint_labels):
            y = self._header_h + int(slot * slot_h)
            widget = tk.Label(
                self.root,
                text=label,
                fg=ON_SURFACE_VARIANT,
                bg=PANEL_BG,
                font=hint_font,
                width=2,
                anchor="center",
            )
            widget.place(
                x=hint_x,
                y=y,
                width=self._hint_strip_w,
                height=int(slot_h),
            )
            self._plate_hint_widgets.append(widget)

    def _flash_plate_hint(self, slot: int) -> None:
        if slot < 0 or slot >= len(self._plate_hint_widgets):
            return
        widget = self._plate_hint_widgets[slot]
        widget.configure(fg=ON_PRIMARY, bg=PRIMARY_CONTAINER)
        self.root.after(
            180,
            lambda w=widget: w.configure(fg=ON_SURFACE_VARIANT, bg=PANEL_BG),
        )

    def _bind_events(self) -> None:
        if self._pitft_keys_bound:
            return
        self._pitft_keys_bound = True
        self.root.bind("<Escape>", lambda _e: self.shutdown())
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._bind_pitft_keys()
        self.root.bind_all("<Button-1>", self._on_screen_tap, add="+")

    def _bind_pitft_keys(self) -> None:
        """PiTFT plate buttons (gpio-keys) and keyboard equivalents."""
        bindings: dict[str, tuple[int, Callable[[], None]]] = {
            "<Up>": (0, lambda: self._scroll_focus(-1)),
            "<Down>": (1, lambda: self._scroll_focus(1)),
            "<Return>": (3, self._select_focused),
            "<KP_Enter>": (3, self._select_focused),
            "<Left>": (2, self.refresh_targets),
            "<KP_Left>": (2, self.refresh_targets),
            "<F5>": (2, self.refresh_targets),
        }
        for seq, (slot, action) in bindings.items():
            self.root.bind_all(
                seq,
                lambda _e, s=slot, fn=action: self._plate_action(s, fn),
                add="+",
            )

    def _plate_action(self, hint_slot: int, action: Callable[[], None]) -> None:
        self._flash_plate_hint(hint_slot)
        action()

    def _on_screen_tap(self, event: tk.Event) -> None:
        """Fallback tap handler when touch events miss individual widgets."""
        widget = event.widget
        if isinstance(widget, (MaterialButton, MaterialIconButton)):
            return

        x = event.x
        y = event.y
        if y < self._header_h:
            refresh_x = self._screen_w - self._top_btn_slot
            if x >= refresh_x:
                self._flash_plate_hint(2)
                self.refresh_targets()
            return

        layout = self._content_layout()
        list_x = layout["list_x"]
        list_w = layout["list_w"]
        if list_x <= x < list_x + list_w and self.targets:
            content_h = self._screen_h - self._header_h
            rel_y = y - self._header_h
            idx = int((rel_y / max(1, content_h)) * len(self.targets))
            idx = max(0, min(len(self.targets) - 1, idx))
            self._on_target_tap(idx)
            return

        hint_x = layout["hint_x"]
        if hint_x <= x < hint_x + self._hint_strip_w:
            content_h = self._screen_h - self._header_h
            rel_y = y - self._header_h
            slot = int((rel_y / max(1, content_h)) * len(self._plate_hint_slots))
            slot = max(0, min(len(self._plate_hint_slots) - 1, slot))
            self._flash_plate_hint(slot)
            if slot == 0:
                self._scroll_focus(-1)
            elif slot == 1:
                self._scroll_focus(1)
            elif slot == 2:
                self.refresh_targets()
            else:
                self._select_focused()

    def _scroll_focus(self, delta: int) -> None:
        if not self.targets:
            return
        if self._focus_index is None:
            self._focus_index = 0
        else:
            self._focus_index = max(0, min(len(self.targets) - 1, self._focus_index + delta))
        self._apply_target_styles()
        self._scroll_focused_into_view()

    def _scroll_focused_into_view(self) -> None:
        if self._focus_index is None or self._focus_index >= len(self._target_buttons):
            return
        btn = self._target_buttons[self._focus_index]
        self.targets_frame.update_idletasks()
        self._list_canvas.update_idletasks()
        canvas_h = max(1, self._list_canvas.winfo_height())
        total_h = max(canvas_h, self.targets_frame.winfo_reqheight())
        y0 = btn.winfo_y()
        y1 = y0 + btn.winfo_height()
        top = self._list_canvas.canvasy(0)
        bottom = top + canvas_h
        if y0 < top:
            self._list_canvas.yview_moveto(y0 / total_h)
        elif y1 > bottom:
            self._list_canvas.yview_moveto(max(0.0, (y1 - canvas_h) / total_h))

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
        if self._cast_busy:
            self._post_status("Still connecting…")
            return

        self._cast_busy = True
        target = self.targets[index]
        self._post_status(f"Connecting to {target.name}…")

        import threading

        threading.Thread(
            target=self._tap_worker,
            args=(index,),
            daemon=True,
        ).start()

    def _tap_worker(self, index: int) -> None:
        try:
            self._ensure_cast_stack()
            tapped_uuid = self.targets[index].uuid

            if self._active_uuid is not None and tapped_uuid == self._active_uuid:
                if self.controller is not None:
                    self.controller.stop_stream()
                self.root.after(0, self._finish_stop_cast_ui)
                return

            if self._active_uuid is not None and self.controller is not None:
                self.controller.stop_stream()

            self._release_audio_for_stream()
            target = self.targets[index]
            fresh_info = self.discovery.fresh_cast_info(target)
            ok = self.controller.start_stream(
                target,
                zconf=self.discovery.zconf,
                cast_info=fresh_info,
                on_status=self._post_status,
            )
            status = self.controller.status
            self.root.after(0, lambda: self._finish_cast_ui(index, ok, status))
        except Exception as exc:
            err = str(exc)
            self.root.after(0, lambda: self._finish_cast_error(err))

    def _finish_cast_ui(self, index: int, ok: bool, status) -> None:
        self._cast_busy = False
        target = self.targets[index]
        if ok:
            self._active_uuid = target.uuid
            self._auto_cast_done = True
            self._apply_target_styles()
            self._set_subtitle(f"Playing on {status.target_name}", SUCCESS_FG)
        else:
            self._active_uuid = None
            self._apply_target_styles()
            msg = status.message if status and status.message else "Cast failed — tap ↻"
            self._set_subtitle(msg, ERROR)
            log_milestone(f"cast connect failed: {msg}")
            self._resume_audio_monitor()

    def _finish_cast_error(self, err: str) -> None:
        self._cast_busy = False
        self._active_uuid = None
        self._apply_target_styles()
        self._set_subtitle(err, ERROR)
        self._resume_audio_monitor()

    def _finish_stop_cast_ui(self) -> None:
        self._cast_busy = False
        self._active_uuid = None
        self._apply_target_styles()
        self._set_subtitle(self._idle_subtitle if self.targets else "No speakers — tap ↻")
        self._resume_audio_monitor()

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
                height=self._list_row_h,
            )
            btn.pack(fill=tk.X, pady=2)
            self._target_buttons.append(btn)

        self._apply_target_styles()
        self.targets_frame.update_idletasks()
        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))
        self._scroll_focused_into_view()

    def _set_subtitle(self, text: str, color: str = ON_SURFACE_VARIANT) -> None:
        self.subtitle_var.set(text)
        self.subtitle_label.configure(fg=color)
        self._status_text = text
        self._status_color = color

    def _post_status(self, text: str, color: str = ON_SURFACE_VARIANT) -> None:
        """Thread-safe status line — schedules Tk update, never blocks mainloop."""
        self.root.after(0, lambda t=text, c=color: self._set_subtitle(t, c))

    @staticmethod
    def _signature(targets: list[CastTarget]) -> tuple:
        return tuple((t.uuid, t.name, t.is_group) for t in targets)

    def _active_target_name(self) -> str | None:
        for target in self.targets:
            if target.uuid == self._active_uuid:
                return target.name
        return None

    def _update_status_text(self) -> None:
        if self._cast_busy:
            # A connect is in flight; its own status messages take precedence.
            return
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
        elif self._auto_cast_waiting():
            self._set_subtitle(self._auto_cast_wait_text())
        elif self.targets:
            count = len(self.targets)
            if count == 1:
                self._set_subtitle(self._idle_subtitle)
            else:
                self._set_subtitle(f"{count} speakers — tap to cast")
        else:
            self._set_subtitle("Scanning…")

    def _preferred_target_index(self) -> int | None:
        from src.cast.group_discovery import select_preferred_target

        if not self.settings.auto_cast_targets:
            return None
        names = [target.name for target in self.targets]
        return select_preferred_target(names, self.settings.auto_cast_targets)

    def _auto_cast_waiting(self) -> bool:
        """True while we still want to auto-connect but no preferred speaker is up."""
        return (
            bool(self.settings.auto_cast_targets)
            and not self._auto_cast_done
            and self._active_uuid is None
            and not self._cast_busy
            and self._preferred_target_index() is None
        )

    def _auto_cast_wait_text(self) -> str:
        names = " / ".join(self.settings.auto_cast_targets)
        return f"Waiting for {names}…"

    def _maybe_auto_cast(self) -> None:
        """Auto-connect to the first available preferred speaker, once per boot."""
        if not self.settings.auto_cast_targets:
            return
        if self._auto_cast_done or self._cast_busy:
            return
        if self._active_uuid is not None:
            # Already streaming (auto or manual) — don't override the user.
            self._auto_cast_done = True
            return
        index = self._preferred_target_index()
        if index is None:
            return  # keep waiting; the next scan will try again
        log_milestone(f"auto-cast → {self.targets[index].name}")
        self._on_target_tap(index)

    def refresh_targets(self, announce: bool = True) -> None:
        from src.network_status import is_lan_ready, network_status_line

        if not is_lan_ready():
            self._set_subtitle(network_status_line())
            return

        self._ensure_cast()
        if announce:
            if self._scan_busy:
                self._post_status("Still scanning…")
                return
            self._post_status("Scanning…")
            self._scan_busy = True
            import threading

            threading.Thread(
                target=self._refresh_worker,
                daemon=True,
            ).start()
            return

        self._apply_refresh_targets(
            self.discovery.discover(wait_seconds=1.0),
            merge=True,
        )

    def _refresh_worker(self) -> None:
        import time

        deadline = time.time() + self.settings.cast_discovery_timeout
        best: list["CastTarget"] = []
        try:
            while time.time() < deadline:
                current = self.discovery.discover(wait_seconds=0.0)
                if len(current) > len(best):
                    best = list(current)
                count = len(best)
                self._post_status(f"Scanning… ({count} found)")
                time.sleep(0.4)
            if not best:
                best = self.discovery.discover(wait_seconds=0.0)
        except Exception:
            best = []
        self.root.after(0, lambda t=best: self._finish_refresh(t))

    def _finish_refresh(self, targets: list["CastTarget"]) -> None:
        self._scan_busy = False
        self._apply_refresh_targets(targets)

    def _apply_refresh_targets(
        self,
        targets: list["CastTarget"],
        *,
        merge: bool = False,
    ) -> None:
        if merge and self.targets:
            from src.cast.group_discovery import CastGroupDiscovery

            targets = CastGroupDiscovery.merge_targets(self.targets, targets)
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
        elif self.targets and self._focus_index is not None:
            self._focus_index = min(self._focus_index, len(self.targets) - 1)

        if self._active_uuid is not None and self._active_target_name() is None:
            self._active_uuid = None

        self._apply_target_styles()
        self._maybe_auto_cast()
        self._update_status_text()

    def _auto_refresh(self) -> None:
        if self.discovery is not None:
            found = self.discovery.discover(wait_seconds=1.0)
            self._apply_refresh_targets(found, merge=True)
        self._auto_after_id = self.root.after(self._refresh_ms, self._auto_refresh)

    def stop_cast(self) -> None:
        import threading

        threading.Thread(target=self._stop_cast_worker, daemon=True).start()

    def _stop_cast_worker(self) -> None:
        if self.controller is not None:
            self.controller.stop_stream()
        self.root.after(0, self._finish_stop_cast_ui)

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

    # ------------------------------------------------------------------
    # Web interface bridge
    #
    # The web server runs in background HTTP threads. To keep the Tk app the
    # single source of truth (so screen + web never disagree), web actions are
    # scheduled onto the Tk main loop via ``after()`` and reuse the exact same
    # handlers as a physical tap. Reads return a plain snapshot dict.
    # ------------------------------------------------------------------
    def _status_kind(self) -> str:
        if self._status_color == ERROR:
            return "error"
        if self._status_color == SUCCESS_FG:
            return "success"
        return "info"

    def get_web_snapshot(self) -> dict:
        """Thread-safe view of the current UI state for the web interface."""
        targets = self.targets
        active = self._active_uuid
        rms = peak = 0.0
        if self.listener is not None:
            snapshot = self.listener.get_latest_snapshot()
            rms = snapshot.levels.rms_linear
            peak = snapshot.levels.peak_linear
        return {
            "status": {"text": self._status_text, "kind": self._status_kind()},
            "active_uuid": active,
            "busy": self._cast_busy,
            "scanning": self._scan_busy,
            "targets": [
                {
                    "uuid": target.uuid,
                    "name": target.name,
                    "is_group": target.is_group,
                    "active": target.uuid == active,
                }
                for target in targets
            ],
            # Match AudioBarsWidget: rms_linear * 3, clamped to 0..1.
            "level": max(0.0, min(1.0, rms * 3.0)),
            "rms": rms,
            "peak": peak,
        }

    def web_request_cast(self, uuid: str) -> bool:
        """Toggle casting for a target by uuid (same as tapping it on screen)."""
        if not any(target.uuid == uuid for target in self.targets):
            return False
        self.root.after(0, lambda u=uuid: self._cast_by_uuid(u))
        return True

    def _cast_by_uuid(self, uuid: str) -> None:
        index = next(
            (i for i, target in enumerate(self.targets) if target.uuid == uuid),
            None,
        )
        if index is not None:
            self._on_target_tap(index)

    def web_request_refresh(self) -> None:
        self.root.after(0, self.refresh_targets)

    def _start_web_ui(self) -> None:
        if not self.settings.web_ui_enabled or self.web is not None:
            return
        try:
            from src.web.server import WebInterface

            self.web = WebInterface(
                self,
                host=self.settings.web_host,
                port=self.settings.web_port,
            )
            self.web.start()
            log_milestone(f"web ui on :{self.settings.web_port}")
        except Exception as exc:  # never let the web UI break the screen
            self.web = None
            log_milestone(f"web ui failed: {exc}")

    def run(self) -> None:
        log_milestone("ui visible on tft")
        self._update_audio_ui()
        self.root.after(50, self._begin_background_startup)
        self.root.after(150, self._ensure_input_focus)
        self.root.after(200, self._start_web_ui)
        self.root.mainloop()

    def _begin_background_startup(self) -> None:
        import threading

        self._set_subtitle("Loading audio…")
        threading.Thread(target=self._load_audio_worker, daemon=True).start()

    def _load_audio_worker(self) -> None:
        import time

        # When auto-cast is enabled, skip the level monitor at boot so ffmpeg can
        # open hw:N,0 immediately (ALSA allows only one capture client).
        if self.settings.auto_cast_targets:
            self._ensure_audio()
            self.root.after(
                0,
                lambda: self._audio_startup_done(True, None),
            )
            return

        input_ok = False
        error: str | None = None
        for attempt in range(6):
            try:
                self._ensure_audio()
                input_ok = self.listener.start()
                error = self.listener.last_error
                if input_ok:
                    break
                if error and "opening" not in error.lower():
                    break
            except Exception as exc:
                input_ok = False
                error = str(exc)
            if attempt < 5:
                time.sleep(1.0)

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
            targets = self.discovery.discover(
                wait_seconds=self.settings.cast_discovery_timeout,
            )
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

        if error and not self.targets:
            self._set_subtitle(error, ERROR)
            log_milestone(f"cast err: {error}")
        elif error:
            log_milestone(f"cast note: {error}")
        else:
            log_milestone(f"first cast scan ({len(self.targets)} target(s))")

        self._maybe_auto_cast()
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
        if self.web is not None:
            try:
                self.web.stop()
            except Exception:
                pass
            self.web = None
        if self.controller is not None:
            self.controller.stop_stream()
        if self.listener is not None:
            self.listener.stop()
        if self.discovery is not None:
            self.discovery.shutdown()
        self.root.destroy()
