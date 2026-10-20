#pragma once
#include <stdbool.h>
#include <stdint.h>
typedef struct { uint32_t scratch[8]; } watchdog_hw_t;
extern watchdog_hw_t test_watchdog;
#define watchdog_hw (&test_watchdog)
void watchdog_enable(uint32_t delay_ms, bool pause_on_debug);
void watchdog_disable(void);
void watchdog_update(void);
bool watchdog_enable_caused_reboot(void);
