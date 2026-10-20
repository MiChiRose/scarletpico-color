/* Five independent snapshots, two checked generations per slot. No legacy
 * fixed-address ABI. Video must be stopped before reusing its buffers. */
#include "console.h"
#include "display.h"
#include "ff.h"
#include <string.h>
#include <stdio.h>
typedef struct {
  uint32_t magic,format,sequence,length,rom_size,ram_size,crc,header_crc;
  uint8_t signature[28];uint32_t identity;
} header_t;
_Static_assert(sizeof(header_t)==64,"State header size");
#ifdef SCARLET_RP2040_NATIVE
#define FORMAT 0x20400003u
#define STATE_DIR "0:/scarlet2040/states"
#else
#define FORMAT 0x23500002u
#define STATE_DIR "0:/scarlet2350/states"
#endif
static uint32_t identity;
static uint32_t crc(uint32_t c,const void *p,unsigned n) {
  const uint8_t *s=p;
  while(n--){c^=*s++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&(0u-(c&1)));}
  return c;
}
void console_state_bind(void) {
  unsigned n;const uint8_t *rom=native_rom(&n);identity=~crc(~0u,rom,n);
}
static unsigned length(void){unsigned n;native_save_ram(&n);return native_core_size()+console_apu_size()+n;}
static uint32_t header_crc(header_t *h) {
  uint32_t v=h->header_crc;h->header_crc=0;uint32_t c=~crc(~0u,h,sizeof *h);h->header_crc=v;return c;
}
static void path(char s[64],unsigned slot,unsigned gen) {
  snprintf(s,64,STATE_DIR "/%08lx-%u%c.sps",(unsigned long)identity,slot+1,gen?'b':'a');
}
static bool valid(header_t *h) {
  unsigned rn,sn;const uint8_t *rom=native_rom(&rn);native_save_ram(&sn);
  return h->magic==0x53504353&&h->format==FORMAT&&h->sequence&&
    h->identity==identity&&h->rom_size==rn&&h->ram_size==sn&&h->length==length()&&
    !memcmp(h->signature,rom+0x134,28)&&h->header_crc==header_crc(h);
}
static unsigned inspect(unsigned slot,unsigned gen,header_t *h,uint8_t *payload,bool full) {
  FIL file;char name[64];path(name,slot,gen);
  FRESULT r=f_open(&file,name,FA_READ);
  if(r==FR_NO_FILE||r==FR_NO_PATH)return STATE_EMPTY;
  if(r)return STATE_IO_ERROR;
  UINT got=0;unsigned result=STATE_INVALID;r=f_read(&file,h,sizeof *h,&got);
  if(r)result=STATE_IO_ERROR;
  else if(got==sizeof *h&&valid(h)){
    result=STATE_SAVED;
    if(full){
      uint8_t scratch[256];uint32_t c=~0u;
      for(unsigned off=0;off<h->length;){
        unsigned n=h->length-off;if(n>sizeof scratch)n=sizeof scratch;
        uint8_t *dest=payload?payload+off:scratch;r=f_read(&file,dest,n,&got);
        if(r){result=STATE_IO_ERROR;break;}
        if(got!=n){result=STATE_INVALID;break;}
        c=crc(c,dest,n);off+=n;
      }
      if(result==STATE_SAVED){
        if(~c!=h->crc)result=STATE_INVALID;
        else if(f_read(&file,scratch,1,&got))result=STATE_IO_ERROR;
        else if(got)result=STATE_INVALID;
      }
    }
  }
  if(f_close(&file))result=STATE_IO_ERROR;
  return result;
}
unsigned state_status(unsigned slot) {
  if(slot>=5)return STATE_INVALID;
  header_t a,b;display_sd_speed();
  unsigned ra=inspect(slot,0,&a,NULL,false),rb=inspect(slot,1,&b,NULL,false);
  display_game_speed();
  if(ra==STATE_SAVED||rb==STATE_SAVED)return STATE_SAVED;
  if(ra==STATE_IO_ERROR||rb==STATE_IO_ERROR)return STATE_IO_ERROR;
  if(ra==STATE_INVALID||rb==STATE_INVALID)return STATE_INVALID;
  return STATE_EMPTY;
}
static bool newer(uint32_t a,uint32_t b){return (int32_t)(a-b)>0;}
static void snapshot(uint8_t *p) {
  unsigned n;uint8_t *ram=native_save_ram(&n);
  native_core_copy(p);console_apu_snapshot(p+native_core_size());
  memcpy(p+native_core_size()+console_apu_size(),ram,n);
}
static void restore(const uint8_t *p) {
  unsigned n;uint8_t *ram=native_save_ram(&n);native_core_restore(p);
  console_apu_restore(p+native_core_size());
  memcpy(ram,p+native_core_size()+console_apu_size(),n);native_mark_save_dirty();
}
unsigned state_save(unsigned slot) {
  if(slot>=5)return STATE_INVALID;
  unsigned capacity;uint8_t *staging=native_staging(&capacity);
  if(length()>capacity)return STATE_NO_MEMORY;
  snapshot(staging);display_sd_speed();FRESULT r=f_mkdir(STATE_DIR);
  if(r&&r!=FR_EXIST){display_game_speed();return STATE_IO_ERROR;}
  header_t a,b,h;unsigned ra=inspect(slot,0,&a,NULL,true),rb=inspect(slot,1,&b,NULL,true);
  unsigned result=STATE_IO_ERROR,gen=0;uint32_t seq=0;
  if(ra==STATE_IO_ERROR||rb==STATE_IO_ERROR)goto done;
  if(ra==STATE_SAVED){seq=a.sequence;gen=1;}
  if(rb==STATE_SAVED&&(!seq||newer(b.sequence,seq))){seq=b.sequence;gen=0;}
  unsigned rn,sn;const uint8_t *rom=native_rom(&rn);native_save_ram(&sn);
  memset(&h,0,sizeof h);h.magic=0x53504353;h.format=FORMAT;
  h.sequence=seq+1;if(!h.sequence)h.sequence=1;
  h.length=length();h.rom_size=rn;h.ram_size=sn;h.identity=identity;
  h.crc=~crc(~0u,staging,h.length);memcpy(h.signature,rom+0x134,28);h.header_crc=header_crc(&h);
  FIL file;char name[64];path(name,slot,gen);
  if(f_open(&file,name,FA_CREATE_ALWAYS|FA_WRITE))goto done;
  UINT got=0;r=f_write(&file,&h,sizeof h,&got);bool ok=!r&&got==sizeof h;
  for(unsigned off=0;ok&&off<h.length;){
    unsigned n=h.length-off;if(n>4096)n=4096;
    r=f_write(&file,staging+off,n,&got);ok=!r&&got==n;off+=n;
  }
  if(ok)ok=!f_sync(&file);
  if(f_close(&file))ok=false;
  if(ok)result=inspect(slot,gen,&a,NULL,true);
done:
  display_game_speed();return result;
}
unsigned state_load(unsigned slot) {
  if(slot>=5)return STATE_INVALID;
  unsigned capacity;uint8_t *staging=native_staging(&capacity);
  if(length()>capacity)return STATE_NO_MEMORY;
  header_t a,b;display_sd_speed();
  unsigned ra=inspect(slot,0,&a,NULL,false),rb=inspect(slot,1,&b,NULL,false);
  unsigned first=rb==STATE_SAVED&&(ra!=STATE_SAVED||newer(b.sequence,a.sequence));
  unsigned result=inspect(slot,first,&a,staging,true);
  if(result!=STATE_SAVED){
    unsigned second=inspect(slot,1-first,&b,staging,true);
    if(second==STATE_SAVED||result==STATE_EMPTY)result=second;
  }
  if(result==STATE_SAVED)restore(staging);
  display_game_speed();return result;
}
