#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "game_library.h"

bool storage_mount(void);
FRESULT storage_scan_games(game_entry_t *entries, size_t capacity,
                           size_t *count, bool *limited);
bool storage_prepare_rom(const char *path, const uint8_t **rom, size_t *rom_size);
bool storage_load_save(const char *path, uint8_t *data, size_t size);
bool storage_write_save(const char *path, const uint8_t *data, size_t size);
