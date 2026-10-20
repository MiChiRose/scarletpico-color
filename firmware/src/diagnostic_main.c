#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "config.h"
#include "display_st7796.h"
#include "ff.h"
#include "diskio.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/stdlib.h"
#include "hw_config.h"
#include "sd_card.h"
#include "SPI/sd_spi_compat.h"

#define COLOR_BG       0x0000
#define COLOR_TEXT     0xffff
#define COLOR_OK       0x07e0
#define COLOR_WARN     0xffe0
#define COLOR_FAIL     0xf800
#define LINE_HEIGHT    20

static FATFS filesystem;
static unsigned line_y = 12;
static char serial_report[1024];
static size_t serial_report_length;
static const char *sd_stage = "DRIVER START";
static int last_sd_command = -1;
static uint32_t last_sd_response = 0xff;
static char driver_errors[1024];
static size_t driver_errors_length;

void sd_spi_trace(const char *stage, int command, uint32_t response) {
    if (stage) sd_stage = stage;
    if (command >= 0) {
        last_sd_command = command;
        last_sd_response = response;
    }
}

/* Capture errors for USB after enumeration, without touching the active bus. */
void put_out_error_message(const char *message) {
    size_t count = strlen(message);
    size_t available = sizeof driver_errors - driver_errors_length - 1;
    if (count > available) count = available;
    memcpy(driver_errors + driver_errors_length, message, count);
    driver_errors_length += count;
    driver_errors[driver_errors_length] = 0;
}

static const char *card_type_name(card_type_t type) {
    switch (type) {
        case SDCARD_V1: return "SDSC V1";
        case SDCARD_V2: return "SDSC V2";
        case SDCARD_V2HC: return "SDHC/SDXC";
        default: return "UNKNOWN";
    }
}

static const char *fr_name(FRESULT result) {
    switch (result) {
        case FR_OK: return "FR_OK";
        case FR_DISK_ERR: return "FR_DISK_ERR";
        case FR_INT_ERR: return "FR_INT_ERR";
        case FR_NOT_READY: return "FR_NOT_READY";
        case FR_NO_FILE: return "FR_NO_FILE";
        case FR_NO_PATH: return "FR_NO_PATH";
        case FR_INVALID_NAME: return "FR_INVALID_NAME";
        case FR_DENIED: return "FR_DENIED";
        case FR_EXIST: return "FR_EXIST";
        case FR_INVALID_OBJECT: return "FR_INVALID_OBJECT";
        case FR_WRITE_PROTECTED: return "FR_WRITE_PROTECTED";
        case FR_INVALID_DRIVE: return "FR_INVALID_DRIVE";
        case FR_NOT_ENABLED: return "FR_NOT_ENABLED";
        case FR_NO_FILESYSTEM: return "FR_NO_FILESYSTEM";
        case FR_MKFS_ABORTED: return "FR_MKFS_ABORTED";
        case FR_TIMEOUT: return "FR_TIMEOUT";
        case FR_LOCKED: return "FR_LOCKED";
        case FR_NOT_ENOUGH_CORE: return "FR_NOT_ENOUGH_CORE";
        case FR_TOO_MANY_OPEN_FILES: return "FR_TOO_MANY_OPEN_FILES";
        case FR_INVALID_PARAMETER: return "FR_INVALID_PARAMETER";
        default: return "FR_UNKNOWN";
    }
}

static void report(uint16_t color, const char *format, ...) {
    char message[96];
    va_list args;
    va_start(args, format);
    vsnprintf(message, sizeof message, format, args);
    va_end(args);

    printf("%s\n", message);
    if (serial_report_length < sizeof serial_report - 2) {
        const int amount = snprintf(serial_report + serial_report_length,
                                    sizeof serial_report - serial_report_length,
                                    "%s\n", message);
        if (amount > 0) serial_report_length += (size_t)amount;
        if (serial_report_length >= sizeof serial_report)
            serial_report_length = sizeof serial_report - 1;
    }
    display_draw_text(12, line_y, message, color, COLOR_BG, 2);
    line_y += LINE_HEIGHT;
}

static void select_sd_bus(void) {
    gpio_put(PIN_LCD_CS, 1);
    gpio_put(PIN_SD_CS, 1);
    spi_set_format(spi0, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);
    spi_set_baudrate(spi0, SD_SPI_BAUD_HZ);
}

static void show_hint(const char *first, const char *second) {
    report(COLOR_WARN, "%s", first);
    if (second) report(COLOR_WARN, "%s", second);
}

