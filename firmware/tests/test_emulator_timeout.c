#include "emulator.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t rom[32768];
int main(void) {
    /* Homebrew regression ROM: disable LCD then loop without a VBlank. */
    const uint8_t code[] = {0xf3, 0xaf, 0xe0, 0x40, 0x18, 0xfe};
    memcpy(rom + 0x100, code, sizeof code);
    uint8_t checksum = 0;
    for (unsigned i = 0x134; i <= 0x14c; ++i) checksum = checksum - rom[i] - 1;
    rom[0x14d] = checksum;
    assert(emulator_load(rom, sizeof rom, NULL));
    /* An LCD-off game still runs and yields to the host; no false crash. */
    for (unsigned i = 0; i < 120; ++i) assert(emulator_frame_render(0xff, false));
    assert(!*emulator_error());
    assert(emulator_program_counter() == 0x104);
    rom[0x100] = 0xd3; /* invalid Game Boy opcode also exits through error UI */
    assert(emulator_load(rom, sizeof rom, NULL));
    assert(!emulator_frame_render(0xff, false));
    assert(strstr(emulator_error(), "CORE ERROR"));
    puts("PASS: LCD-disabled ROM yields repeatedly without a false error; invalid opcode returns a core error");
}
