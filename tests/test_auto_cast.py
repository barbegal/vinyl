"""Tests for startup auto-connect target selection."""

from __future__ import annotations

import unittest

from src.cast.group_discovery import select_preferred_target


class TestSelectPreferredTarget(unittest.TestCase):
    def test_picks_first_priority_when_present(self) -> None:
        names = ["Kitchen", "Upper", "Living Room Speaker"]
        self.assertEqual(
            select_preferred_target(names, ["Upper", "Living Room Speaker"]), 1
        )

    def test_falls_back_to_second_priority(self) -> None:
        names = ["Kitchen", "Living Room Speaker"]
        self.assertEqual(
            select_preferred_target(names, ["Upper", "Living Room Speaker"]), 1
        )

    def test_returns_none_when_no_match(self) -> None:
        names = ["Kitchen", "Patio"]
        self.assertIsNone(
            select_preferred_target(names, ["Upper", "Living Room Speaker"])
        )

    def test_case_insensitive(self) -> None:
        names = ["upper"]
        self.assertEqual(select_preferred_target(names, ["Upper"]), 0)

    def test_exact_match_beats_substring(self) -> None:
        # "Upper" should match the exact entry, not "Upper Patio".
        names = ["Upper Patio", "Upper"]
        self.assertEqual(select_preferred_target(names, ["Upper"]), 1)

    def test_substring_match_when_no_exact(self) -> None:
        names = ["Upper Floor Group"]
        self.assertEqual(select_preferred_target(names, ["Upper"]), 0)

    def test_priority_order_respected(self) -> None:
        # Both present → first priority wins regardless of list order.
        names = ["Living Room Speaker", "Upper"]
        self.assertEqual(
            select_preferred_target(names, ["Upper", "Living Room Speaker"]), 1
        )

    def test_empty_preferences_returns_none(self) -> None:
        self.assertIsNone(select_preferred_target(["Upper"], []))

    def test_blank_preference_entries_skipped(self) -> None:
        names = ["Living Room Speaker"]
        self.assertEqual(
            select_preferred_target(names, ["", "  ", "Living Room Speaker"]), 0
        )


if __name__ == "__main__":
    unittest.main()
