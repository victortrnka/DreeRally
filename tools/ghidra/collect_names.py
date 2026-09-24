#!/usr/bin/env python3
"""List (address, function name) pairs from the Hex-Rays markers in our sources.

A marker line looks like `//----- (0043ACE0) -----`; the function defined right
after it reimplements the original function at that address. Only files compiled
by DreeRally.vcxproj are scanned. Prints `XXXXXXXX<TAB>name` lines; conflicts are
reported on stderr and left out.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

MARKER = re.compile(r"^//----- \(([0-9A-Fa-f]{8})\)")
NAME_BEFORE_PAREN = re.compile(r"([A-Za-z_]\w*)\s*\(")
LOOKAHEAD_LINES = 5


def names_in(text):
    """Yield (address, name) for each marker that is followed by a function definition."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = MARKER.match(line)
        if not m:
            continue
        header = ""
        for following in lines[i + 1:i + 1 + LOOKAHEAD_LINES]:
            stripped = following.strip()
            if MARKER.match(stripped):
                header = ""  # the next marker owns whatever follows
                break
            if not stripped or stripped.startswith(("//", "/*", "*")):
                continue
            header += " " + stripped
            if "(" in stripped or ";" in stripped:
                break
        if ";" in header.split("(")[0]:
            continue  # a variable, not a function
        n = NAME_BEFORE_PAREN.search(header)
        if n:
            yield int(m.group(1), 16), n.group(1)


def merge(pairs):
    """Return ({address: name}, conflicts). Ambiguous addresses and names are dropped."""
    by_addr = defaultdict(set)
    by_name = defaultdict(set)
    for addr, name in pairs:
        by_addr[addr].add(name)
        by_name[name].add(addr)
    conflicts = []
    mapping = {}
    for addr, names in sorted(by_addr.items()):
        if len(names) > 1:
            conflicts.append("CONFLICT %08X has several names: %s" % (addr, ", ".join(sorted(names))))
            continue
        name = next(iter(names))
        if len(by_name[name]) > 1:
            if min(by_name[name]) == addr:
                conflicts.append("CONFLICT %s is used at several addresses: %s" % (
                    name, ", ".join("%08X" % a for a in sorted(by_name[name]))))
            continue
        mapping[addr] = name
    return mapping, conflicts


def compiled_sources(repo):
    text = (repo / "DreeRally.vcxproj").read_text(encoding="utf-8-sig")
    return [repo / p.replace("\\", "/") for p in re.findall(r'<ClCompile Include="([^"]+)"', text)]


def main():
    repo = Path(__file__).resolve().parent.parent.parent
    pairs = []
    for path in compiled_sources(repo):
        pairs.extend(names_in(path.read_text(encoding="latin-1")))
    mapping, conflicts = merge(pairs)
    for line in conflicts:
        print(line, file=sys.stderr)
    for addr, name in sorted(mapping.items()):
        print("%08X\t%s" % (addr, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
