#include <SDL_keysym.h>
#include "menu.h"

#include "util/menus.h"
#include <SDL_stdinc.h>
#include <SDL_timer.h>
#include "util/anim.h"
#include "../imageUtil.h"
#include "../config.h"
#include "../defs.h"
#include "../drivers.h"
#include "../dr.h"
#include "../graphics.h"
#include "../circuit.h"
#include "../variables.h"
#include "../i18n/i18n.h"
#include "util/popup.h"
#include "../sfx/sound.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../asset/haf.h"
#include "../cars.h"
#include "creditsScreen.h"
#include "endGameScreen.h"
#include "licenseScreen.h"
#include "loadSaveGameScreen.h"
#include "raceResultsScreen.h"
#include "shopScreen.h"
#include "startGameScreen.h"
#include "util/bottomText.h"

// Key name for each keyboard scancode (0x462DA0, 256 x 15 bytes, up to
// numberOfLaps at 0x463CA0) and for each gamepad input (0x45EAC0, 9 x 15
// bytes); sub_41CA40 fills both.
char keyNames_462DA0[256][15];
char gamepadNames_45EAC0[9][15];
// Define Keyboard and Define Gamepad rows (menu types 6 and 8) of the
// original's menu text table, drawn as they are. sub_41CA40,
// redefineControls and defineGamepadJoystickMenu rebuild rows 0-7 as a
// template below plus the key name.
char defineKeyboardMenu_446DF4[9][50] = {
  "Accelerate    a",
  "Brake        z",
  "Steer Left    \xFA\xFAleft arrow",
  "Steer Right   \xFA\xFA\xFA\xFA\xFA\xFAright arrow",
  "Turbo Boost  \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAspace",
  "Machine Gun  \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAleft control",
  "Drop Mine    \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAleft alt",
  "Horn        \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAspace",
  "Previous Menu"
};
char defineGamepadMenu_447178[9][50] = {
  "Accelerate    a",
  "Brake        z",
  "Steer Left    \xFA\xFAleft arrow",
  "Steer Right   \xFA\xFA\xFA\xFA\xFA\xFAright arrow",
  "Turbo Boost  \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAspace",
  "Machine Gun  \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAleft control",
  "Drop Mine    \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFAleft alt",
  "Previous Menu",
  ""
};
// Row templates: label, spaces, then 0xFA bytes. drawTextWithFont advances
// 1 px for each 0xFA without drawing, which lines up the key names
// appended after them in one column.
const char aAccelerate_442AD0[] = "Accelerate    ";
const char aBrake_442A60[] = "Brake        ";
const char aSteerLeft_442A4C[] = "Steer Left    \xFA\xFA";
const char aSteerRight_442A34[] = "Steer Right   \xFA\xFA\xFA\xFA\xFA\xFA";
const char aTurboBoost_442A18[] = "Turbo Boost  \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA";
const char aMachineGun_4429FC[] = "Machine Gun  \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA";
const char aDropMine_4429E0[] = "Drop Mine    \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA";
const char aHorn_4429C0[] = "Horn        \xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA\xFA";

int dword_445798 = 9; // weak
int dword_4457B0 = 0; // weak



int dword_4457D0 = 8; // weak
int dword_4457E8 = 0; // weak
int dword_44575C = 0; // weak
int dword_445744 = 6; // weak


__int16 word_4470EE = 0; // weak
int gameStarted_456B5C = 0; // weak

int dword_45E1C0; // weak
int dword_456BC8 = 0; // idb
int dword_456A1C = 1; // weak

int dword_44570C = 6; // weak
/*menus sizes*///la entrada 9 es para el menu de continuar
int dword_4456F0[] = { 6,6,8,6,5,8,9,8,8   }; // weak  //entradas del menu
/*menus sizes*///la entrada 9 es para el menu de continuar
int dword_4456F4[] = { 145,0x6d,0x67,0x5f,0xa8,0xe7,0x32,0xd3,0x32   }; // weak
int dword_4456F8[] = { 124,0xab,0x76,0x92,0xc8,0x72,0x5d,0x74,0x71  }; // weak
int dword_4456FC[] = { 28,0x1c,0x1c,0x1c,0x1c,0x1c,0x1c,0x1c,0x1c   }; // weak
int dword_445700[] = { 349,0x1a5,0x1af,0x1e5,0x12f,0x17f,0x214,0x14f ,0x214  }; // weak
int dword_445704[] = { 192,0xc0,0xfa,0xc0,0xa1,0xfa,0x116,0xfa,0xfa  }; // weak
int dword_445708[] = { 0,0,2,0,0,0,0,0,0 }; // weak

int dword_4470E2 = 1701736276; // weak
int dword_4470E6 = 1634288672; // weak
int dword_4470EA = 1735289196; // weak

int dword_445188 = 163840; // weak
char byte_45FC10[256]; // weak
char menuaStartANewGame[17] = "Start A New Game"; // weak
char menuaStartANewGam_0[50] = "Start A New Game"; // 0x44652A, 50-byte menu text slot
char menuaStartRacing[50] = "Start Racing"; // 0x446368, holds "Continue Racing" too
//----- (0042E0B0) --------------------------------------------------------
signed int   readEventInMenu(int menuType)
{
  int v1; // edi@6
  signed int result; // eax@14
  int key;
  while ( 2 )
  {
    if ( dword_456B9C )
      goto LABEL_14;

	refreshAndCheckConnection_42A570();
    refreshAndCheckConnection_42A570();
    updateCursor(menuType);
	key = eventDetected();
    switch (key)
    {
      default:
        if(key != 0){
          key =1;
        }
        continue; 
      case KEY_ESCAPE :
        if ( !menuType)
        {
          if ( dword_445708[0] != dword_4456F0[0] - 1 )
          {
            sub_41ACF0(0);
            loadMenuSoundEffect(1u, 25, 0, configuration.effectsVolume, dword_445194);
          }
          continue;
        }
        v1 = -1;
        loadMenuSoundEffect(1u, 22, 0, configuration.effectsVolume, dword_445188);
LABEL_13:
        if ( dword_456B9C )
LABEL_14:
          result = -1;
        else
          result = v1;
        return result;
      case KEY_ENTER:
      case KEY_ESPACE:
      case 0x41:
      case SDLK_KP_ENTER:
      case 0x9C:


		  v1 = dword_445708[menuType];
		///v1 = dword_445708[7 * a1];
        loadMenuSoundEffect(1u, 28, 0, configuration.effectsVolume, dword_4451A0);
        if ( v1 != -2 )
          goto LABEL_13;
        continue;
      case KEY_F1:
      
        //if ( isMultiplayerGame )
         // multiplayer_sub_42CCF0();
        continue;
      case KEY_UP:
      case 0xC8:

		  refreshMenuUp(menuType);
        loadMenuSoundEffect(1u, 25, 0, configuration.effectsVolume, dword_445194);
        continue;
      case KEY_DOWN:
      case SDLK_DOWN:
      case 0xD0:
        refreshMenuDown(menuType);
	    loadMenuSoundEffect(1u, 25, 0, configuration.effectsVolume, dword_445194);

        continue;
     
    }
  }
}

//----- (0042E310) --------------------------------------------------------
bool   drawYesNoMenu(int a1, int a2, int a3, signed int *a4)
{
  signed int v4; // ebx@1
  int v5; // esi@1
  int v6; // eax@5
  signed int v7; // edx@5
  char *v8; // ebp@6
  bool v9; // zf@7
  bool v10; // sf@7
  unsigned __int8 v11; // of@7
  char v12; // al@9
  signed int v13; // edx@18
  char *v14; // edi@19
  signed int v15; // edx@23
  char *v16; // edi@24
  signed int v17; // esi@27
  int v19; // [sp-4h] [bp-14h]@1

  v4 = *a4;
  v5 = 640 * a2 + a1 + 7;
  v19 = 640 * a2 + a1 - 4450;
  if ( *a4 == 1 )
  {
    drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("yes"), v19);
    drawTextWithFont((int)graphics2.fbig3bBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("no"), 640 * a2 + a1 - 4280);
  }
  else
  {
    drawTextWithFont((int)graphics2.fbig3bBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("yes"), v19);
    drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("no"), 640 * a2 + a1 - 4280);
  }
  refreshAllScreen();
  while ( 2 )
  {
    refreshAndCheckConnection_42A570();
    refreshAndCheckConnection_42A570();
    v6 = -170 * v4;
    v7 = 20;
    do
    {
      v8 = (char *)screenBuffer + v6 + v5 + 170;
      *(_DWORD *)v8 = -993737532;
      *((_DWORD *)v8 + 1) = -993737532;
      *((_DWORD *)v8 + 2) = -993737532;
      *((_DWORD *)v8 + 3) = -993737532;
      v6 += 640;
      --v7;
      *((_DWORD *)v8 + 4) = -993737532;
    }
    while ( v7 );
    drawImageWithPosition(
      (int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame),
      20,
      20,
      (int)((char *)screenBuffer + v5 + -170 * v4 + 170));
    drawKeyCursor(640 * a2 + a1 + 2, (char *)screenBuffer + 640 * a2 + a1 + 2, 0xF0u, 28);
    v11 = __OFSUB__(cursorBpkFrame + 1, 49);
    v9 = cursorBpkFrame == 48;
    v10 = cursorBpkFrame++ - 48 < 0;
    if ( !((unsigned __int8)(v10 ^ v11) | v9) )
      cursorBpkFrame = 0;
    v12 = eventDetected();
    if ( v12 == 21 )
    {
      v12 = -53;
    }
    else if ( v12 == 49 )
    {
      v12 = -51;
    }
    switch ( v12 )
    {
      default:
        continue;
      case KEY_F1:
        //if ( isMultiplayerGame )
        //  multiplayer_sub_42CCF0();
        continue;
      case KEY_LEFT:
      case 0xCB:
        if ( !v4 )
          loadMenuSoundEffect(1u, 25, 0, configuration.effectsVolume, dword_445194);
        v4 = 1;
        v13 = 0;
        do
        {
          v14 = (char *)screenBuffer + v13;
          v13 += 640;
          memset(&v14[v5 - 5], 0xC4u, 0xF0u);
        }
        while ( v13 < 16000 );
        drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("yes"), 640 * a2 + a1 - 4450);
        drawTextWithFont((int)graphics2.fbig3bBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("no"), 640 * a2 + a1 - 4280);
        continue;
      case KEY_RIGHT:
      case 0xCD:
        if ( v4 == 1 )
          loadMenuSoundEffect(1u, 25, 0, configuration.effectsVolume, dword_445194);
        v4 = 0;
        v15 = 0;
        do
        {
          v16 = (char *)screenBuffer + v15;
          v15 += 640;
          memset(&v16[v5 - 5], 0xC4u, 0xF0u);
        }
        while ( v15 < 16000 );
        drawTextWithFont((int)graphics2.fbig3bBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("yes"), 640 * a2 + a1 - 4450);
        drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("no"), 640 * a2 + a1 - 4280);
        continue;
      case 1:
        if ( !a3 )
          continue;
        v4 = 0;
        v17 = -2;
        break;
      case KEY_ENTER:
      case 0x9C:
        v17 = -1;
        break;
    }
    break;
  }
  loadMenuSoundEffect(1u, 28, 0, configuration.effectsVolume, dword_4451A0);
  *a4 = v4;
  return v17 != -2;
}

