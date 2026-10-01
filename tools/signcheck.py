#!/usr/bin/env python3
"""Find port functions whose signedness differs from the original dr.exe.

Hex-Rays often types a value as `_DWORD`, `unsigned int` or `unsigned
__int8` where the original treats it as signed (or the other way round),
so the port compiles `shr` where the original has `sar`, `div` where it
has `idiv`, `jb`/`ja` where it has `jl`/`jg`, `movzx` where it has
`movsx`. With a negative value the result is wildly wrong (see
doc/FINDINGS.md, "Unsigned `_DWORD` where the original uses `sar`").

This tool pairs every port function with its original by address (the
`//----- (00XXXXXX)` marker above its definition, or an `_XXXXXX` name
suffix), disassembles both sides, counts the signedness-sensitive
instructions per category and ranks the functions where the port uses
the unsigned form in place of the original's signed form, or the other
way round. The two compilers differ (the original is optimised MSVC, the
port clang-cl /Od), so the ranking is a list of candidates to check by
hand, not a verdict.

Categories (signed form / unsigned form):
  shift     sar / shr
  extend    movsx / movzx
  divide    idiv / div, and MSVC's division-by-constant idioms
  mul       one-operand imul / mul (widening products)
  compare   signed jcc/setcc/cmovcc (l, le, g, ge) / unsigned (b, be, a, ae)
  dividend  cdq or sar r, 0x1f (sign extension) / xor edx, edx right
            before a div (zero extension)

Usage: tools/signcheck.py [--dr-data PATH | --orig PATH] [--exe PATH]
                          [--top N] [--all] [--show FUNC ...]
  --dr-data PATH  directory holding dr.exe (default: $DR_DATA)
  --orig PATH     dr.exe directly, overrides --dr-data
  --exe PATH      the port build (default build/debug/dreerally.exe; its
                  .map must sit next to it, and --show needs its .pdb)
  --top N         print the N strongest candidates (default 40)
  --all           print every candidate, including the weak ones, and
                  the unpaired port functions
  --show FUNC     print both sides' signedness instructions for a port
                  function name or original address, the port's with
                  file:line from the PDB (llvm-symbolizer)

Python 3.9, stdlib only. Needs llvm-objdump (and llvm-symbolizer for
--show) from $LLVM (default /opt/homebrew/opt/llvm/bin).
"""
import argparse
import bisect
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "equiv"))
import equiv  # noqa: E402  (read_pe, read_map, functions_in, is_library_obj)

ORIG_SHA256 = "54fe789faca583d67b8e73e7c58908f3f1468c5c8f75942239a60483ae9be58c"

# --- pairing ------------------------------------------------------------

MARKER = re.compile(r"^//----- \(([0-9A-Fa-f]{8})\)")
NAME_BEFORE_PAREN = re.compile(r"([A-Za-z_]\w*)\s*\(")
# "//int   drawMenu(int menuType, int top)": a commented-out definition. A
# marker followed by one belongs to that commented-out function (it was
# moved elsewhere or dropped), not to whatever code comes after it.
COMMENTED_SIGNATURE = re.compile(r"^//\s*(?:[A-Za-z_][\w]*[\s\*]+)+\**([A-Za-z_]\w*)\s*\([^;]*$")
# "drawCarInRace_40D920", "sub_4055A0": the original address as a name suffix.
NAME_SUFFIX = re.compile(r"_([0-9A-Fa-f]{6})$")


def markers_in(text):
    """Yield (address, name, live) for each marker followed by a function
    definition (live) or by a commented-out signature (not live: the
    function was moved, usually to another file, and is defined there
    without a marker of its own). Blank and comment lines between the
    marker and the definition are skipped, however many there are; another
    marker, or a declaration ending in ';' first, means the marker names
    nothing."""
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = MARKER.match(lines[i])
        i += 1
        if not m:
            continue
        addr = int(m.group(1), 16)
        header = ""
        j = i
        in_block = False
        while j < n:
            s = lines[j].strip()
            j += 1
            if in_block:
                if "*/" in s:
                    in_block = False
                continue
            if MARKER.match(s):
                break
            if not s:
                continue
            if s.startswith("//"):
                cm = COMMENTED_SIGNATURE.match(s)
                if cm:
                    yield addr, cm.group(1), False
                    break
                continue
            if s.startswith("/*"):
                in_block = "*/" not in s[2:]
                continue
            if s.startswith("#"):
                continue
            header += " " + s
            if "(" in s or ";" in s:
                break
        if not header or ";" in header.split("(")[0]:
            continue
        nm = NAME_BEFORE_PAREN.search(header)
        if nm:
            yield addr, nm.group(1), True


