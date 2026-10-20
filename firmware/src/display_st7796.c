#include "display_st7796.h"

#include <string.h>
#include <stdio.h>

#include "config.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/stdlib.h"

#define LCD_WIDTH   480
#define LCD_HEIGHT  320
#define GAME_H      LCD_HEIGHT
/* Nearest whole-pixel width: 160 * 320 / 144 = 355.56. */
#define GAME_W      ((GB_WIDTH * GAME_H + GB_HEIGHT / 2) / GB_HEIGHT)
#define GAME_X      ((LCD_WIDTH - GAME_W) / 2)
#define GAME_Y      ((LCD_HEIGHT - GAME_H) / 2)

_Static_assert(GAME_W <= LCD_WIDTH && GAME_H <= LCD_HEIGHT,
               "Scaled Game Boy image must fit the landscape panel");

static uint16_t framebuffer[GB_HEIGHT][GB_WIDTH];
static uint16_t *draw_buffer = &framebuffer[0][0];
static uint8_t scaled_line[GAME_W * 2];
/* Cached nearest-neighbour mapping, reused by every small update window.
 * RP2040 has no integer divide instruction; do not divide per window/pixel. */
static uint8_t scale_xmap[GAME_W], scale_ymap[GAME_H];
static display_scale_t mapped_scale;
static unsigned lcd_spi_baud_hz = LCD_SPI_BAUD_HZ;
static const uint16_t dmg_palette[4] = {0xD7E9, 0x8D66, 0x4323, 0x10C1};

/* Compact 5x7 font: space, punctuation, 0-9 and A-Z. Columns are LSB-first. */
static const uint8_t font_digits[10][5] = {
    {0x3e,0x51,0x49,0x45,0x3e}, {0x00,0x42,0x7f,0x40,0x00},
    {0x42,0x61,0x51,0x49,0x46}, {0x21,0x41,0x45,0x4b,0x31},
    {0x18,0x14,0x12,0x7f,0x10}, {0x27,0x45,0x45,0x45,0x39},
    {0x3c,0x4a,0x49,0x49,0x30}, {0x01,0x71,0x09,0x05,0x03},
    {0x36,0x49,0x49,0x49,0x36}, {0x06,0x49,0x49,0x29,0x1e},
};

static const uint8_t font_letters[26][5] = {
    {0x7e,0x11,0x11,0x11,0x7e}, {0x7f,0x49,0x49,0x49,0x36},
    {0x3e,0x41,0x41,0x41,0x22}, {0x7f,0x41,0x41,0x22,0x1c},
    {0x7f,0x49,0x49,0x49,0x41}, {0x7f,0x09,0x09,0x09,0x01},
    {0x3e,0x41,0x49,0x49,0x7a}, {0x7f,0x08,0x08,0x08,0x7f},
    {0x00,0x41,0x7f,0x41,0x00}, {0x20,0x40,0x41,0x3f,0x01},
    {0x7f,0x08,0x14,0x22,0x41}, {0x7f,0x40,0x40,0x40,0x40},
    {0x7f,0x02,0x0c,0x02,0x7f}, {0x7f,0x04,0x08,0x10,0x7f},
    {0x3e,0x41,0x41,0x41,0x3e}, {0x7f,0x09,0x09,0x09,0x06},
    {0x3e,0x41,0x51,0x21,0x5e}, {0x7f,0x09,0x19,0x29,0x46},
    {0x46,0x49,0x49,0x49,0x31}, {0x01,0x01,0x7f,0x01,0x01},
    {0x3f,0x40,0x40,0x40,0x3f}, {0x1f,0x20,0x40,0x20,0x1f},
    {0x3f,0x40,0x38,0x40,0x3f}, {0x63,0x14,0x08,0x14,0x63},
    {0x07,0x08,0x70,0x08,0x07}, {0x61,0x51,0x49,0x45,0x43},
};

