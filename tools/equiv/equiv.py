#!/usr/bin/env python3
"""Compare two DreeRally builds made with the Makefile's equiv profile.

Prints EQUIVALENT and exits 0 when every section of the two PE images is
byte-identical, which is what a pure refactor (renames, types, formatting)
must produce. Otherwise exits 1.

For .text, byte identity is too strict to answer "which functions did this
change actually touch?": moving a single byte shifts every absolute address
and rel32 call target after it, so nearly every function's raw bytes differ
even though only one of them changed behaviour. The footprint listing below
disassembles the differing functions and normalizes out anything that is
purely a relocation, so only genuine changes are printed.
"""
import bisect
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

# " 0001:00000010       _startRace                 00000000004156b0     dr.obj"
MAP_LINE = re.compile(
    r"^\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(?P<name>\S+)\s+(?P<va>[0-9a-fA-F]{8,16})(?:\s+(?P<obj>\S.*))?$")

# "  401010:      \tmov\teax, dword ptr [ebp + 0xc]"
# (llvm-objdump -d --no-show-raw-insn -M intel; a header/label line has no
# colon right after the leading hex run, so this only matches instructions.)
INSTR_LINE = re.compile(r"^\s*([0-9a-fA-F]+):\s*(.*)$")
HEX_TOKEN = re.compile(r"0x[0-9a-fA-F]+")
# objdump's own "<.text+0x1234>" annotation on call/jmp targets: it is
# section-relative, not the address we already substitute, and it does not
# survive relocation, so it is dropped rather than normalized.
OBJDUMP_ANNOTATION = re.compile(r"\s*<[^>]*>")
BARE_HEX = re.compile(r"^0x[0-9a-fA-F]+$")

# Relative call/jmp/jcc/loop (E8/E9/0F8x/E0-E3 with a rel8/rel32
# displacement): the linker resolves these at link time as an IP-relative
# offset, so the printed target is always an address, and unlike an
# absolute address embedded as data it never carries a base relocation.
BRANCH_MNEMONICS = {
    "call", "jmp",
    "je", "jne", "jz", "jnz", "jg", "jge", "jl", "jle",
    "ja", "jae", "jb", "jbe", "jc", "jnc", "jo", "jno",
    "js", "jns", "jp", "jnp", "jpe", "jpo", "jcxz", "jecxz",
    "loop", "loope", "loopne", "loopz", "loopnz",
}


def read_pe(path):
    """Return (image_base, image_end, {section name: (virtual_address, raw_bytes)})."""
    data = Path(path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("%s: not a PE image" % path)
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    size_of_image = struct.unpack_from("<I", data, pe + 24 + 56)[0]
    sections = {}
    table = pe + 24 + opt_size
    for i in range(count):
        entry = table + 40 * i
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii")
        _vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, entry + 8)
        sections[name] = (va, data[raw_ptr:raw_ptr + raw_size])
    return image_base, image_base + size_of_image, sections


def read_map(path):
    """Return every public and static symbol as (va, name, obj), sorted by va."""
    symbols = []
    for line in Path(path).read_text(errors="replace").splitlines():
        m = MAP_LINE.match(line)
        if m:
            symbols.append((int(m.group("va"), 16), m.group("name"), (m.group("obj") or "").strip()))
    symbols.sort()
    return symbols


def functions_in(symbols, start_va, end_va):
    """Symbols inside [start_va, end_va) as (start, end, name, obj).

    A function ends where the next symbol starts; aliases sharing an address
    collapse into the last one.
    """
    code = [s for s in symbols if start_va <= s[0] < end_va]
    functions = []
    for i, (va, name, obj) in enumerate(code):
        end = code[i + 1][0] if i + 1 < len(code) else end_va
        if end > va:
            functions.append((va, end, name, obj))
    return functions


def _bytes_of(section, start, end):
    va, raw = section
    return raw[start - va:end - va]


def resolve_symbol(symbols, addr):
    """The nearest (name, offset) at or below addr in a va-sorted symbol
    list, or None if addr precedes every symbol."""
    vas = [s[0] for s in symbols]
    i = bisect.bisect_right(vas, addr) - 1
    if i < 0:
        return None
    va, name, _obj = symbols[i]
    return name, addr - va


