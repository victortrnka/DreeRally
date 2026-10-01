#!/usr/bin/env python3
"""Verify initialised C arrays against the original dr.exe.

DreeRally keeps Hex-Rays' address-suffix naming convention for data it has
not renamed yet (`byte_445892`, `carAnimFrameSize_45FBA0`, ...): the digits
after the last underscore are the original static variable's address. That
convention silently rots the moment someone hand-types or hand-edits such a
table: nothing checks it against the original any more. This tool does.

It scans the game sources for initialised scalar arrays (`char`/`BYTE`/
`short`/`_WORD`/`int`/`_DWORD`/`float` and the other types in TYPE_INFO)
whose name ends in `_XXXXXX` (six hex digits), evaluates their C initialiser
into the flat sequence of elements C stores (zero fill, brace elision, a
string literal's NUL only when there is room for it), and compares each
element byte-for-byte against the original `dr.exe` at that address (VA ->
file offset through the PE section table, read with the element's own
size). Any mismatch is reported with the array, the index, and both values.

An address-suffixed array the tool cannot evaluate (unknown element type,
a cast, macro or expression, a designated initialiser, more initialisers
than the declared size, ...) is reported as UNPARSED with the reason: an
array that is silently dropped is a check that silently passes. The tool
exits non-zero if there is at least one mismatch or unparsed array.

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
    "sint8": (1, "B", "b"),
    "uchar": (1, "B", "B"),
    "_UNKNOWN": (1, "B", "b"),  # defs.h: #define _UNKNOWN char
    "__int8": (1, "B", "b"),
    "signed __int8": (1, "B", "b"),
    "unsigned __int8": (1, "B", "B"),
    "short": (2, "H", "h"),
    "short int": (2, "H", "h"),
    "unsigned short int": (2, "H", "H"),
    "ushort": (2, "H", "H"),
    "sint16": (2, "H", "h"),
    "__int16": (2, "H", "h"),
    "signed __int16": (2, "H", "h"),
    "unsigned __int16": (2, "H", "H"),
    "signed short": (2, "H", "h"),
    "unsigned short": (2, "H", "H"),
    "_WORD": (2, "H", "H"),
    "WORD": (2, "H", "H"),
    "uint16": (2, "H", "H"),
    "int16": (2, "H", "h"),
    "int": (4, "I", "i"),
    "signed": (4, "I", "i"),
    "signed int": (4, "I", "i"),
    "unsigned": (4, "I", "I"),
    "unsigned int": (4, "I", "I"),
    "uint": (4, "I", "I"),
    "sint32": (4, "I", "i"),
    "__int32": (4, "I", "i"),
    "signed __int32": (4, "I", "i"),
    "unsigned __int32": (4, "I", "I"),
    "long": (4, "I", "i"),
    "long int": (4, "I", "i"),
    "unsigned long": (4, "I", "I"),
    "unsigned long int": (4, "I", "I"),
    "ulong": (4, "I", "I"),
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
    # ui/util/popup.c: lines 0, 1 and 3 of the original's three sponsor
    # tables (0x447388, 0x448648, 0x449908; 6 cars x 10 lines x 80 bytes,
    # car stride 800). The port keeps each line as its own 4800-byte array
    # with car c at [800 * c], so only bytes 800*c .. 800*c+79 correspond
    # to the original at face value; the rest holds the other lines' text
    # there and zeros here. All 9 are blank in both (checked once with that
    # per-car mask); the tool does not model the mask, hence the allowlist.
    # See doc/KNOWN-ISSUES.md ("sponsor tables in popup.c").
    "byte_447388": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_4473D8": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_447478": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_448648": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_448698": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_448738": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_449908": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_449958": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
    "byte_4499F8": "one line of a de-interleaved sponsor table -- see doc/KNOWN-ISSUES.md",
}

TYPE_WORD = r"(?:unsigned|signed|const|static|short|long)"
DECL_RE = re.compile(
    r"(?P<type>" + TYPE_WORD + r"(?:\s+" + TYPE_WORD + r")*\s+[A-Za-z_][A-Za-z0-9_]*"
    r"|[A-Za-z_][A-Za-z0-9_]*)"
    r"[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*_(?P<addr>[0-9A-Fa-f]{6}))"
    r"[ \t]*(?P<dims>(?:\[[^\]\n]*\][ \t]*)+)"
    r"=(?!=)"
)
# `return x_445000[i] = 1;` matches DECL_RE too, but it is a statement.
STATEMENT_KEYWORDS = {"return", "else", "case", "do", "goto", "sizeof"}


def strip_qualifiers(type_text):
    words = [w for w in type_text.split() if w not in ("const", "static")]
    return " ".join(words)


# --- initialiser parsing ------------------------------------------------
# The initialiser is parsed into a tree (a brace group is a list) and then
# evaluated with C's rules for arrays of scalars: zero fill of short lists,
# brace elision, braces around a scalar, and a char array (or char row)
# initialised from a string literal, whose NUL is stored only when there is
# room for it. Anything else raises Unparsed with the reason: never a guess,
# never a silent skip.

class Unparsed(Exception):
    """A declaration or initialiser this tool cannot evaluate."""


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


def parse_initialiser(text, start):
    """From text[start] (just after the '='), return (init, end_index).

    init is one item: a brace group (a list of items), ('str', [byte
    values]) for a string literal -- adjacent literals already joined, and
    without the NUL, which evaluate() adds only where C stores it -- or
    ('num', token_text) for anything else. A char literal is turned into
    its value's digits inside the token, so `-'a'` still reads as one
    number and `'a' + 1` is rejected later as an expression. end_index is
    just past the ';' that ends the declaration.

    A raw ';' cannot appear inside an initialiser outside a string/char
    literal or a comment, and both are consumed whole before that check
    sees their bytes. Raises Unparsed for unbalanced braces and for a
    second declarator (`int a_445000[] = {1}, b_445010[] = {2};`), which
    would otherwise never be checked.
    """
    i, n = start, len(text)
    stack = [[]]
    buf = ""
    joinable = False  # last token was a string literal: a next one continues it

    def flush():
        s = buf.strip()
        if s:
            stack[-1].append(("num", s))
        return ""

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
            j = i + 1
            raw = []
            while j < n and text[j] != c:
                step = 2 if text[j] == "\\" and j + 1 < n else 1
                raw.append(text[j:j + step])
                j += step
            decoded = decode_c_chars("".join(raw))
            i = j + 1
            if c == "'":
                buf += " %d " % (decoded[0] if decoded else 0)
                joinable = False
            elif joinable and not buf.strip():
                stack[-1][-1][1].extend(decoded)  # "ab" "cd" is one literal
            else:
                buf = flush()
                stack[-1].append(("str", decoded))
                joinable = True
            continue
        if c in "{},;":
            buf = flush()
            joinable = False
            i += 1
            if c == "{":
                group = []
                stack[-1].append(group)
                stack.append(group)
            elif c == "}":
                if len(stack) == 1:
                    raise Unparsed("unbalanced '}'")
                stack.pop()
            elif c == "," and len(stack) == 1:
                raise Unparsed("more than one declarator in one statement")
            elif c == ";":
                if len(stack) != 1:
                    raise Unparsed("';' inside braces")
                if len(stack[0]) != 1:
                    raise Unparsed("expected one initialiser, found %d" % len(stack[0]))
                return stack[0][0], i
            continue
        buf += c
        if not c.isspace():
            joinable = False
        i += 1
    raise Unparsed("no ';' after the initialiser")


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


def parse_dims(dims_text):
    """The dimensions in "[6*64]" -> [384], "[9][50]" -> [9, 50], "[]" ->
    [None] (the first one may be empty: its size is inferred from the
    initialiser). Only integer literals and products of them are supported
    (carAnimFrameSize_445968[6*64] is the product case)."""
    dims = []
    for k, d in enumerate(re.findall(r"\[([^\]]*)\]", dims_text)):
        d = d.strip()
        if not d:
            if k:
                raise Unparsed("only the first dimension may be empty")
            dims.append(None)
            continue
        factor = 1
        for part in d.split("*"):
            try:
                factor *= parse_number(part, False)
            except ValueError:
                raise Unparsed("cannot evaluate dimension [%s]" % d)
        dims.append(factor)
    return dims


def evaluate(init, dims, is_char, zero):
    """The flat list of element values C stores for an array with
    dimensions `dims` initialised from `init` (see parse_initialiser).
    is_char: 1-byte elements, so a string literal may initialise the
    innermost dimension; zero: the fill value (0, or 0.0 for float)."""
    if isinstance(init, list):
        return _fill(dims, init, 0, True, is_char, zero)[0]
    if init[0] == "str" and is_char and len(dims) == 1:
        return _from_string(dims[0], init[1])
    raise Unparsed("an array initialiser must be a brace list or a string literal")


def _from_string(size, chars):
    if size is None:
        size = len(chars) + 1
    if len(chars) > size:
        raise Unparsed("string literal of %d chars for %d elements" % (len(chars), size))
    # The NUL is stored only if there is room: char x[2] = "AB" is valid C.
    return chars + [0] * (size - len(chars))


def _is_str(item):
    return isinstance(item, tuple) and item[0] == "str"


def _fill(dims, items, pos, braced, is_char, zero):
    """Initialise one array of `dims` from items[pos:]. braced: `items` is
    this array's own brace list, so every item must be used. Otherwise the
    braces were elided: take only what this array needs and leave the rest
    of the enclosing list to the caller. Returns (values, next_pos)."""
    count, sub = dims[0], dims[1:]
    sub_size = 1
    for d in sub:
        sub_size *= d
    if is_char and not sub:  # char x[N] = { "AB" }, or a row given as "AB"
        if braced and len(items) == 1 and _is_str(items[0]):
            return _from_string(count, items[0][1]), 1
        if not braced and pos < len(items) and _is_str(items[pos]):
            return _from_string(count, items[pos][1]), pos + 1
    values = []
    done = 0
    while (count is None or done < count) and pos < len(items):
        item = items[pos]
        if not sub:
            if isinstance(item, list):  # braces around a scalar: { {1}, 2 }
                if len(item) != 1 or isinstance(item[0], list):
                    raise Unparsed("a brace group of %d items for one element" % len(item))
                item = item[0]
            values.append(_scalar(item, zero))
            pos += 1
        elif isinstance(item, list):
            values.extend(_fill(sub, item, 0, True, is_char, zero)[0])
            pos += 1
        else:
            sub_values, pos = _fill(sub, items, pos, False, is_char, zero)
            values.extend(sub_values)
        done += 1
    if braced and pos < len(items):
        raise Unparsed("more initialisers than the declared size (%d)" % count)
    if count is None:
        count = done
    values.extend([zero] * (count * sub_size - len(values)))
    return values, pos


def _scalar(item, zero):
    if _is_str(item):
        raise Unparsed("string literal where a number is expected")
    text = item[1]
    if "=" in text:
        raise Unparsed("designated initialiser %r" % text)
    try:
        return parse_number(text, isinstance(zero, float))
    except ValueError:
        raise Unparsed("cannot evaluate %r (casts, macros and expressions"
                       " are not supported)" % text)


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


class UnparsedArray:
    def __init__(self, name, path, line, reason):
        self.name = name
        self.path = path
        self.line = line
        self.reason = reason


def find_arrays(path, text):
    """Yield a TableArray for every initialised, address-suffixed array
    declaration found in `text` (the contents of `path`), or an
    UnparsedArray with the reason when its type or initialiser cannot be
    evaluated."""
    masked = mask_comments(text)
    for m in DECL_RE.finditer(masked):
        type_text = strip_qualifiers(m.group("type"))
        if type_text in STATEMENT_KEYWORDS:
            continue
        name = m.group("name")
        line = text.count("\n", 0, m.start()) + 1
        try:
            info = TYPE_INFO.get(type_text)
            if info is None:
                raise Unparsed("unknown element type %r" % type_text)
            elem_size, read_fmt, disp_fmt = info
            dims = parse_dims(m.group("dims"))
            init, _end = parse_initialiser(text, m.end())
            values = evaluate(init, dims, elem_size == 1, 0.0 if disp_fmt == "f" else 0)
        except Unparsed as e:
            yield UnparsedArray(name, path, line, str(e))
            continue
        addr = RENAME_MAP.get(name, int(m.group("addr"), 16))
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
    unparsed = []
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
            if isinstance(arr, UnparsedArray):
                unparsed.append((arr, rel))
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
    return scanned, mismatches, unparsed, skipped_outside, skipped_allowlisted


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

    scanned, mismatches, unparsed, skipped_outside, skipped_allowlisted = verify(files, image, ALLOWLIST)

    for arr, rel, idx, ours, orig in mismatches:
        print("MISMATCH %s[%d] (%s:%d, original 0x%X): ours=%r original=%r" % (
            arr.name, idx, rel, arr.line, arr.orig_addr(idx), ours, orig))
    for arr, rel in unparsed:
        print("UNPARSED %s (%s:%d): %s" % (arr.name, rel, arr.line, arr.reason))
    for arr, reason in skipped_allowlisted:
        print("allowlisted: %s (%s)" % (arr.name, reason), file=sys.stderr)
    for arr, rel in skipped_outside:
        print("skipped (suffix not in .data/.rdata): %s (%s:%d)" % (arr.name, rel, arr.line), file=sys.stderr)

    print("verify-tables: %d array(s) scanned, %d mismatch(es), %d unparsed, %d skipped (outside .data/.rdata), %d allowlisted"
          % (scanned, len(mismatches), len(unparsed), len(skipped_outside), len(skipped_allowlisted)))
    return 1 if mismatches or unparsed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
