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
caused it. When the overrun hits the function's own stack cookie first, the
crash is instead `Unhandled illegal instruction` inside
`___report_gsfailure` as the function returns (`llvm-symbolizer` names it).

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
`f2c13d1 fix: give previewRaceScreen a 20-byte DstBuf`,
`f9134ef fix: give the key config checks stack arrays` (sub_4284E0's
15-byte list of reserved scancodes had become 15 separate `char` locals,
walked upward through the cookie and the return address, so a valid key
setup could be rejected; its 27-byte message went into a single `char`,
and leaving Define Keyboard died in `___report_gsfailure`),
`3734ad9 fix: give sub_43D050 its vertex array` (the same idiom with
`int` locals: nine arguments the original copies into one array and
indexes by vertex, walked as `&v75 + k`; nothing crashed, the triangle
would just have been drawn from unrelated stack slots).

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
char aBorrow12000Pay[40] = "Borrow $12,000 - Pay $18,000";
...
drawLoanShark(..., &aBorrow12000Pay[240 * carType], ...);  // carType 1..4 reads garbage
```

**Examples:** `6ec5444 fix: restore drawLoanShark message tables`,
`a44f4fc fix: restore loadAcceptedText message tables`,
`1ba2b7a fix: restore six-row sponsor popup tables`,
`0855730 fix: restore the pre-race news-line tables`. The last one is a
variant: four arrays read with the same `280 * v6` stride
(`aThisIsIt_Here_455150` and three siblings) are the four 70-byte columns
of one 280-byte-wide, 19-row table at 0x455150. Searching dr.exe for each
array's first string put the siblings exactly 70, 140 and 210 bytes into
the first one's row 0. The arrays also had no address suffix, so `make
verify-tables` had silently skipped them until they were renamed.

**Fix:** restore the whole table byte-exact from the original's `.data`
(`llvm-objdump -s -j .data`), not by hand-typing strings; a script that
reads the original's stride and row count and emits a C initialiser avoids
the transcription errors that caused the original bug. **`make
verify-tables`** (below) now checks every such table on every run, so a
future regression here is caught immediately rather than only when the
animation advances far enough to show it.

## Hex-Rays 1-byte stand-ins used as buffers

**Symptom:** whatever the linker happened to put after a small global gets
read or overwritten. Seen so far: a race start that faded in "black with a
few stray pixels" and a closed F1 screen that faded in streaky noise
(64000 bytes copied from a 1-byte global); a menu row or news line showing
text that belongs to something else; Define Keyboard showing its labels
but no key names; a `memcpy` crash far from the cause. Often nothing is
visible at all, because the overwritten global does not matter yet.

**What it looks like:** Hex-Rays declares data it could not size as
`_UNKNOWN unk_XXXXXX;` (`defs.h`: `#define _UNKNOWN char`, one byte), as a
scalar (`int dword_XXXXXX`, `__int16 word_XXXXXX`), or as an array only
as long as its first literal, and the code then copies, compares or walks
many bytes at that address:

```c
// before (06c5823, keyMenuInRace_407330): 64000 bytes restored from 1 byte
_UNKNOWN unk_491820;
memcpy((void *)screenPtr, &unk_491820, 0xFA00u);
```

In the port every such global is its own small object, so the access
runs into unrelated port globals. There are two cases, fixed differently:

- **An address inside a larger original object.** `textureTemp`
  (0x481E20) is a 150016-byte scratch buffer: the only absolute addresses
  the original references between 0x481E20 and 0x4A6820 are offsets into
  it (0x481F20, 0x48E620, 0x48E720, 0x491820, ...). These need no storage
  of their own; they are `textureTemp + 0x100`, `+ 0xC800`, `+ 0xC900`,
  `+ 0xFA00`. Examples: `e176723 fix: restore the race-start intro`,
  `ca344e2 fix: restore the race-end outro`, `06c5823 fix: save the race
  screen before the F1 screen`, `7c2c441 fix: draw the mushroom view
  through textureTemp`.
