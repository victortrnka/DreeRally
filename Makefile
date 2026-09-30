# DreeRally build for macOS: cross-compiles the Win32 (x86) game with clang-cl
# and lld-link against the MSVC CRT/SDK fetched by xwin, and runs it in a
# CrossOver bottle. See doc/DEVELOPMENT.md.

LLVM    ?= /opt/homebrew/opt/llvm/bin
LLD     ?= /opt/homebrew/opt/lld/bin
XWIN    ?= $(HOME)/.xwin
CX      ?= /Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin
BOTTLE  ?= DreeRally
DR_DATA ?= $(HOME)/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Death Rally/Death Rally

CC = $(LLVM)/clang-cl
LD = $(LLD)/lld-link

# The vcxproj stays the single source of truth for which files are compiled.
SRCS := $(shell sed -n 's/.*<ClCompile Include="\([^"]*\)".*/\1/p' DreeRally.vcxproj | tr '\\' '/')

PROFILE ?= debug
OUT     ?= build/$(PROFILE)
OBJS    := $(SRCS:%.c=$(OUT)/obj/%.obj)

DEFINES  = /DWIN32 /D_WINDOWS /D_CRT_SECURE_NO_WARNINGS /DUNICODE /D_UNICODE
INCLUDES = /Ilibincludes /Ilibs \
           /imsvc $(XWIN)/crt/include /imsvc $(XWIN)/sdk/include/ucrt \
           /imsvc $(XWIN)/sdk/include/um /imsvc $(XWIN)/sdk/include/shared
# Warnings stay off as in the vcxproj, except calls to undeclared functions:
# without a prototype a double-returning call (ceil, sqrt) is read from eax.
WARNINGS = -Wno-everything -Werror=implicit-function-declaration
# -fcommon: merge C tentative definitions (e.g. `int x;` in several files) like MSVC does.
CFLAGS   = --target=i686-pc-windows-msvc /nologo /c /Od /MT $(DEFINES) $(INCLUDES) $(WARNINGS) -fcommon

LIBPATHS = /libpath:libs /libpath:$(XWIN)/crt/lib/x86 \
           /libpath:$(XWIN)/sdk/lib/um/x86 /libpath:$(XWIN)/sdk/lib/ucrt/x86
LIBS     = opengl32.lib SDL.lib SDLmain.lib fmodvc.lib minifmod.lib Winmm.lib
LDFLAGS  = /nologo /machine:x86 /subsystem:windows /opt:noref /opt:noicf /map:$(OUT)/dreerally.map

ifeq ($(PROFILE),debug)
CFLAGS  += /Z7
LDFLAGS += /debug /pdb:$(OUT)/dreerally.pdb
else ifeq ($(PROFILE),equiv)
# No debug info: a PDB path would end up in .rdata and differ between checkouts.
CFLAGS  += /Brepro
LDFLAGS += /Brepro
else
$(error PROFILE must be debug or equiv)
endif

.PHONY: all clean setup-run run check-equiv stats docker-test verify-tables

BASE ?= HEAD

all: $(OUT)/dreerally.exe

$(OUT)/dreerally.exe: $(OBJS)
	$(LD) $(LDFLAGS) /out:$@ $(LIBPATHS) $(OBJS) $(LIBS)

$(OUT)/obj/%.obj: %.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) /clang:-MMD /clang:-MF$(@:.obj=.d) /Fo$@ $<

# Changing flags must rebuild everything.
$(OBJS): Makefile

-include $(OBJS:.obj=.d)

clean:
	rm -rf build

# Game files copied from the original install. Saves (DR.SG*) and dr.cfg are
# deliberately not copied: DreeRally creates its own inside run/.
RUNTIME_FILES = ENGINE.BPA IBFILES.BPA MENU.BPA MUSICS.BPA \
                TR0.BPA TR1.BPA TR2.BPA TR3.BPA TR4.BPA TR5.BPA TR6.BPA TR7.BPA TR8.BPA TR9.BPA \
                SANIM.haf ENDANI.haf ENDANI0.HAF SDL.dll fmod.dll \
                end.bmp rmd.bmp

setup-run:
	@test -d "$(DR_DATA)" || { echo "Death Rally data not found: DR_DATA=$(DR_DATA)"; exit 1; }
	@mkdir -p run
	@for f in $(RUNTIME_FILES); do cp -p "$(DR_DATA)/$$f" run/ || exit 1; done
	@test -d "$(HOME)/Library/Application Support/CrossOver/Bottles/$(BOTTLE)" || \
		"$(CX)/cxbottle" --bottle "$(BOTTLE)" --create --template win10_64
	@echo "run/ and bottle $(BOTTLE) are ready"

run: $(OUT)/dreerally.exe
	@test -f run/ENGINE.BPA || { echo "Run 'make setup-run' first"; exit 1; }
	cp $(OUT)/dreerally.exe $(OUT)/dreerally.pdb run/
	"$(CX)/wine" --bottle "$(BOTTLE)" --workdir "$(CURDIR)/run" "$(CURDIR)/run/dreerally.exe" $(ARGS)

