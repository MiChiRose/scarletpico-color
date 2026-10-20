#pragma once

#include <stdbool.h>
#include <stdint.h>

#define GB_WIDTH  160
#define GB_HEIGHT 144

/* Legacy sizes remain for regression tests; the launcher always uses FIT_HEIGHT. */
typedef enum {
    DISPLAY_FAST = 2, DISPLAY_BALANCED = 3, DISPLAY_LARGE = 4,
    DISPLAY_FIT_HEIGHT = 5
} display_scale_t;
uint16_t *display_default_framebuffer(void);
void display_set_draw_buffer(uint16_t *pixels);
void display_present_frame(const uint16_t *pixels, display_scale_t scale);
/* previous must contain the last completely presented frame. It is updated
 * after transmission. NULL falls back to a full redraw. Returns pixel count. */
unsigned display_present_changed(const uint16_t *pixels, uint16_t *previous, display_scale_t scale);
void display_draw_fps(unsigned lcd_fps, unsigned emulated_fps, display_scale_t scale);
unsigned display_game_width(display_scale_t scale);
unsigned display_game_height(display_scale_t scale);
const char *display_scale_name(display_scale_t scale);

void display_init(void);
void display_bus_init(void);
void display_select_bus(void);
/* Stopped/idle SPI only. 25/50 MHz exceed the LCD datasheet, test opt-in only. */
bool display_set_spi_baudrate(unsigned baud);
void display_clear(uint16_t rgb565);
void display_fill_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height,
                       uint16_t rgb565);
void display_draw_text(uint16_t x, uint16_t y, const char *text,
                       uint16_t foreground, uint16_t background, uint8_t scale);
void display_store_line(const uint8_t *pixels, uint8_t line);
void display_store_rgb_line(const uint16_t *pixels, uint8_t line);
void display_present(void);
void display_test_pattern(void);
void display_backlight(bool enabled);
