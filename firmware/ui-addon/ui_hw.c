#include "ui.h"
#include "game_library.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "hardware/spi.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"
#include <stddef.h>

/* Exact ABI of the SHA-pinned v0.9-B, built with short enums. */
_Static_assert(sizeof(game_entry_t)==332 && offsetof(game_entry_t,status)==329,"Base ROM library ABI mismatch");
#define GAMES ((const game_entry_t *)0x2001adb8u)
#define CONFIG_OFFSET 0x7f000u
extern void original_display_init(void);
extern void original_display_select_bus(void);
extern void original_fill_rect(uint16_t,uint16_t,uint16_t,uint16_t,uint16_t);
extern void original_lcd_window(uint16_t,uint16_t,uint16_t,uint16_t);
extern bool original_storage_mount(void);
extern bool original_prepare_rom(const char*,const uint8_t**,size_t*);
extern FRESULT original_scan_games(game_entry_t*,size_t,size_t*,bool*);
extern FRESULT original_f_read(FIL*,void*,UINT,UINT*);
extern void original_flash_erase(uint32_t,size_t);
extern void original_flash_program(uint32_t,const uint8_t*,size_t);

unsigned ui_game_count(void){return *(const uint32_t*)0x2001adb4u;}
unsigned ui_game_selected(void){return *(const uint32_t*)0x2001e220u;}
unsigned ui_library_error(void){return *(const uint8_t*)0x2001e258u;}
const char *ui_game_label(unsigned i){return i<ui_game_count() && i<32?GAMES[i].label:"";}
bool ui_game_color(unsigned i){return i<32 && GAMES[i].color;}
unsigned ui_game_status(unsigned i){return i<32?GAMES[i].status:4;}
void ui_rect(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t color){original_fill_rect(x,y,w,h,color);}
void ui_pixels_begin(unsigned x,unsigned y,unsigned w,unsigned h){
 original_display_select_bus();original_lcd_window(x,y,x+w-1,y+h-1);
 gpio_put(8,1);gpio_put(5,0);sleep_us(1);
}
void ui_pixels_row(const uint8_t *p,unsigned n){spi_write_blocking(spi0,p,n);}
void ui_pixels_end(void){sleep_us(1);gpio_put(5,1);sleep_us(1);}
void ui_apply_brightness(unsigned v){
 if(v<10)v=10;
 if(v>100)v=100;
 /* GP10 = PWM slice 5/A. No interrupts, DMA, or shared clock changes. */
 unsigned slice=pwm_gpio_to_slice_num(10);
 pwm_set_enabled(slice,false);pwm_set_clkdiv_int_frac(slice,8,0);
 pwm_set_wrap(slice,999);pwm_set_counter(slice,0);
 pwm_set_gpio_level(10,v*10);gpio_set_function(10,GPIO_FUNC_PWM);pwm_set_enabled(slice,true);
}
static void sd_bus(void){
 gpio_put(5,1);gpio_put(3,1);
 spi_set_format(spi0,8,SPI_CPOL_0,SPI_CPHA_0,SPI_MSB_FIRST);
 spi_set_baudrate(spi0,12500000u); /* Same requested speed as the base image. */
}
static uint8_t keys(void){
 static const uint8_t pins[]={15,26,28,27,14,2,0,1};uint8_t k=0;
 for(unsigned i=0;i<8;i++)if(!gpio_get(pins[i]))k|=1u<<i;
 return k;
}
static void release(void){
 unsigned released=0;
 while(released<6){if(keys())released=0;else released++;sleep_ms(5);}
}
static bool persist(void){
 uint8_t page[256];for(unsigned i=0;i<256;i++)page[i]=255;ui_make_record(page);
 const uint8_t *stored=(const uint8_t *)(0x10000000u+CONFIG_OFFSET);
 bool same=true;for(unsigned i=0;i<16;i++)if(page[i]!=stored[i])same=false;
 if(same)return true;
 /* Called ONLY from the stopped-core launcher. One reserved sector below
  * the unchanged 0x80000 ROM cache, never a ROM/save sector. A torn write
  * is rejected on next boot and falls back to visible 100% brightness. */
 uint32_t irq=save_and_disable_interrupts();
 original_flash_erase(CONFIG_OFFSET,4096);
 original_flash_program(CONFIG_OFFSET,page,256);
 restore_interrupts(irq);
 for(unsigned i=0;i<16;i++)if(page[i]!=stored[i])return false;
 return true;
}
static void settings_screen(void){
 ui_settings_draw();release();uint8_t last=0;uint32_t repeat=0;
 for(;;){
  uint8_t k=keys();
  if(k!=last){sleep_ms(25);if(keys()!=k)continue;}
  uint8_t edge=k&~last;uint32_t now=(uint32_t)time_us_64();
  if(edge)repeat=now+350000u;
  else if((k&(UI_UP|UI_DOWN|UI_LEFT|UI_RIGHT)) && (int32_t)(now-repeat)>=0){
   edge=k&(UI_UP|UI_DOWN|UI_LEFT|UI_RIGHT);repeat=now+140000u;
  }
  last=k;
  if(edge && ui_settings_key(edge))break;
  sleep_ms(5);
 }
 if(!persist()){
  ui_rect(16,286,448,34,UI_SURFACE);
  ui_text(16,292,ui_settings.language?"НЕ УДАЛОСЬ СОХРАНИТЬ НАСТРОЙКИ":"SETTINGS COULD NOT BE SAVED",UI_TEXT,UI_SURFACE,1,72);
  ui_text(16,306,ui_settings.language?"ОНИ ДЕЙСТВУЮТ ДО ПЕРЕЗАПУСКА - B":"ACTIVE UNTIL RESTART - PRESS B",UI_TEXT,UI_SURFACE,1,72);
  release();while(!(keys()&UI_B))sleep_ms(5);
 }
 release();ui_invalidate();
}
bool ui_boot_display(bool mounted){
 original_display_init();ui_init((const uint8_t *)(0x10000000u+CONFIG_OFFSET));
 if(mounted)return true;
 ui_card_error(3);release();
 for(;;){
  uint8_t k=keys();
  if(k){sleep_ms(25);if(keys()!=k)continue;
   if(k&UI_RIGHT){settings_screen();ui_card_error(3);}
   else if(k&UI_A){
    ui_text(30,250,ui_settings.language?"ПРОВЕРКА КАРТЫ...":"CHECKING CARD...",UI_TEAL,UI_BG,1,60);
    if(original_storage_mount()){release();ui_invalidate();return true;}
    ui_card_error(3);
   }
   release();
  }
  sleep_ms(5);
 }
}
uint8_t ui_menu_input(uint8_t edge){
 if(edge&UI_RIGHT){settings_screen();ui_menu_draw(true);return 0;}
 if(ui_library_error() && (edge&UI_A))return UI_B; /* retry failed scan */
 return edge;
}
void ui_menu_full(void){ui_menu_draw(true);}
void ui_menu_update(void){ui_menu_draw(false);}
FRESULT ui_scan_games(game_entry_t*g,size_t cap,size_t*n,bool*limited){
 /* A removed/reinserted card needs a fresh mount, not stale FatFs state. */
 if(!original_storage_mount()){*n=0;*limited=false;return FR_NOT_READY;}
 return original_scan_games(g,cap,n,limited);
}
bool ui_prepare_rom(const char *path,const uint8_t **rom,size_t *size){
 ui_loading();bool ok=original_prepare_rom(path,rom,size);ui_invalidate();return ok;
}
FRESULT ui_rom_read(FIL *f,void *data,UINT n,UINT *got){
 FRESULT r=original_f_read(f,data,n,got);
 ui_spinner_tick((uint32_t)time_us_64());sd_bus();return r;
}
void ui_rom_erase(uint32_t offset,size_t count){
 /* Same erase range, in aligned 64 KiB chunks. XIP is restored by each SDK
  * call before drawing. No timer ISR runs during flash programming. */
 while(count){size_t n=count>65536?65536:count;
  original_flash_erase(offset,n);offset+=n;count-=n;
  ui_spinner_tick((uint32_t)time_us_64());
 }
 sd_bus();
}
