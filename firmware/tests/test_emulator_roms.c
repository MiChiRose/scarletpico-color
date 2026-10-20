#include "emulator.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t frame[144][160];
static uint16_t reference[144][160];
static unsigned lines;
static void line(const uint16_t *pixels, uint8_t y) {
    assert(y < 144);
    memcpy(frame[y], pixels, sizeof frame[y]);
    ++lines;
}
static void dump(const char *prefix, unsigned number) {
    char path[512];
    snprintf(path, sizeof path, "%s-%04u.ppm", prefix, number);
    FILE *out = fopen(path, "wb");
    assert(out);
    fprintf(out, "P6\n160 144\n255\n");
    for (unsigned y = 0; y < 144; ++y) for (unsigned x = 0; x < 160; ++x) {
        uint16_t c = frame[y][x];
        uint8_t rgb[3] = {((c >> 11) & 31) * 255 / 31,
                         ((c >> 5) & 63) * 255 / 63, (c & 31) * 255 / 31};
        assert(fwrite(rgb, 1, 3, out) == 3);
    }
    assert(fclose(out) == 0);
}
int main(int argc, char **argv) {
    assert(argc == 3);
    FILE *input = fopen(argv[1], "rb");
    assert(input && !fseek(input, 0, SEEK_END));
    long size = ftell(input);
    assert(size > 0 && !fseek(input, 0, SEEK_SET));
    uint8_t *rom = malloc((size_t)size);
    assert(rom && fread(rom, 1, (size_t)size, input) == (size_t)size);
    fclose(input);
    uint8_t *reference_save = NULL;
    for (unsigned run = 0; run < 3; ++run) {
        memset(frame, 0, sizeof frame);
        assert(emulator_load(rom, size, line));
        assert(emulator_is_color() == ((rom[0x143] & 0x80) != 0));
        assert(!emulator_save_dirty());
        printf("Loaded %s: color=%d, save=%zu, context=%zu\n", argv[1],
               emulator_is_color(), emulator_save_size(), emulator_context_size());
        fflush(stdout);
        unsigned frames = run == 2 ? 120 : 1800;
        for (unsigned i = 0; i < frames; ++i) {
            uint8_t keys = 0xff;
            if (i > 300 && i % 240 < 10) keys &= (uint8_t)~BUTTON_START;
            if (i > 600 && i % 150 < 10) keys &= (uint8_t)~BUTTON_A;
            bool render = run != 1 || i % 4 == 3;
            unsigned before = lines;
            if (!emulator_frame_render(keys, render)) {
                fprintf(stderr, "FAIL at frame %u: %s\n", i, emulator_error());
                return 1;
            }
            if (!render) assert(lines == before);
            if (!run && (i + 1) % 300 == 0) dump(argv[2], i + 1);
        }
        assert(lines >= 144);
        if (run == 0) {
            memcpy(reference, frame, sizeof reference);
            if (emulator_save_size()) {
                reference_save = malloc(emulator_save_size());
                assert(reference_save);
                memcpy(reference_save, emulator_save_data(), emulator_save_size());
            }
        } else if (run == 1) {
            assert(memcmp(reference, frame, sizeof reference) == 0);
            if (emulator_save_size())
                assert(memcmp(reference_save, emulator_save_data(), emulator_save_size()) == 0);
            puts("PASS: skipping 3/4 video frames preserves final pixels and save RAM after 1800 frames");
        }
    }
    unsigned colors = 0;
    bool seen[65536] = {false};
    for (unsigned y = 0; y < 144; ++y) for (unsigned x = 0; x < 160; ++x)
        if (!seen[frame[y][x]]) { seen[frame[y][x]] = true; ++colors; }
    printf("PASS: 1800 frames + reload, %u scanlines, last frame %u colors\n", lines, colors);
    assert(emulator_load(rom, size, line));
    uint32_t seed = 0x53434152;
    uint8_t held = 0xff;
    for (unsigned i = 0; i < 18000; ++i) {
        if (i % 30 == 0) {
            seed = seed * 1664525u + 1013904223u;
            static const uint8_t dirs[] = {BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT};
            held = (uint8_t)~dirs[(seed >> 16) & 3];
            if (seed & 1) held &= (uint8_t)~BUTTON_A;
            if (seed & 2) held &= (uint8_t)~BUTTON_B;
        }
        uint8_t keys = held;
        if (i % 600 < 5) keys &= (uint8_t)~BUTTON_START;
        if (!emulator_frame_render(keys, i % 3 == 0)) {
            fprintf(stderr, "STRESS FAIL at frame %u PC %04X: %s\n", i,
                    emulator_program_counter(), emulator_error());
            return 1;
        }
    }
    puts("PASS: 18000 additional frames with repeatable movement/action inputs and render skipping");
    free(rom);
    free(reference_save);
}
