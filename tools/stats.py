#!/usr/bin/env python3
"""Count Hex-Rays leftovers per source file: the progress metric for cleanup."""
import re
import sys
from pathlib import Path

PREFIXES = ("sub_", "dword_", "unk_", "byte_")
PATTERNS = {p: re.compile(r"\b%s[0-9A-Fa-f]{5,8}\b" % p) for p in PREFIXES}
SKIP_DIRS = {"libincludes", "libs", "linux", "MINGW32", "tools", "build", "run", ".git"}


def count(text):
    return {p: len(PATTERNS[p].findall(text)) for p in PREFIXES}


def source_files(root):
    for path in sorted(root.rglob("*")):
        if path.suffix in (".c", ".h") and not SKIP_DIRS.intersection(path.relative_to(root).parts):
            yield path


def main():
    root = Path(__file__).resolve().parent.parent
    rows = []
    for path in source_files(root):
        counts = count(path.read_text(encoding="latin-1"))
        if any(counts.values()):
            rows.append((str(path.relative_to(root)), counts))
    rows.sort(key=lambda row: -sum(row[1].values()))
    print("%-40s %8s %8s %8s %8s" % (("file",) + PREFIXES))
    for name, counts in rows:
        print("%-40s %8d %8d %8d %8d" % ((name,) + tuple(counts[p] for p in PREFIXES)))
    totals = [sum(counts[p] for _, counts in rows) for p in PREFIXES]
    print("%-40s %8d %8d %8d %8d" % tuple(["TOTAL"] + totals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
