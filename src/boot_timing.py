"""Append boot milestones to ~/.vinyl-boot.log (kernel uptime seconds)."""

from __future__ import annotations

from pathlib import Path

_BOOT_LOG = Path.home() / ".vinyl-boot.log"


def log_milestone(label: str) -> None:
    try:
        uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        with _BOOT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{uptime:7.2f}s  {label}\n")
    except OSError:
        pass
