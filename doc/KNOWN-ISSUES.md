# Known issues

Re-verified against the tree at this file's own commit. Items fixed since
the previous pass are listed at the end with their commits; older fixes
are in `doc/FINDINGS.md` and `git log`.

## Open issues

1. Command-line flags: `-nosound` is a no-op (`checkArgs` sets
   `configNoSound` to 0, its default); `-window` is ignored (the game
   always runs windowed); `-gl` disables GL.
2. `int debug = 1` (`dr.c`) has one live reader: `shotAction_40E180`'s
   `if(debug) v13=0;`, which forces `v13`, an x87 condition flag (`c0`)
   Hex-Rays could not translate, in a mistranslated round-half-up idiom.
   All other uses are commented out.
3. `dword_4A7D20` is both a `char[16]` field of the race participant
   struct (`raceParticipant.h:250`) and a separate global `BYTE
   dword_4A7D20[64]` (`raceParticipant.h:361`; `dr.c` only has a
   commented-out copy): the same Hex-Rays name for two different original
   globals.
4. Physics fields int vs float: only the last-corner fields were retyped.
   The current-corner fields `0x4A7E10/14/20/24/30/34/40/44` are `int` in
   `raceParticipant.h` but `float` in the original (`fld dword ptr [esi +
   0x4a7e10]` etc.), so the 4 smoke-spawn `roundHalfUpToInt` calls act on
   truncated ints.
5. With `-lang=<name>`, `initI18n` builds the file name by `strcat`ing
   onto the `"lang/"` literal (`i18n/i18n.c:54`), i.e. writes into a
   string literal.
6. `mod/mod.c:58` has no NULL check after `fopen`.
7. About 60 TODO and 5 FIXME comments remain across the tree.
8. The `readKeyboard` typing cursor is 40 rows tall
   (`ui/util/input.c:416`, `drawKeyCursor(..., glyphWidth, 40)`); the
   original pushes 0x20 (32) at 0x42F18C. Two proposed patches that
   touched this area were evaluated and rejected, not applied -- see
   "Rejected patches" below; neither would have fixed this specific
   height.
9. The `0x4A7E7C` decrement is missing from `startRace`'s collision
   recovery loop (a comment in the loop says so: the field is not in
   `RaceParticipantIngame` yet).
10. Stack overrun in the `PORTABILITY` `main()`: `SDL_strlcpy(&v15, &arg,
    ...)` into an `int`. The same bug was fixed in `WinMain` by `46221f0`.
11. `byte_460840`, the original address of `drivers[]` kept as a separate
    2160-byte array, is still read in `recalcRank`'s `isMultiplayerGame`
    branch and in `showHallOfFameEndGame_430FA0`. There the name copy
    writes through `v8`, which is never initialised (its assignment is
    commented out, "TODO FIX halloffame").
12. Unfixed stack-walk sites (see `doc/FINDINGS.md`'s "Stack-walk idiom"
    class for the pattern):
    - `makeSnapshot_4092B0` / `sub_429DC0` (screenshots): a one-char
      `DstBuf` receives `SDL_itoa`, and `(char *)&Val2 + 3` walks build the
      file name; likely a stack smash.
    - `drawRecordByCircuit`: passes a pointer as the `memset` fill.
    - `seeHallOfFame`: benign.
    - `checkAndOpenAnimation`: dead branch.
13. `initDrivers`: the name `memcpy` omits the NUL; `colour = index+1`
    differs from the original when `face > 0`; the name strings differ
    ("MATT MILLER"/"DARK RIDER" vs the original "MATT MILER"/"DARK RYDER").
14. `getDefaulRecords` leaves uninitialised name tails, so `dr.cfg`
    contains random bytes.
15. `asset/haf.c`'s `openAnimation` opens `animFile` instead of the built
    `Filename` (equivalent today, because `byte_45FAA0` is never written).
16. `stopSoundChannel_43C3E0` (`sfx/sound.c:217`) indexes
    `FSOUND_Channel[a1-1]`, while the original goes through
    `FMUSIC_Channel[a1-1].cptr` (0x43EB90). Equivalent while channel `i`
    maps to `cptr` `i`.
17. Linux/`PORTABILITY` build: missing returns under `_NO_MINIFMOD`, plus
    item 10 above.
18. Tooling debt:
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
19. Pre-existing per-frame `malloc` leaks: `drawCarRightSide`,
    `reloadRepairAnimation`, `drawStadistics`'s `tmp`, and
    `racePauseMenu`'s double `malloc` of `dword_47926C`.
20. The `initRaceValues` reset loop has two more dead-shadow-vs-live-global
    mismatches: `lastUserTicks_4A7EE0` (the burn animation throttle) and
    `dword_4A8058` (the horn cooldown).
21. 31 hardware palette entries in the original differ by one VGA step at
    one measured frame. Probably a fade rounding in the original; not
    investigated.
22. `calculateNextRaces` compares a `char` with a `BYTE`. Only different for
    bytes >= 0x80; circuit ids are <= 26.
23. Making `DWORD` unsigned does not compile against the minifmod stub; not
    pursued.
