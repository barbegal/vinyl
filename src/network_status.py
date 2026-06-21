"""Lightweight network readiness checks (no heavy imports)."""

from __future__ import annotations

import socket
from pathlib import Path


def _iface_operstates() -> dict[str, str]:
    states: dict[str, str] = {}
    net_root = Path("/sys/class/net")
    if not net_root.is_dir():
        return states
    for iface in net_root.iterdir():
        if iface.name == "lo":
            continue
        oper = iface / "operstate"
        if oper.is_file():
            try:
                states[iface.name] = oper.read_text(encoding="utf-8").strip()
            except OSError:
                continue
    return states


def is_iface_link_up(iface: str) -> bool:
    state = _iface_operstates().get(iface, "down")
    return state in {"up", "dormant", "unknown"}


def is_lan_ready(timeout: float = 0.35) -> bool:
    """True when the Pi has a routable path off the LAN (Wi‑Fi or Ethernet)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.connect(("8.8.8.8", 80))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def network_status_line() -> str:
    """Short status for the UI subtitle while Wi‑Fi / routing is still coming up."""
    states = _iface_operstates()
    wlan = states.get("wlan0", "down")
    eth = states.get("eth0", "down")

    if is_lan_ready():
        if is_iface_link_up("eth0"):
            return "Network ready"
        if is_iface_link_up("wlan0"):
            return "Wi‑Fi connected"
        return "Network ready"

    if wlan in {"up", "dormant"}:
        return "Wi‑Fi connecting…"
    if eth == "up":
        return "Ethernet connecting…"
    if wlan == "down" and "wlan0" in states:
        return "Waiting for Wi‑Fi…"
    return "Waiting for network…"
