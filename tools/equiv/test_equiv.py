"""Tests for equiv.py: why they matter is that a false EQUIVALENT would let a
behaviour change slip into a refactor commit unnoticed."""
import struct
import tempfile
import unittest
from pathlib import Path

import equiv

IMAGE_BASE = 0x400000

# A minimal, well-formed .reloc section: one page header plus a single
# ABSOLUTE (type 0) padding entry, which parse_base_relocations() ignores.
# Present by default because equiv.py now refuses to run without a .reloc
# section at all -- most tests don't care about relocations
# and just need one to exist; write_build(reloc=None) opts out for the one
# that does.
DEFAULT_RELOC = struct.pack("<IIH", 0x1000, 8 + 2, 0)


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


def write_build(folder, text, symbols, data=b"\0" * 16, reloc=DEFAULT_RELOC):
    """reloc=None omits the .reloc section entirely (only used to test that
    equiv.py refuses to run without one)."""
    folder.mkdir(parents=True, exist_ok=True)
    sections = [(".text", 0x1000, text), (".data", 0x2000, data)]
    if reloc is not None:
        sections.append((".reloc", 0x3000, reloc))
    make_pe(folder / "dreerally.exe", sections)
    lines = [" dreerally", "", "  Address         Publics by Value              Rva+Base               Lib:Object", ""]
    lines += [map_line(*s) for s in symbols]  # (va, name) or (va, name, obj)
    lines += ["", " 0001:00000000 00000020H .text                   CODE"]
    (folder / "dreerally.map").write_text("\n".join(lines) + "\n")
    return folder / "dreerally.exe"


def objdump_line(addr, raw_bytes, mnemonic, operand=""):
    """One line exactly as `llvm-objdump -d -M intel` prints it (raw bytes
    shown): address, space-separated hex byte pairs, a tab,
    then the disassembly text."""
    text = mnemonic if not operand else mnemonic + "\t" + operand
    return "  %06x: %s\t%s" % (addr, raw_bytes.hex(" "), text)


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
        # _c sits first and never moves. _a grows by one NOP, which shifts
        # _b (a direct "call _c", E8 rel32) one byte later; the rel32
        # encoding is computed from _b's own (now different) address, so
        # _b's raw bytes differ even though its behaviour -- "call _c" --
        # did not: this is the case the footprint listing exists for.
        # A direct call target is always an address (rule a), so this needs
        # no real .reloc data to normalize correctly (the default minimal
        # one from write_build is enough to satisfy the fail-loud check).
        with tempfile.TemporaryDirectory() as tmp:
            base_text = b"\xC3" + b"\x90" + b"\xE8" + struct.pack("<i", -7)
            work_text = b"\xC3" + b"\x90\x90" + b"\xE8" + struct.pack("<i", -8)
            base = write_build(Path(tmp) / "base", base_text,
                               [(0x401000, "_c"), (0x401001, "_a"), (0x401002, "_b")])
            work = write_build(Path(tmp) / "work", work_text,
                               [(0x401000, "_c"), (0x401001, "_a"), (0x401003, "_b")])
            same, report = equiv.compare(base, work)
        self.assertFalse(same)
        text = "\n".join(report)
        self.assertIn("functions changed (real): 1", text)
        self.assertNotIn("_b", text)
        self.assertIn("moved-only", text)


class LibraryFunctionsTest(unittest.TestCase):
    def test_library_function_is_counted_not_listed(self):
        # A "lib...:" map obj marks a prebuilt library member (CRT, SDL,
        # etc.), not one of the game's own .obj files. These are frequently
        # compiler-generated jump/lookup tables that disassemble as
        # meaningless garbage, so
        # printing them individually just reintroduces noise -- but a real
        # change there must still be visible as a count, not silently
        # dropped.
        with tempfile.TemporaryDirectory() as tmp:
            base = write_build(Path(tmp) / "base", b"\x90" * 16,
                               [(0x401000, "$LN1", "libvcruntime:memcmp.obj")])
            work = write_build(Path(tmp) / "work", b"\x90" * 15 + b"\xcc",
                               [(0x401000, "$LN1", "libvcruntime:memcmp.obj")])
            same, report = equiv.compare(base, work)
        self.assertFalse(same)
        text = "\n".join(report)
        self.assertNotIn("$LN1", text)
        self.assertIn("functions with different bytes: 0", text)
        self.assertIn("library functions with different bytes: 1 (not listed, 1 changed after normalization)", text)