def parse_line(line):
    """(addr, text): text is the mnemonic+operands with the address column
    dropped and tabs collapsed to single spaces. (None, None) for headers,
    section/symbol labels and blank lines, which carry no instruction."""
    m = INSTR_LINE.match(line)
    if not m:
        return None, None
    return int(m.group(1), 16), m.group(2).replace("\t", " ").strip()


def is_direct_branch(mnemonic, operand):
    """Whether `mnemonic operand` is a relative call/jmp/jcc/loop to a bare
    address (rule a): these are always addresses, and unlike a
    data reference they never carry a base relocation, so rule b (below)
    would otherwise wrongly leave them as unrelocated literals."""
    return mnemonic in BRANCH_MNEMONICS and BARE_HEX.match(operand) is not None


def has_reloc(reloc_vas, start, end):
    """Whether any HIGHLOW base-relocation VA falls in [start, end); reloc_vas
    is sorted ascending."""
    i = bisect.bisect_left(reloc_vas, start)
    return i < len(reloc_vas) and reloc_vas[i] < end


def normalize_line(text, fn_start, fn_end, symbols, image_lo, image_hi, relocated):
    """Replace every operand address that falls inside the image with a form
    that survives relocation: function-relative for a target inside this
    same function, symbol-relative otherwise. A number is only an address
    if it is a direct branch target (rule a) or
    `relocated` says this instruction's own byte range carries a base
    relocation (rule b); every other in-image-looking number is a literal
    the compiler happened to pick, and is compared verbatim like any other
    immediate or stack offset."""
    text = OBJDUMP_ANNOTATION.sub("", text)
    mnemonic, _, operand = text.partition(" ")
    is_address = relocated or is_direct_branch(mnemonic, operand.strip())

    def replace(m):
        n = int(m.group(0), 16)
        if not is_address or not (image_lo <= n < image_hi):
            return m.group(0)
        if fn_start <= n < fn_end:
            return ".+0x%x" % (n - fn_start)
        resolved = resolve_symbol(symbols, n)
        if resolved is None:
            return m.group(0)
        name, offset = resolved
        return "%s+0x%x" % (name, offset)

    return HEX_TOKEN.sub(replace, text)


def normalize(lines, fn_start, fn_end, symbols, image_lo, image_hi, reloc_vas):
    """Turn one function's raw objdump output lines into a relocation-
    insensitive instruction list: two builds normalize to the same list
    exactly when the function's own behaviour is unchanged, even if the
    function (or anything it calls or reads) moved in the image."""
    parsed = [parse_line(line) for line in lines]
    parsed = [(addr, text) for addr, text in parsed if addr is not None]
    out = []
    for i, (addr, text) in enumerate(parsed):
        next_addr = parsed[i + 1][0] if i + 1 < len(parsed) else fn_end
        relocated = has_reloc(reloc_vas, addr, next_addr)
        out.append(normalize_line(text, fn_start, fn_end, symbols, image_lo, image_hi, relocated))
    return out


