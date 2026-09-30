#include "menus.h"
#include "../../util.h"
#include "../../savegame.h"
#include "../../i18n/i18n.h"

#include <stdio.h>

char * menu0[] = { "Start Racing", "Multiplayer Race", "Configure","See Hall Of Fame","Credits","Exit To OS" };
char * menu1[] = { "Start A New Game", "End Current Game", "See Current Statistics","Load Game","Save Game","Previous Menu" };

char * menu3[] = { "Music Volume", "Effect Volume", "Define Keyboard","Define Gamepad/Joystick","Gamepad/Joystick Disabled","Previous Menu" };

char * menu5[] = { "Empty Slot", "Empty Slot", "Empty Slot","Empty Slot","Empty Slot","Empty Slot","Empty Slot","Quicksave Slot" };

char * menu6[] = { "Accelerate", "Brake", "Steer Left","Steer Right","Turbo Boost","Machine Gun","Drop Mine","Horn","Previous Menu" };

char * menu8[] = { "Accelerate", "Brake", "Steer Left","Steer Right","Turbo Boost","Machine Gun","Drop Mine","Previous Menu" };

char menuActive_4457F0[] = { '\x01','\x0','\x01','\x01','\x01','\x01','\x01','\x0','\x0',
						'\x01','\x0','\x0','\x01','\x0','\x01','\x0','\x0','\x0',
						'\x0','\x0','\x01','\x01','\x1','\x01','\x1','\x1','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x01','\x0','\x0','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x0','\x0','\x0','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x1',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x0',
						'\x1','\x1','\x01','\x01','\x1','\x1','\x1','\x1','\x1'			}; // weak
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