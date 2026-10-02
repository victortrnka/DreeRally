# Known issues

Re-verified against the tree at this file's own commit. Items fixed since
the previous pass are listed at the end with their commits; older fixes
are in `doc/FINDINGS.md` and `git log`.

## Open issues

2. `int debug = 1` (`dr.c`) has one live reader: `shotAction_40E180`'s
   `if(debug) v13=0;`, which forces `v13`, an x87 condition flag (`c0`)
   Hex-Rays could not translate, in a mistranslated round-half-up idiom.
   All other uses are commented out.
3. `dword_4A7D20` is both a `char[16]` field of the race participant
   struct (`raceParticipant.h:250`) and a separate global `BYTE
   dword_4A7D20[64]` (`raceParticipant.h:361`; `dr.c` only has a
   commented-out copy): the same Hex-Rays name for two different original
   globals.
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
    Docker runner. Probably CrossOver GL; check with `-nogl`.
26. `multiplayer/multiplayer.c` is compiled but almost entirely commented
    out. `isMultiplayerGame` is set to 1 in one function (around line
    1319), but that function is reached only from a multiplayer-specific
    entry point the single-player-only port never calls; in normal play it
    stays 0. Whoever uncomments it must translate its `byte_445892[c]`
    reads as `letterSpacing_4458B0[c - 30]` (`byte_445892` no longer
    exists), and its bottom-panel stand-ins (`unk_461EC1`..,
    `unk_462096`, `dword_462C4E`..) as `bottomMenuTextFont` and
    `bottomMenuText` rows. The same goes for the commented-out
    multiplayer code in `previewRaceScreen` and at the end of `mainMenu`.
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
29. **Other 1-byte stand-ins still used as buffers**, found by scanning
    for the address of a `_UNKNOWN`/scalar global passed to a copy or
    walked with a stride:
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
31. **Signedness mismatches** (the "Unsigned `_DWORD`" class in
    `doc/FINDINGS.md`): `make signcheck` lists them. The sites in
    `draw3dElements_4116D0` once listed here were in commented-out code,
    now restored with the original's signed shifts. The remaining
    candidates are type mismatches whose values never reach the sign bit
    (repair costs and texture sizes halved through `HIDWORD`, driver
    points, lap counters and race positions held in signed `char` fields,
    font indices of fixed ASCII text); none has a visible effect.
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
36. **`generateBigPowerUps` (0x409460), money/repair branch**: it checks
    the slot's countdown (`dword_501BAC > 0`) where the original checks
    the slot's x position (0x409567: `posX > 0`); latent, since slots
    12-15 have a position on all ten tracks. Its background save also
    reads the first dword of every fourth row from `+4` instead of `+0`
    (0x4095c9), so 4 bytes of each saved row are wrong when the big
    power-up is taken and the track is restored.
37. **Fullscreen's Alt+Enter toggle not verified at runtime**: `refreshScreen`'s
    fullscreen branches (aspect-corrected GL quads) run under Docker
    without `-window` and match the original there; only the Alt+Enter
    toggle itself cannot be exercised, since `keys.exe` has no Alt.
38. **Gouraud case 0x80 not seen on screen**: `draw3dElements_4116D0`'s
    colour-0x80 triangles (Suburbia/West End, TR0) are restored from the
    original's code but no such triangle is in view at the West End start.
39. **`mainMenu`'s two unrestored stores**: the commented-out block
    `6058ab7` removed (to restore the bottom panel) also held
    `drivers[driverId].name[0] = 0` and `drivers[driverId].face = 0`
    (dr.exe 0x43A2AA/0x43A2B7 with `ebx = 0`), not carried over.
    `mainMenu` runs once at start-up, so there is no visible effect today.
40. **Shop missing the DEATH RALLY logo after results -> statistics**: the
    shop shows black top rows (with stray pixels) where dr.exe shows the
    logo. The shop entry (`postLoadedOrLicense`) copies the top of the
    current `screenBuffer`, as dr.exe 0x4388A3 does, so the cause is
    whatever leaves `screenBuffer` in that state on the way through
    statistics, not the shop entry itself; not investigated further.
41. **Per-car physics fields still not float**: next to the fields fixed
    below (0x4A7DF4..0x4A7E54), dr.exe also keeps `carVelocity_4A7DB0`
    (a `double` in the port, 8 bytes; dr.exe reads a dword float),
    `dword_4A7DBC`/`dword_4A7DC0`/`dword_4A7DC4` and
    `unk_4A7E64`/`dword_4A7E68` (`int` in the port) as floats, read and
    written with x87 `fld`/`fstp dword` (e.g. in calculateUserMovements,
    0x40BAB0). 0x4A7DBC is the sideways slide: recalculateCarBoundary
    spawns skid smoke when `|0x4A7DBC| > carType + 13` (dr.exe
    0x4124A2..0x4124E3), and the port also mistranslates that `fabs` as
    a sign flip depending on 0x4A7DC0/0x4A7DC4, so skid smoke can start
    or stop at different moments than in dr.exe.

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
- Screenshots are taken on F6. The original's screenshot code checks F12
  (`keysRead[0x58]`, 0x416B14 in a race, 0x42A480/0x42A570 in menus),
  but its own event loop (0x43BD18) never sets that slot, so the original
  never takes one. Under the Docker runner one F6 in a menu keeps writing
  files up to `HS-PIC99.PCX`: each 640x480 snapshot makes the frame loop
  fall behind, and `refreshScreenWithDelay` (0x43C760, the same in the
  original) skips the event pump while it catches up, so the key-up is
  never seen.
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

