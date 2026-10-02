# Development on macOS

DreeRally is cross-compiled on macOS into a 32-bit Windows executable and run in
CrossOver. Everything below runs on Apple Silicon.

## Prerequisites

- CrossOver with **Death Rally (Classic)** from Steam installed in a bottle. The
  game files are copied from there; nothing in that bottle is modified.
- Build toolchain: `brew install llvm lld xwin`
- MSVC CRT and Windows SDK for x86. Running this accepts Microsoft's license:
  `xwin --accept-license --arch x86 --temp splat --output ~/.xwin`
- Reference tools (optional): `brew install openjdk@21 ghidra`

## Build and run

| Command | What it does |
|---|---|
| `make` | Debug build: `build/debug/dreerally.exe`, `.pdb`, `.map` |
| `make setup-run` | Creates the `DreeRally` bottle and copies the game files into `run/` |
| `make run ARGS="-window"` | Copies the build into `run/` and starts it in the bottle |
| `make check-equiv [BASE=rev]` | Machine-code equivalence against `BASE` (default `HEAD`) |
| `make verify-tables` | Compare hand-typed data tables against the original `dr.exe` |
| `make signcheck` | Rank functions whose signed/unsigned instructions differ from the original's |
| `make calldiff` | List calls the original makes that the port dropped, per function |
| `make stats` | Remaining Hex-Rays names per file (cleanup progress) |
| `make clean` | Removes `build/` |

If the game data lives elsewhere, pass `DR_DATA="/path/to/Death Rally"` to
`make setup-run` (quote it: the path contains spaces). `run/` holds its own `dr.cfg` and saves, separate from the
original game's.

Command-line flags are the original's (see its readme): the game starts
fullscreen, `-window` starts it in a window (Alt+Enter toggles), `-nogl`
uses the software renderer instead of OpenGL, `-smooth` turns on bilinear
filtering in races (F12 toggles) and `-nosound` disables music and effects.
`-noeffect`, `-lang=` and `-mod=` are port additions. Under CrossOver use
`make run ARGS="-window"` for a window.

## Crashes

Wine prints an unhandled-exception backtrace, in the terminal or a crash
dialog. Frame 0 — the actual crash site — is symbolized with function name
and file:line from the PDB. Outer frames are often address-only; name them
with:

```
/opt/homebrew/opt/llvm/bin/llvm-symbolizer --obj=build/debug/dreerally.exe 0x<addr>
```

or find the nearest lower address in `build/debug/dreerally.map`.

**Never attach `winedbg` to a running game.** CrossOver's 64-bit `winedbg`
injects a break-in thread into the 32-bit process at a truncated address, and
that thread immediately faults. This shows up as a spurious
`Unhandled page fault ... at 0xfff50de4` (0xfff50de4 is `DbgUiRemoteBreakin`'s
real, 64-bit address, `0x6ffffff50de4`, truncated to 32 bits) — it is an
artifact of attaching, not a game bug.

A return address made of printable ASCII bytes (e.g. `0x25252525` = `"%%%%"`,
or `0x2E303A30` = `"0:0."`) means a stack buffer overflow: some string-building
code walked past its buffer and overwrote the saved return address with its
own text. See "Common translation bugs" below.

## Sound

The Makefile no longer defines `_NO_MINIFMOD`: `sfx/minifmod/soundSystem.c`
(the minifmod mixer used for sound effects) builds with clang-cl, and sound
effects are on. The `#ifndef _NO_MINIFMOD` guards stay in the sources because
`Makefile.linux` still defines it. Music (via FMOD) works as before. Notes for
anyone touching this area:

- `libincludes/minifmod/Sound.h` pulls in real `<windows.h>`/`<mmsystem.h>`,
  which redefines `BYTE`/`WORD`/`DWORD`/`LONG` with different underlying types
  than `defs.h`. `sfx/minifmod/soundSystem.h` keeps real windows.h out (it
  stands in the handful of types Sound.h actually needs) rather than touching
  `defs.h`'s typedefs project-wide.
