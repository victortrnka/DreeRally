#!/usr/bin/env python3
"""Verify initialised C arrays against the original dr.exe.

DreeRally keeps Hex-Rays' address-suffix naming convention for data it has
not renamed yet (`byte_445892`, `carAnimFrameSize_45FBA0`, ...): the digits
after the last underscore are the original static variable's address. That
convention silently rots the moment someone hand-types or hand-edits such a
table: nothing checks it against the original any more. This tool does.

It scans the game sources for initialised `char`/`BYTE`/`short`/`_WORD`/
`int`/`_DWORD`/`float` arrays whose name ends in `_XXXXXX` (six hex digits),
evaluates their C initialiser into a flat sequence of elements, and compares
each element byte-for-byte against the original `dr.exe` at that address
(VA -> file offset through the PE section table, read with the element's own
size). Any mismatch is reported with the array, the index, and both values;
the tool exits non-zero if there is at least one.

Usage: tools/verify-tables.py [--dr-data PATH] [--exe PATH] [file.c ...]
  --dr-data PATH   directory holding dr.exe (default: $DR_DATA, as in the
                   Makefile; the game data dir, not the exe itself)
  --exe PATH       dr.exe directly, overrides --dr-data
  file.c ...       scan only these files instead of the whole source tree

Python 3.9, stdlib only.
"""
import argparse
import os
import re
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories never scanned: vendored headers/libs and the (mostly dead,
# see doc/KNOWN-ISSUES.md) multiplayer code, which was never ported from the
# original and so has nothing to verify against it.
EXCLUDED_DIR_PREFIXES = ("libincludes/", "libs/", "multiplayer/")

# --- type table --------------------------------------------------------
# (element size in bytes, struct format for *reading raw bytes* -- always
# unsigned, since two byte strings are equal regardless of how you'd sign-
# interpret them; a signed format is used only to format a mismatch for
# display).
TYPE_INFO = {
    "char": (1, "B", "b"),
    "signed char": (1, "B", "b"),
    "unsigned char": (1, "B", "B"),
    "BYTE": (1, "B", "B"),
    "_BYTE": (1, "B", "B"),
    "uint8": (1, "B", "B"),
    "int8": (1, "B", "b"),
    "short": (2, "H", "h"),
    "signed short": (2, "H", "h"),
    "unsigned short": (2, "H", "H"),
    "_WORD": (2, "H", "H"),
    "WORD": (2, "H", "H"),
    "uint16": (2, "H", "H"),
    "int16": (2, "H", "h"),
    "int": (4, "I", "i"),
    "signed int": (4, "I", "i"),
    "unsigned int": (4, "I", "I"),
    "long": (4, "I", "i"),
    "unsigned long": (4, "I", "I"),
    "_DWORD": (4, "I", "I"),
    "DWORD": (4, "I", "I"),
    "uint32": (4, "I", "I"),
    "int32": (4, "I", "i"),
    "float": (4, "I", "f"),
}

# Two small, explicit exception lists for arrays whose name suffix is not
# their address, or whose layout genuinely differs from the original on
# purpose. Prefer fixing the name instead (a `refactor:` commit, EQUIVALENT)
# over adding to RENAME_MAP -- that needs no exception here at all. Kept
# empty by default: the one known case in this tree (continueAnimFramesSize)
# was fixed that way; see doc/KNOWN-ISSUES.md.
RENAME_MAP = {
    # "arrayName_wrongSuffix": 0x_real_address,
}
# Arrays that are one column of a larger original table: element i is at
# addr + STRIDE[name] * i instead of addr + element_size * i. The original's
# menu layout (ui/menu.c) is one 9x7 int table at 0x4456F0, a row of 7 ints
# (stride 0x1C) per menu type; the port keeps each column as its own 9-int
# array indexed by menu type, so it must be compared column-wise.
MENU_LAYOUT_ROW = 0x1C
STRIDE = {
    "dword_4456F0": MENU_LAYOUT_ROW,
    "dword_4456F4": MENU_LAYOUT_ROW,
    "dword_4456F8": MENU_LAYOUT_ROW,
    "dword_4456FC": MENU_LAYOUT_ROW,
    "dword_445700": MENU_LAYOUT_ROW,
    "dword_445704": MENU_LAYOUT_ROW,
    "dword_445708": MENU_LAYOUT_ROW,
}
ALLOWLIST = {
    # ui/util/popup.c: each address falls inside an already-restored
    # neighbouring table's own 4800-byte span (e.g. byte_447478 is 0x50
    # bytes into aNotTooShabbyDr's row 0), so comparing it at face value
    # only reports that neighbour's bytes back as "wrong". The true layout
    # for these 9 arrays is not understood. See doc/KNOWN-ISSUES.md
    # ("sponsor-popup stub tables in popup.c").
    "byte_447388": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_4473D8": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_447478": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_448648": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_448698": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_448738": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_449908": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_449958": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
    "byte_4499F8": "address overlaps a restored neighbour table -- see doc/KNOWN-ISSUES.md",
}

DECL_RE = re.compile(
    r"(?P<type>(?:unsigned|signed|const|static)(?:\s+(?:unsigned|signed|const|static))*\s+[A-Za-z_][A-Za-z0-9_]*"
    r"|[A-Za-z_][A-Za-z0-9_]*)"
    r"[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*_(?P<addr>[0-9A-Fa-f]{6}))"
    r"[ \t]*(?P<dims>(?:\[[^\]\n]*\][ \t]*)+)"
    r"="
)


def strip_qualifiers(type_text):
    words = [w for w in type_text.split() if w not in ("const", "static")]
    return " ".join(words)


# --- initialiser lexing -------------------------------------------------
# Only a flat, in-order list of leaf values is needed (see module docstring:
# byte position in the array only depends on initialiser order, never on
# brace nesting), so the lexer need not build a tree -- it only has to get
# the leaves right, in the presence of comments and escaped characters.

ESCAPES = {"n": 10, "t": 9, "r": 13, "a": 7, "b": 8, "f": 12, "v": 11,
           "\\": 92, "'": 39, '"': 34, "?": 63}


def decode_c_chars(raw):
    """Decode the contents of a C string/char literal (without its quotes)
    into a list of byte values, one per character/escape."""
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c != "\\":
            out.append(ord(c) & 0xFF)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        e = raw[i]
        if e == "x":
            j = i + 1
            hexdigits = ""
            while j < n and raw[j] in "0123456789abcdefABCDEF" and len(hexdigits) < 2:
                hexdigits += raw[j]
                j += 1
            out.append(int(hexdigits, 16) if hexdigits else 0)
            i = j
        elif e in "01234567":
            j = i
            octdigits = ""
            while j < n and raw[j] in "01234567" and len(octdigits) < 3:
                octdigits += raw[j]
                j += 1
            out.append(int(octdigits, 8) & 0xFF)
            i = j
        else:
            out.append(ESCAPES.get(e, ord(e)) & 0xFF)
            i += 1
    return out


def lex_initialiser(text, start):
    """From text[start] (just after the '='), return (leaves, end_index).

    leaves: a list of ('num', literal_text) for a bare numeric token, or
    ('byte', value) for one already-decoded byte from a char/string literal
    (a string literal expands to its characters plus a trailing NUL, exactly
    as an array initialised from one gets it in C). end_index is the index
    just past the top-level ';' that ends the declaration.

    Brace nesting is tracked only to flatten a 2D initialiser (the '{','}'
    branch below does not care about depth at all). The terminating ';' is
    never itself inside a brace: a raw semicolon cannot legally appear in a
    C initialiser list outside a string/char literal or a comment, and both
    of those are consumed whole before this check ever sees their bytes.
    """
    i, n = start, len(text)
    leaves = []
    buf = ""

    def flush():
        s = buf.strip()
        if s:
            leaves.append(("num", s))

    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == '"' or c == "'":
            quote = c
            j = i + 1
            raw = []
            while j < n and text[j] != quote:
                if text[j] == "\\" and j + 1 < n:
                    raw.append(text[j:j + 2])
                    j += 2
                else:
                    raw.append(text[j])
                    j += 1
            flush()
            buf = ""
            decoded = decode_c_chars("".join(raw))
            if quote == '"':
                leaves.extend(("byte", b) for b in decoded)
                leaves.append(("byte", 0))  # implicit NUL terminator
            else:
                leaves.append(("byte", decoded[0] if decoded else 0))
            i = j + 1
            continue
        if c in "{},":
            flush()
            buf = ""
            i += 1
            continue
        if c == ";":
            flush()
            return leaves, i + 1
        buf += c
        i += 1
    flush()
    return leaves, i


def parse_number(text, is_float):
    t = text.strip()
    if is_float:
        return float(t.rstrip("fFlL"))
    neg = False
    if t[:1] == "+":
        t = t[1:]
    elif t[:1] == "-":
        neg = True
        t = t[1:]
    t = t.rstrip("uUlL")
    if t[:2].lower() == "0x":
        v = int(t, 16)
    elif len(t) > 1 and t[0] == "0" and t[1:].isdigit():
        v = int(t, 8)
    else:
        v = int(t, 10) if t else 0
    return -v if neg else v


def eval_dims(dims_text):
    """Total element count from one or more bracketed dimensions, e.g.
    "[6*64]" -> 384, "[3][4]" -> 12, "[]" -> None (infer from initialiser).
    Only products of integer literals are supported (the one real case in
    the tree, carAnimFrameSize_45FBA0[6*64], is exactly this)."""
    dims = re.findall(r"\[([^\]]*)\]", dims_text)
    total = 1
    for d in dims:
        d = d.strip()
        if not d:
            return None
        factor = 1
        for part in d.split("*"):
            factor *= parse_number(part, False)
        total *= factor
    return total


def mask_comments(text):
    """`text` with every // and /* */ comment's content blanked to spaces
    (newlines kept, so line numbers and positions are unaffected). Used only
    to find declarations: a commented-out declaration (there are several in
    this tree, e.g. old `//char dword_4A9160[]= {...` experiments) must not
    be scanned as if it were live code. Skips over string/char literals so a
    '/' inside one is never mistaken for a comment start."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"' or c == "'":
            quote = c
            i += 1
            while i < n and text[i] != quote:
                i += 2 if text[i] == "\\" and i + 1 < n else 1
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            end = text.find("\n", i)
            if end < 0:
                end = n
            for k in range(i, end):
                out[k] = " "
            i = end
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            end = j + 2 if j >= 0 else n
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        i += 1
    return "".join(out)


class TableArray:
    def __init__(self, name, addr, path, line, elem_size, read_fmt, disp_fmt, values, stride=None):
        self.name = name
        self.addr = addr
        self.path = path
        self.line = line
        self.elem_size = elem_size
        self.read_fmt = read_fmt
        self.disp_fmt = disp_fmt
        self.values = values  # list of int/float, already element-typed
        self.stride = stride or elem_size  # bytes between elements in dr.exe

    def orig_addr(self, i):
        return self.addr + i * self.stride


def find_arrays(path, text):
    """Yield a TableArray for every initialised, address-suffixed array
    declaration found in `text` (the contents of `path`)."""
    masked = mask_comments(text)
    for m in DECL_RE.finditer(masked):
        type_text = strip_qualifiers(m.group("type"))
        info = TYPE_INFO.get(type_text)
        if info is None:
            continue
        elem_size, read_fmt, disp_fmt = info
        name = m.group("name")
        addr_text = m.group("addr")
        dims_total = eval_dims(m.group("dims"))
        line = text.count("\n", 0, m.start()) + 1

        leaves, _end = lex_initialiser(text, m.end())
        is_float = disp_fmt == "f"
        values = []
        for kind, val in leaves:
            if kind == "byte":
                values.append(float(val) if is_float else val)
            else:
                values.append(parse_number(val, is_float))

        if dims_total is not None:
            if dims_total < len(values):
                # More initialisers than the declared size: not valid C: the
                # declaration was misparsed (e.g. a brace/quote edge case).
                # Don't guess; skip this array rather than risk a false
                # mismatch report.
                continue
            values.extend([0.0 if is_float else 0] * (dims_total - len(values)))

        addr = RENAME_MAP.get(name, int(addr_text, 16))
        yield TableArray(name, addr, path, line, elem_size, read_fmt, disp_fmt, values,
                         STRIDE.get(name))


# --- PE reading ----------------------------------------------------------

def read_pe_sections(exe_path):
    """Return (image_base, [(name, va, virtual_size, file_offset, raw_size)]),
    sections in file order (same layout equiv.py's read_pe relies on)."""
    data = Path(exe_path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise SystemExit("%s: not a PE image" % exe_path)
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sections = []
    table = pe + 24 + opt_size
    for i in range(count):
        entry = table + 40 * i
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, entry + 8)
        sections.append((name, va, vsize, raw_ptr, raw_size))
    return image_base, sections, data


class OriginalImage:
    """Maps an absolute VA in dr.exe to bytes, through the PE section table."""

    def __init__(self, exe_path):
        self.image_base, self.sections, self.data = read_pe_sections(exe_path)

    def section_of(self, addr):
        rva = addr - self.image_base
        for name, va, vsize, raw_ptr, raw_size in self.sections:
            if va <= rva < va + max(vsize, raw_size):
                return name, va, raw_ptr, raw_size
        return None

    def read(self, addr, length):
        """`length` bytes at absolute VA `addr`, or None if addr doesn't
        fall inside any section. Bytes past a section's raw data (the
        zero-initialised tail of .bss-like space) read as zero, matching
        how the PE loader maps them."""
        found = self.section_of(addr)
        if found is None:
            return None
        _name, va, raw_ptr, raw_size = found
        offset_in_section = addr - self.image_base - va
        out = bytearray(length)
        for i in range(length):
            o = offset_in_section + i
            if 0 <= o < raw_size:
                out[i] = self.data[raw_ptr + o]
        return bytes(out)


# --- scanning --------------------------------------------------------

def game_sources(root):
    vcxproj = root / "DreeRally.vcxproj"
    srcs = re.findall(r'<ClCompile Include="([^"]+)"', vcxproj.read_text())
    out = []
    for s in srcs:
        rel = s.replace("\\", "/")
        if rel.startswith(EXCLUDED_DIR_PREFIXES):
            continue
        out.append(root / rel)
    return out


def verify(files, image, allowlist):
    mismatches = []
    skipped_outside = []
    skipped_allowlisted = []
    scanned = 0
    for path in files:
        try:
            text = path.read_text(encoding="latin-1")
        except OSError:
            continue
        for arr in find_arrays(path, text):
            scanned += 1
            try:
                rel = path.relative_to(REPO_ROOT) if path.is_absolute() else path
            except ValueError:
                rel = path  # outside REPO_ROOT (e.g. a test's temp dir): show it as given
            if arr.name in allowlist:
                skipped_allowlisted.append((arr, allowlist[arr.name]))
                continue
            section = image.section_of(arr.addr)
            if section is None or section[0] not in (".data", ".rdata"):
                skipped_outside.append((arr, rel))
                continue
            for i, our_val in enumerate(arr.values):
                addr = arr.orig_addr(i)
                raw = image.read(addr, arr.elem_size)
                if raw is None:
                    break
                if arr.disp_fmt == "f":
                    orig_val = struct.unpack("<f", raw)[0]
                    our_bytes = struct.pack("<f", our_val)
                else:
                    orig_val = struct.unpack("<" + arr.disp_fmt, raw)[0]
                    mask = (1 << (8 * arr.elem_size)) - 1
                    our_bytes = struct.pack("<" + arr.read_fmt, our_val & mask)
                if our_bytes != raw:
                    our_disp = our_val
                    mismatches.append((arr, rel, i, our_disp, orig_val))
    return scanned, mismatches, skipped_outside, skipped_allowlisted


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dr-data", default=os.environ.get("DR_DATA"))
    ap.add_argument("--exe")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv[1:])

    exe_path = args.exe
    if exe_path is None:
        if not args.dr_data:
            print("verify-tables: no dr.exe found: pass --exe, --dr-data, or set DR_DATA", file=sys.stderr)
            return 2
        exe_path = os.path.join(args.dr_data, "dr.exe")
    if not os.path.isfile(exe_path):
        print("verify-tables: original dr.exe not found at %s" % exe_path, file=sys.stderr)
        return 2

    files = [Path(f) for f in args.files] if args.files else game_sources(REPO_ROOT)
    image = OriginalImage(exe_path)

    scanned, mismatches, skipped_outside, skipped_allowlisted = verify(files, image, ALLOWLIST)

    for arr, rel, idx, ours, orig in mismatches:
        print("MISMATCH %s[%d] (%s:%d, original 0x%X): ours=%r original=%r" % (
            arr.name, idx, rel, arr.line, arr.orig_addr(idx), ours, orig))
    for arr, reason in skipped_allowlisted:
        print("allowlisted: %s (%s)" % (arr.name, reason), file=sys.stderr)
    for arr, rel in skipped_outside:
        print("skipped (suffix not in .data/.rdata): %s (%s:%d)" % (arr.name, rel, arr.line), file=sys.stderr)

    print("verify-tables: %d array(s) scanned, %d mismatch(es), %d skipped (outside .data/.rdata), %d allowlisted"
          % (scanned, len(mismatches), len(skipped_outside), len(skipped_allowlisted)))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
