"""USB capture calibration — ALSA level + cast gain, persisted under ~/.vinyl/."""

from __future__ import annotations

import json
import math
import os
import re
import struct
import subprocess
import wave
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.config.settings import AppSettings

CALIBRATION_VERSION = 1
CAPTURE_NUMID = 3
CAPTURE_MAX = 62
DEFAULT_PERCENTS = (60, 55, 50, 45, 40, 35)


@dataclass(frozen=True)
class AudioCalibration:
    version: int = CALIBRATION_VERSION
    updated_at: str = ""
    alsa_card: int = 3
    capture_numid: int = CAPTURE_NUMID
    capture_max: int = CAPTURE_MAX
    capture_value: int = 28
    capture_percent: int = 45
    measured_peak: int = 0
    measured_rms_db: float = -120.0
    cast_input_gain_db: float = -9.0
    cast_high_cut_hz: int = 14000
    cast_output_volume: float = 0.32
    cast_stereo_mode: str = "stereo"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudioCalibration:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def calibration_path() -> Path:
    return Path.home() / ".vinyl" / "calibration.json"


def load_calibration() -> AudioCalibration | None:
    path = calibration_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return AudioCalibration.from_dict(data)
    except (OSError, ValueError, TypeError):
        return None


def save_calibration(cal: AudioCalibration) -> None:
    path = calibration_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = cal.to_dict()
    if not payload.get("updated_at"):
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def resolve_alsa_card(usb_alsa_device: str) -> int:
    asoundrc = Path.home() / ".asoundrc"
    if asoundrc.is_file():
        match = re.search(r'pcm "hw:(\d+)', asoundrc.read_text(encoding="utf-8"))
        if match:
            return int(match.group(1))
    match = re.search(r"(\d+)", usb_alsa_device or "")
    if match:
        return int(match.group(1))
    return 3


def percent_to_capture_value(percent: int, capture_max: int = CAPTURE_MAX) -> int:
    return max(0, min(capture_max, int(percent * capture_max / 100)))


def recommend_gain_db(peak: int) -> float:
    if peak <= 0:
        return -9.0
    if peak >= 32760:
        return -15.0
    if peak > 20000:
        return -12.0
    if peak > 12000:
        return -9.0
    return -6.0


def measure_capture(device: str, seconds: float = 2.0) -> tuple[int, float]:
    """Return (peak sample, rms dBFS) from a short stereo capture."""
    out = Path(f"/tmp/vinyl-cal-{os.getpid()}.wav")
    try:
        proc = subprocess.run(
            [
                "arecord",
                "-D",
                device,
                "-f",
                "S16_LE",
                "-r",
                "48000",
                "-c",
                "2",
                "-d",
                str(max(1, int(seconds))),
                str(out),
            ],
            capture_output=True,
            text=True,
            timeout=max(10, int(seconds) + 8),
        )
        if proc.returncode != 0 or not out.is_file():
            return 0, -120.0

        with wave.open(str(out), "rb") as handle:
            raw = handle.readframes(handle.getnframes())
        if len(raw) < 4:
            return 0, -120.0
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        peak = max(abs(x) for x in samples)
        rms = math.sqrt(sum(x * x for x in samples) / max(len(samples), 1))
        rms_db = 20.0 * math.log10(max(rms, 1.0) / 32768.0)
        return peak, rms_db
    finally:
        out.unlink(missing_ok=True)


def set_capture_percent(card: int, percent: int, *, numid: int = CAPTURE_NUMID) -> int:
    value = percent_to_capture_value(percent)
    subprocess.run(
        ["amixer", "-c", str(card), "cset", f"numid={numid}", str(value)],
        capture_output=True,
        check=False,
    )
    return value


