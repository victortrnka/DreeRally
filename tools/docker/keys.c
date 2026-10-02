/* keys.exe: a tiny key injector for driving DreeRally headlessly.
 *
 * Finds the game's window (class "SDL_app") and posts WM_KEYDOWN/WM_KEYUP
 * pairs to it with real set-1 scancodes, so the game's input handling sees
 * the same messages it would from a real keyboard. Waits up to ~60s for the
 * window to appear before giving up (exit 1).
 *
 * Usage: keys.exe TOKEN [TOKEN ...]
 * Tokens:
 *   enter, esc, space, back        - named keys
 *   f1, tab                        - in-race keys (info screen, status bar;
 *                                    tab is held 400 ms, see below)
 *   f6                             - screenshot (menus and races)
 *   up, down, left, right          - arrow keys
 *   a-z                            - letter keys (e.g. to type a nickname)
 *   +KEY, -KEY                     - hold / release an arrow or letter key
 *                                    (e.g. +up w3000 -up to accelerate)
 *   wNNN                           - wait NNN milliseconds (e.g. w1500)
 *
 * Originally a scratch tool for reproducing a crash; promoted to
 * tools/docker/keys.c as the one canonical copy for the headless Docker test
 * runner.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void key(HWND h, int vk, int sc, int ext)
{
	LPARAM down = 1 | (sc << 16) | (ext << 24);
	LPARAM up = down | (1u << 30) | (1u << 31);
	PostMessageA(h, WM_KEYDOWN, vk, down);
	Sleep(60);
	PostMessageA(h, WM_KEYUP, vk, up);
}
/* Set-1 (PC/XT) scancodes for a US QWERTY layout, by row. */
static int scancodeForLetter(char c)
{
	static const char *row1 = "qwertyuiop";
	static const unsigned char sc1[10] = {0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19};
	static const char *row2 = "asdfghjkl";
	static const unsigned char sc2[9]  = {0x1E,0x1F,0x20,0x21,0x22,0x23,0x24,0x25,0x26};
	static const char *row3 = "zxcvbnm";
	static const unsigned char sc3[7]  = {0x2C,0x2D,0x2E,0x2F,0x30,0x31,0x32};
	int i;
	for (i = 0; row1[i]; i++) if (row1[i] == c) return sc1[i];
	for (i = 0; row2[i]; i++) if (row2[i] == c) return sc2[i];
	for (i = 0; row3[i]; i++) if (row3[i] == c) return sc3[i];
	return 0;
}
int main(int argc, char **argv)
{
	HWND h = NULL;
	int i;
	DWORD t0 = GetTickCount();
	for (i = 0; i < 1200 && !(h = FindWindowA("SDL_app", NULL)); i++)
		Sleep(50);
	if (!h) { printf("no window\n"); return 1; }
	printf("%lu window %p\n", GetTickCount() - t0, (void *)h); fflush(stdout);
	for (i = 1; i < argc; i++) {
		char *a = argv[i];
		if (a[0] == 'w' && a[1] >= '0' && a[1] <= '9') Sleep(atoi(a + 1));
		else if (!strcmp(a, "enter")) key(h, VK_RETURN, 0x1c, 0);
		else if (!strcmp(a, "down")) key(h, VK_DOWN, 0x50, 1);
		else if (!strcmp(a, "up")) key(h, VK_UP, 0x48, 1);
		else if (!strcmp(a, "left")) key(h, VK_LEFT, 0x4b, 1);
		else if (!strcmp(a, "right")) key(h, VK_RIGHT, 0x4d, 1);
		else if (!strcmp(a, "esc")) key(h, VK_ESCAPE, 0x01, 0);
		else if (!strcmp(a, "space")) key(h, VK_SPACE, 0x39, 0);
		else if (!strcmp(a, "back")) key(h, VK_BACK, 0x0e, 0);
		else if (!strcmp(a, "f1")) key(h, VK_F1, 0x3b, 0);
		else if (!strcmp(a, "tab")) {
			/* The race loop reads the TAB state once per frame; a 60 ms tap
			 * was missed under emulation, a 400 ms hold was not. */
			PostMessageA(h, WM_KEYDOWN, VK_TAB, 1 | (0x0f << 16));
			Sleep(400);
			PostMessageA(h, WM_KEYUP, VK_TAB, 1 | (0x0f << 16) | (1u << 30) | (1u << 31));
		}
		else if (!strcmp(a, "f6")) key(h, VK_F6, 0x40, 0);
		else if (strlen(a) == 1 && a[0] >= 'a' && a[0] <= 'z') {
			int sc = scancodeForLetter(a[0]);
			key(h, 'A' + (a[0] - 'a'), sc, 0);
		}
		else if ((a[0] == '+' || a[0] == '-') && a[1]) {
			/* +KEY presses an arrow or letter key and keeps it held, -KEY
			 * releases it: "+up w3000 +left w800 -left -up" accelerates,
			 * turns left for 0.8 s and stops. */
			int vk = 0, sc = 0, ext = 1;
			LPARAM l;
			if (!strcmp(a + 1, "up")) { vk = VK_UP; sc = 0x48; }
			else if (!strcmp(a + 1, "down")) { vk = VK_DOWN; sc = 0x50; }
			else if (!strcmp(a + 1, "left")) { vk = VK_LEFT; sc = 0x4b; }
			else if (!strcmp(a + 1, "right")) { vk = VK_RIGHT; sc = 0x4d; }
			else if (!a[2] && a[1] >= 'a' && a[1] <= 'z') {
				vk = 'A' + (a[1] - 'a');
				sc = scancodeForLetter(a[1]);
				ext = 0;
			}
			if (!vk) { printf("bad token %s\n", a); return 2; }
			l = 1 | (sc << 16) | (ext << 24);
			if (a[0] == '+') PostMessageA(h, WM_KEYDOWN, vk, l);
			else PostMessageA(h, WM_KEYUP, vk, l | (1u << 30) | (1u << 31));
		}
		else { printf("bad token %s\n", a); return 2; }
		printf("%lu %s\n", GetTickCount() - t0, a); fflush(stdout);
	}
	return 0;
}
