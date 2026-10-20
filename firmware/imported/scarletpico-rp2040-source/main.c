#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <stdatomic.h>
#include <setjmp.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "hardware/clocks.h"
#include "hardware/vreg.h"
#include "ff.h"
#include "sd_card.h"
#include "config.h"
#include "display.h"
#include "video_math.h"
#include "console.h"
#include "console_power.h"
#include "../../vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu/minigb_apu.h"
#define PEANUT_GB_HOT __attribute__((section(".time_critical.gb_core")))
#include "peanut_gb.h"

// Core 0 owns emulation, menu, SD and flash. Core 1 owns LCD during a game.
// SD is accessed only after core 1 exits: these devices share one SPI bus.
static struct gb_s gb;
static uint8_t cart_ram[MAX_SAVE_SIZE];
static uint8_t flash_page[FLASH_SECTOR_SIZE] __attribute__((aligned(4)));
static uint16_t frames[FRAME_BUFFERS][160*144] __attribute__((aligned(4)));
enum buffer_state {FREE,WRITING,READY,DISPLAYING};
static enum buffer_state states[FRAME_BUFFERS];
static spin_lock_t *frame_lock;
static int writing;
static atomic_bool stop_video, video_exited;
static atomic_uint emu_count, lcd_count, drop_count;
static atomic_uint emu_fps, lcd_fps, display_drops;
static atomic_uint error_code, error_address;
static uint32_t rom_size, save_size;
static bool save_dirty;
static const uint8_t *rom=(const uint8_t *)(XIP_BASE+ROM_FLASH_OFFSET);
static const uint8_t buttons[8]=BUTTON_PINS;
static FATFS fs;
static char save_path[320], rtc_path[320];
static uint16_t dmg_palette[]={0xefbd,0xad55,0x52aa,0x1082};
static jmp_buf core_escape;
static bool core_running;

static uint8_t keys(void) {
  uint32_t levels=gpio_get_all();uint8_t pressed=0;
  for(unsigned i=0;i<8;i++)if(!(levels&(1u<<buttons[i])))pressed|=1u<<i;
  return pressed;
}
static void released(void) {while(keys())sleep_ms(10);sleep_ms(20);}
static uint8_t wait_key(void) {
  released();uint8_t a;
  do{sleep_ms(10);a=keys();}while(!a);
  sleep_ms(20);return keys();
}
static void message(const char *a,const char *b) {
  console_message(a,b);
}
static uint8_t __not_in_flash_func(rom_read)(struct gb_s *g,uint_fast32_t addr) {
  return addr<rom_size?rom[addr]:0xff;
}
static uint8_t __not_in_flash_func(ram_read)(struct gb_s *g,uint_fast32_t addr) {
  return addr<save_size?cart_ram[addr]:0xff;
}
static void __not_in_flash_func(ram_write)(struct gb_s *g,uint_fast32_t addr,uint8_t value) {
  if(addr<save_size&&cart_ram[addr]!=value){cart_ram[addr]=value;save_dirty=true;}
}
static void emulation_error(struct gb_s *g,enum gb_error_e e,uint16_t addr) {
  atomic_store(&error_address,addr);atomic_store(&error_code,(unsigned)e+1);
  /* Peanut-GB requires its fatal-error callback not to return. Catch it in
   * the front-end instead of continuing execution with an invalid opcode. */
  if(core_running)longjmp(core_escape,1);
}
static void __not_in_flash_func(draw_line)(struct gb_s *g,const uint8_t *pixels,uint_fast8_t line) {
  if(line>=144)return;
  uint16_t *out=frames[writing]+line*160;
  if(g->cgb.cgbMode) {
    for(unsigned x=0;x<160;x++) {
      // Peanut-GB's fixed palette is RGB555. Convert once to LCD RGB565,
      // duplicating the green high bit to retain 5->6 bit dynamic range.
      uint16_t c=g->cgb.fixPalette[pixels[x]&63u];
      out[x]=color555_to565(c);
    }
  } else for(unsigned x=0;x<160;x++)out[x]=dmg_palette[pixels[x]&3u];
}

