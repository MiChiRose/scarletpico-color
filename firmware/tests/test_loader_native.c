/* Test the exact loader logic with sanitizer coverage, including failover.
 * No emulation, display rendering or source ROM is modified. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern bool loader_prepare(const char *,const uint8_t **,size_t *);
extern uint8_t loader_header_read(void *,void *,unsigned,unsigned *);
extern uint8_t loader_page_read(void *,void *,unsigned,unsigned *);
bool original_ui_loading;
uint32_t original_spinner_time;
static uint64_t ticks;
static unsigned restores,draws,reads,allocs,frees,bulk_reads;
static unsigned source_size,cursor,fail_at,short_at;
static bool oom,cached,open_fail;
static void *live;
static uint8_t source[20000],copied[20000];
uint64_t time_us_64(void){return ticks;}
void original_sd_bus(void){restores++;}
void original_ui_spinner_tick(uint32_t now){
 assert(original_ui_loading && (uint32_t)(now-original_spinner_time)>=100000u);
 original_spinner_time=now;draws++;
}
void *original_malloc(size_t n){
 assert(n==4096 && !live);allocs++;
 return oom?NULL:(live=malloc(n));
}
void original_free(void *p){assert(p && p==live);free(p);live=NULL;frees++;}
uint8_t original_f_read(void *file,void *p,unsigned n,unsigned *got){
 (void)file;reads++;if(n==4096)bulk_reads++;
 ticks+=2000;*got=0;
 if(cursor==fail_at)return 1;
 if(cursor+n>source_size)n=source_size-cursor;
 if(cursor==short_at && n>17)n=17;
 memcpy(p,source+cursor,n);cursor+=n;*got=n;return 0;
}
bool original_ui_prepare(const char *path,const uint8_t **rom,size_t *size){
 (void)path;
 if(open_fail)return false;
 original_ui_loading=true;
 uint8_t header[28];unsigned got=0;cursor=0;
 if(loader_header_read(NULL,header,sizeof header,&got) || got!=sizeof header)goto failed;
 if(cached){original_ui_loading=false;*rom=source;*size=source_size;return true;}
 cursor=0;
 for(unsigned off=0;off<source_size;){
  unsigned n=source_size-off;if(n>256)n=256;
  if(loader_page_read(NULL,copied+off,n,&got)||got!=n)goto failed;
  off+=got;ticks+=1000;
 }
 original_ui_loading=false;*rom=copied;*size=source_size;return true;
failed:original_ui_loading=false;return false;
}
static void reset(unsigned n){
 assert(!live);source_size=n;cursor=0;reads=bulk_reads=allocs=frees=restores=draws=0;
 ticks=0;original_spinner_time=0;original_ui_loading=false;
 fail_at=short_at=UINT32_MAX;oom=cached=open_fail=false;
 memset(copied,0,sizeof copied);
 for(unsigned i=0;i<n;i++)source[i]=(uint8_t)(i*19+(i>>8));
}
int main(void){
 const uint8_t *rom;size_t size;
 for(unsigned n=28;n<=sizeof source;n+=37){
  reset(n);assert(loader_prepare("test",&rom,&size));
  assert(size==n && !memcmp(rom,source,n));
  assert(bulk_reads==(n+4095)/4096 && allocs==1 && frees==1 && !live);
  assert(restores==draws);
 }
 reset(16384);oom=true;assert(loader_prepare("test",&rom,&size));
 assert(allocs==1 && frees==0 && reads==1+16384/256 && !memcmp(rom,source,size));
 reset(16384);cached=true;assert(loader_prepare("test",&rom,&size));
 assert(reads==1 && !allocs && !frees);
 reset(16384);open_fail=true;assert(!loader_prepare("test",&rom,&size));
 assert(!reads && !allocs);
 for(unsigned pos=0;pos<16384;pos+=4096){
  reset(16384);fail_at=pos;assert(!loader_prepare("test",&rom,&size));assert(!live && frees==allocs);
  reset(16384);short_at=pos;assert(!loader_prepare("test",&rom,&size));assert(!live && frees==allocs);
  reset(8192);assert(loader_prepare("retry",&rom,&size));assert(!memcmp(rom,source,size));
 }
 reset(4096);original_ui_loading=true;original_spinner_time=UINT32_MAX-49999u;ticks=50000;
 uint8_t page[256];unsigned got;
 assert(!loader_header_read(NULL,page,28,&got));assert(restores==1 && draws==1);
 assert(loader_page_read(NULL,page,257,&got)==2 && got==0);
 puts("PASS native loader: 540+ sizes/tails, data integrity, OOM fallback, cache hit, read/short-read failures, retry, SPI guard and timer wrap");
}
