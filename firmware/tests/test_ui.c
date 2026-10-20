#include "../ui-addon/ui.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#ifdef SCARLET_RP2040_NATIVE
/* The shared UI-only test has no physical battery adapter. */
void console_power_header(void){}
#endif

static uint16_t screen[320][480];
static unsigned writes,full_clears,min_y=320,max_y,brightness;
static unsigned count=9,selected,error;
static unsigned px,py,pw,ph,rows;
static const char *labels[]={"Aladdin (U) [C][!]","Legend of Zelda - Link's Awakening", "Pac-Man", "Pokemon - Yellow Version","Pokemon - Crystal Version","Tetris","Wario Land 3","Super Mario Land 2","An extremely long game title exceeds width"};
unsigned ui_game_count(void){return count;}
unsigned ui_game_selected(void){return selected;}
unsigned ui_library_error(void){return error;}
const char *ui_game_label(unsigned i){return labels[i%9];}
bool ui_game_color(unsigned i){return i==0||i==3||i==4||i==6;}
unsigned ui_game_status(unsigned i){return i==8?3:0;}
void ui_apply_brightness(unsigned p){assert(p>=10 && p<=100);brightness=p;}
static void region(unsigned x,unsigned y,unsigned w,unsigned h){
 assert(w && h && x+w<=480 && y+h<=320);
 writes+=w*h;if(w==480 && h==320)full_clears++;
 if(y<min_y)min_y=y;if(y+h>max_y)max_y=y+h;
}
void ui_rect(unsigned x,unsigned y,unsigned w,unsigned h,uint16_t c){
 region(x,y,w,h);for(unsigned j=y;j<y+h;j++)for(unsigned i=x;i<x+w;i++)screen[j][i]=c;
}
void ui_pixels_begin(unsigned x,unsigned y,unsigned w,unsigned h){region(x,y,w,h);px=x;py=y;pw=w;ph=h;rows=0;}
void ui_pixels_row(const uint8_t *p,unsigned size){
 assert(size==pw*2 && rows<ph);
 for(unsigned i=0;i<pw;i++)screen[py+rows][px+i]=(p[2*i]<<8)|p[2*i+1];rows++;
}
void ui_pixels_end(void){assert(rows==ph);}
static void reset_metrics(void){writes=full_clears=max_y=0;min_y=320;}
static void snapshot(const char *dir,const char *name){
 char path[1024];snprintf(path,sizeof path,"%s/%s.ppm",dir,name);
 FILE *f=fopen(path,"wb");assert(f);fprintf(f,"P6\n480 320\n255\n");
 for(unsigned y=0;y<320;y++)for(unsigned x=0;x<480;x++){
  unsigned c=screen[y][x];uint8_t rgb[]={((c>>11)&31)*255/31,((c>>5)&63)*255/63,(c&31)*255/31};
  assert(fwrite(rgb,1,3,f)==3);
 }
 fclose(f);
}
int main(int argc,char **argv){
 assert(argc==2);const char *dir=argv[1];
 ui_init(NULL);assert(ui_settings.language==0 && ui_volume==50 && brightness==100);
 ui_menu_draw(true);snapshot(dir,"menu-en");
 reset_metrics();ui_menu_draw(false);assert(writes==0);
 selected=1;ui_menu_draw(false);assert(!full_clears && min_y>=57 && max_y<=282 && writes<45000);
 snapshot(dir,"menu-zelda");
 selected=7;reset_metrics();ui_menu_draw(false);assert(!full_clears && min_y>=57 && max_y<=282);
 snapshot(dir,"menu-page2");
 selected=0;
 ui_settings_draw();ui_settings_key(UI_DOWN);snapshot(dir,"settings-en");
 reset_metrics();ui_settings_key(UI_RIGHT);assert(ui_volume==60 && !full_clears && min_y>=170 && max_y<=202);
 for(unsigned i=0;i<20;i++)ui_settings_key(UI_RIGHT);assert(ui_volume==100);
 reset_metrics();ui_settings_key(UI_RIGHT);assert(writes==0);
 for(unsigned i=0;i<20;i++)ui_settings_key(UI_LEFT);assert(ui_volume==0);
 reset_metrics();ui_settings_key(UI_LEFT);assert(writes==0);
 for(unsigned i=0;i<5;i++)ui_settings_key(UI_RIGHT);assert(ui_volume==50);
 reset_metrics();ui_settings_key(UI_DOWN);assert(!full_clears && min_y>=162 && max_y<=272);
 for(unsigned i=0;i<20;i++)ui_settings_key(UI_LEFT);assert(brightness==10 && ui_settings.brightness==10);
 reset_metrics();ui_settings_key(UI_LEFT);assert(writes==0 && brightness==10);
 snapshot(dir,"brightness-min");
 for(unsigned i=0;i<20;i++)ui_settings_key(UI_RIGHT);assert(brightness==100);
 ui_settings_key(UI_DOWN);reset_metrics();ui_settings_key(UI_RIGHT);
 assert(ui_settings.language==1 && !full_clears && min_y>=48);
 ui_settings_key(UI_DOWN);snapshot(dir,"settings-ru");
 uint8_t record[16];ui_make_record(record);ui_init(record);assert(ui_settings.language==1 && ui_volume==50);
 for(unsigned i=0;i<16;i++){uint8_t bad[16];memcpy(bad,record,16);bad[i]^=1;ui_init(bad);assert(ui_settings.language==0 && ui_volume==50 && brightness==100);}
 ui_init(record);ui_menu_draw(true);snapshot(dir,"menu-ru");
 error=3;count=0;ui_menu_draw(true);snapshot(dir,"no-card-ru");
 reset_metrics();ui_menu_draw(false);assert(writes==0);
 ui_settings.language=0;ui_card_error(3);snapshot(dir,"no-card-en");
 error=0;ui_menu_draw(true);snapshot(dir,"empty-en");
 error=5;ui_menu_draw(true);snapshot(dir,"missing-roms-en");
 count=9;error=0;selected=1;ui_loading();snapshot(dir,"loading-en");
 reset_metrics();ui_spinner_tick(99999);assert(writes==0);
 ui_spinner_tick(100000);assert(writes==392 && !full_clears && min_y>=124 && max_y<=179);
 ui_settings.language=1;ui_invalidate();ui_loading();snapshot(dir,"loading-ru");
 ui_invalidate();reset_metrics();ui_spinner_tick(200000);assert(writes==0);
 ui_legacy_clear(0xd7e9);ui_legacy_text(20,24,"SAVE READ FAILED",0,0,2);
 ui_legacy_text(20,80,"EXISTING SAVE WAS NOT REPLACED",0,0,1);snapshot(dir,"save-error-ru");
 puts("PASS UI: navigation dirty regions, unchanged idle screen, limits, gain default, persistence validation, both languages, card/empty/loading/error states");
}