def parse_base_relocations(reloc_bytes, image_base):
    """The sorted list of VAs with a HIGHLOW (type 3) base relocation, from
    a .reloc section's raw bytes: a sequence of per-page blocks, each a
    (page RVA, block size) header followed by 16-bit (type:4, offset:12)
    entries. Type 0 (ABSOLUTE, used only to pad a block to a WORD count) and
    any other type are skipped; this target only has HIGHLOW ones."""
    vas = []
    off = 0
    n = len(reloc_bytes)
    while off + 8 <= n:
        page_rva, block_size = struct.unpack_from("<II", reloc_bytes, off)
        if block_size < 8 or off + block_size > n:
            break
        for i in range((block_size - 8) // 2):
            entry = struct.unpack_from("<H", reloc_bytes, off + 8 + 2 * i)[0]
            if entry >> 12 == 3:  # IMAGE_REL_BASED_HIGHLOW
                vas.append(image_base + page_rva + (entry & 0xFFF))
        off += block_size
    vas.sort()
    return vas


def is_library_obj(obj):
    """Whether a map object string names a member of a prebuilt library
    (e.g. "libvcruntime:...undname.obj", "SDL:...SDL.lib") rather than one
    of the game's own .obj files (always a bare relative path such as
    "bpaUtil.obj", so never containing ':')."""
    return ":" in obj


def instr_addr(line):
    """The instruction address of one objdump line, or None if it isn't one."""
    m = INSTR_LINE.match(line)
    return int(m.group(1), 16) if m else None


def objdump_tool():
    return os.path.join(os.environ.get("LLVM", "/opt/homebrew/opt/llvm/bin"), "llvm-objdump")


def dump_text(exe, start, end):
    """Disassemble [start, end) of exe once; return its raw output lines."""
    tool = objdump_tool()
    try:
        result = subprocess.run(
            [tool, "-d", "--no-show-raw-insn", "-M", "intel",
             "--start-address=0x%x" % start, "--stop-address=0x%x" % end, str(exe)],
            capture_output=True, text=True)
    except OSError as e:
        raise SystemExit("llvm-objdump not runnable at %s (%s); set LLVM=/path/to/llvm/bin" % (tool, e))
    if result.returncode != 0:
        raise SystemExit("llvm-objdump failed on %s:\n%s" % (exe, result.stderr))
    return result.stdout.splitlines()


def lines_in(dump_lines, addrs, start, end):
    """The raw dump lines whose address is in [start, end); addrs is the
    parallel, ascending list of dump_lines' instruction addresses."""
    lo = bisect.bisect_left(addrs, start)
    hi = bisect.bisect_left(addrs, end)
    return dump_lines[lo:hi]


def pair_functions(base_funcs, work_funcs):
    """Pair functions by name. Falls back to pairing by position when name
    pairing covers less than half of the smaller side (e.g. a mass rename),
    which is noted in the returned flag rather than silently mispairing.

    Returns (pairs, added, removed, used_fallback).
    """
    base_by_name = {}
    for f in base_funcs:
        base_by_name.setdefault(f[2], f)
    work_by_name = {}
    for f in work_funcs:
        work_by_name.setdefault(f[2], f)
    common = set(base_by_name) & set(work_by_name)
    smaller = min(len(base_funcs), len(work_funcs)) or 1
    if len(common) * 2 < smaller:
        pairs = list(zip(base_funcs, work_funcs))
        added = work_funcs[len(pairs):]
        removed = base_funcs[len(pairs):]
        return pairs, added, removed, True

    pairs = sorted(((base_by_name[n], work_by_name[n]) for n in common), key=lambda p: p[0][0])
    added = sorted((work_by_name[n] for n in work_by_name if n not in common), key=lambda f: f[0])
    removed = sorted((base_by_name[n] for n in base_by_name if n not in common), key=lambda f: f[0])
    return pairs, added, removed, False


def _raw_differing(pairs, base_text, base_ib, work_text, work_ib):
    out = []
    for bf, wf in pairs:
        b_bytes = _bytes_of(base_text, bf[0] - base_ib, bf[1] - base_ib)
        w_bytes = _bytes_of(work_text, wf[0] - work_ib, wf[1] - work_ib)
        if b_bytes != w_bytes:
            out.append((bf, wf))
    return out


def text_footprint(base_exe, work_exe, base_ib, base_hi, work_ib, work_hi, base_secs, work_secs):
    """The footprint report lines for a .text that differs: which paired
    functions really changed, vs. moved-only collateral, vs. added/removed.
    Library-object functions are excluded from the listing
    and folded into a single count instead: they are frequently compiler-
    generated jump/lookup tables that disassemble as meaningless garbage,
    so per-function detail for them
    would just reintroduce the noise this tool exists to remove.
    """
    base_text, work_text = base_secs[".text"], work_secs[".text"]
    base_map = read_map(Path(base_exe).with_suffix(".map"))
    work_map = read_map(Path(work_exe).with_suffix(".map"))
    base_start, base_end = base_ib + base_text[0], base_ib + base_text[0] + len(base_text[1])
    work_start, work_end = work_ib + work_text[0], work_ib + work_text[0] + len(work_text[1])
    base_funcs = functions_in(base_map, base_start, base_end)
    work_funcs = functions_in(work_map, work_start, work_end)

    pairs, added, removed, fallback = pair_functions(base_funcs, work_funcs)
    game_pairs = [p for p in pairs if not is_library_obj(p[0][3])]
    lib_pairs = [p for p in pairs if is_library_obj(p[0][3])]
    game_added = [f for f in added if not is_library_obj(f[3])]
    lib_added = [f for f in added if is_library_obj(f[3])]
    game_removed = [f for f in removed if not is_library_obj(f[3])]
    lib_removed = [f for f in removed if is_library_obj(f[3])]

    game_raw_differ = _raw_differing(game_pairs, base_text, base_ib, work_text, work_ib)
    lib_raw_differ = _raw_differing(lib_pairs, base_text, base_ib, work_text, work_ib)

    report = []
    if fallback:
        report.append("  name pairing failed for most functions (mass rename?); paired by order instead")
    report.append("  functions with different bytes: %d" % len(game_raw_differ))

    changed = []
    moved_only = 0
    lib_changed = 0
    if game_raw_differ or lib_raw_differ:
        base_dump = dump_text(base_exe, base_start, base_end)
        work_dump = dump_text(work_exe, work_start, work_end)
        base_addrs = [instr_addr(l) for l in base_dump]
        base_dump = [l for l, a in zip(base_dump, base_addrs) if a is not None]
        base_addrs = [a for a in base_addrs if a is not None]
        work_addrs = [instr_addr(l) for l in work_dump]
        work_dump = [l for l, a in zip(work_dump, work_addrs) if a is not None]
        work_addrs = [a for a in work_addrs if a is not None]

        base_reloc = parse_base_relocations(base_secs.get(".reloc", (0, b""))[1], base_ib)
        work_reloc = parse_base_relocations(work_secs.get(".reloc", (0, b""))[1], work_ib)

        def changed_after_normalize(bf, wf):
            b_lines = lines_in(base_dump, base_addrs, bf[0], bf[1])
            w_lines = lines_in(work_dump, work_addrs, wf[0], wf[1])
            b_norm = normalize(b_lines, bf[0], bf[1], base_map, base_ib, base_hi, base_reloc)
            w_norm = normalize(w_lines, wf[0], wf[1], work_map, work_ib, work_hi, work_reloc)
            return b_norm != w_norm

        for bf, wf in game_raw_differ:
            if changed_after_normalize(bf, wf):
                changed.append((bf, wf))
            else:
                moved_only += 1
        for bf, wf in lib_raw_differ:
            if changed_after_normalize(bf, wf):
                lib_changed += 1
    changed.sort(key=lambda p: p[0][0])

    report.append("  functions changed (real): %d" % len(changed))
    for bf, wf in changed:
        report.append("    0x%x %s -> %s  size 0x%x -> 0x%x  %s" % (
            bf[0], bf[2], wf[2], bf[1] - bf[0], wf[1] - wf[0], wf[3]))
    report.append("  moved-only (collateral, bytes differ but normalized code does not): %d" % moved_only)
    report.append("  library functions with different bytes: %d (not listed, %d changed after normalization)"
                  % (len(lib_raw_differ), lib_changed))
    if game_added:
        report.append("  added: %d" % len(game_added))
        for f in game_added:
            report.append("    0x%x %s  %s" % (f[0], f[2], f[3]))
    if game_removed:
        report.append("  removed: %d" % len(game_removed))
        for f in game_removed:
            report.append("    0x%x %s  %s" % (f[0], f[2], f[3]))
    if lib_added:
        report.append("  library added: %d (not listed)" % len(lib_added))
    if lib_removed:
        report.append("  library removed: %d (not listed)" % len(lib_removed))
    if changed:
        bf, wf = changed[0]
        report.append("  inspect the first one:")
        report.append("    llvm-objdump -d --start-address=0x%x --stop-address=0x%x %s" % (bf[0], bf[1], base_exe))
        report.append("    llvm-objdump -d --start-address=0x%x --stop-address=0x%x %s" % (wf[0], wf[1], work_exe))
    return report


def compare(base_exe, work_exe):
    """Return (equivalent, report lines)."""
    base_ib, base_hi, base_secs = read_pe(base_exe)
    work_ib, work_hi, work_secs = read_pe(work_exe)
    differing = [name for name in sorted(set(base_secs) | set(work_secs))
                 if base_secs.get(name) != work_secs.get(name)]
    if not differing:
        return True, ["EQUIVALENT"]

    report = ["DIFFERENT"]
    for name in differing:
        b, w = base_secs.get(name), work_secs.get(name)
        report.append("  section %s: size 0x%x -> 0x%x" % (
            name, len(b[1]) if b else 0, len(w[1]) if w else 0))

    if ".text" in differing and ".text" in base_secs and ".text" in work_secs:
        report.extend(text_footprint(base_exe, work_exe, base_ib, base_hi, work_ib, work_hi,
                                     base_secs, work_secs))
    return False, report


def main(argv):
    if len(argv) != 3:
        print("usage: equiv.py BASE.exe WORK.exe", file=sys.stderr)
        return 2
    same, report = compare(argv[1], argv[2])
    print("\n".join(report))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
