/* Read-only device facts. Draw once: no timer, allocation, SD or flash writes. */
#include "features.h"
#include <string.h>

extern uint32_t clock_get_hz(unsigned clock);

static void mhz_text(char *s,unsigned mhz) {
 if(mhz>999)mhz=999;
 s[0]='0'+mhz/100;s[1]='0'+mhz/10%10;s[2]='0'+mhz%10;
 memcpy(s+3," MHZ",5);
}
void features_about_draw(void) {
 const char *en[]={"FIRMWARE","BOARD","CPU NOW","CPU IN GAMES","DISPLAY","FLASH"};
 const char *ru[]={"ПРОШИВКА","ПЛАТА","CPU СЕЙЧАС","CPU В ИГРАХ","ДИСПЛЕЙ","ФЛЕШ-ПАМЯТЬ"};
 static const unsigned rates[]={125,170,200};
 char actual[8],selected[8];
 /* clk_sys is enum value 5 in this pinned RP2040 SDK. Read its SDK value,
  * not the selected game profile: the library/settings run at 125 MHz. */
 mhz_text(actual,clock_get_hz(5)/1000000u);
 mhz_text(selected,rates[cpu_profile<3?cpu_profile:2]);
 const char *values[]={"v" FEATURES_VERSION,"RP2040-ZERO",actual,selected,"480 X 320","2 MIB"};
 feature_page(feature_tr("ABOUT DEVICE","ОБ УСТРОЙСТВЕ"));
 for(unsigned i=0;i<6;i++) {
  unsigned y=101+i*27;
  ui_text(20,y,ui_settings.language?ru[i]:en[i],UI_TEXT,UI_BG,2,17);
  ui_text(248,y,values[i],i==0?UI_TEAL:UI_TEXT,UI_BG,2,18);
 }
 feature_footer(feature_tr("GB + GBC | 5 SAVE-STATE SLOTS PER GAME","GB + GBC | 5 СЛОТОВ СОХРАНЕНИЙ НА ИГРУ"),feature_tr("B: BACK   170 / 200 MHZ: OVERCLOCK","B: НАЗАД   170 / 200 МГЦ: РАЗГОН"));
}
void feature_about(void) {
 features_about_draw();feature_release();
 for(;;) {
  if(feature_keys()&UI_B) {
   sleep_ms(25);
   if(feature_keys()&UI_B)break;
  }
  sleep_ms(5);
 }
 feature_release();
}