24. `drawTextWithFont` still has one port-only line: `if (v9 < 32) v9 =
    32;` ("TODO fix"), a clamp that guards a read before the font texture.
    With a signed `char` it also draws every byte >= 0x80 as a space. The
    original (0x41A314) draws glyph `(uchar)c - 32` unconditionally. Only
    matters for non-ASCII text.
25. Some difficulty-popup "dots" appear in CrossOver only, not in the
    Docker runner. Probably CrossOver GL; check with `-gl`.
26. `multiplayer/multiplayer.c` is compiled but almost entirely commented
    out. `isMultiplayerGame` is set to 1 in one function (around line
    1319), but that function is reached only from a multiplayer-specific
    entry point the single-player-only port never calls; in normal play it
    stays 0. Whoever uncomments it must translate its `byte_445892[c]`
    reads as `letterSpacing_4458B0[c - 30]` (`byte_445892` no longer
    exists).
27. **Sponsor tables in `ui/util/popup.c`**: `make verify-tables` still
    allowlists `byte_447388`, `byte_4473D8`, `byte_447478` and the same
    trios at 0x448648 and 0x449908. Their layout is understood and they
    are correct: each original table is 6 cars x 10 lines x 80 bytes (car
    stride 800), and the port keeps each line as its own 4800-byte array
    with car `c` at `[800 * c]`, so only bytes `800*c .. 800*c+79`
    correspond to the original at face value. These nine are lines 0, 1
    and 3, blank for every car in the original and in the port (checked
    once with that per-car mask: no mismatch). The tool cannot express
    the mask, hence the allowlist.
