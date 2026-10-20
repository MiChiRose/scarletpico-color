#pragma once
#include <stdbool.h>
#define GPIO_OUT 1
#define GPIO_IN 0
#define GPIO_FUNC_SPI 1
void gpio_init(unsigned pin);
void gpio_put(unsigned pin, bool value);
bool gpio_get(unsigned pin);
void gpio_set_dir(unsigned pin, bool output);
void gpio_set_function(unsigned pin, unsigned function);
void gpio_pull_up(unsigned pin);
