#include "game_library.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

static bool rom_filename(const char *name) {
    if (name[0] == '.') return false; /* includes macOS ._ resource forks */
    const char *extension = strrchr(name, '.');
    return extension && (!strcasecmp(extension, ".gb") || !strcasecmp(extension, ".gbc"));
}

static int compare_games(const void *a, const void *b) {
    return strcasecmp(((const game_entry_t *)a)->filename,
                      ((const game_entry_t *)b)->filename);
}

bool game_rom_path(const game_entry_t *game, char *path, size_t capacity) {
    int n = snprintf(path, capacity, "0:/roms/%s", game->filename);
    return n > 0 && (size_t)n < capacity;
}

bool game_save_path(const game_entry_t *game, char *path, size_t capacity) {
    /* Header identity shares saves between a long filename and its short copy.
     * Preserve the original prototype's Zelda save name for this cartridge. */
    uint32_t identity = 2166136261u;
    for (unsigned i = 0; i < sizeof game->signature; ++i)
        identity = (identity ^ game->signature[i]) * 16777619u;
    for (unsigned shift = 0; shift < 32; shift += 8)
        identity = (identity ^ ((game->size >> shift) & 255u)) * 16777619u;
    int n;
    static const uint8_t legacy_zelda[28] = {
        'Z','E','L','D','A',0,0,0,0,0,0,0,0,0,0,0,
        0,0,0,3,4,2,1,1,2,0x6a,0x3a,0xee
    };
    if (!memcmp(game->signature, legacy_zelda, sizeof legacy_zelda) && game->size == 524288u) {
        n = snprintf(path, capacity, "0:/saves/zelda.sav");
    } else {
        n = snprintf(path, capacity, "0:/saves/%08lX.sav", (unsigned long)identity);
    }
    return n > 0 && (size_t)n < capacity;
}

static void inspect_game(game_entry_t *game, uint32_t max_rom_size) {
    char path[GAME_PATH_SIZE];
    uint8_t header[0x150];
    FIL file;
    UINT read;
    game->status = GAME_READ_ERROR;
    if (!game_rom_path(game, path, sizeof path) || f_open(&file, path, FA_READ) != FR_OK)
        return;
    FRESULT result = f_read(&file, header, sizeof header, &read);
    FRESULT closed = f_close(&file);
    if (result != FR_OK || closed != FR_OK) return;
    game->status = GAME_BAD_HEADER;
    if (read != sizeof header) return;
    memcpy(game->signature, header + 0x134, sizeof game->signature);
    uint8_t checksum = 0;
    for (unsigned i = 0x134; i <= 0x14c; ++i) checksum -= header[i] + 1u;
    if (checksum != header[0x14d] || header[0x148] > 8 || header[0x149] > 5)
        return;
    if (game->size != (32768u << header[0x148])) return;
    game->color = (header[0x143] & 0x80) != 0;
    if (game->size > max_rom_size) { game->status = GAME_TOO_LARGE; return; }
    static const int8_t supported_mbc[] = {
        0,1,1,1,-1,2,2,-1,0,0,-1,0,0,0,-1,3,
        3,3,3,3,-1,-1,-1,-1,-1,5,5,5,5,5,5,-1
    };
    if (header[0x147] >= sizeof supported_mbc || supported_mbc[header[0x147]] < 0) {
        game->status = GAME_UNSUPPORTED; return;
    }
    game->status = GAME_READY;
}

FRESULT game_library_scan(game_entry_t *entries, size_t capacity, size_t *count,
                         bool *limited, uint32_t max_rom_size) {
    *count = 0;
    *limited = false;
    DIR dir;
    FILINFO info;
    FRESULT result = f_opendir(&dir, "0:/roms");
    if (result != FR_OK) return result;
    while ((result = f_readdir(&dir, &info)) == FR_OK && info.fname[0]) {
        if ((info.fattrib & (AM_DIR | AM_HID | AM_SYS)) || !rom_filename(info.fname)) continue;
        if (*count == capacity) { *limited = true; continue; }
        game_entry_t *game = &entries[(*count)++];
        memset(game, 0, sizeof *game);
        snprintf(game->filename, sizeof game->filename, "%s", info.fname);
        game->size = info.fsize;
        const char *extension = strrchr(game->filename, '.');
        size_t label_length = (size_t)(extension - game->filename);
        if (label_length >= sizeof game->label) label_length = sizeof game->label - 1;
        for (size_t i = 0; i < label_length; ++i) {
            unsigned char c = (unsigned char)game->filename[i];
            game->label[i] = (char)(isalnum(c) || c == '-' || c == ' ' ? c : ' ');
        }
        inspect_game(game, max_rom_size);
    }
    FRESULT closed = f_closedir(&dir);
    qsort(entries, *count, sizeof *entries, compare_games);
    return result != FR_OK ? result : closed;
}

const char *game_status_message(game_status_t status) {
    switch (status) {
        case GAME_READY: return "READY";
        case GAME_BAD_HEADER: return "INVALID ROM HEADER OR SIZE";
        case GAME_TOO_LARGE: return "ROM TOO LARGE FOR FLASH CACHE";
        case GAME_UNSUPPORTED: return "CARTRIDGE TYPE NOT SUPPORTED";
        default: return "COULD NOT READ ROM";
    }
}
