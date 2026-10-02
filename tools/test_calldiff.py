"""Tests for calldiff.py: why they matter is that the port author
commented out or deleted calls that crashed for him, and each one hid a
real feature (the race-start intro, the race-end outro, mine explosions,
recalcRank, strupr; see doc/FINDINGS.md, "Original code commented out by
the port author"). A call the tool fails to see on the original's side,
or wrongly sees on the port's, hides such a bug; one it cannot match up
across the two builds buries the real ones in noise."""
import collections
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calldiff as cd  # noqa: E402

LO, HI = 0x401000, 0x402000
IAT_STRUPR, IAT_FREE = 0x441020, 0x4410A0


def insns(text, base=0x401100):
    """'mnemonic operands' lines -> [(address, mnemonic, operands)]."""
    out = []
    for n, line in enumerate(l.strip() for l in text.strip().splitlines()):
        mnemonic, _, operands = line.partition(" ")
        out.append((base + 4 * n, mnemonic, operands.strip()))
    return out


def original():
    """An Original over a hand-made .text: 0x401050 `jmp 0x401060`,
    0x401060 `jmp [free]`, 0x401070 `ret`, 0x401080 and 0x401200 real
    functions."""
    raw = bytearray(b"\xcc" * (HI - LO))

    def put(addr, data):
        raw[addr - LO:addr - LO + len(data)] = data
    put(0x401050, b"\xe9" + struct.pack("<i", 0x401060 - 0x401055))
    put(0x401060, b"\xff\x25" + struct.pack("<I", IAT_FREE))
    put(0x401070, b"\xc3")
    put(0x401080, b"\x55\x8b\xec")
    put(0x401200, b"\x55\x8b\xec")
    o = object.__new__(cd.Original)
    o.lo, o.hi, o.raw = LO, HI, bytes(raw)
    o.imports = {IAT_STRUPR: "_strupr", IAT_FREE: "free"}
    o.starts = {0x401050, 0x401060, 0x401070, 0x401080, 0x401100, 0x401200}
    return o


def orig_callees(text, start=0x401100, end=0x401180):
    o = original()
    return cd.call_targets(insns(text, start), start, end, o.resolve, o.resolve_slot)


class OriginalCallsTest(unittest.TestCase):
    def test_direct_calls_are_counted_per_callee(self):
        c = orig_callees("call 0x401080\nnop\ncall 0x401080\ncall 0x401200")
        self.assertEqual(c, {("fn", 0x401080): 2, ("fn", 0x401200): 1})

    def test_import_held_in_a_register_past_an_earlier_epilogue(self):
        # MSVC loads _strupr into esi once and calls it in several blocks,
        # some placed after an early return's `pop esi; ret`; previewRaceScreen's
        # strupr on the drivers' names (3de827c) was such a call
        c = orig_callees("""
            push esi
            mov esi, dword ptr [0x441020]
            call esi
            pop esi
            ret
            call esi
        """)
        self.assertEqual(c, {("lib", "_strupr"): 2})

    def test_caller_saved_register_is_lost_at_a_call(self):
        c = orig_callees("mov eax, dword ptr [0x441020]\ncall 0x401080\ncall eax")
        self.assertEqual(c, {("fn", 0x401080): 1, cd.INDIRECT: 1})

    def test_tail_jump_to_a_function_is_a_call_but_a_branch_is_not(self):
        c = orig_callees("jmp 0x401104\njmp 0x401200\njmp 0x401190")
        self.assertEqual(c, {("fn", 0x401200): 1})

    def test_stubs_resolve_to_what_they_jump_to(self):
        # 0x401050 (jmp 0x401060) and 0x401060 (jmp [free]) are free;
        # a bare `ret` (0x43C720, the port's nullsub_1) is nothing
        c = orig_callees("call 0x401050\ncall 0x401060\ncall dword ptr [0x4410a0]\ncall 0x401070")
        self.assertEqual(c, {("lib", "free"): 3, cd.EMPTY: 1})

    def test_runtime_helpers_are_library_calls(self):
        o = original()
        o.lo, o.hi = 0x43F000, 0x440000
        o.raw = b"\x55" * 0x1000
        self.assertEqual(o.resolve(0x43F8D0), ("lib", "_ftol2"))


