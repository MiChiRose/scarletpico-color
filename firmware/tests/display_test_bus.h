#pragma once
/* Shared ST7796 SPI simulator: checks every command and output pixel. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "config.h"
#include "display_st7796.h"
#include "hardware/spi.h"

spi_inst_t test_spi;
static uint16_t panel[320][480];
static bool pins[32];
static uint8_t command, parameters[16], hi, madctl, colmod;
static unsigned parameter_count, pixel_half, x0, x1, y0, y1, x, y;
static unsigned baud, pixels_written, window_count;
static uint64_t wire_bytes;
static uint64_t now;

void gpio_init(unsigned pin) { (void)pin; }
void gpio_put(unsigned pin, bool value) { pins[pin] = value; }
bool gpio_get(unsigned pin) { return pins[pin]; }
void gpio_set_dir(unsigned pin, bool value) { (void)pin; (void)value; }
void gpio_set_function(unsigned pin, unsigned fn) { (void)pin; (void)fn; }
void gpio_pull_up(unsigned pin) { pins[pin] = true; }
void sleep_ms(uint32_t ms) { now += ms * 1000ull; }
void sleep_us(uint64_t us) { now += us; }
uint64_t time_us_64(void) { return now; }
unsigned spi_set_baudrate(spi_inst_t *spi, unsigned rate) {
    assert(spi == spi0 && (rate <= 12500000u || rate == 25000000u || rate == 50000000u));
    baud = rate;
    return rate;
}
unsigned spi_init(spi_inst_t *spi, unsigned rate) { return spi_set_baudrate(spi, rate); }
unsigned spi_get_baudrate(const spi_inst_t *spi) { (void)spi; return baud; }
void spi_set_format(spi_inst_t *spi, unsigned bits, unsigned cpol, unsigned cpha, unsigned order) {
    assert(spi == spi0 && bits == 8 && cpol == 0 && cpha == 0 && order == 0);
}
int spi_write_blocking(spi_inst_t *spi, const uint8_t *data, size_t size) {
    assert(spi == spi0 && !pins[PIN_LCD_CS] && pins[PIN_SD_CS]);
    wire_bytes += size;
    if (!pins[PIN_LCD_DC]) {
        assert(size == 1);
        command = data[0];
        parameter_count = 0;
        pixel_half = 0;
        if (command == 0x2c) {
            ++window_count;
            assert(x0 <= x1 && x1 < 480 && y0 <= y1 && y1 < 320);
            x = x0; y = y0;
        }
    } else if (command == 0x2c) {
        assert(madctl == 0x28 && colmod == 0x55);
        for (size_t i = 0; i < size; ++i) {
            if (!pixel_half) hi = data[i];
            else {
                assert(x <= x1 && y <= y1);
                panel[y][x] = ((uint16_t)hi << 8) | data[i];
                ++pixels_written;
                if (++x > x1) { x = x0; ++y; }
            }
            pixel_half ^= 1u;
        }
    } else {
        assert(parameter_count + size <= sizeof parameters);
        memcpy(parameters + parameter_count, data, size);
        parameter_count += size;
        if (command == 0x36) madctl = parameters[0];
        if (command == 0x3a) colmod = parameters[0];
        if (parameter_count == 4 && command == 0x2a) {
            x0 = (parameters[0] << 8) | parameters[1];
            x1 = (parameters[2] << 8) | parameters[3];
        }
        if (parameter_count == 4 && command == 0x2b) {
            y0 = (parameters[0] << 8) | parameters[1];
            y1 = (parameters[2] << 8) | parameters[3];
        }
    }
    return (int)size;
}