- clang-cl's MS-style `__asm` accepts `[reg].field` only when it can infer
  the struct type from a plain, directly-assigned C variable; every other
  register-relative field access in the ported asm needs an explicit
  `[reg]STRUCT.field`, and ambiguous-size memory/immediate comparisons need
  an explicit `dword ptr`. Both are spelled out with the identical resulting
  instructions - see `sfx/minifmod/soundSystem.c`.
- `libs/minifmod.lib` is on the link line but no longer contributes any
  object to the binary: `soundSystem.c` now defines the handful of globals
  (`FSOUND_Channel`, `FSOUND_MixBlock`, `FMUSIC_Channel`,
  `FMUSIC_DummyInstrument`, `FSOUND_Software_RealBlock`) that would otherwise
  pull in `libs/minifmod.lib`'s own threaded/waveOut mixer path, which needs
  imports and a CRT exception helper this build doesn't otherwise have.

## Refactor or fix?

Every commit is one or the other:

- **`refactor:`** renames, types, structs, formatting and comments. Must print
  `EQUIVALENT` from `make check-equiv` before committing.
- **`fix:`** deliberately changes behaviour to match the original game. The
  commit message names the original function address and the evidence.
  `make check-equiv` must list exactly the functions you meant to change.

Moving functions between files changes the link layout even when the code is
unchanged, so `check-equiv` prints `DIFFERENT`. The relocation-aware listing
should then report no real changes, only moved functions, but no such commit
has been made yet, so treat moves as unproven.

### `make check-equiv` output

- `EQUIVALENT`: `make check-equiv` exits 0; every section of the built PE is
  byte-identical to `BASE`.
- `DIFFERENT`: the checker exits 1, which make reports as
  `make: *** [check-equiv] Error 1`; `make` itself then exits **2**, so test
  `$? -ne 0` in scripts. The output has a size diff per differing section, and
  for `.text`:
  - `functions with different bytes: N` — raw count, before normalization.
  - `functions changed (real): N`, followed by the list (`0xADDR name -> name
    size 0x.. -> 0x..  obj`). This list must be exactly the function(s) you
    meant to change.
  - `moved-only (collateral, bytes differ but normalized code does not): N` —
    pure relocation noise from something else moving in the image; not a real
    change.
  - `library functions with different bytes: N (not listed, M changed after
    normalization)` — compiler/runtime library code, excluded from the named
    listing.
  - `added:`/`removed:` counts and lists, if any game functions were added or
    removed.
- Needs `llvm-objdump` (`LLVM=` overrides the default
  `/opt/homebrew/opt/llvm/bin`, same as the main build).
- The `BASE` build is cached under `build/equiv/<sha>-<makefile-hash>/`; your
  own working tree is always rebuilt from scratch.
- Known limitation: adding or removing an unnamed literal can shift the symbol
  that anchors unnamed `.rdata`, so a function that only *reads* such data can
  show up in `functions changed (real)` even though its own code didn't
  change. Confirm this from the disassembly (the tool prints ready-to-run
  `llvm-objdump` commands for the first changed function) before treating it
  as a real change.

## Headless Docker test runner

`make docker-test` builds `dreerally.exe` and a key-injector `keys.exe`,
assembles its own `run-docker/` runtime dir (or `run-docker-orig/` with
`ORIG=1`) — never `run/`, so it never collides with a CrossOver run in
progress — and runs the game headless in a `linux/amd64` Wine+Xvfb Docker
container. Screenshots and a log land in `build/docker-out/` (override with
`OUT_SHOTS=`).

```sh
make docker-test                                   # default: reach the main menu
make docker-test SCENARIO=race SECS=90              # start a race, run for 90s
make docker-test DOCKER_ARGS="-window -nosound -nogl" KEYS="down enter" SHOTS="3:a 9:b"
make docker-test ORIG=1 SCENARIO=results-orig       # run the original dr.exe instead
```