//----- (00439CD0) --------------------------------------------------------
void startRacingMenu()
{
  signed int v0; // eax@6
  int v1; // esi@9
  int v2; // eax@11
  int v3; // eax@20
  int v4; // [sp+10h] [bp-4h]@11

  gameStarted_456B5C = 0;
LABEL_2:
  while ( !dword_456B64 )
  {
    memcpy((char *)screenBuffer + 58880, (char *)graphicsGeneral.menubg5Bpk + 58880, 0x2AF80u);
    drawMenu(INITIAL_MENU, 0);
	
	drawMenu(START_NEW_GAME_MENU, 1);
	if ( gameStarted_456B5C )
    {
      screenBuffer = (void *)dword_461250;
      sub_42C4A0();
      refreshAllScreen();
      gameStarted_456B5C = 0;
    }
    else
    {
      refreshAllScreen();
    }
	v0 = readEventInMenu(START_NEW_GAME_MENU);
	
    switch ( v0 )
    {
      case START_CONTINUE_GAME:
        if ( memcmp(menuaStartANewGam_0, "Start A New Game", 0x11u) )
          goto LABEL_10;
        drawMenu(START_NEW_GAME_MENU, 0);
        if ( licenseScreen(1) )
        {
          v1 = drivers[driverId].colour;
		  menuActive_4457F0[1] = 0;
		  menuActive_4457F0[10] = 1;
		  menuActive_4457F0[11] = 1;
		  menuActive_4457F0[13] = 1;
          showHardWarningRace = 1;
          showMediumWarningRace = 1;
          showUndergroundPopup_456B78 = 1;
          showWelcomePopup_456B74 = 1;
		  
		  isMultiplayerGame = 0; ///puesto por mi!
		  initDrivers();
          drivers[driverId].colour = v1;
          copyPalette1toPalette();
          *(_DWORD *)menuaStartANewGam_0 = 1702129221;
          *(_DWORD *)&menuaStartANewGam_0[4] = 1750343794;
          *(_DWORD *)&menuaStartANewGam_0[8] = 1750278245;
          *(_WORD *)&menuaStartANewGam_0[12] = 28783;
          menuaStartANewGam_0[14] = 0;
          *(_DWORD *)menuaStartRacing = 1953394499;
          firstRacePlayed_464F44 = 1;
		  menuActive_4457F0[10] = 1;
          *(_DWORD *)&menuaStartRacing[4] = 1702194793;
          *(_DWORD *)&menuaStartRacing[8] = 1667322400;
          *(_DWORD *)&menuaStartRacing[12] = 6778473;
LABEL_10:
          postLoadedOrLicense();
          gameStarted_456B5C = 1;
        }
        goto LABEL_2;
      case END_CURRENT_GAME:
        drawMenu(START_NEW_GAME_MENU, 0);
        createPopup(170, 220, 300, 80, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "End current game?", 146152);
        v4 = 1;
        v2 = drawYesNoMenu(180, 258, 1, &v4);
        if ( v4 )
        {
          if ( v2 )
          {
            *(_DWORD *)menuaStartANewGam_0 = *(_DWORD *)"Start A New Game";
            *(_DWORD *)&menuaStartANewGam_0[4] = *(_DWORD *)"t A New Game";
            *(_DWORD *)&menuaStartANewGam_0[8] = *(_DWORD *)"New Game";
            *(_DWORD *)&menuaStartANewGam_0[12] = *(_DWORD *)"Game";
            menuaStartANewGam_0[16] = menuaStartANewGame[16];
            *(_DWORD *)menuaStartRacing = 1918989395;
            *(_DWORD *)&menuaStartRacing[4] = 1632772212;
            *(_DWORD *)&menuaStartRacing[8] = 1735289187;
            menuaStartRacing[12] = 0;
			menuActive_4457F0[10] = 0;
			menuActive_4457F0[11] = 0;
			menuActive_4457F0[13] = 0;
            showHardWarningRace = 0;
            showMediumWarningRace = 0;
            showUndergroundPopup_456B78 = 0;
            showWelcomePopup_456B74 = 0;
            initDrivers();
            copyPalette1toPalette();
            firstRacePlayed_464F44 = 1;
            dword_445724 = 0;
          }
        }
        goto LABEL_2;
      case SEE_STADISTICS:
        seeStadistics_42C940();
        goto LABEL_2;
      case LOAD_GAME:
        if ( loadGame() )
        {
          postLoadedOrLicense();
          gameStarted_456B5C = 1;
        }
        goto LABEL_2;
      case SAVE_GAME:
        savegameWithName();
        goto LABEL_2;
      case PREVIOUS_MENU: //previous menu
        v3 = 0;
        dword_445724 = 0;
        if ( !menuActive_4457F0[9] )
        {
          do
          {
            if ( v3 >= dword_44570C - 1 )
              v3 = 0;
            else
              ++v3;
          }
          while ( !menuActive_4457F0[9+v3] );
          dword_445724 = v3;
        }
        return;
      default:
        if ( v0 == -1 )
          return;
        break;
    }
  }
}

//----- (0043A020) --------------------------------------------------------
int mainMenu()
{
  unsigned int v0; // eax@7
  void *v1 =malloc(0x4B000u); // eax@10
  int v2; // eax@10
  char *v3; // edx@10
  signed int v4; // ecx@10
  int v5; // eax@10
  float v6; // ST38_4@10
  float v7; // ST34_4@10
  float v8; // ST30_4@10
  signed int v31; // ebx@32
  unsigned __int8 v32; // bp@35
  signed int v33; // esi@35
  int v34; // ST38_4@36
  int v35; // ST34_4@36
  int v36; // eax@36
//  char *v37; // eax@54
//  char v38; // dl@55
//  unsigned int v39; // eax@56
//  char *v40; // edi@56
//  char v41; // cl@57
//  char *v42; // edi@58
//  char v43; // al@59
//  char *v44; // eax@60
//  char v45; // dl@61
//  unsigned int v46; // eax@62
//  char *v47; // edi@62
//  char v48; // cl@63
//  char *v49; // edi@64
//  char v50; // al@65
//  bool v51; // zf@66
//  char *v52; // eax@68
//  char *v53; // edx@68
//  char v54; // cl@69
//  unsigned int v55; // eax@70
//  char *v56; // edi@70
//  char v57; // cl@71
//  char *v58; // edi@72
//  char v59; // al@73
  signed int v62; // [sp+20h] [bp-8h]@1
  int i;
  int v63; // [sp+24h] [bp-4h]@1

  v62 = 0;
  v63 = 0;
  //checkIntro(); //esto solo chequea intro
  memset(usedNewsMessageFlags, 0, sizeof(usedNewsMessageFlags));
  dword_45E1C0 = 0;
  byte_45FB84 = 0;
  initCars();
  initDrivers();
  initShopMessages();
  loadConfig();
  //TODO review because is not necesary
	//dword_4A9140 = (int)exitGame;
  ++configuration.timesPlayed;
  saveConfiguration();
  printf("\nLoading music & effects, please wait..\n");
  
  
  checkAndOpenAnimation();
  
  loadMusic(1, "MEN-MUS.CMF", 2,"MEN-SAM.CMF");
  //es men-sam pero carga mal! loadMusic(1, "MEN-MUS.CMF", 2,"GEN-EFE.CMF");
  musicSetmusicVolume(configuration.musicVolume);
  musicSetVolume(configuration.effectsVolume);
  musicSetOrder(11520);
  nullsub_1();
  musicPlayMusic();
  nullsub_1();
  //estos arrays setean los circuitos iniciales de la partida
  byte_45FC10[0] = circuitOrder_45673C[0];
  byte_45FC10[3] = circuitOrder_45673C[3];
  //byte_45FC13 = byte_45673F;
  dword_456BC8 = 4;
  //byte_45FC11 = byte_45673D;
  byte_45FC10[1] = circuitOrder_45673C[1];
  byte_45FC10[2] = circuitOrder_45673C[2];
  //byte_45FC12 = byte_45673E[0];
  if ( configuration.useJoystick == 1 || configuration.useJoystick == 2 )
  {
    configJoystick();
    memcpy(aGamepadDisable, "Gamepad/Joystick Enabled", 0x19u);
  }
  else
  {
    memcpy(aGamepadDisable, "Gamepad/Joystick Disabled", 0x1Au);
  }
  if ( !configuration.dword_456734 )
  {
    dword_4470E2 = 1936487760; //Puls
    dword_4470E6 = 1766072421; //e Di
    dword_4470EA = 1852402785;//alin
    word_4470EE = 103;//g
  }
  v0 = SDL_GetTicks();
  srand(v0);
  nullsub_1();
  setWindowCaption2();
  if ( isVesaCompatible() )
  {
    setWindowCaption();
    printf("DEATH RALLY Error: Your VGA-adapter is not fully VESA (VBE 1.0) compliant.\n                   Use UNIVBE or similar emulator to fix the problem.\n");
    printf("Please consult DRHELP.EXE for more information on how to resolve this problem.\n");
    stopAndOpenMusic();
    freeMusic();
    nullsub_1();
    exit(112);
  }
  recalculateSDLTicks_43C740();
 // allocateMemoryPtr((void *)&v1,0x4B000u); //tama\F1o pantalla
  //puesto por mi
  screenBuffer = v1;
  dword_461250 = v1;  
  apogeeScreen();
  showStartScreen();
 
  inicializeGraphicVars();
  loadGraphics1();
  loadGraphics2();
  loadGraphics3();
  loadGraphics4();
  //SDL_Delay(2000);
  transitionToBlack();
  loadPaletteMenu();
  
 
  
  v2 = drivers[driverId].colour;
  v3 = (char *)graphicsGeneral.copperPal + 2 * v2;
  //allocateMemoryPtr(v3, 0x2u);
  v4 = (unsigned __int8)v3[v2 + 2];
  v5 = (int)&v3[v2];
  v6 = (double)v4;
  v7 = (double)*(BYTE *)(v5 + 1);
  v8 = (double)*(BYTE *)v5;
  sub_418B00(v8, v7, v6);
  
  memcpy(screenBuffer, graphicsGeneral.menubg5Bpk, 0x4B000u); //tama\F1o pantalla

  

  memset(bottomMenuTextFont, 0, sizeof(bottomMenuTextFont));
  for ( i = 0; i < 22; ++i )
    bottomMenuText[i][0] = 0;
  strcpy(bottomMenuText[21], "     Welcome to Death Rally(tm) - Windows Version 1.0");
  bottomMenuTextFont[21] = 1;
  for ( i = 0; i < 21; ++i )
    bottomMenuTextFont[i] = bottomMenuTextFont[i + 1];
  for ( i = 1; i < 22; ++i )
    strcpy(bottomMenuText[i - 1], bottomMenuText[i]);
  strcpy(bottomMenuText[21], "         Port by Jari Komppa - http://iki.fi/sol/");
  bottomMenuTextFont[21] = 1;
  for ( i = 0; i < 21; ++i )
    bottomMenuTextFont[i] = bottomMenuTextFont[i + 1];
  for ( i = 1; i < 22; ++i )
    strcpy(bottomMenuText[i - 1], bottomMenuText[i]);
  strcpy(bottomMenuText[21], "    (c)Remedy Entertainment - http://www.remedygames.com");
  bottomMenuTextFont[21] = 1;
  for ( i = 0; i < 21; ++i )
    bottomMenuTextFont[i] = bottomMenuTextFont[i + 1];
  for ( i = 1; i < 22; ++i )
    strcpy(bottomMenuText[i - 1], bottomMenuText[i]);
  bottomMenuText[21][0] = 0;
  bottomMenuTextFont[21] = 1;
  for ( i = 0; i < 21; ++i )
    bottomMenuTextFont[i] = bottomMenuTextFont[i + 1];
  for ( i = 1; i < 22; ++i )
    strcpy(bottomMenuText[i - 1], bottomMenuText[i]);
  strcpy(bottomMenuText[21], "Use arrow keys to change selection and press enter to confirm.");
  bottomMenuTextFont[21] = 1;
  drawTransparentBlock(0, 371, 639, 109);
  
  drawBottomMenuText();
  
  
  
  do
  {
	  menuActive_4457F0[1] = 0;
	  memcpy((char *)screenBuffer + 53760, (char *)graphicsGeneral.menubg5Bpk + 53760, 0x2C380u);
	  drawMenu(INITIAL_MENU, 1);
	  
	  if ((dword_456A1C || dword_456B64) && !dword_456B9C)
	  {
		  refreshAllScreen();
		  sub_4224E0();
		  v31 = 0;
		  do
		  {
			  waitWithRefresh();
			  if (v31 % 2)
				  updateCursor(0);
			  v32 = 0;
			  v33 = 0;
			  //FIXED
			  //v33 = (signed int)dword_45FC44;
			  do
			  {
				  v34 = (convertColorToPaletteColor((palette1[v33+2]), v31 << 17) + 0x8000) >> 16;
				  v35 = (convertColorToPaletteColor(palette1[v33 +1], v31 << 17) + 0x8000) >> 16;
				  v36 = convertColorToPaletteColor((palette1[v33 ]), v31 << 17);
				  setPaletteAndGetValue(v32, (v36 + 0x8000) >> 16, v35, v34);
				  v33 += 3;
				  ++v32;
			  } while (v33 < maxPaletteEntries);
			  ++v31;
		  } while (v31 < 50);
		  dword_456A1C = 0;
		  if (dword_456B64)
		  {
			  dword_456B64 = 0;
			  memcpy((void *)dword_461250, dword_461ED8, 0x4B000u);
			  screenBuffer = (void *)dword_461250;
			  dword_461ED8 = (void *)dword_45FC00;
		  }
	  }
	  
	   if (v62)
	  {
		  if (dword_456B9C)
			  goto LABEL_45;
		  screenBuffer = (void *)dword_461250;
		  sub_42C560(-1);
		  stopSong();
		  musicPlayMusic();
		  musicSetOrder(dword_462D7C);
		  setMusicVolume(0x10000);
		  v62 = 0;
	  }
	  if (!dword_456B9C)
		  refreshAllScreen();
  LABEL_45:
	  switch ( readEventInMenu(INITIAL_MENU) )
	  {
		case 0:
		  startRacingMenu();
		  break;
		case 2:
		  showAdjustOptions();
		  break;
		case 3:
		  seeHallOfFame();
		  v62 = 1;
		  break;
		case 4:
		  showCredits();
		  break;
		case 5:
			//exit to os
		  drawMenu(INITIAL_MENU, 0);
		  createPopup(170, 200, 300, 80, 1);
		  drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, getLanguageEntry("Are you sure?"), 133373);
		  drawYesNoMenu(180, 238, 1, &v63);
		  break;
		default:

		  break;
	  }
	  if (!dword_456B9C) {
		  v62 = 0;
	  }
  

  }
  while ( !v63 );
  /*if ( isMultiplayerGame )
  {
    if ( !memcmp(&dword_44671E, "Abort Current Game", 0x13u) )
    {
      v37 = &byte_460840[108 * driverId];
      dword_462C4E = 2108717;
      do
        v38 = *v37++;
      while ( v38 );
      v39 = v37 - &byte_460840[108 * driverId];
      v40 = (char *)&dword_462C4E - 1;
      do
        v41 = (v40++)[1];
      while ( v41 );
      memcpy(v40, &byte_460840[108 * driverId], v39);
      v42 = (char *)&dword_462C4E - 1;
      do
        v43 = (v42++)[1];
      while ( v43 );
      memcpy(v42, " has left from Death Rally.", 0x1Cu);
      HIBYTE(word_461ED4) = 0;
      multiplayer_41EA70((int)&dword_462C4E, 100, 20);
      v44 = &byte_460840[108 * driverId];
      dword_462C4E = 2108717;
      do
        v45 = *v44++;
      while ( v45 );
      v46 = v44 - &byte_460840[108 * driverId];
      v47 = (char *)&dword_462C4E - 1;
      do
        v48 = (v47++)[1];
      while ( v48 );
      memcpy(v47, &byte_460840[108 * driverId], v46);
      v49 = (char *)&dword_462C4E - 1;
      do
        v50 = (v49++)[1];
      while ( v50 );
      memcpy(v49, " aborted current netgame.", 0x18u);
      HIBYTE(word_461ED4) = 0;
      v51 = dword_45E0A8 == 2;
      *((_WORD *)v49 + 12) = *(_WORD *)".";
      if ( !v51 )
      {
        multiplayer_41EA70((int)&dword_462C4E, 100, 9);
        goto LABEL_76;
      }
    }
    else
    {
      v52 = &byte_460840[108 * driverId];
      dword_462C4E = 2108717;
      v53 = &byte_460840[108 * driverId];
      do
        v54 = *v52++;
      while ( v54 );
      v55 = v52 - v53;
      v56 = (char *)&dword_462C4E - 1;
      do
        v57 = (v56++)[1];
      while ( v57 );
      memcpy(v56, v53, v55);
      v58 = (char *)&dword_462C4E - 1;
      do
        v59 = (v58++)[1];
      while ( v59 );
      memcpy(v58, " has left from Death Rally.", 0x1Cu);
      HIBYTE(word_461ED4) = 0;
    }
    multiplayer_41EA70((int)&dword_462C4E, 100, 6);
LABEL_76:
    nullsub_1();
    nullsub_1();
    isMultiplayerGame = 0;
    dword_45E0A8 = 0;
  }*/
  showEndScreen();
  saveConfiguration();
  freeMemoryGraphics();
  freeMemoryGraphics1();
  freeMemoryGraphics2();
  freeMemoryGraphics3();
  freeMemoryGraphics4();
  stopSong();
  return stopAndOpenMusic();
}

