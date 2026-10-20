/* Storage adapter only: the original MBC/CPU/PPU continue using gb_rom_read.
 * First 0x17f000 bytes stay XIP-fast. The tail uses two 2-KiB LRU slots. */
#include "features.h"
#include <string.h>
#include <stddef.h>

_Static_assert(sizeof(FSIZE_t)==8 && sizeof(FIL)==608 && offsetof(FIL,obj.objsize)==16,"FatFs ABI");
typedef struct {
 FIL file;
 uint32_t size, tag[2];
 unsigned recent;
 uint8_t bytes[4096];
} stream_t;
static stream_t *stream;
static char stream_path[288];

void features_stream_close(void) {
 if(!stream)return;
 original_video_wait_idle();original_sd_bus();
 f_close(&stream->file);original_free(stream);stream=NULL;
 original_display_select_bus();
}
static bool exact(FIL *f,void *p,unsigned n) {
 UINT got=0;return f_read(f,p,n,&got)==FR_OK && got==n;
}
bool features_prepare(const char *path,const uint8_t **rom,size_t *size) {
 features_stream_close();pause_pending=exit_requested=false;
 original_sd_bus();FIL file;
 if(f_open(&file,path,FA_READ)!=FR_OK){original_display_select_bus();return false;}
 FSIZE_t n=f_size(&file);
 if(n<=RESIDENT_SIZE) {
  f_close(&file);original_display_select_bus();
  return original_loader_prepare(path,rom,size);
 }
 /* Validate limits BEFORE allocating or touching the flash cache. */
 uint8_t signature[48];memset(signature,255,sizeof signature);
 memcpy(signature,"SPPAGE1",8);
 uint32_t total=(uint32_t)n,resident=RESIDENT_SIZE,marker=0x51a6c0de;
 memcpy(signature+8,&total,4);memcpy(signature+40,&resident,4);
 memcpy(signature+44,&marker,4);
 bool ok=n<=0x800000 && f_lseek(&file,0x134)==FR_OK && exact(&file,signature+12,28);
 if(ok) {
  const uint8_t *h=signature+12;
  ok=h[0x14]<=8 && total==(32768u<<h[0x14]);
 }
 f_close(&file);
 if(!ok){original_display_select_bus();return false;}
 unsigned path_len=0;
 while(path[path_len] && path_len<sizeof stream_path-1)path_len++;
 if(path[path_len]){original_display_select_bus();return false;}
 memcpy(stream_path,path,path_len+1);
 stream=original_malloc(sizeof *stream);
 if(!stream){original_display_select_bus();return false;}
 memset(stream,0,sizeof *stream);
 if(f_open(&stream->file,path,FA_READ)!=FR_OK){original_free(stream);stream=NULL;original_display_select_bus();return false;}
 stream->size=total;stream->tag[0]=stream->tag[1]=UINT32_MAX;
 ui_loading();original_sd_bus();
 if(memcmp((const void *)0x10080000,signature,sizeof signature)) {
  /* Commit metadata last. A failed read never makes a partial cache valid. */
  for(uint32_t off=0x80000;off<0x200000;off+=65536) {
   uint32_t irq=features_irq_off();original_flash_erase(off,65536);features_irq_restore(irq);
   ui_spinner_tick((uint32_t)time_us_64());original_sd_bus();
  }
  ok=f_lseek(&stream->file,0)==FR_OK;
  for(uint32_t off=0;ok && off<RESIDENT_SIZE;off+=4096) {
   ok=exact(&stream->file,stream->bytes,4096);
   if(!ok)break;
   for(unsigned p=0;p<4096;p+=256) {
    uint32_t irq=features_irq_off();
    original_flash_program(0x81000+off+p,stream->bytes+p,256);
    features_irq_restore(irq);
   }
   ui_spinner_tick((uint32_t)time_us_64());original_sd_bus();
  }
  if(ok) {
   uint8_t page[256];memset(page,255,sizeof page);memcpy(page,signature,sizeof signature);
   uint32_t irq=features_irq_off();original_flash_program(0x80000,page,256);features_irq_restore(irq);
  }
 }
 ui_invalidate();original_display_select_bus();
 if(!ok){features_stream_close();return false;}
 *rom=(const uint8_t *)0x10081000;*size=total;return true;
}
uint8_t features_rom_read(void *core,uint32_t address) {
 /* This callback is installed only for a validated ROM larger than resident
  * flash. Keep its common path independent of the FIL/cache heap object. */
 if(address<RESIDENT_SIZE)return ((const uint8_t *)0x10081000)[address];
 if(!stream || address>=stream->size)return 255;
 uint32_t block=address&~2047u;
 unsigned i;
 if(stream->tag[0]==block)i=0;
 else if(stream->tag[1]==block)i=1;
 else {
  i=1-stream->recent;
  /* Core 0 cannot publish a new video job while inside this callback.
   * Wait for the last job before claiming shared SPI. No lock spans XIP. */
  original_video_wait_idle();bool guard=original_guard_pause();original_sd_bus();
  unsigned n=stream->size-block;if(n>2048)n=2048;
  stream->tag[i]=UINT32_MAX;
  bool ok=f_lseek(&stream->file,block)==FR_OK && exact(&stream->file,stream->bytes+i*2048,n);
  original_display_select_bus();original_guard_resume(guard);
  if(!ok)original_core_error(core,2,(uint16_t)address);
  stream->tag[i]=block;
 }
 stream->recent=i;return stream->bytes[i*2048+(address&2047)];
}
bool features_load(const uint8_t *rom,size_t size,void *draw) {
 bool paged=stream!=NULL;
 /* Release the temporary loader allocation BEFORE the core frees/replaces
  * the previous game's SRAM. Otherwise the cache can split the heap and
  * needlessly prevent allocation of the optional changed-frame buffer. */
 if(paged)features_stream_close();
 bool ok=original_emulator_load(rom,size,draw);
 if(ok && paged) {
  stream=original_malloc(sizeof *stream);
  if(!stream){feature_error("NOT ENOUGH MEMORY FOR ROM CACHE");return false;}
  memset(stream,0,sizeof *stream);original_sd_bus();
  if(f_open(&stream->file,stream_path,FA_READ)!=FR_OK) {
   original_free(stream);stream=NULL;original_display_select_bus();
   feature_error("ROM CARD READ ERROR");return false;
  }
  uint8_t header[28];
  ok=f_size(&stream->file)==size && f_lseek(&stream->file,0x134)==FR_OK &&
      exact(&stream->file,header,28) && !memcmp(header,rom+0x134,28);
  stream->size=size;stream->tag[0]=stream->tag[1]=UINT32_MAX;
  original_display_select_bus();
  if(!ok)feature_error("ROM CHANGED OR REMOVED");
  else *(void **)CORE=(void *)features_rom_read;
 }
 if(!ok)features_stream_close();
 return ok;
}
void features_stop(void) {
 original_addon_stop();features_stream_close();pause_pending=exit_requested=false;
}