28. **The pre-race news lines are written but never drawn.** `sub_4279C0`
    (`ui/prevRaceScreen.c`, before a race) copies them, and `sub_427BC0`
    (`ui/hallOfFame.c`, end of game) other lines, into `byte_4629F6`,
    `byte_462A8C`, `byte_462B22` and `byte_462BB8`: rows 17-20 of the
    original's message table at 0x462000 (22 rows x 150 bytes). In the
    original, 0x41E810 draws rows 16-21 at the bottom of the menu
    screens; the port's
    `drawBottomMenuText` (`ui/util/bottomText.c`) draws the project's own
    footer there instead (see "Deliberate deviations"), with the original
    body commented out. The table itself is not real storage either: both
    functions first scroll it up a row with `for (v3 = &unk_462096; v3 <
    &blacktx1Bpk; v3 += 150)`, a 1-byte stand-in bounded by an unrelated
    global (see `doc/FINDINGS.md`, "Hex-Rays 1-byte stand-ins used as
    buffers"); in the current link map `unk_462096` lies after
    `blacktx1Bpk`, so the loop runs once and copies a string to 150 bytes
    before `unk_462096`.
29. **Other 1-byte stand-ins still used as buffers**, found by scanning
    for the address of a `_UNKNOWN`/scalar global passed to a copy or
    walked with a stride:
    - `sub_429DC0` (menu screenshot): `fwrite(&unk_456848, 1, 0x80,
      File)`. dr.exe 0x456848 holds a 128-byte PCX header for 640x480, the
      counterpart of the 320x200 one `c9cc8bf` restored for the in-race
      screenshot.
    - `keyMenuInRace_407330` (F1 screen): the key lines are fixed
      strings ("ACCELERATE...............A"), plus one live line that
      reads `(char *)&unk_4A6B20 + 15 * configuration.accelerateKey`. The
      original builds every line from the configured keys through name
      tables at 0x4A6B20 (keyboard) and 0x479E40 (gamepad), e.g.
      0x408920..0x40897A.
    - About 20 strided text reads such as `(const char *)&unk_44E258 +
      1760 * carType + 240 * engine` in `ui/util/anim.c`,
      `ui/shopScreen.c` and `ui/blackMarketScreen.c`. The original's rows
      there are empty strings, except the shop's engine popup table at
      0x44E258/0x44E2F8, which reads "N/A" for the engines a car cannot
      take.
    - Further `&unk_` uses passed as addresses (e.g. in
      `race/3dSystem.c`, `race/leftBar.c`) are not checked yet.
30. **Menu 7 (multiplayer) row 6** of the flat menu text table (0x4470E2,
    "Tone Dialing", rewritten to "Pulse Dialing" by `mainMenu`) is three
    `int` stand-ins plus `word_4470EE` in `ui/menu.c`, not a 50-byte row.
    Multiplayer only; the port never draws it.
31. **Possible unsigned-shift sites** (the "Unsigned `_DWORD`" class in
    `doc/FINDINGS.md`), not checked against the original yet: e.g.
    `draw3dElements_4116D0` (`race/3dSystem.c:606/609/632`) shifts
    `(100 - *(_DWORD *)&dword_4B4328[...]) >> 8`, a logical shift if the
    difference is negative.
32. **Define Keyboard popup, one pixel column**: side by side with the
    original, the popup's rightmost inner column (x = 581, y 132..372) is
    popup fill in the port and background in the original, with the same
    width in the menu layout table. Probably in `createPopup`'s drawing;
    not investigated.
33. **Race intro/outro palette, +/-1 of 63** (accepted): during the
    race-start intro (`sub_404C30`) and race-end outro (`sub_4055A0`) some
    grey levels differ from the original's by one step (mostly lower) for
    about 2.5 s. The original multiplies by the float 1/90 at 0x441628
    and computes the luminance sum on the x87 in extended precision
    before truncating; the port uses the double `0.011111111` that
    Hex-Rays printed and clang's SSE arithmetic. The constant could be
    matched, the extended-precision intermediate cannot be reproduced in C
    without `long double` (a `double` under MSVC), so it is left as is.
34. **Missing function markers**: `loadConfig` (0x429FD0) and
    `defaultConfig` (0x426700) in `config.c` have no `//----- (address)`
    line.
35. **The original overruns `textureTemp` in the credits**: `showCredits`
    (0x4274E0) extracts `credit1.bpk` (171989 bytes) into `textureTemp`
    (0x481E20), past its end at 0x4A6820, over whatever the original keeps
    there. Harmless in the port, whose `textureTemp` is `int[0xFFFFF]`
    (4 MB).
36. **Intermittent crash in a race, under investigation**: one Docker run
    died mid-race with `Unhandled illegal instruction` in
    `_invoke_watson`, the CRT's invalid-parameter handler, i.e. a CRT
    function received an invalid argument. A rerun of the same key
    sequence stayed alive, and it has not been reproduced on demand.

## Deliberate deviations from the original (not bugs)

- `bbc54cc fix: don't skip the easy race results screen`: the original has
  its own bug here (a stale buffered key skips the Easy Race Results
  "press any key" wait on its first poll); this reproduces and then fixes
  it on purpose, rather than reproducing the skip.
- Five port guards kept on purpose, adapted from fixes in marianoluzza's
  fork: `9d6db72 fix: clear held keys when the window loses focus`,
  `d220c27 fix: clamp damage bar width to 0..100 percent`, `43503ca fix:
  bounds-check replayed input slots`, `ae5eeb3 fix: clamp AI difficulty
  index to 0..2`, `5d24dc1 fix: bounds-check tyre and skid mark writes`.
  These bounds/state checks are not in the original and are harmless in
  normal play; `5d24dc1` keeps the original's rounding
  (`roundHalfUpToInt`) alongside its bounds check.
- `e5ad961 fix: drop app name stack copy in initSystem`: `initSystem`
  returns 1 instead of 0 when `SDL_Init` fails.
- `02b4ae0 fix: restore driver name on license cancel`: the licence screen
  saves and restores the player's name with a 12-byte `memcpy` of the name
  field, where the original copies up to the NUL (same visible name).
- `-noeffect` (the `configNoSoundEffect` guard in `loadMusic`) is a port
  feature, not present in the original.
- The DreeRally branding "Windows Version 0.2" in the menu footer is the
  project's own text, not the original's: `drawBottomMenuText` (0x41E810)
  draws it instead of the original's six message lines (open issue 28).
- `6ea4c17 fix: show key names in Define Keyboard/Gamepad`: the Define
  Keyboard and Define Gamepad rows are built as in the original (label,
  padding, key name), so their labels stay English when a language file
  is loaded (`-lang=`): the 0xFA padding bytes in each row are sized for
  the English label. "Previous Menu" and the save-slot texts are still
  translated.

## Rejected patches

Two proposed patches to `readKeyboard` were evaluated against the
original and rejected; neither is in the tree:

- **"Widen readKeyboard redraw areas."** The claim that the redraw area is
  undersized is false. The original's Backspace erase is already `width +
  20`, and the typing blit already uses the dynamic glyph width times 32
  -- exactly what the port does. Applying it would have changed correct,
  already-matching behaviour.
- **"Bound readKeyboard input to its buffer."** Its width pre-check
  rejects keys that the original accepts, which is a behavioural
  regression, not a bugfix. (Its buffer-bounding *intent* is legitimate
  -- see the still-open cursor-height item above, which is a different
  bug in the same area -- but this specific patch's mechanism is wrong.)

## Fixed since the previous pass

- `DEFAULT_BIGLETTER_SPACING_OFFSET` was -23 where the original uses -30:
  `eb13133 fix: measure big text like the original` (the constant is gone).
- `sub_4284E0` read past its buffer: `f9134ef fix: give the key config
  checks stack arrays`.
- Define Keyboard/Gamepad showed fixed labels (`menu6`/`menu8`) without
  key names, and opening them overflowed 1-byte stand-ins: `6ea4c17 fix:
  show key names in Define Keyboard/Gamepad`.
- `drawTextWithFont`'s port-only `-24` and `'Z'` branches and
  `writeTextInScreen`'s `'z'` hack: `edb1db4 fix: index small-font
  advances like the original` (only the glyph clamp remains, item 24).
- "Menu layout tables use the wrong stride": they did not; the seven
  arrays are the original's table stored column-wise, now checked as
  columns by `9752459 build: check menu layout tables column-wise`, and
  the three typos it found were fixed by `f60c84a fix: restore three menu
  popup heights`.
- "Sponsor-popup stub tables": layout understood, see item 27.
