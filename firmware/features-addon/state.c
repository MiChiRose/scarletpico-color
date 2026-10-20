/* Build-specific frame-boundary snapshots, never CPU/PPU algorithm changes.
 * Two generations per slot; validate entire file before mutating live state.
 * A snapshot intentionally includes ALL of this cartridge's save RAM. */
#include "features.h"
#include <string.h>
#define FORMAT 0x53503201u
#define PAYLOAD_BASE (CORE_SIZE+APU_SIZE+4u)
typedef struct {
 uint32_t magic,format,sequence,length,rom_size,ram_size,crc,header_crc;
 uint8_t signature[28];
 uint32_t reserved;
} header_t;
_Static_assert(sizeof(header_t)==64,"Snapshot header ABI");

uint32_t state_crc(uint32_t crc,const void *data,size_t n) {
 const uint8_t *p=data;
 while(n--) {
  crc^=*p++;
  for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xedb88320u & (0u-(crc&1u)));
 }
 return crc;
}
static uint32_t identity(void) {
 uint32_t crc=state_crc(UINT32_MAX,&ROM_SIZE,4);
 return ~state_crc(crc,ROM_DATA+0x134,28);
}
static void path(char out[40],unsigned slot,unsigned generation) {
 memcpy(out,"0:/states/",10);
 uint32_t id=identity();
 for(unsigned i=0;i<8;i++)out[10+i]="0123456789abcdef"[(id>>(28-i*4))&15];
 out[18]='-';out[19]='1'+slot;out[20]=generation?'b':'a';
 memcpy(out+21,".sps",5);
}
static uint32_t header_crc(header_t *h) {
 uint32_t saved=h->header_crc;h->header_crc=0;
 uint32_t crc=~state_crc(UINT32_MAX,h,sizeof *h);h->header_crc=saved;return crc;
}
static bool header_valid(header_t *h) {
 return h->magic==0x53504353 && h->format==FORMAT && h->sequence &&
  h->rom_size==ROM_SIZE && h->ram_size==SAVE_SIZE &&
  h->length==PAYLOAD_BASE+SAVE_SIZE && !memcmp(h->signature,ROM_DATA+0x134,28) &&
  h->header_crc==header_crc(h);
}
/* All callers have stopped the video core and audio and paused the watchdog.
 * Header-only status is fast; actual load/save always verifies payload CRC. */
