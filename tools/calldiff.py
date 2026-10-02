#!/usr/bin/env python3
"""Find calls the port dropped: compare each function's callees with dr.exe's.

The port author often commented out, or deleted, a call that crashed for
him, and each time a real feature went missing with it: the race-start
intro, the race-end outro, mine explosions, recalcRank, strupr (see
doc/FINDINGS.md, "Original code commented out by the port author"). A
grep finds the commented-out calls it can see, but not the deleted ones,
nor those inside a /* ... */ block. The machine code finds all three.

The tool pairs every port function with its original exactly like
tools/signcheck.py (marker, moved marker or `_XXXXXX` name suffix),
collects the direct call targets of both, maps the port's callees to
original addresses through the same pairing, and lists per function:

  missing  an original callee the port calls fewer times, or not at all,
           with the number of calls on each side;
  extra    a port callee the original never calls (lower priority: MSVC
           inlined many small functions the port still calls).

Original side: `call rel32`, a `jmp` to another function's start (a tail
call), `call [IAT]`, and `call reg` after `mov reg, [IAT]`; calls through
the `jmp [IAT]` and `jmp func` stubs are resolved to what they jump to.
Port side: the map names every target. Library calls (the original's
imports from MSVCR71/SDL/fmod/OpenGL, the port's static CRT and import
thunks) are compared by name in a separate, lower-priority list, because
the port's library layer differs (MSVC inlines strcpy/memcpy/strlen, the
port calls them). A function that is a bare `ret` in the original
(0x43C720, the port's nullsub_1) is ignored on both sides.

For every missing callee the tool looks for its name (any name the
sources give its address, or `sub_XXXXXX`) in the port function's own
source lines: "commented" if it appears in a comment there, "in code"
if it appears outside one (compiled out, or under another name), else
nothing, which means the call was deleted or never translated.

Functions are grouped by single-player relevance, from the original's
own call graph: "race" (reachable from startRace, 0x415710), "menus"
(from mainMenu, 0x43A020), "startup" (from the game's main, 0x43ACE0),
"other" (none of those: callbacks reached through function pointers),
and last "multiplayer" (a multiplayer_* function, or reachable only
through one). The walk never enters a multiplayer function.

Usage: tools/calldiff.py [--dr-data PATH | --orig PATH] [--exe PATH]
                         [--all] [--func FUNC ...]
  --dr-data PATH  directory holding dr.exe (default: $DR_DATA)
  --orig PATH     dr.exe directly, overrides --dr-data
  --exe PATH      the port build (default build/debug/dreerally.exe; its
                  .map and .pdb must sit next to it)
  --all           also list the extra port callees and library calls the
                  original lacks, and calls that only differ in count
  --func FUNC     only these port functions (name or original address)

Python 3.9, stdlib only. Needs llvm-objdump and llvm-symbolizer from
$LLVM (default /opt/homebrew/opt/llvm/bin).
"""
import argparse
import bisect
import collections
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "equiv"))
import signcheck as sc  # noqa: E402  (pairing, objdump, disassembly helpers)
import equiv  # noqa: E402  (read_pe, read_map, is_library_obj)

START_RACE = 0x415710
MAIN_MENU = 0x43A020
GAME_MAIN = 0x43ACE0
AREAS = ("race", "menus", "startup", "other", "multiplayer")

# CRT functions the UCRT headers define inline, so the map puts them in
# a game object: they are library calls all the same.
CRT_INLINE = {
    "sprintf", "vsprintf", "_snprintf", "_vsnprintf", "_vsprintf_l", "_vsnprintf_l",
    "snprintf", "vsnprintf", "printf", "fprintf", "_vfprintf_l", "__local_stdio_printf_options",
}
# The original's statically linked runtime helpers that game code calls,
# and 0x43C4C0, a bare wrapper that passes its argument to malloc.
ORIG_RUNTIME = {0x43F8D0: "_ftol2", 0x43F950: "_alldiv", 0x43FA00: "_allshr", 0x43C4C0: "malloc"}
# Library calls only the original makes, for a reason that is not a
# dropped call: clang converts float to int inline (cvttss2si) and
# shifts a 64-bit value by a constant inline.
LIB_NOISE = {"_ftol2", "_allshr"}
EMPTY = ("empty",)
INDIRECT = ("indirect",)
HEXADDR = re.compile(r"^0x[0-9a-fA-F]+$")
SUFFIX_NAME = re.compile(r"\b([A-Za-z_]\w*?_([0-9A-Fa-f]{6}))\b")