//----- (0041A880) --------------------------------------------------------

//pinta el menu
//menu type
// 0 es el menu principal
// 1 es comenzar racing
int   drawMenu(int menuType, int top)
{
  int v2; // edi@1
  int v3; // esi@1
  int result; // eax@1
  int v5; // ebx@1
  signed int v6; // ebp@1
  int v7; // eax@2
  const char *v8; // edi@2
  int v9; // eax@5
  int v10; // eax@14
  int v11; // ecx@14
  int v12; // [sp+10h] [bp-4h]@2
  signed int v13; // [sp+18h] [bp+4h]@1
  int menuEntryIndex = 0;
  v2 = menuType;
  //v3 = 7 * a1;
  v3 = menuType;
  //createPopup(dword_4456F4[7 * a1], dword_4456F8[7 * a1], dword_445700[7 * a1], dword_445704[7 * a1], checked);
  createPopup(dword_4456F4[menuType], dword_4456F8[menuType], dword_445700[menuType], dword_445704[menuType], top);
  result = dword_4456F0[menuType];
  //result = dword_4456F0[7 * a1];
  v5 = 0;
  v6 = 3232;
  v13 = 7049;
  if ( result > 0 )
  {
    v7 = 9 * v2;
    v12 = 9 * v2;
   // v8 = &aStartRacing[450 * v2];

	///si el menu es 6 keyboard definition hay que poner la tecla
	v8 = getMenuText(menuType, menuEntryIndex);
	
    while ( dword_445708[v3] != v5 )
    {
      if ( *(&menuActive_4457F0[v7] + v5) != 1 )
      {
        v9 = dword_4456F8[v3];
LABEL_13:
        drawTextWithFont((int)graphics2.fbig3dBpk, (int)&bigLetterSpacing_445848, v8, v6 + dword_4456F4[v3] + 640 * v9);
        goto LABEL_14;
      }
      if (top == 1 )
      {
        drawTextWithFont((int)graphics2.fbig3bBpk, (int)&bigLetterSpacing_445848, v8, v6 + dword_4456F4[v3] + 640 * dword_4456F8[v3]);
      }
      else if ( !top)
      {
        drawTextWithFont((int)graphics2.fbig3dBpk, (int)&bigLetterSpacing_445848, v8, v6 + dword_4456F4[v3] + 640 * dword_4456F8[v3]);
      }
LABEL_14:
      v10 = 640 * dword_4456FC[v3];
      v11 = v10 + v13;
      v6 += v10;
      result = dword_4456F0[v3];
      ++v5;
	   if ( v5 >= result )
        return result;
	  v8 = getMenuText(menuType, ++menuEntryIndex);
      v13 = v11;
      if ( v5 >= result )
        return result;
      v7 = v12;
    }
    v9 = dword_4456F8[v3];
    if (top > 0 )
    {
      drawImageWithPosition(
        (int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame),
        20,  20,
        (int)((char *)screenBuffer + 640 * v9 + dword_4456F4[v3] + v13));
      drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, v8, v6 + dword_4456F4[v3] + 640 * dword_4456F8[v3]);
      goto LABEL_14;
    }
    goto LABEL_13;
  }
  return result;
}

//----- (0041AA40) --------------------------------------------------------
int   drawKeyCursor(signed int a1, const void *a2, unsigned int a3, int a4)
{
  signed int v4; // ebx@1
  signed int v5; // edi@1
  int result; // eax@1
  const void *v7; // ebp@2
  unsigned int v8; // esi@3
  signed int v9; // esi@9
  bool v10; // zf@11
  unsigned int v11; // [sp+8h] [bp+4h]@8

  v4 = a1;
  v5 = a1 >> 16;
  updateScreenPtr(a1 >> 16);
  result = a4;
  if ( a4 > 0 )
  {
    v7 = a2;
    while ( 1 )
    {
      v8 = a3;
      if ( (signed int)(a3 + v4 % 0x10000) < 0xFFFF )
        break;
      if ( (signed int)a3 > 0 )
      {
        v11 = a3;
        do
        {
          v9 = v4 >> 16;
          if ( v5 != v4 >> 16 )
            updateScreenPtr(v4 >> 16);
          *(BYTE *)(v4++ % 0x10000 + screenPtr) = *(BYTE *)v7;
          v7 = (char *)v7 + 1;
          v10 = v11 == 1;
          v5 = v9;
          --v11;
        }
        while ( !v10 );
        goto LABEL_12;
      }
LABEL_13:
      v4 += 640 - v8;
      v7 = (char *)v7 + 640 - v8;
      result = a4-- - 1;
      if ( !a4 )
        return result;
    }
    if ( v5 != v4 >> 16 )
      updateScreenPtr(v4 >> 16);
    memcpy((void *)(v4 % 0x10000 + screenPtr), v7, a3);
    v5 = v4 >> 16;
    v4 += a3;
    v7 = (char *)v7 + a3;
LABEL_12:
    v8 = a3;
    goto LABEL_13;
  }
  return result;
}
// 456BF0: using guessed type int screenPtr;

//----- (0041AB50) --------------------------------------------------------
int   updateCursor(int a1)
{
  int v1; // esi@1
  int v2; // edi@1
  signed int v3; // ecx@1
  char *v4; // eax@2
  int v5; // eax@3
  int result; // eax@3
  bool v7; // zf@3
  bool v8; // sf@3
  unsigned __int8 v9; // of@3

  v1 = a1;
  //v1 = 7 * a1;
  v2 = 640 * dword_4456FC[ a1] * dword_445708[ a1] + 7049;
  //v2 = 640 * dword_4456FC[7 * a1] * dword_445708[7 * a1] + 7049;
  v3 = 0;
  do
  {
    v4 = (char *)screenBuffer + 640 * (v3 + dword_4456F8[v1]) + v2 + dword_4456F4[v1];
    *(_DWORD *)v4 = -993737532;
    *((_DWORD *)v4 + 1) = -993737532;
    *((_DWORD *)v4 + 2) = -993737532;
    ++v3;
    *((_DWORD *)v4 + 3) = -993737532;
    *((_DWORD *)v4 + 4) = -993737532;
  }
  while ( v3 < 20 );
  drawImageWithPosition(
    (int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame),
    20,
    20,
    (int)((char *)screenBuffer + 640 * dword_4456F8[v1] + v2 + dword_4456F4[v1]));
  v5 = dword_4456F4[v1] + 640 * dword_4456F8[v1];
  drawKeyCursor(v2 + v5, (char *)screenBuffer + v5 + v2, 0x14u, 20);
  result = cursorBpkFrame + 1;
  v9 = __OFSUB__(cursorBpkFrame + 1, 49);
  v7 = cursorBpkFrame == 48;
  v8 = cursorBpkFrame++ - 48 < 0;
  if ( !((unsigned __int8)(v8 ^ v9) | v7) )
    cursorBpkFrame = 0;
  return result;
}