Variables (Makefile defaults in parentheses):
- `DOCKER_ARGS` (`-window -nosound`) — `dreerally.exe`'s own arguments.
- `KEYS` (empty) — tokens for `keys.exe`: named keys
  (`up`/`down`/`left`/`right`/`enter`/`esc`/`space`/`back`, in a race
  `f1`/`tab`, and `f6` for a screenshot, `HS-PICnn.PCX` in the run
  directory), letters `a`-`z`,
  `wNNN` to wait `NNN` ms, and `shot:<label>` to take a mid-sequence screenshot
  (handled by `entrypoint.sh`, which splits the sequence there). Ignored if
  `SCENARIO` is set.
- `SHOTS` (`3:intro 9:menu`) — fixed "seconds-since-launch:label" shots taken
  before `KEYS` starts.
- `SECS` (`12`) — total seconds before the game is stopped; each `keys.exe`
  segment's own timeout scales with this.
- `OUT_SHOTS` (`build/docker-out`) — where screenshots, `wine.log` and
  `status.txt` land.
- `SCENARIO` (empty) — reads `KEYS` from `tools/docker/scenarios/<name>.keys`
  instead: `menu`, `configure-effects`, `race`, `results`, `results-orig`.
- `ORIG` (`0`) — `1` copies the original `dr.exe` (+ `msvcr71.dll`) from
  `DR_DATA` into `run-docker-orig/` and runs that instead of our build.
  `DR_DATA`/the Steam bottle are only ever read.
- `AUDIO` (`0`) — `1` starts a PulseAudio null sink and records its
  monitor to `audio.wav` in `OUT_SHOTS` for the run. The default
  `DOCKER_ARGS` (`-nosound`) and `AUDIO=0` both skip `FSOUND_Init`, so
  none of the sound code (`FreeSong`, the file callbacks, `loadMusic`'s
  frees, `FSOUND_Close`) ever runs; checking sound code needs real sound,
  `DOCKER_ARGS="-window" AUDIO=1`.

Things to know:

- **Pin Wine 8.0 from Debian bookworm, not WineHQ's repo.** WineHQ 11.0's new
  WoW64 `ntdll` aborts on this host's amd64-under-QEMU emulation even at plain
  `wineboot --init` (see `tools/docker/Dockerfile`'s comment). Re-verify with a
  rebuild before ever bumping the Wine version.
- Containers run amd64 via QEMU user-mode emulation on this Apple Silicon
  host; whether enabling Docker Desktop's Rosetta option changes that was not
  conclusively established.
- `wineserver -w` occasionally hangs. Every wait in `entrypoint.sh`, and
  `run.sh`'s own host-side watchdog, are time-bounded, so a run always
  finishes and reports a status — but treat an unusually slow run's *timing*
  as unreliable even when its *result* looks fine.
- **No symbolized crash backtraces** come out of the container: a crash is
  reliably detected (the `Unhandled ...` line, reported as `STATUS=crashed`
  and saved to `crash.txt`), but there is no working PDB-symbolized call
  stack. Symbolize on the host instead (see "Crashes" above).
- GL mode needs Mesa's software rasterizer (`LIBGL_ALWAYS_SOFTWARE=1`, baked
  into the image), since the container has no GPU. The *original* `dr.exe`
  needs it too and has no non-GL fallback; the port degrades gracefully via
  `-nogl` either way.
- **Never run two `make docker-test` at the same time in one worktree.**
  Each run starts with `rm -rf` of its runtime directory (`run-docker/`,
  or the `-orig`/`-orighook` one) and writes to the same `OUT_SHOTS`, so a
  second run deletes the first one's files under it. Run them one after
  the other, or from separate worktrees.
- **Screenshot, then check state, before sending the next key.** The
  intro-skip count is not deterministic. Esc on the main menu is not a no-op:
  it moves the highlighted item to the last one ("Exit to OS"), not back to a
  previous menu — none of the built-in scenarios rely on it to reach the main
  menu.

## Verifying data tables

