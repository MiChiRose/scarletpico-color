/* Compile-time validation only; do not compile another emulator core. */
#define PEANUT_GB_HEADER_ONLY
#define PEANUT_FULL_GBC_SUPPORT 1
#define ENABLE_LCD 1
#define ENABLE_SOUND 0
#include "peanut_gb.h"
#include <stddef.h>
_Static_assert(sizeof(struct gb_s)==0xc324,"Pinned core layout changed");
_Static_assert(offsetof(struct gb_s,display.lcd_draw_line)==0xc1f0,"LCD callback layout");
_Static_assert(offsetof(struct gb_s,direct.priv)==0xc320,"Private pointer layout");
_Static_assert(offsetof(struct gb_s,direct.joypad)==0xc31d,"Joypad layout");
