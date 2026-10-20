#include "battery_model.h"

unsigned battery_adc_mv(unsigned raw) {
  if(raw>4095)raw=4095;
  return (raw*6600u+2048u)/4096u;
}
enum battery_charge battery_charge_state(bool charging, bool complete) {
  if(charging&&complete)return BAT_CHECK;
  return charging?BAT_CHARGING:complete?BAT_COMPLETE:BAT_IDLE;
}
void battery_model_sample(battery_model_t *m,unsigned mv) {
  /* Invalid/disconnected/5 V readings are not displayed as an empty/full cell. */
  if(mv<2500||mv>4350) {
    m->valid=false;m->millivolts=0;m->bars=0;m->low=false;m->low_count=0;
    return;
  }
  m->millivolts=m->valid?(m->millivolts*3+mv+2)/4:mv;
  m->valid=true;
  /* Approximate voltage bands, NOT linear state-of-charge percentages. */
  static const unsigned thresholds[]={3500,3650,3750,3900,4050};
  unsigned bars=0;
  while(bars<5&&m->millivolts>=thresholds[bars])bars++;
  m->bars=bars;
  if(m->millivolts<=3500) {
    if(m->low_count<5)m->low_count++;
    if(m->low_count==5)m->low=true;
  } else {
    m->low_count=0;
    if(m->millivolts>=3650)m->low=false;
  }
}