static void font_glyph(char c, uint8_t out[5]) {
    memset(out, 0, 5);
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    if (c >= '0' && c <= '9') {
        memcpy(out, font_digits[c - '0'], 5);
    } else if (c >= 'A' && c <= 'Z') {
        memcpy(out, font_letters[c - 'A'], 5);
    } else if (c == '-') {
        out[0] = out[1] = out[2] = out[3] = out[4] = 0x08;
    } else if (c == ':') {
        out[2] = 0x36;
    } else if (c == '.') {
        out[2] = 0x60;
    } else if (c == '/') {
        out[0] = 0x20; out[1] = 0x10; out[2] = 0x08;
        out[3] = 0x04; out[4] = 0x02;
    } else if (c == '_') {
        out[0] = out[1] = out[2] = out[3] = out[4] = 0x40;
    }
}

static void lcd_begin(bool data) {
    gpio_put(PIN_LCD_DC, data);
    gpio_put(PIN_LCD_CS, 0);
    /* Explicit CS/DC setup margin, also at the overclocked CPU rate. */
    sleep_us(1);
}

static void lcd_end(void) {
    /* spi_write_blocking already drains the shifter before returning. */
    sleep_us(1);
    gpio_put(PIN_LCD_CS, 1);
    sleep_us(1);
}

static void lcd_command_data(uint8_t command, const uint8_t *data, size_t size) {
    lcd_begin(false);
    spi_write_blocking(spi0, &command, 1);
    if (size) {
        gpio_put(PIN_LCD_DC, 1);
        sleep_us(1);
        spi_write_blocking(spi0, data, size);
    }
    lcd_end();
}

static void lcd_command(uint8_t command) {
    lcd_command_data(command, NULL, 0);
}

static void lcd_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
    const uint8_t columns[] = {x0 >> 8, x0 & 0xff, x1 >> 8, x1 & 0xff};
    const uint8_t rows[] = {y0 >> 8, y0 & 0xff, y1 >> 8, y1 & 0xff};
    lcd_command_data(0x2A, columns, sizeof columns);
    lcd_command_data(0x2B, rows, sizeof rows);
    lcd_command(0x2C);
}

bool display_set_spi_baudrate(unsigned baud) {
    /* Only the stopped-core launcher may change this, never while a frame is
     * in flight. 25/50 MHz are explicit out-of-spec LCD experiments. */
    if (baud != LCD_SPI_BAUD_HZ && baud != 25000000u && baud != 50000000u) return false;
    lcd_spi_baud_hz = baud;
    return true;
}

