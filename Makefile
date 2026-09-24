# DreeRally build for macOS: cross-compiles the Win32 (x86) game with clang-cl
# and lld-link against the MSVC CRT/SDK fetched by xwin, and runs it in a
# CrossOver bottle. See doc/DEVELOPMENT.md.

LLVM    ?= /opt/homebrew/opt/llvm/bin
LLD     ?= /opt/homebrew/opt/lld/bin
XWIN    ?= $(HOME)/.xwin

CC = $(LLVM)/clang-cl
LD = $(LLD)/lld-link

# The vcxproj stays the single source of truth for which files are compiled.
SRCS := $(shell sed -n 's/.*<ClCompile Include="\([^"]*\)".*/\1/p' DreeRally.vcxproj | tr '\\' '/')

PROFILE ?= debug
OUT     ?= build/$(PROFILE)
OBJS    := $(SRCS:%.c=$(OUT)/obj/%.obj)

# _NO_MINIFMOD is temporary: minifmod's MSVC inline assembly (sfx/minifmod/soundSystem.c)
# does not build with clang-cl yet, so in-race sound effects are off in this build.
DEFINES  = /DWIN32 /D_WINDOWS /D_CRT_SECURE_NO_WARNINGS /DUNICODE /D_UNICODE /D_NO_MINIFMOD
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

.PHONY: all clean

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