check-equiv:
	LLVM=$(LLVM) tools/equiv/check-equiv.sh $(BASE)

stats:
	@python3 tools/stats.py

verify-tables:
	@python3 tools/verify-tables.py --dr-data "$(DR_DATA)"

# --- Headless Docker test runner ---------------------------------------
# keys.exe: a small standalone console tool, not part of the game itself, so
# it gets its own simple build rule rather than folding into $(OBJS)/CFLAGS.
$(OUT)/keys.obj: tools/docker/keys.c Makefile
	@mkdir -p $(@D)
	$(CC) --target=i686-pc-windows-msvc /nologo /c /Od /MT \
	  /imsvc $(XWIN)/crt/include /imsvc $(XWIN)/sdk/include/ucrt \
	  /imsvc $(XWIN)/sdk/include/um /imsvc $(XWIN)/sdk/include/shared \
	  /Fo$@ $<

$(OUT)/keys.exe: $(OUT)/keys.obj
	$(LD) /nologo /machine:x86 /subsystem:console \
	  /libpath:$(XWIN)/crt/lib/x86 /libpath:$(XWIN)/sdk/lib/um/x86 /libpath:$(XWIN)/sdk/lib/ucrt/x86 \
	  /out:$@ $< user32.lib kernel32.lib

# docker-test: builds and runs the game headless in Docker (see
# tools/docker/). Uses its own run-docker/ (or run-docker-orig/) runtime
# dir, never run/, so it never collides with a CrossOver run in progress.
#   DOCKER_ARGS -> DR_ARGS  (dreerally.exe args, default "-window -nosound")
#   KEYS      -> DR_KEYS  (keys.exe tokens, incl. "shot:<label>"; ignored if
#                SCENARIO is set)
#   SHOTS     -> DR_SHOTS (screenshot offsets, default "3:intro 9:menu")
#   SECS      -> RUN_SECS (seconds before stopping the game, default 12)
#   OUT_SHOTS -> where screenshots/log/status land (default build/docker-out)
#   SCENARIO  -> reads KEYS from tools/docker/scenarios/<name>.keys instead
#   ORIG      -> 1 runs the original dr.exe (+ msvcr71.dll) copied from
#                DR_DATA instead of our built dreerally.exe. DR_DATA/the
#                Steam bottle are only ever read, never modified.
#   AUDIO     -> 1 records a PulseAudio null-sink monitor to audio.wav in
#                OUT_SHOTS for the whole run. Needs DOCKER_ARGS without
#                -nosound.
DOCKER_ARGS ?= -window -nosound
KEYS      ?=
SHOTS     ?= 3:intro 9:menu
SECS      ?= 12
OUT_SHOTS ?= build/docker-out
SCENARIO  ?=
ORIG      ?= 0
AUDIO     ?= 0

ifneq ($(SCENARIO),)
SCENARIO_FILE := tools/docker/scenarios/$(SCENARIO).keys
KEYS := $(shell sed -e 's/\#.*//' $(SCENARIO_FILE) 2>/dev/null | tr '\n' ' ' | tr -s ' ')
endif

RUN_DIR := run-docker$(if $(filter 1,$(ORIG)),-orig)

docker-test: $(OUT)/dreerally.exe $(OUT)/keys.exe
	@test -d "$(DR_DATA)" || { echo "Death Rally data not found: DR_DATA=$(DR_DATA)"; exit 1; }
	@if [ -n "$(SCENARIO)" ]; then test -f "$(SCENARIO_FILE)" || { echo "no such scenario: $(SCENARIO_FILE)"; exit 1; }; fi
	@rm -rf $(RUN_DIR)
	@mkdir -p $(RUN_DIR)
	@for f in $(RUNTIME_FILES); do cp -p "$(DR_DATA)/$$f" $(RUN_DIR)/ || exit 1; done
	@if [ "$(ORIG)" = "1" ]; then \
	  test -f "$(DR_DATA)/dr.exe" || { echo "original dr.exe not found under DR_DATA=$(DR_DATA)"; exit 1; }; \
	  cp -p "$(DR_DATA)/dr.exe" $(RUN_DIR)/dreerally.exe || exit 1; \
	  test -f "$(DR_DATA)/msvcr71.dll" && { cp -p "$(DR_DATA)/msvcr71.dll" $(RUN_DIR)/ || exit 1; } || true; \
	else \
	  cp $(OUT)/dreerally.exe $(RUN_DIR)/ || exit 1; \
	fi
	@cp $(OUT)/keys.exe $(RUN_DIR)/
	@mkdir -p $(OUT_SHOTS)
	RUNTIME_DIR="$(CURDIR)/$(RUN_DIR)" OUT_DIR="$(CURDIR)/$(OUT_SHOTS)" \
	  DR_ARGS="$(DOCKER_ARGS)" DR_KEYS="$(KEYS)" DR_SHOTS="$(SHOTS)" RUN_SECS="$(SECS)" \
	  AUDIO="$(AUDIO)" \
	  NAME="dreerally-docker-test-$$$$" \
	  tools/docker/run.sh
