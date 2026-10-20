#pragma once
#include <stdint.h>
#include <stdbool.h>
void sleep_ms(uint32_t ms);
void sleep_us(uint64_t us);
uint64_t time_us_64(void);
void stdio_init_all(void);
#define __wfe scarlet_test_wfe
#define __sev scarlet_test_sev
void scarlet_test_wfe(void);
void scarlet_test_sev(void);
