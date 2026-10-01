#!/usr/bin/env python3
"""Patch a COPY of the original dr.exe to LoadLibraryA a hook DLL at startup.

Never touches the source file: it is only ever read, and its SHA-256 is
checked against the known Steam build before anything else happens. The
patch appends a small stub into the zero slack already present at the end
of .text's raw data (no file growth needed for this build of dr.exe):

    push  <VA of the hook DLL's file name, a NUL-terminated ASCII string
           appended right after the stub>
    call  dword ptr [0x44100C]      ; the resolved LoadLibraryA IAT slot
    jmp   <the original AddressOfEntryPoint>

then points AddressOfEntryPoint at the stub and extends .text's
VirtualSize so the loader actually maps it. By the time this stub runs,
the OS has already resolved every import (imports are always resolved
before a PE's entry point is called), so the IAT slot already holds the
real LoadLibraryA address -- this needs no import-table parsing.

0x44100C is KERNEL32!LoadLibraryA's slot in this exact dr.exe build's
import address table (sha256 below; read from its import directory). The
jump-back target is instead read from the file's own PE header
(AddressOfEntryPoint) and asserted to match this build's known entry point
(0x43FA60), rather than trusting a second hardcoded constant.

Usage: tools/orighook/patch_exe.py SOURCE_DR_EXE OUTPUT_EXE HOOK_DLL_NAME
OUTPUT_EXE must not be SOURCE_DR_EXE (or a link to it); that is refused.
Python 3.9, stdlib only.
"""
import hashlib
import os
import struct
import sys
from pathlib import Path

EXPECTED_SHA256 = "54fe789faca583d67b8e73e7c58908f3f1468c5c8f75942239a60483ae9be58c"
LOADLIBRARYA_IAT_VA = 0x44100C
EXPECTED_ORIGINAL_ENTRY_VA = 0x43FA60


def read_pe_header(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise SystemExit("not a PE image")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    entry_rva = struct.unpack_from("<I", data, opt + 16)[0]
    return pe, opt, opt_size, count, image_base, entry_rva


def find_text_section(data, table, count):
    for i in range(count):
        entry = table + 40 * i
        name = data[entry:entry + 8].rstrip(b"\0")
        if name == b".text":
            vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, entry + 8)
            return entry, va, vsize, raw_ptr, raw_size
    raise SystemExit("no .text section")


def patch(src_path, out_path, dll_name):
    src_path = Path(src_path)
    out_path = Path(out_path)
    # The source passes the sha256 check below, so without this guard
    # "patch_exe.py dr.exe dr.exe x.dll" would overwrite the original.
    if out_path.exists() and os.path.samefile(src_path, out_path):
        raise SystemExit(
            "patch_exe: OUTPUT %s is the same file as SOURCE %s -- refusing "
            "to overwrite the original" % (out_path, src_path))
    data = bytearray(src_path.read_bytes())

    sha = hashlib.sha256(data).hexdigest()
    if sha != EXPECTED_SHA256:
        raise SystemExit(
            "patch_exe: %s has sha256 %s, expected %s -- refusing to patch "
            "an exe this tool has not been verified against"
            % (src_path, sha, EXPECTED_SHA256))

    pe, opt, opt_size, count, image_base, entry_rva = read_pe_header(data)
    original_entry_va = image_base + entry_rva
    if original_entry_va != EXPECTED_ORIGINAL_ENTRY_VA:
        raise SystemExit(
            "patch_exe: original entry point is 0x%X, expected 0x%X "
            "(the verified build's value) -- the jmp-back "
            "target below would be wrong" % (original_entry_va, EXPECTED_ORIGINAL_ENTRY_VA))

    table = opt + opt_size
    text_entry, text_va, text_vsize, text_raw_ptr, text_raw_size = find_text_section(data, table, count)

    name_bytes = dll_name.encode("ascii") + b"\0"
    stub_rva = (text_va + text_vsize + 3) & ~3  # 4-byte align, cosmetic only
    string_rva = stub_rva + 16
    new_vsize = (string_rva + len(name_bytes)) - text_va
    if new_vsize > text_raw_size:
        raise SystemExit(
            "patch_exe: stub + name (%d bytes past .text's current VirtualSize) "
            "does not fit in .text's existing raw slack (%d bytes free) -- "
            "this dr.exe build has less free space than the verified one"
            % (new_vsize - text_vsize, text_raw_size - text_vsize))

    slack_start = text_raw_ptr + text_vsize
    slack_end = text_raw_ptr + new_vsize
    if data[slack_start:slack_end] != b"\0" * (slack_end - slack_start):
        raise SystemExit("patch_exe: the .text slack this stub would use is not all zero -- refusing to overwrite it")

    stub_va = image_base + stub_rva
    string_va = image_base + string_rva
    jmp_instr_va = stub_va + 11  # 5 (push) + 6 (call [mem]) bytes before it
    jmp_rel32 = original_entry_va - (jmp_instr_va + 5)

    stub = struct.pack("<B I", 0x68, string_va)                       # push string_va
    stub += struct.pack("<BB I", 0xFF, 0x15, LOADLIBRARYA_IAT_VA)     # call dword ptr [IAT]
    stub += struct.pack("<B i", 0xE9, jmp_rel32)                      # jmp original_entry_va
    assert len(stub) == 16, len(stub)

    file_off = text_raw_ptr + (stub_rva - text_va)
    data[file_off:file_off + 16] = stub
    data[file_off + 16:file_off + 16 + len(name_bytes)] = name_bytes

    struct.pack_into("<I", data, text_entry + 8, new_vsize)  # VirtualSize
    struct.pack_into("<I", data, opt + 16, stub_rva)          # AddressOfEntryPoint

    out_path.write_bytes(bytes(data))
    return stub_va, string_va


def main(argv):
    if len(argv) != 4:
        print("usage: patch_exe.py SOURCE_DR_EXE OUTPUT_EXE HOOK_DLL_NAME", file=sys.stderr)
        return 2
    stub_va, string_va = patch(argv[1], argv[2], argv[3])
    print("patched %s -> %s: entry point now the stub at 0x%X, loads %r" % (argv[1], argv[2], stub_va, argv[3]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
