/* Launcher only. No emulator, video-worker, ROM timing or clock changes. */
#include "ui.h"

ui_settings_t ui_settings;
uint8_t ui_volume;
static uint8_t text_row[960]; /* Single scanline, never a full framebuffer. */
static unsigned focus, last_selected, last_count, last_error;
static bool menu_valid, loading, loading_legacy;
static uint32_t spinner_time;
static unsigned spinner_phase;

static const uint8_t digits[10][5] = {
 {0x3e,0x51,0x49,0x45,0x3e},{0,0x42,0x7f,0x40,0},
 {0x42,0x61,0x51,0x49,0x46},{0x21,0x41,0x45,0x4b,0x31},
 {0x18,0x14,0x12,0x7f,0x10},{0x27,0x45,0x45,0x45,0x39},
 {0x3c,0x4a,0x49,0x49,0x30},{1,0x71,9,5,3},
 {0x36,0x49,0x49,0x49,0x36},{6,0x49,0x49,0x29,0x1e}};
static const uint8_t latin[26][5] = {
 {0x7e,0x11,0x11,0x11,0x7e},{0x7f,0x49,0x49,0x49,0x36},
 {0x3e,0x41,0x41,0x41,0x22},{0x7f,0x41,0x41,0x22,0x1c},
 {0x7f,0x49,0x49,0x49,0x41},{0x7f,9,9,9,1},
 {0x3e,0x41,0x49,0x49,0x7a},{0x7f,8,8,8,0x7f},
 {0,0x41,0x7f,0x41,0},{0x20,0x40,0x41,0x3f,1},
 {0x7f,8,0x14,0x22,0x41},{0x7f,0x40,0x40,0x40,0x40},
 {0x7f,2,0xc,2,0x7f},{0x7f,4,8,0x10,0x7f},
 {0x3e,0x41,0x41,0x41,0x3e},{0x7f,9,9,9,6},
 {0x3e,0x41,0x51,0x21,0x5e},{0x7f,9,0x19,0x29,0x46},
 {0x46,0x49,0x49,0x49,0x31},{1,1,0x7f,1,1},
 {0x3f,0x40,0x40,0x40,0x3f},{0x1f,0x20,0x40,0x20,0x1f},
 {0x3f,0x40,0x38,0x40,0x3f},{0x63,0x14,8,0x14,0x63},
 {7,8,0x70,8,7},{0x61,0x51,0x49,0x45,0x43}};
/* А..Я, compact Cyrillic columns. Ё reuses Е with upper dots. */
static const uint8_t cyrillic[32][5] = {
 {0x7e,0x11,0x11,0x11,0x7e},{0x7f,0x49,0x49,0x49,0x31},
 {0x7f,0x49,0x49,0x49,0x36},{0x7f,1,1,1,1},
 {0x60,0x3e,0x21,0x3f,0x60},{0x7f,0x49,0x49,0x49,0x41},
 {0x77,8,0x7f,8,0x77},{0x22,0x41,0x49,0x49,0x36},
 {0x7f,0x20,0x10,8,0x7f},{0x7c,0x41,0x22,0x11,0x7c},
 {0x7f,8,0x14,0x22,0x41},{0x40,0x3e,1,1,0x7f},
 {0x7f,2,0xc,2,0x7f},{0x7f,8,8,8,0x7f},
 {0x3e,0x41,0x41,0x41,0x3e},{0x7f,1,1,1,0x7f},
 {0x7f,9,9,9,6},{0x3e,0x41,0x41,0x41,0x22},
 {1,1,0x7f,1,1},{7,0x48,0x48,0x48,0x3f},
 {0x1c,0x22,0x7f,0x22,0x1c},{0x63,0x14,8,0x14,0x63},
 {0x3f,0x20,0x20,0x3f,0x60},{0xf,8,8,8,0x7f},
 {0x7f,0x40,0x7f,0x40,0x7f},{0x3f,0x20,0x3f,0x20,0x7f},
 {1,0x7f,0x48,0x48,0x30},{0x7f,0x48,0x30,0,0x7f},
 {0x7f,0x48,0x48,0x48,0x30},{0x22,0x41,0x49,0x49,0x3e},
 {0x7f,8,0x3e,0x41,0x3e},{0x46,0x29,0x19,9,0x7f}};

