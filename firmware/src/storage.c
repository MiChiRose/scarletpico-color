#include "storage.h"

#include <stdio.h>
#include <string.h>

#include "config.h"
#include "display_st7796.h"
#include "ff.h"
#include "hardware/flash.h"
#include "hardware/regs/addressmap.h"
#include "hardware/spi.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"

#define CACHE_MAGIC "SPROM01"

typedef struct __attribute__((packed)) {
    char magic[8];
    uint32_t rom_size;
    uint8_t cartridge_header[28];
    uint32_t complete_marker;
} rom_cache_header_t;

static FATFS filesystem;
extern uint8_t __flash_binary_end;

static void storage_select_bus(void) {
    gpio_put(PIN_LCD_CS, 1);
    gpio_put(PIN_SD_CS, 1);
    spi_set_format(spi0, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    spi_set_baudrate(spi0, SD_SPI_BAUD_HZ);
}

bool storage_mount(void) {
    storage_select_bus();
    const FRESULT result = f_mount(&filesystem, "0:", 1);
    display_select_bus();
    printf("SD mount: %d, filesystem=%u, volume LBA=%lu\n", result,
           filesystem.fs_type, (unsigned long)filesystem.volbase);
    return result == FR_OK;
}

FRESULT storage_scan_games(game_entry_t *entries, size_t capacity,
                           size_t *count, bool *limited) {
    storage_select_bus();
    FRESULT result = game_library_scan(entries, capacity, count, limited,
                                       PICO_FLASH_SIZE_BYTES - ROM_DATA_OFFSET);
    display_select_bus();
    return result;
}

static bool read_rom_signature(FIL *file, rom_cache_header_t *signature) {
    memset(signature, 0xff, sizeof *signature);
    memcpy(signature->magic, CACHE_MAGIC, sizeof signature->magic);
    signature->rom_size = f_size(file);
    signature->complete_marker = 0x51A6C0DEu;

    if (f_lseek(file, 0x134) != FR_OK) return false;
    UINT bytes_read = 0;
    if (f_read(file, signature->cartridge_header,
               sizeof signature->cartridge_header, &bytes_read) != FR_OK) {
        return false;
    }
    return bytes_read == sizeof signature->cartridge_header;
}

static bool program_rom_cache(FIL *file, const rom_cache_header_t *signature) {
    const uintptr_t firmware_end = (uintptr_t)&__flash_binary_end - XIP_BASE;
    if (firmware_end >= ROM_CACHE_OFFSET) {
        printf("Firmware overlaps ROM cache: %lu\n", (unsigned long)firmware_end);
        return false;
    }

    const size_t available = PICO_FLASH_SIZE_BYTES - ROM_DATA_OFFSET;
    if (signature->rom_size == 0 || signature->rom_size > available) {
        printf("ROM too large: %lu, max %lu\n",
               (unsigned long)signature->rom_size, (unsigned long)available);
        return false;
    }

    size_t erase_size = 4096u + signature->rom_size;
    erase_size = (erase_size + FLASH_SECTOR_SIZE - 1u) & ~(FLASH_SECTOR_SIZE - 1u);

    uint32_t interrupts = save_and_disable_interrupts();
    flash_range_erase(ROM_CACHE_OFFSET, erase_size);
    restore_interrupts(interrupts);

    if (f_lseek(file, 0) != FR_OK) return false;
    uint8_t page[FLASH_PAGE_SIZE];
    size_t written = 0;
    while (written < signature->rom_size) {
        memset(page, 0xff, sizeof page);
        const UINT requested = (signature->rom_size - written) > sizeof page
            ? sizeof page : (UINT)(signature->rom_size - written);
        UINT bytes_read = 0;
        if (f_read(file, page, requested, &bytes_read) != FR_OK || bytes_read != requested) {
            return false;
        }

        interrupts = save_and_disable_interrupts();
        flash_range_program(ROM_DATA_OFFSET + written, page, sizeof page);
        restore_interrupts(interrupts);
        written += requested;
    }

    memset(page, 0xff, sizeof page);
    memcpy(page, signature, sizeof *signature);
    interrupts = save_and_disable_interrupts();
    flash_range_program(ROM_CACHE_OFFSET, page, sizeof page);
    restore_interrupts(interrupts);
    return true;
}

bool storage_prepare_rom(const char *path, const uint8_t **rom, size_t *rom_size) {
    storage_select_bus();
    FIL file;
    const FRESULT open_result = f_open(&file, path, FA_READ);
    if (open_result != FR_OK) {
        printf("ROM open failed (%d): %s\n", open_result, path);
        display_select_bus();
        return false;
    }

    rom_cache_header_t wanted;
    bool ok = read_rom_signature(&file, &wanted);
    const rom_cache_header_t *cached =
        (const rom_cache_header_t *)(XIP_BASE + ROM_CACHE_OFFSET);

    if (ok && memcmp(cached, &wanted, sizeof wanted) != 0) {
        printf("Caching ROM (%lu bytes)...\n", (unsigned long)wanted.rom_size);
        ok = program_rom_cache(&file, &wanted);
    } else if (ok) {
        printf("ROM cache hit (%lu bytes)\n", (unsigned long)wanted.rom_size);
    }

    f_close(&file);
    display_select_bus();
    if (!ok) return false;

    *rom = (const uint8_t *)(XIP_BASE + ROM_DATA_OFFSET);
    *rom_size = wanted.rom_size;
    return true;
}

bool storage_load_save(const char *path, uint8_t *data, size_t size) {
    if (!size) return true;
    storage_select_bus();
    FIL file;
    FRESULT result = f_open(&file, path, FA_READ);
    if (result == FR_NO_FILE || result == FR_NO_PATH) {
        memset(data, 0xff, size);
        display_select_bus();
        return true;
    }
    if (result != FR_OK) {
        display_select_bus();
        return false;
    }
    UINT bytes_read = 0;
    result = f_read(&file, data, size, &bytes_read);
    f_close(&file);
    display_select_bus();
    if (result != FR_OK) return false;
    if (bytes_read < size) memset(data + bytes_read, 0xff, size - bytes_read);
    printf("Loaded save: %u bytes\n", bytes_read);
    return true;
}

bool storage_write_save(const char *path, const uint8_t *data, size_t size) {
    if (!size) return true;
    storage_select_bus();
    FRESULT result = f_mkdir("0:/saves");
    if (result != FR_OK && result != FR_EXIST) {
        display_select_bus();
        return false;
    }

    FIL file;
    result = f_open(&file, path, FA_WRITE | FA_CREATE_ALWAYS);
    if (result != FR_OK) {
        display_select_bus();
        return false;
    }
    UINT bytes_written = 0;
    result = f_write(&file, data, size, &bytes_written);
    if (result == FR_OK) result = f_sync(&file);
    FRESULT close_result = f_close(&file);
    if (result == FR_OK) result = close_result;
    display_select_bus();
    printf("Saved SRAM: %u/%lu bytes, result %d\n",
           bytes_written, (unsigned long)size, result);
    return result == FR_OK && bytes_written == size;
}
