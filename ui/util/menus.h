

typedef enum
{
	INITIAL_MENU = 0,
	START_NEW_GAME_MENU = 1,

	CONFIGURE_MENU = 3,
	LOAD_MENU = 5,
	DEFINE_KEYBOARD_MENU = 6,

	DEFINE_GAMEPAD_MENU = 8,
}Menus;

typedef enum
{
	START_CONTINUE_GAME = 0,
	END_CURRENT_GAME = 1,
	SEE_STADISTICS = 2,
	LOAD_GAME = 3,
	SAVE_GAME = 4,
	PREVIOUS_MENU =5
}StartNewGameMenu;

typedef enum
{
	BUY_CAR = 0,
	BUY_ENGINE = 1,
	BUY_TIRE = 2,
	BUY_ARMOUR = 3,
	REPAIR = 4,
	CONTINUE = 5,
	
}ShopMenu;

extern char menuActive_4457F0[];
char* getMenuText(int menu, int position);
// Original 0x446368/0x44652A: two 50-byte slots of the original's menu
// text table (stride 50), rewritten in place when a game starts or ends.
extern char menuaStartANewGame[17];
extern char menuaStartANewGam_0[50];
extern char menuaStartRacing[50];
// Original 0x446C32: menu 5's rows of the same table, the 8 Load/Save slot
// texts that loadGame and savegameWithName fill.
extern char unk_446C32[8 * 50];
// Original 0x446DF4/0x447178: the Define Keyboard and Define Gamepad rows of
// the same table, label plus key name (see sub_41CA40).
extern char defineKeyboardMenu_446DF4[9][50];
extern char defineGamepadMenu_447178[9][50];
