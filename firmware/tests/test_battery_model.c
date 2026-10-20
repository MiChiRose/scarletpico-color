#include "../imported/scarletpico-rp2040-source/battery_model.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
  assert(battery_adc_mv(0)==0);
  assert(battery_adc_mv(2048)==3300);
  assert(battery_adc_mv(2607)>=4199&&battery_adc_mv(2607)<=4201);
  assert(battery_charge_state(false,false)==BAT_IDLE);
  assert(battery_charge_state(true,false)==BAT_CHARGING);
  assert(battery_charge_state(false,true)==BAT_COMPLETE);
  assert(battery_charge_state(true,true)==BAT_CHECK);
  battery_model_t m={0};battery_model_sample(&m,4200);
  assert(m.valid&&m.bars==5&&!m.low);
  battery_model_sample(&m,5000);assert(!m.valid&&!m.low&&m.millivolts==0);
  battery_model_sample(&m,0);assert(!m.valid);
  battery_model_sample(&m,3400);assert(m.valid&&m.bars==0&&!m.low);
  for(unsigned i=0;i<3;i++)battery_model_sample(&m,3400);
  assert(!m.low);battery_model_sample(&m,3400);assert(m.low);
  for(unsigned i=0;i<10;i++)battery_model_sample(&m,3550);
  assert(m.low); /* Hysteresis, not flickering at threshold. */
  for(unsigned i=0;i<30;i++)battery_model_sample(&m,3800);
  assert(!m.low&&m.bars==3);
  puts("PASS battery model: conversion, four charger states, invalid inputs, filtering, delayed low warning and hysteresis");
}
