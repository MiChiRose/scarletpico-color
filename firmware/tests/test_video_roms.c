/* Real local ROM + production emulator + production ST7796 driver.
 * Reports SPI traffic, NOT predicted or measured physical-board FPS. */
#include "display_test_bus.h"
#include "emulator.h"
#include <stdlib.h>

static uint16_t previous[GB_WIDTH * GB_HEIGHT];
static unsigned old_bbox_pixels(const uint16_t *frame) {
    unsigned l = 160, r = 0, t = 144, b = 0;
    for (unsigned sy = 0; sy < 144; ++sy) for (unsigned sx = 0; sx < 160; ++sx) {
        unsigned i = sy * 160 + sx;
        if (frame[i] == previous[i]) continue;
        if (sx < l) l = sx;
        if (sx + 1 > r) r = sx + 1;
        if (sy < t) t = sy;
        if (sy + 1 > b) b = sy + 1;
    }
    if (!r) return 0;
    return ((r * 356 + 159) / 160 - (l * 356 + 159) / 160) *
           ((b * 320 + 143) / 144 - (t * 320 + 143) / 144);
}
static void verify_panel(const uint16_t *frame) {
    for (unsigned py = 0; py < 320; ++py) for (unsigned px = 0; px < 480; ++px) {
        uint16_t expected = px >= 62 && px < 418
            ? frame[(py * 144 / 320) * 160 + (px - 62) * 160 / 356] : 0;
        assert(panel[py][px] == expected);
    }
}
static void capture(const char *prefix, unsigned number) {
    char path[512];
    snprintf(path, sizeof path, "%s-%u.ppm", prefix, number);
    FILE *out = fopen(path, "wb");
    assert(out);
    fprintf(out, "P6\n480 320\n255\n");
    for (unsigned py = 0; py < 320; ++py) for (unsigned px = 0; px < 480; ++px) {
        uint16_t c = panel[py][px];
        uint8_t rgb[] = {((c >> 11) & 31) * 255 / 31,
                         ((c >> 5) & 63) * 255 / 63, (c & 31) * 255 / 31};
        assert(fwrite(rgb, 1, 3, out) == 3);
    }
    assert(fclose(out) == 0);
}
int main(int argc, char **argv) {
    assert(argc == 3);
    FILE *in = fopen(argv[1], "rb");
    assert(in && !fseek(in, 0, SEEK_END));
    long size = ftell(in);
    assert(size > 0 && !fseek(in, 0, SEEK_SET));
    uint8_t *rom = malloc(size);
    assert(rom && fread(rom, 1, size, in) == (size_t)size);
    fclose(in);
    display_init();
    assert(emulator_load(rom, size, display_store_rgb_line));
    uint64_t old_bytes = 0, new_bytes = 0, windows = 0;
    unsigned updates = 0;
    for (unsigned frame = 0; frame < 3600; ++frame) {
        uint8_t keys = 0xff;
        /* The monochrome Pac-Man's second Start would pause gameplay. The
         * Color compilation needs it to pass its extra game-selection screen. */
        if ((frame >= 300 && frame < 306) ||
            (emulator_is_color() && frame >= 660 && frame < 666))
            keys &= (uint8_t)~BUTTON_START;
        if (frame >= 720) {
            static const uint8_t dirs[] = {BUTTON_RIGHT, BUTTON_DOWN, BUTTON_LEFT, BUTTON_UP};
            keys &= (uint8_t)~dirs[(frame / 120) % 4];
            if (frame % 180 < 8) keys &= (uint8_t)~BUTTON_A;
        }
        if (!emulator_frame_render(keys, true)) {
            fprintf(stderr, "FRAME %u FAILED: %s\n", frame, emulator_error());
            return 1;
        }
        const uint16_t *pixels = display_default_framebuffer();
        unsigned old = old_bbox_pixels(pixels);
        uint64_t before = wire_bytes;
        unsigned win_before = window_count;
        unsigned sent = display_present_changed(pixels, previous, DISPLAY_FIT_HEIGHT);
        assert(sent <= old); /* no overlapping windows or larger-than-old coverage */
        verify_panel(pixels); /* every pixel, every frame, including black sidebars */
        if (frame >= 720) {
            old_bytes += old ? old * 2u + 11u : 0;
            new_bytes += wire_bytes - before;
            windows += window_count - win_before;
            updates += sent != 0;
        }
        if ((frame + 1) % 600 == 0) capture(argv[2], frame + 1);
    }
    printf("ROM: %s\n", argv[1]);
    printf("PASS: 3600 frames, full-height pixels verified every frame; last 2880 frames: "
           "updates=%u old_SPI_bytes=%llu new_SPI_bytes=%llu reduction=%.1f%% windows=%llu\n",
           updates, (unsigned long long)old_bytes, (unsigned long long)new_bytes,
           old_bytes ? 100.0 * (1.0 - (double)new_bytes / old_bytes) : 0.0,
           (unsigned long long)windows);
    free(rom);
}
