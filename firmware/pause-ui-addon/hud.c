/* Only presentation changes: the completed LCD-transfer counter is untouched. */
#include "features.h"
extern void original_display_draw_text(unsigned,unsigned,const char *,uint16_t,uint16_t,unsigned);

void pause_ui_draw_fps(unsigned lcd_fps,unsigned emulated_fps,unsigned scale) {
 (void)emulated_fps;(void)scale;
 char text[]="    FPS";
 if(lcd_fps>999)lcd_fps=999;
 if(lcd_fps>=100)text[0]='0'+lcd_fps/100;
 if(lcd_fps>=10)text[1]='0'+lcd_fps/10%10;
 text[2]='0'+lcd_fps%10;
 /* 42x8 pixels, inside the left 62-pixel rail, two pixels from the bottom.
  * Fixed width clears old digits; original stack-only glyph renderer avoids
  * sharing the menu's scanline scratch buffer with the display core. */
 original_display_draw_text(8,310,text,0xffff,0,1);
}