//----- (0041AC50) --------------------------------------------------------
int   drawCursor(int a1, int a2)
{
  signed int v2; // esi@1
  signed int v3; // eax@1
  char *v4; // edx@2
  int result; // eax@3
  bool v6; // zf@3
  bool v7; // sf@3
  unsigned __int8 v8; // of@3

  v2 = a1 + 640 * a2;
  v3 = 0;
  do
  {
    v4 = (char *)screenBuffer + v3 + v2;
    *(_DWORD *)v4 = -993737532;
    *((_DWORD *)v4 + 1) = -993737532;
    *((_DWORD *)v4 + 2) = -993737532;
    v3 += 640;
    *((_DWORD *)v4 + 3) = -993737532;
    *((_DWORD *)v4 + 4) = -993737532;
  }
  while ( v3 < 12800 );
  drawImageWithPosition((int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame), 20, 20, (int)((char *)screenBuffer + v2));
  drawKeyCursor(v2, (char *)screenBuffer + v2, 0x14u, 20);
  result = cursorBpkFrame + 1;
  v8 = __OFSUB__(cursorBpkFrame + 1, 49);
  v6 = cursorBpkFrame == 48;
  v7 = cursorBpkFrame++ - 48 < 0;
  if ( !((unsigned __int8)(v7 ^ v8) | v6) )
    cursorBpkFrame = 0;
  return result;
}
// 45FBF8: using guessed type int cursorBpkFrame;

//----- (0041ACF0) --------------------------------------------------------
int   sub_41ACF0(int a1)
{
  int v1; // esi@1
  int v2; // ebx@1
  int v3; // edx@1
  int v4; // eax@3
  int v5; // edx@3
  int v6; // eax@3
  int v7; // ebp@3
  bool v8; // zf@4
  int v9; // edx@5
  int v10; // eax@5
  int v11; // edi@5
  signed int v13; // [sp+10h] [bp-10h]@1
  signed int v14; // [sp+10h] [bp-10h]@3
  unsigned int v15; // [sp+14h] [bp-Ch]@1
  unsigned int v16; // [sp+18h] [bp-8h]@1
  int v18; // [sp+1Ch] [bp-4h]@1
  int v19; // [sp+24h] [bp+4h]@3

  v1 =  a1;
  v2 = dword_4456F4[ a1];
  v15 = dword_445700[ a1] - 10;
  v16 = dword_445700[ a1] - 20;
  v18 = 640 * (dword_445708[ a1] * dword_4456FC[ a1] + dword_4456F8[ a1] + 6);
  v3 = 640 * (dword_445708[ a1] * dword_4456FC[a1] + dword_4456F8[ a1] + 6);
  /*v1 = 7 * a1;
  v2 = dword_4456F4[7 * a1];
  v15 = dword_445700[7 * a1] - 10;
  v16 = dword_445700[7 * a1] - 20;
  v18 = 640 * (dword_445708[7 * a1] * dword_4456FC[7 * a1] + dword_4456F8[7 * a1] + 6);
  v3 = 640 * (dword_445708[7 * a1] * dword_4456FC[7 * a1] + dword_4456F8[7 * a1] + 6);*/
  v13 = 22;
  do
  {
    memset((char *)screenBuffer + v3 + v2 + 2569, 0xC4u, v16);
    v3 += 640;
    --v13;
  }
  while ( v13 );
  drawTextWithFont(
    (int)graphics2.fbig3bBpk,
    (int)&bigLetterSpacing_445848,
    getMenuText(a1, dword_445708[v1]),
    640 * (dword_4456F8[v1] + dword_445708[v1] * dword_4456FC[v1]) + dword_4456F4[v1] + 3232);
  v4 = dword_4456F0[v1] - 1;
  v5 = v4 * dword_4456FC[v1];
  dword_445708[v1] = v4;
  v6 = dword_4456F8[v1];
  v7 = 640 * (v5 + v6 + 6);
  v19 = 640 * (v5 + v6 + 6);
  v14 = 22;
  do
  {
    memset((char *)screenBuffer + v19 + v2 + 2569, 0xC4u, v15 - 10);
    v8 = v14 == 1;
    v19 += 640;
    --v14;
  }
  while ( !v8 );
  v9 = dword_445708[v1];
  v10 = v9 * dword_4456FC[v1];
  v11 = 640 * v10 + 7049;
  drawTextWithFont(
    (int)graphicsGeneral.fbig3aBpk,
    (int)&bigLetterSpacing_445848,
    getMenuText(a1, v9),
    640 * (v10 + dword_4456F8[v1]) + dword_4456F4[v1] + 3232);
  drawImageWithPosition(
    (int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame),
    20,
    20,
    (int)((char *)screenBuffer + 640 * dword_4456F8[v1] + dword_4456F4[v1] + v11));
  drawKeyCursor(v18 + v2 + 7, (char *)screenBuffer + v18 + v2 + 7, v15, 32);
  return drawKeyCursor(v2 + v7 + 7, (char *)screenBuffer + v7 + v2 + 7, v15, 32);
}
// 4456F0: using guessed type int dword_4456F0[];
// 4456F4: using guessed type int dword_4456F4[];
// 4456F8: using guessed type int dword_4456F8[];
// 4456FC: using guessed type int dword_4456FC[];
// 445700: using guessed type int dword_445700[];
// 445708: using guessed type int dword_445708[];
// 45FBF8: using guessed type int cursorBpkFrame;

//----- (0041AF40) --------------------------------------------------------
int   refreshMenuUp(int a1)
{
  int v1; // esi@1
  int v2; // ebx@1
  int v3; // edx@1
  int v4; // eax@3
  int v6; // edx@7
  int v7; // eax@7
  int v8; // ebp@7
  bool v9; // zf@8
  int v10; // edx@9
  int v11; // eax@9
  int v12; // edi@9
  signed int v14; // [sp+10h] [bp-10h]@1
  signed int v15; // [sp+10h] [bp-10h]@7
  unsigned int v16; // [sp+14h] [bp-Ch]@1
  unsigned int v17; // [sp+18h] [bp-8h]@1
  int v18; // [sp+18h] [bp-8h]@3
  int v19; // [sp+1Ch] [bp-4h]@1
  int v20; // [sp+24h] [bp+4h]@7

  v1 = a1;
  v2 = dword_4456F4[ a1];
  v16 = dword_445700[ a1] - 10;
  v17 = dword_445700[ a1] - 20;
  v19 = 640 * (dword_445708[ a1] * dword_4456FC[ a1] + dword_4456F8[ a1] + 6);
  v3 = 640 * (dword_445708[ a1] * dword_4456FC[ a1] + dword_4456F8[ a1] + 6);
  /*v1 = 7 * a1;
  v2 = dword_4456F4[7 * a1];
  v16 = dword_445700[7 * a1] - 10;
  v17 = dword_445700[7 * a1] - 20;
  v19 = 640 * (dword_445708[7 * a1] * dword_4456FC[7 * a1] + dword_4456F8[7 * a1] + 6);
  v3 = 640 * (dword_445708[7 * a1] * dword_4456FC[7 * a1] + dword_4456F8[7 * a1] + 6);*/
  v14 = 22;
  do
  {
    memset((char *)screenBuffer + v3 + v2 + 2569, 0xC4u, v17);
    v3 += 640;
    --v14;
  }
  while ( v14 );
  v18 = 9 * a1;
  /*drawTextWithFont(
    (int)fbig3bBpk,
    (int)&bigLetterSpacing_445848,
    &aStartRacing[50 * (9 * a1 + dword_445708[v1])],
    640 * (dword_4456F8[v1] + dword_445708[v1] * dword_4456FC[v1]) + dword_4456F4[v1] + 3232);*/
  drawTextWithFont(
	  (int)graphics2.fbig3bBpk,
	  (int)&bigLetterSpacing_445848,
	  getMenuText(a1, dword_445708[v1]),
	  640 * (dword_4456F8[v1] + dword_445708[v1] * dword_4456FC[v1]) + dword_4456F4[v1] + 3232);

  
  v4 = dword_445708[v1];
  do
  {
    if ( v4 <= 0 )
      v4 = dword_4456F0[v1];
  }
  //ver si es menuactive o bigletterspacing
  while ( !*(&menuActive_4457F0[9 * a1]-1 + v4--) );
  //while (!*(&byte_4457EF[9 * a1] + v4--));
  v6 = v4 * dword_4456FC[v1];
  dword_445708[v1] = v4;
  v7 = dword_4456F8[v1];
  v8 = 640 * (v6 + v7 + 6);
  v20 = 640 * (v6 + v7 + 6);
  v15 = 22;
  do
  {
    memset((char *)screenBuffer + v20 + v2 + 2569, 0xC4u, v16 - 10);
    v9 = v15 == 1;
    v20 += 640;
    --v15;
  }
  while ( !v9 );
  v10 = dword_445708[v1];
  v11 = v10 * dword_4456FC[v1];
  v12 = 640 * v11 + 7049;
 /* drawTextWithFont(
    (int)graphicsGeneral.fbig3aBpk,
    (int)&bigLetterSpacing_445848,
    &aStartRacing[50 * (v10 + v18)],
    640 * (v11 + dword_4456F8[v1]) + dword_4456F4[v1] + 3232);*/
  drawTextWithFont(
	  (int)graphicsGeneral.fbig3aBpk,
	  (int)&bigLetterSpacing_445848,
	  getMenuText(a1, v10),
	  640 * (v11 + dword_4456F8[v1]) + dword_4456F4[v1] + 3232);
 
  drawImageWithPosition(
    (int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame),
    20,
    20,
    (int)((char *)screenBuffer + 640 * dword_4456F8[v1] + dword_4456F4[v1] + v12));
  drawKeyCursor(v19 + v2 + 7, (char *)screenBuffer + v19 + v2 + 7, v16, 32);
  return drawKeyCursor(v2 + v8 + 7, (char *)screenBuffer + v8 + v2 + 7, v16, 32);
}

