"""Tests for Cast discovery wait + sort."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.cast.group_discovery import CastGroupDiscovery, make_cast_target


class TestDiscoverySort(unittest.TestCase):
    def test_groups_listed_before_speakers(self):
        targets = [
            make_cast_target(
                "00000000-0000-0000-0000-000000000001",
                "Kitchen",
                "10.0.0.1",
                8009,
                False,
                "Nest Audio",
            ),
            make_cast_target(
                "00000000-0000-0000-0000-000000000002",
                "Whole House",
                "10.0.0.2",
                8009,
                True,
                "Google Cast Group",
            ),
        ]
        output = CastGroupDiscovery._sort_targets(targets)
        self.assertEqual([item.name for item in output], ["Whole House", "Kitchen"])

    def test_returns_all_targets(self):
        targets = [
            make_cast_target(
                "00000000-0000-0000-0000-000000000001",
                "Kitchen",
                "10.0.0.1",
                8009,
                False,
                "Nest Audio",
            ),
            make_cast_target(
                "00000000-0000-0000-0000-000000000002",
                "Patio",
                "10.0.0.2",
                8009,
                False,
                "Nest Mini",
            ),
        ]
        output = CastGroupDiscovery._sort_targets(targets)
        self.assertEqual(len(output), 2)
        self.assertEqual([item.name for item in output], ["Kitchen", "Patio"])

    @patch("src.cast.group_discovery.time.sleep", return_value=None)
    def test_discover_wait_keeps_largest_result(self, _sleep: MagicMock) -> None:
        discovery = CastGroupDiscovery(discovery_timeout=12.0)
        one = [
            make_cast_target(
                "00000000-0000-0000-0000-000000000001",
                "A",
                "10.0.0.1",
                8009,
                False,
                "Speaker",
            ),
        ]
        two = one + [
            make_cast_target(
                "00000000-0000-0000-0000-000000000002",
                "B",
                "10.0.0.2",
                8009,
                False,
                "Speaker",
            ),
        ]
        with patch.object(
            discovery,
            "_read_browser_targets",
            side_effect=[one, two, two],
        ):
            result = discovery.discover(wait_seconds=1.0)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