/* Keep this ownership transition callable for compiled ARM regression tests. */
static __attribute__((noinline)) void publish_frame(void) {
  uint32_t irq=spin_lock_blocking(frame_lock);
  for(unsigned i=0;i<FRAME_BUFFERS;i++)if(states[i]==READY) {
    states[i]=FREE;atomic_fetch_add(&drop_count,1);
  }
  int next=-1;
  for(unsigned i=0;i<FRAME_BUFFERS;i++)if(states[i]==FREE){next=i;break;}
  /* RP2040 has two buffers. Never block emulation/audio or overwrite a
   * DISPLAYING buffer: keep WRITING and omit this presentation when busy. */
  if(next<0){atomic_fetch_add(&drop_count,1);spin_unlock(frame_lock,irq);return;}
  states[writing]=READY;
  writing=next;states[writing]=WRITING;
  spin_unlock(frame_lock,irq);__sev();
}
static void video_worker(void) {
  bool initial=true;
  uint64_t status_time=0;
  while(!atomic_load(&stop_video)) {
    int selected=-1;
    uint32_t irq=spin_lock_blocking(frame_lock);
    for(unsigned i=0;i<FRAME_BUFFERS;i++)if(states[i]==READY){selected=i;states[i]=DISPLAYING;break;}
    spin_unlock(frame_lock,irq);
    if(selected<0){__wfe();continue;}
    if(initial){display_game_speed();initial=false;}
    display_frame(frames[selected]);
    atomic_fetch_add(&lcd_count,1);
    uint64_t now=time_us_64();
    if(now-status_time>=1000000) {
      display_status(atomic_load(&lcd_fps),atomic_load(&emu_fps),atomic_load(&display_drops));
      console_power_game();
      status_time=now;
    }
    irq=spin_lock_blocking(frame_lock);states[selected]=FREE;spin_unlock(frame_lock,irq);
  }
  atomic_store(&video_exited,true);__sev();
  while(true)__wfe();
}
void native_video_start(void) {
  memset(states,0,sizeof(states));writing=0;states[0]=WRITING;
  // A game may leave LCD disabled; retain a deterministic black frame.
  memset(frames,0,sizeof(frames));
  atomic_store(&stop_video,false);atomic_store(&video_exited,false);
  atomic_store(&emu_count,0);atomic_store(&lcd_count,0);atomic_store(&drop_count,0);
  atomic_store(&emu_fps,0);atomic_store(&lcd_fps,0);atomic_store(&display_drops,0);
  display_game_speed();display_clear(0);
  multicore_reset_core1();multicore_launch_core1(video_worker);
}
void native_video_stop(void) {
  atomic_store(&stop_video,true);__sev();
  while(!atomic_load(&video_exited))tight_loop_contents();
  multicore_reset_core1();display_sd_speed();
}

