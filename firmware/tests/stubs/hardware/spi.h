#pragma once
#include <stdint.h>
#include <stddef.h>
typedef unsigned uint;
typedef struct { int unused; } spi_inst_t;
extern spi_inst_t test_spi;
#define spi0 (&test_spi)
#define SPI_CPOL_0 0
#define SPI_CPHA_0 0
#define SPI_MSB_FIRST 0
uint spi_init(spi_inst_t *spi, uint rate);
uint spi_set_baudrate(spi_inst_t *spi, uint rate);
uint spi_get_baudrate(const spi_inst_t *spi);
void spi_set_format(spi_inst_t *spi, uint bits, uint cpol, uint cpha, uint order);
int spi_write_blocking(spi_inst_t *spi, const uint8_t *bytes, size_t count);
