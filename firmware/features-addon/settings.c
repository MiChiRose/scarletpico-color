/* Additional launcher settings; the original menu, font and mixer stay intact. */
#include "features.h"
#include <string.h>

uint8_t cpu_profile;
static unsigned focus;
extern bool check_sys_clock_khz(uint32_t, uint32_t *, uint32_t *, uint32_t *);
extern void set_sys_clock_pll(uint32_t, uint32_t, uint32_t);

const char *feature_tr(const char *en, const char *ru) { return ui_settings.language ? ru : en; }
void feature_error(const char *s) {
 char *dest=(char *)0x2000f960u;unsigned n=0;
 while(s[n] && n<79){dest[n]=s[n];n++;}dest[n]=0;
}
uint8_t feature_keys(void) {
 static const uint8_t pins[] = {15,26,28,27,14,2,0,1};
 uint32_t gpio = *(volatile uint32_t *)0xd0000004u;
 uint8_t k=0;
 for (unsigned i=0;i<8;i++) if (!(gpio & (1u<<pins[i]))) k |= 1u<<i;
 return k;
}
void feature_release(void) {
 unsigned n=0;
 while(n<6) { n=feature_keys()?0:n+1; sleep_ms(5); }
}
void feature_page(const char *title) {
 ui_rect(0,0,480,320,UI_BG); ui_header();
 ui_text(20,65,title,UI_TEXT,UI_BG,2,37);
}
void feature_row(unsigned i,unsigned selected,const char *label,const char *value) {
 unsigned y=94+i*34;
 uint16_t bg=i==selected?UI_SURFACE:UI_BG;
 ui_rect(16,y,448,32,bg);
 if(i==selected) {
  ui_rect(16,y,448,1,UI_ACCENT);ui_rect(16,y+31,448,1,UI_ACCENT);
  ui_rect(16,y,1,32,UI_ACCENT);ui_rect(463,y,1,32,UI_ACCENT);
  ui_text(24,y+9,">",UI_ACCENT,bg,2,1);
 }
 ui_text(44,y+9,label,UI_TEXT,bg,2,value?19:34);
 if(value)ui_text(296,y+9,value,UI_TEXT,bg,2,13);
}
void feature_footer(const char *line1,const char *line2) {
 ui_rect(0,282,480,38,UI_SURFACE);
 ui_text(16,291,line1,UI_TEXT,UI_SURFACE,1,74);
 if(line2)ui_text(16,306,line2,UI_TEXT,UI_SURFACE,1,74);
}
void feature_message(const char *en,const char *ru) {
 ui_rect(16,264,448,14,UI_BG);
 ui_text(20,267,feature_tr(en,ru),UI_TEAL,UI_BG,1,73);
}
void features_ui_init(const uint8_t *p) {
 original_ui_init(p);
 cpu_profile=2; /* Same tested 200 MHz default as the rollback. */
 if(p && p[16]=='S' && p[17]=='P' && p[18]=='C' && p[19]==1 && p[20]<3) {
  bool ok=true;
  for(unsigned i=0;i<8;i++) if((uint8_t)(p[16+i]^p[24+i])!=255)ok=false;
  if(ok)cpu_profile=p[20];
 }
}
static void voltage(unsigned code) {
 volatile uint32_t *vreg=(volatile uint32_t *)0x40064000u;
 *vreg=(*vreg & ~0xf0u) | (code<<4);
 sleep_ms(10);
}
void features_game_clock(uint32_t old_vco,uint32_t old_p1,uint32_t old_p2) {
 (void)old_vco;(void)old_p1;(void)old_p2;
 static const uint32_t khz[]={125000,170000,200000};
 uint32_t rate=khz[cpu_profile<3?cpu_profile:2],vco,p1,p2;
 if(!check_sys_clock_khz(rate,&vco,&p1,&p2)) {
  rate=200000;check_sys_clock_khz(rate,&vco,&p1,&p2);
 }
 /* Both cores/video and I2S are stopped at this sole launch call site.
  * The pinned SDK's set_sys_clock_pll also sources clk_peri from clk_sys.
  * USB remains on its separate 48 MHz PLL. Never change game pacing. */
 if(rate>125000)voltage(12); /* 1.15V BEFORE increasing frequency. */
 set_sys_clock_pll(vco,p1,p2);
 if(rate==125000)voltage(11); /* 1.10V AFTER reducing frequency. */
}
void features_menu_clock(uint32_t vco,uint32_t p1,uint32_t p2) {
 set_sys_clock_pll(vco,p1,p2);voltage(11);
}
static void setting_row(unsigned i) {
 const char *labels_en[]={"LANGUAGE","VOLUME","BRIGHTNESS","CPU FREQUENCY","ABOUT DEVICE"};
 const char *labels_ru[]={"ЯЗЫК","ГРОМКОСТЬ","ЯРКОСТЬ","ЧАСТОТА CPU","ОБ УСТРОЙСТВЕ"};
 char value[14];
 if(i==4)memcpy(value,">",2);
 else if(i==0)memcpy(value,ui_settings.language?"< РУС >":"< ENG >",ui_settings.language?11:8);
 else if(i==3) {
  static const char *s[]={"< 125 MHZ >","< 170 MHZ >","< 200 MHZ >"};
  memcpy(value,s[cpu_profile],12);
 } else {
  unsigned v=i==1?ui_settings.volume:ui_settings.brightness,j=0;
  value[j++]='<';value[j++]=' ';
  if(v>=100)value[j++]='1';
  if(v>=10)value[j++]='0'+(v/10)%10;
  value[j++]='0'+v%10;value[j++]='%';value[j++]=' ';value[j++]='>';value[j]=0;
 }
 feature_row(i,focus,ui_settings.language?labels_ru[i]:labels_en[i],value);
 if(i==1 || i==2) {
  unsigned v=i==1?ui_settings.volume:ui_settings.brightness;
  for(unsigned k=0;k<10;k++)ui_rect(296+k*13,120+i*34,10,3,k<v/10?UI_TEAL:UI_TRACK);
 }
}
static void description(void) {
 const char *en[]={"125 MHZ: ECO | APPLIES ON NEXT GAME LAUNCH","170 MHZ: BALANCED | APPLIES ON NEXT GAME LAUNCH","200 MHZ: PERFORMANCE (DEFAULT) | NEXT GAME LAUNCH"};
 const char *ru[]={"125 МГЦ: ЭКОНОМИЧНЫЙ | СО СЛЕДУЮЩЕГО ЗАПУСКА ИГРЫ","170 МГЦ: СБАЛАНСИРОВАННЫЙ | СО СЛЕДУЮЩЕГО ЗАПУСКА ИГРЫ","200 МГЦ: ПО УМОЛЧАНИЮ | СО СЛЕДУЮЩЕГО ЗАПУСКА ИГРЫ"};
 feature_message(en[cpu_profile],ru[cpu_profile]);
}
static void settings_draw(void) {
 feature_page(feature_tr("SETTINGS","НАСТРОЙКИ"));
 for(unsigned i=0;i<5;i++)setting_row(i);
 description();
 feature_footer(feature_tr("UP/DN: CHOOSE   LEFT/RIGHT: CHANGE","ВВЕРХ/ВНИЗ: ПУНКТ   ВЛЕВО/ВПРАВО: ИЗМЕНИТЬ"),feature_tr("B: BACK AND SAVE   A/START: OPEN ABOUT","B: НАЗАД И СОХРАНИТЬ   A/START: ОБ УСТРОЙСТВЕ"));
}
bool features_settings_key(uint8_t key) {
 if(key&UI_B)return true;
 unsigned old=focus;
 if(key&UI_UP)focus=focus?focus-1:4;
 else if(key&(UI_DOWN|UI_SELECT))focus=(focus+1)%5;
 if(focus!=old){setting_row(old);setting_row(focus);return false;}
 if(focus==4) {
  if(key&(UI_A|UI_START|UI_RIGHT)){feature_about();settings_draw();}
  return false;
 }
 if(!(key&(UI_LEFT|UI_RIGHT)))return false;
 bool right=key&UI_RIGHT;
 if(focus==0){ui_settings.language^=1;settings_draw();}
 else if(focus==3){cpu_profile=(cpu_profile+(right?1u:2u))%3u;setting_row(3);description();}
 else {
  uint8_t *v=focus==1?&ui_settings.volume:&ui_settings.brightness;
  unsigned min=focus==1?0:10;
  if(right && *v<100)*v+=10;
  else if(!right && *v>min)*v-=10;
  ui_volume=ui_settings.volume;
  if(focus==2)ui_apply_brightness(*v);
  setting_row(focus);
 }
 return false;
}
static bool persist(void) {
 uint8_t p[256];memset(p,255,sizeof p);ui_make_record(p);
 p[16]='S';p[17]='P';p[18]='C';p[19]=1;p[20]=cpu_profile;
 p[21]=p[22]=p[23]=0;
 for(unsigned i=0;i<8;i++)p[24+i]=(uint8_t)~p[16+i];
 const uint8_t *stored=(const uint8_t *)0x1007f000u;
 if(!memcmp(stored,p,32))return true;
 uint32_t irq=features_irq_off();
 original_flash_erase(0x7f000,4096);original_flash_program(0x7f000,p,256);
 features_irq_restore(irq);
 return !memcmp(stored,p,32);
}
void feature_settings(void) {
 focus=0;settings_draw();feature_release();
 uint8_t last=0;uint32_t repeat=0;
 for(;;) {
  uint8_t k=feature_keys();
  if(k!=last){sleep_ms(25);if(feature_keys()!=k)continue;}
  uint8_t edge=k&~last;uint32_t now=(uint32_t)time_us_64();
  if(edge)repeat=now+350000;
  else if((k&0xf0) && (int32_t)(now-repeat)>=0){edge=k&0xf0;repeat=now+140000;}
  last=k;if(edge && features_settings_key(edge))break;sleep_ms(5);
 }
 if(!persist()) {
  feature_message("SETTINGS WRITE FAILED - PRESS B","ОШИБКА ЗАПИСИ НАСТРОЕК - НАЖМИТЕ B");
  feature_release();while(!(feature_keys()&UI_B))sleep_ms(5);
 }
 feature_release();ui_invalidate();
}
