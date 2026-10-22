/* Legacy RP2040 launcher only. Keep the original 32-entry array/ABI intact.
 * Four UI screens (28 records) form a window into a globally sorted directory.
 * No catalogue-sized allocation, no writes to the card, no emulator rebuild.
 */
#include "game_library.h"
#include "../ui-addon/ui.h"
#include <stddef.h>
#include <string.h>

_Static_assert(sizeof(game_entry_t)==332 && offsetof(game_entry_t,status)==329,"Pinned game ABI");
_Static_assert(offsetof(FILINFO,fname)==26 && offsetof(FILINFO,fattrib)==12,"Pinned FatFs ABI");
_Static_assert(sizeof(DIR)==88,"Pinned FatFs directory size");

#define GAMES ((game_entry_t *)0x2001adb8u)
#define COUNT (*(unsigned *)0x2001adb4u)
#define SELECTED (*(unsigned *)0x2001e220u)
#define ERROR (*(uint8_t *)0x2001e258u)
enum { WINDOW=28 };
enum { FIRST, KEEP, NEXT, PREVIOUS, LAST };
static unsigned total_count,window_offset;
static bool initialized,reset_requested;
extern bool original_storage_mount(void);
extern void original_sd_bus(void);
extern uint8_t old_menu_input(uint8_t);
extern void polished_invalidate(void);
extern void polished_menu_draw(bool);
extern uint64_t time_us_64(void);

/* Held-key repeats use a second path in the legacy main loop. Preserve its
 * r5 &= r7 operation and route it through exactly the same input bridge. */
__attribute__((naked)) void paged_repeat_bridge(void){
 __asm__ volatile(".syntax unified\n ands r5,r7\n push {r6,lr}\n bl legacy_input_bridge\n pop {r6,pc}");
}

unsigned library_total_count(void){return total_count;}
unsigned library_window_offset(void){return window_offset;}
static unsigned lower(unsigned c){return c>='A'&&c<='Z'?c+32:c;}
static int compare(const char *a,const char *b){
 const unsigned char *x=(const unsigned char *)a,*y=(const unsigned char *)b;
 while(*x&&lower(*x)==lower(*y)){x++;y++;}
 if(lower(*x)!=lower(*y))return lower(*x)<lower(*y)?-1:1;
 /* FAT filenames cannot differ by ASCII case alone, but keep a total order. */
 while(*a&&*a==*b){a++;b++;}
 return (unsigned char)*a-(unsigned char)*b;
}
static bool eligible(const FILINFO *f){
 if(f->fattrib&(AM_DIR|AM_HID|AM_SYS) || f->fname[0]=='.')return false;
 const char *ext=0;
 for(const char *s=f->fname;*s;s++)if(*s=='.')ext=s;
 return ext&&(!compare(ext,".gb")||!compare(ext,".gbc")||
   (lower(ext[1])=='g'&&lower(ext[2])=='b'&&
    (!ext[3]||(lower(ext[3])=='c'&&!ext[4]))));
}
static void copy_name(char *dst,const char *src){
 unsigned i=0;while(i<255&&src[i]){dst[i]=src[i];i++;}dst[i]=0;
}
static void inspect(game_entry_t *g){
 FIL file;UINT got;uint8_t h[0x150];char path[288];
 static const int8_t mbc[]={0,1,1,1,-1,2,2,-1,0,0,-1,0,0,0,-1,3,
   3,3,3,3,-1,-1,-1,-1,-1,5,5,5,5,5,5,-1};
 g->status=GAME_READ_ERROR;
 memcpy(path,"0:/roms/",8);copy_name(path+8,g->filename);
 if(f_open(&file,path,FA_READ)!=FR_OK)return;
 FRESULT r=f_read(&file,h,sizeof h,&got),closed=f_close(&file);
 if(r!=FR_OK||closed!=FR_OK)return;
 g->status=GAME_BAD_HEADER;
 if(got!=sizeof h)return;
 memcpy(g->signature,h+0x134,28);
 uint8_t checksum=0;for(unsigned i=0x134;i<=0x14c;i++)checksum-=h[i]+1u;
 if(checksum!=h[0x14d]||h[0x148]>8||h[0x149]>5||g->size!=(32768u<<h[0x148]))return;
 g->color=(h[0x143]&0x80)!=0;
 if(g->size>0x800000u){g->status=GAME_TOO_LARGE;return;}
 if(h[0x147]>=sizeof mbc||mbc[h[0x147]]<0){g->status=GAME_UNSUPPORTED;return;}
 g->status=GAME_READY;
}
static FRESULT fail(unsigned *n,FRESULT r){
 *n=0;total_count=window_offset=0;initialized=false;return r;
}
static FRESULT load_window(game_entry_t *g,unsigned cap,unsigned *n,unsigned mode,const char *anchor){
 DIR dir;FILINFO info;unsigned total,below,equal;
 if(cap>WINDOW)cap=WINDOW;
 if(!cap)return fail(n,FR_INVALID_PARAMETER);
restart:
 total=below=equal=0;*n=0;
 FRESULT r=f_opendir(&dir,"0:/roms");if(r!=FR_OK)return fail(n,r);
 for(;;){
  r=f_readdir(&dir,&info);if(r!=FR_OK||!info.fname[0])break;
  if(!eligible(&info))continue;
  if(total==UINT32_MAX){r=FR_INT_ERR;break;}total++;
  int relation=anchor[0]?compare(info.fname,anchor):0;
  if(relation<0)below++;else if(!relation&&anchor[0])equal++;
  if((mode==KEEP&&relation<0)||(mode==NEXT&&relation<=0)||
     (mode==PREVIOUS&&relation>=0))continue;
  unsigned pos=0;while(pos<*n&&compare(g[pos].filename,info.fname)<0)pos++;
  bool largest=mode==PREVIOUS||mode==LAST;
  if(*n==cap){
   if(!largest&&pos==cap)continue;
   if(largest){
    if(!pos)continue;
    for(unsigned i=1;i<*n;i++)g[i-1]=g[i];
    pos--;
   }
  }else (*n)++;
  for(unsigned i=*n-1;i>pos;i--)g[i]=g[i-1];
  memset(&g[pos],0,sizeof g[pos]);copy_name(g[pos].filename,info.fname);
  g[pos].size=info.fsize>UINT32_MAX?0:(uint32_t)info.fsize;
 }
 FRESULT closed=f_closedir(&dir);if(r==FR_OK)r=closed;
 if(r!=FR_OK)return fail(n,r);
 if(mode==LAST&&*n){
  unsigned tail=total%cap;if(!tail)tail=cap;
  unsigned skip=*n-tail;
  for(unsigned i=0;i<tail;i++)g[i]=g[i+skip];
  *n=tail;
 }
 if(!*n&&total&&mode!=FIRST){mode=FIRST;anchor="";goto restart;}
 total_count=total;
 window_offset=mode==FIRST?0:mode==LAST?total-*n:
   mode==PREVIOUS?below-*n:mode==NEXT?below+equal:below;
 for(unsigned i=0;i<*n;i++){
  const char *ext=0;unsigned len=0;
  for(const char *s=g[i].filename;*s;s++)if(*s=='.')ext=s;
  if(ext)len=(unsigned)(ext-g[i].filename);
  if(len>36)len=36;
  for(unsigned j=0;j<len;j++){
   unsigned c=(unsigned char)g[i].filename[j];
   g[i].label[j]=(c>='0'&&c<='9')||(lower(c)>='a'&&lower(c)<='z')||c=='-'||c==' '?c:' ';
  }
  inspect(&g[i]);
 }
 initialized=true;return FR_OK;
}
/* The caller is the old launcher, with its exact ABI and array. All returns
 * close files/directories before anything can launch a game or change SPI. */
