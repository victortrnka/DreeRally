"""Tests for equiv.py: why they matter is that a false EQUIVALENT would let a
behaviour change slip into a refactor commit unnoticed."""
import struct
import tempfile
import unittest
from pathlib import Path

import equiv

IMAGE_BASE = 0x400000


def make_pe(path, sections):
    """Write a minimal PE32 image. sections: list of (name, va, raw_bytes).

    Real enough for llvm-objdump to disassemble: an "MZ" stub (objdump's PE
    reader ignores everything else about it but requires the signature) and
    IMAGE_SCN_CNT_CODE|MEM_EXECUTE|MEM_READ on every section.
    """
    pe_offset = 0x40
    opt_size = 0xE0
    header = bytearray(0x400)
    header[0:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, pe_offset)
    header[pe_offset:pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<HH", header, pe_offset + 4, 0x14C, len(sections))
    struct.pack_into("<H", header, pe_offset + 20, opt_size)
    opt = pe_offset + 24
    struct.pack_into("<H", header, opt, 0x10B)
    struct.pack_into("<I", header, opt + 28, IMAGE_BASE)
    struct.pack_into("<I", header, opt + 56, 0x100000)  # SizeOfImage
    table = opt + opt_size
    body = bytearray()
    raw_ptr = len(header)
    for i, (name, va, raw) in enumerate(sections):
        entry = table + 40 * i
        header[entry:entry + 8] = name.encode().ljust(8, b"\0")
        struct.pack_into("<IIII", header, entry + 8, len(raw), va, len(raw), raw_ptr + len(body))
        struct.pack_into("<I", header, entry + 36, 0x60000020)  # section characteristics
        body += raw
    Path(path).write_bytes(bytes(header) + bytes(body))


def map_line(va, name, obj="dr.obj"):
    """One symbol line exactly as lld-link /map writes it (lld/COFF/MapFile.cpp)."""
    return " 0001:%08x       %-26s %016x     %s" % (va - IMAGE_BASE - 0x1000, name, va, obj)


def write_build(folder, text, symbols, data=b"\0" * 16):
    folder.mkdir(parents=True, exist_ok=True)
    make_pe(folder / "dreerally.exe", [(".text", 0x1000, text), (".data", 0x2000, data)])
    lines = [" dreerally", "", "  Address         Publics by Value              Rva+Base               Lib:Object", ""]
    lines += [map_line(va, name) for va, name in symbols]
    lines += ["", " 0001:00000000 00000020H .text                   CODE"]
    (folder / "dreerally.map").write_text("\n".join(lines) + "\n")
    return folder / "dreerally.exe"


class ReadMapTest(unittest.TestCase):
    def test_parses_lld_symbol_lines_and_ignores_section_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = write_build(Path(tmp) / "a", b"\x90" * 32, [(0x401010, "_b"), (0x401000, "_a")])
            symbols = equiv.read_map(exe.with_suffix(".map"))
        self.assertEqual(symbols, [(0x401000, "_a", "dr.obj"), (0x401010, "_b", "dr.obj")])


class FunctionsInTest(unittest.TestCase):
    def test_end_is_next_symbol_and_aliases_collapse(self):
        symbols = [(0x401000, "_a", "x.obj"), (0x401000, "_alias", "x.obj"),
                   (0x401010, "_b", "x.obj"), (0x402000, "_data", "x.obj")]
        functions = equiv.functions_in(symbols, 0x401000, 0x401020)
        self.assertEqual(functions, [(0x401000, 0x401010, "_alias", "x.obj"),
                                     (0x401010, 0x401020, "_b", "x.obj")])


class CompareTest(unittest.TestCase):
    def test_renamed_symbols_with_identical_bytes_are_equivalent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = write_build(Path(tmp) / "base", b"\x90" * 32, [(0x401000, "_sub_401000")])
            work = write_build(Path(tmp) / "work", b"\x90" * 32, [(0x401000, "_drawCar")])
            same, report = equiv.compare(base, work)
        self.assertTrue(same)
        self.assertEqual(report, ["EQUIVALENT"])

    def test_changed_code_names_the_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = write_build(Path(tmp) / "base", b"\x90" * 32,
                               [(0x401000, "_first"), (0x401010, "_second")])
            work = write_build(Path(tmp) / "work", b"\x90" * 16 + b"\xcc" + b"\x90" * 15,
                               [(0x401000, "_first"), (0x401010, "_second")])
            same, report = equiv.compare(base, work)
        self.assertFalse(same)
        text = "\n".join(report)
        self.assertIn("DIFFERENT", text)
        self.assertIn("_second", text)
        self.assertNotIn("_first", text)

    def test_changed_data_is_reported_even_when_code_is_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = write_build(Path(tmp) / "base", b"\x90" * 32, [(0x401000, "_a")], data=b"\0" * 16)
            work = write_build(Path(tmp) / "work", b"\x90" * 32, [(0x401000, "_a")], data=b"\1" + b"\0" * 15)
            same, report = equiv.compare(base, work)
        self.assertFalse(same)
        self.assertIn(".data", "\n".join(report))

    def test_moved_only_function_is_not_reported_as_changed(self):
        # _a grows by one NOP, which shifts _b (a plain "mov eax, &_c" with no
        # symbol renamed) one byte later. _b's raw bytes therefore differ
        # (the embedded address changed), but its behaviour did not: this is
        # the case the footprint listing exists for. _c's own byte (ret)
        # never moves relative to itself, so it never even reaches the
        # disassembly step.
        with tempfile.TemporaryDirectory() as tmp:
            base_text = b"\x90" + b"\xB8" + struct.pack("<I", 0x401006) + b"\xC3"
            work_text = b"\x90\x90" + b"\xB8" + struct.pack("<I", 0x401007) + b"\xC3"
            base = write_build(Path(tmp) / "base", base_text,
                               [(0x401000, "_a"), (0x401001, "_b"), (0x401006, "_c")])
            work = write_build(Path(tmp) / "work", work_text,
                               [(0x401000, "_a"), (0x401002, "_b"), (0x401007, "_c")])
            same, report = equiv.compare(base, work)
        self.assertFalse(same)
        text = "\n".join(report)
        self.assertIn("functions changed (real): 1", text)
        self.assertNotIn("_b", text)
        self.assertIn("moved-only", text)


IMAGE_LO = 0x400000
IMAGE_HI = 0x900000


class NormalizeTest(unittest.TestCase):
    """normalize() answers 'did this function's own behaviour change?',
    independent of where it (or anything it calls/reads) landed in the
    image. A false 'no change' here would let a real edit hide inside the
    moved-only bucket; a false 'changed' would drown each fix's
    footprint check back in the address-shift noise this tool exists to
    remove."""

    def test_moved_call_and_data_target_is_not_a_change(self):
        # Same call, same data read; only the callee/data addresses shifted
        # (as every later symbol does when an earlier function's size
        # changes). Must normalize identically across builds.
        base_symbols = [(0x401000, "_caller", "x.obj"), (0x420000, "_callee", "x.obj"),
                        (0x4b0000, "_table", "x.obj")]
        work_symbols = [(0x401000, "_caller", "x.obj"), (0x420010, "_callee", "x.obj"),
                        (0x4b0010, "_table", "x.obj")]
        base_lines = [
            "  401000:      \tcall\t0x420000 <.text+0x1f000>",
            "  401005:      \tmov\teax, dword ptr [0x4b0000]",
        ]
        work_lines = [
            "  401000:      \tcall\t0x420010 <.text+0x1f010>",
            "  401005:      \tmov\teax, dword ptr [0x4b0010]",
        ]
        base_norm = equiv.normalize(base_lines, 0x401000, 0x401010, base_symbols, IMAGE_LO, IMAGE_HI)
        work_norm = equiv.normalize(work_lines, 0x401000, 0x401010, work_symbols, IMAGE_LO, IMAGE_HI)
        self.assertEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["call _callee+0x0", "mov eax, dword ptr [_table+0x0]"])

    def test_changed_immediate_is_a_change(self):
        symbols = [(0x401000, "_f", "x.obj")]
        base = ["  401000:      \tmov\teax, 0x5"]
        work = ["  401000:      \tmov\teax, 0x6"]
        base_norm = equiv.normalize(base, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI)
        work_norm = equiv.normalize(work, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI)
        self.assertNotEqual(base_norm, work_norm)

    def test_call_to_different_symbol_is_a_change(self):
        # Both targets are "addresses" that would survive relocation on
        # their own; the point is the call moved from one real function to
        # another one, which normalize() must not paper over.
        symbols = [(0x401000, "_f", "x.obj"), (0x420000, "_foo", "x.obj"), (0x430000, "_bar", "x.obj")]
        base = ["  401000:      \tcall\t0x420000 <.text+0x1f000>"]
        work = ["  401000:      \tcall\t0x430000 <.text+0x2f000>"]
        base_norm = equiv.normalize(base, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI)
        work_norm = equiv.normalize(work, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI)
        self.assertNotEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["call _foo+0x0"])
        self.assertEqual(work_norm, ["call _bar+0x0"])

    def test_intrafunction_jump_uses_function_relative_offset(self):
        symbols = [(0x401000, "_f", "x.obj"), (0x401020, "_g", "x.obj")]
        lines = ["  401000:      \tjmp\t0x401010 <.text+0x10>"]
        norm = equiv.normalize(lines, 0x401000, 0x401020, symbols, IMAGE_LO, IMAGE_HI)
        self.assertEqual(norm, ["jmp .+0x10"])

    def test_non_instruction_lines_are_not_part_of_the_listing(self):
        # A parser regression that let a header/label line through would
        # silently pad every normalized list, hiding real diffs behind a
        # constant offset.
        symbols = [(0x401000, "_f", "x.obj")]
        lines = [
            "",
            "dreerally.exe:\tfile format coff-i386",
            "",
            "Disassembly of section .text:",
            "",
            "00401000 <.text>:",
            "  401000:      \tret",
        ]
        norm = equiv.normalize(lines, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI)
        self.assertEqual(norm, ["ret"])


if __name__ == "__main__":
    unittest.main()
