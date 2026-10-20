#pragma once
#include <stdbool.h>
#include <stdint.h>

enum battery_charge { BAT_IDLE, BAT_CHARGING, BAT_COMPLETE, BAT_CHECK };
typedef struct {
  unsigned millivolts, bars, low_count;
  bool valid, low;
} battery_model_t;
/* Equal-resistor 2:1 divider (assembled: 4.7k/4.7k), nominal 3.3 V ADC
 * reference; absolute resistance does not change the ratio. Calibrate by meter. */
unsigned battery_adc_mv(unsigned raw);
enum battery_charge battery_charge_state(bool charging, bool complete);
void battery_model_sample(battery_model_t *model, unsigned millivolts);
