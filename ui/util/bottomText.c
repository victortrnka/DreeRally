#include "bottomText.h"

#include "../../graphics.h"
#include "../../imageUtil.h"
#include "../../dr.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
//----- (0041E810) --------------------------------------------------------
char drawBottomMenuText()
{
  signed int v0; // eax@1
  char *v1; // esi@2
  char *v2; // edi@2
  int v3; // ebp@3
  const char *v4; // edi@3
  int v5; // esi@3
  char result; // al@4

  v0 = 243200;
  do
  {
    v1 = (char *)graphicsGeneral.menubg5Bpk + v0;
    v2 = (char *)screenBuffer + v0;
    v0 += 640;
    memcpy(v2, v1, 0x280u);
  }
  while ( v0 < 300160 );
  v3 = 16;
  v4 = bottomMenuText[16];
  v5 = 241932;
  do
  {
    result = bottomMenuTextFont[v3];
    if ( !result )
      result = drawTextWithFont((int)graphicsGeneral.fsma3aBpk, (int)&letterSpacing_4458B0, v4, v5);
    if ( bottomMenuTextFont[v3] == 1 )
      result = drawTextWithFont((int)graphicsGeneral.fsma3bBpk, (int)&letterSpacing_4458B0, v4, v5);
    if ( bottomMenuTextFont[v3] == 2 )
      result = drawTextWithFont((int)graphicsGeneral.fsma3cBpk, (int)&letterSpacing_4458B0, v4, v5);
    v5 += 9600;
    ++v3;
    v4 += 150;
  }
  while ( v5 < 299532 );
  return result;
}
// 4458B0: using guessed type char letterSpacing_4458B0;