//----- (0041B1A0) --------------------------------------------------------
int   refreshMenuDown(int a1)
{
  int v1; // esi@1
  int v2; // ebx@1
  int v3; // edx@1
  int v4; // eax@3
  int v5; // edx@8
  int v6; // eax@8
  int v7; // ebp@8
  bool v8; // zf@9
  int v9; // edx@10
  int v10; // eax@10
  int v11; // edi@10
  signed int v13; // [sp+10h] [bp-10h]@1
  signed int v14; // [sp+10h] [bp-10h]@8
  unsigned int v15; // [sp+14h] [bp-Ch]@1
  unsigned int v16; // [sp+18h] [bp-8h]@1
  int v17; // [sp+18h] [bp-8h]@3
  int v18; // [sp+1Ch] [bp-4h]@1
  int v19; // [sp+24h] [bp+4h]@8

  v1 =  a1;
  v2 = dword_4456F4[ a1];
  v15 = dword_445700[ a1] - 10;
  v16 = dword_445700[ a1] - 20;
  v18 = 640 * (dword_445708[ a1] * dword_4456FC[ a1] + dword_4456F8[ a1] + 5);
  v3 = 640 * (dword_445708[a1] * dword_4456FC[ a1] + dword_4456F8[ a1] + 5);
 /*v1 = 7 * a1;
  v2 = dword_4456F4[7 * a1];
  v15 = dword_445700[7 * a1] - 10;
  v16 = dword_445700[7 * a1] - 20;
  v18 = 640 * (dword_445708[7 * a1] * dword_4456FC[7 * a1] + dword_4456F8[7 * a1] + 5);
  v3 = 640 * (dword_445708[7 * a1] * dword_4456FC[7 * a1] + dword_4456F8[7 * a1] + 5);*/
  v13 = 22;
  do
  {
    memset((char *)screenBuffer + v3 + v2 + 2569, 0xC4u, v16);
    v3 += 640;
    --v13;
  }
  while ( v13 );
  v17 = 9 * a1;
  /*drawTextWithFont(
	  (int)fbig3bBpk,
	  (int)&bigLetterSpacing_445848,
	  &aStartRacing[50 * (9 * a1 + dword_445708[v1])],
	  640 * (dword_4456F8[v1] + dword_445708[v1] * dword_4456FC[v1]) + dword_4456F4[v1] + 3232);*/
  drawTextWithFont(
    (int)graphics2.fbig3bBpk,
    (int)&bigLetterSpacing_445848,
	  getMenuText(a1, dword_445708[v1]),
    640 * (dword_4456F8[v1] + dword_445708[v1] * dword_4456FC[v1]) + dword_4456F4[v1] + 3232);
  v4 = dword_445708[v1];
  do
  {
    if ( v4 >= dword_4456F0[v1] - 1 )
      v4 = 0;
    else
      ++v4;
  }
  while ( !*(&menuActive_4457F0[9 * a1] + v4) );
  v5 = v4 * dword_4456FC[v1];
  dword_445708[v1] = v4;
  v6 = dword_4456F8[v1];
  v7 = 640 * (v5 + v6 + 5);
  v19 = 640 * (v5 + v6 + 5);
  v14 = 22;
  do
  {
    memset((char *)screenBuffer + v19 + v2 + 2569, 0xC4u, v15 - 10);
    v8 = v14 == 1;
    v19 += 640;
    --v14;
  }
  while ( !v8 );
  v9 = dword_445708[v1];
  v10 = v9 * dword_4456FC[v1];
  v11 = 640 * v10 + 7049;
  /*drawTextWithFont(
	  (int)graphicsGeneral.fbig3aBpk,
	  (int)&bigLetterSpacing_445848,
	  &aStartRacing[50 * (v9 + v17)],
	  640 * (v10 + dword_4456F8[v1]) + dword_4456F4[v1] + 3232);*/
  drawTextWithFont(
    (int)graphicsGeneral.fbig3aBpk,
    (int)&bigLetterSpacing_445848,
	  getMenuText(a1, v9 ), 
    640 * (v10 + dword_4456F8[v1]) + dword_4456F4[v1] + 3232);
  drawImageWithPosition(
    (int)((char *)graphics2.cursorBpk + 400 * cursorBpkFrame),
    20,
    20,
    (int)((char *)screenBuffer + 640 * dword_4456F8[v1] + dword_4456F4[v1] + v11));
  drawKeyCursor(v18 + v2 + 7, (char *)screenBuffer + v18 + v2 + 7, v15, 32);
  return drawKeyCursor(v2 + v7 + 7, (char *)screenBuffer + v7 + v2 + 7, v15, 32);
}

//----- (0042C940) --------------------------------------------------------
char seeStadistics_42C940()
{
  signed int v0; // ebp@1
  int v1; // esi@1
  unsigned __int8 v2; // bl@4
  signed int v3; // edi@4
  int v4; // ST20_4@5
  int v5; // ST1C_4@5
  int v6; // eax@5
  unsigned __int8 v7; // bl@6
  signed int v8; // edi@6
  int v9; // ST20_4@7
  int v10; // ST1C_4@7
  int v11; // eax@7
  signed int v12; // ebp@11
  int v13; // esi@11
  unsigned __int8 v14; // bl@14
  signed int v15; // edi@14
  int v16; // ST20_4@15
  int v17; // ST1C_4@15
  int v18; // eax@15
  unsigned __int8 v19; // bl@16
  signed int v20; // edi@16
  int v21; // ST20_4@17
  int v22; // ST1C_4@17
  int v23; // eax@17
  const char **v25; // [sp+0h] [bp-10h]@0
  const char **v26; // [sp+4h] [bp-Ch]@0

  sub_4224E0();
  v0 = 50;
  v1 = 6553600;
  do
  {
    waitWithRefresh();
    if ( v0 % 2 )
      updateCursor(1);
    v2 = 0;
    v3 = 0;
	//FIXED
	//v3 = (signed int)dword_45FC44;
    do
    {
      v4 = (convertColorToPaletteColor((palette1[v3+2]), v1) + 0x8000) >> 16;
      v5 = (convertColorToPaletteColor(palette1[v3 + 1], v1) + 0x8000) >> 16;
      v6 = convertColorToPaletteColor((palette1[v3]), v1);
      setPaletteAndGetValue(v2, (v6 + 0x8000) >> 16, v5, v4);
      v3 += 3;
      ++v2;
    }
    while ( v3 <288);
	//while (v3 < (signed int)&unk_4600C4);
    v7 = -128;
    v8 = 384;
	//FIXED
	//v8 = (signed int)&unk_460244;
    do
    {
      v9 = (convertColorToPaletteColor(palette1[v8+2], v1) + 0x8000) >> 16;
      v10 = (convertColorToPaletteColor(palette1[v8 + 1], v1) + 0x8000) >> 16;
      v11 = convertColorToPaletteColor(palette1[v8 ], v1);
      setPaletteAndGetValue(v7, (v11 + 0x8000) >> 16, v10, v9);
      v8 += 3;
      ++v7;
	  /* v9 = (convertColorToPaletteColor(*(_DWORD *)(v8 + 4), v1) + 0x8000) >> 16;
      v10 = (convertColorToPaletteColor(*(_DWORD *)v8, v1) + 0x8000) >> 16;
      v11 = convertColorToPaletteColor(*(_DWORD *)(v8 - 4), v1);
      setPaletteAndGetValue(v7, (v11 + 0x8000) >> 16, v10, v9);
      v8 += 12;
      ++v7;*/
    }
    while ( v8 < maxPaletteEntries);
	//while (v8 < (signed int)&unk_460844);
    --v0;
    v1 -= 0x20000;
  }
  while ( v1 >= 0 );
  sub_418090();
  eventDetected();
  //esto es mio 
  v26 = malloc(10);
  v25 = malloc(10);
  //same case: postRaceMain only checks argc, and v25/v26 were not initialized.
  postRaceMain(2, (const char **)"", (const char **)"");
  memcpy(screenBuffer, graphicsGeneral.menubg5Bpk, 0x4B000u);
  drawMenu(INITIAL_MENU, 0);
  drawMenu(START_NEW_GAME_MENU, 1);
  drawTransparentBlock(0, 371, 639, 109);
  if ( isMultiplayerGame )
  {
    drawTextWithFont((int)graphicsGeneral.fsma3bBpk, (int)&letterSpacing_4458B0, "press   to enter chat mode", 233635);
    drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "F1", 233689);
  }
  drawBottomMenuText();
  refreshAllScreen();
  sub_4224E0();
  v12 = 0;
  v13 = 0;
  do
  {
    waitWithRefresh();
    if ( v12 % 2 )
      updateCursor(1);
    v14 = 0;
    v15 =0;
	//FIXED
	//v15 = (signed int)dword_45FC44;
    do
    {
      v16 = (convertColorToPaletteColor((palette1[v15+2]), v13) + 0x8000) >> 16;
      v17 = (convertColorToPaletteColor(palette1[v15 + 1], v13) + 0x8000) >> 16;
      v18 = convertColorToPaletteColor((palette1[v15 ]), v13);
      setPaletteAndGetValue(v14, (v18 + 0x8000) >> 16, v17, v16);
      v15 += 3;
      ++v14;
    }
    while ( v15 < 288 );
	//while (v15 < (signed int)&unk_4600C4);
    v19 = -128;
	v20 = 384;
	//FIXED
    //v20 = (signed int)&unk_460244;
    do
    {
      v21 = (convertColorToPaletteColor(palette1[v20 + 2], v13) + 0x8000) >> 16;
      v22 = (convertColorToPaletteColor(palette1[v20 + 1], v13) + 0x8000) >> 16;
      v23 = convertColorToPaletteColor(palette1[v20], v13);
      setPaletteAndGetValue(v19, (v23 + 0x8000) >> 16, v22, v21);
      v20 += 3;
      ++v19;
	  /* v21 = (convertColorToPaletteColor(*(_DWORD *)(v20 + 4), v13) + 0x8000) >> 16;
      v22 = (convertColorToPaletteColor(*(_DWORD *)v20, v13) + 0x8000) >> 16;
      v23 = convertColorToPaletteColor(*(_DWORD *)(v20 - 4), v13);
      setPaletteAndGetValue(v19, (v23 + 0x8000) >> 16, v22, v21);
      v20 += 12;
      ++v19;*/

    }
    while ( v20 < maxPaletteEntries);
	//while ( v20 < (signed int)&unk_460844 );
    v13 += 0x20000;
    ++v12;
  }
  while ( v13 < 6553600 );
  sub_418090();
  
  return eventDetected();
}

//----- (004302E0) --------------------------------------------------------
signed int defineGamepadJoystickMenu()
{
  signed int v0; // eax@2
  signed int v1; // ebx@2
  signed int result; // eax@2

  sub_41CA40();
  while ( 2 )
  {
    memcpy((char *)screenBuffer + 67200, (char *)graphicsGeneral.menubg5Bpk + 67200, 0x28F00u);
    drawMenu(INITIAL_MENU, 0);
    drawMenu(CONFIGURE_MENU, 0);
    drawMenu(DEFINE_GAMEPAD_MENU, 1);
    refreshAllScreen();
    v0 = readEventInMenu(DEFINE_GAMEPAD_MENU);
    v1 = v0;
    result = v0 + 1;
    switch ( result )
    {
      case 1:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 121, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad for accelerate...", 86065);
        refreshAllScreen();
		configuration.accelerateGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[0], aAccelerate_442AD0);
        strcat(defineGamepadMenu_447178[0], gamepadNames_45EAC0[configuration.accelerateGamepad]);
        goto LABEL_40;
      case 2:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 149, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad for brake...", 103985);
        refreshAllScreen();
		configuration.brakeGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[1], aBrake_442A60);
        strcat(defineGamepadMenu_447178[1], gamepadNames_45EAC0[configuration.brakeGamepad]);
        goto LABEL_40;
      case 3:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 177, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad for left steer...", 121905);
        refreshAllScreen();
		configuration.leftSteeringGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[2], aSteerLeft_442A4C);
        strcat(defineGamepadMenu_447178[2], gamepadNames_45EAC0[configuration.leftSteeringGamepad]);
        goto LABEL_40;
      case 4:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 205, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad for right steer...", 139825);
        refreshAllScreen();
		configuration.rightSteeringGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[3], aSteerRight_442A34);
        strcat(defineGamepadMenu_447178[3], gamepadNames_45EAC0[configuration.rightSteeringGamepad]);
        goto LABEL_40;
      case 5:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 233, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad for turbo boost...", 157745);
        refreshAllScreen();
		configuration.turboGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[4], aTurboBoost_442A18);
        strcat(defineGamepadMenu_447178[4], gamepadNames_45EAC0[configuration.turboGamepad]);
        goto LABEL_40;
      case 6:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 261, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad  for machine gun...", 175665);
        refreshAllScreen();
		configuration.gunGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[5], aMachineGun_4429FC);
        strcat(defineGamepadMenu_447178[5], gamepadNames_45EAC0[configuration.gunGamepad]);
        goto LABEL_40;
      case 7:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_GAMEPAD_MENU, 0);
        createPopup(295, 289, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Move gamepad for drop mine...", 193585);
        refreshAllScreen();
		configuration.mineGamepad = (unsigned __int8)sub_42CBF0();
        sub_418090();
        eventDetected();
        strcpy(defineGamepadMenu_447178[6], aDropMine_4429E0);
        strcat(defineGamepadMenu_447178[6], gamepadNames_45EAC0[configuration.mineGamepad]);
        goto LABEL_40;
      case 0:
      case 8:
        result = sub_428740();
        if ( result == 1 )
          continue;
        if ( v1 != 7 )
          goto LABEL_40;
        result = 0;
        dword_4457E8 = 0;
        if ( !menuActive_4457F0 [72] )
        {
          do
          {
            if ( result >= dword_4457D0 - 1 )
              result = 0;
            else
              ++result;
          }
          while ( !menuActive_4457F0[72+result] );
          dword_4457E8 = result;
        }
        return result;
      default:
LABEL_40:
        if ( v1 != -1 )
          continue;
        return result;
    }
  }
}
// 4457D0: using guessed type int dword_4457D0;
// 4457E8: using guessed type int dword_4457E8;
// 4458B0: using guessed type char letterSpacing_4458B0;
// 45EEA0: using guessed type int configuration.leftSteeringGamepad;
// 461294: using guessed type int configuration.accelerateGamepad;
// 461F14: using guessed type int configuration.brakeGamepad;
// 462CFC: using guessed type int configuration.gunGamepad;
// 462D6C: using guessed type int configuration.rightSteeringGamepad;
// 463CA4: using guessed type int configuration.mineGamepad;
// 463D8C: using guessed type int configuration.turboGamepad;