# --- the original's imports -------------------------------------------------

def rva_bytes(secs, rva, size):
    for va, raw in secs.values():
        if va <= rva < va + len(raw):
            return raw[rva - va:rva - va + size]
    return b""


def c_string(secs, rva):
    data = rva_bytes(secs, rva, 256)
    return data.split(b"\0", 1)[0].decode("latin-1")


def library_name(name):
    """The C name of an import or map symbol: `_FSOUND_Update@0` and
    `__imp__SDL_Delay` -> `FSOUND_Update`, `SDL_Delay`; `__strupr` (the
    map's name for `_strupr`) -> `_strupr`."""
    if name.startswith("__imp_"):
        name = name[len("__imp_"):]
    return sc.plain_name(name)


def read_imports(path):
    """{IAT slot address: C name} of a PE's imports."""
    data = Path(path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    image_base, _end, secs = equiv.read_pe(path)
    imp_rva = struct.unpack_from("<I", data, pe + 24 + 96 + 8)[0]
    out = {}
    k = 0
    while True:
        desc = rva_bytes(secs, imp_rva + 20 * k, 20)
        k += 1
        if len(desc) < 20 or desc == b"\0" * 20:
            break
        lookup, _t, _f, _name, first = struct.unpack("<IIIII", desc)
        lookup = lookup or first
        i = 0
        while True:
            entry = struct.unpack("<I", rva_bytes(secs, lookup + 4 * i, 4))[0]
            if entry == 0:
                break
            name = "#%d" % (entry & 0xFFFF) if entry & 0x80000000 else c_string(secs, entry + 2)
            # the original's own import names: `_strupr` is the C name,
            # fmod's are decorated (`_FSOUND_Update@0`)
            if re.match(r"^_\w+@\d+$", name):
                name = sc.plain_name(name)
            out[image_base + first + 4 * i] = name
            i += 1
    return out


# --- callees ------------------------------------------------------------------

def register_source(insns, i, reg):
    """Index of the instruction that last loaded `reg` before insns[i], in
    address order, skipping the `pop reg` of an epilogue placed earlier in
    the function (MSVC loads an import into esi once and calls it many
    times). None if a call clobbers the (caller-saved) register first."""
    for k in range(i - 1, -1, -1):
        mn, ops = insns[k][1], insns[k][2]
        if mn == "call" and reg in ("eax", "ecx", "edx"):
            return None
        if mn in ("pop", "push", "call", "cmp", "test") or mn.startswith("j"):
            continue  # reads its first operand, or is an epilogue's pop
        if ops.split(", ")[0] in sc.REG_PARTS.get(reg, (reg,)):
            return k
    return None


def memory_address(operand):
    """0x441024 of `dword ptr [0x441024]`, else None."""
    m = re.match(r"^dword ptr \[(0x[0-9a-fA-F]+)\]$", operand)
    return int(m.group(1), 16) if m else None


FRAME_SLOT = re.compile(r"^dword ptr \[(ebp|esp)( [-+] 0x[0-9a-fA-F]+)?\]$")


def operand_value(insns, i, operand, depth=4):
    """What `operand` holds at insns[i]: ("addr", a) for a constant
    address, ("slot", a) for the dword at address a (an import slot), or
    None. Follows `mov reg, x` and, for the port's function-pointer locals
    (`v8 = rand; v8()`), `mov dword ptr [ebp - n], x` or the same
    through esp (clang /Od, which never pushes in a body: a push, pop or
    esp adjustment on the way back ends the search). `lea reg, [a]` is
    the address a."""
    if HEXADDR.match(operand):
        return "addr", int(operand, 16)
    slot = memory_address(operand)
    if slot is not None:
        return "slot", slot
    if depth == 0:
        return None
    if operand in sc.REG_PARTS:
        k = register_source(insns, i, operand)
        if k is None or insns[k][1] not in ("mov", "lea"):
            return None
        src = insns[k][2].partition(", ")[2]
        if insns[k][1] == "lea":
            m = re.match(r"^\[(0x[0-9a-fA-F]+)\]$", src)
            return ("addr", int(m.group(1), 16)) if m else None
        return operand_value(insns, k, src, depth - 1)
    m = FRAME_SLOT.match(operand)
    if m:
        for k in range(i - 1, -1, -1):
            mn, ops = insns[k][1], insns[k][2]
            if m.group(1) == "esp" and (mn in ("push", "pop") or re.match(r"^(add|sub|and) esp,", mn + " " + ops)):
                return None
            if mn in ("call", "push", "cmp", "test") or mn.startswith("j"):
                continue  # reads the slot
            dest, _, src = ops.partition(", ")
            if dest == operand:
                return operand_value(insns, k, src, depth - 1) if mn == "mov" else None
    return None


def call_targets(insns, start, end, resolve_address, resolve_slot):
    """Counter of callee keys in one function's instructions.

    resolve_address(target) -> key of a direct call or jmp target (None for
    a jmp that is not a tail call); resolve_slot(address) -> key of a call
    through the dword at that address (an import slot), None otherwise.
    Calls through anything else count as INDIRECT."""
    out = collections.Counter()
    for i, (_a, mn, ops) in enumerate(insns):
        if mn not in ("call", "jmp"):
            continue
        if mn == "jmp" and HEXADDR.match(ops) and start <= int(ops, 16) < end:
            continue  # a branch inside the function
        key = None
        value = operand_value(insns, i, ops)
        if value is not None:
            key = resolve_address(value[1]) if value[0] == "addr" else resolve_slot(value[1])
        if key is None and mn == "call":
            key = INDIRECT
        if key is not None:
            out[key] += 1
    return out


class Original:
    """The original dr.exe: function slices, imports and call resolution."""

    def __init__(self, exe, known):
        ib, _hi, secs = equiv.read_pe(exe)
        va, raw = secs[".text"]
        self.lo, self.hi = ib + va, ib + va + len(raw)
        self.raw = raw
        self.imports = read_imports(exe)
        self.full = sc.objdump(exe, self.lo, self.hi)
        self.addrs = [i[0] for i in self.full]
        # MSVC pads between functions with int3, never inside one: the
        # first instruction after padding starts a function, even one
        # without a marker that nothing calls directly (0x402A00)
        padded = set(self.full[k + 1][0] for k in range(len(self.full) - 1)
                     if self.full[k][1] == "int3" and self.full[k + 1][1] != "int3")
        self.bounds = sorted(set(sc.original_boundaries(self.full, known, self.lo, self.hi)) | padded)
        self.starts = set(a for a in known if self.lo <= a < self.hi) | padded
        for _a, mn, ops in self.full:
            if mn == "call" and HEXADDR.match(ops) and self.lo <= int(ops, 16) < self.hi:
                self.starts.add(int(ops, 16))
        self.exe = exe

    def end_of(self, addr):
        k = bisect.bisect_right(self.bounds, addr)
        return self.bounds[k] if k < len(self.bounds) else self.hi

    def insns(self, addr):
        end = self.end_of(addr)
        k = bisect.bisect_left(self.addrs, addr)
        if k < len(self.addrs) and self.addrs[k] == addr:
            return self.full[k:bisect.bisect_left(self.addrs, end)]
        return sc.objdump(self.exe, addr, end)  # the linear dump lost sync here

    def stub(self, addr):
        """What a one-instruction function does: ("jmp", target),
        ("slot", address) for `jmp [address]`, ("ret",), or None."""
        off = addr - self.lo
        b = self.raw[off:off + 6]
        if b[:1] == b"\xe9" and len(b) >= 5:
            return "jmp", addr + 5 + struct.unpack("<i", b[1:5])[0]
        if b[:2] == b"\xff\x25" and len(b) >= 6:
            return "slot", struct.unpack("<I", b[2:6])[0]
        if b[:1] in (b"\xc3", b"\xc2"):
            return ("ret",)
        return None

    def resolve_slot(self, slot):
        name = self.imports.get(slot)
        return ("lib", name) if name else None

    def resolve(self, addr):
        """Key of a call to addr: ("fn", address) of the function it ends
        up in, ("lib", name), EMPTY, or None if addr is not a function."""
        for _ in range(8):
            if not (self.lo <= addr < self.hi):
                return None
            if addr in ORIG_RUNTIME:
                return "lib", ORIG_RUNTIME[addr]
            s = self.stub(addr)
            if s is None:
                break
            if s[0] == "ret":
                return EMPTY
            if s[0] == "slot":
                return self.resolve_slot(s[1])
            addr = s[1]
        return ("fn", addr) if addr in self.starts else None

    def callees(self, addr):
        insns = self.insns(addr)
        return call_targets(insns, addr, self.end_of(addr), self.resolve, self.resolve_slot)


class Port:
    """The port build: map symbols and call resolution through the pairing."""

    def __init__(self, exe, to_orig, original):
        self.at = collections.defaultdict(list)  # aliases share an address
        for va, name, obj in equiv.read_map(Path(exe).with_suffix(".map")):
            self.at[va].append((name, obj))
        self.to_orig = to_orig  # {port function start: original address}
        self.original = original
        self.orig_libs = set(original.imports.values()) | set(ORIG_RUNTIME.values())

    def lib_key(self, names):
        """("lib", name) for a symbol's aliases (`_itoa` and `__itoa`),
        preferring the name the original imports."""
        plain = [library_name(n) for n in names]
        return "lib", next((n for n in plain if n in self.orig_libs), plain[-1])

    def resolve(self, addr):
        syms = self.at.get(addr)
        if not syms:
            return None
        name, obj = syms[-1]
        plain = sc.plain_name(name)
        if equiv.is_library_obj(obj) or plain in CRT_INLINE:
            return self.lib_key([n for n, _o in syms])
        if re.match(r"^nullsub_\d+$", plain):
            return EMPTY
        if addr in self.to_orig:
            return self.original.resolve(self.to_orig[addr]) or ("fn", self.to_orig[addr])
        return "port", plain

    def resolve_slot(self, slot):
        names = [n for n, _o in self.at.get(slot, ()) if n.startswith("__imp_")]
        return self.lib_key(names) if names else None

    def callees(self, func, insns):
        return call_targets(insns, func[0], func[1], self.resolve, self.resolve_slot)


# --- comparison ---------------------------------------------------------------

# Library calls under another name in the other build.
LIB_EQUIVALENT = {"_ftol2_sse": "_ftol2", "_CIpow": "pow"}


def comparable(counter):
    """The callees worth comparing: functions ("fn", address), library
    calls ("lib", name) under one name for both builds, and the port's
    unpaired functions ("port", name); not empty functions, indirect
    calls, or the library calls in LIB_NOISE."""
    out = collections.Counter()
    for key, n in counter.items():
        if key[0] == "lib":
            name = LIB_EQUIVALENT.get(key[1], key[1])
            if name in LIB_NOISE:
                continue
            key = ("lib", name)
        if key[0] in ("fn", "lib", "port"):
            out[key] += n
    return out


def sort_key(key):
    return key[0], ("%08X" % key[1]) if key[0] == "fn" else key[1]


def compare(orig, port):
    """(lost, extra) for two callee Counters, each [(key, orig count,
    port count)]: lost are the callees the port calls fewer times than
    the original, or not at all; extra those it calls more often."""
    o, p = comparable(orig), comparable(port)
    lost = [(k, o[k], p[k]) for k in sorted(o, key=sort_key) if p[k] < o[k]]
    extra = [(k, o[k], p[k]) for k in sorted(p, key=sort_key) if p[k] > o[k]]
    return lost, extra


# --- call graph areas -----------------------------------------------------------

def reachable(graph, roots, stop):
    seen = set()
    todo = [r for r in roots if r not in stop]
    while todo:
        a = todo.pop()
        if a in seen:
            continue
        seen.add(a)
        todo.extend(t for t in graph.get(a, ()) if t not in seen and t not in stop)
    return seen


def areas(graph, multiplayer):
    """{original address: area} over the original's call graph ({address:
    callee addresses}); multiplayer: addresses of multiplayer functions."""
    race = reachable(graph, [START_RACE], multiplayer)
    menus = reachable(graph, [MAIN_MENU], multiplayer)
    startup = reachable(graph, [GAME_MAIN], multiplayer)
    everything = reachable(graph, [GAME_MAIN], set())
    out = {}
    for a in graph:
        if a in multiplayer or (a in everything and a not in startup):
            out[a] = "multiplayer"
        elif a in race:
            out[a] = "race"
        elif a in menus:
            out[a] = "menus"
        elif a in startup:
            out[a] = "startup"
        else:
            out[a] = "other"
    return out


# --- source hints -------------------------------------------------------------

def split_comments(text):
    """(code, comments): two copies of text with the same lines, one with
    every comment blanked out, the other with everything but comments
    blanked out. String and char literals count as code."""
    code, comm = [], []
    i, n = 0, len(text)
    state = "code"
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if state == "code":
            if two == "//":
                state = "line"
            elif two == "/*":
                state = "block"
            elif c in "\"'":
                j = i + 1
                while j < n and text[j] != c and text[j] != "\n":
                    j += 2 if text[j] == "\\" else 1
                code.append(text[i:j + 1])
                comm.append(re.sub(r"[^\n]", " ", text[i:j + 1]))
                i = j + 1
                continue
        if state == "code":
            code.append(c)
            comm.append("\n" if c == "\n" else " ")
            i += 1
            continue
        if state == "line" and c == "\n":
            state = "code"
            continue
        if state == "block" and two == "*/":
            code.append("  ")
            comm.append("*/")
            state = "code"
            i += 2
            continue
        code.append("\n" if c == "\n" else " ")
        comm.append(c)
        i += 1
    return "".join(code), "".join(comm)


class Sources:
    """Names for original addresses, and where a name occurs in a port
    function's source lines."""

    def __init__(self, paths):
        self.files = {}
        self.names = collections.defaultdict(set)
        for path in paths:
            try:
                text = path.read_text(encoding="latin-1")
            except OSError:
                continue
            code, comm = split_comments(text)
            self.files[str(path)] = (code.splitlines(), comm.splitlines())
            for m in SUFFIX_NAME.finditer(text):
                self.names[int(m.group(2), 16)].add(m.group(1))

    def find(self, path, first, last, names):
        """("commented" or "in code", line) of the first of `names` in lines
        first..last of path, or None."""
        lines = self.files.get(path)
        if not lines or not names:
            return None
        pattern = re.compile(r"\b(%s)\b" % "|".join(re.escape(n) for n in sorted(names)))
        for kind, side in (("commented", lines[1]), ("in code", lines[0])):
            for ln in range(max(1, first), min(len(side), last) + 1):
                if pattern.search(side[ln - 1]):
                    return kind, ln
        return None


def symbolize(exe, addrs):
    """{address: (file, line)} through the PDB."""
    tool = os.path.join(os.environ.get("LLVM", "/opt/homebrew/opt/llvm/bin"), "llvm-symbolizer")
    if not addrs:
        return {}
    try:
        result = subprocess.run([tool, "--obj=%s" % exe, "--output-style=GNU", "--no-inlines"],
                                input="\n".join("0x%x" % a for a in addrs), capture_output=True, text=True)
    except OSError as e:
        raise SystemExit("llvm-symbolizer not runnable at %s (%s); set LLVM=/path/to/llvm/bin" % (tool, e))
    lines = result.stdout.splitlines()
    out = {}
    for a, k in zip(addrs, range(0, len(lines), 2)):
        loc = lines[k + 1] if k + 1 < len(lines) else ""
        path, _, line = loc.rpartition(":")
        if line.isdigit() and path:
            out[a] = (os.path.normpath(os.path.join(str(REPO_ROOT), path)), int(line))
    return out


# --- driver -------------------------------------------------------------------

def relpath(path):
    try:
        return os.path.relpath(path, str(REPO_ROOT))
    except ValueError:
        return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dr-data", default=sc.default_dr_data())
    ap.add_argument("--orig")
    ap.add_argument("--exe", default=str(REPO_ROOT / "build" / "debug" / "dreerally.exe"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--func", action="append", default=[])
    args = ap.parse_args(argv)

    orig_exe = sc.check_inputs("calldiff", args.orig, args.dr_data, args.exe)
    pairing = sc.load_pairing(orig_exe, args.exe)
    original = Original(orig_exe, set(pairing.orig_funcs))
    to_orig = {pf[0]: a for a, pf, _how in pairing.pairs}
    port = Port(args.exe, to_orig, original)

    # names: the paired port function, a moved marker, any `name_XXXXXX`
    sources = Sources(sc.compiled_sources(REPO_ROOT) +
                      sorted(REPO_ROOT.glob("*.h")) + sorted(REPO_ROOT.glob("*/**/*.h")))
    port_name = {}
    for a, pf, _how in pairing.pairs:
        port_name.setdefault(a, sc.plain_name(pf[2]))
    for a, name, _live in pairing.markers:
        port_name.setdefault(a, name)

    def name_of(addr):
        if addr in port_name:
            return port_name[addr]
        named = sorted(n for n in sources.names.get(addr, ()) if not n.startswith("sub_"))
        return named[0] if named else "sub_%06X" % addr

    def label(key):
        return "0x%06X %s" % (key[1], name_of(key[1])) if key[0] == "fn" else key[1]

    # the original's call graph, for the areas
    graph = {}
    todo = list(pairing.orig_funcs)
    while todo:
        a = todo.pop()
        if a in graph:
            continue
        graph[a] = [k[1] for k in original.callees(a) if k[0] == "fn"]
        todo.extend(t for t in graph[a] if t not in graph)
    multiplayer = {a for a in graph if name_of(a).lower().startswith("multiplayer")}
    area = areas(graph, multiplayer)

    # the port's call graph: {callee key of a port function: its callees}
    port_graph = collections.defaultdict(collections.Counter)
    for pf, code in pairing.port_code.items():
        key = port.resolve(pf[0])
        if key is not None:
            port_graph[key] += comparable(port.callees(pf, code))

    def via(key, extra):
        """Why a lost callee may be noise: another callee of the port
        function calls it (MSVC inlined that one in the original), or
        the lost callee's own original callee is what the port calls
        instead (the port inlined it, or calls the library directly).
        Callees the original never calls are the likelier explanation."""
        extra = sorted(extra, key=lambda r: r[1] > 0)
        for e, _o, _p in extra:
            if port_graph.get(e, {}).get(key):
                return "via %s" % label(e)
        if key[0] == "fn":
            inner = comparable(original.callees(key[1]))
            for e, _o, _p in extra:
                if inner.get(e):
                    return "port calls its callee %s" % label(e)
        return None

    entries = []
    for orig_addr, pf, how in pairing.pairs:
        if orig_addr not in pairing.orig_funcs:
            continue
        pname = sc.plain_name(pf[2])
        if args.func and not any(f == pname or (re.match(r"^(0x)?[0-9a-fA-F]{6,8}$", f)
                                                and int(f, 16) == orig_addr) for f in args.func):
            continue
        lost, extra = compare(original.callees(orig_addr), port.callees(pf, pairing.port_code[pf]))
        entries.append(dict(orig=orig_addr, pf=pf, name=pname, area=area.get(orig_addr, "other"),
                            lost=lost, extra=extra))

    # where each port function's source is, for the hints
    ends = {}
    for e in entries:
        code = pairing.port_code[e["pf"]]
        ends[e["pf"][0]] = code[-1][0] if code else e["pf"][0]
    locs = symbolize(args.exe, sorted(set(list(ends) + list(ends.values()))))
    for e in entries:
        start = locs.get(e["pf"][0])
        end = locs.get(ends[e["pf"][0]])
        e["src"] = start
        e["hints"] = {}
        for key, _o, _p in e["lost"]:
            names = {key[1]}
            if key[0] == "fn":
                names = ({name_of(key[1]), "sub_%06X" % key[1], "sub_%06x" % key[1]}
                         | sources.names.get(key[1], set()))
            found = None
            if start:
                last = end[1] if end and end[0] == start[0] and end[1] >= start[1] else start[1] + 400
                found = sources.find(start[0], start[1], last, names)
            if found:
                e["hints"][key] = "%s %s:%d" % (found[0], relpath(start[0]), found[1])
            else:
                e["hints"][key] = via(key, e["extra"]) or "none"

    count = collections.Counter()
    for e in entries:
        for key, _o, p in e["lost"]:
            count[(e["area"], "lib" if key[0] == "lib" else "missing" if p == 0 else "fewer")] += 1
    print("calldiff: %d port functions paired with the original (%d unpaired)"
          % (len(entries), len(pairing.unpaired)))
    for kind, what in (("missing", "original callees the port never calls"),
                       ("fewer", "callees the port calls fewer times"),
                       ("lib", "library calls the port lacks")):
        print("%-8s %s: %s" % (kind, what, ", ".join("%s %d" % (a, count[(a, kind)]) for a in AREAS)))
    print("hint: commented/in code = the callee's name is in a comment/in the code of the port function;"
          " via X = the port's extra callee X calls it; none = deleted or never translated")

    for a in AREAS:
        group = sorted((e for e in entries if e["area"] == a), key=lambda e: e["orig"])
        shown = [e for e in group if e["lost"] or (args.all and e["extra"])]
        if not shown:
            continue
        print("\n== %s" % a)
        for e in shown:
            src = "%s:%d" % (relpath(e["src"][0]), e["src"][1]) if e["src"] else "?"
            print("0x%06X %s  (%s)" % (e["orig"], e["name"], src))
            for key, o, p in sorted(e["lost"], key=lambda r: (r[0][0] == "lib", r[2] > 0)):
                kind = "lib" if key[0] == "lib" else "missing" if p == 0 else "fewer"
                print("   %-8s %-44s orig %2d port %2d  %s" % (kind, label(key), o, p, e["hints"][key]))
            for key, o, p in e["extra"]:
                if key[0] != "lib" or args.all:
                    print("   %-8s %-44s orig %2d port %2d" % ("extra", label(key), o, p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
