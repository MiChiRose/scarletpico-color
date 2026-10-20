#include "display_test_bus.h"

int main(void) {
    display_init();
    assert(baud == 12500000u && pixels_written == 480u * 320u);
    display_clear(0x1234);
    for (unsigned row = 0; row < 320; ++row)
        for (unsigned col = 0; col < 480; ++col) assert(panel[row][col] == 0x1234);
    uint16_t line[160];
    for (unsigned row = 0; row < 144; ++row) {
        for (unsigned col = 0; col < 160; ++col) line[col] = (uint16_t)(row * 160 + col);
        display_store_rgb_line(line, row);
    }
    unsigned before = pixels_written;
    display_present();
    assert(pixels_written - before == 356u * 320u);
    assert(pins[PIN_LCD_CS] && pins[PIN_SD_CS] && pixel_half == 0);
    for (unsigned row = 0; row < 320; ++row) for (unsigned col = 0; col < 480; ++col) {
        uint16_t expected = col >= 62 && col < 418
            ? (uint16_t)((row * 144 / 320) * 160 + (col - 62) * 160 / 356) : 0x1234;
        assert(panel[row][col] == expected);
    }
    for (unsigned factor = DISPLAY_FAST; factor <= DISPLAY_FIT_HEIGHT; ++factor) {
        display_clear(0x1234);
        unsigned width = display_game_width(factor), height = display_game_height(factor);
        unsigned left = (480 - width) / 2, top = (320 - height) / 2;
        before = pixels_written;
        display_present_frame(display_default_framebuffer(), factor);
        assert(pixels_written - before == width * height);
        for (unsigned row = 0; row < 320; ++row) for (unsigned col = 0; col < 480; ++col) {
            uint16_t expected = row >= top && row < top + height && col >= left && col < left + width
                ? (uint16_t)(((row - top) * 144 / height) * 160 + (col - left) * 160 / width) : 0x1234;
            assert(panel[row][col] == expected);
        }
        printf("PASS: scale %u, centered %ux%u, %u RGB565 bytes/frame\n", factor, width, height, width * height * 2);
    }
    uint16_t previous[GB_WIDTH * GB_HEIGHT];
    uint16_t *source = display_default_framebuffer();
    memcpy(previous, source, sizeof previous);
    before = pixels_written;
    assert(display_present_changed(source, previous, DISPLAY_FIT_HEIGHT) == 0);
    assert(pixels_written == before);
    /* Exact pixel comparisons, including corner samples and moving objects.
     * A changed bounding rectangle must erase old positions, not leave trails. */
    uint32_t seed = 23;
    for (unsigned n = 0; n < 100; ++n) {
        seed = seed * 1664525u + 1013904223u;
        unsigned sx = n == 0 ? 0 : n == 1 ? 159 : seed % 160;
        unsigned sy = n == 0 ? 0 : n == 1 ? 143 : (seed >> 8) % 144;
        source[sy * 160 + sx] ^= 0xffff;
        before = pixels_written;
        unsigned count = display_present_changed(source, previous, DISPLAY_FIT_HEIGHT);
        assert(count >= 4 && count <= 9); /* one source pixel expands to 2/3 per axis */
        assert(pixels_written - before == count);
        assert(memcmp(previous, source, sizeof previous) == 0);
        for (unsigned row = 0; row < 320; ++row) for (unsigned col = 0; col < 480; ++col) {
            uint16_t expected = col >= 62 && col < 418
                ? source[(row * 144 / 320) * 160 + (col - 62) * 160 / 356] : 0x1234;
            assert(panel[row][col] == expected);
        }
    }
    source[0] ^= 0xffff;
    source[160 * 144 - 1] ^= 0xffff;
    /* Two opposite corner changes must not resend the full screen. */
    assert(display_present_changed(source, previous, DISPLAY_FIT_HEIGHT) <= 18u);
    assert(display_present_changed(source, NULL, DISPLAY_FIT_HEIGHT) == 356u * 320u);
    display_draw_fps(60, 60, DISPLAY_FIT_HEIGHT);
    display_draw_fps(10000, 10000, DISPLAY_FIT_HEIGHT);
    for (unsigned row = 0; row < 320; ++row) for (unsigned col = 62; col < 418; ++col)
        assert(panel[row][col] == source[(row * 144 / 320) * 160 + (col - 62) * 160 / 356]);
    for (unsigned factor = DISPLAY_FAST; factor <= DISPLAY_FIT_HEIGHT; ++factor) {
        display_clear(0x1234);
        display_present_frame(source, factor);
        memcpy(previous, source, sizeof previous);
        unsigned width = display_game_width(factor), height = display_game_height(factor);
        unsigned left = (480 - width) / 2, top = (320 - height) / 2;
        for (unsigned n = 0; n < 40; ++n) {
            if (!n) {
                for (unsigned i = 0; i < 160u * 144u; ++i) source[i] ^= 0xffff;
            } else for (unsigned obj = 0; obj < 12; ++obj) {
                seed = seed * 1664525u + 1013904223u;
                unsigned sx = seed % 160, sy = (seed >> 8) % 144;
                unsigned w = 1 + (seed >> 16) % 20, h = 1 + (seed >> 24) % 16;
                for (unsigned y = sy; y < sy + h && y < 144; ++y)
                    for (unsigned x = sx; x < sx + w && x < 160; ++x)
                        source[y * 160 + x] ^= 0x7359;
            }
            unsigned win_before = window_count;
            unsigned count = display_present_changed(source, previous, factor);
            assert(count <= width * height);
            if (!n) {
                assert(count == width * height);
                assert(window_count == win_before + 1); /* merge full-frame motion */
            }
            assert(memcmp(source, previous, sizeof previous) == 0);
            for (unsigned py = 0; py < 320; ++py) for (unsigned px = 0; px < 480; ++px) {
                uint16_t expected = py >= top && py < top + height && px >= left && px < left + width
                    ? source[((py - top) * 144 / height) * 160 + (px - left) * 160 / width] : 0x1234;
                assert(panel[py][px] == expected);
            }
        }
    }
    puts("PASS: tiled updates, distant objects, dense full-frame merge, 160 randomized multi-rectangle frames at all scales");
    puts("PASS: fit-height 356x320, 62px sidebars, dirty updates, identical-frame zero transfer, corner mapping, sidebar FPS never overlays game");
    /* Batched text preserves spacing, newline, scaling and edge clipping. */
    display_clear(0x1234);
    display_draw_text(10, 10, "A \nA", 0xffff, 0, 2);
    const uint8_t a_glyph[5] = {0x7e,0x11,0x11,0x11,0x7e};
    for (unsigned row = 0; row < 14; ++row) for (unsigned col = 0; col < 24; ++col) {
        uint16_t expected = col < 10 && ((a_glyph[col / 2] >> (row / 2)) & 1u) ? 0xffff : 0;
        assert(panel[10 + row][10 + col] == expected);
        if (col < 12) assert(panel[28 + row][10 + col] == expected);
    }
    display_draw_text(478, 318, "A", 0xffff, 0, 3);
    assert(panel[318][478] == 0 && panel[319][479] == 0);
    display_fill_rect(479, 319, 12, 12, 0xabcd);
    assert(panel[319][479] == 0xabcd);
    display_test_pattern();
    for (unsigned col = 0; col < 480; ++col)
        assert(panel[0][col] == 0xffff && panel[319][col] == 0xffff);
    for (unsigned row = 0; row < 320; ++row)
        assert(panel[row][0] == 0xffff && panel[row][479] == 0xffff);
    puts("PASS: landscape 480x320, RGB565, full-height and legacy scales, batched text/clipping, CS exclusion, safe baud");
    assert(!display_set_spi_baudrate(99000000u));
    assert(display_set_spi_baudrate(25000000u));
    display_select_bus(); assert(baud == 25000000u);
    assert(display_set_spi_baudrate(50000000u));
    display_select_bus(); assert(baud == 50000000u);
    assert(display_set_spi_baudrate(LCD_SPI_BAUD_HZ));
    display_select_bus(); assert(baud == LCD_SPI_BAUD_HZ);
    puts("PASS: bounded test SPI profiles and explicit safe-rate restoration (not electrical qualification)");
}
