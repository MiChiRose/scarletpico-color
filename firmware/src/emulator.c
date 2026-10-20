#define ENABLE_LCD 1
#ifndef ENABLE_SOUND
#define ENABLE_SOUND 0
#endif
#if ENABLE_SOUND
#include "minigb_apu.h"
#endif
#define PEANUT_FULL_GBC_SUPPORT 1
#include "peanut_gb.h"
#include "emulator.h"

#include <setjmp.h>
#include <stdio.h>

static struct gb_s core;
static const uint8_t *rom_data;
static size_t rom_size, save_size;
static uint8_t *save_data;
static bool dirty, loaded;
static char error_text[80];
static jmp_buf escape;
static emulator_line_fn draw_line;

static uint8_t read_rom(struct gb_s *gb, uint_fast32_t address) {
    (void)gb;
    return address < rom_size ? rom_data[address] : 0xff;
}
static uint8_t read_ram(struct gb_s *gb, uint_fast32_t address) {
    (void)gb;
    return address < save_size ? save_data[address] : 0xff;
}
static void write_ram(struct gb_s *gb, uint_fast32_t address, uint8_t value) {
    (void)gb;
    if (address < save_size && save_data[address] != value) {
        save_data[address] = value;
        dirty = true;
    }
}
static void core_error(struct gb_s *gb, enum gb_error_e error, uint16_t address) {
    (void)gb;
    snprintf(error_text, sizeof error_text, "CORE ERROR %u AT %04X", error, address);
    longjmp(escape, 1); /* upstream requires this callback not to return */
}
static void core_line(struct gb_s *gb, const uint8_t *pixels, uint_fast8_t line) {
    if (line >= 144 || !draw_line) return;
    uint16_t converted[160];
    static const uint16_t palette[4] = {0xD7E9, 0x8D66, 0x4323, 0x10C1};
    for (unsigned x = 0; x < 160; ++x) {
        if (gb->cgb.cgbMode) {
            /* CGB branch provides RGB555; expand green to six bits. Convert
             * on each scanline, before games can change their palettes. */
            uint16_t rgb555 = gb->cgb.fixPalette[pixels[x] & 63u];
            converted[x] = ((rgb555 & 0x7c00u) << 1) |
                           ((rgb555 & 0x03e0u) << 1) |
                           ((rgb555 >> 4) & 0x20u) | (rgb555 & 0x1fu);
        } else {
            converted[x] = palette[pixels[x] & 3u];
        }
    }
    draw_line(converted, (uint8_t)line);
}

bool emulator_load(const uint8_t *rom, size_t size, emulator_line_fn draw) {
    loaded = false;
    dirty = false;
    free(save_data);
    save_data = NULL;
    save_size = 0;
    error_text[0] = 0;
    if (!rom || size < 0x150 || rom[0x148] > 8 || rom[0x149] > 5 ||
        size != (32768u << rom[0x148])) {
        snprintf(error_text, sizeof error_text, "INVALID ROM HEADER OR SIZE");
        return false;
    }
    rom_data = rom;
    rom_size = size;
    draw_line = draw;
    memset(&core, 0, sizeof core);
    if (setjmp(escape)) return false;
    enum gb_init_error_e result = gb_init(&core, read_rom, read_ram, write_ram, core_error, NULL);
    if (result != GB_INIT_NO_ERROR) {
        snprintf(error_text, sizeof error_text, "ROM INIT ERROR %u", result);
        return false;
    }
    static const size_t ram_sizes[] = {0, 2048, 8192, 32768, 131072, 65536};
    /* Avoid the upstream get_save_size's missing RAM code 5 entry. */
    save_size = core.mbc == 2 ? 512 : core.cart_ram ? ram_sizes[rom[0x149]] : 0;
    save_data = save_size ? malloc(save_size) : NULL;
    if (save_size && !save_data) {
        snprintf(error_text, sizeof error_text, "NOT ENOUGH MEMORY FOR SAVE RAM");
        save_size = 0;
        return false;
    }
    if (save_size) memset(save_data, 0xff, save_size);
    core.direct.joypad = 0xff;
    core.direct.frame_skip = 0;
    core.direct.interlace = 0;
    gb_init_lcd(&core, core_line);
    loaded = true;
    return true;
}

bool emulator_frame(uint8_t joypad) {
    return emulator_frame_render(joypad, true);
}
bool emulator_frame_render(uint8_t joypad, bool render) {
    if (!loaded) return false;
    if (setjmp(escape)) { loaded = false; return false; }
    core.direct.joypad = joypad;
    /* Do not call gb_init_lcd here: it resets window/scanline state. The core
     * explicitly supports a NULL callback to bypass only pixel generation. */
    core.display.lcd_draw_line = render ? core_line : NULL;
    /* The local core patch yields after 70224 base-clock ticks with LCD off,
     * so valid initialization is not classified as a crash. Retain an outer
     * instruction budget as a backstop; watchdog covers a stuck inner HALT. */
    core.gb_frame = 0;
    unsigned steps = 0;
    while (!core.gb_frame && steps++ < 200000u) __gb_step_cpu(&core);
    if (!core.gb_frame) {
        snprintf(error_text, sizeof error_text, "FRAME TIMEOUT PC %04X LCD %02X",
                 core.cpu_reg.pc.reg, core.hram_io[IO_LCDC]);
        loaded = false;
        return false;
    }
    return true;
}
bool emulator_is_color(void) { return core.cgb.cgbMode != 0; }
const char *emulator_error(void) { return error_text; }
uint8_t *emulator_save_data(void) { return save_data; }
size_t emulator_save_size(void) { return save_size; }
bool emulator_save_dirty(void) { return dirty; }
void emulator_save_clean(void) { dirty = false; }
size_t emulator_context_size(void) { return sizeof core; }
uint16_t emulator_program_counter(void) { return core.cpu_reg.pc.reg; }
