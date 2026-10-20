#pragma once
#include <stdbool.h>
#include <stdint.h>
bool set_sys_clock_khz(uint32_t khz, bool required);
#define clk_peri 1
#define CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS 0
void clock_configure_undivided(unsigned clock, uint32_t src, uint32_t aux, uint32_t frequency);
