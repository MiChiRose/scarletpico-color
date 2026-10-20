#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { UI_A=1, UI_B=2, UI_SELECT=4, UI_START=8, UI_RIGHT=16,
       UI_LEFT=32, UI_UP=64, UI_DOWN=128 };
enum { UI_BG=0x10a3, UI_SURFACE=0x18e5, UI_ACCENT=0xfa6c,
       UI_TEXT=0xf79e, UI_MUTED=0x8433, UI_TEAL=0x4e98, UI_TRACK=0x2967 };
typedef struct { uint8_t language, volume, brightness; } ui_settings_t;
extern ui_settings_t ui_settings;
/* This byte is read by an ABI-preserving hook in the existing PCM mixer. */
extern uint8_t ui_volume;
void ui_init(const uint8_t record[16]);
void ui_make_record(uint8_t record[16]);
void ui_text(unsigned x, unsigned y, const char *s, uint16_t fg, uint16_t bg, unsigned scale, unsigned max_chars);
void ui_header(void);
void ui_settings_draw(void);
bool ui_settings_key(uint8_t key);
void ui_menu_draw(bool force);
void ui_card_error(unsigned code);
void ui_loading(void);
void ui_spinner_tick(uint32_t now);
void ui_invalidate(void);
void ui_legacy_clear(uint16_t color);
void ui_legacy_text(uint16_t x, uint16_t y, const char *text, uint16_t fg, uint16_t bg, uint8_t scale);

/* Platform boundary: shared with native visual/dirty-region tests. */
void ui_rect(unsigned x, unsigned y, unsigned w, unsigned h, uint16_t color);
void ui_pixels_begin(unsigned x, unsigned y, unsigned w, unsigned h);
void ui_pixels_row(const uint8_t *bytes, unsigned size);
void ui_pixels_end(void);
void ui_apply_brightness(unsigned percent);
unsigned ui_game_count(void);
unsigned ui_game_selected(void);
unsigned ui_library_error(void);
const char *ui_game_label(unsigned index);
bool ui_game_color(unsigned index);
unsigned ui_game_status(unsigned index);
