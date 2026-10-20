#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "config.h"
#include "display_st7796.h"
#include "ff.h"
#include "diskio.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "hw_config.h"
#include "pico/stdlib.h"
#include "sd_card.h"
#include "SPI/sd_spi_compat.h"

#define WHITE 0xffff
#define GREEN 0x07e0
#define RED 0xf800
#define ROOT_NAMES 8

typedef struct {
    FRESULT root_result, dir_result, file_result;
    BYTE dir_attributes;
    FSIZE_t rom_size;
    unsigned count;
    bool complete;
    char names[ROOT_NAMES][38];
} fs_snapshot_t;

static FATFS fs;
static fs_snapshot_t before, after;
static DSTATUS init_status;
static FRESULT mount_result = FR_NOT_READY;
static FRESULT rom_result = FR_NOT_READY;
static FSIZE_t rom_bytes;
static uint32_t rom_crc;
static bool header_ok, rom_ok;
static char rom_title[17];
static const char *stage = "DRIVER START";
static int last_command = -1;
static uint32_t last_response = 0xff;
static char errors[1024];
static unsigned text_y;
static uint8_t read_buffer[4096];

void sd_spi_trace(const char *next_stage, int command, uint32_t response) {
    if (next_stage) stage = next_stage;
    if (command >= 0) {
        last_command = command;
        last_response = response;
    }
}

void put_out_error_message(const char *message) {
    size_t used = strlen(errors);
    if (used < sizeof errors - 1)
        snprintf(errors + used, sizeof errors - used, "%s", message);
}

static const char *type_name(void) {
    switch (sd_get_by_num(0)->state.card_type) {
        case SDCARD_V1: return "SDSC V1";
        case SDCARD_V2: return "SDSC V2";
        case SDCARD_V2HC: return "SDHC/SDXC";
        default: return "UNKNOWN";
    }
}