def all_marker_addresses(text):
    """Every marker address in a source, whether or not live code follows:
    each is still the start of an original function."""
    return [int(m.group(1), 16) for m in (MARKER.match(l) for l in text.splitlines()) if m]


def compiled_sources(repo):
    text = (repo / "DreeRally.vcxproj").read_text(encoding="utf-8-sig")
    return [repo / p.replace("\\", "/") for p in re.findall(r'<ClCompile Include="([^"]+)"', text)]


def plain_name(map_name):
    """The C name of a map symbol: `_name`, `_name@8` (stdcall) or `@name@8`
    (fastcall) -> `name`."""
    name = map_name
    if name.startswith(("_", "@")):
        name = name[1:]
    return re.sub(r"@\d+$", "", name)


def pair(port_funcs, markers, text_lo, text_hi):
    """Pair port functions with original addresses.

    port_funcs: [(start, end, name, obj)] (game code only); markers:
    [(address, name, live)] from markers_in. Returns (pairs, conflicts,
    unpaired): pairs is [(orig_addr, port_func, how)], how being "marker",
    "moved" (only a marker above a commented-out copy of the signature
    names it) or "suffix"; a function whose marker and name suffix
    disagree is paired by the marker and listed in conflicts; unpaired
    lists port functions with none of these. Several port functions may
    claim one original address (a duplicated implementation): each is
    paired."""
    live = {}
    moved = {}
    for addr, name, is_live in markers:
        (live if is_live else moved).setdefault(name, set()).add(addr)
    pairs = []
    conflicts = []
    unpaired = []
    for f in port_funcs:
        name = plain_name(f[2])
        marked = sorted(live.get(name, ()))
        how = "marker"
        if not marked:
            marked = sorted(moved.get(name, ()))
            how = "moved"
        sm = NAME_SUFFIX.search(name)
        suffix = int(sm.group(1), 16) if sm else None
        if suffix is not None and not (text_lo <= suffix < text_hi):
            suffix = None
        if len(marked) > 1:
            conflicts.append("%s has several markers: %s" % (name, ", ".join("%08X" % a for a in marked)))
        if marked:
            if suffix is not None and suffix not in marked:
                conflicts.append("%s: marker %08X, name suffix %06X; using the marker" % (name, marked[0], suffix))
            pairs.append((marked[0], f, how))
        elif suffix is not None:
            pairs.append((suffix, f, "suffix"))
        else:
            unpaired.append(f)
    return pairs, conflicts, unpaired


# --- disassembly ------------------------------------------------------------

# "  405f84:      \tshl\tedi" (llvm-objdump -d -M intel --no-show-raw-insn)
INSN = re.compile(r"^\s*([0-9a-fA-F]+):\s+(\S.*)$")


def parse_insn(line):
    """(address, mnemonic, operands) of one objdump line, or None."""
    m = INSN.match(line)
    if not m:
        return None
    rest = m.group(2).replace("\t", " ").strip()
    rest = re.sub(r"\s*<[^>]*>", "", rest)  # objdump's "<.text+0x...>" annotations
    mnemonic, _, operands = rest.partition(" ")
    return int(m.group(1), 16), mnemonic, " ".join(operands.split())


def objdump(exe, start, end):
    tool = os.path.join(os.environ.get("LLVM", "/opt/homebrew/opt/llvm/bin"), "llvm-objdump")
    try:
        result = subprocess.run(
            [tool, "-d", "-M", "intel", "--no-show-raw-insn",
             "--start-address=0x%x" % start, "--stop-address=0x%x" % end, str(exe)],
            capture_output=True, text=True)
    except OSError as e:
        raise SystemExit("llvm-objdump not runnable at %s (%s); set LLVM=/path/to/llvm/bin" % (tool, e))
    if result.returncode != 0:
        raise SystemExit("llvm-objdump failed on %s:\n%s" % (exe, result.stderr))
    return [i for i in (parse_insn(l) for l in result.stdout.splitlines()) if i]