static unsigned inspect(unsigned slot,unsigned gen,header_t *h,uint8_t *payload,bool full) {
 FIL file;char name[40];path(name,slot,gen);
 FRESULT r=f_open(&file,name,FA_READ);
 if(r==FR_NO_FILE || r==FR_NO_PATH)return STATE_EMPTY;
 if(r!=FR_OK)return STATE_IO_ERROR;
 UINT got=0;
 unsigned result=STATE_INVALID;
 r=f_read(&file,h,sizeof *h,&got);
 if(r!=FR_OK)result=STATE_IO_ERROR;
 else if(got==sizeof *h && header_valid(h) && f_size(&file)==sizeof *h+h->length) {
  result=STATE_SAVED;
  if(full) {
   uint8_t scratch[256];uint32_t crc=UINT32_MAX;
   for(unsigned off=0;off<h->length;) {
    unsigned n=h->length-off;if(n>sizeof scratch)n=sizeof scratch;
    uint8_t *dest=payload?payload+off:scratch;
    r=f_read(&file,dest,n,&got);
    if(r!=FR_OK || got!=n){result=STATE_IO_ERROR;break;}
    crc=state_crc(crc,dest,n);off+=n;
   }
   if(result==STATE_SAVED && ~crc!=h->crc)result=STATE_INVALID;
  }
 }
 if(f_close(&file)!=FR_OK)result=STATE_IO_ERROR;
 return result;
}
static bool newer(uint32_t a,uint32_t b) {return (int32_t)(a-b)>0;}
unsigned state_status(unsigned slot) {
 if(slot>=5 || !ROM_DATA)return STATE_INVALID;
 header_t a,b;original_sd_bus();
 unsigned ra=inspect(slot,0,&a,NULL,false),rb=inspect(slot,1,&b,NULL,false);
 original_display_select_bus();
 if(ra==STATE_SAVED || rb==STATE_SAVED)return STATE_SAVED;
 if(ra==STATE_IO_ERROR || rb==STATE_IO_ERROR)return STATE_IO_ERROR;
 if(ra==STATE_INVALID || rb==STATE_INVALID)return STATE_INVALID;
 return STATE_EMPTY;
}
static void snapshot(uint8_t *p) {
 memcpy(p,CORE,CORE_SIZE);
 /* No executable pointers on disk. On restore, retain current callbacks. */
 memset(p,0,28);memset(p+0xc1f0,0,4);memset(p+0xc320,0,4);
 memcpy(p+CORE_SIZE,APU,APU_SIZE);
 memcpy(p+CORE_SIZE+APU_SIZE,&SAMPLE_REMAINDER,4);
 if(SAVE_SIZE)memcpy(p+PAYLOAD_BASE,SAVE_DATA,SAVE_SIZE);
}
static void restore(const uint8_t *p) {
 uint8_t callbacks[36];memcpy(callbacks,CORE,28);
 memcpy(callbacks+28,CORE+0xc1f0,4);memcpy(callbacks+32,CORE+0xc320,4);
 memcpy(CORE,p,CORE_SIZE);memcpy(CORE,callbacks,28);
 memcpy(CORE+0xc1f0,callbacks+28,4);memcpy(CORE+0xc320,callbacks+32,4);
 CORE[0xc31d]=255; /* Never restore held physical buttons. */
 memcpy(APU,p+CORE_SIZE,APU_SIZE);
 memcpy(&SAMPLE_REMAINDER,p+CORE_SIZE+APU_SIZE,4);
 if(SAVE_SIZE){memcpy(SAVE_DATA,p+PAYLOAD_BASE,SAVE_SIZE);DIRTY=1;}
}
unsigned state_save(unsigned slot) {
 if(slot>=5 || !ROM_DATA || SAVE_SIZE>131072)return STATE_INVALID;
 unsigned length=PAYLOAD_BASE+SAVE_SIZE;
 uint8_t *p=original_malloc(length);
 if(!p)return STATE_NO_MEMORY;
 snapshot(p);original_sd_bus();
 FRESULT r=f_mkdir("0:/states");
 if(r!=FR_OK && r!=FR_EXIST){original_free(p);original_display_select_bus();return STATE_IO_ERROR;}
 header_t a,b,h;
 unsigned ra=inspect(slot,0,&a,NULL,true),rb=inspect(slot,1,&b,NULL,true),gen=0;
 unsigned result=STATE_IO_ERROR;
 /* On an I/O error, do not guess which file is the user's good generation. */
 if(ra==STATE_IO_ERROR || rb==STATE_IO_ERROR)goto done;
 uint32_t seq=0;
 if(ra==STATE_SAVED){seq=a.sequence;gen=1;}
 if(rb==STATE_SAVED && (!seq || newer(b.sequence,seq))){seq=b.sequence;gen=0;}
 memset(&h,0,sizeof h);h.magic=0x53504353;h.format=FORMAT;
 h.sequence=seq+1;if(!h.sequence)h.sequence=1;
 h.length=length;h.rom_size=ROM_SIZE;h.ram_size=SAVE_SIZE;
 h.crc=~state_crc(UINT32_MAX,p,length);memcpy(h.signature,ROM_DATA+0x134,28);
 h.header_crc=header_crc(&h);
 FIL file;char name[40];path(name,slot,gen);
 if(f_open(&file,name,FA_WRITE|FA_CREATE_ALWAYS)!=FR_OK)goto done;
 UINT got=0;r=f_write(&file,&h,sizeof h,&got);
 bool ok=r==FR_OK && got==sizeof h;
 for(unsigned off=0;ok && off<length;) {
  unsigned n=length-off;if(n>4096)n=4096;
  r=f_write(&file,p+off,n,&got);ok=r==FR_OK && got==n;off+=n;
 }
 if(ok)ok=f_sync(&file)==FR_OK;
 if(f_close(&file)!=FR_OK)ok=false;
 if(ok)result=inspect(slot,gen,&a,NULL,true);
done:
 original_free(p);original_display_select_bus();return result;
}
unsigned state_load(unsigned slot) {
 if(slot>=5 || !ROM_DATA || SAVE_SIZE>131072)return STATE_INVALID;
 uint8_t *p=original_malloc(PAYLOAD_BASE+SAVE_SIZE);
 if(!p)return STATE_NO_MEMORY;
 header_t a,b;original_sd_bus();
 unsigned ra=inspect(slot,0,&a,NULL,false),rb=inspect(slot,1,&b,NULL,false);
 unsigned first=rb==STATE_SAVED && (ra!=STATE_SAVED || newer(b.sequence,a.sequence));
 unsigned result=inspect(slot,first,&a,p,true);
 if(result!=STATE_SAVED) {
  unsigned second=inspect(slot,1-first,&b,p,true);
  if(second==STATE_SAVED || result==STATE_EMPTY)result=second;
 }
 /* No live memory changed on OOM, missing, truncated, wrong-ROM or bad CRC. */
 if(result==STATE_SAVED)restore(p);
 original_free(p);original_display_select_bus();return result;
}