def apply_alsa_capture(cal: AudioCalibration) -> bool:
    try:
        probe = subprocess.run(
            ["amixer", "-c", str(cal.alsa_card), "cget", f"numid={cal.capture_numid}"],
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0:
            return False
        subprocess.run(
            [
                "amixer",
                "-c",
                str(cal.alsa_card),
                "cset",
                f"numid={cal.capture_numid}",
                str(cal.capture_value),
            ],
            capture_output=True,
            check=False,
        )
        return True
    except OSError:
        return False


def run_calibration(
    capture_device: str = "vinyl_in",
    usb_alsa_device: str = "vinyl_in",
    seconds: float = 2.0,
) -> AudioCalibration:
    card = resolve_alsa_card(usb_alsa_device)
    best_percent = 50
    best_peak = 0
    best_rms_db = -120.0
    best_value = percent_to_capture_value(best_percent)

    for percent in DEFAULT_PERCENTS:
        value = set_capture_percent(card, percent)
        peak, rms_db = measure_capture(capture_device, seconds)
        best_percent = percent
        best_peak = peak
        best_rms_db = rms_db
        best_value = value
        if 3000 < peak < 18000:
            break
        if 0 < peak < 3000:
            break

    cal = AudioCalibration(
        updated_at=datetime.now(timezone.utc).isoformat(),
        alsa_card=card,
        capture_numid=CAPTURE_NUMID,
        capture_max=CAPTURE_MAX,
        capture_value=best_value,
        capture_percent=best_percent,
        measured_peak=best_peak,
        measured_rms_db=round(best_rms_db, 1),
        cast_input_gain_db=recommend_gain_db(best_peak),
        cast_high_cut_hz=14000,
        cast_output_volume=0.32,
        cast_stereo_mode="stereo",
    )
    save_calibration(cal)
    return cal


def _env_explicit(name: str) -> bool:
    raw = os.getenv(name)
    return raw is not None and str(raw).strip() != ""


def merge_calibration(settings: AppSettings, cal: AudioCalibration | None = None) -> AppSettings:
    """Apply saved calibration unless .env explicitly overrides audio keys."""
    if cal is None:
        cal = load_calibration()
    if cal is None:
        return settings

    updates: dict[str, Any] = {}
    if not _env_explicit("CAST_INPUT_GAIN_DB"):
        updates["stream_input_gain_db"] = cal.cast_input_gain_db
    if not _env_explicit("AUDIO_LEVEL_INPUT_TRIM_DB"):
        updates["level_input_trim_db"] = cal.cast_input_gain_db
    if not _env_explicit("CAST_HIGH_CUT_HZ"):
        updates["stream_high_cut_hz"] = cal.cast_high_cut_hz
    if not _env_explicit("CAST_OUTPUT_VOLUME"):
        updates["cast_output_volume"] = cal.cast_output_volume
    if not _env_explicit("CAST_STEREO_MODE"):
        updates["cast_stereo_mode"] = cal.cast_stereo_mode

    if not updates:
        return settings
    return replace(settings, **updates)


def load_settings_with_calibration() -> AppSettings:
    from src.config.settings import AppSettings

    settings = AppSettings.from_env()
    cal = load_calibration()
    if cal is not None:
        apply_alsa_capture(cal)
    return merge_calibration(settings, cal)


def auto_calibrate_enabled() -> bool:
    raw = os.getenv("VINYL_AUTO_CALIBRATE", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def needs_recalibration(cal: AudioCalibration | None) -> bool:
    if cal is None:
        return True
    return cal.measured_peak >= 18000


def ensure_calibration(
    settings: AppSettings,
    *,
    force: bool = False,
    seconds: float = 2.0,
) -> AudioCalibration | None:
    """Load or run calibration; returns latest calibration if any."""
    capture = settings.usb_alsa_device.strip() or "vinyl_in"
    device = capture if capture == "vinyl_in" else "vinyl_in"

    existing = load_calibration()
    if not force and not needs_recalibration(existing) and existing is not None:
        apply_alsa_capture(existing)
        return existing

    if not force and not auto_calibrate_enabled():
        if existing is not None:
            apply_alsa_capture(existing)
        return existing

    try:
        return run_calibration(
            capture_device=device,
            usb_alsa_device=capture,
            seconds=seconds,
        )
    except OSError:
        return existing


def main() -> int:
    import argparse

    from src.config.settings import AppSettings

    parser = argparse.ArgumentParser(description="Calibrate USB capture gain for vinyl cast")
    parser.add_argument("seconds", nargs="?", type=float, default=2.0, help="capture length")
    parser.add_argument("--force", action="store_true", help="re-run even if calibration exists")
    args = parser.parse_args()

    settings = AppSettings.from_env()
    cal = ensure_calibration(settings, force=args.force, seconds=args.seconds)
    if cal is None:
        print("Calibration failed — is vinyl_in available? Play a record and retry.")
        return 1

    merged = merge_calibration(settings, cal)
    print(f"Saved {calibration_path()}")
    print(
        f"  Mic Capture: {cal.capture_percent}% (val {cal.capture_value}/{cal.capture_max})"
    )
    print(f"  measured peak={cal.measured_peak}  rms={cal.measured_rms_db:+.1f} dBFS")
    print(f"  CAST_INPUT_GAIN_DB={merged.stream_input_gain_db}")
    print(f"  CAST_OUTPUT_VOLUME={merged.cast_output_volume}")
    print(f"  CAST_STEREO_MODE={merged.cast_stereo_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