HEX = re.compile(r"0x([0-9a-fA-F]+)")


def original_boundaries(insns, known, text_lo, text_hi):
    """Sorted addresses where an original function, or data inside .text,
    starts: the known function addresses, every direct call target, every
    immediate that points into .text (a function pointer), and every memory
    operand that points into .text (a switch jump table, which must not be
    disassembled as code)."""
    starts = set(a for a in known if text_lo <= a < text_hi)
    data = set()
    for _addr, mnemonic, operands in insns:
        if mnemonic == "call" and re.match(r"^0x[0-9a-fA-F]+$", operands):
            t = int(operands, 16)
            if text_lo <= t < text_hi:
                starts.add(t)
            continue
        for part in operands.split(","):
            for h in HEX.findall(part):
                v = int(h, 16)
                if not (text_lo <= v < text_hi):
                    continue
                if "[" in part:
                    data.add(v)
                elif mnemonic in ("push", "mov"):
                    starts.add(v)
    return sorted(starts | data)


# --- classification ---------------------------------------------------------

CATEGORIES = ("shift", "extend", "divide", "mul", "compare", "dividend")

SIGNED_CC = {"l", "nge", "le", "ng", "g", "nle", "ge", "nl"}
UNSIGNED_CC = {"b", "nae", "c", "be", "na", "a", "nbe", "ae", "nb", "nc"}
# Instructions whose flags come from a floating-point compare: the
# unsigned condition codes after them (ja/jb, from SSE in the port, sahf
# in x87 code) say nothing about integer signedness.
FLOAT_FLAGS = {"ucomiss", "comiss", "ucomisd", "comisd", "fcomi", "fcomip", "fucomi", "fucomip", "sahf"}
# Integer instructions that set the flags a jcc/setcc reads.
INT_FLAGS = {"cmp", "test", "sub", "add", "and", "or", "xor", "neg", "dec", "inc",
             "sbb", "adc", "sar", "shr", "shl", "sal", "bt", "imul", "cmpxchg"}
# How far back to look for the instruction that set the flags (or the
# 8-bit register) an instruction reads: the port's /Od code can put a
# dozen SSE/x87 moves, which change neither, in between.
LOOKBACK = 16


def condition_code(mnemonic):
    for prefix in ("j", "set", "cmov"):
        if mnemonic.startswith(prefix):
            cc = mnemonic[len(prefix):]
            if cc in SIGNED_CC:
                return "S"
            if cc in UNSIGNED_CC:
                return "U"
    return None


def flags_source(insns, i):
    """Mnemonic of the instruction that last set the flags before insns[i]."""
    for k in range(i - 1, max(-1, i - 1 - LOOKBACK), -1):
        mn = insns[k][1]
        if mn in FLOAT_FLAGS or mn in INT_FLAGS:
            return mn
    return None


REG_PARTS = {
    "eax": ("eax", "ax", "al"), "ebx": ("ebx", "bx", "bl"), "ecx": ("ecx", "cx", "cl"),
    "edx": ("edx", "dx", "dl"), "esi": ("esi", "si"), "edi": ("edi", "di"), "ebp": ("ebp", "bp"),
}
REG_BITS = {}
for _parts in REG_PARTS.values():
    for _r, _bits in zip(_parts, (32, 16, 8)):
        REG_BITS[_r] = _bits
IMM = re.compile(r"^0x[0-9a-fA-F]+$")


def kept_bits(insns, i, reg):
    """How many low bits of the 32-bit `reg` the code keeps right after
    insns[i], when the next instruction touching it narrows it at once:
    `and reg, mask` (or `and dl, mask`) keeps the mask's bit length, a copy
    or store of `dl`/`dx` keeps 8/16 bits. None if it is used whole."""
    family = REG_PARTS.get(reg)
    if family is None:
        return None
    for k in range(i + 1, min(len(insns), i + 3)):
        mn, ops = insns[k][1], insns[k][2]
        words = set(re.findall(r"[a-z]+", ops))
        if not words & set(family) and not words & {"ah", "bh", "ch", "dh"}:
            continue
        parts = ops.split(", ")
        if mn == "and" and len(parts) == 2 and parts[0] in family and IMM.match(parts[1]):
            return min(int(parts[1], 16).bit_length(), REG_BITS[parts[0]])
        if mn in ("mov", "movzx", "movsx") and len(parts) == 2 and parts[1] in family and parts[1] != reg:
            return REG_BITS[parts[1]]
        return None
    return None


