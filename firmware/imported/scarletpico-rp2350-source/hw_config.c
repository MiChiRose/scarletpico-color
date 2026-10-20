#include "hw_config.h"
#include "config.h"
static spi_t spis[] = {{.hw_inst=spi0, .miso_gpio=PIN_MISO,
  .mosi_gpio=PIN_MOSI, .sck_gpio=PIN_SCK, .baud_rate=SD_HZ}};
static sd_card_t cards[] = {{.pcName="0:", .spi=&spis[0],
  .ss_gpio=PIN_SD_CS, .use_card_detect=false}};
size_t sd_get_num(void) {return 1;}
sd_card_t *sd_get_by_num(size_t n) {return n < 1 ? &cards[n] : NULL;}
size_t spi_get_num(void) {return 1;}
spi_t *spi_get_by_num(size_t n) {return n < 1 ? &spis[n] : NULL;}