int main(void) {
    stdio_init_all();
    display_bus_init();
    sleep_ms(10);
    select_sd_bus();
    const DSTATUS init_status = disk_initialize(0);
    const char *init_stage = sd_stage;
    const int init_command = last_sd_command;
    const uint32_t init_response = last_sd_response;
    display_init();
    display_clear(COLOR_BG);
    report(COLOR_TEXT, "SCARLETPICO SD DIAG V03");
    report(COLOR_TEXT, "PINS CS3 MISO4 CLK6 MOSI7");
    report(COLOR_TEXT, "SD SPI 1 MHZ READ ONLY");

    const bool card_ready = !(init_status & (STA_NOINIT | STA_NODISK));
    report(card_ready ? COLOR_OK : COLOR_FAIL,
           "CARD INIT %s STATUS %02X", card_ready ? "OK" : "FAIL",
           init_status);
    sd_card_t *card = sd_get_by_num(0);
    report(COLOR_TEXT, "TYPE %s", card_type_name(card->state.card_type));

    bool ready = card_ready;
    FRESULT mount_result = FR_NOT_READY;
    if (ready) {
        select_sd_bus();
        mount_result = f_mount(&filesystem, "", 1);
        display_select_bus();
        report(mount_result == FR_OK ? COLOR_OK : COLOR_FAIL,
               "MOUNT %s CODE %u", fr_name(mount_result), mount_result);
        ready = mount_result == FR_OK;
    } else {
        report(COLOR_TEXT, "STAGE %s", init_stage);
        report(COLOR_TEXT, "LAST CMD %d R1 %02lX", init_command,
               (unsigned long)init_response);
        show_hint("INIT FAILED BEFORE FILESYSTEM", "SEND PHOTO OF THIS SCREEN");
    }

    if (ready) {
        DIR directory;
        select_sd_bus();
        FRESULT result = f_opendir(&directory, "/roms");
        if (result == FR_OK) f_closedir(&directory);
        display_select_bus();
        report(result == FR_OK ? COLOR_OK : COLOR_FAIL,
               "ROMS DIR %s CODE %u", fr_name(result), result);
        ready = result == FR_OK;
        if (!ready) show_hint("CREATE FOLDER NAMED ROMS", NULL);
    }

    if (ready) {
        FIL rom;
        select_sd_bus();
        FRESULT result = f_open(&rom, ROM_PATH, FA_READ);
        FSIZE_t size = 0;
        if (result == FR_OK) size = f_size(&rom);
        display_select_bus();
        report(result == FR_OK ? COLOR_OK : COLOR_FAIL,
               "ZELDA.GB %s CODE %u", fr_name(result), result);
        ready = result == FR_OK;
        if (!ready) {
            show_hint("EXPECTED ROMS/ZELDA.GB", NULL);
        } else {
            report(size == 524288u ? COLOR_OK : COLOR_WARN,
                   "ROM SIZE %lu BYTES", (unsigned long)size);
            uint8_t header[26] = {0};
            UINT bytes_read = 0;
            select_sd_bus();
            result = f_lseek(&rom, 0x134);
            if (result == FR_OK)
                result = f_read(&rom, header, sizeof header, &bytes_read);
            display_select_bus();
            char title[17] = {0};
            for (unsigned i = 0; i < 16; ++i) {
                const uint8_t c = header[i];
                title[i] = (c >= 32 && c <= 126) ? (char)c : ' ';
            }
            report(result == FR_OK && bytes_read == sizeof header
                       ? COLOR_OK : COLOR_FAIL,
                   "ROM READ %s %u BYTES",
                   result == FR_OK ? "OK" : fr_name(result), bytes_read);
            if (result == FR_OK && bytes_read == sizeof header)
                report(COLOR_OK, "TITLE %.16s", title);
            ready = result == FR_OK && bytes_read == sizeof header;
            if (ready) {
                uint8_t checksum = 0;
                for (unsigned i = 0; i < 25; ++i)
                    checksum = (uint8_t)(checksum - header[i] - 1u);
                ready = checksum == header[25];
                report(ready ? COLOR_OK : COLOR_FAIL, "HEADER CHECK %s",
                       ready ? "OK" : "FAIL");
            }
            if (ready) {
                /* Read the entire file, exercising nonzero LBAs and ROM banks. */
                static uint8_t buffer[4096];
                uint32_t crc = 0xffffffffu;
                FSIZE_t total = 0;
                select_sd_bus();
                result = f_lseek(&rom, 0);
                while (result == FR_OK && total < size) {
                    result = f_read(&rom, buffer, sizeof buffer, &bytes_read);
                    if (result != FR_OK || !bytes_read) break;
                    total += bytes_read;
                    for (UINT i = 0; i < bytes_read; ++i) {
                        crc ^= buffer[i];
                        for (unsigned bit = 0; bit < 8; ++bit)
                            crc = (crc >> 1) ^ ((crc & 1u) ? 0xedb88320u : 0);
                    }
                }
                display_select_bus();
                ready = result == FR_OK && total == size;
                report(ready ? COLOR_OK : COLOR_FAIL, "FULL READ %s CODE %u",
                       ready ? "OK" : "FAIL", result);
                if (ready) report(COLOR_TEXT, "ROM CRC32 %08lX",
                                  (unsigned long)(crc ^ 0xffffffffu));
            }
            select_sd_bus();
            f_close(&rom);
            display_select_bus();
        }
    }

    if (card_ready && mount_result != FR_OK) {
        if (mount_result == FR_NO_FILESYSTEM)
            show_hint("CARD FOUND BUT FAT INVALID", "USE MS DOS FAT PLUS MBR");
        else
            show_hint("CARD FOUND FILESYSTEM FAIL", "SEE USB SERIAL CODE");
    }

    report(ready ? COLOR_OK : COLOR_FAIL,
           ready ? "RESULT READY FOR EMULATOR" : "RESULT FAILED SEE LINE ABOVE");

    /* Keep the result visible and periodically repeat it over USB serial. */
    while (true) {
        printf("\n--- ScarletPico diagnostic report ---\n%s\n%s",
               serial_report, driver_errors);
        sleep_ms(3000);
    }
}
