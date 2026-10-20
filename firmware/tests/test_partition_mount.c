/* Regression test against the production FatFs sources and partition map.
 * All sectors are synthetic and in memory. This test never opens a device. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "ff.h"
#include "diskio.h"

#define SECTOR_SIZE 512u
#define PARTITION_SIZE 100000u
#define SECTOR_SLOTS 96u

typedef struct {
    LBA_t lba;
    uint8_t bytes[SECTOR_SIZE];
} sector_t;

static sector_t sectors[SECTOR_SLOTS];
static unsigned used, writes;
static uint32_t partition_start;
static FATFS fs;
static const uint8_t file_name[] = "ZELDA   GB ";
static uint8_t rom_contents[600];

static uint8_t *sector(LBA_t lba) {
    for (unsigned i = 0; i < used; ++i)
        if (sectors[i].lba == lba) return sectors[i].bytes;
    assert(used < SECTOR_SLOTS);
    sectors[used].lba = lba;
    memset(sectors[used].bytes, 0, SECTOR_SIZE);
    return sectors[used++].bytes;
}

static void le16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}

static void le32(uint8_t *p, uint32_t v) {
    le16(p, (uint16_t)v);
    le16(p + 2, (uint16_t)(v >> 16));
}

static void signature(uint8_t *p) {
    p[0] = 0xeb; p[1] = 0x3c; p[2] = 0x90;
    le16(p + 11, SECTOR_SIZE);
    le16(p + 510, 0xaa55);
}

static void entry(uint8_t *p, const uint8_t name[11], uint8_t attr,
                  uint32_t cluster, uint32_t size) {
    memcpy(p, name, 11);
    p[11] = attr;
    le16(p + 20, (uint16_t)(cluster >> 16));
    le16(p + 26, (uint16_t)cluster);
    le32(p + 28, size);
}

static void make_disk(uint32_t start, bool stale_boot_record) {
    used = writes = 0;
    partition_start = start;
    uint8_t *mbr = sector(0);
    signature(mbr);
    if (stale_boot_record) {
        /* A valid-looking old FAT16 BPB in the MBR's boot-code area. */
        mbr[13] = 1;
        le16(mbr + 14, 1);
        mbr[16] = 2;
        le16(mbr + 17, 512);
        le16(mbr + 19, 32768);
        mbr[21] = 0xf8;
        le16(mbr + 22, 128);
        memcpy(mbr + 54, "FAT16   ", 8);
    } else {
        memset(mbr, 0, 446);
    }
    mbr[446 + 4] = 0x0c;
    le32(mbr + 446 + 8, start);
    le32(mbr + 446 + 12, PARTITION_SIZE);

    uint8_t *vbr = sector(start);
    signature(vbr);
    memcpy(vbr + 3, "MSDOS5.0", 8);
    vbr[13] = 1;
    le16(vbr + 14, 32);
    vbr[16] = 2;
    vbr[21] = 0xf8;
    le32(vbr + 28, start);
    le32(vbr + 32, PARTITION_SIZE);
    le32(vbr + 36, 800);
    le32(vbr + 44, 2);
    le16(vbr + 48, 0xffff); /* no FSINFO sector in this fixture */
    memcpy(vbr + 82, "FAT32   ", 8);

    for (unsigned copy = 0; copy < 2; ++copy) {
        uint8_t *fat = sector(start + 32 + 800 * copy);
        le32(fat + 0 * 4, 0x0ffffff8);
        le32(fat + 1 * 4, 0x0fffffff);
        le32(fat + 2 * 4, 0x0fffffff); /* root */
        le32(fat + 3 * 4, 0x0fffffff); /* roms */
        le32(fat + 4 * 4, 6);          /* file: clusters 4 -> 6 */
        le32(fat + 5 * 4, 0x0fffffff); /* saves */
        le32(fat + 6 * 4, 0x0fffffff);
    }
    uint32_t data = start + 32 + 1600;
    uint8_t *root = sector(data);
    entry(root, (const uint8_t *)"ROMS       ", AM_DIR, 3, 0);
    entry(root + 32, (const uint8_t *)"SAVES      ", AM_DIR, 5, 0);
    entry(sector(data + 1), file_name, AM_ARC, 4, sizeof rom_contents);
    for (unsigned i = 0; i < sizeof rom_contents; ++i)
        rom_contents[i] = (uint8_t)(i * 37u + 9u);
    memcpy(sector(data + 2), rom_contents, 512);
    memcpy(sector(data + 4), rom_contents + 512, sizeof rom_contents - 512);
}

DSTATUS disk_initialize(BYTE drive) { return drive == 0 ? 0 : STA_NOINIT; }
DSTATUS disk_status(BYTE drive) { return disk_initialize(drive); }

