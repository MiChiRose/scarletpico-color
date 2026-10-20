#pragma once
#include <stdbool.h>
#include <stdint.h>
void console_power_init(const uint8_t *settings);
void console_power_record(uint8_t *settings);
void console_power_poll(void); /* Core 0 only; never draws to the LCD. */
void console_power_ui_tick(void); /* Only with video worker stopped. */
void console_power_header(void);
void console_power_game(void); /* Core 1, after completed display transfer. */
void console_power_page(void);