`make verify-tables` scans the game sources for initialised arrays whose
name still ends in an original address (`_XXXXXX`, six hex digits, the
Hex-Rays convention -- see `doc/CONTRIBUTING.md`), reads the original
`dr.exe` from `DR_DATA`, and compares every element byte-for-byte. It
exits non-zero and prints the array, index and both values on any
mismatch. These arrays were hand-typed from Hex-Rays output or Ghidra
dumps at some point, and nothing else checks them against the original
ever again; `check-equiv` cannot catch a wrong data value, only a code
change. See `doc/FINDINGS.md`'s "hand-typed data tables" bug class.

The initialiser is evaluated with C's rules, so the compared bytes are
the bytes the compiler stores: short lists and short rows are zero-filled
(each row of `char t[9][50] = { "Brake", ... }` is padded to 50), brace
elision works, and a string literal's NUL is stored only when there is
room for it. An address-suffixed array the tool cannot evaluate (an
unknown element type, a cast, macro or expression, a designated
initialiser, more initialisers than the declared size, two declarators
in one statement) is printed as `UNPARSED` with the reason and also makes
the run fail: an array that is silently skipped is a check that silently
passes.

A genuine port typo found this way gets its own `fix:` commit, byte-exact
against `dr.exe`. An array whose name suffix is provably not its real
address is better renamed to the correct address (a `refactor:` commit,
`EQUIVALENT`) than added to the tool's exception lists.
`tools/verify-tables.py` has three small, explicit lists for what renaming
cannot fix:
- `STRIDE`: arrays that are one column of a larger original table, so
  element `i` is at `addr + stride * i`. The seven menu layout arrays in
  `ui/menu.c` are the columns of the original's 9x7 int table at
  0x4456F0, one 0x1C-byte row per menu type.
- `RENAME_MAP`: a suffix that is definitely wrong but whose correct name is
  not worth cleaning up yet.
- `ALLOWLIST`, with a reason: an array the tool cannot compare as is
  (today the nine blank sponsor-table lines in `ui/util/popup.c`, see
  `doc/KNOWN-ISSUES.md`).

Tests: `python3 tools/test_verify_tables.py`.

## Signedness check

`make signcheck` looks for the "Unsigned `_DWORD` where the original uses
`sar`" and "Signed `BYTE`" bug classes (`doc/FINDINGS.md`): Hex-Rays types
a value as unsigned where the original treats it as signed, or the other
way round, and the port then compiles `shr` for the original's `sar`,
`div` for `idiv`, `jb`/`ja` for `jl`/`jg`, `movzx` for `movsx`.
`check-equiv` cannot see this; the code is wrong from the start.

`tools/signcheck.py` pairs each port function with its original by
address (the `//----- (00XXXXXX)` marker above the definition, a marker
above a commented-out copy of the signature when the function moved to
another file, or an `_XXXXXX` name suffix). It disassembles the debug
build's function (range from the map) and the original from its address
to the next known function start or switch jump table. In both it counts
the signed and unsigned form of six categories: `sar`/`shr`,
`movsx`/`movzx`, `idiv`/`div`, one-operand `imul`/`mul`, signed/unsigned
`jcc`/`setcc`, and `cdq`/`xor edx, edx` before a divide. It ranks the
functions by how many signed instructions the port has swapped for
unsigned ones or the other way round, e.g. "orig sar 5 shr 0 | port sar
2 shr 2" is 2 lost. Idioms that look like a signedness signal but are
not are left out: a shift whose result is masked so the shifted-in bits
never matter, `shr r, 31` (the sign bit), MSVC's division by a constant,
`abs()`, the port's 0/1 booleans and x87 control word, conditions after a
float compare, and switch range checks.

The compilers differ (optimised MSVC against clang-cl `/Od`), so the
list is candidates to check by hand, not a verdict. Read each against
the source (`--show` prints both sides' instructions and the port's
`file:line`), then decide whether the value can actually be negative (or
reach 0x80/0x8000/2^31 for the reverse direction).

