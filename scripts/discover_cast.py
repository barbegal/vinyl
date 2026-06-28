#!/usr/bin/env python3
"""Scan the LAN for Google Cast devices and print what the app would see."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.settings import AppSettings
from src.cast.group_discovery import CastGroupDiscovery


def main() -> None:
    settings = AppSettings.from_env()
    discovery = CastGroupDiscovery(
        discovery_timeout=settings.cast_discovery_timeout,
        known_hosts=settings.cast_known_hosts,
    )

    print(f"Scanning for Cast devices ({settings.cast_discovery_timeout}s)...")
    if settings.cast_known_hosts:
        print(f"Known hosts: {', '.join(settings.cast_known_hosts)}")

    targets = discovery.discover(wait_seconds=settings.cast_discovery_timeout)

    if discovery.last_error:
        print(f"Note: {discovery.last_error}")

    if not targets:
        print("No targets listed in the app.")
        return

    print(f"Found {len(targets)} target(s):")
    for target in targets:
        group = "group" if target.is_group else "speaker"
        print(
            f"  - {target.name} ({group}) "
            f"{target.host}:{target.port} model={target.model_name}"
        )

    discovery.shutdown()


if __name__ == "__main__":
    main()