def shift_is_masked(insns, i):
    """Whether sar and shr give the same kept bits here: shifting a 32-bit
    register right by k and keeping its low w bits only sees the bits
    shifted in from the top (sign or zero) when k + w > 32. E.g.
    `(c >> 10) & 0x3F` on a palette dword, `sar edx, 0xa; and dl, 0x3f` in
    the original and `shr eax, 0xa; and eax, 0x3f` in the port."""
    ops = insns[i][2].split(", ")
    reg = ops[0]
    if len(ops) == 1:
        count = 1
    elif IMM.match(ops[1]):
        count = int(ops[1], 16)
    else:
        return False
    bits = kept_bits(insns, i, reg)
    return bits is not None and count + bits <= 32


def is_boolean(insns, i, reg8):
    """Whether the 8-bit register read at insns[i] holds a 0/1 truth value:
    its last writer is a setcc or `and reg8, 0x1` (the port's /Od code)."""
    family = next(f for f in REG_PARTS.values() if reg8 in f)
    for k in range(i - 1, max(-1, i - 1 - LOOKBACK), -1):
        mn, ops = insns[k][1], insns[k][2]
        dest = ops.split(", ")[0]
        if dest not in family:
            continue
        return (mn.startswith("set") and dest == reg8) or (mn == "and" and ops == reg8 + ", 0x1")
    return False


def is_indirect_jmp(insn):
    return insn[1] == "jmp" and not re.match(r"^0x[0-9a-fA-F]+$", insn[2])


