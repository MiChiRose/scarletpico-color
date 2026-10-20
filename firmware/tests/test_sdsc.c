#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "SPI/sd_spi_compat.h"
#include "sd_regs.h"

/* Test the actual vendor headers used by both firmware binaries. */
static void set_bits(uint8_t csd[16], unsigned msb, unsigned lsb, uint32_t value) {
    for (unsigned bit = lsb; bit <= msb; ++bit) {
        uint8_t mask = (uint8_t)(1u << (bit & 7u));
        unsigned byte = 15u - bit / 8u;
        csd[byte] &= (uint8_t)~mask;
        if (value & (1u << (bit - lsb))) csd[byte] |= mask;
    }
}

static void test_addresses(void) {
    const cmdSupported commands[] = {
        CMD17_READ_SINGLE_BLOCK, CMD18_READ_MULTIPLE_BLOCK,
        CMD24_WRITE_BLOCK, CMD25_WRITE_MULTIPLE_BLOCK,
        CMD32_ERASE_WR_BLK_START_ADDR, CMD33_ERASE_WR_BLK_END_ADDR,
    };
    const uint32_t lbas[] = {0, 1, 2048, 4194303, 8388607};
    uint32_t argument;
    for (unsigned c = 0; c < sizeof commands / sizeof commands[0]; ++c) {
        for (unsigned i = 0; i < sizeof lbas / sizeof lbas[0]; ++i) {
            assert(sd_spi_command_arg(SDCARD_V1, commands[c], false, lbas[i], &argument));
            assert(argument == (uint64_t)lbas[i] * 512u);
            assert(sd_spi_command_arg(SDCARD_V2, commands[c], false, lbas[i], &argument));
            assert(argument == (uint64_t)lbas[i] * 512u);
            assert(sd_spi_command_arg(SDCARD_V2HC, commands[c], false, lbas[i], &argument));
            assert(argument == lbas[i]);
        }
        assert(!sd_spi_command_arg(SDCARD_V1, commands[c], false, 8388608u, &argument));
    }
    assert(sd_spi_command_arg(SDCARD_V1, CMD16_SET_BLOCKLEN, false, 512, &argument));
    assert(argument == 512);
    assert(sd_spi_command_arg(SDCARD_V2, CMD8_SEND_IF_COND, false, 0x1aa, &argument));
    assert(argument == 0x1aa);
    assert(sd_spi_command_arg(SDCARD_V2, ACMD41_SD_SEND_OP_COND, true, 0x40000000, &argument));
    assert(argument == 0x40000000);
    assert(sd_spi_command_arg(SDCARD_V1, ACMD23_SET_WR_BLK_ERASE_COUNT, true, 8, &argument));
    assert(argument == 8);
}

static void test_capacity(void) {
    CSD_t csd = {0};
    set_bits(csd, 73, 62, 4095);
    set_bits(csd, 49, 47, 7);
    set_bits(csd, 83, 80, 9);
    assert(CSD_sectors(csd) == 2097152u); /* 1 GiB with native 512-byte blocks */
    set_bits(csd, 83, 80, 10);
    assert(CSD_sectors(csd) == 4194304u); /* 2 GiB with native 1024-byte blocks */
    set_bits(csd, 73, 62, 2047);
    set_bits(csd, 83, 80, 11);
    assert(CSD_sectors(csd) == 4194304u); /* same capacity, 2048-byte blocks */
    set_bits(csd, 83, 80, 15);
    assert(CSD_sectors(csd) == 0); /* reserved block size */
    memset(csd, 0, sizeof csd);
    set_bits(csd, 127, 126, 1);
    set_bits(csd, 69, 48, 16383);
    assert(CSD_sectors(csd) == 16777216u); /* 8 GiB SDHC unchanged */
    set_bits(csd, 127, 126, 3);
    assert(CSD_sectors(csd) == 0);
}

static void test_ranges(void) {
    assert(sd_spi_valid_range(4194304, 4194303, 1));
    assert(sd_spi_valid_range(4194304, 0, 4194304));
    assert(!sd_spi_valid_range(4194304, 4194303, 2));
    assert(!sd_spi_valid_range(4194304, 4194304, 1));
    assert(!sd_spi_valid_range(4194304, 0, 0));
    assert(!sd_spi_valid_range(4194304, UINT32_MAX - 1, 4));
}

int main(void) {
    test_addresses();
    test_capacity();
    test_ranges();
    puts("PASS: SDSC v1/v2 addressing, SDHC addressing, CSD capacity, LBA bounds");
}
