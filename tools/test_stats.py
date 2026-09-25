"""make stats is the progress metric; it must count Hex-Rays names
exactly, and never count ordinary identifiers that merely contain them."""
import unittest

import stats


class CountTest(unittest.TestCase):
    def test_counts_each_hexrays_prefix(self):
        text = "sub_40D920(dword_4A7DBC, &unk_45F04C, byte_463D9C); sub_401000();"
        self.assertEqual(stats.count(text), {"sub_": 2, "dword_": 1, "unk_": 1, "byte_": 1})

    def test_ignores_identifiers_that_only_contain_a_prefix(self):
        text = "my_sub_401000(); drawCar_40D920(); dword_count = 1;"
        self.assertEqual(stats.count(text), {"sub_": 0, "dword_": 0, "unk_": 0, "byte_": 0})


if __name__ == "__main__":
    unittest.main()