- **A separate original object.** It needs real storage of the original's
  size: initialised byte-exact when the original's `.data` has content
  there (verify-tables then checks it), otherwise sized from the access
  sizes and the gap to the next referenced address. Examples: `2200f53 fix:
  size the save-slot table like the original` (8 x 50 bytes at 0x446C32),
  `1e8cb78 fix: make dword_443D18 the Empty Slot string` (an `int` compared
  over 11 bytes), `6ea4c17 fix: show key names in Define Keyboard/Gamepad`
  (457 stand-ins for two name tables, two blocks of menu rows and eight
  templates), `6681214 fix: size popup.c's killed-driver name buffer`,
  `5dfa273 fix: widen word_462D54 to the real 4 bytes`, `c9cc8bf fix: size
  the screenshot PCX header for real`, `a2b3cfe fix: size the
  driver/participant swap scratch`, `afb6910 fix: size menu start texts
  like the original` (a 13-byte array that received "Continue Racing"),
  and the palette tables `e176723` added at 0x4B3400 and 0x509E60.

A related form is a loop whose end is the address of an unrelated
global. The original compares against the address where the next object
starts, and Hex-Rays names that bound after the object found there:
`&obstacleBpk`
for the end of the palette table at 0x4B4004 (`e176723`),
`&joystick_y_axis_default_4A9EA0 + 1` for the end of
`circuitPalette_4A9BA0` (`ca344e2`), `&numberOfLaps` for the end of the
key-name table (`6ea4c17`). In the port that global can be anywhere, so
the loop runs once, or across unrelated memory.

**Detect:**
- a `_UNKNOWN`, scalar or short global whose address is passed to
  `memcpy`/`memset`/`memcmp`/`strcpy`/`strcat`/`strlen`/`fread`/`fwrite`,
  or cast to a pointer that is then walked with a stride
  (`(char *)&unk_X + 240 * k`);
- a constant-offset write past a declared size (`*(_DWORD *)&x[12]` into
  `char x[13]`);
- a loop bound `p < (int)&someGlobal` where `someGlobal` is not the table
  being walked;
- for a known large original object, every identifier whose address suffix
  falls inside its range, and every hex literal in that range.

**Verify:** take the size from the original: the access sizes (`mov ecx,
N` before `rep movsd`, the size pushed for `fread`/`fwrite`), a `cmp reg,
<end address>` loop bound, and the next separately referenced address
(see "Object bounds from absolute references" below). The linker map
(`build/debug/dreerally.map`) shows what the port's access actually hits.
`make check-equiv` for a resize usually reports `functions changed (real):
0` and many moved-only functions, since everything after the resized
global moves; that is expected.

## The flat menu text table

The original keeps the rows of all menus in one table at 0x446368: 9 menus
x 9 rows x 50 bytes, row `r` of menu `m` at `0x446368 + 450 * m + 50 * r`.
drawMenu (0x41A880) draws from it, and the game rewrites some rows in
place: "Start Racing"/"Continue Racing" (menu 0 row 0), "Start A New
Game"/"Enter The Shop" (menu 1 row 0), the Gamepad/Joystick
Enabled/Disabled toggle (menu 3 row 4), the eight Load/Save slot names
(menu 5), and the Define Keyboard and Define Gamepad rows with their key
names (menus 6 and 8).

The port reads rows through `getMenuText` (`ui/util/menus.c`), which used
to return fixed literals, so rewritten rows were never shown; and Hex-Rays
had split the rewritten rows into small separate globals, so the rewrites
overflowed them (previous class). Each rewritten row, or block of rows,
now has real storage of 50 bytes per row, declared once in
`ui/util/menus.h` with its original address, and `getMenuText` returns
it. Rows the game never
rewrites stay literals.

**Examples:** `09b7909 fix: show Continue Racing when a game is active`,
`afb6910 fix: size menu start texts like the original`, `64a52e1 fix:
reset shared menu texts after game over`, `2200f53`, `1f00526 fix: label
save slot 7 Quicksave Slot`, `b449094 fix: draw save slots from the slot
table`, `1e10bef fix: redraw main-menu rows on Esc like drawMenu` (it read
`&menuaStartRacing[50 * k]`, i.e. the whole table, from one 50-byte row),
`6ea4c17`, `cda47d8 fix: show the Configure Gamepad toggle text`.

