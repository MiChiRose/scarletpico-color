/* Host FatFs API adapter: inspect the user's real ROM files read-only while
 * exercising production filtering, sorting, metadata, paths and limits. */
#include "game_library.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static const char *names[] = {
    "Legend of Zelda, The - Link's Awakening (U) (V1.2) [!].gb",
    ".DS_Store", "._Aladdin (U) [C][!].gbc", "notes.txt", "directory.gb",
    "Aladdin (U) [C][!].gbc"
};
static size_t cursor;
static FILE *file;
static bool missing;
FRESULT f_opendir(DIR *dir, const TCHAR *path) {
    (void)dir;
    assert(!strcmp(path, "0:/roms"));
    cursor = 0;
    return missing ? FR_NO_PATH : FR_OK;
}
FRESULT f_readdir(DIR *dir, FILINFO *info) {
    (void)dir;
    memset(info, 0, sizeof *info);
    if (cursor == sizeof names / sizeof names[0]) return FR_OK;
    snprintf(info->fname, sizeof info->fname, "%s", names[cursor]);
    info->fattrib = cursor == 4 ? AM_DIR : AM_ARC;
    info->fsize = cursor == 0 ? 524288 : 1048576;
    ++cursor;
    return FR_OK;
}
FRESULT f_closedir(DIR *dir) { (void)dir; return FR_OK; }
FRESULT f_open(FIL *fp, const TCHAR *path, BYTE mode) {
    (void)fp;
    assert(mode == FA_READ && !strncmp(path, "0:/roms/", 8));
    char local[512];
    snprintf(local, sizeof local, "roms/%s", path + 8);
    file = fopen(local, "rb");
    return file ? FR_OK : FR_NO_FILE;
}
FRESULT f_read(FIL *fp, void *buffer, UINT amount, UINT *read) {
    (void)fp;
    *read = (UINT)fread(buffer, 1, amount, file);
    return ferror(file) ? FR_DISK_ERR : FR_OK;
}
FRESULT f_close(FIL *fp) { (void)fp; return fclose(file) == 0 ? FR_OK : FR_DISK_ERR; }

int main(void) {
    game_entry_t entries[4];
    size_t count;
    bool limited;
    assert(game_library_scan(entries, 4, &count, &limited, 1572864 - 4096) == FR_OK);
    assert(count == 2 && !limited);
    assert(!strcmp(entries[0].filename, names[5]) && entries[0].color);
    assert(!strcmp(entries[1].filename, names[0]) && !entries[1].color);
    assert(entries[0].status == GAME_READY && entries[1].status == GAME_READY);
    char path[GAME_PATH_SIZE], save0[GAME_PATH_SIZE], save1[GAME_PATH_SIZE];
    assert(game_rom_path(&entries[0], path, sizeof path));
    assert(!strcmp(path, "0:/roms/Aladdin (U) [C][!].gbc"));
    assert(!game_rom_path(&entries[0], path, 5));
    assert(game_save_path(&entries[0], save0, sizeof save0));
    assert(game_save_path(&entries[1], save1, sizeof save1));
    assert(strcmp(save0, save1) && !strcmp(save1, "0:/saves/zelda.sav"));
    snprintf(entries[1].filename, sizeof entries[1].filename, "zelda.gb");
    assert(game_save_path(&entries[1], path, sizeof path) && !strcmp(path, save1));
    assert(game_library_scan(entries, 1, &count, &limited, 1572864 - 4096) == FR_OK);
    assert(count == 1 && limited);
    assert(game_library_scan(entries, 4, &count, &limited, 1048576 - 4096) == FR_OK);
    assert(entries[0].status == GAME_TOO_LARGE && entries[1].status == GAME_READY);
    missing = true;
    assert(game_library_scan(entries, 4, &count, &limited, 1572864 - 4096) == FR_NO_PATH && count == 0);
    puts("PASS: both real ROMs ready, long filenames, GB/GBC mode, sorted list, macOS junk filtering, size limits, separate saves and Zelda migration");
}