def classify(insns):
    """Return [(index, category, "S" or "U")] for one function's
    instructions (address, mnemonic, operands).

    Idioms whose instruction would otherwise be miscounted:
    - division by a constant (optimised MSVC): `mov eax, magic; imul r`
      then `sar edx, k` and the sign fixup `shr r, 0x1f` is one signed
      divide; `mov eax, magic; mul r` then `shr edx, k` an unsigned one;
    - signed division by a power of two (`cdq; sub eax, edx; sar eax, 1`)
      is deliberately left as cdq plus a sar: Hex-Rays often renders it as
      `(x - HIDWORD(x)) >> 1`, and an unsigned HIDWORD there makes the
      port's shift a shr, which must stay visible;
    - abs(): `cdq; xor eax, edx; sub eax, edx` is not a division at all;
    - the port's boolean results (`setl al; and al, 1; movzx eax, al`)
      zero-extend a 0/1, which says nothing about the operands;
    - a switch's range check (`cmp; ja default; ... jmp [table]`) is
      unsigned in both compilers;
    - a condition read after a float compare (see FLOAT_FLAGS);
    - `shr r, 0x1f` reads the sign bit (`x < 0`), the same for either
      signedness, and `sar r, 0x1f` is a sign extension, counted with cdq;
    - the port's float -> int rounding saves the x87 control word with
      fnstcw and reads it back with movzx, which is not a data load;
    - a right shift whose result is masked or narrowed so that the bits
      shifted in never matter (see shift_is_masked).
    """
    out = []
    consumed = set()
    n = len(insns)
    for i, (_addr, mn, ops) in enumerate(insns):
        if i in consumed:
            continue
        if mn in ("imul", "mul") and "," not in ops:
            magic = any(insns[k][1] == "mov" and insns[k][2].startswith("eax, 0x")
                        and int(insns[k][2][5:], 16) >= 0x10000
                        for k in range(max(0, i - 3), i))
            if magic:
                out.append((i, "divide", "S" if mn == "imul" else "U"))
                want = "sar" if mn == "imul" else "shr"
                for k in range(i + 1, min(n, i + 4)):
                    if insns[k][1] == want and insns[k][2].startswith("edx"):
                        consumed.add(k)
                        break
                if mn == "imul":
                    for k in range(i + 1, min(n, i + 6)):
                        if insns[k][1] == "shr" and insns[k][2].endswith(", 0x1f"):
                            consumed.add(k)
                            break
            else:
                out.append((i, "mul", "S" if mn == "imul" else "U"))
            continue
        if mn == "cdq":
            nxt = [insns[k][1:] for k in range(i + 1, min(n, i + 4))]
            if len(nxt) >= 2 and nxt[0] == ("xor", "eax, edx") and nxt[1] == ("sub", "eax, edx"):
                continue  # abs()
            out.append((i, "dividend", "S"))
            continue
        if mn == "xor" and ops == "edx, edx":
            if any(insns[k][1] in ("div", "idiv") for k in range(i + 1, min(n, i + 4))):
                out.append((i, "dividend", "U"))
            continue
        if mn in ("idiv", "div"):
            out.append((i, "divide", "S" if mn == "idiv" else "U"))
            continue
        if mn in ("sar", "shr"):
            if ops.endswith(", 0x1f"):
                if mn == "sar":  # 0 or -1 from the sign: a sign extension, like cdq
                    out.append((i, "dividend", "S"))
                continue  # shr r, 31 reads the sign bit, the same either way
            if not shift_is_masked(insns, i):
                out.append((i, "shift", "S" if mn == "sar" else "U"))
            continue
        if mn in ("movsx", "movzx"):
            if mn == "movzx" and re.match(r"^\w+, (al|bl|cl|dl)$", ops) and is_boolean(insns, i, ops.split(", ")[1]):
                continue
            if mn == "movzx" and "word ptr" in ops and any(
                    insns[k][1] == "fnstcw" and insns[k][2] == ops.split(", ", 1)[1]
                    for k in range(max(0, i - 3), i)):
                continue  # the port's x87 control word, saved to round float -> int
            out.append((i, "extend", "S" if mn == "movsx" else "U"))
            continue
        cc = condition_code(mn)
        if cc:
            if flags_source(insns, i) in FLOAT_FLAGS:
                continue
            if cc == "U" and mn in ("ja", "jae", "jnbe", "jnb") and \
                    any(is_indirect_jmp(insns[k]) for k in range(i + 1, min(n, i + 5))):
                continue  # switch range check
            out.append((i, "compare", cc))
    return out


def counts(classified):
    """{category: [signed, unsigned]}"""
    c = {cat: [0, 0] for cat in CATEGORIES}
    for _i, cat, sign in classified:
        c[cat][0 if sign == "S" else 1] += 1
    return c


def score(orig, port):
    """Compare two {category: [signed, unsigned]} counts.

    Returns {category: (lost, gained, exclusive)}:
    - lost: signed forms the port lacks that it has as extra unsigned forms
      instead, min(orig S - port S, port U - orig U), e.g. original
      `sar` x3 `shr` x0, port `sar` x0 `shr` x3 -> 3;
    - gained: the same the other way round (port signed where the
      original is unsigned);
    - exclusive: "lost" or "gained" when the original uses only one form
      of the category and the port has the other one at all, however the
      counts compare (a weaker hint when lost/gained is 0)."""
    out = {}
    for cat in CATEGORIES:
        so, uo = orig[cat]
        sp, up = port[cat]
        lost = max(0, min(so - sp, up - uo))
        gained = max(0, min(sp - so, uo - up))
        exclusive = None
        if so > 0 and uo == 0 and up > 0:
            exclusive = "lost"
        elif uo > 0 and so == 0 and sp > 0:
            exclusive = "gained"
        out[cat] = (lost, gained, exclusive)
    return out


def strength(scored):
    """Ranking key: total swapped instructions, then exclusive categories."""
    total = sum(l + g for l, g, _x in scored.values())
    excl = sum(1 for _l, _g, x in scored.values() if x)
    return total, excl


SIGN_NAME = {
    "shift": ("sar", "shr"), "extend": ("movsx", "movzx"), "divide": ("idiv", "div"),
    "mul": ("imul", "mul"), "compare": ("signed", "unsigned"), "dividend": ("cdq", "xor-edx"),
}