**Detect / verify:** a menu row that should change (after starting a game,
a toggle, a save) but does not; a reader indexing a row as `[50 * k]` or
`[450 * m]`. To find every writer of a row, search the original's
disassembly for operands in 0x446368..0x44733A: the start texts alone
have four writers (game over, game won, startRacingMenu, loadGame), and
`64a52e1` fixed the two that `09b7909` had missed.

## Hand-typed data tables with typos

**Symptom:** wrong, but plausible-looking, numeric data -- a frame-size
table off by one entry, so an animation desyncs or a decrypt routine reads
past its buffer only once the animation actually reaches that frame.

**Example:** `c66cd91 fix: correct three shop animation frame sizes` --
`continueAnimFramesSize_4611D0`'s frame 1 was `0x577` where the original has
`0x5F7`; every later frame in that table then started 128 bytes early and
`decryptTexture` eventually walked off the end.

This is the class **`tools/verify-tables.py`** (`make verify-tables`, see
`doc/DEVELOPMENT.md`) catches on every run, instead of only once a bug
happens to be visibly reachable: it compares every initialised array whose
name still carries an original address suffix (`_XXXXXX`) with `dr.exe`,
element by element. Its first run found:

- two arrays whose suffix was the address of their sibling
  `*CurrentFrame` counter instead of their own table,
  `carAnimFrameSize_45FBA0` and `continueAnimFramesSize_4611D0` (now
  `_445968` and `_4462A8`, `9f394ec refactor: correct anim table address
  suffixes`);
- single-element typos in `byte_445892`, `menuActive_4457F0`,
  `streamId_4444F8`, `letterSpacing_4458B0` and `bigLetterSpacing_445848`
  (`83e798c fix: correct five hand-typed table values`).

**Restoring a table byte-exact is half the fix: check every reader's index
too.** After `83e798c` restored the font advance tables exactly, every
small-font text came out misspaced ("Velcome", "gear lp"). The values were
right; the readers had been tuned to the old, wrong table: drawTextWithFont
advanced all but the big font by `a2[c - 24]` (plus a special case for
'Z'); writeTextInScreen and three other readers used a 24-byte
`byte_445892` that the linker happened to place right before
`letterSpacing_4458B0`, landing on `[c - 24]` as well (plus a `'z'` -> 10
hack); the big-font measuring functions used `c - 23`; and the price
font's '$' was read as `[0]` and `[97]`. The original reads
`[(uchar)c - 30]` everywhere (0x41A337, 0x41A4E5, 0x41CA14, ...) and the
price '$' at 0x445916 (`letterSpacing_4458B0[102]`). Fixed by `edb1db4 fix:
index small-font advances like the original`, `eb13133 fix: measure big
text like the original`, `d48f2a4 fix: use the price font's advance for
'$'` and `9f8e0e1 fix: zero-extend chars in font width lookups`; the text
now matches the original glyph for glyph on every screen compared, which
the old table never quite did. The bytes at 0x445848..0x445967 are four
font descriptors back to back (`{width, height, advances...}` for the
big, small, price-digit and medium fonts), and the original's readers
cross from one into the next, so each port array holds "dr.exe from its
own address onwards" and overlaps its neighbours (comment in
`imageUtil.c`).

**Menu layout tables.** The seven arrays `dword_4456F0` .. `dword_445708`
in `ui/menu.c` are the original's 9x7 int table at 0x4456F0 (one
0x1C-byte row per menu type) stored column-wise and indexed by menu type,
which is semantically right. Only three values in `dword_445704`, the
popup height, were typos; the Define Keyboard popup was 74 px too tall
(`f60c84a fix: restore three menu popup heights`). verify-tables compares
such columns at `addr + 0x1C * i` (`9752459 build: check menu layout
tables column-wise`).

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

**Detect / verify:** when a per-driver/per-participant value is wrong for
everything but index 0, check the original's stride between struct
instances (Ghidra's struct size, or read the original at a hypothesised
stride and confirm that a constant field reads the same at every row; that
is how the menu layout table above showed its 0x1C-byte rows: its fourth
column is 28 in all nine).

