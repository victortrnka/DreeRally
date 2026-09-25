"""Tests for equiv.py: why they matter is that a false EQUIVALENT would let a
behaviour change slip into a refactor commit unnoticed."""
import struct
import tempfile
import unittest
from pathlib import Path

import equiv

IMAGE_BASE = 0x400000


def make_pe(path, sections):
    """Write a minimal PE32 image. sections: list of (name, va, raw_bytes)."""
    pe_offset = 0x40
    opt_size = 0xE0
    header = bytearray(0x400)
    struct.pack_into("<I", header, 0x3C, pe_offset)
    header[pe_offset:pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<HH", header, pe_offset + 4, 0x14C, len(sections))
    struct.pack_into("<H", header, pe_offset + 20, opt_size)
    opt = pe_offset + 24
    struct.pack_into("<H", header, opt, 0x10B)
    struct.pack_into("<I", header, opt + 28, IMAGE_BASE)
    table = opt + opt_size
    body = bytearray()
    raw_ptr = len(header)
    for i, (name, va, raw) in enumerate(sections):
        entry = table + 40 * i
        header[entry:entry + 8] = name.encode().ljust(8, b"\0")
        struct.pack_into("<IIII", header, entry + 8, len(raw), va, len(raw), raw_ptr + len(body))
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


if __name__ == "__main__":
    unittest.main()