static unsigned next(const char **s) {
 unsigned a=(uint8_t)*(*s)++;
 if (a<128) return a;
 unsigned b=(uint8_t)**s;
 if ((a==0xd0 || a==0xd1) && b>=0x80 && b<=0xbf) {
  ++*s; return ((a&31)<<6)|(b&63);
 }
 return '?';
}
static void glyph(unsigned c, uint8_t g[5]) {
 for (unsigned i=0;i<5;i++) g[i]=0;
 if (c>='a' && c<='z') c-=32;
 if (c>=0x430 && c<=0x44f) c-=32;
 const uint8_t *p=0;
 if (c>='0' && c<='9') p=digits[c-'0'];
 else if (c>='A' && c<='Z') p=latin[c-'A'];
 else if (c>=0x410 && c<=0x42f) p=cyrillic[c-0x410];
 else if (c==0x401 || c==0x451) p=cyrillic[5];
 if (p) { for(unsigned i=0;i<5;i++) g[i]=p[i]; return; }
 switch(c) {
 case '-': for(unsigned i=0;i<5;i++) g[i]=8; break;
 case ':': g[2]=0x36; break;
 case '.': g[2]=0x60; break;
 case '/': for(unsigned i=0;i<5;i++) g[i]=0x20>>i; break;
 case '%': g[0]=0x63;g[1]=0x13;g[2]=8;g[3]=0x64;g[4]=0x63;break;
 case '<':g[1]=8;g[2]=0x14;g[3]=0x22;break;
 case '>':g[1]=0x22;g[2]=0x14;g[3]=8;break;
 case '+':g[1]=8;g[2]=0x3e;g[3]=8;break;
 case '!':g[2]=0x5f;break;
 case '?':g[0]=2;g[1]=1;g[2]=0x51;g[3]=9;g[4]=6;break;
 case '(':g[2]=0x3e;g[3]=0x41;break;
 case ')':g[1]=0x41;g[2]=0x3e;break;
 case '_':for(unsigned i=0;i<5;i++)g[i]=0x40;break;
 default:break;
 }
}
void ui_text(unsigned x,unsigned y,const char*s,uint16_t fg,uint16_t bg,unsigned scale,unsigned limit) {
 if (!scale || scale>3 || x>=480 || y>=320) return;
 uint8_t gs[80][5]; unsigned n=0, cap=(480-x)/(6*scale);
 if(cap>limit)cap=limit;
 while(*s && n<cap && n<80) { glyph(next(&s),gs[n]);++n; }
 if(!n)return;
 unsigned w=n*6*scale,h=7*scale;if(h>320-y)h=320-y;
 ui_pixels_begin(x,y,w,h);
 for(unsigned r=0;r<h;r++) {
  unsigned i=0;
  for(unsigned ch=0;ch<n;ch++)for(unsigned col=0;col<6;col++) {
   uint16_t color=col<5 && (gs[ch][col]&(1u<<(r/scale)))?fg:bg;
   for(unsigned k=0;k<scale;k++){text_row[i++]=color>>8;text_row[i++]=color;}
  }
  ui_pixels_row(text_row,w*2);
 }
 ui_pixels_end();
}
static const char *tr(const char *en,const char *ru){return ui_settings.language?ru:en;}
static void text(unsigned x,unsigned y,const char*s,unsigned size){ui_text(x,y,s,UI_TEXT,UI_BG,size,80);}
static void centered(unsigned y,const char *s,unsigned size){
 const char *p=s;unsigned n=0;while(*p){next(&p);n++;}
 unsigned width=n*6*size; text(width<480?(480-width)/2:0,y,s,size);
}
static void border(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t c){
 ui_rect(x,y,w,1,c);ui_rect(x,y+h-1,w,1,c);ui_rect(x,y,1,h,c);ui_rect(x+w-1,y,1,h,c);
}
static void arrow(unsigned x,unsigned y,uint16_t c){
 for(unsigned i=0;i<5;i++)ui_rect(x+i,y+i,1,9-2*i,c);
}
static void number(unsigned v,char out[5]){
 unsigned n=0;if(v>=100)out[n++]='0'+v/100;
 if(v>=10)out[n++]='0'+v/10%10;
 out[n++]='0'+v%10;out[n]=0;
}
void ui_make_record(uint8_t p[16]) {
 for(unsigned i=0;i<16;i++)p[i]=0;
 p[0]='S';p[1]='P';p[2]='U';p[3]='I';p[4]=1;
 p[5]=ui_settings.language;p[6]=ui_settings.volume;p[7]=ui_settings.brightness;
 for(unsigned i=0;i<8;i++)p[i+8]=(uint8_t)~p[i];
}
void ui_init(const uint8_t p[16]) {
 bool ok=p && p[0]=='S' && p[1]=='P' && p[2]=='U' && p[3]=='I' && p[4]==1;
 if(ok)for(unsigned i=0;i<8;i++)if((uint8_t)(p[i]^p[i+8])!=255)ok=false;
 if(ok)ok=p[5]<=1 && p[6]<=100 && p[6]%10==0 && p[7]>=10 && p[7]<=100 && p[7]%10==0;
 ui_settings.language=ok?p[5]:0;
 ui_settings.volume=ok?p[6]:50;
 ui_settings.brightness=ok?p[7]:100;
 ui_volume=ui_settings.volume;focus=0;menu_valid=loading=loading_legacy=false;
 ui_apply_brightness(ui_settings.brightness);
}
void ui_header(void){
 ui_rect(0,0,480,46,UI_SURFACE);
 ui_text(16,13,"SCARLET",UI_ACCENT,UI_SURFACE,3,7);
 ui_text(142,13,"PICO",UI_TEXT,UI_SURFACE,3,4);
 ui_text(224,20,"COLOR",UI_MUTED,UI_SURFACE,2,5);
 ui_rect(0,46,480,2,UI_ACCENT);
#ifdef SCARLET_RP2040_NATIVE
 extern void console_power_header(void);
 console_power_header();
#endif
}
static void clear_page(void){ui_rect(0,0,480,320,UI_BG);ui_header();menu_valid=false;loading=false;}
void ui_invalidate(void){menu_valid=false;loading=false;loading_legacy=false;}
static void setting_value(unsigned i){
 unsigned y=102+i*60;uint16_t bg=i==focus?UI_SURFACE:UI_BG;
 ui_rect(306,y+8,140,16,bg);
 if(!i){ui_text(306,y+8,ui_settings.language?"< РУССКИЙ >":"< ENGLISH >",UI_TEXT,bg,2,12);return;}
 unsigned v=i==1?ui_settings.volume:ui_settings.brightness;
 char n[5],buf[12];number(v,n);unsigned j=0;buf[j++]='<';buf[j++]=' ';
 for(unsigned k=0;n[k];k++)buf[j++]=n[k];
 buf[j++]='%';buf[j++]=' ';buf[j++]='>';buf[j]=0;
 ui_text(342,y+8,buf,UI_TEXT,bg,2,9);
 for(unsigned k=0;k<10;k++)ui_rect(48+k*39,y+32,33,7,k<v/10?UI_TEAL:UI_TRACK);
}
static void setting_row(unsigned i){
 unsigned y=102+i*60;uint16_t bg=i==focus?UI_SURFACE:UI_BG;
 ui_rect(16,y,448,50,bg);
 if(i==focus){border(16,y,448,50,UI_ACCENT);arrow(25,y+10,UI_ACCENT);}
 const char *s=i==0?tr("LANGUAGE","ЯЗЫК"):i==1?tr("VOLUME","ГРОМКОСТЬ"):tr("BRIGHTNESS","ЯРКОСТЬ");
 ui_text(42,y+8,s,UI_TEXT,bg,2,20);setting_value(i);
}
static void settings_body(void){
 text(20,68,tr("SETTINGS","НАСТРОЙКИ"),2);
 for(unsigned i=0;i<3;i++)setting_row(i);
 ui_rect(0,286,480,34,UI_SURFACE);
 ui_text(16,292,tr("UP/DN: CHOOSE   LEFT/RIGHT: CHANGE","ВВЕРХ/ВНИЗ: ПУНКТ   ВЛЕВО/ВПРАВО: ИЗМЕНИТЬ"),UI_TEXT,UI_SURFACE,1,75);
 ui_text(16,306,tr("B: BACK AND SAVE","B: НАЗАД И СОХРАНИТЬ"),UI_TEXT,UI_SURFACE,1,70);
}
void ui_settings_draw(void){clear_page();settings_body();}
bool ui_settings_key(uint8_t key){
 if(key&UI_B)return true;
 unsigned old=focus;
 if(key&UI_UP)focus=focus?focus-1:2;
 else if(key&(UI_DOWN|UI_SELECT))focus=(focus+1)%3;
 if(focus!=old){setting_row(old);setting_row(focus);return false;}
 if(!(key&(UI_LEFT|UI_RIGHT)))return false;
 if(!focus){
  ui_settings.language^=1;ui_rect(0,48,480,272,UI_BG);settings_body();return false;
 }
 uint8_t *v=focus==1?&ui_settings.volume:&ui_settings.brightness;
 unsigned min=focus==1?0:10, before=*v;
 if(key&UI_RIGHT){if(*v<100)*v+=10;}else if(*v>min)*v-=10;
 if(*v==before)return false;
 ui_volume=ui_settings.volume;
 if(focus==2)ui_apply_brightness(ui_settings.brightness);
 setting_value(focus);return false;
}
static void clean_label(unsigned i,char out[33]){
 const char *s=ui_game_label(i);unsigned n=0;
 while(*s && n<30){char c=*s++;if(c=='('||c=='[')break;out[n++]=c;}
 while(n&&out[n-1]==' ')--n;
 if(*s && n==30){out[28]='.';out[29]='.';}
 out[n]=0;
}
static void game_row(unsigned row,unsigned index,unsigned selected){
 unsigned y=57+row*28;uint16_t bg=index==selected?UI_SURFACE:UI_BG;
 ui_rect(12,y,450,26,bg);
 if(index>=ui_game_count())return;
 if(index==selected){border(12,y,450,26,UI_ACCENT);arrow(21,y+9,UI_ACCENT);}
 char label[33];clean_label(index,label);
 ui_text(36,y+6,label,UI_TEXT,bg,2,30);
#ifdef SCARLET_NATIVE_SOURCE
 if(ui_game_status(index)==5)ui_text(418,y+9,"DIR",UI_MUTED,bg,1,3);
 else
#endif
 ui_text(418,y+9,ui_game_color(index)?"GBC":"GB",ui_game_color(index)?0xfdc9:UI_TEAL,bg,1,3);
}
static void menu_info(unsigned selected,unsigned count){
 ui_rect(16,258,448,24,UI_BG);char s[5];number(selected+1,s);text(16,258,s,1);
 text(36,258,"/",1);number(count,s);text(48,258,s,1);
 unsigned status=ui_game_status(selected);
#ifdef SCARLET_NATIVE_SOURCE
 if(status==5){text(102,258,"OPEN FOLDER",1);return;}
#endif
 const char *en[]={"READY TO PLAY","INVALID ROM HEADER","ROM TOO LARGE","UNSUPPORTED CARTRIDGE","ROM READ ERROR"};
 const char *ru[]={"ГОТОВО К ЗАПУСКУ","ОШИБКА ЗАГОЛОВКА ROM","ROM СЛИШКОМ БОЛЬШОЙ","КАРТРИДЖ НЕ ПОДДЕРЖИВАЕТСЯ","ОШИБКА ЧТЕНИЯ ROM"};
 if(status>4)status=4;
 text(102,258,ui_settings.language?ru[status]:en[status],1);
}
void ui_card_error(unsigned code){
 clear_page();
 /* Simple SD outline and exclamation mark, drawn as primitives. */
 border(217,69,46,53,UI_ACCENT);ui_rect(221,72,15,5,UI_BG);
 for(unsigned i=0;i<3;i++)ui_rect(241+i*6,76,3,10,UI_MUTED);
 ui_text(234,94,"!",UI_ACCENT,UI_BG,2,1);
 text(30,146,tr("MICROSD NOT AVAILABLE","MICROSD НЕ НАЙДЕНА"),2);
 text(30,183,tr("CARD MISSING OR CANNOT BE READ.","КАРТА ОТСУТСТВУЕТ ИЛИ НЕ ЧИТАЕТСЯ."),1);
 text(30,204,tr("POWER OFF, CHECK THE CARD, THEN RESTART.","ВЫКЛЮЧИТЕ ПРИСТАВКУ, ПРОВЕРЬТЕ КАРТУ"),1);
 text(30,220,tr("YOUR GAMES AND SAVES ARE NOT MODIFIED.","И ВКЛЮЧИТЕ СНОВА. ДАННЫЕ НЕ УДАЛЕНЫ."),1);
 ui_rect(0,281,480,39,UI_SURFACE);
 ui_text(20,296,tr("A: RETRY   RIGHT: SETTINGS","A: ПОВТОРИТЬ   ВПРАВО: НАСТРОЙКИ"),UI_TEXT,UI_SURFACE,1,72);
 char n[5];number(code<100?code:99,n);ui_text(450,304,n,UI_MUTED,UI_SURFACE,1,3);
}
void ui_menu_draw(bool force){
 loading=loading_legacy=false;
 unsigned count=ui_game_count(),sel=ui_game_selected(),err=ui_library_error();
#ifdef SCARLET_NATIVE_SOURCE
 if(count>192)count=192;
#else
 if(count>32)count=32;
#endif
 if(sel>=count)sel=0;
 if(!force && menu_valid && last_count==count && last_selected==sel && last_error==err)return;
 bool full=force||!menu_valid||last_count!=count||last_error!=err;
 if(err && err!=4 && err!=5){ui_card_error(err);last_count=count;last_selected=sel;last_error=err;menu_valid=true;return;}
 if(full){
  clear_page();
  ui_rect(0,284,480,36,UI_SURFACE);
  ui_text(16,291,tr("UP/DN OR SELECT: CHOOSE   A/START: PLAY","ВВЕРХ/ВНИЗ ИЛИ SELECT: ВЫБОР   A/START: ИГРАТЬ"),UI_TEXT,UI_SURFACE,1,75);
  ui_text(16,306,tr("RIGHT: SETTINGS   B: REFRESH","ВПРАВО: НАСТРОЙКИ   B: ОБНОВИТЬ"),UI_TEXT,UI_SURFACE,1,75);
 }
 if(!count||err){
  if(full){text(24,106,tr("NO GAMES FOUND","ИГРЫ НЕ НАЙДЕНЫ"),2);
   text(24,156,tr("CREATE /ROMS ON YOUR MICROSD CARD.","СОЗДАЙТЕ ПАПКУ /ROMS НА MICROSD."),1);
   text(24,176,tr("COPY .GB AND .GBC FILES INTO /ROMS.","СКОПИРУЙТЕ В НЕЕ ФАЙЛЫ .GB И .GBC."),1);}
 }else{
  unsigned first=sel/7*7;
  if(full || last_selected/7!=sel/7){for(unsigned i=0;i<7;i++)game_row(i,first+i,sel);}
  else{game_row(last_selected%7,last_selected,sel);game_row(sel%7,sel,sel);}
  menu_info(sel,count);
 }
 last_selected=sel;last_count=count;last_error=err;menu_valid=true;
}
static void spinner(void){
 static const int8_t xy[8][2]={{-3,-26},{14,-18},{22,-3},{14,14},{-3,22},{-18,14},{-26,-3},{-18,-18}};
 /* Only the 56x56 spinner region changes, no title/game-name redraw. */
 for(unsigned i=0;i<8;i++)ui_rect(240+xy[i][0],150+xy[i][1],7,7,
  i==spinner_phase?UI_ACCENT:((i+1)%8==spinner_phase?UI_MUTED:UI_TRACK));
}
void ui_loading(void){
 if(loading)return; /* The legacy title and ROM wrapper share this screen. */
 clear_page();char label[33];clean_label(ui_game_selected(),label);
 centered(74,label,2);centered(208,tr("PLEASE WAIT","ПОДОЖДИТЕ"),2);
 centered(238,tr("THE GAME IS LOADING","ИГРА ЗАГРУЖАЕТСЯ"),2);
 centered(290,tr("DO NOT SWITCH OFF THE CONSOLE","НЕ ВЫКЛЮЧАЙТЕ ПРИСТАВКУ"),1);
 spinner_phase=0;spinner_time=0;loading=true;spinner();
}
void ui_spinner_tick(uint32_t now){
 if(!loading||(uint32_t)(now-spinner_time)<100000)return;
 spinner_time=now;spinner_phase=(spinner_phase+1)%8;spinner();
}
static bool equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
void ui_legacy_clear(uint16_t color){
 ui_invalidate();
 if(color==0){ui_rect(0,0,480,320,0);return;}
 clear_page();
}
void ui_legacy_text(uint16_t x,uint16_t y,const char*s,uint16_t fg,uint16_t bg,uint8_t scale){
 (void)fg;(void)bg;
 if(y==24){loading_legacy=equal(s,"LOADING GAME");if(loading_legacy){ui_loading();return;}}
 if(loading_legacy)return;
 static const char * const en[]={"SCARLETPICO COLOR","READING MICROSD GAME LIST...","LOADING GAME","ROM LOAD FAILED","CHECK THE SD CARD AND ROM SIZE","CANNOT START GAME","SAVE READ FAILED","EXISTING SAVE WAS NOT REPLACED","SAVE FAILED","A: RETRY SAVE   B: DISCARD UNSAVED CHANGES","THE GAME WILL RETURN TO THE MENU","B: BACK","NOT ENOUGH MEMORY","THIS GAME NEEDS MORE RAM THAN THE VIDEO MODE ALLOWS","RECOVERED FROM FREEZE","TAKE A PHOTO OF THIS SCREEN - A: CONTINUE","VIDEO WORKER STALLED"};
 static const char * const ru[]={"SCARLETPICO COLOR","ЧТЕНИЕ СПИСКА ИГР С MICROSD...","ЗАГРУЗКА ИГРЫ","НЕ УДАЛОСЬ ЗАГРУЗИТЬ ROM","ПРОВЕРЬТЕ MICROSD И РАЗМЕР ROM","НЕ УДАЛОСЬ ЗАПУСТИТЬ ИГРУ","ОШИБКА ЧТЕНИЯ СОХРАНЕНИЯ","СУЩЕСТВУЮЩЕЕ СОХРАНЕНИЕ НЕ ИЗМЕНЕНО","ОШИБКА СОХРАНЕНИЯ","A: ПОВТОРИТЬ   B: ВЫЙТИ БЕЗ СОХРАНЕНИЯ","ВОЗВРАТ В МЕНЮ ИГР","B: НАЗАД","НЕДОСТАТОЧНО ПАМЯТИ","ДЛЯ ЭТОЙ ИГРЫ НЕДОСТАТОЧНО ОПЕРАТИВНОЙ ПАМЯТИ","ВОССТАНОВЛЕНО ПОСЛЕ ЗАВИСАНИЯ","СФОТОГРАФИРУЙТЕ ЭКРАН - A: ПРОДОЛЖИТЬ","ОШИБКА ВЫВОДА ИЗОБРАЖЕНИЯ"};
 if(ui_settings.language)for(unsigned i=0;i<sizeof(en)/sizeof(en[0]);i++)if(equal(s,en[i])){s=ru[i];break;}
 if(y==24){y=64;scale=2;if(equal(s,"SCARLETPICO COLOR"))s=tr("GAME LIBRARY","БИБЛИОТЕКА ИГР");}
 else if(y==80)y=108;
 /* The original error detail may contain newlines. Keep it bounded. */
 unsigned line=0;char buf[76];
 while(*s&&y+line*18<280){unsigned n=0;while(*s&&*s!='\n'&&n<74)buf[n++]=*s++;buf[n]=0;
  ui_text(x,y+line*18,buf,UI_TEXT,UI_BG,scale,70);if(*s=='\n')s++;line++;}
}
