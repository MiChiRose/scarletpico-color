#pragma once

#ifndef GAME_CLOCK_KHZ
#define GAME_CLOCK_KHZ 125000u
#endif

/* Shared SPI0 bus: ST7796 display + microSD. */
#define PIN_SD_CS       3
#define PIN_SPI_MISO    4
#define PIN_LCD_CS      5
#define PIN_SPI_CLK     6
#define PIN_SPI_MOSI    7
#define PIN_LCD_DC      8
#define PIN_LCD_RST     9
#define PIN_LCD_BL      10

/* MAX98357A I2S, wiring PDF page 2. */
#define PIN_AUDIO_BCLK  11
#define PIN_AUDIO_LRCLK 12
#define PIN_AUDIO_DIN   13

/* Active-low controls. */
#define PIN_BTN_UP      0
#define PIN_BTN_DOWN    1
#define PIN_BTN_LEFT    2
#define PIN_BTN_RIGHT   14
#define PIN_BTN_A       15
#define PIN_BTN_B       26
#define PIN_BTN_START   27
#define PIN_BTN_SELECT  28

#ifndef SD_SPI_BAUD_HZ
#define SD_SPI_BAUD_HZ      1000000u
#endif
#ifndef LCD_SPI_BAUD_HZ
/* ST7796S specifies >=66 ns write cycles (~15 MHz). Start conservatively
 * on the wire-built prototype; the previous 62.5 MHz request was too high. */
#define LCD_SPI_BAUD_HZ     12500000u
#endif
#ifndef LCD_INVERT_COLORS
#define LCD_INVERT_COLORS   0
#endif

/* ST7796 landscape rotation. Change to 0xE8 if the image is upside down. */
#define LCD_MADCTL_VALUE    0x28

#define ROM_PATH            "0:/roms/zelda.gb"
#define SAVE_PATH           "0:/saves/zelda.sav"

/* RP2040-Zero has 2 MiB flash. Reserve 512 KiB for firmware, leaving room
 * for a complete 1 MiB GBC ROM plus the cache metadata sector. */
#define ROM_CACHE_OFFSET    (512u * 1024u)
#define ROM_DATA_OFFSET     (ROM_CACHE_OFFSET + 4096u)
