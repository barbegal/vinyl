#!/usr/bin/env python3
"""Verify runtime dependencies for the cast app."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    ok = True
    for name, module in (
        ("numpy", "numpy"),
        ("PIL", "PIL"),
        ("zeroconf", "zeroconf"),
        ("sounddevice", "sounddevice"),
        ("protobuf", "google.protobuf"),
    ):
        try:
            __import__(module)
            print(f"OK  {name}")
        except ImportError as exc:
            ok = False
            print(f"FAIL {name}: {exc}")

    try:
        import pychromecast  # noqa: F401
        print("OK  pychromecast")
    except ImportError as exc:
        ok = False
        print(f"FAIL pychromecast: {exc}")
        print("     Run: pip install -r requirements.txt")

    if not ok:
        sys.exit(1)
    print("All dependencies OK")


if __name__ == "__main__":
    main()
