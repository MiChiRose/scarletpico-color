#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Active-low byte in the core's joypad layout. */
enum {
    BUTTON_A = 1u, BUTTON_B = 2u, BUTTON_SELECT = 4u, BUTTON_START = 8u,
    BUTTON_RIGHT = 16u, BUTTON_LEFT = 32u, BUTTON_UP = 64u, BUTTON_DOWN = 128u
};
typedef void (*emulator_line_fn)(const uint16_t *, uint8_t);

bool emulator_load(const uint8_t *rom, size_t size, emulator_line_fn draw);
bool emulator_frame(uint8_t joypad);
/* Advance to VBlank, or a frame-sized interval with virtual LCD off,
 * optionally omitting pixel generation. */
bool emulator_frame_render(uint8_t joypad, bool render);
bool emulator_is_color(void);
const char *emulator_error(void);
uint8_t *emulator_save_data(void);
size_t emulator_save_size(void);
bool emulator_save_dirty(void);
void emulator_save_clean(void);
size_t emulator_context_size(void);
uint16_t emulator_program_counter(void);
