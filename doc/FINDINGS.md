# Findings: bug classes from porting Death Rally

DreeRally is a readable decompilation of `dr.exe`: every function stays 1:1
with the original, translated from Hex-Rays/Ghidra output. That translation
went wrong in the same handful of ways, over and over. This catalogue exists
so the next contributor recognises the pattern instead of re-discovering it.
For each class: the symptom, what the code looks like, a few example commits
(`git log --oneline`), and how to detect and verify it.

## Stack-walk idiom / one-char buffers

**Symptom:** a crash whose saved return address is printable ASCII (e.g.
`0x25252525` = `"%%%%"`), usually well after the string-building code that
caused it.

**What it looks like:** Hex-Rays sometimes decompiles a stack string as a
single scalar local plus a `(char *)&v + k` walk that finds the buffer's
"end" by scanning for the first zero byte above it on the stack -- which only
works in the *original* binary's own stack layout. In the port's differently
laid-out frame, the walk lands on adjacent locals, saved registers, or the
return address, and a `strcpy`/`strcat`/`_itoa` through it overwrites them.

```c
// before (01dc1b1, openAnimation): Filename is one char, not a buffer
char Filename;
strcat((char *)&Filename + 3, "SANIM.haf");
```

**Examples:** `01dc1b1 fix: give openAnimation a 256-byte file name`,
`715098c fix: give showAdjustOptions a 12-byte buffer`,
`5fdd276 fix: give addParticipantToRace stack text buffers`,
`cd8b50c fix: give drawStadistics its stack text buffers`,
`e0659bb fix: give showCarBought a stack price buffer`,
`8eb602b fix: build enterShop's buy-car text on the stack`,
`d034af9 fix: build quicksave name in a 16-byte buffer`,
`cf060a8 fix: give previewRaceScreen a 40-byte Str`,
`f2c13d1 fix: give previewRaceScreen a 20-byte DstBuf`.

**Detect / verify:** grep for `(char *)&` / `(int)&` walks on a scalar
local feeding a `strcpy`/`strcat`/`_itoa`/`sprintf`. Size the buffer from the
*original* frame (`sub esp` and the `lea`/`[ebp-N]` offsets, from Ghidra or
`llvm-objdump`), declare it as a real fixed-size `char[]`, and write into it
in the original's order with plain string calls, not a pointer walk. Confirm
with `make check-equiv` (the changed function must be exactly the one
touched) and, where reachable, a Docker run showing `STATUS=alive` with
`0 Unhandled` where it used to crash.

## Strided tables declared as one truncated row

**Symptom:** text (a loan offer, a sponsor's popup, an accepted-text
message) is correct for one specific item and garbled or blank for every
other one of the same kind.

**What it looks like:** a Hex-Rays global is only as long as its first row's
string literal, but the code indexes it with a shared stride across several
rows (one row per car type, sponsor, etc.):

```c
// before (6ec5444): only byte_452140 was ever given room for 5 rows
char aBorrow12000Pay[40] = "Borrow \$12,000 - Pay \$18,000";
...
drawLoanShark(..., &aBorrow12000Pay[240 * carType], ...);  // carType 1..4 reads garbage
```

**Examples:** `6ec5444 fix: restore drawLoanShark message tables`,
`a44f4fc fix: restore loadAcceptedText message tables`,
`1ba2b7a fix: restore six-row sponsor popup tables`.

**Fix:** restore the whole table byte-exact from the original's `.data`
(`llvm-objdump -s -j .data`), not by hand-typing strings; a script that
reads the original's stride and row count and emits a C initialiser avoids
the transcription errors that caused the original bug. **`make
verify-tables`** (below) now checks every such table on every run, so a
future regression here is caught immediately rather than only when the
animation advances far enough to show it.

## Hand-typed data tables with typos

**Symptom:** wrong, but plausible-looking, numeric data -- a frame-size
table off by one entry, so an animation desyncs or a decrypt routine reads
past its buffer only once the animation actually reaches that frame.

**Example:** `c66cd91 fix: correct three shop animation frame sizes` --
`continueAnimFramesSize_4611D0`'s frame 1 was `0x577` where the original has
`0x5F7`; every later frame in that table then started 128 bytes early and
`decryptTexture` eventually walked off the end.

This is exactly the class **`tools/verify-tables.py`** (`make
verify-tables`) now exists to catch on every run, instead of only once a bug
happens to be visibly reachable. It scans the
game sources for every initialised array whose name still carries an
original address suffix (`_XXXXXX`), reads the real `dr.exe`, and compares
element by element. Run against the current tree it found, and the
commits below fixed:

- two more arrays with a *name* bug of the same kind `c66cd91` already fixed
  by *value*: `carAnimFrameSize_45FBA0` and `continueAnimFramesSize_4611D0`
  both had their address suffix pointing at their sibling `*CurrentFrame`
  counter instead of their own table (`refactor: fix two wrong address
  suffixes in anim tables`; `c66cd91`'s own `Checked:` trailer already names
  `0x445968` as one of "all six tables" without ever renaming the symbol);
- five single/scattered-element typos across `byte_445892`,
  `menuActive_4457F0`, `streamId_4444F8`, `letterSpacing_4458B0` and
  `bigLetterSpacing_445848` (`fix: correct five hand-typed table values`).

It also turned up two layout problems too large to fix mechanically; see
`doc/KNOWN-ISSUES.md` ("menu layout tables use the wrong
stride", "sponsor-popup stub tables in popup.c").

## Missing per-driver stride

**Symptom:** an effect (muzzle flash, a shot, a popup) works for driver/car
0 and silently does nothing, or reads someone else's state, for every other
car.

**What it looks like:** a per-driver array declared and indexed as if each
driver used one slot, when the original driver struct is 108 bytes
(`0x6C`) resp. the race-participant struct's live fields need a 216-int
(`0x360`-byte) stride, and only slot/driver 0 happens to start at offset 0:

```c
// before (8053a9f): drawFlames_4A7EB8[v3], should be [216 * v3]
drawFlames_4A7EB8[v3] = 1;
```

**Examples:** `8053a9f fix: index muzzle flash by driver stride`,
`e807dc9 fix: index shot flash/trail arrays by stride`,
`48dd425 fix: reset live shot-state arrays each race` (the same stride
missing from a reset loop, so state from a previous race leaked into the
next one for everyone but slot 0).

**A new, not-yet-fixed instance**, found by `make verify-tables`: seven
`ui/menu.c` globals (`dword_4456F0`, `_4456F4`, `_4456F8`, `_4456FC`,
`_445700`, `_445704`, `_445708`, "menu sizes/positions" per-menu-type) are
really one interleaved 9-row x 7-column table at `0x4456F0` with a `0x1C`
(28-byte) row stride, each declared instead as a separate contiguous 9-int
array -- only index 0 of each is correct. See `doc/KNOWN-ISSUES.md`.

**Detect / verify:** when a per-driver/per-participant/per-menu-type value
is wrong for everything but index 0, check the original's stride between
struct instances (Ghidra's struct size, or -- as with the menu table above
-- read the original at a hypothesised stride and confirm a constant column
reads the same constant at every row).

## Dead globals or struct shadows versus the live data

**Symptom:** a feature that depends on "who's in the lead" or "how many
points does X have" always behaves as if the answer were the initial/zero
value, even though the underlying race state is otherwise correct.

**What it looks like:** Hex-Rays named two different things that are really
the same original global, and the port kept both -- writing the live one but
reading the dead one, or vice versa:

- `dword_45EB50` should be `racePositions` (`5908f4b fix: build the
  sabotage popup like the original`, `6ce7587`; the sabotage popup and the
  hitman quest both read a `dword_45EB50` that nothing ever writes);
- `dword_4608F0` should be `&drivers[1].points` (`8b08dca fix: point the
  max-other-points loop at drivers[]`: a 256-int global nothing ever writes,
  used for "does anyone else have more points", always reading 0, i.e.
  "nobody ever beats me");
- `initRaceValues` zeroed a dead shadow instead of the live, strided array
  (`48dd425`, above).

**Detect / verify:** `git grep` for a `dword_`/`byte_` global that is only
ever *read*. If nothing in the tree writes it, it is almost certainly a
decompiler alias for a global that already has a real name elsewhere;
confirm with Ghidra that both port symbols decompile to the same original
address or an adjacent field of the same struct.

## Hex-Rays placeholder symbols used as constants

**Symptom:** a computation that should use a fixed constant instead uses
"the address of" an IDA/Hex-Rays placeholder symbol for unnamed data --
numerically similar, but not the intended value, and everything downstream
still runs (just with a plausible-looking wrong result), so nothing crashes.

**Example:** `715a7f9 fix: use the real popup tile velocity divisor` --
`drawRacepopupEffect_406100` divided by `&unk_460000` (the *address* Hex-Rays
picked for an unnamed byte at that location) instead of the plain integer
constant `0x460000` the original pushes. Every one of the popup's 969 tiles
still animated, just settling at the wrong final position -- a wipe effect
that looked "permanently scrambled" rather than a crash. Ghidra's own
decompile of the call site was garbled here (a bogus 4-argument/`long long`
shape); raw `llvm-objdump` disassembly (`push 0x460000 / push eax / call
0x43b290`, a plain immediate, never an address) settled it.

**Detect / verify:** any `&unk_XXXXXX`, `&dword_XXXXXX` etc. used in
arithmetic (not as a pointer) is suspect -- Hex-Rays only generates those
names for data it could not otherwise identify. Cross-check the raw
disassembly, not just the decompiler's pseudo-C, since the decompiler can
garble exactly this kind of call.

## Original code commented out by the port author

**Symptom:** the described bug looks exactly like "this feature does
nothing", and the file has a suspiciously large commented-out block right
where you'd expect the feature's code to be.

Rule: **when the port has commented-out code next to a bug, compare it with
the original first** -- the port author usually commented it out because
something else crashed at the time, not because the original doesn't have
it.

**Examples:**
- the `recalcRank`/sort-by-points calls (`622f83d fix: recalculate rank
  after a race`): both believed multiplayer-only and commented out in
  `postRaceMain` and the shop's points cheat, so the player's rank was
  stuck at its initial value forever in single-player; the original calls
  both unconditionally, no `isMultiplayerGame` guard;
- `loadGraphics1`'s `copyImageToBuffer` (`2b14d89 fix: decode the
  wipe-transition mask texture`);
- `_strupr` on the race/track names (`3de827c fix: restore the dropped
  strupr on race names`);
- `racePauseMenu`'s reveal loop (`fbf29fe fix: run racePauseMenu's reveal
  loop`): the whole second phase of the race-start wipe, plus its final
  restore copy and two frees, was commented out, so the popup stayed frozen
  mid-wipe until dismissed, and both scratch buffers leaked every time;
- the collision call (`2367392 fix: re-enable car-to-car collision
  detection`).

## Port-author "tuning" hacks that must go

**Symptom:** something is audibly or numerically *off* in a way that still
basically works -- quiet sound effects, a too-fast pitch, a value that
never seems to exceed some suspiciously round number -- and the code has an
extra arithmetic step the decompiled original does not.

**Examples:**
- volume `>>5` (`1b27b39 fix: don't over-shift the effects mix volume`):
  an extra divide-by-32 on the effects mix volume the original never does;
  peak PCM amplitude rose from ~50-100 to ~4500-6500 (of 32767) once removed;
- freq `*0.62` (`f035a05 fix: don't rescale channel period into freq`): a
  hand-added rescale on top of the original's XM period->freq value, making
  every effect note finish ~3.27x too fast; the measured ratio matched the
  formula's own prediction of the *removed* scale factor exactly;
- the `if (v2 > 200)` clamp (`b0a8849 fix: drop bogus clamp in
  drawShadows_40D7B0`): substituted a wrong shadow-triangle vertex whenever
  the real index exceeded 200, distorting the shadow shape; the original has
  no such clamp;
- the Enter special case in results (`98222cb fix: let Enter dismiss the
  race results screen`, with the follow-up `bbc54cc fix: don't skip the
  easy race results screen`): Enter was excluded from "any key" on the
  first results wait, so only Enter failed to dismiss it; `bbc54cc` is the
  opposite kind of case -- a real original bug (a stale buffered key skips
  the *Easy* results screen specifically), reproduced deliberately and kept
  on purpose. See `doc/KNOWN-ISSUES.md` for the "deliberate
  deviation" writeup.

**Detect / verify:** any extra scale/clamp/round with no counterpart in the
`llvm-objdump`/Ghidra output of the original function is suspect by
default -- ask "does the original do this?" before assuming a magic
constant is intentional tuning.

## Signed `BYTE`

**Symptom:** a value that should be a small non-negative index or delay is
occasionally very large/negative-looking after a byte load, or (rarer) a
table lookup reads garbage for a byte >= 0x80.

**What it looks like:** `defs.h` (the Hex-Rays header) had
`typedef int8 BYTE;` -- `int8` is a plain (signed) `char` under
clang-cl/MSVC -- in every translation unit that does not see real
`windows.h` first, where `BYTE` is `unsigned char`. The original always
zero-extends (`movzx`); a `char`-typed `BYTE` compiles a byte load as
`movsx` instead, so any value >= 0x80 sign-extends into a huge 32-bit
number before it is used as an index, a comparison operand, or arithmetic.

**Examples:** `eef0a0d fix: decode music with unsigned bytes` (the first
instance found: `getMusicStream`'s byte-rotate decoder, `movsx` instead of
`movzx`, corrupted the S3M/XM header enough to set an order count of 24618
and crash with a stack overflow); `506d3e4 fix: zero-extend pixel index in
triangle remap` (found by deep, deterministic pixel-diffing against a
hooked copy of the original -- see "Methods that worked" below -- the same
signed byte read as a lookup-table index, producing red dithered
"starburst" artifacts in the headlight cones); `a61e96b fix: make BYTE
unsigned as Hex-Rays defines it` (the global fix: retyped `BYTE` itself to
`uint8` in all 31 translation units that had the signed typedef -- 19
functions, 87 changed byte loads, every one `movsx` -> `movzx`, verified
site-by-site against the original's own disassembly; the shipped game data
never actually exercises a byte >= 0x80 at any of those 87 sites, so this
fixed a *latent* class rather than a visible symptom at 30 of them).

**Verify:** `movsx` vs `movzx` at the load, both in our build's disassembly
and the original's, for the exact same field/global -- a byte-indexed table
lookup or a byte compared/cast to `unsigned` is the pattern to search for.
A useful positive control: the original does have a handful of genuinely
signed byte operations (`imul` on an 8-bit register, `movsx` in minifmod's
own byte-crypt loops) -- confirm the *specific* site you're fixing has no
such original counterpart before assuming `movzx` is always right.

## Wrong field or wrong base

**Symptom:** the game writes/reads the right *kind* of value, but into or
from the wrong struct field or the wrong base address -- a value that looks
plausible in isolation (it is a real number the game produces) but never
what the original shows.

**Examples:**
- damage written to `racesWon` (`1ce5cba fix: write race damage to the
  right field`): `previewRaceScreen`'s post-race loop copied each racer's
  damage into `drivers[].racesWon` instead of `drivers[].damage`, so the
  shop always showed 0% damage;
- palette base `0x45FD00` vs `0x45FC40`, the -48 error (`6ccecf5 fix: use
  the original car palette ramp base`, `f465ad9`, `893a925`): `palette1[0]`
  is really at `0x45FC40`; a stale patch had shifted every later index
  computation by -48 to compensate for the wrong base instead of fixing the
  base, corrupting/blotching the player's car texture;
- the stream format `0x80` vs `0x50` (`68f7eab fix: use correct
  effects-stream sample format`): the effects stream was declared
  `FSOUND_UNSIGNED` (0x80, no bit-depth/channel flags) while the mixer that
  actually fills it always writes signed 16-bit stereo -- exactly the
  "broken and crispy" in-race sound effects, with clean music (the music
  channel doesn't go through this stream).

**Detect / verify:** when a value is "a real number, just the wrong one",
suspect a field-offset or base-address mixup before a formula error --
check the struct layout or the base global against Ghidra/`llvm-objdump`
field-by-field.

## Missing prototypes / implicit int returns and float params

**Symptom:** a build warning (or, worse, silently wrong values) from a
function called without a visible prototype: an implicit `int` return
truncates a real `double` return value (`ceil`, `sqrt`, anything returning a
wider type read back from `eax` alone), and a float/double parameter passed
without a prototype gets promoted/laid out incorrectly by the calling
convention.

**Examples:** `99af640 fix: declare missing project function
prototypes` (61 missing prototypes across `dr.h`/`config.h`, plus the
matching `#include` at every caller that lacked it);
`d24f4d4 fix: add missing math.h includes`, `9737aee fix: add missing
string.h includes`, `2f9408e fix: add missing SDL_timer.h includes`,
`e08b6b8 fix: include imageUtil.h in imageUtil.c`; the float-parameter half
of the same class, `750b1ba fix: take float params in sub_418B00` and
`4f31ca5 fix: take float params in sub_424240`.

The Makefile's `-Werror=implicit-function-declaration` (the one warning
promoted to an error, see `doc/DEVELOPMENT.md`) exists specifically so this
class cannot silently reappear: without a visible prototype, a
double-returning call is read from `eax` alone and silently truncated.

## "Methods that worked"

- **`make check-equiv`'s footprint discipline.** Every `refactor:` commit
  must print `EQUIVALENT`; every `fix:` commit must list *exactly* the
  function(s) meant to change, not more. Known false positive: the
  **unnamed-data anchor** -- adding or removing an unnamed literal can shift
  the symbol `equiv.py` uses to name unrelated `.rdata`, so a function that
  only *reads* such data can show up in `functions changed (real)` even
  though its own code did not change (confirm from the disassembly the tool
  prints before treating it as real; see `doc/DEVELOPMENT.md`).
- **The Docker runner with `ORIG=1`** (`make docker-test ORIG=1
  SCENARIO=...`) runs the *unmodified* original `dr.exe` side by side with
  the port, both screenshotted at the same `shot:<label>` points in a key
  sequence, for a direct visual/behavioural diff.
- **Forcing the same track** with `srand(9)` at `calculateNextRaces`'s
  entry (original `0x4240B0`) makes the "random" next-race selection
  deterministic in both builds, which is what made the headlight/wipe-mask
  pixel diffs (`506d3e4`, `2b14d89`) possible at all.
- **`AUDIO=1` capture** (`make docker-test AUDIO=1 ...`) records a
  PulseAudio null-sink monitor to a WAV file for the whole run; several
  audio fixes (`1b27b39`, `f035a05`, `68f7eab`) were confirmed by comparing
  RMS/peak amplitude, not by ear.
- **The runtime hook into a patched COPY of the original** (see
  `tools/orighook/`): since `winedbg` does not work in this
  container (below), a small stub appended into `.text`'s existing zero
  slack loads a hook DLL into a *copy* of `dr.exe`, which inline-patches
  chosen function entries (5-byte `jmp` + trampoline) and logs
  arguments/dumps buffers to a file. This is how `506d3e4`'s headlight bug
  and `a61e96b`'s per-site signedness table were actually proven against
  the original's own runtime state, not just its static disassembly.
- **Comparing byte tables against `.data`** (`llvm-objdump -s -j .data`)
  rather than re-typing them by hand is the fix for the "strided tables"
  and "hand-typed table" classes above; `make verify-tables` now automates
  the comparison step itself.
- **Ghidra plus `objdump` when Ghidra's pseudo-C is wrong.** `715a7f9`'s
  call at `0x406100` and its `0x460000` constant were both garbled by
  Ghidra's decompiler (a bogus 4-argument/`long long` shape); raw
  disassembly settled it in both cases. Treat the decompiler's pseudo-C as
  a hint, the disassembly as ground truth, whenever they disagree.

## Environment pitfalls

A human contributor is much more likely to hit these than any of the bug
classes above:

- **Never attach `winedbg` to the running game.** CrossOver's 64-bit
  `winedbg` injects a break-in thread into the 32-bit process at a
  truncated address, which immediately faults -- `Unhandled page fault ...
  at 0xfff50de4` is that attach artifact (`0xfff50de4` is
  `DbgUiRemoteBreakin`'s real 64-bit address, `0x6ffffff50de4`, truncated),
  not a game bug. Neither launching under the debugger nor attaching to a
  running instance works in the Docker container either (both abort/fail
  outright); use the Docker runner's screenshots/logs, or the hook-DLL
  approach in `tools/orighook/`, instead.
- **QEMU "uncaught target signal 11"** in the container means retry -- it
  is the amd64-under-QEMU-user-emulation host faulting, not the game.
- **WineHQ 11 aborts** at plain `wineboot --init` on this host (amd64 under
  QEMU user-mode emulation on Apple Silicon); Wine 8.0 from Debian bookworm
  is pinned in `tools/docker/Dockerfile`. Re-verify with a rebuild before
  ever bumping the Wine version.
- **Some sources are ISO-8859, not UTF-8.** Plain `grep` may treat them as
  binary, and this shell's `grep` is aliased to `ugrep`, which may skip
  them outright -- use `grep -a` (or `command grep -a` if the alias is
  active) for anything that must actually search these files, and edit
  byte-preservingly (e.g. `LC_ALL=C perl -pi`), confirming the encoding is
  unchanged afterwards with `file`.
- **`make` exits 2 on a `DIFFERENT` `check-equiv`.** `check-equiv.sh` itself
  exits 1, which `make` reports as `Error 1` and then exits 2 itself --
  test `\$? -ne 0` in scripts, not `\$? -eq 1`.