## Dead globals or struct shadows versus the live data

**Symptom:** a feature that depends on "who's in the lead" or "how many
points does X have" always behaves as if the answer were the initial/zero
value, even though the underlying race state is otherwise correct.

**What it looks like:** Hex-Rays named two different things that are really
the same original global, and the port kept both -- writing the live one but
reading the dead one, or vice versa:

- `dword_45EB50` should be `racePositions` (`5908f4b fix: build the
  sabotage popup like the original`, `1d4ea75 fix: pick hitman target from
  racePositions`; the sabotage popup and the hitman quest both read a
  `dword_45EB50` that nothing ever writes);
- `dword_4608F0` should be `&drivers[1].points` (`8b08dca fix: point the
  max-other-points loop at drivers[]`: a 256-int global nothing ever writes,
  used for "does anyone else have more points", always reading 0, i.e.
  "nobody ever beats me");
- `initRaceValues` zeroed a dead shadow instead of the live, strided array
  (`48dd425`, above);
- the game-over and game-won screens reset "Start Racing"/"Start A New
  Game" in private copies while the menu drew the shared rows (`64a52e1
  fix: reset shared menu texts after game over`, see "The flat menu text
  table" above).

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
- `_strupr` on the race participants' (drivers') names after
  previewRaceScreen copies them (`3de827c fix: restore the dropped strupr
  on race names`);
- `racePauseMenu`'s reveal loop (`fbf29fe fix: run racePauseMenu's reveal
  loop`): the whole second phase of the race-start wipe, plus its final
  restore copy and two frees, was commented out, so the popup stayed frozen
  mid-wipe until dismissed, and both scratch buffers leaked every time;
- the car-to-car collision call (`2367392 fix: re-enable car-to-car
  collision detection`);
- the race-start intro and the race-end outro (`e176723 fix: restore the
  race-start intro`, `ca344e2 fix: restore the race-end outro`): both calls
  in startRace were commented out, and a port-only `refreshPaleteCheat`
  faded a screen copied from a 1-byte global in instead of the intro. Both
  functions walked original addresses that the port had only as 1-byte
  globals, so restoring the calls also meant giving those real storage
  (see "Hex-Rays 1-byte stand-ins used as buffers");
- draw3dElements' two gouraud-shaded triangle cases, colours 0x80 and
  0x8A (`4d96525 fix: restore draw3dElements' shaded triangles`), which a
  signed colour then kept unreachable (`8d7d1f8`, see "Unsigned `_DWORD`
  where the original uses `sar`");
- the F1 screen's screen save and palette copy (`06c5823 fix: save the race
  screen before the F1 screen`, `4119bc6 fix: fade the F1 screen out from
  the track palette`): the save into a 1-byte global had been disabled,
  with a comment saying it wrecked other things, but the restore from it
  stayed live and faded in 64000 bytes of unrelated memory.

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
fixed a *latent* class rather than a visible symptom at 30 of them);
`9f8e0e1 fix: zero-extend chars in font width lookups` (the same with a
plain `char` used as a table index).

**Verify:** `movsx` vs `movzx` at the load, both in our build's disassembly
and the original's, for the exact same field/global -- a byte-indexed table
lookup or a byte compared/cast to `unsigned` is the pattern to search for.
A useful positive control: the original does have a handful of genuinely
signed byte operations (`imul` on an 8-bit register, `movsx` in minifmod's
own byte-crypt loops) -- confirm the *specific* site you're fixing has no
such original counterpart before assuming `movzx` is always right.

## Unsigned `_DWORD` where the original uses `sar`

**Symptom:** a value that should be small and negative behaves as if it
were about 2^31: with the status bar off, every frame of the race-end
outro was black, because its rotation produced texture coordinates near
+/-2^21.

**What it looks like:** the "Signed `BYTE`" class the other way round.
Hex-Rays reads a signed value through `*(_DWORD *)` (`_DWORD` is `uint32`
in `defs.h`) and then shifts it right, which C compiles to a logical
`shr`; the original used an arithmetic `sar` on the signed value:

```c
// before (89caa70, sub_4055A0): sin < 0 became about 2^31
v166 = 2 * *(_DWORD *)((char *)dword_4A6854 + v163) >> 1;
```

The same goes for compares (`jb`/`jae` for the original's `jl`/`jns`),
divides (`div` for `idiv`) and, the other way round, a signed `char`
where the original reads an unsigned or wider value (`movsx` for
`movzx`).

**Examples:**
- `89caa70 fix: rotate the status-bar-off outro correctly` (original
  0x405F84..0x405F8E: `shl edi; ... sar edx`);
- `e34f46a fix: shift the drunk view's sine signed`: the drunk view's
  vertical wobble shifted a negative sine with `shr` (original 0x404871
  `sar edx, 0x7`), so about half of the race view was cleared to black
  in diagonal bands; it went unnoticed because the view also ended after
  one frame (`c557187 fix: count the drunk view's time down`, a `=-` for
  `-=`);
- `bcbe879 fix: read the fullscreen flag as signed`: `*(_DWORD
  *)screenSurface < 0` is never true, so Alt+Enter could not leave
  fullscreen (original 0x43BCEA `cmp dword ptr [ecx], 0; jns`);
- `8d7d1f8 fix: read polygon colours unsigned`: a 3D-object triangle's
  colour was a signed `char`, so no colour from 0x80 up matched its
  `switch` case and the gouraud-shaded triangles (the cacti on Snake
  Alley and Desert Run, 0x8A) were filled flat. Making those cases
  reachable also needed two other classes fixed first: the cases were
  commented out (`4d96525`, see "Original code commented out by the
  port author") and the triangle function they call walked its
  arguments as separate locals (`3734ad9`, see "Stack-walk idiom").

**Detect / verify:** `make signcheck` (`tools/signcheck.py`, see
`doc/DEVELOPMENT.md`) pairs every port function with the original by
address and ranks those where the port has the unsigned form of an
instruction the original has signed, or the reverse; `--show NAME`
prints both sides with the port's `file:line`. Most candidates are type
mismatches that cannot matter (repair costs, points, lap counters and
pixel sums are never negative); judge each by whether the value can be
negative (or reach 0x80/2^31 the other way round). Then compare the
original's instruction at that site. The original's game code has no
`movsx` at all apart from two joystick-axis reads, so a `movsx` in a
port function is always worth a look.

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
- **Logging both builds at the same points.** For the race intro, outro
  and F1 screen fixes (`e176723`, `ca344e2`, `06c5823`, `4119bc6`,
  `7c2c441`, `89caa70`), a hook DLL in the original and a temporary edit
  in the port logged the same globals at the same places (every presented
  frame's palette sum and pixel hash, snapshots of the screen buffer) on
  the same forced track. The first log line where the two differ is the
  bug; after the fix, the logs match phase for phase. The temporary port
  edit is reverted before committing.
- **Object bounds from absolute references.** dr.exe has no symbols. To
  find how big an original object is, list every absolute address the
  disassembly references near it: the next separately referenced address
  is the next object. That is how `textureTemp` was shown to span
  0x481E20..0x4A6820 with nothing else inside it.
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
- **Never run two `make docker-test` at once in the same worktree**: each
  starts by deleting the shared runtime directory (see
  `doc/DEVELOPMENT.md`).
- **WineHQ 11 aborts** at plain `wineboot --init` on this host (amd64 under
  QEMU user-mode emulation on Apple Silicon); Wine 8.0 from Debian bookworm
  is pinned in `tools/docker/Dockerfile`. Re-verify with a rebuild before
  ever bumping the Wine version.
- **Some sources are ISO-8859, not UTF-8.** Plain `grep` may treat them as
  binary, and some `grep` replacements (e.g. `ugrep`) skip them outright
  -- use `grep -a` for anything that must actually search these files, and
  edit byte-preservingly (e.g. `LC_ALL=C perl -pi`), confirming the
  encoding is unchanged afterwards with `file`.
- **`make` exits 2 on a `DIFFERENT` `check-equiv`.** `check-equiv.sh` itself
  exits 1, which `make` reports as `Error 1` and then exits 2 itself --
  test `$? -ne 0` in scripts, not `$? -eq 1`.
