#pragma once
#include "hardware/spi.h"
// Recovered from v0.9 UF2, not confirmed against the current physical wiring.
#define LCD_SPI spi0
#define PIN_SCK 6
#define PIN_MOSI 7
#define PIN_MISO 4
#define PIN_LCD_CS 5
#define PIN_LCD_DC 8
#define PIN_LCD_RST 9
#define PIN_LCD_BL 10
#define PIN_SD_CS 3
#define SD_HZ 12000000u
// Same active-low joypad bit order as Peanut-GB and v0.9.
#define BUTTON_PINS {15,26,28,27,14,2,0,1}
#define KEY_A 1u
#define KEY_B 2u
#define KEY_SELECT 4u
#define KEY_START 8u
#define KEY_RIGHT 16u
#define KEY_LEFT 32u
#define KEY_UP 64u
#define KEY_DOWN 128u
#define ROM_FLASH_OFFSET (512u * 1024u)
#define MAX_SAVE_SIZE (128u * 1024u)
