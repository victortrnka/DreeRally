/* orighook: a minimal in-process hook DLL for the ORIGINAL dr.exe.
 *
 * Loaded into a patched COPY of dr.exe by the stub tools/orighook/patch_exe.py
 * appends (see that file, and its docstring for why 0x44100C/0x43FA60 are
 * safe to reuse as-is). By the time DllMain runs, the OS has already
 * resolved every import and run static init for the image, so addresses in
 * the original binary can be poked directly.
 *
 * This file has ONE example hook, an ordinary x86 inline detour on
 * calculateNextRaces (original 0x4240B0, already proven reachable and
 * useful for deterministic testing: it seeds the RNG that picks the next
 * race). It logs
 * its own call count to orighook.log and returns control to the original
 * function unchanged. To hook a different or additional function:
 *   1. get its first >=5 bytes, on an instruction boundary, with
 *      `llvm-objdump -d -M intel --start-address=<addr> dr.exe` (a shorter
 *      instruction run, like the 3 one-byte pushes here, needs more than
 *      5 bytes -- see kHookedPrologue below);
 *   2. put those bytes in a new kHookedPrologue-style array, add the
 *      address and length to HOOKED_ADDR/HOOKED_LEN, and write a new log
 *      function + naked thunk following logHook/hookThunk below;
 *   3. call installHook() with the new address/length/prologue/thunk from
 *      DllMain, the same way it is called for the one example here.
 *
 * Each hook works the same way:
 *   1. at DLL_PROCESS_ATTACH, check the target's first HOOKED_LEN bytes
 *      still match kHookedPrologue (a different dr.exe build at this
 *      address fails this check instead of corrupting itself);
 *   2. copy those bytes into a small executable trampoline, followed by a
 *      jmp back to target+HOOKED_LEN;
 *   3. overwrite the target's first 5 bytes with `E9 <rel32>` to the hook
 *      function below, NOPing out the rest of the stolen region;
 *   4. the hook function logs, then jmps to the trampoline, which runs the
 *      stolen bytes and returns to the original function as if nothing
 *      had happened.
 *
 * Build: `make -C tools/orighook` (see tools/orighook/Makefile), the same
 * clang-cl/lld/xwin toolchain as the main game build.
 * Run: `make docker-test ORIGHOOK=1 ...` (see the top-level Makefile).
 *
 * This DLL is only ever loaded into a PATCHED COPY of dr.exe, made by
 * patch_exe.py into a private runtime directory -- never run/, never the
 * Steam install.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#define HOOKED_ADDR ((unsigned char *)0x4240B0) /* calculateNextRaces */
#define HOOKED_LEN 9 /* "push ebx; push esi; push edi; mov edi,[0x463ce8]" */

static const unsigned char kHookedPrologue[HOOKED_LEN] = {
    0x53, 0x56, 0x57, 0x8B, 0x3D, 0xE8, 0x3C, 0x46, 0x00,
};

static unsigned char *gTrampoline;
static int gCallCount;
static FILE *gLog;

static void logLine(const char *msg) {
    if (!gLog) return;
    fputs(msg, gLog);
    fflush(gLog);
}

static void __cdecl logHook(void) {
    char buf[96];
    gCallCount++;
    wsprintfA(buf, "orighook: calculateNextRaces (0x4240B0) call #%d\r\n", gCallCount);
    logLine(buf);
}

/* naked: exactly "log, then run the stolen bytes via the trampoline", with
 * no compiler prologue/epilogue to disturb the registers the trampoline
 * (and the rest of the original function) expect. pushad/popad around the
 * call preserves every register logHook might use. */
__declspec(naked) static void hookThunk(void) {
    __asm {
        pushad
        call logHook
        popad
        jmp dword ptr [gTrampoline]
    }
}

static void installHook(void) {
    if (memcmp(HOOKED_ADDR, kHookedPrologue, HOOKED_LEN) != 0) {
        logLine("orighook: prologue mismatch at 0x4240B0, not installing\r\n");
        return;
    }

    gTrampoline = (unsigned char *)VirtualAlloc(
        NULL, HOOKED_LEN + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!gTrampoline) {
        logLine("orighook: VirtualAlloc failed\r\n");
        return;
    }
    memcpy(gTrampoline, HOOKED_ADDR, HOOKED_LEN);
    gTrampoline[HOOKED_LEN] = 0xE9; /* jmp rel32 back to HOOKED_ADDR+HOOKED_LEN */
    *(DWORD *)(gTrampoline + HOOKED_LEN + 1) =
        (DWORD)(HOOKED_ADDR + HOOKED_LEN) - (DWORD)(gTrampoline + HOOKED_LEN + 5);

    DWORD oldProtect;
    if (!VirtualProtect(HOOKED_ADDR, HOOKED_LEN, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        logLine("orighook: VirtualProtect failed\r\n");
        return;
    }
    HOOKED_ADDR[0] = 0xE9;
    *(DWORD *)(HOOKED_ADDR + 1) = (DWORD)hookThunk - (DWORD)(HOOKED_ADDR + 5);
    for (int k = 5; k < HOOKED_LEN; k++) HOOKED_ADDR[k] = 0x90; /* NOP the rest */
    VirtualProtect(HOOKED_ADDR, HOOKED_LEN, oldProtect, &oldProtect);

    logLine("orighook: hook installed at 0x4240B0\r\n");
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved) {
    (void)hinst;
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        gLog = fopen("orighook.log", "w");
        logLine("orighook: attached\r\n");
        installHook();
    } else if (reason == DLL_PROCESS_DETACH) {
        if (gLog) fclose(gLog);
    }
    return TRUE;
}
