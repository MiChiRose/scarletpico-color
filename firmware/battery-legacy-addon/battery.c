/* Append-only GP29 indicator for the SHA-pinned, hardware-working 2.2.2.
 * Never reinitialise the display/SPI/SD/clocks or rebuild the emulator.
 * Core 0 alone reads ADC. Core 1 reads an aligned published word and draws
 * only from the original worker's HUD call after the video transfer ends. */
#include <stdbool.h>
#include <stdint.h>
#include "../imported/scarletpico-rp2040-source/battery_model.h"

extern uint64_t time_us_64(void);
extern void old_rect(unsigned,unsigned,unsigned,unsigned,uint16_t);
extern void old_text(unsigned,unsigned,const char *,uint16_t,uint16_t,unsigned);
extern unsigned old_menu_input(unsigned);
extern unsigned old_pace_frame(unsigned,unsigned,uint32_t);
extern void old_hud(unsigned,unsigned,unsigned);

#define REG(a) (*(volatile uint32_t *)(a))
#define VALID (1u<<16)
#define LOW (1u<<17)
#define TEAL 0x4e98
#define MUTED 0x8433
#define ACCENT 0xfa6c
#define SURFACE 0x18e5
static volatile unsigned battery_snapshot;
static battery_model_t model;
static uint32_t next_sample;
static unsigned menu_painted;
static bool adc_started, sampled, menu_valid;

static bool ready(void) {
  /* No broken ADC/clock can strand boot/menu in an infinite wait. */
  for(unsigned n=0;n<10000;n++)if(REG(0x4004c000u)&(1u<<8))return true;
  return false;
}
static void start_adc(void) {
  /* Only GP29: NULL function, no digital receiver/pulls. Do not touch 26-28. */
  REG(0x400140ecu)=31;
  REG(0x4001c078u)&=~((1u<<6)|(1u<<3)|(1u<<2));
  /* ADC clock only, PLL_USB/1. Core/peripheral/SPI/USB clocks are unchanged. */
  REG(0x40008064u)=1u<<8;
  REG(0x40008060u)=1u<<11;
  REG(0x4000f000u)=1u; /* release ADC reset only */
  for(unsigned n=0;n<10000;n++)if(REG(0x4000c008u)&1u)break;
  REG(0x4004c000u)=1u|(3u<<12);
  adc_started=true;
}
/* Separate boundary: compiled tests exercise real register writes/timeouts. */
__attribute__((noinline)) unsigned legacy_battery_read_sample(void) {
  if(!adc_started)start_adc();
  unsigned sum=0;
  for(unsigned i=0;i<17;i++) {
    if(!ready())return 0xffffffffu;
    REG(0x4004e000u)=1u<<2; /* ADC CS SET: START_ONCE */
    if(!ready() || (REG(0x4004c000u)&(1u<<9)))return 0xffffffffu;
    unsigned raw=REG(0x4004c004u)&4095u;
    if(i)sum+=raw; /* discard first conversion after input select */
  }
  return (sum+8u)/16u;
}
void legacy_battery_poll(void) {
  uint32_t now=(uint32_t)time_us_64();
  if(sampled&&(int32_t)(now-next_sample)<0)return;
  sampled=true;next_sample=now+1000000u;
  unsigned raw=legacy_battery_read_sample();
  battery_model_sample(&model,raw>4095?0:battery_adc_mv(raw));
  unsigned p=model.millivolts|(model.bars<<13);
  if(model.valid)p|=VALID;
  if(model.low)p|=LOW;
  __asm volatile("dmb" ::: "memory");battery_snapshot=p;
}
static unsigned published(void) {
  unsigned p=battery_snapshot;__asm volatile("dmb" ::: "memory");return p;
}
static void indicator(unsigned x,unsigned width,uint16_t bg,unsigned scale) {
  unsigned p=published(),n=6;char text[]="--.--V";
  uint16_t color=p&LOW?ACCENT:TEAL;
  old_rect(x,0,width,44,bg);
  unsigned body=x+(width-46)/2;
  old_rect(body,5,42,18,MUTED);old_rect(body+2,7,38,14,bg);
  old_rect(body+42,10,3,8,MUTED);
  if(p&VALID) {
    for(unsigned i=0;i<((p>>13)&7);i++)old_rect(body+4+i*6,9,4,10,color);
    unsigned mv=p&8191;
    text[0]='0'+mv/1000;text[1]='.';text[2]='0'+mv/100%10;
    text[3]='0'+mv/10%10;text[4]='V';text[5]=0;n=5;
  }
  old_text(x+(width-n*6*scale)/2,28,text,p&VALID?color:MUTED,bg,scale);
}
/* This replaces only the final underline drawing CALL in the old header.
 * Its original five-argument ABI and all earlier title rendering survive. */
void legacy_battery_header(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t c) {
  old_rect(x,y,w,h,c);legacy_battery_poll();
  indicator(400,80,SURFACE,2);menu_painted=published();menu_valid=true;
}
unsigned legacy_battery_menu_input(unsigned edge) {
  unsigned result=old_menu_input(edge);
  legacy_battery_poll();
  if(!menu_valid||menu_painted!=published()) {
    indicator(400,80,SURFACE,2);menu_painted=published();menu_valid=true;
  }
  return result;
}
unsigned legacy_battery_frame(unsigned keys,unsigned offered,uint32_t due) {
  /* Keep original PACED bridge, including its special R7 frame-ready ABI. */
  legacy_battery_poll();return old_pace_frame(keys,offered,due);
}
void legacy_battery_hud(unsigned lcd,unsigned emu,unsigned scale) {
  old_hud(lcd,emu,scale);
  /* Full-height 356px game ends at x417. Minimum right rail is 62px.
   * Use stack-only original text drawing, NOT the shared UI text scanline. */
  indicator(418,62,0,1);
}
