# Known issues

Re-verified against the tree at this file's own commit. Items fixed since
an earlier pass are not listed here; see `doc/FINDINGS.md` and `git log`
for what fixed them.

## Open issues

1. Command-line flags: `-nosound` is a no-op; `-window` is ignored (the
   game always runs windowed); `-gl` disables GL.
2. `int debug = 1` (`dr.c:63`) still forces some locals. `dr.c:7800`
   (`if(debug) v13=0`) has a mistranslated round-half-up idiom that
   remains.
3. `dword_4A7D20` is `char[16]` (`raceParticipant.h:250`) but the port also
   keeps a separate, unrelated `BYTE dword_4A7D20[64]` at `dr.c:361` --
   the same Hex-Rays name reused for two different original globals.
4. Physics fields int vs float: only the last-corner fields were retyped.
   The current-corner fields `0x4A7E10/14/20/24/30/34/40/44` are `int` in
   `raceParticipant.h` but `float` in the original, so the 4 smoke-spawn
   `roundHalfUpToInt` calls act on truncated ints.
5. `strcat` onto the `"lang/"` literal (`i18n/i18n.c:54`).
6. `mod/mod.c:58` has no NULL check after `fopen`.
7. About 65 TODO and 5 FIXME comments remain across the tree.
8. The `readKeyboard` typing cursor is 40 rows tall
   (`ui/util/input.c:416`, `drawKeyCursor(..., glyphWidth, 40)`); the
   original pushes 0x20 (32) at 0x42F18C. Two proposed patches that
   touched this area were evaluated and rejected, not applied -- see
   "Rejected patches" below; neither would have fixed this specific height.
9. `DEFAULT_BIGLETTER_SPACING_OFFSET` is -23; the original uses -30
   (0x44582A): `imageUtil.c:10/234/368` (used by the big-letter text
   drawing path), `ui/hallOfFame.c:638`.
10. The `0x4A7E7C` decrement is missing from the collision recovery loop
    (`dr.c` ~11036).
11. Stack overrun in the `PORTABILITY` `main()`: `SDL_strlcpy(&v15, &arg,
    ...)` into an `int` (`dr.c` ~16695). The same bug was fixed in
    `WinMain` by `46221f0`.
12. `byte_460840` is still live in `recalcRank`'s multiplayer branch
    (`dr.c:13429/13433`) and in `ui/hallOfFame.c:831` (`v6` uninitialised,
    "TODO FIX halloffame").
13. Unfixed stack-walk sites (see `doc/FINDINGS.md`'s "Stack-walk idiom"
    class for the pattern):
    - `makeSnapshot_4092B0` / `_429DC0`: likely a stack smash.
    - `sub_4284E0`: reads past its buffer.
    - `drawRecordByCircuit`: passes a pointer as the `memset` fill.
    - `seeHallOfFame`: benign.
    - `checkAndOpenAnimation`: dead branch.
14. `initDrivers`: the name `memcpy` omits the NUL; `colour = index+1`
    differs from the original when `face > 0`; the name strings differ
    ("MATT MILLER"/"DARK RIDER" vs the original "MATT MILER"/"DARK RYDER").
15. `getDefaulRecords` leaves uninitialised name tails, so `dr.cfg`
    contains random bytes.
16. `asset/haf.c`'s `openAnimation` opens `animFile` instead of the built
    `Filename` (equivalent today, because `byte_45FAA0` is never written).
17. `stopSoundChannel_43C3E0` (`sfx/sound.c:217`) indexes
    `FSOUND_Channel[a1-1]`, while the original goes through
    `FMUSIC_Channel[a1-1].cptr` (0x43EB90). Equivalent while channel `i`
    maps to `cptr` `i`.
18. Linux/`PORTABILITY` build: missing returns under `_NO_MINIFMOD`, plus
    item 11 above.
19. Tooling debt:
    - `collect_names` misparses functions that return function pointers
      (0x43C7B0, 0x43F6B0).
    - `collect_names` exits 0 on an empty source list.
    - `check-equiv` shows `.rdata`/`.reloc` only as size lines.
    - `check-equiv` leaves a temp dir behind when `git worktree add` fails.
    - `mkdir -p $(@D)` in the Makefile is unquoted.
    - `objdump` "..." elision.
    - Docker `shot:` labels are not validated.
    - `wine --version` is untimed.
    - PulseAudio runs as root in the container.
    - `wait $PAREC_PID` has no inner timeout.
    - Makefile nits: `docker-test ORIG=1` still builds `dreerally.exe`;
      `make run PROFILE=equiv` fails (no pdb).
20. Pre-existing per-frame `malloc` leaks: `drawCarRightSide`,
    `reloadRepairAnimation`, `drawStadistics`'s `tmp`, and
    `racePauseMenu`'s double `malloc` of `dword_47926C`.
21. Menu control labels (`menu6`/`menu8`): the original's copies are
    space-padded ("Steer Right   "). No visual effect today.
22. The `initRaceValues` reset loop has two more dead-shadow-vs-live-global
    mismatches: `lastUserTicks_4A7EE0` (the burn animation throttle) and
    `dword_4A8058` (the horn cooldown).