```sh
make signcheck                                         # top 40 candidates
make signcheck SIGNCHECK_ARGS="--all"                  # every hint, plus unpaired functions
make signcheck SIGNCHECK_ARGS="--show refreshScreen"   # or --show 0x43B580
```

Two things worth knowing beyond single candidates: the original's game
code has **no** `movsx` at all, apart from two joystick-axis reads at
0x43C674/0x43C690 and minifmod's code from 0x43D940 on, so nearly every
`movsx` the port has in game code loads a byte or word the original
zero-extends; and a function missing from the list may simply be
unpaired (`--all` lists those).

Tests: `python3 tools/test_signcheck.py`.

## Call check

`make calldiff` looks for the "Original code commented out by the port
author" class (`doc/FINDINGS.md`): a call the port dropped, whether it
was commented out with `//`, hidden in a `/* ... */` block or deleted
outright. A grep only finds the first kind.

`tools/calldiff.py` pairs functions like signcheck and collects each
side's call targets. In the original these are `call rel32`, a `jmp` to
another function's start (a tail call), `call [IAT]`, and `call reg`
after `mov reg, [IAT]`; a call through a `jmp [IAT]` or `jmp func` stub
counts as a call to what the stub jumps to. In the port the map names
every target, also through the function-pointer locals Hex-Rays made of
MSVC's import registers (`v8 = rand; v8()`). Port callees are mapped to original addresses through the
pairing, and per function the tool lists:

- `missing`: an original callee the port never calls, with the count
  of calls on each side;
- `fewer`: one it calls fewer times;
- `lib`: a library call (by name) the port makes fewer times;
- `extra`: a port callee the original does not call, printed as context
  next to the lost ones.

Each lost callee gets a hint. `commented` or `in code` means its name
(any name the sources give its address, or `sub_XXXXXX`) occurs in a
comment, or in the code, of the port function's source lines (from the
PDB). `via X` means the port's extra callee X calls it: MSVC inlined X
in the original. `port calls its callee X` means the port calls X
directly where the original called a wrapper around it. `none` means
the call was deleted or never translated.

Functions are grouped by the original's own call graph: `race`
(reachable from startRace), `menus` (from mainMenu), `startup` (from the
game's main, 0x43ACE0), `other` (reached only through function
pointers), and last `multiplayer` (a `multiplayer_*` function, or
reachable only through one).

Noise to expect:
- MSVC inlined small functions in the original, so their callees show
  up as lost in the caller. startRace's 32 `setWindowCaption`,
  `freeMusic`, `printf` and `exit` calls are allocateMemory's error
  path, inlined at each of its allocations; the port calls `malloc`
  directly.
- The original calls `_ftol2` for every float-to-int conversion and
  `_allshr` for a 64-bit shift, while clang does both inline; they are
  left out.
