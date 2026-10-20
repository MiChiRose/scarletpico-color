#include "config.h"
#include "hw_config.h"
#include "sd_card.h"

static spi_t sd_spi = {
    .hw_inst = spi0,
    .miso_gpio = PIN_SPI_MISO,
    .mosi_gpio = PIN_SPI_MOSI,
    .sck_gpio = PIN_SPI_CLK,
    .baud_rate = SD_SPI_BAUD_HZ,
    .spi_mode = 0,
};

static sd_spi_if_t sd_spi_if = {
    .spi = &sd_spi,
    .ss_gpio = PIN_SD_CS,
};

static sd_card_t sd_card = {
    .type = SD_IF_SPI,
    .spi_if_p = &sd_spi_if,
};

size_t sd_get_num(void) {
    return 1;
}

sd_card_t *sd_get_by_num(size_t num) {
    return num == 0 ? &sd_card : NULL;
}
