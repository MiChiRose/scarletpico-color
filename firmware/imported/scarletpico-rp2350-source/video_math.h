#pragma once
#include <stdint.h>
static inline uint16_t color555_to565(uint16_t c) {
  return ((c&0x7fe0u)<<1)|(c&31u)|((c>>4)&0x20u);
}
static inline unsigned scaled_source(unsigned position,unsigned source,unsigned dest) {
  return position*source/dest;
}