void display_select_bus(void) {
    gpio_put(PIN_SD_CS, 1);
    gpio_put(PIN_LCD_CS, 1);
    spi_set_format(spi0, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    spi_set_baudrate(spi0, lcd_spi_baud_hz);
    sleep_us(1);
}

void display_backlight(bool enabled) {
    gpio_put(PIN_LCD_BL, enabled ? 1 : 0);
}

void display_bus_init(void) {
    static bool initialized;
    if (initialized) return;
    gpio_init(PIN_LCD_CS);
    gpio_init(PIN_LCD_DC);
    gpio_init(PIN_LCD_RST);
    gpio_init(PIN_LCD_BL);
    gpio_init(PIN_SD_CS);
    gpio_put(PIN_LCD_CS, 1);
    gpio_put(PIN_SD_CS, 1);
    gpio_set_dir(PIN_LCD_CS, GPIO_OUT);
    gpio_set_dir(PIN_LCD_DC, GPIO_OUT);
    gpio_set_dir(PIN_LCD_RST, GPIO_OUT);
    gpio_set_dir(PIN_LCD_BL, GPIO_OUT);
    gpio_set_dir(PIN_SD_CS, GPIO_OUT);
    gpio_put(PIN_LCD_CS, 1);
    gpio_put(PIN_SD_CS, 1);
    display_backlight(false);

    /* Allow SD to enter SPI mode before the first display transaction. */
    spi_init(spi0, 400000u);
    gpio_set_function(PIN_SPI_CLK, GPIO_FUNC_SPI);
    gpio_set_function(PIN_SPI_MOSI, GPIO_FUNC_SPI);
    gpio_set_function(PIN_SPI_MISO, GPIO_FUNC_SPI);
    gpio_pull_up(PIN_SPI_MISO);
    initialized = true;
}

void display_init(void) {
    display_bus_init();
    display_select_bus();

    gpio_put(PIN_LCD_RST, 0);
    sleep_ms(20);
    gpio_put(PIN_LCD_RST, 1);
    sleep_ms(120);

    lcd_command(0x01);
    sleep_ms(120);
    lcd_command(0x11);
    sleep_ms(120);

    const uint8_t unlock1[] = {0xC3};
    const uint8_t unlock2[] = {0x96};
    const uint8_t madctl[] = {LCD_MADCTL_VALUE};
    const uint8_t pixel_format[] = {0x55};
    const uint8_t inversion[] = {0x01};
    const uint8_t gate[] = {0xC6};
    const uint8_t display_function[] = {0x80, 0x02, 0x3B};
    const uint8_t power1[] = {0x06};
    const uint8_t power2[] = {0xA7};
    const uint8_t vcom[] = {0x18};
    const uint8_t gamma_pos[] = {
        0xF0, 0x09, 0x0B, 0x06, 0x04, 0x15, 0x2F,
        0x54, 0x42, 0x3C, 0x17, 0x14, 0x18, 0x1B
    };
    const uint8_t gamma_neg[] = {
        0xE0, 0x09, 0x0B, 0x06, 0x04, 0x03, 0x2B,
        0x43, 0x42, 0x3B, 0x16, 0x14, 0x17, 0x1B
    };
    const uint8_t lock1[] = {0x3C};
    const uint8_t lock2[] = {0x69};

    lcd_command_data(0xF0, unlock1, sizeof unlock1);
    lcd_command_data(0xF0, unlock2, sizeof unlock2);
    lcd_command_data(0x36, madctl, sizeof madctl);
    lcd_command_data(0x3A, pixel_format, sizeof pixel_format);
    lcd_command_data(0xB4, inversion, sizeof inversion);
    lcd_command_data(0xB7, gate, sizeof gate);
    lcd_command_data(0xB6, display_function, sizeof display_function);
    lcd_command_data(0xC1, power1, sizeof power1);
    lcd_command_data(0xC2, power2, sizeof power2);
    lcd_command_data(0xC5, vcom, sizeof vcom);
    lcd_command_data(0xE0, gamma_pos, sizeof gamma_pos);
    lcd_command_data(0xE1, gamma_neg, sizeof gamma_neg);
    lcd_command_data(0xF0, lock1, sizeof lock1);
    lcd_command_data(0xF0, lock2, sizeof lock2);
    lcd_command(LCD_INVERT_COLORS ? 0x21 : 0x20);
    lcd_command(0x13);
    lcd_command(0x29);
    sleep_ms(50);

    display_clear(0x0000);
    display_backlight(true);
}

void display_clear(uint16_t rgb565) {
    uint8_t chunk[256];
    for (size_t i = 0; i < sizeof chunk; i += 2) {
        chunk[i] = rgb565 >> 8;
        chunk[i + 1] = rgb565 & 0xff;
    }

    display_select_bus();
    lcd_window(0, 0, LCD_WIDTH - 1, LCD_HEIGHT - 1);
    lcd_begin(true);
    size_t remaining = LCD_WIDTH * LCD_HEIGHT * 2u;
    while (remaining) {
        const size_t amount = remaining > sizeof chunk ? sizeof chunk : remaining;
        spi_write_blocking(spi0, chunk, amount);
        remaining -= amount;
    }
    lcd_end();
}

void display_fill_rect(uint16_t x, uint16_t y, uint16_t width, uint16_t height,
                       uint16_t rgb565) {
    if (!width || !height || x >= LCD_WIDTH || y >= LCD_HEIGHT) return;
    if (x + width > LCD_WIDTH) width = LCD_WIDTH - x;
    if (y + height > LCD_HEIGHT) height = LCD_HEIGHT - y;

    uint8_t chunk[256];
    for (size_t i = 0; i < sizeof chunk; i += 2) {
        chunk[i] = rgb565 >> 8;
        chunk[i + 1] = rgb565 & 0xff;
    }
    display_select_bus();
    lcd_window(x, y, x + width - 1, y + height - 1);
    lcd_begin(true);
    size_t remaining = (size_t)width * height * 2u;
    while (remaining) {
        const size_t amount = remaining > sizeof chunk ? sizeof chunk : remaining;
        spi_write_blocking(spi0, chunk, amount);
        remaining -= amount;
    }
    lcd_end();
}

void display_draw_text(uint16_t x, uint16_t y, const char *text,
                       uint16_t foreground, uint16_t background, uint8_t scale) {
    if (!scale) return;
    const unsigned origin_x = x;
    unsigned cursor_x = x, cursor_y = y;
    uint8_t glyph[5];
    uint8_t row_pixels[LCD_WIDTH * 2];
    while (*text) {
        if (*text == '\n') {
            cursor_x = origin_x;
            cursor_y += 9u * scale;
            ++text;
            continue;
        }
        font_glyph(*text++, glyph);
        if (cursor_x < LCD_WIDTH && cursor_y < LCD_HEIGHT) {
            unsigned width = 6u * scale, height = 7u * scale;
            if (width > LCD_WIDTH - cursor_x) width = LCD_WIDTH - cursor_x;
            if (height > LCD_HEIGHT - cursor_y) height = LCD_HEIGHT - cursor_y;
            /* One address window per glyph, not one per font pixel. This also
             * keeps the periodic FPS overlay inexpensive on the shared bus. */
            display_select_bus();
            lcd_window(cursor_x, cursor_y, cursor_x + width - 1, cursor_y + height - 1);
            lcd_begin(true);
            for (unsigned row = 0; row < height; ++row) {
                for (unsigned col = 0; col < width; ++col) {
                    unsigned gx = col / scale;
                    bool set = gx < 5 && ((glyph[gx] >> (row / scale)) & 1u);
                    uint16_t color = set ? foreground : background;
                    row_pixels[col * 2] = color >> 8;
                    row_pixels[col * 2 + 1] = color & 0xff;
                }
                spi_write_blocking(spi0, row_pixels, width * 2);
            }
            lcd_end();
        }
        cursor_x += 6u * scale;
    }
}

void display_store_line(const uint8_t *pixels, uint8_t line) {
    if (line >= GB_HEIGHT) return;
    for (unsigned x = 0; x < GB_WIDTH; ++x) {
        draw_buffer[line * GB_WIDTH + x] = dmg_palette[pixels[x] & 0x03];
    }
}

void display_store_rgb_line(const uint16_t *pixels, uint8_t line) {
    if (line >= GB_HEIGHT) return;
    memcpy(draw_buffer + line * GB_WIDTH, pixels, GB_WIDTH * sizeof *pixels);
}

uint16_t *display_default_framebuffer(void) { return &framebuffer[0][0]; }
void display_set_draw_buffer(uint16_t *pixels) {
    draw_buffer = pixels ? pixels : display_default_framebuffer();
}
static unsigned scale_value(display_scale_t scale) {
    return scale >= DISPLAY_FAST && scale <= DISPLAY_LARGE ? (unsigned)scale : DISPLAY_FAST;
}
unsigned display_game_width(display_scale_t scale) {
    return scale == DISPLAY_FIT_HEIGHT ? GAME_W : GB_WIDTH * scale_value(scale) / 2u;
}
unsigned display_game_height(display_scale_t scale) {
    return scale == DISPLAY_FIT_HEIGHT ? GAME_H : GB_HEIGHT * scale_value(scale) / 2u;
}
const char *display_scale_name(display_scale_t scale) {
    switch (scale) {
        case DISPLAY_FIT_HEIGHT: return "FIT HEIGHT 356X320";
        case DISPLAY_BALANCED: return "BALANCED 240X216";
        case DISPLAY_LARGE: return "LARGE 320X288";
        default: return "FAST 160X144";
    }
}

static void present_region(const uint16_t *pixels, display_scale_t scale,
                           unsigned left, unsigned top, unsigned right, unsigned bottom) {
    const unsigned width = display_game_width(scale), height = display_game_height(scale);
    const unsigned x0 = (LCD_WIDTH - width) / 2u, y0 = (LCD_HEIGHT - height) / 2u;
    if (mapped_scale != scale) {
        for (unsigned x = 0; x < width; ++x) scale_xmap[x] = x * GB_WIDTH / width;
        for (unsigned y = 0; y < height; ++y) scale_ymap[y] = y * GB_HEIGHT / height;
        mapped_scale = scale;
    }
    lcd_window(x0 + left, y0 + top, x0 + right - 1, y0 + bottom - 1);
    lcd_begin(true);
    unsigned previous_row = GB_HEIGHT;
    for (unsigned y = top; y < bottom; ++y) {
        const unsigned row = scale_ymap[y];
        if (row != previous_row) {
            for (unsigned x = left; x < right; ++x) {
                const uint16_t color = pixels[row * GB_WIDTH + scale_xmap[x]];
                scaled_line[(x - left) * 2] = color >> 8;
                scaled_line[(x - left) * 2 + 1] = color & 0xff;
            }
            previous_row = row;
        }
        spi_write_blocking(spi0, scaled_line, (right - left) * 2u);
    }
    lcd_end();
}

void display_present_frame(const uint16_t *pixels, display_scale_t scale) {
    display_select_bus();
    present_region(pixels, scale, 0, 0, display_game_width(scale), display_game_height(scale));
}

/* Tight pixel bounds within 8x8 source tiles. Keep distant moving objects in
 * separate windows, merging neighbours and vertically identical spans. Only
 * two rows of rectangles are needed; there is no heap allocation. */
#define DIRTY_TILE 8u
#define DIRTY_COLS (GB_WIDTH / DIRTY_TILE)
typedef struct { uint8_t left, top, right, bottom; } dirty_rect_t;

static unsigned present_dirty_rect(const uint16_t *pixels, display_scale_t scale,
                                   dirty_rect_t r) {
    const unsigned width = display_game_width(scale), height = display_game_height(scale);
    unsigned left = (r.left * width + GB_WIDTH - 1) / GB_WIDTH;
    unsigned right = (r.right * width + GB_WIDTH - 1) / GB_WIDTH;
    unsigned top = (r.top * height + GB_HEIGHT - 1) / GB_HEIGHT;
    unsigned bottom = (r.bottom * height + GB_HEIGHT - 1) / GB_HEIGHT;
    present_region(pixels, scale, left, top, right, bottom);
    return (right - left) * (bottom - top);
}

unsigned display_present_changed(const uint16_t *pixels, uint16_t *previous, display_scale_t scale) {
    const unsigned width = display_game_width(scale), height = display_game_height(scale);
    if (!previous) { display_present_frame(pixels, scale); return width * height; }
    dirty_rect_t active[DIRTY_COLS], tiles[DIRTY_COLS], next[DIRTY_COLS];
    unsigned active_count = 0, sent = 0;
    bool bus_selected = false;
    for (unsigned band = 0; band < GB_HEIGHT; band += DIRTY_TILE) {
        memset(tiles, 0, sizeof tiles);
        for (unsigned y = band; y < band + DIRTY_TILE; ++y) {
            for (unsigned x = 0; x < GB_WIDTH; ++x) {
                unsigned i = y * GB_WIDTH + x;
                if (pixels[i] == previous[i]) continue;
                dirty_rect_t *r = &tiles[x / DIRTY_TILE];
                if (!r->right) {
                    *r = (dirty_rect_t){x, y, x + 1, y + 1};
                } else {
                    if (x < r->left) r->left = x;
                    if (x + 1 > r->right) r->right = x + 1;
                    r->bottom = y + 1;
                }
            }
        }
        unsigned count = 0;
        for (unsigned t = 0; t < DIRTY_COLS; ++t) {
            dirty_rect_t r = tiles[t];
            if (!r.right) continue;
            /* Sending <=2 unchanged source columns costs less than another
             * command window. Never merge across a large unchanged gap. */
            if (count && r.left <= next[count - 1].right + 2u) {
                dirty_rect_t *p = &next[count - 1];
                p->right = r.right;
                if (r.top < p->top) p->top = r.top;
                if (r.bottom > p->bottom) p->bottom = r.bottom;
            } else next[count++] = r;
        }
        if (!bus_selected && count) { display_select_bus(); bus_selected = true; }
        for (unsigned n = 0; n < count; ++n) {
            for (unsigned a = 0; a < active_count; ++a) {
                if (active[a].right && active[a].left == next[n].left &&
                    active[a].right == next[n].right && active[a].bottom == next[n].top) {
                    next[n].top = active[a].top;
                    active[a].right = 0;
                    break;
                }
            }
        }
        for (unsigned a = 0; a < active_count; ++a)
            if (active[a].right) sent += present_dirty_rect(pixels, scale, active[a]);
        memcpy(active, next, count * sizeof *next);
        active_count = count;
    }
    for (unsigned a = 0; a < active_count; ++a)
        sent += present_dirty_rect(pixels, scale, active[a]);
    if (sent) memcpy(previous, pixels, GB_WIDTH * GB_HEIGHT * sizeof *pixels);
    return sent;
}

void display_draw_fps(unsigned lcd_fps, unsigned emulated_fps, display_scale_t scale) {
    char line[72];
    /* Keep all diagnostics outside the game, including its bottom scanline. */
    if (scale == DISPLAY_FIT_HEIGHT) {
        snprintf(line, sizeof line, "LCD\n%3u FPS", lcd_fps > 999 ? 999 : lcd_fps);
        display_draw_text(8, 268, line, 0xffff, 0, 1);
        snprintf(line, sizeof line, "EMU\n%3u FPS", emulated_fps > 999 ? 999 : emulated_fps);
        display_draw_text(8, 293, line, 0xffff, 0, 1);
    } else {
        snprintf(line, sizeof line, "LCD %2u FPS  EMU %2u FPS  %s      ",
                 lcd_fps, emulated_fps, display_scale_name(scale));
        display_draw_text(8, 310, line, 0xffff, 0, 1);
    }
}

void display_present(void) { display_present_frame(draw_buffer, DISPLAY_FIT_HEIGHT); }

void display_test_pattern(void) {
    display_clear(0x0000);
    /* Full-panel outline and all four corners verify 480x320 addressing. */
    display_fill_rect(0, 0, LCD_WIDTH, 2, 0xffff);
    display_fill_rect(0, LCD_HEIGHT - 2, LCD_WIDTH, 2, 0xffff);
    display_fill_rect(0, 0, 2, LCD_HEIGHT, 0xffff);
    display_fill_rect(LCD_WIDTH - 2, 0, 2, LCD_HEIGHT, 0xffff);
    display_draw_text(8, 8, "TL", 0xffff, 0, 2);
    display_draw_text(LCD_WIDTH - 32, 8, "TR", 0xffff, 0, 2);
    display_draw_text(8, LCD_HEIGHT - 22, "BL", 0xffff, 0, 2);
    display_draw_text(LCD_WIDTH - 32, LCD_HEIGHT - 22, "BR", 0xffff, 0, 2);

    /* Exercise the same indexed-frame -> full-height RGB565 path as Zelda. */
    uint8_t row[GB_WIDTH];
    for (unsigned y = 0; y < GB_HEIGHT; ++y) {
        for (unsigned x = 0; x < GB_WIDTH; ++x) {
            row[x] = (uint8_t)((x >= GB_WIDTH / 2) + 2 * (y >= GB_HEIGHT / 2));
            if (!x || x == GB_WIDTH - 1 || !y || y == GB_HEIGHT - 1)
                row[x] = 0;
        }
        display_store_line(row, y);
    }
    display_present();
    /* Full-height games reach the top/bottom; restore the diagnostic outline. */
    display_fill_rect(0, 0, LCD_WIDTH, 2, 0xffff);
    display_fill_rect(0, LCD_HEIGHT - 2, LCD_WIDTH, 2, 0xffff);
    display_draw_text(GAME_X + 58, GAME_Y + 24, "V10 LCD CHECK", 0xffff, 0, 2);
    display_draw_text(GAME_X + 94, GAME_Y + 48, "356 X 320", 0xffff, 0, 2);
    memset(draw_buffer, 0, sizeof framebuffer);
}
