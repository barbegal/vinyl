import unittest

from src.cast.group_discovery import CastGroupDiscovery, make_cast_target


class TestDiscoveryFilter(unittest.TestCase):
    def test_prefers_groups_when_available(self):
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
        output = CastGroupDiscovery._filter_targets(targets, groups_only=True)
        self.assertEqual([item.name for item in output], ["Whole House"])

    def test_falls_back_to_all_when_no_groups(self):
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
        output = CastGroupDiscovery._filter_targets(targets, groups_only=True)
        self.assertEqual(len(output), 2)


if __name__ == "__main__":
    unittest.main()
