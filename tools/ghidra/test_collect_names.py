"""The name sync is only useful if every name lands on the right address:
a wrong or ambiguous mapping would mislabel the original in Ghidra."""
import unittest

import collect_names

MARKER = "//----- (%08X) --------------------------------------------------------"


class NamesInTest(unittest.TestCase):
    def test_function_right_after_marker(self):
        text = MARKER % 0x415710 + "\nvoid __cdecl startRace(int a1)\n{\n}\n"
        self.assertEqual(list(collect_names.names_in(text)), [(0x415710, "startRace")])

    def test_blank_and_comment_lines_are_skipped(self):
        text = MARKER % 0x40D920 + "\n\n// draws a car\nint drawCarInRace_40D920(int a1)\n{\n}\n"
        self.assertEqual(list(collect_names.names_in(text)), [(0x40D920, "drawCarInRace_40D920")])

    def test_return_type_on_its_own_line(self):
        text = MARKER % 0x401000 + "\nsigned int\nsub_401000(void)\n{\n}\n"
        self.assertEqual(list(collect_names.names_in(text)), [(0x401000, "sub_401000")])

    def test_marker_without_function_yields_nothing(self):
        text = MARKER % 0x402000 + "\nint dword_402000;\n"
        self.assertEqual(list(collect_names.names_in(text)), [])

    def test_stacked_markers_name_only_the_last_one(self):
        # dr.c: 004156B0 belongs to a commented-out function, then 00415710 is startRace.
        text = (MARKER % 0x4156B0 + "\n//int sub_4156B0()\n" + MARKER % 0x415710 +
                "\nvoid   startRace(int a1, int numberOfParticipants)\n{\n}\n")
        self.assertEqual(list(collect_names.names_in(text)), [(0x415710, "startRace")])


class MergeTest(unittest.TestCase):
    def test_same_address_two_names_is_a_conflict_and_is_dropped(self):
        mapping, conflicts = collect_names.merge([(0x401000, "a"), (0x401000, "b"), (0x402000, "c")])
        self.assertEqual(mapping, {0x402000: "c"})
        self.assertEqual(len(conflicts), 1)
        self.assertIn("00401000", conflicts[0])

    def test_same_name_two_addresses_is_a_conflict_and_is_dropped(self):
        mapping, conflicts = collect_names.merge([(0x401000, "a"), (0x402000, "a")])
        self.assertEqual(mapping, {})
        self.assertEqual(len(conflicts), 1)

    def test_duplicate_identical_pair_is_fine(self):
        mapping, conflicts = collect_names.merge([(0x401000, "a"), (0x401000, "a")])
        self.assertEqual(mapping, {0x401000: "a"})
        self.assertEqual(conflicts, [])


if __name__ == "__main__":
    unittest.main()