class RelocSectionRequiredTest(unittest.TestCase):
    def test_missing_reloc_section_fails_loudly(self):
        # equiv.py now needs the base relocations to tell an address from a
        # literal; silently treating a missing .reloc as "no
        # relocations" would quietly turn every relocated data reference
        # into a literal and resurrect the false positives rule b fixed.
        # It must fail loudly instead.
        with tempfile.TemporaryDirectory() as tmp:
            base = write_build(Path(tmp) / "base", b"\x90" * 32,
                               [(0x401000, "_first"), (0x401010, "_second")], reloc=None)
            work = write_build(Path(tmp) / "work", b"\x90" * 16 + b"\xcc" + b"\x90" * 15,
                               [(0x401000, "_first"), (0x401010, "_second")], reloc=None)
            with self.assertRaises(SystemExit):
                equiv.compare(base, work)


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
        # Same call, same relocated data read; only the callee/data addresses
        # shifted (as every later symbol does when an earlier function's
        # size changes). Must normalize identically across builds. The call
        # target needs no reloc entry (direct branch, rule a); the data
        # read does (rule b): its disp32 field is at instr_addr+2.
        base_symbols = [(0x401000, "_caller", "x.obj"), (0x420000, "_callee", "x.obj"),
                        (0x4b0000, "_table", "x.obj")]
        work_symbols = [(0x401000, "_caller", "x.obj"), (0x420010, "_callee", "x.obj"),
                        (0x4b0010, "_table", "x.obj")]
        base_lines = [
            objdump_line(0x401000, b"\xE8\x00\x00\x00\x00", "call", "0x420000 <.text+0x1f000>"),
            objdump_line(0x401005, b"\x8b\x05" + struct.pack("<I", 0x4b0000), "mov", "eax, dword ptr [0x4b0000]"),
        ]
        work_lines = [
            objdump_line(0x401000, b"\xE8\x00\x00\x00\x00", "call", "0x420010 <.text+0x1f010>"),
            objdump_line(0x401005, b"\x8b\x05" + struct.pack("<I", 0x4b0010), "mov", "eax, dword ptr [0x4b0010]"),
        ]
        base_norm = equiv.normalize(base_lines, 0x401000, 0x401010, base_symbols, IMAGE_LO, IMAGE_HI, [0x401007])
        work_norm = equiv.normalize(work_lines, 0x401000, 0x401010, work_symbols, IMAGE_LO, IMAGE_HI, [0x401007])
        self.assertEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["call _callee+0x0", "mov eax, dword ptr [_table+0x0]"])

    def test_changed_immediate_is_a_change(self):
        symbols = [(0x401000, "_f", "x.obj")]
        base = [objdump_line(0x401000, b"\xB8\x05\x00\x00\x00", "mov", "eax, 0x5")]
        work = [objdump_line(0x401000, b"\xB8\x06\x00\x00\x00", "mov", "eax, 0x6")]
        base_norm = equiv.normalize(base, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        work_norm = equiv.normalize(work, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        self.assertNotEqual(base_norm, work_norm)

    def test_call_to_different_symbol_is_a_change(self):
        # Both targets are "addresses" that would survive relocation on
        # their own; the point is the call moved from one real function to
        # another one, which normalize() must not paper over.
        symbols = [(0x401000, "_f", "x.obj"), (0x420000, "_foo", "x.obj"), (0x430000, "_bar", "x.obj")]
        base = [objdump_line(0x401000, b"\xE8\x00\x00\x00\x00", "call", "0x420000 <.text+0x1f000>")]
        work = [objdump_line(0x401000, b"\xE8\x00\x00\x00\x00", "call", "0x430000 <.text+0x2f000>")]
        base_norm = equiv.normalize(base, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        work_norm = equiv.normalize(work, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        self.assertNotEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["call _foo+0x0"])
        self.assertEqual(work_norm, ["call _bar+0x0"])

    def test_intrafunction_jump_uses_function_relative_offset(self):
        symbols = [(0x401000, "_f", "x.obj"), (0x401020, "_g", "x.obj")]
        lines = [objdump_line(0x401000, b"\xE9\x00\x00\x00\x00", "jmp", "0x401010 <.text+0x10>")]
        norm = equiv.normalize(lines, 0x401000, 0x401020, symbols, IMAGE_LO, IMAGE_HI, [])
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
            objdump_line(0x401000, b"\xC3", "ret"),
        ]
        norm = equiv.normalize(lines, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        self.assertEqual(norm, ["ret"])

    def test_relocated_data_target_that_moved_is_still_moved_only(self):
        # Rule (b): an absolute address embedded as data is only an address
        # if the specific 4-byte field it is encoded in carries a base
        # relocation. Here it does (the disp32 field at instr_addr+2), so
        # the moved target still normalizes to the same symbol+offset.
        base_symbols = [(0x401000, "_f", "x.obj"), (0x4b0000, "_table", "x.obj")]
        work_symbols = [(0x401000, "_f", "x.obj"), (0x4b0010, "_table", "x.obj")]
        base_lines = [objdump_line(0x401000, b"\x8b\x05" + struct.pack("<I", 0x4b0000), "mov",
                                   "eax, dword ptr [0x4b0000]")]
        work_lines = [objdump_line(0x401000, b"\x8b\x05" + struct.pack("<I", 0x4b0010), "mov",
                                   "eax, dword ptr [0x4b0010]")]
        base_norm = equiv.normalize(base_lines, 0x401000, 0x401010, base_symbols, IMAGE_LO, IMAGE_HI, [0x401002])
        work_norm = equiv.normalize(work_lines, 0x401000, 0x401010, work_symbols, IMAGE_LO, IMAGE_HI, [0x401002])
        self.assertEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["mov eax, dword ptr [_table+0x0]"])

    def test_unrelocated_literal_that_stayed_identical_is_not_reported(self):
        # An earlier false positive, reproduced directly:
        # selectRaceScreen/drawStadistics compared against a frozen 32-bit
        # literal that happens to numerically fall in the image but carries
        # no base relocation. Its nearest symbol moved, but since no reloc
        # covers this literal's own encoding, it is never resolved against
        # that symbol at all -- it stays byte-for-byte identical text on
        # both sides, so it must not be reported.
        symbols_base = [(0x401000, "_f", "x.obj"), (0x420000, "_anchor", "x.obj")]
        symbols_work = [(0x401000, "_f", "x.obj"), (0x41ffa0, "_anchor", "x.obj")]  # _anchor moved -0x60
        raw = b"\x81\x7d\xb4" + struct.pack("<I", 0x44d000)  # illustrative cmp [ebp-N], imm32
        lines = [objdump_line(0x401000, raw, "cmp", "dword ptr [ebp - 0x14c], 0x44d000")]
        base_norm = equiv.normalize(lines, 0x401000, 0x401010, symbols_base, IMAGE_LO, IMAGE_HI, [])
        work_norm = equiv.normalize(lines, 0x401000, 0x401010, symbols_work, IMAGE_LO, IMAGE_HI, [])
        self.assertEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["cmp dword ptr [ebp - 0x14c], 0x44d000"])

    def test_unrelocated_literal_that_changed_is_reported(self):
        # An unrelocated literal is compared verbatim, so a real edit to it
        # must still be caught, same as any other immediate.
        symbols = [(0x401000, "_f", "x.obj")]
        base = [objdump_line(0x401000, b"\x3d" + struct.pack("<I", 0x44d000), "cmp", "eax, 0x44d000")]
        work = [objdump_line(0x401000, b"\x3d" + struct.pack("<I", 0x44d100), "cmp", "eax, 0x44d100")]
        base_norm = equiv.normalize(base, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        work_norm = equiv.normalize(work, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [])
        self.assertNotEqual(base_norm, work_norm)

    def test_collision_unrelocated_immediate_next_to_relocated_destination_is_reported(self):
        # The per-instruction false negative: `mov dword ptr [DEST],
        # IMM` where DEST is a real relocated address and IMM is a plain
        # constant that happens to shift by exactly the same delta as some
        # nearby anchor symbol. Under the old per-INSTRUCTION reloc
        # decision (af8d5ee), the whole instruction was "relocated" because
        # of DEST, so IMM was wrongly resolved against the anchor too, and
        # the two builds' resolved offsets matched even though IMM
        # genuinely changed -- the change vanished. Per-operand resolution
        # must catch it: only DEST's own 4-byte field has a relocation, so
        # IMM is compared as a literal and the change is visible.
        symbols_base = [(0x401000, "_f", "x.obj"), (0x420000, "_anchor", "x.obj"), (0x4c06e9, "_table", "x.obj")]
        symbols_work = [(0x401000, "_f", "x.obj"), (0x420020, "_anchor", "x.obj"), (0x4c06e9, "_table", "x.obj")]
        dest = 0x4c06e9  # unchanged; always resolves to _table+0x0 regardless of _anchor
        base_imm = 0x420005  # = _anchor(base) + 0x5
        work_imm = 0x420025  # = _anchor(work) + 0x5 -- same *resolved* offset if wrongly treated as an address
        base_raw = b"\xC7\x05" + struct.pack("<I", dest) + struct.pack("<I", base_imm)
        work_raw = b"\xC7\x05" + struct.pack("<I", dest) + struct.pack("<I", work_imm)
        base_lines = [objdump_line(0x401000, base_raw, "mov", "dword ptr [0x%x], 0x%x" % (dest, base_imm))]
        work_lines = [objdump_line(0x401000, work_raw, "mov", "dword ptr [0x%x], 0x%x" % (dest, work_imm))]
        reloc = [0x401002]  # only DEST's disp32 field (instr_addr+2) is relocated
        base_norm = equiv.normalize(base_lines, 0x401000, 0x401010, symbols_base, IMAGE_LO, IMAGE_HI, reloc)
        work_norm = equiv.normalize(work_lines, 0x401000, 0x401010, symbols_work, IMAGE_LO, IMAGE_HI, reloc)
        self.assertNotEqual(base_norm, work_norm)

    def test_mixed_instruction_with_only_relocated_part_moved_is_moved_only(self):
        # Complement of the collision case: DEST (relocated) moves
        # consistently with its own target symbol, IMM (not relocated) is a
        # genuine constant that never changes. The instruction's raw bytes
        # differ (DEST's encoding changed) but its behaviour did not.
        symbols_base = [(0x401000, "_f", "x.obj"), (0x4c06e9, "_table", "x.obj")]
        symbols_work = [(0x401000, "_f", "x.obj"), (0x4c0709, "_table", "x.obj")]  # _table moved +0x20
        imm = 0x676e69  # unrelated constant, unchanged
        base_dest, work_dest = 0x4c06e9, 0x4c0709
        base_raw = b"\xC7\x05" + struct.pack("<I", base_dest) + struct.pack("<I", imm)
        work_raw = b"\xC7\x05" + struct.pack("<I", work_dest) + struct.pack("<I", imm)
        base_lines = [objdump_line(0x401000, base_raw, "mov", "dword ptr [0x%x], 0x%x" % (base_dest, imm))]
        work_lines = [objdump_line(0x401000, work_raw, "mov", "dword ptr [0x%x], 0x%x" % (work_dest, imm))]
        base_norm = equiv.normalize(base_lines, 0x401000, 0x401010, symbols_base, IMAGE_LO, IMAGE_HI, [0x401002])
        work_norm = equiv.normalize(work_lines, 0x401000, 0x401010, symbols_work, IMAGE_LO, IMAGE_HI, [0x401002])
        self.assertEqual(base_norm, work_norm)
        self.assertEqual(base_norm, ["mov dword ptr [_table+0x0], 0x676e69"])

    def test_encoding_not_found_falls_back_to_literal_and_is_counted(self):
        # A token in the text with no matching 4-byte LE window anywhere in
        # the instruction's own raw bytes (e.g. a narrower encoding, or an
        # objdump-computed display value) must be treated as a literal, not
        # guessed at -- and the fallback must be visible via `stats` so an
        # unexpectedly high not-found rate can be noticed.
        symbols = [(0x401000, "_f", "x.obj")]
        raw = b"\x90\x90\x90\x90"  # no bytes anywhere encode 0x44d000
        lines = [objdump_line(0x401000, raw, "cmp", "eax, 0x44d000")]
        stats = {"found": 0, "not_found": 0}
        norm = equiv.normalize(lines, 0x401000, 0x401010, symbols, IMAGE_LO, IMAGE_HI, [], stats)
        self.assertEqual(norm, ["cmp eax, 0x44d000"])
        self.assertEqual(stats, {"found": 0, "not_found": 1})


class RelocationsTest(unittest.TestCase):
    def test_parses_highlow_entries_and_skips_absolute_padding(self):
        # One block covering page 0x1000: a HIGHLOW (type 3) fixup at page
        # offset 0x008, then an ABSOLUTE (type 0) entry, which the linker
        # only ever uses to pad a block to a WORD count and which must not
        # be reported as a relocation.
        block = struct.pack("<IIHH", 0x1000, 8 + 2 * 2, (3 << 12) | 0x008, (0 << 12) | 0x000)
        vas = equiv.parse_base_relocations(block, 0x400000)
        self.assertEqual(vas, [0x401008])


if __name__ == "__main__":
    unittest.main()