def describe(orig, port, scored):
    parts = []
    for cat in CATEGORIES:
        lost, gained, excl = scored[cat]
        if not (lost or gained or excl):
            continue
        s, u = SIGN_NAME[cat]
        what = []
        if lost:
            what.append("lost %d" % lost)
        if gained:
            what.append("gained %d" % gained)
        if excl and not (lost or gained):
            what.append("only-%s" % ("signed" if excl == "lost" else "unsigned") + " in orig")
        parts.append("%s %s (orig %s %d %s %d | port %s %d %s %d)" % (
            cat, ", ".join(what), s, orig[cat][0], u, orig[cat][1], s, port[cat][0], u, port[cat][1]))
    return "; ".join(parts)


# --- driver -----------------------------------------------------------------

def default_dr_data():
    return os.environ.get("DR_DATA", os.path.expanduser(
        "~/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/"
        "Steam/steamapps/common/Death Rally/Death Rally"))


def load_original(orig_exe, known):
    """{address: [insn]} for every known original function address."""
    ib, _hi, secs = equiv.read_pe(orig_exe)
    va, raw = secs[".text"]
    lo, hi = ib + va, ib + va + len(raw)
    full = objdump(orig_exe, lo, hi)
    bounds = original_boundaries(full, known, lo, hi)
    addrs = [i[0] for i in full]
    at = set(addrs)
    funcs = {}
    for a in sorted(set(known)):
        if not (lo <= a < hi):
            continue
        k = bisect.bisect_right(bounds, a)
        end = bounds[k] if k < len(bounds) else hi
        if a in at:
            funcs[a] = full[bisect.bisect_left(addrs, a):bisect.bisect_left(addrs, end)]
        else:  # the linear dump lost sync (data in .text before it)
            funcs[a] = objdump(orig_exe, a, end)
    return funcs, (lo, hi)


def load_port(exe):
    ib, _hi, secs = equiv.read_pe(exe)
    va, raw = secs[".text"]
    lo, hi = ib + va, ib + va + len(raw)
    symbols = equiv.read_map(Path(exe).with_suffix(".map"))
    funcs = [f for f in equiv.functions_in(symbols, lo, hi) if not equiv.is_library_obj(f[3])]
    if not funcs:
        raise SystemExit("signcheck: no game functions in %s's map" % exe)
    game_lo = min(f[0] for f in funcs)
    game_hi = max(f[1] for f in funcs)
    full = objdump(exe, game_lo, game_hi)
    addrs = [i[0] for i in full]
    code = {}
    for f in funcs:
        code[f] = full[bisect.bisect_left(addrs, f[0]):bisect.bisect_left(addrs, f[1])]
    return funcs, code


def symbolize(exe, addrs):
    """{address: "file:line"} via llvm-symbolizer and the PDB."""
    if not addrs:
        return {}
    tool = os.path.join(os.environ.get("LLVM", "/opt/homebrew/opt/llvm/bin"), "llvm-symbolizer")
    try:
        result = subprocess.run([tool, "--obj=%s" % exe, "--output-style=GNU", "--no-inlines"],
                                input="\n".join("0x%x" % a for a in addrs), capture_output=True, text=True)
    except OSError as e:
        raise SystemExit("llvm-symbolizer not runnable at %s (%s); set LLVM=/path/to/llvm/bin" % (tool, e))
    lines = result.stdout.splitlines()
    out = {}
    # GNU style: two lines per address, "function" then "file:line"
    for a, k in zip(addrs, range(0, len(lines), 2)):
        loc = lines[k + 1] if k + 1 < len(lines) else "?"
        try:
            loc = os.path.relpath(loc.rsplit(":", 1)[0], REPO_ROOT) + ":" + loc.rsplit(":", 1)[1]
        except (ValueError, IndexError):
            pass
        out[a] = loc
    return out