class PortCallsTest(unittest.TestCase):
    def port(self):
        p = object.__new__(cd.Port)
        p.at = collections.defaultdict(list)
        for va, name, obj in [
                (0x500000, "_startRace", "dr.obj"),
                (0x500100, "_explodeMine", "dr.obj"),
                (0x500200, "_getLanguageEntry", "i18n.obj"),
                (0x500300, "_nullsub_1", "dr.obj"),
                (0x500400, "__itoa", "libucrt:xtoa.obj"),
                (0x500400, "_itoa", "libucrt:xtoa.obj"),
                (0x500500, "_SDL_Delay", "SDL:SDL.dll"),
                (0x4C2574, "__imp__SDL_Delay", "SDL:SDL.dll")]:
            p.at[va].append((name, obj))
        p.to_orig = {0x500000: 0x415710, 0x500100: 0x401080}
        p.original = original()
        p.original.lo, p.original.hi = 0x401000, 0x441000
        p.original.raw = b"\x55" * (0x441000 - 0x401000)
        p.original.starts |= {0x415710}
        p.orig_libs = {"_itoa", "SDL_Delay"}
        return p

    def test_callees_map_to_original_addresses_through_the_pairing(self):
        p = self.port()
        c = cd.call_targets(insns("""
            call 0x500100
            call 0x500200
            call 0x500300
            call 0x500400
            call 0x500500
            call dword ptr [0x4c2574]
            call dword ptr [ebp - 0x8]
        """), 0x500000, 0x500100, p.resolve, p.resolve_slot)
        self.assertEqual(c, {("fn", 0x401080): 1, ("port", "getLanguageEntry"): 1, cd.EMPTY: 1,
                             ("lib", "_itoa"): 1, ("lib", "SDL_Delay"): 2, cd.INDIRECT: 1})

    def test_function_pointer_locals_are_followed(self):
        # Hex-Rays keeps MSVC's `mov esi, [IAT]; call esi` as a local
        # function pointer (`v8 = rand; v8()`, `v10 = glTexCoord2f`), which
        # clang /Od spills to the frame; counting those as unknown made
        # generatePowerUps look as if it had lost two rand() calls
        p = self.port()
        c = cd.call_targets(insns("""
            mov dword ptr [ebp - 0x24], 0x500400
            mov eax, dword ptr [0x4c2574]
            mov dword ptr [ebp - 0x4c], eax
            call dword ptr [ebp - 0x24]
            mov eax, dword ptr [ebp - 0x4c]
            call eax
            call dword ptr [ebp - 0x4c]
            call dword ptr [ebp - 0x30]
        """), 0x500000, 0x500100, p.resolve, p.resolve_slot)
        self.assertEqual(c, {("lib", "_itoa"): 1, ("lib", "SDL_Delay"): 2, cd.INDIRECT: 1})

    def test_esp_slots_only_without_pushes_in_between(self):
        # clang /Od keeps esp fixed in a body (generatePowerUps: lea eax,
        # [rand]; mov [esp + 0xe8], eax; call [esp + 0xe8]); MSVC pushes
        # arguments, so the same text then names another slot
        p = self.port()
        c = cd.call_targets(insns("""
            lea eax, [0x500400]
            mov dword ptr [esp + 0xe8], eax
            call dword ptr [esp + 0xe8]
            cmp dword ptr [esp + 0xe8], 0x0
            call dword ptr [esp + 0xe8]
            push eax
            call dword ptr [esp + 0xe8]
        """), 0x500000, 0x500100, p.resolve, p.resolve_slot)
        self.assertEqual(c, {("lib", "_itoa"): 2, cd.INDIRECT: 1})