static void select_sd(void) {
    gpio_put(PIN_LCD_CS, 1);
    gpio_put(PIN_SD_CS, 1);
    spi_set_format(spi0, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    spi_set_baudrate(spi0, SD_SPI_BAUD_HZ);
}

/* No display transactions within a snapshot: every result is buffered. */
static void snapshot(fs_snapshot_t *out) {
    memset(out, 0, sizeof *out);
    out->root_result = out->dir_result = out->file_result = mount_result;
    if (mount_result != FR_OK) return;
    select_sd();
    DIR directory;
    FILINFO info;
    out->root_result = f_opendir(&directory, "0:/");
    if (out->root_result == FR_OK) {
        for (unsigned i = 0; i < 128; ++i) {
            out->root_result = f_readdir(&directory, &info);
            if (out->root_result != FR_OK) break;
            if (!info.fname[0]) {
                out->complete = true;
                break;
            }
            if (out->count < ROOT_NAMES)
                snprintf(out->names[out->count], sizeof out->names[0],
                         "%c %.34s", (info.fattrib & AM_DIR) ? 'D' : 'F', info.fname);
            ++out->count;
        }
        f_closedir(&directory);
    }
    out->dir_result = f_stat("0:/roms", &info);
    if (out->dir_result == FR_OK) out->dir_attributes = info.fattrib;
    out->file_result = f_stat("0:/roms/zelda.gb", &info);
    if (out->file_result == FR_OK) out->rom_size = info.fsize;
}

static void check_rom(void) {
    if (after.file_result != FR_OK) {
        rom_result = after.file_result;
        return;
    }
    select_sd();
    FIL file;
    rom_result = f_open(&file, "0:/roms/zelda.gb", FA_READ);
    if (rom_result != FR_OK) return;
    const FSIZE_t size = f_size(&file);
    uint32_t crc = 0xffffffffu;
    while (rom_result == FR_OK && rom_bytes < size) {
        UINT count = 0;
        rom_result = f_read(&file, read_buffer, sizeof read_buffer, &count);
        if (rom_result != FR_OK || !count) break;
        if (rom_bytes == 0 && count >= 0x150) {
            uint8_t checksum = 0;
            for (unsigned i = 0x134; i <= 0x14c; ++i)
                checksum = (uint8_t)(checksum - read_buffer[i] - 1u);
            header_ok = checksum == read_buffer[0x14d];
            for (unsigned i = 0; i < 16; ++i) {
                uint8_t c = read_buffer[0x134 + i];
                rom_title[i] = (c >= 32 && c <= 126) ? (char)c : ' ';
            }
        }
        rom_bytes += count;
        for (UINT i = 0; i < count; ++i) {
            crc ^= read_buffer[i];
            for (unsigned bit = 0; bit < 8; ++bit)
                crc = (crc >> 1) ^ ((crc & 1u) ? 0xedb88320u : 0);
        }
    }
    const FRESULT close_result = f_close(&file);
    if (rom_result == FR_OK) rom_result = close_result;
    rom_crc = crc ^ 0xffffffffu;
    rom_ok = rom_result == FR_OK && rom_bytes == size && size >= 0x150 && header_ok;
}

static void line(uint16_t color, const char *format, ...) {
    char text[40];
    va_list args;
    va_start(args, format);
    vsnprintf(text, sizeof text, format, args);
    va_end(args);
    display_draw_text(8, text_y, text, color, 0, 2);
    text_y += 20;
}

static void summary(void) {
    display_clear(0);
    text_y = 8;
    line(WHITE, "SCARLETPICO SD DIAG V05");
    const bool initialized = !(init_status & (STA_NOINIT | STA_NODISK));
    line(initialized ? GREEN : RED, "INIT %02X TYPE %s", init_status, type_name());
    if (!initialized) {
        line(RED, "STAGE %s", stage);
        line(RED, "LAST CMD %d R1 %02lX", last_command, (unsigned long)last_response);
    } else {
        line(mount_result == FR_OK ? GREEN : RED, "MOUNT CODE %u FS %u LBA %lu",
             mount_result, fs.fs_type, (unsigned long)fs.volbase);
        line(before.root_result == FR_OK ? WHITE : RED,
             "ROOT BEFORE %u COUNT %u", before.root_result, before.count);
        line(before.dir_result == FR_OK ? GREEN : RED,
             "ROMS BEFORE CODE %u", before.dir_result);
        line(before.file_result == FR_OK ? GREEN : RED,
             "ZELDA BEFORE CODE %u", before.file_result);
        line(after.root_result == FR_OK ? WHITE : RED,
             "ROOT AFTER %u COUNT %u", after.root_result, after.count);
        line(after.dir_result == FR_OK ? GREEN : RED,
             "ROMS AFTER CODE %u", after.dir_result);
        line(after.file_result == FR_OK ? GREEN : RED,
             "ZELDA AFTER CODE %u", after.file_result);
        if (after.file_result == FR_OK) {
            line(rom_ok ? GREEN : RED, "FULL READ CODE %u BYTES %lu", rom_result,
                 (unsigned long)rom_bytes);
            line(header_ok ? GREEN : RED, "HEADER %s TITLE %.16s",
                 header_ok ? "OK" : "FAIL", rom_title);
            line(WHITE, "ROM CRC32 %08lX", (unsigned long)rom_crc);
        }
    }
    line(rom_ok ? GREEN : RED, rom_ok ? "RESULT SD AND ROM READ OK" : "RESULT FAILED - A FOR ROOT LIST");
    display_draw_text(8, 304, "A OR SELECT - SHOW ROOT LIST", WHITE, 0, 1);
}

static void root_page(const fs_snapshot_t *s, const char *label) {
    display_clear(0);
    text_y = 8;
    line(WHITE, "V05 ROOT %s LCD", label);
    line(WHITE, "CODE %u COUNT %u COMPLETE %u", s->root_result, s->count, s->complete);
    line(WHITE, "VOLUME LBA %lu CLUSTER %u", (unsigned long)fs.volbase, fs.csize);
    line(WHITE, "ROOT CL %lu DATA LBA %lu", (unsigned long)fs.dirbase,
         (unsigned long)fs.database);
    for (unsigned i = 0; i < s->count && i < ROOT_NAMES; ++i)
        line(WHITE, "%s", s->names[i]);
    if (!s->count) line(RED, "NO ENTRIES RETURNED");
    line(WHITE, "D DIRECTORY - F FILE");
    display_draw_text(8, 304, "A OR SELECT - NEXT PAGE", WHITE, 0, 1);
}

static void usb_snapshot(const char *label, const fs_snapshot_t *s) {
    printf("%s: root=%u count=%u complete=%u roms=%u attr=%02x zelda=%u size=%lu\n",
           label, s->root_result, s->count, s->complete, s->dir_result,
           s->dir_attributes, s->file_result, (unsigned long)s->rom_size);
    for (unsigned i = 0; i < s->count && i < ROOT_NAMES; ++i)
        printf("  %s\n", s->names[i]);
}

int main(void) {
    stdio_init_all();
    gpio_init(PIN_BTN_A);
    gpio_set_dir(PIN_BTN_A, GPIO_IN);
    gpio_pull_up(PIN_BTN_A);
    gpio_init(PIN_BTN_SELECT);
    gpio_set_dir(PIN_BTN_SELECT, GPIO_IN);
    gpio_pull_up(PIN_BTN_SELECT);
    display_bus_init();
    sleep_ms(10);
    select_sd();
    init_status = disk_initialize(0);
    if (!(init_status & (STA_NOINIT | STA_NODISK)))
        mount_result = f_mount(&fs, "0:", 1);
    snapshot(&before);
    display_init();
    display_draw_text(8, 8, "V05 CHECKING CARD AND FULL ROM", WHITE, 0, 2);
    snapshot(&after);
    check_rom();
    summary();

    unsigned page = 0;
    bool previous = true;
    uint64_t last_change = 0, last_report = 0;
    while (true) {
        bool pressed = !gpio_get(PIN_BTN_A) || !gpio_get(PIN_BTN_SELECT);
        uint64_t now = time_us_64();
        if (pressed != previous && now - last_change >= 80000u) {
            previous = pressed;
            last_change = now;
            if (pressed) {
                page = (page + 1) % 3;
                if (page == 0) summary();
                else root_page(page == 1 ? &before : &after, page == 1 ? "BEFORE" : "AFTER");
            }
        }
        if (now - last_report >= 3000000u) {
            printf("\nSD DIAG V05 init=%u type=%s stage=%s cmd=%d R1=%02lx mount=%u\n",
                   init_status, type_name(), stage, last_command,
                   (unsigned long)last_response, mount_result);
            printf("FS=%u vol=%lu fat=%lu root=%lu data=%lu cluster=%u\n",
                   fs.fs_type, (unsigned long)fs.volbase, (unsigned long)fs.fatbase,
                   (unsigned long)fs.dirbase, (unsigned long)fs.database, fs.csize);
            usb_snapshot("BEFORE LCD", &before);
            usb_snapshot("AFTER LCD", &after);
            printf("ROM result=%u bytes=%lu header=%u crc=%08lx OK=%u\n%s",
                   rom_result, (unsigned long)rom_bytes, header_ok,
                   (unsigned long)rom_crc, rom_ok, errors);
            last_report = now;
        }
        sleep_ms(10);
    }
}
