/* Our existing launcher skin, boot and pause menus on the native SDK API. */
#include "console.h"
#include "console_power.h"
#include "config.h"
#include "display.h"
#include "hardware/flash.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include <string.h>
#include <stdio.h>

bool pause_pending,exit_requested,chord_active,chord_latched;
uint32_t chord_since;
uint8_t slot_status[5];
static unsigned selected;
__attribute__((noinline)) uint8_t feature_keys(void) {
  static const uint8_t pins[]=BUTTON_PINS;
  uint32_t gpio=gpio_get_all();uint8_t k=0;
  for(unsigned i=0;i<8;i++)if(!(gpio&(1u<<pins[i])))k|=1u<<i;
  return k;
}
void feature_release(void) {
  unsigned n=0;while(n<6){n=feature_keys()?0:n+1;sleep_ms(5);}
}
void console_input_reset(void) {
  pause_pending=exit_requested=chord_active=chord_latched=false;feature_release();
}
unsigned ui_game_count(void){return native_game_count();}
unsigned ui_game_selected(void){return selected;}
unsigned ui_library_error(void){return 0;}
const char *ui_game_label(unsigned i){return native_game_label(i);}
bool ui_game_color(unsigned i){return native_game_color(i);}
unsigned ui_game_status(unsigned i){return native_game_folder(i)?5:0;}
void ui_rect(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t c){display_rect(x,y,w,h,c);}
void ui_pixels_begin(unsigned x,unsigned y,unsigned w,unsigned h){display_ui_begin(x,y,w,h);}
void ui_pixels_row(const uint8_t *p,unsigned n){display_ui_row(p,n);}
void ui_pixels_end(void){display_ui_end();}
void ui_apply_brightness(unsigned v) {
  if(v<10)v=10;
  if(v>100)v=100;
  unsigned slice=pwm_gpio_to_slice_num(PIN_LCD_BL);
  pwm_config cfg=pwm_get_default_config();pwm_config_set_clkdiv(&cfg,8);
  pwm_config_set_wrap(&cfg,999);pwm_init(slice,&cfg,false);
  pwm_set_gpio_level(PIN_LCD_BL,v*10);gpio_set_function(PIN_LCD_BL,GPIO_FUNC_PWM);
  pwm_set_enabled(slice,true);
}
const char *feature_tr(const char *en,const char *ru){(void)ru;return en;}
void feature_page(const char *title) {
  ui_rect(0,0,480,320,UI_BG);ui_header();ui_text(20,65,title,UI_TEXT,UI_BG,2,37);
}
void feature_row(unsigned i,unsigned focus,const char *label,const char *value) {
  unsigned y=94+i*34;uint16_t bg=i==focus?UI_SURFACE:UI_BG;
  ui_rect(16,y,448,32,bg);
  if(i==focus){
    ui_rect(16,y,448,1,UI_ACCENT);ui_rect(16,y+31,448,1,UI_ACCENT);
    ui_rect(16,y,1,32,UI_ACCENT);ui_rect(463,y,1,32,UI_ACCENT);
    ui_text(24,y+9,">",UI_ACCENT,bg,2,1);
  }
  ui_text(44,y+9,label,UI_TEXT,bg,2,value?19:34);
  if(value)ui_text(296,y+9,value,UI_TEXT,bg,2,13);
}
void feature_footer(const char *a,const char *b) {
  ui_rect(0,282,480,38,UI_SURFACE);ui_text(16,291,a,UI_TEXT,UI_SURFACE,1,74);
  if(b)ui_text(16,306,b,UI_TEXT,UI_SURFACE,1,74);
}
void feature_message(const char *en,const char *ru) {
  (void)ru;ui_rect(16,264,448,14,UI_BG);ui_text(20,267,en,UI_TEAL,UI_BG,1,73);
}
void feature_error(const char *s){feature_message(s,0);}
void console_message(const char *title,const char *detail) {
  feature_page(title);if(detail)ui_text(20,108,detail,UI_TEXT,UI_BG,1,73);
  feature_footer("A/B: CONTINUE",NULL);
}
void features_ui_init(const uint8_t *p){ui_init(p);ui_settings.language=0;}
static uint8_t menu_edge(uint8_t *last,uint32_t *repeat) {
  console_power_ui_tick();
  uint8_t k=feature_keys();if(k!=*last){sleep_ms(25);if(feature_keys()!=k)return 0;}
  uint8_t e=k&~*last;uint32_t now=(uint32_t)time_us_64();
  if(e)*repeat=now+350000;
  else if((k&0xc0)&&(int32_t)(now-*repeat)>=0){e=k&0xc0;*repeat=now+140000;}
  *last=k;return e;
}
static bool persist(void) {
  uint8_t p[FLASH_PAGE_SIZE];memset(p,255,sizeof p);ui_make_record(p);
  console_power_record(p);
  const uint8_t *saved=(const uint8_t *)(XIP_BASE+SETTINGS_FLASH_OFFSET);
  if(!memcmp(p,saved,22))return true;
  /* Both video and audio are stopped when this page is open. */
  uint32_t irq=save_and_disable_interrupts();flash_range_erase(SETTINGS_FLASH_OFFSET,FLASH_SECTOR_SIZE);
  flash_range_program(SETTINGS_FLASH_OFFSET,p,sizeof p);restore_interrupts(irq);
  return !memcmp(p,saved,22);
}
static void setting_row(unsigned i,unsigned focus) {
  static const char *names[]={"VOLUME","BRIGHTNESS","CPU FREQUENCY","ABOUT DEVICE","BATTERY / VOLTAGE"};
  char value[16];
  if(i<2)snprintf(value,sizeof value,"< %u%% >",i?ui_settings.brightness:ui_settings.volume);
  else if(i==2)snprintf(value,sizeof value,"%u MHZ",SCARLET_CPU_KHZ/1000);
  else strcpy(value,">");
  feature_row(i,focus,names[i],value);
  if(i<2){unsigned v=i?ui_settings.brightness:ui_settings.volume;
    for(unsigned k=0;k<10;k++)ui_rect(296+k*13,120+i*34,10,3,k<v/10?UI_TEAL:UI_TRACK);}
}
static void settings_draw(unsigned focus) {
  feature_page("SETTINGS");for(unsigned i=0;i<5;i++)setting_row(i,focus);
  feature_message("CPU/LCD CLOCKS ARE FIXED FOR THIS TEST BUILD",NULL);
  feature_footer("UP/DN: CHOOSE   LEFT/RIGHT: CHANGE","B: BACK AND SAVE   A/START: OPEN");
}
static void about(void) {
  feature_page("ABOUT DEVICE");
  feature_row(0,9,"FIRMWARE","2.2.5 TEST");feature_row(1,9,"BOARD","RP2040");
  char value[16];snprintf(value,sizeof value,"%u MHZ",SCARLET_CPU_KHZ/1000);
  feature_row(2,9,"NATIVE CPU",value);
  snprintf(value,sizeof value,"%u X %u",display_width(),display_height());feature_row(3,9,"GAME VIDEO",value);
  snprintf(value,sizeof value,"%u MHZ",SCARLET_LCD_HZ/1000000);feature_row(4,9,"LCD REQUEST",value);
  feature_footer("FPS COUNTS COMPLETED DISPLAY TRANSFERS","B: BACK");feature_release();
  while(!(feature_keys()&UI_B)){console_power_ui_tick();sleep_ms(5);}
  feature_release();
}
void feature_settings(void) {
  unsigned focus=0;settings_draw(focus);feature_release();uint8_t last=0;uint32_t repeat=0;
  for(;;){
    uint8_t e=menu_edge(&last,&repeat);unsigned old=focus;
    if(e&UI_B)break;
    if(e&UI_UP)focus=focus?focus-1:4;else if(e&(UI_DOWN|UI_SELECT))focus=(focus+1)%5;
    if(focus!=old){setting_row(old,focus);setting_row(focus,focus);}
    else if(focus==3&&(e&(UI_A|UI_START|UI_RIGHT))){about();settings_draw(focus);last=0;}
    else if(focus==4&&(e&(UI_A|UI_START|UI_RIGHT))){console_power_page();settings_draw(focus);last=0;}
    else if(focus<2&&(e&(UI_LEFT|UI_RIGHT))){
      uint8_t *v=focus?&ui_settings.brightness:&ui_settings.volume;unsigned min=focus?10:0;
      unsigned before=*v;
      if((e&UI_RIGHT)&&*v<100)*v+=10;else if((e&UI_LEFT)&&*v>min)*v-=10;
      if(*v!=before){ui_volume=ui_settings.volume;if(focus)ui_apply_brightness(*v);setting_row(focus,focus);}
    }
    sleep_ms(5);
  }
  if(!persist()){
    feature_message("SETTINGS WRITE FAILED - PRESS B",NULL);feature_release();
    while(!(feature_keys()&UI_B))sleep_ms(5);
  }
  feature_release();ui_invalidate();
}
void console_card_error(void) {
  ui_card_error(3);feature_release();
  for(;;){uint8_t k=feature_keys();
    console_power_ui_tick();
    if(k&UI_RIGHT){feature_settings();ui_card_error(3);}
    if(k&UI_A){feature_release();return;}sleep_ms(5);
  }
}
unsigned console_menu(unsigned old_selected) {
  original_audio_stop();console_input_reset();selected=old_selected<ui_game_count()?old_selected:0;
  ui_invalidate();ui_menu_draw(true);uint8_t last=0;uint32_t repeat=0;
  for(;;){
    uint8_t e=menu_edge(&last,&repeat);unsigned old=selected,n=ui_game_count();
    if(e&UI_RIGHT){feature_settings();ui_menu_draw(true);last=0;}
    else if(n&&(e&UI_UP))selected=selected?selected-1:n-1;
    else if(n&&(e&(UI_DOWN|UI_SELECT)))selected=(selected+1)%n;
    if(old!=selected)ui_menu_draw(false);
    if(e&UI_B){feature_release();return 0x10000u;}
    if(n&&(e&(UI_A|UI_START))){feature_release();return selected;}
    sleep_ms(5);
  }
}
void original_video_wait_idle(void){}
void original_video_stop(void){native_video_stop();}
bool original_video_start(unsigned scale){(void)scale;native_video_start();return true;}
bool original_guard_pause(void){return false;}
void original_guard_resume(bool previous){(void)previous;}
bool original_addon_frame(uint8_t joypad,bool render){(void)joypad;(void)render;return true;}
