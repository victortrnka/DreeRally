# Headless test runner for DreeRally: Wine (32-bit capable) + Xvfb on linux/amd64.
# Build: docker build --platform linux/amd64 -t dreerally-wine:trial tools/docker
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# wine needs the i386 arch enabled before its multiarch deps can install.
#
# Wine 8.0 from Debian bookworm on purpose, not WineHQ's repo (11.0): WineHQ
# 11.0's new WoW64 ntdll aborts under this host's QEMU-based amd64 emulation
# (dlls/ntdll/unix/virtual.c:267 anon_mmap_fixed assertion) even at plain
# `wineboot --init`, before the game is involved. Re-verify with a rebuild
# before ever switching to a newer Wine.
#
# NOTE, full detail: WineHQ 11.0's new WoW64 (syscall-thunking) ntdll aborts
# on this host with:
#   dlls/ntdll/unix/virtual.c:267: anon_mmap_fixed: Assertion
#   `!((UINT_PTR)start & host_page_mask)' failed.
#   qemu: uncaught target signal 6 (Aborted) - core dumped
# This is a QEMU-user-mode-emulation incompatibility with wine's new WoW64
# memory manager. Debian's older wine (classic
# separate wine32/wine64 WoW64) does not hit it. Revisit if WineHQ ships a
# fix, or if amd64 containers run through Rosetta instead of QEMU on this
# host.
#
# procps (ps, pgrep, ...) is not used by entrypoint.sh itself, but is kept
# for `docker exec <container> ps aux` when diagnosing a hung run from
# outside. xdotool was dropped: keys.exe (WM_KEYDOWN/UP via PostMessage)
# covers all current input needs.
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        wine wine32 \
        xvfb x11-apps x11-utils imagemagick procps \
        libgl1-mesa-dri libgl1-mesa-dri:i386 libglx-mesa0 libglx-mesa0:i386 libgl1 libgl1:i386 \
        pulseaudio pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# /runtime: mounted game files (exe + BPA/haf assets + keys.exe). /out: mounted output (log + screenshots).
VOLUME ["/runtime", "/out"]
ENTRYPOINT ["/entrypoint.sh"]