def show(entry, exe):
    orig_addr, pf, how, oi, pi, oc, pc, sc = entry
    print("== 0x%X  %s  (paired by %s, port 0x%x..0x%x)" % (orig_addr, plain_name(pf[2]), how, pf[0], pf[1]))
    print("   " + (describe(oc, pc, sc) or "no signal"))
    print("-- original")
    for i, cat, sign in classify(oi):
        a, mn, ops = oi[i]
        print("   %06x  %-8s %s  %s %s" % (a, cat, sign, mn, ops))
    print("-- port")
    port_cls = classify(pi)
    locs = symbolize(exe, [pi[i][0] for i, _c, _s in port_cls])
    for i, cat, sign in port_cls:
        a, mn, ops = pi[i]
        print("   %06x  %-8s %s  %-28s %s" % (a, cat, sign, mn + " " + ops, locs.get(a, "")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dr-data", default=default_dr_data())
    ap.add_argument("--orig")
    ap.add_argument("--exe", default=str(REPO_ROOT / "build" / "debug" / "dreerally.exe"))
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--show", action="append", default=[])
    args = ap.parse_args(argv)

    orig_exe = Path(args.orig) if args.orig else Path(args.dr_data) / "dr.exe"
    if not orig_exe.is_file():
        raise SystemExit("signcheck: original dr.exe not found: %s (set DR_DATA or --orig)" % orig_exe)
    if not Path(args.exe).is_file():
        raise SystemExit("signcheck: %s not found; run make first" % args.exe)
    digest = hashlib.sha256(orig_exe.read_bytes()).hexdigest()
    if digest != ORIG_SHA256:
        raise SystemExit("signcheck: %s is not the Steam dr.exe the markers refer to (sha256 %s)"
                         % (orig_exe, digest))

    markers = []
    every_marker = []
    for path in compiled_sources(REPO_ROOT):
        text = path.read_text(encoding="latin-1")
        markers.extend(markers_in(text))
        every_marker.extend(all_marker_addresses(text))

    ib, _hi, secs = equiv.read_pe(orig_exe)
    tva, traw = secs[".text"]
    text_lo, text_hi = ib + tva, ib + tva + len(traw)

    port_funcs, port_code = load_port(args.exe)
    pairs, conflicts, unpaired = pair(port_funcs, markers, text_lo, text_hi)
    known = set(every_marker) | {a for a, _f, _h in pairs}
    orig_funcs, _ = load_original(orig_exe, known)

    entries = []
    for orig_addr, pf, how in pairs:
        oi = orig_funcs.get(orig_addr)
        if oi is None:
            continue
        pi = port_code[pf]
        oc = counts(classify(oi))
        pc = counts(classify(pi))
        sc = score(oc, pc)
        entries.append((orig_addr, pf, how, oi, pi, oc, pc, sc))

    if args.show:
        for want in args.show:
            hits = [e for e in entries if plain_name(e[1][2]) == want or
                    (re.match(r"^(0x)?[0-9a-fA-F]{6,8}$", want) and e[0] == int(want, 16))]
            if not hits:
                print("signcheck: no paired function %s" % want)
            for e in hits:
                show(e, args.exe)
        return 0

    ranked = sorted((e for e in entries if any(strength(e[7]))), key=lambda e: (
        tuple(-x for x in strength(e[7])), e[0]))
    strong = [e for e in ranked if strength(e[7])[0] > 0]
    print("signcheck: %d port functions paired (%d by marker, %d by a moved marker, %d by name suffix),"
          " %d unpaired" % (len(entries), sum(1 for e in entries if e[2] == "marker"),
                             sum(1 for e in entries if e[2] == "moved"),
                             sum(1 for e in entries if e[2] == "suffix"), len(unpaired)))
    for c in conflicts:
        print("  pairing: %s" % c)
    if args.all and unpaired:
        print("  unpaired: %s" % " ".join(plain_name(f[2]) for f in unpaired))
    print("candidates: %d with swapped forms, %d more with only an exclusive-form hint"
          % (len(strong), len(ranked) - len(strong)))
    shown = ranked if args.all else strong[:args.top]
    print("score = swapped instructions / categories where the original uses one form only;")
    print("lost = port has the unsigned form where the original is signed, gained = the reverse")
    print("%5s  %-8s  %-34s  %s" % ("score", "original", "port function", "evidence"))
    for e in shown:
        total, excl = strength(e[7])
        print("%3d/%d  0x%06X  %-34s  %s" % (total, excl, e[0], plain_name(e[1][2]), describe(e[5], e[6], e[7])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
