#include "menus.h"
#include "../../util.h"
#include "../../savegame.h"
#include "../../i18n/i18n.h"

#include <stdio.h>

// Original 0x446368/0x44652a: one mutable buffer per slot that
// startRacingMenu(), loadGame(), sub_4291D0() and adversaryPreviewScreen()
// overwrite in place ("Start Racing" <-> "Continue Racing", "Start A New
// Game" <-> "Enter The Shop") when a game starts or ends. Position 0 of
// these two menus must read from them instead of a fixed literal, or the
// swap never reaches the screen.
char * menu0[] = { menuaStartRacing, "Multiplayer Race", "Configure","See Hall Of Fame","Credits","Exit To OS" };
char * menu1[] = { menuaStartANewGam_0, "End Current Game", "See Current Statistics","Load Game","Save Game","Previous Menu" };

char * menu3[] = { "Music Volume", "Effect Volume", "Define Keyboard","Define Gamepad/Joystick","Gamepad/Joystick Disabled","Previous Menu" };

char * menu5[] = { "Empty Slot", "Empty Slot", "Empty Slot","Empty Slot","Empty Slot","Empty Slot","Empty Slot","Quicksave Slot" };

char * menu6[] = { "Accelerate", "Brake", "Steer Left","Steer Right","Turbo Boost","Machine Gun","Drop Mine","Horn","Previous Menu" };

char * menu8[] = { "Accelerate", "Brake", "Steer Left","Steer Right","Turbo Boost","Machine Gun","Drop Mine","Previous Menu" };

// verified byte-exact against dr.exe by make verify-tables (index 80, menu
// type 8's unused 9th slot -- menu8 only has 8 items -- was a stray 1).
char menuActive_4457F0[] = { '\x01','\x0','\x01','\x01','\x01','\x01','\x01','\x0','\x0',
						'\x01','\x0','\x0','\x01','\x0','\x01','\x0','\x0','\x0',
						'\x0','\x0','\x01','\x01','\x1','\x01','\x1','\x1','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x01','\x0','\x0','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x0','\x0','\x0','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x1',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x0'			}; // weak
char* getMenuText(int menu, int position) {
	
	switch (menu)
	{
	default:
		break;
	case INITIAL_MENU://menu principal
		return getLanguageEntry(menu0[position]);
		break;

	case START_NEW_GAME_MENU://
		return getLanguageEntry(menu1[position]);
		break;
	
	case CONFIGURE_MENU://
		return getLanguageEntry(menu3[position]);
		break;
	case LOAD_MENU://
		
		if (position == 8) {
			return getLanguageEntry(menu5[position]);
		}
		else {
			if (getSaveGameName(position) != NULL) {
				return getSaveGameName(position);
			}else return getLanguageEntry(menu5[position]);

		}
		
		break;
	case DEFINE_KEYBOARD_MENU://
		return getLanguageEntry(menu6[position]);
		break;
	case DEFINE_GAMEPAD_MENU://
		return getLanguageEntry(menu8[position]);
		break;
	}
	return "";
	

}