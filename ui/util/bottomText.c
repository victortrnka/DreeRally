#include "bottomText.h"

#include "../../graphics.h"
#include "../../imageUtil.h"
#include "../../dr.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
//----- (0041E810) --------------------------------------------------------
// DreeRally footer: the original draws the six message rows of
// bottomMenuText here (see the 0.4.x note in doc/KNOWN-ISSUES.md).
char drawBottomMenuText()
{
  signed int v0; // eax@1
  char *v1; // esi@2
  char *v2; // edi@2

  v0 = 243200;
  do
  {
    v1 = (char *)graphicsGeneral.menubg5Bpk + v0;
    v2 = (char *)screenBuffer + v0;
    v0 += 640;
    memcpy(v2, v1, 0x280u);
  }
  while ( v0 < 300160 );
  drawTextWithFont((int)graphicsGeneral.fsma3bBpk, (int)&letterSpacing_4458B0, "         Welcome to DreeRally - Windows Version 0.4", 640 * 395);
  drawTextWithFont((int)graphicsGeneral.fsma3bBpk, (int)&letterSpacing_4458B0, "           Follow us on https://www.dreerally.com", 640 * 410);
  drawTextWithFont((int)graphicsGeneral.fsma3bBpk, (int)&letterSpacing_4458B0, "  Use arrow keys to change selection and press enter to confirm.", 640 * 425);
  return 0;
}
// 4458B0: using guessed type char letterSpacing_4458B0;
