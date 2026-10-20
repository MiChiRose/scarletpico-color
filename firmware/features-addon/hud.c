/* Only the display worker's HUD call changes. Its original completed-transfer
 * counter, cadence, rendering, scale and pacing remain byte-for-byte intact. */
#include "features.h"
extern void original_display_draw_text(unsigned,unsigned,const char *,uint16_t,uint16_t,unsigned);

void features_draw_fps(unsigned lcd_fps,unsigned emulated_fps,unsigned scale) {
 (void)emulated_fps;
 char text[]="LCD\n    FPS";
 if(lcd_fps>999)lcd_fps=999;
 if(lcd_fps>=100)text[4]='0'+lcd_fps/100;
 if(lcd_fps>=10)text[5]='0'+lcd_fps/10%10;
 text[6]='0'+lcd_fps%10;
 if(scale!=5)text[3]=' ';
 /* Original stack-only text renderer: no shared UI scanline buffer on core 1.
  * Fixed-width digits erase the previous value, including 100 -> 9 -> 0.
  * Full-height mode stays in the existing left black rail, clear of the game. */
 original_display_draw_text(8,scale==5?268:310,text,0xffff,0,1);
}
