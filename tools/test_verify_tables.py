"""Tests for verify-tables.py: why they matter is that a single hand-typed
byte can drift from the original and nothing else would ever catch it --
see doc/FINDINGS.md's "hand-typed data tables" bug class. A false PASS here
would let that class of bug back in silently."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util

spec = importlib.util.spec_from_file_location("verify_tables", Path(__file__).resolve().parent / "verify-tables.py")
vt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vt)

IMAGE_BASE = 0x400000


def make_pe(path, data_va, data_bytes, rdata_va=None, rdata_bytes=b""):
    """A minimal PE32 image with a .data section (and optionally .rdata)
    holding known bytes at a known VA, enough for OriginalImage to map an
    address back to file content -- the same shape tools/equiv/test_equiv.py
    uses for its synthetic PE."""
    pe_offset = 0x40
    opt_size = 0xE0
    sections = [(".data", data_va, data_bytes)]
    if rdata_va is not None:
        sections.append((".rdata", rdata_va, rdata_bytes))
    header = bytearray(0x400)
    header[0:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, pe_offset)
    header[pe_offset:pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<HH", header, pe_offset + 4, 0x14C, len(sections))
    struct.pack_into("<H", header, pe_offset + 20, opt_size)
    opt = pe_offset + 24
    struct.pack_into("<H", header, opt, 0x10B)
    struct.pack_into("<I", header, opt + 28, IMAGE_BASE)
    struct.pack_into("<I", header, opt + 56, 0x200000)  # SizeOfImage
    table = opt + opt_size
    body = bytearray()
    raw_ptr = len(header)
    for i, (name, va, raw) in enumerate(sections):
        entry = table + 40 * i
        header[entry:entry + 8] = name.encode().ljust(8, b"\0")
        struct.pack_into("<IIII", header, entry + 8, len(raw), va, len(raw), raw_ptr + len(body))
        body += raw
    Path(path).write_bytes(bytes(header) + bytes(body))


class OriginalImageTest(unittest.TestCase):
    def test_reads_bytes_at_va_through_section_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, 0x45000, b"\x01\x02\x03\x04\x05\x06\x07\x08")
            img = vt.OriginalImage(exe)
        self.assertEqual(img.read(0x445000, 4), b"\x01\x02\x03\x04")
        self.assertEqual(img.read(0x445004, 2), b"\x05\x06")

    def test_address_outside_any_section_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, 0x45000, b"\x00" * 4)
            img = vt.OriginalImage(exe)
        self.assertIsNone(img.section_of(0x500000))

    def test_section_of_reports_data_vs_rdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, 0x45000, b"\x00" * 4, rdata_va=0x10000, rdata_bytes=b"\x00" * 4)
            img = vt.OriginalImage(exe)
        self.assertEqual(img.section_of(0x445000)[0], ".data")
        self.assertEqual(img.section_of(0x410000)[0], ".rdata")


class ParseInitialiserTest(unittest.TestCase):
    def _init(self, src):
        return vt.parse_initialiser(src, 0)

    def test_plain_int_list(self):
        init, _ = self._init("{ 1, 2, 0x10 };")
        self.assertEqual(init, [("num", "1"), ("num", "2"), ("num", "0x10")])

    def test_nested_braces_are_kept_as_nesting(self):
        # Byte positions depend on the nesting, not only on the order: in
        # int a[2][3], { {1}, {2,3} } puts 2 at index 3, not at index 1.
        init, _ = self._init("{ {1}, {2,3} };")
        self.assertEqual(init, [[("num", "1")], [("num", "2"), ("num", "3")]])

    def test_comment_inside_initialiser_is_skipped(self):
        # Real case: imageUtil.c's letterSpacing_4458B0 has "//20"-style
        # inline comments between values on their own lines.
        init, _ = self._init("{ 1, //comment\n 2 };")
        self.assertEqual(init, [("num", "1"), ("num", "2")])

    def test_block_comment_inside_initialiser_is_skipped(self):
        init, _ = self._init("{ 1, /* two */ 2 };")
        self.assertEqual(init, [("num", "1"), ("num", "2")])

    def test_char_literals_decode_escapes(self):
        init, _ = self._init(r"{ 'A', '\0', '\x41', '\12' };")
        self.assertEqual([int(t) for _, t in init], [65, 0, 65, 10])

    def test_string_literal_is_one_item_without_its_nul(self):
        # Whether the NUL is stored depends on the array size (see
        # FindArraysTest), so the parser must not add it.
        init, _ = self._init('"AB";')
        self.assertEqual(init, ("str", [65, 66]))

    def test_adjacent_string_literals_are_one_literal(self):
        # C joins "ab" "cd" into "abcd": an extra NUL between them would
        # shift every later byte of the table by one.
        init, _ = self._init('{ "ab" /* x */ "cd" };')
        self.assertEqual(init, [("str", [97, 98, 99, 100])])

    def test_stops_at_the_terminating_semicolon(self):
        init, end = self._init("{ 1, 2 };\nchar next")
        self.assertEqual(len(init), 2)
        self.assertEqual(end, len("{ 1, 2 };"))

    def test_semicolon_inside_a_string_literal_does_not_end_the_scan(self):
        init, end = self._init('{ "a;b" };')
        self.assertEqual(init, [("str", [ord("a"), ord(";"), ord("b")])])
        self.assertEqual(end, len('{ "a;b" };'))

    def test_second_declarator_is_unparsed_not_skipped(self):
        # The second array of `int a[] = {1}, b[] = {2};` would never be
        # checked, so the statement must be reported.
        with self.assertRaises(vt.Unparsed):
            self._init("{ 1 }, b_445010[] = { 2 };")


class ParseDimsTest(unittest.TestCase):
    def test_empty_first_dim_means_infer(self):
        self.assertEqual(vt.parse_dims("[]"), [None])

    def test_single_dim(self):
        self.assertEqual(vt.parse_dims("[10]"), [10])

    def test_product_expression(self):
        # carAnimFrameSize_445968[6*64] in the real tree.
        self.assertEqual(vt.parse_dims("[6*64]"), [384])

    def test_two_dims(self):
        self.assertEqual(vt.parse_dims("[3][4]"), [3, 4])

    def test_macro_dimension_is_unparsed(self):
        with self.assertRaises(vt.Unparsed):
            vt.parse_dims("[SIZE]")


class FindArraysTest(unittest.TestCase):
    def test_finds_declaration_and_flattens_values(self):
        text = "int foo_401000[] = { 1, 2, 3 };\n"
        arrs = list(vt.find_arrays(Path("x.c"), text))
        self.assertEqual(len(arrs), 1)
        a = arrs[0]
        self.assertEqual(a.name, "foo_401000")
        self.assertEqual(a.addr, 0x401000)
        self.assertEqual(a.values, [1, 2, 3])
        self.assertEqual(a.elem_size, 4)

    def test_explicit_size_pads_with_zero(self):
        text = "char foo_401000[5] = { 1, 2 };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 2, 0, 0, 0])

    def test_commented_out_declaration_is_not_found(self):
        # The real-tree bug this guards: a stale duplicate like
        # "//char dword_4A9160[]= {...}" in dr.c must not be scanned --
        # verify-tables.py masks comments before matching declarations.
        text = "//int foo_401000[] = { 1, 2, 3 };\nint bar_401010[] = { 4 };\n"
        arrs = list(vt.find_arrays(Path("x.c"), text))
        self.assertEqual([a.name for a in arrs], ["bar_401010"])

    def test_block_commented_declaration_is_not_found(self):
        text = "/* int foo_401000[] = { 1 }; */\nint bar_401010[] = { 4 };\n"
        arrs = list(vt.find_arrays(Path("x.c"), text))
        self.assertEqual([a.name for a in arrs], ["bar_401010"])

    def _unparsed(self, text):
        """The reason the one array in `text` is reported as unparsed."""
        arrs = list(vt.find_arrays(Path("x.c"), text))
        self.assertEqual(len(arrs), 1)
        self.assertIsInstance(arrs[0], vt.UnparsedArray)
        return arrs[0].reason

    def test_unknown_type_is_reported_not_dropped(self):
        # A dropped array is a check that silently passes.
        reason = self._unparsed("ShopMessages foo_401000[] = { 1 };\n")
        self.assertIn("unknown element type", reason)

    def test_unsigned_char_and_hexrays_word_types_recognised(self):
        text = "unsigned char a_401000[] = { 1 };\n_WORD b_401010[] = { 2 };\n"
        arrs = {a.name: a for a in vt.find_arrays(Path("x.c"), text)}
        self.assertEqual(arrs["a_401000"].elem_size, 1)
        self.assertEqual(arrs["b_401010"].elem_size, 2)

    def test_hexrays_scalar_types_recognised(self):
        # Hex-Rays declares data with these; before they were in TYPE_INFO
        # such an array was silently not verified.
        text = ("unsigned __int8 a_401000[] = { 1 };\n__int16 b_401010[] = { 2 };\n"
                "_UNKNOWN c_401020[] = { 3 };\n")
        arrs = {a.name: a for a in vt.find_arrays(Path("x.c"), text)}
        self.assertEqual({k: a.elem_size for k, a in arrs.items()},
                         {"a_401000": 1, "b_401010": 2, "c_401020": 1})

    def test_string_that_exactly_fills_the_array_has_no_nul(self):
        # Valid C (the NUL is not stored); it used to be dropped as
        # "longer than declared".
        a = list(vt.find_arrays(Path("x.c"), 'char foo_401000[2] = "AB";\n'))[0]
        self.assertEqual(a.values, [65, 66])

    def test_string_rows_that_exactly_fill_a_row_have_no_nul(self):
        text = 'char foo_401000[2][2] = { "AB", "CD" };\n'
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [65, 66, 67, 68])

    def test_more_initialisers_than_the_size_is_reported(self):
        # clang accepts excess initialisers with -Wno-everything, so a typed
        # extra element compiles; it must not make the array unchecked.
        reason = self._unparsed("char foo_401000[2] = { 1, 2, 3 };\n")
        self.assertIn("more initialisers", reason)

    def test_string_longer_than_the_array_is_reported(self):
        reason = self._unparsed('char foo_401000[2] = "ABC";\n')
        self.assertIn("string literal", reason)

    def test_casts_macros_and_expressions_are_reported_not_a_traceback(self):
        for init in ("(char)0x80", "SIZE", "1 + 1", "'a' + 1"):
            reason = self._unparsed("char foo_401000[] = { %s };\n" % init)
            self.assertIn("cannot evaluate", reason, init)

    def test_designated_initialiser_is_reported(self):
        reason = self._unparsed("char foo_401000[4] = { [2] = 1 };\n")
        self.assertIn("designated", reason)

    def test_assignment_statement_is_not_a_declaration(self):
        # `return x[i] = 2;` matches the declaration pattern; reporting it
        # would be noise, so it is not scanned at all.
        self.assertEqual(list(vt.find_arrays(Path("x.c"), "return foo_401000[1] = 2;\n")), [])

    def test_two_dimensional_array_flattens_row_major(self):
        text = "int foo_401000[2][2] = { {1,2}, {3,4} };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 2, 3, 4])

    def test_string_rows_of_a_2d_char_array_are_padded_to_the_row(self):
        # C pads each row: the original's menu text table is 9 rows of 50
        # bytes per menu, each holding one short string. Flattened without
        # padding, every row after the first would be compared at the wrong
        # address.
        text = 'char foo_401000[3][4] = { "AB", "C" };\n'
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [65, 66, 0, 0, 67, 0, 0, 0, 0, 0, 0, 0])

    def test_short_brace_rows_are_padded_too(self):
        text = "int foo_401000[2][3] = { {1}, {2, 3} };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 0, 0, 2, 3, 0])

    def test_brace_elision_stays_flat(self):
        text = "int foo_401000[2][2] = { 1, 2, 3, 4 };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 2, 3, 4])

    def test_braced_row_then_elided_row_zero_fills_like_c(self):
        # Row 0 is braced and short, row 1 takes 2 and 3 by brace elision.
        text = "int foo_401000[2][3] = { {1}, 2, 3 };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 0, 0, 2, 3, 0])

    def test_three_dimensional_short_lists_zero_fill_like_c(self):
        text = "int foo_401000[2][2][2] = { { {1}, {2, 3} }, { {4} } };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 0, 2, 3, 4, 0, 0, 0])

    def test_braces_around_scalars(self):
        text = "int foo_401000[3] = { {1}, 2 };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 2, 0])

    def test_inferred_first_dimension_counts_elided_rows(self):
        text = "int foo_401000[][3] = { 1, 2, 3, 4 };\n"
        a = list(vt.find_arrays(Path("x.c"), text))[0]
        self.assertEqual(a.values, [1, 2, 3, 4, 0, 0])

    def test_rename_map_redirects_the_address(self):
        # Mirrors the real continueAnimFramesSize_4611D0 case before it was
        # fixed by renaming: the suffix is not the array's real address.
        text = "int foo_401999[] = { 1 };\n"
        old = dict(vt.RENAME_MAP)
        vt.RENAME_MAP["foo_401999"] = 0x402000
        try:
            a = list(vt.find_arrays(Path("x.c"), text))[0]
            self.assertEqual(a.addr, 0x402000)
        finally:
            vt.RENAME_MAP.clear()
            vt.RENAME_MAP.update(old)


class VerifyTest(unittest.TestCase):
    def _run(self, text, data_va, data_bytes, allowlist=None):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "x.c"
            src.write_text(text)
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, data_va, data_bytes)
            img = vt.OriginalImage(exe)
            return vt.verify([src], img, allowlist or {})

    def test_matching_array_reports_no_mismatch(self):
        text = "int foo_445000[] = { 1, 2, 3 };\n"
        data = struct.pack("<3i", 1, 2, 3)
        scanned, mismatches, unparsed, skipped, allow = self._run(text, 0x45000, data)
        self.assertEqual(scanned, 1)
        self.assertEqual(mismatches, [])

    def test_single_element_typo_is_caught(self):
        # The whole point of this tool (see FINDINGS.md): a one-element
        # hand-typing slip, indistinguishable from correct code by eye or by
        # check-equiv (it never runs the original to compare), must be
        # reported precisely -- which array, which index, both values.
        text = "int foo_445000[] = { 1, 2, 4 };\n"  # last element should be 3
        data = struct.pack("<3i", 1, 2, 3)
        scanned, mismatches, unparsed, skipped, allow = self._run(text, 0x45000, data)
        self.assertEqual(len(mismatches), 1)
        arr, rel, idx, ours, orig = mismatches[0]
        self.assertEqual(arr.name, "foo_445000")
        self.assertEqual(idx, 2)
        self.assertEqual(ours, 4)
        self.assertEqual(orig, 3)

    def test_allowlisted_array_is_skipped_not_reported(self):
        text = "int foo_445000[] = { 1, 2, 4 };\n"
        data = struct.pack("<3i", 1, 2, 3)
        scanned, mismatches, unparsed, skipped, allow = self._run(
            text, 0x45000, data, allowlist={"foo_445000": "known layout gap"})
        self.assertEqual(mismatches, [])
        self.assertEqual(len(allow), 1)

    def test_address_outside_any_section_is_skipped_not_a_mismatch(self):
        text = "int foo_500000[] = { 1 };\n"  # 0x500000 is not backed by any section here
        data = struct.pack("<i", 1)
        scanned, mismatches, unparsed, skipped, allow = self._run(text, 0x45000, data)
        self.assertEqual(mismatches, [])
        self.assertEqual(len(skipped), 1)

    def test_typo_in_a_later_string_row_is_caught_at_its_address(self):
        text = 'char foo_445000[2][4] = { "AB", "CE" };\n'  # row 1 should be "CD"
        data = b"AB\0\0CD\0\0"
        scanned, mismatches, unparsed, skipped, allow = self._run(text, 0x45000, data)
        self.assertEqual(len(mismatches), 1)
        arr, rel, idx, ours, orig = mismatches[0]
        self.assertEqual((idx, ours, orig), (5, ord("E"), ord("D")))
        self.assertEqual(arr.orig_addr(idx), 0x445005)

    def test_float_array_compares_ieee754(self):
        text = "float foo_445000[] = { 1.5, -2.25 };\n"
        data = struct.pack("<2f", 1.5, -2.25)
        scanned, mismatches, unparsed, skipped, allow = self._run(text, 0x45000, data)
        self.assertEqual(mismatches, [])

    def test_main_exits_nonzero_on_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "x.c"
            src.write_text("int foo_445000[] = { 1, 2, 4 };\n")
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, 0x45000, struct.pack("<3i", 1, 2, 3))
            rc = vt.main(["verify-tables.py", "--exe", str(exe), str(src)])
        self.assertEqual(rc, 1)

    def test_unparsed_array_is_counted_not_compared(self):
        text = "int foo_445000[2] = { 1, 2, 3 };\n"
        data = struct.pack("<3i", 1, 2, 3)
        scanned, mismatches, unparsed, skipped, allow = self._run(text, 0x45000, data)
        self.assertEqual((scanned, mismatches), (1, []))
        self.assertEqual([a.name for a, _rel in unparsed], ["foo_445000"])

    def test_main_exits_nonzero_on_an_unparsed_array(self):
        # Even when nothing mismatches: an array that could not be checked
        # must fail the run, or `make verify-tables` passes without it.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "x.c"
            src.write_text("int foo_445000[] = { 1 };\nint bar_445004[] = { FOO };\n")
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, 0x45000, struct.pack("<2i", 1, 2))
            rc = vt.main(["verify-tables.py", "--exe", str(exe), str(src)])
        self.assertEqual(rc, 1)

    def test_main_exits_zero_when_equivalent(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "x.c"
            src.write_text("int foo_445000[] = { 1, 2, 3 };\n")
            exe = Path(tmp) / "dr.exe"
            make_pe(exe, 0x45000, struct.pack("<3i", 1, 2, 3))
            rc = vt.main(["verify-tables.py", "--exe", str(exe), str(src)])
        self.assertEqual(rc, 0)


class StrideTest(unittest.TestCase):
    """The original's menu layout is one int table, a row of 7 ints per menu
    type (stride 0x1C); the port keeps each column as its own array indexed
    by menu type. These columns used to be allowlisted as "wrong stride",
    which hid three hand-typed typos in the popup-height column (the Define
    Keyboard popup was 74 px too tall). A strided column must be compared at
    addr + stride * i, so that a one-element typo in it is still caught."""

    # 3 rows x 2 ints, row-major like the original: column 1 is {20, 21, 22}.
    TABLE = struct.pack("<6i", 10, 20, 11, 21, 12, 22)

    def _run(self, text, strides):
        old = dict(vt.STRIDE)
        vt.STRIDE.clear()
        vt.STRIDE.update(strides)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "x.c"
                src.write_text(text)
                exe = Path(tmp) / "dr.exe"
                make_pe(exe, 0x45000, self.TABLE)
                return vt.verify([src], vt.OriginalImage(exe), {})
        finally:
            vt.STRIDE.clear()
            vt.STRIDE.update(old)

    def test_correct_column_matches_at_its_stride(self):
        text = "int col_445004[] = { 20, 21, 22 };\n"
        scanned, mismatches, unparsed, skipped, allow = self._run(text, {"col_445004": 8})
        self.assertEqual(scanned, 1)
        self.assertEqual(mismatches, [])

    def test_one_element_typo_in_a_strided_column_is_caught(self):
        text = "int col_445004[] = { 20, 21, 23 };\n"  # last element should be 22
        scanned, mismatches, unparsed, skipped, allow = self._run(text, {"col_445004": 8})
        self.assertEqual(len(mismatches), 1)
        arr, rel, idx, ours, orig = mismatches[0]
        self.assertEqual((idx, ours, orig), (2, 23, 22))
        self.assertEqual(arr.orig_addr(idx), 0x445004 + 2 * 8)

    def test_without_its_stride_a_correct_column_reads_the_wrong_row(self):
        # Why the map is needed at all: read contiguously, the column is
        # compared against its neighbours in the same row.
        text = "int col_445004[] = { 20, 21, 22 };\n"
        scanned, mismatches, unparsed, skipped, allow = self._run(text, {})
        self.assertEqual(len(mismatches), 2)

    def test_menu_layout_columns_are_strided_not_allowlisted(self):
        for name in ("dword_4456F0", "dword_4456F4", "dword_4456F8", "dword_4456FC",
                     "dword_445700", "dword_445704", "dword_445708"):
            self.assertEqual(vt.STRIDE.get(name), 0x1C, name)
            self.assertNotIn(name, vt.ALLOWLIST)


if __name__ == "__main__":
    unittest.main()
