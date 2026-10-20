/* 480x320 physical-button UI, appended to the accepted legacy 2.2.6.
 * Uses its original pixel font, RGB565 palette and LCD transport. */
#include "../ui-addon/ui.h"

extern void legacy_battery_header(unsigned,unsigned,unsigned,unsigned,uint16_t);
extern void old_features_ui_init(const uint8_t *);
extern void old_boot_draw(int,int);
extern bool old_boot_chime(void);
extern uint8_t old_keys(void);
extern void old_release(void);
extern void sleep_ms(uint32_t);
extern uint64_t time_us_64(void);
extern void old_card_error(unsigned);

static unsigned last_selected,last_count,last_error,last_status;
static bool valid;
enum { ROWS=7, ROW_Y=78, ROW_STEP=26, ROW_HEIGHT=24 };
static const char *tr(const char *en,const char *ru){return ui_settings.language?ru:en;}
static void text(unsigned x,unsigned y,const char *s,uint16_t c,unsigned scale,unsigned n) {
 ui_text(x,y,s,c,UI_BG,scale,n);
}
static void border(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t c) {
 ui_rect(x,y,w,1,c);ui_rect(x,y+h-1,w,1,c);
 ui_rect(x,y,1,h,c);ui_rect(x+w-1,y,1,h,c);
}
void polished_header(void) {
 ui_rect(0,0,480,46,UI_SURFACE);
 ui_text(16,13,"SCARLET",UI_ACCENT,UI_SURFACE,3,7);
 ui_text(154,13,"PICO",UI_TEXT,UI_SURFACE,3,4);
 ui_text(242,20,"COLOR",UI_TEAL,UI_SURFACE,1,5);
 ui_text(312,20,"2.2.7",UI_MUTED,UI_SURFACE,1,5);
 legacy_battery_header(0,46,480,2,UI_ACCENT);
}
void polished_invalidate(void) {
 /* Original ui_init/loading code still owns these three legacy flags. */
 volatile uint8_t *p=(volatile uint8_t *)0x2001f400u;
 p[0]=p[1]=p[2]=0;valid=false;
}
static unsigned number(unsigned n,char *out) {
 unsigned len=0;if(n>=10)out[len++]='0'+n/10;
 out[len++]='0'+n%10;return len;
}
static void counter(unsigned selected,unsigned count) {
 char s[12];unsigned n=number(count?selected+1:0,s);
 s[n++]=' ';s[n++]='/';s[n++]=' ';n+=number(count,s+n);s[n]=0;
 ui_rect(384,58,80,10,UI_BG);text(464-n*6,59,s,UI_MUTED,1,n);
}
static void label(unsigned index,char out[88]) {
 const char *s=ui_game_label(index);unsigned bytes=0,chars=0;
 while(*s&&chars<28) {
  if((*s=='('||*s=='[')&&(bytes==0||out[bytes-1]==' '))break;
  unsigned n=((uint8_t)*s>=0xc0&&(uint8_t)*s<0xe0)?2:1;
  if(n==2&&!s[1])break;
  for(unsigned i=0;i<n;i++)out[bytes++]=*s++;
  chars++;
 }
 while(bytes&&out[bytes-1]==' ')bytes--;
 if(*s&&chars==28&&bytes>=2){out[bytes++]='.';out[bytes++]='.';}
 out[bytes]=0;
}
static void focus(unsigned row,bool selected) {
 unsigned y=ROW_Y+row*ROW_STEP;
 border(12,y,448,ROW_HEIGHT,selected?UI_ACCENT:UI_BG);
 ui_rect(20,y+7,12,10,UI_BG);
 if(selected)text(22,y+8,">",UI_ACCENT,1,1);
}
static void row(unsigned r,unsigned index,unsigned count) {
 if(index>=count)return;
 char name[88];label(index,name);
 text(40,ROW_Y+r*ROW_STEP+5,name,UI_TEXT,2,30);
 const char *kind=ui_game_color(index)?"GBC":"GB";
 uint16_t color=ui_game_color(index)?0xfdc9:UI_TEAL;
 text(418,ROW_Y+r*ROW_STEP+8,kind,color,1,3);
}
static void status(unsigned index,bool force) {
 unsigned s=ui_game_status(index);if(s>4)s=4;
 if(!force&&s==last_status)return;
 const char *en[]={"READY TO PLAY","INVALID ROM HEADER","ROM TOO LARGE","UNSUPPORTED CARTRIDGE","ROM READ ERROR"};
 const char *ru[]={"ГОТОВО К ЗАПУСКУ","ОШИБКА ЗАГОЛОВКА ROM","ROM СЛИШКОМ БОЛЬШОЙ","КАРТРИДЖ НЕ ПОДДЕРЖИВАЕТСЯ","ОШИБКА ЧТЕНИЯ ROM"};
 ui_rect(16,268,448,12,UI_BG);
 text(16,270,ui_settings.language?ru[s]:en[s],s?UI_ACCENT:UI_MUTED,1,70);
 last_status=s;
}
static void key(unsigned x,const char *k,const char *name,bool primary,bool enabled) {
 uint16_t bg=primary?UI_TEAL:UI_SURFACE;
 ui_rect(x,290,18,14,bg);
 if(!primary)border(x,290,18,14,enabled?UI_MUTED:UI_TRACK);
 ui_text(x+6,293,k,primary?UI_BG:enabled?UI_TEXT:UI_MUTED,bg,1,1);
 ui_text(x+26,294,name,enabled?UI_TEXT:UI_MUTED,UI_SURFACE,1,18);
}
static void footer(bool playable) {
 ui_rect(0,284,480,36,UI_SURFACE);
 key(16,"A",tr("PLAY","ИГРАТЬ"),playable,playable);
 key(152,">",tr("SETTINGS","НАСТРОЙКИ"),false,true);
 key(340,"B",tr("REFRESH","ОБНОВИТЬ"),false,true);
 ui_text(16,309,tr("UP/DN OR SELECT: CHOOSE    START: PLAY","ВВЕРХ/ВНИЗ ИЛИ SELECT: ВЫБОР    START: ИГРАТЬ"),UI_MUTED,UI_SURFACE,1,74);
}
void polished_menu_draw(bool force) {
 volatile uint8_t *flags=(volatile uint8_t *)0x2001f400u;
 flags[0]=flags[1]=0;
 unsigned count=ui_game_count(),selected=ui_game_selected(),error=ui_library_error();
 if(count>32)count=32;
 if(selected>=count)selected=0;
 if(!force&&valid&&last_selected==selected&&last_count==count&&last_error==error)return;
 bool full=force||!valid||last_count!=count||last_error!=error;
 if(error&&error!=4&&error!=5) {
  if(full)old_card_error(error);
  last_selected=selected;last_count=count;last_error=error;valid=true;return;
 }
 if(full) {
  ui_rect(0,0,480,320,UI_BG);polished_header();footer(count&&!error);
  text(16,59,tr("LIBRARY","ИГРЫ"),UI_MUTED,1,15);
 }
 if(count&&!error) {
  unsigned first=selected/ROWS*ROWS;
  if(full||last_selected/ROWS!=selected/ROWS) {
   if(!full)ui_rect(12,ROW_Y,448,ROWS*ROW_STEP,UI_BG);
   for(unsigned i=0;i<ROWS;i++)row(i,first+i,count);
   focus(selected%ROWS,true);
  } else {
   focus(last_selected%ROWS,false);focus(selected%ROWS,true);
  }
  status(selected,full);
 } else if(full) {
  text(24,116,tr("NO GAMES YET","ПОКА НЕТ ИГР"),UI_TEXT,2,30);
  text(24,160,tr("COPY .GB / .GBC FILES TO /ROMS ON MICROSD.","СКОПИРУЙТЕ .GB / .GBC В /ROMS НА MICROSD."),UI_TEXT,1,70);
  text(24,184,tr("THEN PRESS B TO REFRESH.","ЗАТЕМ НАЖМИТЕ B ДЛЯ ОБНОВЛЕНИЯ."),UI_MUTED,1,70);
 }
 counter(selected,count);
 last_selected=selected;last_count=count;last_error=error;valid=true;
}
void polished_boot(const uint8_t *record) {
 old_features_ui_init(record);ui_rect(0,0,480,320,UI_BG);
 uint32_t start=(uint32_t)time_us_64();int previous=-72;bool skipped=false;
 for(;;) {
  if(old_keys()&UI_START){skipped=true;break;}
  uint32_t elapsed=(uint32_t)time_us_64()-start;
  if(elapsed>600000)elapsed=600000;
  unsigned ms=elapsed/1000;
  int y=-72+(int)(196u*ms*(1200u-ms)/360000u);
  if(y!=previous){old_boot_draw(previous,y);previous=y;}
  if(elapsed==600000)break;
  sleep_ms(16);
 }
 if(previous!=124)old_boot_draw(previous,124);
 text(210,208,"COLOR",UI_TEAL,2,5);
 if(!skipped){old_boot_chime();sleep_ms(120);}else sleep_ms(30);
 if(old_keys()&UI_START)old_release();
 polished_invalidate();
}