DRESULT disk_read(BYTE drive, BYTE *buffer, LBA_t lba, UINT count) {
    if (drive || !count || lba + count > partition_start + PARTITION_SIZE) return RES_PARERR;
    for (UINT i = 0; i < count; ++i)
        memcpy(buffer + i * SECTOR_SIZE, sector(lba + i), SECTOR_SIZE);
    return RES_OK;
}

DRESULT disk_write(BYTE drive, const BYTE *buffer, LBA_t lba, UINT count) {
    if (drive || !count || lba + count > partition_start + PARTITION_SIZE) return RES_PARERR;
    assert(lba >= partition_start); /* no writes to the old whole-disk volume */
    for (UINT i = 0; i < count; ++i)
        memcpy(sector(lba + i), buffer + i * SECTOR_SIZE, SECTOR_SIZE);
    writes += count;
    return RES_OK;
}

DRESULT disk_ioctl(BYTE drive, BYTE command, void *data) {
    if (drive) return RES_PARERR;
    switch (command) {
        case CTRL_SYNC: return RES_OK;
        case GET_SECTOR_COUNT: *(LBA_t *)data = partition_start + PARTITION_SIZE; return RES_OK;
        case GET_BLOCK_SIZE: *(DWORD *)data = 1; return RES_OK;
        default: return RES_PARERR;
    }
}

DWORD get_fattime(void) { return (46u << 25) | (9u << 21) | (26u << 16); }

static void test_legacy_auto(void) {
    VolToPart[0].pt = 0;
    assert(f_mount(&fs, "0:", 1) == FR_OK);
    assert(fs.fs_type == FS_FAT16 && fs.volbase == 0);
    DIR dir;
    FILINFO info;
    assert(f_opendir(&dir, "0:/") == FR_OK);
    assert(f_readdir(&dir, &info) == FR_OK && info.fname[0] == 0);
    assert(f_closedir(&dir) == FR_OK);
    assert(f_stat("0:/roms", &info) == FR_NO_FILE);
    assert(f_stat("0:/roms/zelda.gb", &info) == FR_NO_PATH);
    assert(f_mount(NULL, "0:", 0) == FR_OK);
    puts("REPRODUCED: auto-mount FS2 LBA0, empty root, ROMS=4, ZELDA=5");
}

static void test_partition(void) {
    VolToPart[0].pt = 1;
    assert(f_mount(&fs, "0:", 1) == FR_OK);
    assert(fs.fs_type == FS_FAT32 && fs.volbase == partition_start);
    FILINFO info;
    assert(f_stat("0:/roms", &info) == FR_OK && (info.fattrib & AM_DIR));
    assert(f_stat("0:/roms/zelda.gb", &info) == FR_OK && info.fsize == sizeof rom_contents);
    FIL file;
    UINT transferred;
    uint8_t data[sizeof rom_contents];
    assert(f_open(&file, "0:/roms/zelda.gb", FA_READ) == FR_OK);
    assert(f_read(&file, data, sizeof data, &transferred) == FR_OK);
    assert(transferred == sizeof data && memcmp(data, rom_contents, sizeof data) == 0);
    assert(f_close(&file) == FR_OK);
    assert(writes == 0);

    memset(data, 0x5a, sizeof data);
    assert(f_open(&file, "0:/saves/zelda.sav", FA_WRITE | FA_CREATE_ALWAYS) == FR_OK);
    assert(f_write(&file, data, sizeof data, &transferred) == FR_OK && transferred == sizeof data);
    assert(f_sync(&file) == FR_OK);
    assert(f_close(&file) == FR_OK && writes > 0);
    memset(data, 0, sizeof data);
    assert(f_open(&file, "0:/saves/zelda.sav", FA_READ) == FR_OK);
    assert(f_read(&file, data, sizeof data, &transferred) == FR_OK && transferred == sizeof data);
    for (unsigned i = 0; i < sizeof data; ++i) assert(data[i] == 0x5a);
    assert(f_close(&file) == FR_OK);
    assert(f_mount(NULL, "0:", 0) == FR_OK);
    printf("PASS: MBR partition at LBA %u, ROM read and save round-trip\n", partition_start);
}

int main(void) {
    assert(VolToPart[0].pd == 0 && VolToPart[0].pt == 1);
    make_disk(16, true);
    test_legacy_auto();
    test_partition();
    make_disk(2048, true);
    test_partition();
    make_disk(16, false);
    test_partition();
    make_disk(16, true);
    memset(sector(0) + 446, 0, 64); /* missing partition must not fall back to stale FAT */
    assert(f_mount(&fs, "0:", 1) == FR_NO_FILESYSTEM);
    assert(f_mount(NULL, "0:", 0) == FR_OK);
    puts("PASS: missing MBR partition is rejected without fallback");
}