static bool read_file(const char *path,void *buf,UINT bytes) {
  display_sd_speed();
  FIL f;UINT got=0;FRESULT r=f_open(&f,path,FA_READ);
  if(r!=FR_OK)return false;
  r=f_read(&f,buf,bytes,&got);FRESULT closed=f_close(&f);
  return r==FR_OK&&closed==FR_OK&&got==bytes;
}
static bool write_file(const char *path,const void *buf,UINT bytes) {
  display_sd_speed();
  // Commit via a temporary file. Preserve a prior save as .bak rather than
  // truncating it before the new data has reached the SD card.
  char temp[340],backup[340];
  snprintf(temp,sizeof(temp),"%s.tmp",path);snprintf(backup,sizeof(backup),"%s.bak",path);
  FIL f;UINT wrote=0;FRESULT r=f_open(&f,temp,FA_CREATE_ALWAYS|FA_WRITE);
  if(r!=FR_OK)return false;
  r=f_write(&f,buf,bytes,&wrote);
  FRESULT sync=f_sync(&f),closed=f_close(&f);
  if(r!=FR_OK||sync!=FR_OK||closed!=FR_OK||wrote!=bytes)return false;
  FILINFO info;
  if(f_stat(path,&info)==FR_OK) {
    FRESULT old=f_unlink(backup);
    if(old!=FR_OK&&old!=FR_NO_FILE)return false;
    if(f_rename(path,backup)!=FR_OK)return false;
  }
  return f_rename(temp,path)==FR_OK;
}
static bool save_game(void) {
  if(save_size&&save_dirty) {
    if(!write_file(save_path,cart_ram,save_size))return false;
    save_dirty=false;
  }
  if(gb.mbc==3&&!write_file(rtc_path,gb.cart_rtc,5))return false;
  return true;
}
static bool load_rom(const char *path) {
  display_sd_speed();
  FIL f;
  if(f_open(&f,path,FA_READ)!=FR_OK){message("ROM OPEN FAILED",path);return false;}
  rom_size=f_size(&f);
  if(rom_size<0x150||rom_size>PICO_FLASH_SIZE_BYTES-ROM_FLASH_OFFSET) {
    f_close(&f);message("ROM TOO LARGE OR INVALID","RP2040 CACHE: STANDARD ROM UP TO 1 MB");return false;
  }
  ui_invalidate();ui_loading();
  display_sd_speed();
  for(uint32_t offset=0;offset<rom_size;offset+=FLASH_SECTOR_SIZE) {
    UINT got=0;UINT want=rom_size-offset;
    if(want>FLASH_SECTOR_SIZE)want=FLASH_SECTOR_SIZE;
    memset(flash_page,0xff,sizeof(flash_page));
    if(f_read(&f,flash_page,want,&got)!=FR_OK||got!=want) {
      f_close(&f);message("ROM READ FAILED",NULL);return false;
    }
    // No core 1 is running here. Both flash APIs execute from RAM while XIP
    // is unavailable; the source page is also RAM, and IRQs are masked.
    if(memcmp(rom+offset,flash_page,FLASH_SECTOR_SIZE)) {
      uint32_t irq=save_and_disable_interrupts();
      flash_range_erase(ROM_FLASH_OFFSET+offset,FLASH_SECTOR_SIZE);
      flash_range_program(ROM_FLASH_OFFSET+offset,flash_page,FLASH_SECTOR_SIZE);
      restore_interrupts(irq);
    }
    if(memcmp(rom+offset,flash_page,want)) {
      f_close(&f);message("FLASH VERIFY FAILED",NULL);return false;
    }
    ui_spinner_tick((uint32_t)time_us_64());display_sd_speed();
    if(!(offset&0xffff))printf("ROM %lu/%lu\n",(unsigned long)offset,(unsigned long)rom_size);
  }
  f_close(&f);
  /* Front-end validation: the native core indexes fixed ROM/RAM tables. */
  if(rom[0x148]>8||rom[0x149]>5||rom_size!=(32768u<<rom[0x148])){
    message("INVALID ROM HEADER OR SIZE",NULL);return false;
  }
  // Buffer bound is established before callbacks are first used by the core.
  save_size=MAX_SAVE_SIZE;
  console_apu_init();
  if(gb_init(&gb,rom_read,ram_read,ram_write,emulation_error,NULL)!=GB_INIT_NO_ERROR) {
    message("UNSUPPORTED OR INVALID ROM",NULL);return false;
  }
  static const uint32_t ram_sizes[]={0,2048,8192,32768,131072,65536};
  save_size=gb.mbc==2?512:gb.cart_ram?ram_sizes[rom[0x149]]:0;
  if(save_size>MAX_SAVE_SIZE){message("SAVE RAM TOO LARGE",NULL);return false;}
  gb_init_lcd(&gb,draw_line);
  memset(cart_ram,0xff,sizeof(cart_ram));
  f_mkdir("0:/scarlet2040");f_mkdir("0:/scarlet2040/saves");
  const char *name=strrchr(path,'/');name=name?name+1:path;
  snprintf(save_path,sizeof(save_path),"0:/scarlet2040/saves/%s.sav",name);
  snprintf(rtc_path,sizeof(rtc_path),"0:/scarlet2040/saves/%s.rtc",name);
  if(save_size&&!read_file(save_path,cart_ram,save_size)) {
    char backup[340];snprintf(backup,sizeof(backup),"%s.bak",save_path);
    if(!read_file(backup,cart_ram,save_size))memset(cart_ram,0xff,save_size);
  }
  if(gb.mbc==3) {
    if(!read_file(rtc_path,gb.cart_rtc,5))memset(gb.cart_rtc,0,5);
  }
  save_dirty=false;atomic_store(&error_code,0);
  console_state_bind();
  return true;
}
static void play(void) {
  console_input_reset();native_video_start();
  if(!original_audio_start()){
    native_video_stop();message("AUDIO INITIALIZATION FAILED",NULL);wait_key();return;
  }
  uint64_t next=time_us_64(),stats=next,rtc_tick=next;
  uint32_t old_emu=0,old_lcd=0,old_drop=0;
  while(true) {
    uint8_t k=keys();unsigned filtered=features_buttons(k);
    uint64_t now=time_us_64();
    console_power_poll();
    if(pause_pending){
      bool resumed=features_frame(255,true);
      if(exit_requested){exit_requested=false;break;}
      if(!resumed){original_audio_stop();message("RESUME FAILED",NULL);wait_key();break;}
      /* The pause can take minutes. Reset deadlines and stats baselines, not
       * emulator state: no fast-forward catch-up, wrong FPS or stale chord. */
      next=stats=rtc_tick=time_us_64();old_emu=atomic_load(&emu_count);
      old_lcd=atomic_load(&lcd_count);old_drop=atomic_load(&drop_count);filtered=0;
    }
    gb.direct.joypad=(uint8_t)~filtered;
    if(setjmp(core_escape)){core_running=false;break;}
    core_running=true;gb_run_frame(&gb);core_running=false;
    atomic_fetch_add(&emu_count,1);publish_frame();
    console_audio_frame();
    if(atomic_load(&error_code))break;
    now=time_us_64();
    while(now-rtc_tick>=1000000){gb_tick_rtc(&gb);rtc_tick+=1000000;}
    if(now-stats>=1000000) {
      uint32_t ec=atomic_load(&emu_count),lc=atomic_load(&lcd_count),dc=atomic_load(&drop_count);
      uint64_t elapsed=now-stats;
      unsigned ef=((ec-old_emu)*1000000ull+elapsed/2)/elapsed;
      unsigned lf=((lc-old_lcd)*1000000ull+elapsed/2)/elapsed;
      atomic_store(&emu_fps,ef);atomic_store(&lcd_fps,lf);
      atomic_store(&display_drops,dc-old_drop);
      printf("EMU %u LCD %u DROP %u LCD_SPI %u\n",ef,lf,(unsigned)(dc-old_drop),SCARLET_LCD_HZ);
      old_emu=ec;old_lcd=lc;old_drop=dc;stats=now;
    }
    // 70224 clocks / 4194304 Hz = 16,742.706 us; approximately 59.7275 FPS.
    next+=16743;
    now=time_us_64();
    if(now<next)sleep_until(from_us_since_boot(next));
    else if(now-next>16743)next=now; // avoid a backlog after a slow frame
  }
  original_audio_stop();
  if(!atomic_load(&video_exited))native_video_stop();
  bool saved=save_game();
  if(atomic_load(&error_code)) {
    char detail[80];snprintf(detail,sizeof(detail),"ERROR %u PC %04X",atomic_load(&error_code)-1,atomic_load(&error_address));
    message("EMULATION STOPPED",detail);wait_key();
  }
  if(!saved){message("SAVE FAILED - SD ERROR","OLD SAVE REMAINS IN BACKUP IF PRESENT");wait_key();}
  released();
}

