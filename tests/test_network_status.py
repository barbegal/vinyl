"""Tests for network_status (no live network required)."""

from __future__ import annotations

import unittest

from src.network_status import is_iface_link_up, network_status_line


class TestNetworkStatus(unittest.TestCase):
    def test_network_status_line_is_non_empty(self) -> None:
        line = network_status_line()
        self.assertTrue(line)

    def test_iface_link_up_unknown_state(self) -> None:
        # On dev machines wlan0/eth0 may be absent; should not raise.
        self.assertIsInstance(is_iface_link_up("wlan0"), bool)


if __name__ == "__main__":
    unittest.main()