FRESULT paged_scan_games(game_entry_t *g,size_t cap,size_t *n,bool *limited){
 char anchor[256];anchor[0]=0;
 unsigned mode=FIRST;
 if(initialized&&!reset_requested&&*n){copy_name(anchor,g[0].filename);mode=KEEP;}
 reset_requested=false;*limited=false;
 if(!original_storage_mount())return fail(n,FR_NOT_READY);
 original_sd_bus();return load_window(g,cap,n,mode,anchor);
}
uint8_t paged_menu_input(uint8_t edge){
 uint8_t remaining=old_menu_input(edge);
 if(remaining&UI_B){reset_requested=true;return remaining;}
 if(ERROR||!COUNT||!initialized||total_count<=COUNT)return remaining;
 bool up=(remaining&UI_UP)!=0,down=!up&&(remaining&(UI_DOWN|UI_SELECT));
 if((!up||SELECTED)&&(!down||SELECTED+1<COUNT))return remaining;
 char anchor[256];unsigned mode;
 if(up){copy_name(anchor,GAMES[0].filename);mode=window_offset?PREVIOUS:LAST;}
 else{copy_name(anchor,GAMES[COUNT-1].filename);mode=window_offset+COUNT<total_count?NEXT:FIRST;}
 ui_rect(16,268,448,12,UI_BG);
 ui_text(16,270,ui_settings.language?"ЧТЕНИЕ СПИСКА...":"READING LIBRARY...",UI_MUTED,UI_BG,1,70);
 original_sd_bus();
 FRESULT r=load_window(GAMES,WINDOW,(unsigned *)0x2001adb4u,mode,anchor);
 ERROR=(uint8_t)r;SELECTED=up&&COUNT?COUNT-1:0;
 polished_invalidate();polished_menu_draw(true);
 /* Consume the boundary key; the old launcher must not move a second time. */
 return 0;
}
