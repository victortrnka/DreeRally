"""Tests for signcheck.py: why they matter is that a signed value read as
unsigned (a `shr` where the original has `sar`, a `jb` where it has `jl`)
is wildly wrong once the value is negative, and nothing else looks for it
-- see doc/FINDINGS.md, "Unsigned `_DWORD` where the original uses `sar`".
A pairing or classification slip here hides such a bug, and an idiom
counted as a signedness signal buries the real ones in noise."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signcheck as sc  # noqa: E402

MARKER = "//----- (%08X) --------------------------------------------------------"


def insns(text):
    """'mnemonic operands' lines -> [(address, mnemonic, operands)]."""
    out = []
    for n, line in enumerate(l.strip() for l in text.strip().splitlines()):
        mnemonic, _, operands = line.partition(" ")
        out.append((0x1000 + 4 * n, mnemonic, operands.strip()))
    return out


def count(text):
    return sc.counts(sc.classify(insns(text)))


class MarkersTest(unittest.TestCase):
    def test_function_right_after_marker(self):
        text = MARKER % 0x415710 + "\nvoid startRace(int a1)\n{\n}\n"
        self.assertEqual(list(sc.markers_in(text)), [(0x415710, "startRace", True)])

    def test_any_number_of_comment_lines_before_the_definition(self):
        # ui/menu.c: drawMenu's marker is followed by five comment lines and a
        # blank one; a fixed lookahead dropped it, leaving it unchecked.
        text = (MARKER % 0x41A880 + "\n\n//pinta el menu\n//menu type\n// 0 es el menu principal\n"
                "// 1 es comenzar racing\n// 2 ...\nint   drawMenu(int menuType, int top)\n{\n}\n")
        self.assertEqual(list(sc.markers_in(text)), [(0x41A880, "drawMenu", True)])

    def test_commented_signature_names_a_moved_function_not_the_next_one(self):
        # dr.c: 0x439CD0's marker sits above "//void startRacingMenu()" and then
        # an unrelated port-only function; pairing that one with 0x439CD0
        # would compare it against the wrong original code.
        text = (MARKER % 0x439CD0 + "\n//void startRacingMenu()\n\n"
                "void inicializeGraphicVars() {\n}\n")
        self.assertEqual(list(sc.markers_in(text)), [(0x439CD0, "startRacingMenu", False)])

    def test_marker_above_a_variable_names_nothing(self):
        text = MARKER % 0x402000 + "\nint dword_402000;\n"
        self.assertEqual(list(sc.markers_in(text)), [])


class PairTest(unittest.TestCase):
    LO, HI = 0x401000, 0x441000

    def func(self, name):
        return (0x500000, 0x500010, "_" + name, "dr.obj")

    def test_marker_wins_over_a_disagreeing_suffix_and_is_reported(self):
        f = self.func("shopScreenMoveLeft_421DF0")
        pairs, conflicts, unpaired = sc.pair([f], [(0x42D8C0, "shopScreenMoveLeft_421DF0", True)],
                                             self.LO, self.HI)
        self.assertEqual(pairs, [(0x42D8C0, f, "marker")])
        self.assertEqual(len(conflicts), 1)

    def test_suffix_pairs_a_function_without_marker(self):
        f = self.func("drawCarInRace_40D920")
        pairs, _c, unpaired = sc.pair([f], [], self.LO, self.HI)
        self.assertEqual(pairs, [(0x40D920, f, "suffix")])
        self.assertEqual(unpaired, [])

    def test_data_suffix_outside_text_is_not_an_address(self):
        f = self.func("copy_4A7DBC")
        pairs, _c, unpaired = sc.pair([f], [], self.LO, self.HI)
        self.assertEqual((pairs, unpaired), ([], [f]))

    def test_moved_marker_is_used_only_without_a_live_one(self):
        f = self.func("startRacingMenu")
        markers = [(0x439CD0, "startRacingMenu", False)]
        self.assertEqual(sc.pair([f], markers, self.LO, self.HI)[0], [(0x439CD0, f, "moved")])
        markers.append((0x439CD0, "startRacingMenu", True))
        self.assertEqual(sc.pair([f], markers, self.LO, self.HI)[0], [(0x439CD0, f, "marker")])

    def test_stdcall_and_fastcall_names(self):
        self.assertEqual(sc.plain_name("_WinMain@16"), "WinMain")
        self.assertEqual(sc.plain_name("@fast@8"), "fast")
        self.assertEqual(sc.plain_name("_startRace"), "startRace")


class BoundariesTest(unittest.TestCase):
    def test_call_targets_pointers_and_jump_tables_end_a_function(self):
        code = insns("""
            call 0x402000
            push 0x403000
            jmp dword ptr [4*eax + 0x404000]
            mov eax, dword ptr [0x445000]
        """)
        b = sc.original_boundaries(code, [0x401000], 0x401000, 0x441000)
        # 0x445000 is .data, not a boundary
        self.assertEqual(b, [0x401000, 0x402000, 0x403000, 0x404000])


class ClassifyTest(unittest.TestCase):
    def test_shift_signedness(self):
        self.assertEqual(count("sar eax, 0x8\nshr ecx, 0x3")["shift"], [1, 1])

    def test_masked_shift_is_sign_agnostic(self):
        # regenerateRacePalette (0x43C0F0): (c >> 18) & 0x3F gives the same
        # bits with sar and shr; it must not rank as a candidate.
        self.assertEqual(count("sar edx, 0x12\nand dl, 0x3f\nmov byte ptr [eax], dl")["shift"], [0, 0])
        self.assertEqual(count("shr eax, 0xa\nand eax, 0x3f")["shift"], [0, 0])

    def test_wide_mask_keeps_the_shifted_in_bits(self):
        # 24 + 16 > 32: the top 8 kept bits are sign or zero fill
        self.assertEqual(count("shr eax, 0x18\nand eax, 0xffff")["shift"], [0, 1])

    def test_sign_bit_reads(self):
        c = count("shr eax, 0x1f\nsar ecx, 0x1f")
        self.assertEqual(c["shift"], [0, 0])
        self.assertEqual(c["dividend"], [1, 0])

    def test_port_boolean_movzx_is_not_a_load(self):
        c = count("cmp eax, ecx\nsetl al\nand al, 0x1\nmovzx eax, al\nmovzx ecx, byte ptr [eax]")
        self.assertEqual(c["extend"], [0, 1])
        self.assertEqual(c["compare"], [1, 0])

    def test_port_x87_control_word_is_not_a_load(self):
        c = count("fnstcw word ptr [esp + 0x6e]\nmovzx ecx, word ptr [esp + 0x6e]\nor ecx, 0xc00")
        self.assertEqual(c["extend"], [0, 0])

    def test_sign_flag_conditions_are_signed(self):
        # refreshScreen (0x43B8CA): the original tests SDL_FULLSCREEN with
        # cmp [surface], 0; jns where the port compared unsigned (jae)
        self.assertEqual(count("cmp dword ptr [eax], 0x0\njns 0x1000\ntest eax, eax\njs 0x1000")["compare"], [2, 0])

    def test_masked_extension_is_sign_agnostic(self):
        # dr.c recalculateCarBoundary: `keys[frame] & IN_RACE_ACELERATE`
        self.assertEqual(count("movsx eax, byte ptr [eax + ecx + 0x20]\nand eax, 0x1\ncmp eax, 0x0")["extend"], [0, 0])
        self.assertEqual(count("movsx eax, byte ptr [ecx]\nand eax, 0x1ff")["extend"], [1, 0])

    def test_float_compare_conditions_are_ignored(self):
        c = count("ucomiss xmm0, xmm1\nmovss xmm0, dword ptr [esp]\njbe 0x1000\ncmp eax, ecx\njb 0x1000")
        self.assertEqual(c["compare"], [0, 1])

    def test_switch_range_check_is_ignored(self):
        c = count("sub eax, 0x4\nja 0x2000\nmov eax, dword ptr [4*eax + 0x404000]\njmp eax")
        self.assertEqual(c["compare"], [0, 0])

    def test_division_by_constant_idioms(self):
        signed = count("mov eax, 0x66666667\nimul ecx\nsar edx, 0x2\nmov eax, edx\nshr eax, 0x1f\nadd edx, eax")
        self.assertEqual((signed["divide"], signed["shift"], signed["mul"]), ([1, 0], [0, 0], [0, 0]))
        unsigned = count("mov eax, 0xcccccccd\nmul ecx\nshr edx, 0x3")
        self.assertEqual((unsigned["divide"], unsigned["shift"]), ([0, 1], [0, 0]))
        # clang's form (race/leftBar.c, `t / 70 / 60`): the magic in edx,
        # the shift after an add
        clang = count("mov edx, 0x88888889\nmov dword ptr [esp + 0xdc], edx\nimul edx\nmov eax, edx\n"
                      "add eax, ecx\nmov edx, eax\nshr edx, 0x1f\nsar eax, 0x5\nadd eax, edx")
        self.assertEqual((clang["divide"], clang["shift"]), ([1, 0], [0, 0]))
        spilled = count("mov edx, dword ptr [esp + 0xdc]\nimul edx\nadd edx, eax\nmov esi, edx\n"
                        "shr esi, 0x1f\nsar edx, 0x5\nadd edx, esi")
        self.assertEqual((spilled["divide"], spilled["shift"]), ([1, 0], [0, 0]))

    def test_widening_multiply(self):
        self.assertEqual(count("imul ecx\nmul ebx\nimul eax, ecx, 0x3")["mul"], [1, 1])

    def test_dividend_extension(self):
        c = count("cdq\nidiv ecx\nxor edx, edx\ndiv ecx\nxor edx, edx\nmov eax, 0x1")
        self.assertEqual((c["dividend"], c["divide"]), ([1, 1], [1, 1]))

    def test_abs_is_not_a_division(self):
        self.assertEqual(count("cdq\nxor eax, edx\nsub eax, edx")["dividend"], [0, 0])

    def test_pow2_divide_keeps_its_sar(self):
        # dr.c calculateCircuitReversed: the original's cdq; sub; sar is
        # Hex-Rays' (x - HIDWORD(x)) >> 1, and an unsigned HIDWORD makes the
        # port's shift a shr; hiding the sar would hide that.
        c = count("cdq\nsub eax, edx\ninc esi\nsar eax")
        self.assertEqual((c["shift"], c["dividend"]), ([1, 0], [1, 0]))


class ScoreTest(unittest.TestCase):
    def test_original_sar_port_shr_is_flagged(self):
        # 89caa70 (sub_4055A0): the port shifted an unsigned _DWORD with shr
        # where the original's sar kept a negative sine negative.
        orig = count("shl edi\nmov edx, edi\nsar edx\ncmp eax, ecx\njl 0x1000")
        port = count("shl eax\nshr eax\ncmp eax, ecx\njl 0x1000")
        s = sc.score(orig, port)
        self.assertEqual(s["shift"], (1, 0, "lost"))
        self.assertEqual(sc.strength(s), (1, 1))

    def test_partial_swap_counts_the_swapped_part(self):
        orig = {c: [0, 0] for c in sc.CATEGORIES}
        port = {c: [0, 0] for c in sc.CATEGORIES}
        orig["shift"], port["shift"] = [5, 0], [2, 2]
        self.assertEqual(sc.score(orig, port)["shift"], (2, 0, "lost"))

    def test_unsigned_where_original_is_signed_compare(self):
        orig = {c: [0, 0] for c in sc.CATEGORIES}
        port = {c: [0, 0] for c in sc.CATEGORIES}
        orig["compare"], port["compare"] = [4, 0], [3, 1]
        self.assertEqual(sc.score(orig, port)["compare"], (1, 0, "lost"))

    def test_port_signed_where_original_is_unsigned(self):
        # the BYTE class (a61e96b): movsx in the port, movzx in the original
        orig = count("movzx eax, byte ptr [ecx]\nmovzx edx, byte ptr [ecx + 0x1]")
        port = count("movsx eax, byte ptr [ecx]\nmovzx edx, byte ptr [ecx + 0x1]")
        self.assertEqual(sc.score(orig, port)["extend"], (0, 1, "gained"))

    def test_same_signedness_is_silent(self):
        orig = count("sar eax, 0x8\nmovzx eax, byte ptr [ecx]\njl 0x1000")
        port = count("sar eax, 0x8\nsar eax, 0x8\nmovzx eax, byte ptr [ecx]\njl 0x1000")
        self.assertEqual(sc.strength(sc.score(orig, port)), (0, 0))


if __name__ == "__main__":
    unittest.main()
