#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "sd_card_constants.h"

/* FatFs uses 512-byte LBAs. SDSC commands require byte addresses. */
static inline bool sd_spi_command_arg(card_type_t type, cmdSupported command,
                                      bool is_acmd, uint32_t logical_arg,
                                      uint32_t *wire_arg) {
    *wire_arg = logical_arg;
    if (is_acmd || (type != SDCARD_V1 && type != SDCARD_V2)) return true;
    switch (command) {
        case CMD17_READ_SINGLE_BLOCK:
        case CMD18_READ_MULTIPLE_BLOCK:
        case CMD24_WRITE_BLOCK:
        case CMD25_WRITE_MULTIPLE_BLOCK:
        case CMD32_ERASE_WR_BLK_START_ADDR:
        case CMD33_ERASE_WR_BLK_END_ADDR:
            if (logical_arg > UINT32_MAX / 512u) return false;
            *wire_arg = logical_arg * 512u;
            break;
        default:
            break;
    }
    return true;
}

static inline bool sd_spi_valid_range(uint32_t sectors, uint32_t start,
                                       uint32_t count) {
    return count && start < sectors && count <= sectors - start;
}

/* Optional application hook. Never access SPI/display inside this callback. */
void sd_spi_trace(const char *stage, int command, uint32_t response);