class CompareTest(unittest.TestCase):
    def test_a_callee_the_port_never_calls_is_flagged(self):
        # the race-start intro (e176723): startRace calls it, the port's
        # call was commented out
        lost, extra = cd.compare(collections.Counter({("fn", 0x4028C0): 1, ("fn", 0x406410): 3}),
                                 collections.Counter({("fn", 0x406410): 3}))
        self.assertEqual(lost, [(("fn", 0x4028C0), 1, 0)])
        self.assertEqual(extra, [])

    def test_one_of_several_calls_dropped_is_flagged_with_both_counts(self):
        lost, _extra = cd.compare(collections.Counter({("fn", 0x406410): 54}),
                                  collections.Counter({("fn", 0x406410): 46}))
        self.assertEqual(lost, [(("fn", 0x406410), 54, 46)])

    def test_a_port_only_callee_is_extra_not_lost(self):
        lost, extra = cd.compare(collections.Counter(),
                                 collections.Counter({("port", "getLanguageEntry"): 2}))
        self.assertEqual((lost, extra), ([], [(("port", "getLanguageEntry"), 0, 2)]))

    def test_library_calls_compare_by_name_without_the_noise(self):
        # the original's _ftol2 is inline code in the port, and an empty
        # function or a function pointer says nothing about a dropped call
        lost, extra = cd.compare(
            collections.Counter({("lib", "_strupr"): 3, ("lib", "_ftol2"): 9, cd.EMPTY: 2, cd.INDIRECT: 1}),
            collections.Counter({("lib", "_strupr"): 2, ("lib", "_ftol2_sse"): 1}))
        self.assertEqual((lost, extra), ([(("lib", "_strupr"), 3, 2)], []))


class AreasTest(unittest.TestCase):
    def test_race_menus_and_multiplayer(self):
        graph = {
            cd.GAME_MAIN: [cd.MAIN_MENU],
            cd.MAIN_MENU: [0x4321B0, 0x42A570],
            0x4321B0: [cd.START_RACE],
            cd.START_RACE: [0x40F6A0, 0x415280],
            0x40F6A0: [],
            0x415280: [0x403960],  # multiplayer_415280
            0x403960: [],          # only reached through it
            0x42A570: [],
            0x43DCB0: [],          # a callback: nothing calls it directly
        }
        a = cd.areas(graph, {0x415280})
        self.assertEqual(a[0x40F6A0], "race")
        self.assertEqual(a[0x4321B0], "menus")
        self.assertEqual(a[cd.GAME_MAIN], "startup")
        self.assertEqual(a[0x415280], "multiplayer")
        self.assertEqual(a[0x403960], "multiplayer")
        self.assertEqual(a[0x43DCB0], "other")


class SourcesTest(unittest.TestCase):
    def test_comments_and_code_are_told_apart(self):
        code, comm = cd.split_comments('a(); // b();\n/* c();\n d(); */ e("//f");\n')
        self.assertEqual([l.strip() for l in code.splitlines()], ["a();", "", 'e("//f");'])
        self.assertEqual([l.strip() for l in comm.splitlines()], ["// b();", "/* c();", "d(); */"])

    def test_a_call_inside_a_block_comment_is_found_as_commented(self):
        # a grep for "//.*name(" misses these
        s = object.__new__(cd.Sources)
        s.files = {"x.c": tuple(t.splitlines() for t in cd.split_comments(
            "void f()\n{\n  /*\n  sub_426080(1);\n  */\n  g();\n}\n"))}
        self.assertEqual(s.find("x.c", 1, 7, {"sub_426080"}), ("commented", 4))
        self.assertEqual(s.find("x.c", 1, 7, {"g"}), ("in code", 6))
        self.assertIsNone(s.find("x.c", 1, 7, {"h"}))


if __name__ == "__main__":
    unittest.main()