//----- (004309A0) --------------------------------------------------------
int showAdjustOptions()
{
  int v0; // ebp@1
  signed int v1; // eax@3
  char v2; // bl@4
  char v3; // al@8
  signed int v4; // edx@23
  char *v5; // edi@24
  int v8; // eax@27
  char v9; // bl@29
  char v10; // al@33
  signed int v11; // edx@46
  char *v12; // edi@47
  int v15; // eax@50
  int v17; // eax@62
  int v18; // [sp+10h] [bp-14h]@1
  int v19; // [sp+14h] [bp-10h]@1
  char DstBuf[12]; // [sp+18h] [bp-Ch]@25

  v18 = configuration.musicVolume / 512;
  v0 = configuration.effectsVolume / 512;
  v19 = configuration.effectsVolume / 512;
LABEL_2:
  while ( !dword_456B9C )
  {
    memcpy((char *)screenBuffer + 53760, (char *)graphicsGeneral.menubg5Bpk + 53760, 0x2C380u);
    drawMenu(INITIAL_MENU, 0);
    drawMenu(CONFIGURE_MENU, 1);
    refreshAllScreen();
    v1 = readEventInMenu(CONFIGURE_MENU);
    switch ( v1 )
    {
      case 0:
        drawMenu(CONFIGURE_MENU, 0);
        createPopup(214, 218, 330, 70, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Adjust music volume:", 144864);
        drawImageWithPosition((int)slidmus2Bpk, 172, 24, (int)((char *)screenBuffer + 160314));
        refreshAllScreen();
        v2 = 0;
        do
        {
          if ( v2 == -100 || v2 == 1 || dword_456B9C )
            break;
          v3 = eventDetected();
          v2 = v3;
          switch ( v3 )
          {
            case -53:
              if ( v18 > 0 )
                v18 -= 2;
              break;
            case KEY_LEFT:
              if ( v18 > 0 )
                v18 -= 2;
              break;
            case -51:
              if ( v18 < 128 )
                v18 += 2;
              break;
            case KEY_RIGHT:
              if ( v18 < 128 )
                v18 += 2;
              break;
            default:
              //if ( v3 == 59 && isMultiplayerGame )
              //  multiplayer_sub_42CCF0();
              break;
          }
          v4 = 0;
          do
          {
            v5 = (char *)screenBuffer + v4 + 157660;
            memset(v5, 0xC4u, 0x110u);
            v5 += 272;
            *(_WORD *)v5 = -15164;
            v4 += 640;
            v5[2] = -60;
          }
          while ( v4 < 19200 );
          drawImageWithPosition((int)slidmus2Bpk, 172, 24, (int)((char *)screenBuffer + 160314));
          drawImageWithPosition((int)volcur2Bpk, 10, 24, (int)((char *)screenBuffer + v18 + 160329));
          drawKeyCursor(v18 + 160327, (char *)screenBuffer + v18 + 160327, 0xEu, 24);

          
          SDL_itoa((unsigned __int64)((double)v18 * 0.78125), DstBuf, 10);
          strcat(DstBuf, "%");
          v8 = getBoxBigTextOffset(DstBuf);
          drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, DstBuf, 157109 - v8);
          drawKeyCursor(157024, (char *)screenBuffer + 157024, 0x78u, 32);
          musicSetmusicVolume(v18 << 9);
          refreshAndCheckConnection_42A570();
        }
        while ( v2 != 28 );
        configuration.musicVolume = v18 << 9;
        loadMenuSoundEffect(1u, 22, 0, configuration.effectsVolume, dword_4451A0);
        goto LABEL_2;
      case 1:
        drawMenu(CONFIGURE_MENU, 0);
        createPopup(214, 218, 330, 70, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Adjust effect volume:", 144864);
        drawImageWithPosition((int)slidmus2Bpk, 172, 24, (int)((char *)screenBuffer + 160314));
        refreshAllScreen();
        v9 = 0;
        do
        {
          if ( v9 == -100 || v9 == 1 || dword_456B9C )
            break;
          v10 = eventDetected();
          v9 = v10;
          if ( v10 == -53 )
          {
            if ( v0 > 0 )
            {
              v0 -= 2;
              v19 = v0;
            }
          }
          else if ( v10 == KEY_LEFT)
          {
            if ( v0 > 0 )
            {
              v0 -= 2;
              v19 = v0;
            }
          }
          else if ( v10 != -51 && v10 != KEY_RIGHT)
          {
            //if ( v10 == 59 && isMultiplayerGame )
            //  multiplayer_sub_42CCF0();
          }
          else if ( v0 < 128 )
          {
            v0 += 2;
            v19 = v0;
          }
          v11 = 0;
          do
          {
            v12 = (char *)screenBuffer + v11 + 157660;
            memset(v12, 0xC4u, 0x110u);
            v12 += 272;
            *(_WORD *)v12 = -15164;
            v11 += 640;
            v12[2] = -60;
          }
          while ( v11 < 19200 );
          drawImageWithPosition((int)slidmus2Bpk, 172, 24, (int)((char *)screenBuffer + 160314));
          drawImageWithPosition((int)volcur2Bpk, 10, 24, (int)((char *)screenBuffer + v0 + 160329));
          drawKeyCursor(v0 + 160327, (char *)screenBuffer + v0 + 160327, 0xEu, 24);
          SDL_itoa((unsigned __int64)((double)v19 * 0.78125),DstBuf, 10);
          strcat(DstBuf, "%");
          v15 = getBoxBigTextOffset(DstBuf);
          drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, DstBuf, 157109 - v15);
          drawKeyCursor(157024, (char *)screenBuffer + 157024, 0x78u, 32);
          musicSetVolume(v0 << 9);
          refreshAndCheckConnection_42A570();
        }
        while ( v9 != 28 );
        configuration.effectsVolume = v0 << 9;
        loadMenuSoundEffect(1u, 22, 0, configuration.effectsVolume, dword_4451A0);
        goto LABEL_2;
      case 2:
        redefineControls();
        goto LABEL_2;
      case 3:
        defineGamepadJoystickMenu();
        goto LABEL_2;
      case 4:
        if ( configuration.useJoystick )
        {
          configuration.useJoystick = 0;
LABEL_58:
          memcpy(aGamepadDisable, "Gamepad/Joystick Disabled", 0x1Au);
          goto LABEL_2;
        }
        configuration.useJoystick = 1;
        SDLConfigureJoystick();
        if ( !configuration.useJoystick )
          GamepadNotFoundPopup_41E3B0();
        configJoystick();
        memcpy(aGamepadDisable, "Gamepad/Joystick Enabled", 0x19u);
        if ( !configuration.useJoystick )
          goto LABEL_58;
        break;
      case PREVIOUS_MENU:
        v17 = 0;
        dword_44575C = 0;
        if ( !menuActive_4457F0[27] )
        {
          do
          {
            if ( v17 >= dword_445744 - 1 )
              v17 = 0;
            else
              ++v17;
          }
          while ( !menuActive_4457F0[27+v17] );
          dword_44575C = v17;
        }
        return saveConfiguration();
      default:
        if ( v1 != -1 )
          goto LABEL_2;
        return saveConfiguration();
    }
  }
  return saveConfiguration();
}

//----- (0042FB00) --------------------------------------------------------
signed int redefineControls()
{
  signed int v0; // eax@2
  signed int v1; // ebx@2
  signed int result; // eax@2

  sub_41CA40();
  while ( 2 )
  {
    memcpy((char *)screenBuffer + 67200, (char *)graphicsGeneral.menubg5Bpk + 67200, 0x28F00u);
    drawMenu(INITIAL_MENU, 0);
    drawMenu(CONFIGURE_MENU, 0);
    drawMenu(DEFINE_KEYBOARD_MENU, 1);
    refreshAllScreen();
    v0 = readEventInMenu(DEFINE_KEYBOARD_MENU);
    v1 = v0;
    result = v0 + 1;
    switch ( result )
    {
      case 1:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 121, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for accelerate...", 86065);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.accelerateKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.accelerateKey);
        }
        while (configuration.accelerateKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[0], aAccelerate_442AD0);
        strcat(defineKeyboardMenu_446DF4[0], keyNames_462DA0[configuration.accelerateKey]);
        goto LABEL_69;
      case 2:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 149, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for brake...", 103985);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.brakeKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.brakeKey );
        }
        while (configuration.brakeKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[1], aBrake_442A60);
        strcat(defineKeyboardMenu_446DF4[1], keyNames_462DA0[configuration.brakeKey]);
        goto LABEL_69;
      case 3:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 177, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for left steer...", 121905);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.leftSteeringKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.leftSteeringKey);
        }
        while (configuration.leftSteeringKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[2], aSteerLeft_442A4C);
        strcat(defineKeyboardMenu_446DF4[2], keyNames_462DA0[configuration.leftSteeringKey]);
        goto LABEL_69;
      case 4:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 205, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for right steer...", 139825);
        refreshAllScreen();
        do
        {
          do
          {
			configuration.rightSteeringKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.rightSteeringKey);
        }
        while (configuration.rightSteeringKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[3], aSteerRight_442A34);
        strcat(defineKeyboardMenu_446DF4[3], keyNames_462DA0[configuration.rightSteeringKey]);
        goto LABEL_69;
      case 5:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 233, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for turbo boost...", 157745);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.turboKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.turboKey);
        }
        while (configuration.turboKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[4], aTurboBoost_442A18);
        strcat(defineKeyboardMenu_446DF4[4], keyNames_462DA0[configuration.turboKey]);
        goto LABEL_69;
      case 6:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 261, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for machine gun...", 175665);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.gunKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.gunKey);
        }
        while (configuration.gunKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[5], aMachineGun_4429FC);
        strcat(defineKeyboardMenu_446DF4[5], keyNames_462DA0[configuration.gunKey]);
        goto LABEL_69;
      case 7:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 289, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for drop mine...", 193585);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.mineKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.mineKey);
        }
        while (configuration.mineKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[6], aDropMine_4429E0);
        strcat(defineKeyboardMenu_446DF4[6], keyNames_462DA0[configuration.mineKey]);
        goto LABEL_69;
      case 8:
        drawMenu(INITIAL_MENU, 0);
        drawMenu(CONFIGURE_MENU, 0);
        drawMenu(DEFINE_KEYBOARD_MENU, 0);
        createPopup(295, 317, 323, 48, 1);
        drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, "Press a key for horn...", 211505);
        refreshAllScreen();
        do
        {
          do
          {
			  configuration.hornKey = (unsigned __int8)eventDetected();
            waitWithRefresh();
          }
          while ( !configuration.hornKey);
        }
        while (configuration.hornKey == 170 );
        sub_418090();
        eventDetected();
        strcpy(defineKeyboardMenu_446DF4[7], aHorn_4429C0);
        strcat(defineKeyboardMenu_446DF4[7], keyNames_462DA0[configuration.hornKey]);
        goto LABEL_69;
      case 0:
      case 9:
        result = sub_4284E0();
        if ( result == 1 )
          continue;
        if ( v1 != 8 )
          goto LABEL_69;
        result = 0;
        dword_4457B0 = 0;
        if ( !menuActive_4457F0[54] )
        {
          do
          {
            if ( result >= dword_445798 - 1 )
              result = 0;
            else
              ++result;
          }
          while ( !menuActive_4457F0[54+result] );
          dword_4457B0 = result;
        }
        return result;
      default:
LABEL_69:
        if ( v1 != -1 )
          continue;
        return result;
    }
  }
}
// 445798: using guessed type int dword_445798;
// 4457B0: using guessed type int dword_4457B0;
// 4458B0: using guessed type char letterSpacing_4458B0;
// 45EA68: using guessed type int configuration.rightSteeringKey;
// 45FBF4: using guessed type int configuration.turboKey;
// 461270: using guessed type int configuration.mineKey;
// 461EA8: using guessed type int configuration.accelerateKey;
// 461FF8: using guessed type int configuration.leftSteeringKey;
// 463CA8: using guessed type int configuration.brakeKey;
// 463CE4: using guessed type int configuration.gunKey;
// 463D18: using guessed type int configuration.hornKey;


//----- (0041CA40) --------------------------------------------------------
void sub_41CA40()
{
  int i;

  strcpy(gamepadNames_45EAC0[(unsigned __int8)byte_456B01], "-           ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultLeftSteeringGamepad], "left        ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultRightSteeringGamepad], "right       ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)byte_44512A], "up          ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultBrakeGamepad], "down        ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultAccelerateGamepad], "button 1    ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultTurboGamepad], "button 2    ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultGunGamepad], "button 3    ");
  strcpy(gamepadNames_45EAC0[(unsigned __int8)configuration.defaultMineGamepad], "button 4    ");
  for ( i = 0; i < 256; ++i )
    strcpy(keyNames_462DA0[i], "UNAVAILABLE ");
  strcpy(keyNames_462DA0[0x01], "esc         ");
  strcpy(keyNames_462DA0[0x02], "1           ");
  strcpy(keyNames_462DA0[0x03], "2           ");
  strcpy(keyNames_462DA0[0x04], "3           ");
  strcpy(keyNames_462DA0[0x05], "4           ");
  strcpy(keyNames_462DA0[0x06], "5           ");
  strcpy(keyNames_462DA0[0x07], "6           ");
  strcpy(keyNames_462DA0[0x08], "7           ");
  strcpy(keyNames_462DA0[0x09], "8           ");
  strcpy(keyNames_462DA0[0x0A], "9           ");
  strcpy(keyNames_462DA0[0x0B], "0           ");
  strcpy(keyNames_462DA0[0x0C], "minus       ");
  strcpy(keyNames_462DA0[0x0D], "equal       ");
  strcpy(keyNames_462DA0[0x0E], "backspace   ");
  strcpy(keyNames_462DA0[0x0F], "tab         ");
  strcpy(keyNames_462DA0[0x10], "q           ");
  strcpy(keyNames_462DA0[0x11], "w           ");
  strcpy(keyNames_462DA0[0x12], "e           ");
  strcpy(keyNames_462DA0[0x13], "r           ");
  strcpy(keyNames_462DA0[0x14], "t           ");
  strcpy(keyNames_462DA0[0x15], "y           ");
  strcpy(keyNames_462DA0[0x16], "u           ");
  strcpy(keyNames_462DA0[0x17], "i           ");
  strcpy(keyNames_462DA0[0x18], "o           ");
  strcpy(keyNames_462DA0[0x19], "p           ");
  strcpy(keyNames_462DA0[0x1A], "left bracket");
  strcpy(keyNames_462DA0[0x1B], "right bracket");
  strcpy(keyNames_462DA0[0x1C], "enter       ");
  strcpy(keyNames_462DA0[0x1D], "left control");
  strcpy(keyNames_462DA0[0x1E], "a           ");
  strcpy(keyNames_462DA0[0x1F], "s           ");
  strcpy(keyNames_462DA0[0x20], "d           ");
  strcpy(keyNames_462DA0[0x21], "f           ");
  strcpy(keyNames_462DA0[0x22], "g           ");
  strcpy(keyNames_462DA0[0x23], "h           ");
  strcpy(keyNames_462DA0[0x24], "j           ");
  strcpy(keyNames_462DA0[0x25], "k           ");
  strcpy(keyNames_462DA0[0x26], "l           ");
  strcpy(keyNames_462DA0[0x27], "semicolon   ");
  strcpy(keyNames_462DA0[0x28], "tick        ");
  strcpy(keyNames_462DA0[0x29], "apostrophe  ");
  strcpy(keyNames_462DA0[0x2A], "left shift  ");
  strcpy(keyNames_462DA0[0x2B], "backslash   ");
  strcpy(keyNames_462DA0[0x2C], "z           ");
  strcpy(keyNames_462DA0[0x2D], "x           ");
  strcpy(keyNames_462DA0[0x2E], "c           ");
  strcpy(keyNames_462DA0[0x2F], "v           ");
  strcpy(keyNames_462DA0[0x30], "b           ");
  strcpy(keyNames_462DA0[0x31], "n           ");
  strcpy(keyNames_462DA0[0x32], "m           ");
  strcpy(keyNames_462DA0[0x33], "comma       ");
  strcpy(keyNames_462DA0[0x34], "period      ");
  strcpy(keyNames_462DA0[0x35], "slash       ");
  strcpy(keyNames_462DA0[0x36], "right shift ");
  strcpy(keyNames_462DA0[0x37], "keypad-star ");
  strcpy(keyNames_462DA0[0x38], "left alt    ");
  strcpy(keyNames_462DA0[0x39], "space       ");
  strcpy(keyNames_462DA0[0x3A], "capslock    ");
  strcpy(keyNames_462DA0[0x3B], "f1          ");
  strcpy(keyNames_462DA0[0x3C], "f2          ");
  strcpy(keyNames_462DA0[0x3D], "f3          ");
  strcpy(keyNames_462DA0[0x3E], "f4          ");
  strcpy(keyNames_462DA0[0x3F], "f5          ");
  strcpy(keyNames_462DA0[0x40], "f6          ");
  strcpy(keyNames_462DA0[0x41], "f7          ");
  strcpy(keyNames_462DA0[0x42], "f8          ");
  strcpy(keyNames_462DA0[0x43], "f9          ");
  strcpy(keyNames_462DA0[0x44], "f10         ");
  strcpy(keyNames_462DA0[0x45], "numlock     ");
  strcpy(keyNames_462DA0[0x46], "scrolllock  ");
  strcpy(keyNames_462DA0[0x47], "keypad-7    ");
  strcpy(keyNames_462DA0[0x48], "keypad-8    ");
  strcpy(keyNames_462DA0[0x49], "keypad-9    ");
  strcpy(keyNames_462DA0[0x4A], "keypad-minus");
  strcpy(keyNames_462DA0[0x4B], "keypad-4    ");
  strcpy(keyNames_462DA0[0x4C], "keypad-5    ");
  strcpy(keyNames_462DA0[0x4D], "keypad-6    ");
  strcpy(keyNames_462DA0[0x4E], "keypad-plus ");
  strcpy(keyNames_462DA0[0x4F], "keypad-1    ");
  strcpy(keyNames_462DA0[0x50], "keypad-2    ");
  strcpy(keyNames_462DA0[0x51], "keypad-3    ");
  strcpy(keyNames_462DA0[0x52], "keypad-0    ");
  strcpy(keyNames_462DA0[0x53], "keypad-del  ");
  strcpy(keyNames_462DA0[0x54], "sysreq      ");
  strcpy(keyNames_462DA0[0x57], "f11         ");
  strcpy(keyNames_462DA0[0x58], "f12         ");
  strcpy(keyNames_462DA0[0x9C], "keypad-enter");
  strcpy(keyNames_462DA0[0x9D], "right control");
  strcpy(keyNames_462DA0[0xB5], "keypad-slash");
  strcpy(keyNames_462DA0[0xB7], "printscr    ");
  strcpy(keyNames_462DA0[0xB8], "right alt   ");
  strcpy(keyNames_462DA0[0xC7], "home        ");
  strcpy(keyNames_462DA0[0xC8], "up arrow    ");
  strcpy(keyNames_462DA0[0xC9], "page up     ");
  strcpy(keyNames_462DA0[0xCB], "left arrow  ");
  strcpy(keyNames_462DA0[0xCD], "right arrow ");
  strcpy(keyNames_462DA0[0xCF], "end         ");
  strcpy(keyNames_462DA0[0xD0], "down arrow  ");
  strcpy(keyNames_462DA0[0xD1], "page down   ");
  strcpy(keyNames_462DA0[0xD2], "ins         ");
  strcpy(keyNames_462DA0[0xD3], "del         ");
  strcpy(defineKeyboardMenu_446DF4[0], aAccelerate_442AD0);
  strcpy(defineKeyboardMenu_446DF4[1], aBrake_442A60);
  strcpy(defineKeyboardMenu_446DF4[2], aSteerLeft_442A4C);
  strcpy(defineKeyboardMenu_446DF4[3], aSteerRight_442A34);
  strcpy(defineKeyboardMenu_446DF4[4], aTurboBoost_442A18);
  strcpy(defineKeyboardMenu_446DF4[5], aMachineGun_4429FC);
  strcpy(defineKeyboardMenu_446DF4[6], aDropMine_4429E0);
  strcpy(defineKeyboardMenu_446DF4[7], aHorn_4429C0);
  strcat(defineKeyboardMenu_446DF4[0], keyNames_462DA0[configuration.accelerateKey]);
  strcat(defineKeyboardMenu_446DF4[1], keyNames_462DA0[configuration.brakeKey]);
  strcat(defineKeyboardMenu_446DF4[2], keyNames_462DA0[configuration.leftSteeringKey]);
  strcat(defineKeyboardMenu_446DF4[3], keyNames_462DA0[configuration.rightSteeringKey]);
  strcat(defineKeyboardMenu_446DF4[4], keyNames_462DA0[configuration.turboKey]);
  strcat(defineKeyboardMenu_446DF4[5], keyNames_462DA0[configuration.gunKey]);
  strcat(defineKeyboardMenu_446DF4[6], keyNames_462DA0[configuration.mineKey]);
  strcat(defineKeyboardMenu_446DF4[7], keyNames_462DA0[configuration.hornKey]);
  strcpy(defineGamepadMenu_447178[0], aAccelerate_442AD0);
  strcpy(defineGamepadMenu_447178[1], aBrake_442A60);
  strcpy(defineGamepadMenu_447178[2], aSteerLeft_442A4C);
  strcpy(defineGamepadMenu_447178[3], aSteerRight_442A34);
  strcpy(defineGamepadMenu_447178[4], aTurboBoost_442A18);
  strcpy(defineGamepadMenu_447178[5], aMachineGun_4429FC);
  strcpy(defineGamepadMenu_447178[6], aDropMine_4429E0);
  strcat(defineGamepadMenu_447178[0], gamepadNames_45EAC0[configuration.accelerateGamepad]);
  strcat(defineGamepadMenu_447178[1], gamepadNames_45EAC0[configuration.brakeGamepad]);
  strcat(defineGamepadMenu_447178[2], gamepadNames_45EAC0[configuration.leftSteeringGamepad]);
  strcat(defineGamepadMenu_447178[3], gamepadNames_45EAC0[configuration.rightSteeringGamepad]);
  strcat(defineGamepadMenu_447178[4], gamepadNames_45EAC0[configuration.turboGamepad]);
  strcat(defineGamepadMenu_447178[5], gamepadNames_45EAC0[configuration.gunGamepad]);
  strcat(defineGamepadMenu_447178[6], gamepadNames_45EAC0[configuration.mineGamepad]);
}