typedef struct {char name[256];bool dir;} entry_t;
static entry_t entries[MAX_ENTRIES];
static unsigned entry_count;
static bool is_rom(const char *s) {
  const char *ext=strrchr(s,'.');if(!ext)return false;
  size_t n=strlen(ext);if(n!=3&&n!=4)return false;
  return tolower(ext[1])=='g'&&tolower(ext[2])=='b'&&
    (!ext[3]||(tolower(ext[3])=='c'&&!ext[4]));
}
static int compare_entries(const void *a,const void *b) {
  const entry_t *x=a,*y=b;
  if(x->dir!=y->dir)return y->dir-x->dir;
  return strcmp(x->name,y->name);
}
static bool scan(const char *path) {
  display_sd_speed();
  DIR dir;FILINFO info;entry_count=0;
  if(f_opendir(&dir,path)!=FR_OK)return false;
  while(entry_count<MAX_ENTRIES&&f_readdir(&dir,&info)==FR_OK&&info.fname[0]) {
    if(info.fname[0]=='.')continue;
    bool folder=info.fattrib&AM_DIR;
    if(!folder&&!is_rom(info.fname))continue;
    snprintf(entries[entry_count].name,256,"%s",info.fname);
    entries[entry_count++].dir=folder;
  }
  f_closedir(&dir);qsort(entries,entry_count,sizeof(entries[0]),compare_entries);
  return true;
}
unsigned native_game_count(void){return entry_count;}
const char *native_game_label(unsigned i){return i<entry_count?entries[i].name:"";}
bool native_game_folder(unsigned i){return i<entry_count&&entries[i].dir;}
bool native_game_color(unsigned i){
  const char *p=native_game_label(i);unsigned n=strlen(p);
  return !native_game_folder(i)&&n>=4&&tolower(p[n-1])=='c';
}
void *native_staging(unsigned *n){*n=sizeof frames;return frames;}
unsigned native_core_size(void){return sizeof gb;}
const uint8_t *native_rom(unsigned *n){*n=rom_size;return rom;}
uint8_t *native_save_ram(unsigned *n){*n=save_size;return cart_ram;}
void native_mark_save_dirty(void){save_dirty=save_size!=0;}
void native_core_copy(void *p){
  memcpy(p,&gb,sizeof gb);struct gb_s *saved=p;
  saved->gb_rom_read=NULL;saved->gb_cart_ram_read=NULL;saved->gb_cart_ram_write=NULL;
  saved->gb_error=NULL;saved->gb_serial_tx=NULL;saved->gb_serial_rx=NULL;
  saved->gb_bootrom_read=NULL;saved->display.lcd_draw_line=NULL;saved->direct.priv=NULL;
}
void native_core_restore(const void *p){
  /* Reinstall callbacks from THIS build. Never deserialize code pointers. */
  memcpy(&gb,p,sizeof gb);gb.gb_rom_read=rom_read;gb.gb_cart_ram_read=ram_read;
  gb.gb_cart_ram_write=ram_write;gb.gb_error=emulation_error;
  gb.gb_serial_tx=NULL;gb.gb_serial_rx=NULL;gb.gb_bootrom_read=NULL;
  gb.display.lcd_draw_line=draw_line;gb.direct.priv=NULL;gb.direct.joypad=255;
  atomic_store(&error_code,0);atomic_store(&error_address,0);
}
static void lcd_benchmark(void) {
  // Hold SELECT at power-on to measure actual completed LCD transfers without
  // emulation or SD. A moving white stripe makes repeated-frame counts visible.
  released();display_game_speed();display_clear(0);
  uint64_t stats=time_us_64();unsigned count=0,fps=0,phase=0;
  while(!(keys()&KEY_B)) {
    for(unsigned y=0;y<144;y++)for(unsigned x=0;x<160;x++) {
      uint16_t color=x<53?0xf800:x<106?0x07e0:0x001f;
      if((x+phase)%160<4)color=0xffff;
      frames[0][y*160+x]=color;
    }
    display_frame(frames[0]);count++;phase++;
    uint64_t now=time_us_64();
    if(now-stats>=1000000) {
      fps=(count*1000000ull+(now-stats)/2)/(now-stats);
      display_status(fps,0,0);
      printf("LCD BENCH completed=%u actual_spi=%u width=%u height=%u\n",
        fps,spi_get_baudrate(LCD_SPI),display_width(),display_height());
      count=0;stats=now;
    }
  }
  display_sd_speed();released();
}
int main(void) {
  // Native source build for Cortex-M0+ and the RP2040 SDK startup.
  vreg_set_voltage(VREG_VOLTAGE_1_20);sleep_ms(10);
  if(!set_sys_clock_khz(SCARLET_CPU_KHZ,false))while(true)tight_loop_contents();
  clock_configure(clk_peri,0,CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS,
    clock_get_hz(clk_sys),clock_get_hz(clk_sys));
  stdio_init_all();
  for(unsigned i=0;i<8;i++){gpio_init(buttons[i]);gpio_set_dir(buttons[i],GPIO_IN);gpio_pull_up(buttons[i]);}
  frame_lock=spin_lock_init(spin_lock_claim_unused(true));
  display_init();
  console_power_init((const uint8_t *)(XIP_BASE+SETTINGS_FLASH_OFFSET));
  console_power_poll();
  if(keys()&KEY_SELECT)lcd_benchmark();
  features_boot_ui_init((const uint8_t *)(XIP_BASE+SETTINGS_FLASH_OFFSET));
  printf("RP2040 native CPU=%lu PERI=%lu LCD request=%u\n",(unsigned long)clock_get_hz(clk_sys),(unsigned long)clock_get_hz(clk_peri),SCARLET_LCD_HZ);
  display_sd_speed();
  while(f_mount(&fs,"0:",1)!=FR_OK) {
    console_card_error();display_sd_speed();
  }
  char path[320]="0:/roms";
  if(!scan(path)){strcpy(path,"0:");scan(path);}
  unsigned selected=0;
  while(true) {
    unsigned chosen=console_menu(selected);
    if(chosen==0x10000u) {
      char *p=strrchr(path,'/');if(p)*p=0;
      scan(path);selected=0;
    } else if(chosen<entry_count) {
      selected=chosen;
      char full[600];snprintf(full,sizeof(full),"%s/%s",path,entries[selected].name);
      if(strlen(full)>=sizeof(path)){message("PATH TOO LONG",NULL);wait_key();continue;}
      if(entries[selected].dir){strcpy(path,full);scan(path);selected=0;}
      else if(load_rom(full)){play();scan(path);if(selected>=entry_count)selected=0;}
      else wait_key();
    }
  }
}
