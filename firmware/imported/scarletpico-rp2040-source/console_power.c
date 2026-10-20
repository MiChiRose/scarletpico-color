#include "console.h"
#include "console_power.h"
#include "battery_model.h"
#include "hardware/adc.h"
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

/* Hardware confirmed by the user: only a 2:1 divider on GP29 is connected.
 * Do not initialise/read GP18/19 or infer charger state from battery voltage. */
#define POWER_ADC_PIN 29
#define POWER_ENABLED (1u<<20)
#define POWER_VALID (1u<<21)
#define POWER_LOW (1u<<22)
static atomic_uint snapshot;
static bool enabled;
static battery_model_t model;
static uint64_t next_adc;

static void enable(bool on) {
  enabled=on;memset(&model,0,sizeof model);
  next_adc=0;
  if(on) {
    adc_init();adc_gpio_init(POWER_ADC_PIN);adc_select_input(3);
  } else {
    /* High impedance, not driven low: no output contention with future wiring. */
    gpio_init(POWER_ADC_PIN);gpio_set_dir(POWER_ADC_PIN,GPIO_IN);gpio_disable_pulls(POWER_ADC_PIN);
  }
  atomic_store(&snapshot,on?POWER_ENABLED:0);
}
void console_power_init(const uint8_t *p) {
  /* This hardware-specific release defaults ON: divider assembly was confirmed.
   * BAT2 is distinct from the old three-pin monitor; preserve its own OFF only.
   * The original 16-byte volume/brightness record remains compatible. */
  bool ok=p&&memcmp(p+16,"BAT2",4)==0&&p[20]<=1&&p[21]==(uint8_t)~p[20];
  enable(!ok||p[20]==1);
}
void console_power_record(uint8_t *p) {
  memcpy(p+16,"BAT2",4);p[20]=enabled;p[21]=(uint8_t)~p[20];
}
/* Hardware-only boundaries kept callable for compiled ARM regression tests. */
__attribute__((noinline)) unsigned console_power_read_sample(void) {
  adc_select_input(3);(void)adc_read();
  unsigned sum=0;for(unsigned i=0;i<16;i++)sum+=adc_read();
  return (sum+8)/16;
}
void console_power_poll(void) {
  if(!enabled)return;
  uint64_t now=time_us_64();if(now<next_adc)return;next_adc=now+1000000;
  battery_model_sample(&model,battery_adc_mv(console_power_read_sample()));
  unsigned packed=POWER_ENABLED|(model.bars<<13)|model.millivolts;
  if(model.valid)packed|=POWER_VALID;
  if(model.low)packed|=POWER_LOW;
  atomic_store(&snapshot,packed);
}
static void voltage(unsigned p,char out[24]) {
  unsigned mv=p&8191;
  if(!(p&POWER_ENABLED))snprintf(out,24,"MONITOR OFF");
  else if(!(p&POWER_VALID))snprintf(out,24,"SENSOR CHECK");
  else snprintf(out,24,"%u.%02u V",mv/1000,(mv%1000)/10);
}
static void indicator(uint16_t bg) {
  unsigned p=atomic_load(&snapshot);char text[16];
  uint16_t color=p&POWER_LOW?UI_ACCENT:UI_TEAL;
  /* Same top-right coordinates in menu and game. The game ends at x=399,
   * so all drawing stays in its right black rail, including the voltage. */
  ui_rect(400,0,80,44,bg);
  ui_rect(416,5,44,18,UI_MUTED);ui_rect(418,7,40,14,bg);
  ui_rect(460,10,3,8,UI_MUTED);
  if(p&POWER_VALID) {
    for(unsigned i=0;i<((p>>13)&7);i++)ui_rect(420+i*7,9,5,10,color);
    unsigned mv=p&8191;snprintf(text,sizeof text,"%u.%02uV",mv/1000,(mv%1000)/10);
  } else if(p&POWER_ENABLED) {
    ui_text(435,10,"?",UI_MUTED,bg,1,1);strcpy(text,"--.--V");
  } else strcpy(text,"OFF");
  unsigned n=strlen(text);
  ui_text(440-n*6,28,text,p&POWER_VALID?color:UI_MUTED,bg,2,6);
}
void console_power_header(void) {indicator(UI_SURFACE);}
void console_power_ui_tick(void) {
  unsigned old=atomic_load(&snapshot);console_power_poll();
  if(old!=atomic_load(&snapshot))console_power_header();
}
void console_power_game(void) {
  indicator(0);
}
static void page_rows(void) {
  unsigned p=atomic_load(&snapshot);char text[24];
  voltage(p,text);
  feature_row(0,9,"BATTERY",text);
  if(p&POWER_VALID)snprintf(text,sizeof text,"%u / 5 BARS",(p>>13)&7);else strcpy(text,"UNKNOWN");
  feature_row(1,9,"VOLTAGE LEVEL",text);
  feature_row(2,9,"MONITOR",enabled?"ON":"OFF");
  feature_row(3,9,"ADC INPUT","GP29 ONLY");
  feature_row(4,9,"DIVIDER","472 + 472");
}
static void page_draw(void) {
  feature_page("BATTERY / VOLTAGE");page_rows();
  feature_footer("A: ENABLE/DISABLE   B: BACK","VOLTAGE BANDS ARE APPROXIMATE; CHARGER SIGNALS NOT CONNECTED");
}
void console_power_page(void) {
  console_power_poll();page_draw();feature_release();uint8_t last=0;
  for(;;) {
    unsigned old=atomic_load(&snapshot);console_power_poll();
    if(old!=atomic_load(&snapshot)){console_power_header();page_rows();}
    uint8_t k=feature_keys(),edge=k&~last;last=k;
    if(edge&UI_B)break;
    if(edge&UI_A) {
      if(!enabled) {
        feature_page("HARDWARE CONFIRMATION");
        ui_text(20,104,"ONLY AFTER THE SENSE CIRCUIT IS INSTALLED",UI_TEXT,UI_BG,1,73);
        ui_text(20,126,"GP29: MIDDLE OF TWO EQUAL 472 RESISTORS",UI_TEXT,UI_BG,1,73);
        ui_text(20,148,"NEVER CONNECT BATTERY OR 5V DIRECTLY TO GP29",UI_ACCENT,UI_BG,1,73);
        feature_footer("A: CONFIRM WIRED HARDWARE","B: CANCEL");feature_release();
        uint8_t confirm=0;while(!(confirm&(UI_A|UI_B))){confirm=feature_keys();sleep_ms(5);}
        if(confirm&UI_A)enable(true);
      } else enable(false);
      console_power_poll();page_draw();feature_release();last=0;
    }
    sleep_ms(5);
  }
  feature_release();
}