//----- (0041E3B0) --------------------------------------------------------
char GamepadNotFoundPopup_41E3B0()
{
  loadMenuSoundEffect(1u, 29, 0, configuration.effectsVolume, dword_4451A4);
  memcpy((char *)screenBuffer + 67200, (char *)graphicsGeneral.menubg5Bpk + 67200, 0x28F00u);
  drawMenu(INITIAL_MENU, 0);
  drawMenu(CONFIGURE_MENU, 0);
  createPopup(28, 198, 595, 86, 1);
  drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, "Gamepad not detected!", 133260);
  drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, getLanguageEntry("Press any key to continue."), 153697);
  refreshAllScreen();
  eventDetected();
  sub_418090();
  while ( !eventDetected() )
    waitWithRefresh();
  eventDetected();
  return sub_418090();
}
// 4451A4: using guessed type int dword_4451A4;
// 45DC18: using guessed type int configuration.effectsVolume;

//----- (004284E0) --------------------------------------------------------
signed int sub_4284E0()
{
  char *v0; // edx@1
  signed int v1; // ebp@1
  int v2; // eax@2
  signed int result; // eax@41
  int v4; // eax@42
  char v5; // [sp+13h] [bp-39h]@1
  char v6[15]; // [sp+14h] [bp-38h]@1
  char v21[40]; // [sp+24h] [bp-28h]@42

  v6[0] = 25;
  v6[1] = 15;
  v6[2] = 59;
  v6[3] = 60;
  v6[4] = 61;
  v6[5] = 62;
  v6[6] = 63;
  v6[7] = 64;
  v6[8] = 65;
  v6[9] = 66;
  v6[10] = 67;
  v6[11] = 68;
  v6[12] = 87;
  v6[13] = 88;
  v6[14] = 1;
  v5 = 0;
  v0 = v6;
  v1 = 15;
  do
  {
    v2 = (unsigned __int8)*v0;
    if (configuration.accelerateKey == v2
      || configuration.brakeKey == v2
      || configuration.leftSteeringKey == v2
      || configuration.rightSteeringKey == v2
      || configuration.turboKey == v2
      || configuration.gunKey == v2
      || configuration.mineKey == v2
      || configuration.hornKey == v2 )
      v5 = 1;
    ++v0;
    --v1;
  }
  while ( v1 );
  if (configuration.accelerateKey == configuration.brakeKey
    || configuration.accelerateKey == configuration.leftSteeringKey
    || configuration.accelerateKey == configuration.rightSteeringKey
    || configuration.accelerateKey == configuration.turboKey
    || configuration.accelerateKey == configuration.gunKey
    || configuration.accelerateKey == configuration.mineKey
    || configuration.accelerateKey == configuration.hornKey
    || configuration.brakeKey == configuration.leftSteeringKey
    || configuration.brakeKey == configuration.rightSteeringKey
    || configuration.brakeKey == configuration.turboKey
    || configuration.brakeKey == configuration.gunKey
    || configuration.brakeKey == configuration.mineKey
    || configuration.brakeKey == configuration.hornKey
    || configuration.leftSteeringKey == configuration.rightSteeringKey
    || configuration.leftSteeringKey == configuration.turboKey
    || configuration.leftSteeringKey == configuration.gunKey
    || configuration.leftSteeringKey == configuration.mineKey
    || configuration.leftSteeringKey == configuration.hornKey
    || configuration.rightSteeringKey == configuration.turboKey
    || configuration.rightSteeringKey == configuration.gunKey
    || configuration.rightSteeringKey == configuration.mineKey
    || configuration.rightSteeringKey == configuration.hornKey
    || configuration.turboKey == configuration.gunKey
    || configuration.turboKey == configuration.mineKey
    || configuration.turboKey == configuration.hornKey
    || configuration.gunKey == configuration.mineKey
    || configuration.gunKey == configuration.hornKey
    || configuration.mineKey == configuration.hornKey
    || v5 == 1 )
  {
    memcpy(dword_461ED8, screenBuffer, 0x4B000u);
    createPopup(26, 194, 595, 86, 1);
    memcpy(v21, "Invalid key configuration!", 0x1Bu);
    v4 = getBigTextMidSize(v21);
    drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, v21, 130242 - v4);
    drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, "Press any key to re-enter.", 150495);
    refreshAllScreen();
    loadMenuSoundEffect(1u, 29, 0, configuration.effectsVolume, dword_4451A4);
    eventDetected();
    sub_418090();
    while ( !eventDetected() )
      waitWithRefresh();
    eventDetected();
    sub_418090();
    memcpy(screenBuffer, dword_461ED8, 0x4B000u);
    refreshAllScreen();
    result = 1;
  }
  else
  {
    result = 0;
  }
  return result;
}
// 4451A4: using guessed type int dword_4451A4;
// 45DC18: using guessed type int configuration.effectsVolume;
// 45EA68: using guessed type int configuration.rightSteeringKey;
// 45FBF4: using guessed type int configuration.turboKey;
// 461270: using guessed type int configuration.mineKey;
// 461EA8: using guessed type int configuration.accelerateKey;
// 461FF8: using guessed type int configuration.leftSteeringKey;
// 463CA8: using guessed type int configuration.brakeKey;
// 463CE4: using guessed type int configuration.gunKey;
// 463D18: using guessed type int configuration.hornKe;

//----- (00428740) --------------------------------------------------------
signed int sub_428740()
{
  int v0; // ebp@1
  char v1; // bl@1
  int v2; // eax@15
  int v3; // ecx@24
  int v4; // eax@40
  signed int result; // eax@42
  char v6[40]; // [sp+10h] [bp-28h]@40

  v0 = configuration.turboGamepad;
  v1 = 0;
  if (configuration.accelerateGamepad == (unsigned __int8)byte_456B01 )
    goto LABEL_11;
  if (configuration.accelerateGamepad != configuration.brakeGamepad
    && configuration.accelerateGamepad != configuration.leftSteeringGamepad
    && configuration.accelerateGamepad != configuration.rightSteeringGamepad
    && configuration.accelerateGamepad != configuration.turboGamepad)
  {
    if (configuration.accelerateGamepad != configuration.gunGamepad && configuration.accelerateGamepad != configuration.mineGamepad)
    {
      v0 = configuration.turboGamepad;
      goto LABEL_11;
    }
    v0 = configuration.turboGamepad;
  }
  v1 = 1;
LABEL_11:
  if (configuration.brakeGamepad != (unsigned __int8)byte_456B01 )
  {
    if (configuration.brakeGamepad == configuration.leftSteeringGamepad || configuration.brakeGamepad == configuration.rightSteeringGamepad || configuration.brakeGamepad == v0 )
      goto LABEL_46;
    v2 = configuration.gunGamepad;
    if (configuration.brakeGamepad == configuration.gunGamepad)
    {
LABEL_18:
      v1 = 1;
      goto LABEL_20;
    }
    if (configuration.brakeGamepad == configuration.mineGamepad)
    {
LABEL_46:
      v2 = configuration.gunGamepad;
      goto LABEL_18;
    }
  }
  v2 = configuration.gunGamepad;
LABEL_20:
  if (configuration.leftSteeringGamepad == (unsigned __int8)byte_456B01 )
  {
    v3 = configuration.mineGamepad;
  }
  else if (configuration.leftSteeringGamepad == configuration.rightSteeringGamepad || configuration.leftSteeringGamepad == v0 || configuration.leftSteeringGamepad == v2 )
  {
    v3 = configuration.mineGamepad;
    v1 = 1;
  }
  else
  {
    v3 = configuration.mineGamepad;
    if (configuration.leftSteeringGamepad == configuration.mineGamepad)
      v1 = 1;
  }
  if (configuration.rightSteeringGamepad != (unsigned __int8)byte_456B01 && (configuration.rightSteeringGamepad == v0 || configuration.rightSteeringGamepad == v2 || configuration.rightSteeringGamepad == v3) )
    v1 = 1;
  if ( v0 != (unsigned __int8)byte_456B01 && (v0 == v2 || v0 == v3) )
    v1 = 1;
  if ( (v2 == (unsigned __int8)byte_456B01 || v2 != v3) && v1 != 1 )
  {
    result = 0;
  }
  else
  {
    memcpy(dword_461ED8, screenBuffer, 0x4B000u);
    createPopup(26, 194, 595, 86, 1);
    memcpy(v6, "Invalid gamepad configuration!", 0x1Fu);
    v4 = getBigTextMidSize(v6);
    drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, v6, 130242 - v4);
    drawTextWithFont((int)graphicsGeneral.fbig3aBpk, (int)&bigLetterSpacing_445848, "Press any key to re-enter.", 150495);
    refreshAllScreen();
    loadMenuSoundEffect(1u, 29, 0, configuration.effectsVolume, dword_4451A4);
    eventDetected();
    sub_418090();
    while ( !eventDetected() )
      waitWithRefresh();
    eventDetected();
    sub_418090();
    memcpy(screenBuffer, dword_461ED8, 0x4B000u);
    refreshAllScreen();
    result = 1;
  }
  return result;
}

//----- (0042CBF0) --------------------------------------------------------
char sub_42CBF0()
{
  char v0; // bl@1
  signed int v1; // esi@1
  char v2; // al@20
  char result; // al@25

  v0 = -1;
  byte_456B00 = 1;
  v1 = 0;
  do
  {
    refreshAndCheckConnection_42A570();
    if ( configuration.useJoystick > 0 )
    {
      SDLConfigureJoystick();
      if ( v1 > 15 )
      {
        if ( joystick_x_axis_4A7A44 < joystick_x_axis_default_4AA3E0 - 50 )
          v0 = configuration.defaultLeftSteeringGamepad;
        if ( joystick_x_axis_4A7A44 > joystick_x_axis_default_4AA3E0 + 50 )
          v0 = configuration.defaultRightSteeringGamepad;
        if ( joystick_y_axis_4A9EB8 < joystick_y_axis_default_4A9EA0 - 50 )
          v0 = byte_44512A;
        if ( joystick_y_axis_4A9EB8 > joystick_y_axis_default_4A9EA0 + 50 )
          v0 = configuration.defaultBrakeGamepad;
        if ( byte_463E00[(unsigned __int8)configuration.defaultAccelerateGamepad] )
          v0 = configuration.defaultAccelerateGamepad;
        if ( byte_463E00[(unsigned __int8)configuration.defaultTurboGamepad] )
          v0 = configuration.defaultTurboGamepad;
        if ( byte_463E00[(unsigned __int8)configuration.defaultGunGamepad] )
          v0 = configuration.defaultGunGamepad;
        if ( byte_463E00[(unsigned __int8)configuration.defaultMineGamepad] )
          v0 = configuration.defaultMineGamepad;
      }
    }
    v2 = eventDetected();
    if ( v2 == 28 || v2 == -100 || v2 == 1 )
      v0 = byte_456B01;
    ++v1;
  }
  while ( v0 == -1 );
  result = v0;
  byte_456B00 = 0;
  return result;
}
