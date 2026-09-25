#!/usr/bin/env python3
"""Compare two DreeRally builds made with the Makefile's equiv profile.

Prints EQUIVALENT and exits 0 when every section of the two PE images is
byte-identical, which is what a pure refactor (renames, types, formatting)
must produce. Otherwise exits 1 and names the functions whose bytes differ,
using the lld-link map file next to each image.
"""
import re
import struct
import sys
from pathlib import Path

MAX_LISTED = 20

# " 0001:00000010       _startRace                 00000000004156b0     dr.obj"
MAP_LINE = re.compile(
    r"^\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(?P<name>\S+)\s+(?P<va>[0-9a-fA-F]{8,16})(?:\s+(?P<obj>\S.*))?$")


def read_pe(path):
    """Return (image_base, {section name: (virtual_address, raw_bytes)})."""
    data = Path(path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("%s: not a PE image" % path)
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sections = {}
    table = pe + 24 + opt_size
    for i in range(count):
        entry = table + 40 * i
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii")
        _vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, entry + 8)
        sections[name] = (va, data[raw_ptr:raw_ptr + raw_size])
    return image_base, sections


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


def compare(base_exe, work_exe):
    """Return (equivalent, report lines)."""
    base_ib, base_secs = read_pe(base_exe)
    work_ib, work_secs = read_pe(work_exe)
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
        base_text, work_text = base_secs[".text"], work_secs[".text"]
        base_funcs = functions_in(read_map(Path(base_exe).with_suffix(".map")),
                                  base_ib + base_text[0], base_ib + base_text[0] + len(base_text[1]))
        work_funcs = functions_in(read_map(Path(work_exe).with_suffix(".map")),
                                  work_ib + work_text[0], work_ib + work_text[0] + len(work_text[1]))
        if len(base_funcs) != len(work_funcs):
            report.append("  function count: %d -> %d (added or removed functions; pairing below is by order)"
                          % (len(base_funcs), len(work_funcs)))
        changed = []
        for bf, wf in zip(base_funcs, work_funcs):
            b_bytes = _bytes_of(base_text, bf[0] - base_ib, bf[1] - base_ib)
            w_bytes = _bytes_of(work_text, wf[0] - work_ib, wf[1] - work_ib)
            if b_bytes != w_bytes:
                changed.append((bf, wf))
        report.append("  functions with different bytes: %d" % len(changed))
        for bf, wf in changed[:MAX_LISTED]:
            report.append("    0x%x %s -> %s  size 0x%x -> 0x%x  %s" % (
                bf[0], bf[2], wf[2], bf[1] - bf[0], wf[1] - wf[0], wf[3]))
        if len(changed) > MAX_LISTED:
            report.append("    ... %d more" % (len(changed) - MAX_LISTED))
        if changed:
            bf, wf = changed[0]
            report.append("  inspect the first one:")
            report.append("    llvm-objdump -d --start-address=0x%x --stop-address=0x%x %s" % (bf[0], bf[1], base_exe))
            report.append("    llvm-objdump -d --start-address=0x%x --stop-address=0x%x %s" % (wf[0], wf[1], work_exe))
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
