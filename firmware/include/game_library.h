#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "ff.h"

#define GAME_LIBRARY_MAX 32u
#define GAME_PATH_SIZE 288u

typedef enum {
    GAME_READY, GAME_BAD_HEADER, GAME_TOO_LARGE,
    GAME_UNSUPPORTED, GAME_READ_ERROR
} game_status_t;

typedef struct {
    char filename[256];
    char label[37];
    uint32_t size;
    uint8_t signature[28];
    bool color;
    game_status_t status;
} game_entry_t;

/* Caller owns the shared SPI bus while these functions access FatFs. */
FRESULT game_library_scan(game_entry_t *entries, size_t capacity, size_t *count,
                         bool *limited, uint32_t max_rom_size);
bool game_rom_path(const game_entry_t *game, char *path, size_t capacity);
bool game_save_path(const game_entry_t *game, char *path, size_t capacity);
const char *game_status_message(game_status_t status);