- Command-line flags: `-window` was ignored and the game always started
  windowed (`30d1e78 fix: start fullscreen unless -window is given`);
  `-nosound` did nothing and GL was switched off by `-gl` instead of the
  original's `-nogl` (`df40023 fix: honour -nosound and -nogl like the
  original`).
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
- The hitman offer crashed the game (a /GS stack-cookie failure) when it
  returned, and both offers' texts were garbled: `977c13f fix: build
  showHitmanScreen's offer text safely`.
- Accepting the steroid run crashed the next race's load: `9747355 fix:
  place the steroid pills by position value`.
- Screenshots (item 12's `makeSnapshot` stack walks, item 29's menu PCX
  header) and their RLE writer: `fc669f4 fix: give both screenshot
  functions real buffers`, `1c58ea8 fix: give the menu screenshot its PCX
  header`, `8cd5382 fix: escape lone PCX bytes of 0xC0 and up`.
- The intermittent `_invoke_watson` crash in a Docker race (formerly item
  36) was the test harness, not the game: the run's `run-docker/` was
  emptied while the race ran, and the first file load after the race, an
  `fopen`/`fread` of `MENU.BPA` in `extractFromBpa` (unchecked in the
  original too, 0x4027D7), failed. Emptying that directory mid-race
  reproduces the exact log; never touch a worktree's `run-docker/` while
  its container runs.
- The bottom message panel was never drawn: `drawBottomMenuText` showed
  the port's own "DreeRally - Windows Version 0.2" footer, the news and
  welcome lines went into stand-ins, and the end-game lines were 1 byte
  each: `a78a1a7 fix: give the bottom panel its real storage`, `6058ab7
  fix: restore mainMenu's bottom panel lines`, `193d81b fix: restore the
  end-game panel lines`, `1ba4827 fix: draw the bottom panel like the
  original`. The branding deviation is gone with it.
- Mine explosions were never drawn: `drawExplosion_40FE20` reset its only
  loop index on every drawn frame (so any mine past slot 0 was animated
  from slot 0's state), cleared the wrong field when an explosion
  finished, and its compaction loop never advanced, plus its call from
  `startRace` was commented out: `0adff23 fix: draw and clear mine
  explosions`. With drawing restored, a pre-existing bug became visible:
  see the mine-slot-reset fix below.
- `calculateNextRaces` picked the medium and hard next races from the
  same pool as the easy race (`circuitOrder_45673C[0..4]` for all three,
  instead of offsets 2 and 5), so Utopia, Bogota, Downtown and Velodrome
  could never be offered as hard races: `1ea8b1f fix: read medium/hard
  races from own pools`. `lastCircuitsSelected_456780` was
  zero-initialised instead of the original's `{-1, -1, -1}`, so the
  first easy race could never be Suburbia: `05eba79 fix: init
  lastCircuitsSelected to -1,-1,-1`.
- The news-already-used flags (`dword_45F000`..`byte_45F012`) were kept
  as 6 separate globals that only acted as one 19-byte array because the
  linker happened to place them adjacently: `0d4627f fix: use one real
  array for news-used flags`.
- `FMUSIC_LoadXM` ran two iterations past `numinsts`, writing two
  instrument entries past the end of its table and corrupting the next
  heap block; the heap corruption crashed the game as soon as a loaded
  song was freed, with real sound on: `1d585cb fix: load exactly
  numinsts XM instruments`.
- `initRaceValues` reset only 16 of the 32 mine slots, so any 17th or
  later armed mine animated an explosion by itself: `fix: reset all 32
  mine slots in race init`.
- `-lang=`/`-mod=`'s `strtok` parsing cut the shared argument string, so
  a trailing `-window` was lost: `fix: test -window before the strtok
  parsers`.
- Three 256-byte polygon-colour remap tables (colours 0x81-0x83) were
  1-byte stand-ins: `fix: size the 0x81-0x83 colour remap tables`.
- A handle-sized block in `FSOUND_File_Open_43F720` and `openAnimation`'s
  packed-data buffer on the `FEATURE_SKIP_VIDEO` path leaked: `fix: drop
  two leaks next to restored frees`.
- Skid smoke and the per-car physics fields 0x4A7DF4..0x4A7E54
  (formerly item 4): every AI car's right-rear smoke puffs and skid
  marks were drawn at the player's height, up to about 400 px off
  (`fix: use the car's own Y for its rear-right corner`), and the car
  corners, push, spin, nose terrain probe and previous position were
  `int` where dr.exe keeps floats (`fix: keep the car corner positions
  as floats`, `fix: keep the push and spin fields as floats`, `fix: keep
  the nose terrain probe as floats`, `fix: keep each car's previous
  position as floats`). Listing the push's users also showed that
  startRace's wall-hit damage walked a dead global, so walls never
  damaged a car: `fix: damage cars that hit a wall like dr.exe`. The
  fields still left are item 41.