23. 31 hardware palette entries in the original differ by one VGA step at
    one measured frame. Probably a fade rounding in the original; not
    investigated.
24. `calculateNextRaces` compares a `char` with a `BYTE`. Only different for
    bytes >= 0x80; circuit ids are <= 26.
25. Making `DWORD` unsigned does not compile against the minifmod stub; not
    pursued.
26. `drawTextWithFont` has code that is not in the original.
27. Some difficulty-popup "dots" appear in CrossOver only, not in the
    Docker runner. Probably CrossOver GL; check with `-gl`.
28. `multiplayer/multiplayer.c` is compiled but almost entirely commented
    out. `isMultiplayerGame` is set to 1 in one function (around line
    1318), but that function is reached only from a multiplayer-specific
    entry point the single-player-only port never calls; in normal play it
    stays 0.
29. **Menu layout tables use the wrong stride** (`ui/menu.c`, found by
    `make verify-tables`): `dword_4456F0`, `_4456F4`, `_4456F8`, `_4456FC`,
    `_445700`, `_445704` and `_445708` ("menu sizes/positions" per menu
    type, `menu.c:562-569`) are declared as 7 separate, contiguous 9-int
    arrays. Reading the original at a hypothesised stride confirms they
    are really one interleaved 9-row x 7-column table starting at
    `0x4456F0`, row stride `0x1C` (28 bytes, matching `dword_4456FC`'s
    constant value of 28 at every one of the 9 rows, and `dword_4456F0`'s
    already-correct values at column 0). Only index 0 of each of the 7
    arrays is right; every other menu type (1-8) reads the wrong column.
    `dword_445708` is also live game state (read *and* written at
    runtime, not just initial data), so the fix is a proper struct/2D
    array refactor across roughly 80 call sites in `ui/menu.c`, not a
    mechanical rename -- out of scope for a single `fix:` commit.
    Allowlisted in `tools/verify-tables.py` with a reason pointing here.
30. **Sponsor-popup stub tables in `ui/util/popup.c`** (found by `make
    verify-tables`): `byte_447388`, `byte_4473D8`, `byte_447478` and two
    further such trios (`byte_448648`/`_448698`/`_448738`,
    `byte_449908`/`_449958`/`_4499F8`) are each declared as blank
    4800-byte arrays ("every row blank in the original", per their own
    comment). Their declared addresses are only 0x50/0xF0 bytes apart,
    which is *inside* the 4800-byte span of an adjacent, already-restored,
    descriptively-named table (e.g. `byte_447478` at 0x447478 falls 0x50
    bytes into `aNotTooShabbyDr`'s row 0, which starts at 0x447428). Every
    one of these 9 arrays is genuinely read at runtime
    (`writeTextInScreen(&byte_447388[v2], 87201)` etc., `popup.c:1071` and
    around), so they are not dead code -- but comparing them at their
    declared address just reports their restored neighbour's bytes back
    as "wrong", and it is not established whether the original truly
    reuses that overlapping memory for a second purpose or whether these
    9 suffixes are simply mis-attributed the way `carAnimFrameSize` was
    (see `doc/FINDINGS.md`). Allowlisted in `tools/verify-tables.py` with
    a reason pointing here.

## Deliberate deviations from the original (not bugs)

- `bbc54cc fix: don't skip the easy race results screen`: the original has
  its own bug here (a stale buffered key skips the Easy Race Results
  "press any key" wait on its first poll); this reproduces and then fixes
  it on purpose, rather than reproducing the skip.
- Port guards (`9d6db72`, `d220c27`, `43503ca`, `ae5eeb3`, `5d24dc1`):
  bounds/state checks kept on purpose (window-focus key clear, damage-bar
  clamp, replayed-input bounds, AI-difficulty clamp, tyre/skid-mark bounds)
  that are harmless in normal play; `5d24dc1` keeps the
  original's rounding (`roundHalfUpToInt`) alongside the bounds check.
- `e5ad961`: `initSystem` returns 1 instead of 0 when `SDL_Init` fails.
  `02b4ae0`: a 12-byte `memcpy` instead of `strcpy` (same visible name,
  different original instruction).
- `-noeffect` (the `configNoSoundEffect` guard in `loadMusic`) is a port
  feature, not present in the original.
- The DreeRally branding "Windows Version 0.2" in the menu footer is the
  project's own text, not the original's.

## Rejected patches

Two proposed patches touching `readKeyboard` were evaluated against
the original and rejected -- their claimed bugs do not hold up, or their
fix would diverge from the original's own behaviour:

- **"Widen readKeyboard redraw areas."** Rejected: the claim
  that the redraw area is undersized is false. The original's Backspace
  erase is already `width + 20`, and the typing blit already uses the
  dynamic glyph width times 32 -- exactly what the port does. Applying it
  would have changed correct, already-matching behaviour.
- **"Bound readKeyboard input to its buffer."** Rejected: its
  width pre-check rejects keys that the original accepts, which is a
  behavioural regression, not a bugfix. (Its buffer-bounding *intent* is
  legitimate -- see the still-open cursor-height item above, which is a
  different bug in the same area -- but this specific patch's mechanism is
  wrong.)

Neither is in the current tree.