- A bare `ret` function (0x43C720, the port's `nullsub_1`) is ignored
  on both sides.
- An original callee without a marker (`sub_XXXXXX` that the port names
  differently) shows up as missing next to an `extra` unpaired port
  function, as in postRaceMain's `sub_423870` and `loadGraphics4`.

```sh
make calldiff                                          # every function with a lost callee
make calldiff CALLDIFF_ARGS="--all"                    # also functions with only extra callees
make calldiff CALLDIFF_ARGS="--func startRace"         # or --func 0x415710
```

Tests: `python3 tools/test_calldiff.py`.

## Hooking the original dr.exe

`winedbg` does not work in this container (see "Environment pitfalls" in
`doc/FINDINGS.md`), so the original's own runtime state is instead observed
with `tools/orighook/`: an in-process hook DLL loaded into a **patched COPY**
of `dr.exe`, never the Steam install.

- `tools/orighook/patch_exe.py` copies `dr.exe`, checks its sha256 against
  the known Steam build before touching anything, and appends a 16-byte
  stub into `.text`'s existing zero slack (no file growth needed for this
  build): `push <hook DLL name>; call dword ptr [0x44100C]` (the resolved
  `LoadLibraryA` IAT slot -- already valid by the time this runs, since
  Windows resolves every import before calling a PE's entry point) `; jmp
  <original AddressOfEntryPoint>`. It then points `AddressOfEntryPoint` at
  the stub and extends `.text`'s `VirtualSize` so the loader maps it. It
  refuses to write its output over the source file.
- `tools/orighook/hook_template.c` is the DLL: one example hook (an
  ordinary 5-byte-`jmp`-plus-trampoline x86 inline detour) on
  `calculateNextRaces` (original `0x4240B0`), which logs each call to
  `orighook.log` in the current directory and otherwise runs the original
  function unchanged. The file's own comment explains how to point it at a
  different or additional function. `DllMain` runs from the stub, before
  dr.exe's own entry point: code and initialised data can be patched, but
  the original's CRT startup has not run yet.
- `make orighook` builds the DLL with the same clang-cl/lld/xwin toolchain
  as the main game; `make docker-test ORIGHOOK=1 SCENARIO=orighook-race`
  builds it, patches a copy of `dr.exe` into `run-docker-orighook/` (never
  `run/`), and runs it through the headless Docker runner. `orighook.log`
  lands in `run-docker-orighook/` afterwards.

```sh
make docker-test ORIGHOOK=1 SCENARIO=orighook-race SECS=60
cat run-docker-orighook/orighook.log
```

Proven working: the log shows the hook installing and firing
(`calculateNextRaces (0x4240B0) call #1`) while the original game runs to a
live race, `STATUS=alive`, `0 Unhandled`.

## Common translation bugs

Two patterns turned up repeatedly while porting Hex-Rays output;
worth checking for in new code too.

1. **A one-char or scalar local receiving a string.** Hex-Rays sometimes
   decompiles a stack string as a single `char`/scalar local plus a
   `(char *)&v + k` walk that finds its "end" by scanning for the first zero
   byte above it — which only worked in the *original* binary's stack layout.
   In the port's differently-laid-out frame, the walk lands on adjacent
   locals, saved registers, or the return address, and a
   `strcpy`/`strcat`/`_itoa` through it overwrites them. Symptom: a crash with
   a return address made of printable ASCII (see "Crashes" above). Fix: size
   the buffer from the *original* frame (`sub esp` and the `lea`/`[ebp-N]`
   offsets, from Ghidra or objdump) as a real fixed-size `char[]`, and write
   into it in the original's order with plain `strcpy`/`strcat`/`_itoa`, not a
   raw pointer walk.
2. **A global declared as one string, indexed as a table with a stride.**
   E.g. `&aBorrow12000Pay[240 * v1]` or `&aVagabond[1760 * car]`: the
   Hex-Rays global is only as long as its first row's literal, but the code
   reads/writes further rows past its end. Fix: restore the whole table
   byte-exact from the original's `.data` (`llvm-objdump -s -j .data`), not by
   hand-typing strings.

For both: verify against the original with Ghidra
(`tools/ghidra/decompile.sh`) and `llvm-objdump`, and `make check-equiv` must
list exactly the function(s) you changed.

Practical tips:
- Some sources are ISO-8859, not UTF-8. Plain `grep` may treat them as binary
  or (with ugrep) skip them; use `grep -a`. Edit
  byte-preservingly (e.g. `LC_ALL=C perl -pi`) and confirm the encoding is
  unchanged with `file` afterwards.
- For frame-layout instrumentation, use `__builtin_frame_address(0)`; a
  clang-cl `__asm` block grows the frame at `/Od` and will throw off the
  measurement.

## Comparing with the original (Ghidra)

```
tools/ghidra/setup.sh              # once: import and analyse the original dr.exe
tools/ghidra/sync-names.sh         # after renaming functions: push our names to Ghidra
tools/ghidra/decompile.sh 0x415710 # print the original function at that address
```

The project lives in `~/Ghidra/DreeRally`. Close the Ghidra GUI before running
the scripts, because a project open in the GUI is locked.

## Windows

Open `DreeRally.sln` in Visual Studio 2022 and build `Debug|Win32`. CI builds
the same project on every push.
