#pragma once
#include <stdint.h>
#include <stdbool.h>
void display_init(void);
uint32_t display_game_speed(void);
void display_sd_speed(void);
void display_clear(uint16_t color);
void display_text(int x, int y, const char *text, uint16_t color, uint16_t bg);
void display_frame(const uint16_t *pixels);
void display_status(unsigned lcd, unsigned emu, unsigned drops);
unsigned display_width(void);
unsigned display_height(void);
/* UI-only operations, used exclusively while the game worker is stopped. */
void display_ui_begin(unsigned,unsigned,unsigned,unsigned);
void display_ui_row(const uint8_t *,unsigned);
void display_ui_end(void);
void display_rect(unsigned,unsigned,unsigned,unsigned,uint16_t);
