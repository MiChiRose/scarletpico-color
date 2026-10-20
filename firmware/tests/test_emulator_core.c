/* Test private core state without adding debug accessors to the firmware API. */
#include "../src/emulator.c"
#include <assert.h>

static uint8_t rom[32768];
static void header(void) {
    uint8_t sum = 0;
    for (unsigned i = 0x134; i <= 0x14c; ++i) sum = sum - rom[i] - 1;
    rom[0x14d] = sum;
}
int main(void) {
    const uint8_t init[] = {
        0xf3, 0xaf, 0xe0, 0x40, /* DI; XOR A; LDH (LCDC),A */
        0x01, 0xff, 0xff,       /* LD BC,65535 */
        0x0b, 0x78, 0xb1, 0x20, 0xfb, /* DEC BC; LD A,B; OR C; JR NZ,-5 */
        0x3e, 0x91, 0xe0, 0x40, /* turn LCD back on after >200,000 instructions */
        0x18, 0xfe
    };
    memcpy(rom + 0x100, init, sizeof init);
    header();
    assert(emulator_load(rom, sizeof rom, NULL));
    core.hram_io[IO_IF] = 0;
    assert(emulator_frame_render(0xff, false));
    assert(!(core.hram_io[IO_LCDC] & LCDC_ENABLE));
    assert(core.hram_io[IO_LY] == 0 && !(core.hram_io[IO_IF] & VBLANK_INTR));
    for (unsigned i = 0; i < 60; ++i) assert(emulator_frame_render(0xff, false));
    assert(core.hram_io[IO_LCDC] & LCDC_ENABLE);
    assert(emulator_program_counter() == 0x110);
    assert(!*emulator_error());

    /* Sound is muted, but the game must still be able to read its registers.
     * In particular FF30..FF3F must not index beyond the 48-byte mask table. */
    static const uint8_t mask[48] = {
        0x80,0x3f,0x00,0xff,0xbf,0xff,0x3f,0x00,0xff,0xbf,
        0x7f,0xff,0x9f,0xff,0xbf,0xff,0xff,0x00,0x00,0xbf,
        0x00,0x00,0x70,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    };
    for (unsigned a = 0xff10; a <= 0xff3f; ++a) {
        for (unsigned v = 0; v <= 255; v += 17) {
            core.hram_io[a - IO_ADDR] = v;
            assert(__gb_read(&core, a) == (uint8_t)(v | mask[a - 0xff10]));
        }
    }
    /* Double-speed LCD-off slices advance twice as many CPU cycles, without
     * advancing the LCD or fabricating an interrupt. */
    rom[0x100] = 0x18; rom[0x101] = 0xfe;
    assert(emulator_load(rom, sizeof rom, NULL));
    core.hram_io[IO_LCDC] = 0;
    core.hram_io[IO_IF] = 0;
    core.hram_io[IO_DIV] = 0;
    core.counter.div_count = 0;
    assert(emulator_frame_render(0xff, false));
    uint8_t normal_div = core.hram_io[IO_DIV];
    core.cgb.doubleSpeed = 1;
    core.hram_io[IO_DIV] = 0;
    core.counter.div_count = 0;
    core.counter.lcd_off_count = 0;
    assert(emulator_frame_render(0xff, false));
    assert(normal_div == (70224u / 256u) % 256u);
    assert(core.hram_io[IO_DIV] == (2u * 70224u / 256u) % 256u);
    assert(!(core.hram_io[IO_IF] & VBLANK_INTR));
    puts("PASS: long LCD-off initialization resumes, no fake VBlank, double-speed timing, all 48 APU read masks");
}
