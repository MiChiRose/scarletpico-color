#include "../imported/scarletpico-rp2350-source/console.h"
#include "ff.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#ifndef TEST_STAGING_SIZE
#define TEST_STAGING_SIZE 138240
#endif
static uint8_t core[0xc320],apu[316],ram[131072],rom[32768],staging[TEST_STAGING_SIZE];
static unsigned ram_size=32768;
static bool dirty,sd;
typedef struct {char name[64];uint8_t bytes[200000];unsigned size;} file_t;
static file_t files[12];
static bool fail_write,fail_read;
unsigned native_core_size(void){return sizeof core;}
void native_core_copy(void *p){memcpy(p,core,sizeof core);}
void native_core_restore(const void *p){memcpy(core,p,sizeof core);}
unsigned console_apu_size(void){return sizeof apu;}
void console_apu_snapshot(uint8_t *p){memcpy(p,apu,sizeof apu);}
void console_apu_restore(const uint8_t *p){memcpy(apu,p,sizeof apu);}
void *native_staging(unsigned *n){*n=sizeof staging;return staging;}
const uint8_t *native_rom(unsigned *n){*n=sizeof rom;return rom;}
uint8_t *native_save_ram(unsigned *n){*n=ram_size;return ram;}
void native_mark_save_dirty(void){dirty=true;}
void display_sd_speed(void){sd=true;}
uint32_t display_game_speed(void){sd=false;return 100000000;}
FRESULT f_mkdir(const TCHAR *p){assert(sd);return FR_OK;}
FRESULT f_open(FIL *f,const TCHAR *path,BYTE mode){
#ifdef SCARLET_RP2040_NATIVE
  assert(!strncmp(path,"0:/scarlet2040/states/",21));
#endif
  assert(sd);file_t *v=NULL;
  for(unsigned i=0;i<12;i++)if(!strcmp(files[i].name,path)){v=&files[i];break;}
  if(!v){
    if(!(mode&FA_WRITE))return FR_NO_FILE;
    for(unsigned i=0;i<12;i++)if(!files[i].name[0]){v=&files[i];strcpy(v->name,path);break;}
    if(!v)return FR_DISK_ERR;
  }
  if(mode&FA_CREATE_ALWAYS)v->size=0;
  memset(f,0,sizeof *f);f->obj.fs=(FATFS *)v;return FR_OK;
}
FRESULT f_read(FIL *f,void *p,UINT n,UINT *got){
  assert(sd);file_t *v=(file_t *)f->obj.fs;
  if(fail_read){*got=0;return FR_DISK_ERR;}
  unsigned available=f->fptr<v->size?v->size-f->fptr:0;if(n>available)n=available;
  memcpy(p,v->bytes+f->fptr,n);f->fptr+=n;*got=n;return FR_OK;
}
FRESULT f_write(FIL *f,const void *p,UINT n,UINT *got){
  assert(sd);file_t *v=(file_t *)f->obj.fs;
  if(fail_write){*got=0;return FR_DISK_ERR;}
  assert(f->fptr+n<=sizeof v->bytes);memcpy(v->bytes+f->fptr,p,n);
  f->fptr+=n;v->size=f->fptr;*got=n;return FR_OK;
}
FRESULT f_sync(FIL *f){assert(sd);return FR_OK;}
FRESULT f_close(FIL *f){assert(sd);return FR_OK;}
static void set_state(unsigned v){memset(core,v,sizeof core);memset(apu,v+1,sizeof apu);memset(ram,v+2,ram_size);}
static void check(unsigned v){
  for(unsigned i=0;i<sizeof core;i++)assert(core[i]==v);
  for(unsigned i=0;i<sizeof apu;i++)assert(apu[i]==v+1);
  for(unsigned i=0;i<ram_size;i++)assert(ram[i]==v+2);
}
int main(void){
  memcpy(rom+0x134,"STATE TEST",10);console_state_bind();
  assert(state_status(0)==STATE_EMPTY);assert(state_load(0)==STATE_EMPTY);
  set_state(10);assert(state_save(0)==STATE_SAVED);assert(!sd);
  set_state(20);assert(state_save(0)==STATE_SAVED);
  set_state(30);assert(state_load(0)==STATE_SAVED);check(20);assert(dirty);
  /* Corrupt latest payload: the untouched older generation remains usable. */
  files[1].bytes[100]^=1;set_state(30);
  assert(state_load(0)==STATE_SAVED);check(10);
  fail_write=true;set_state(40);assert(state_save(0)==STATE_IO_ERROR);
  fail_write=false;assert(state_load(0)==STATE_SAVED);check(10);
  files[0].bytes[110]^=1;set_state(50);dirty=false;
  assert(state_load(0)!=STATE_SAVED);check(50);assert(!dirty);
  assert(state_save(5)==STATE_INVALID);assert(state_load(5)==STATE_INVALID);
  ram_size=131072;assert(state_save(0)==STATE_NO_MEMORY);
  assert(state_load(0)==STATE_NO_MEMORY);ram_size=32768;
  /* Same title/size but different ROM bytes must select a different identity. */
  rom[2000]^=1;console_state_bind();assert(state_status(0)==STATE_EMPTY);
  for(unsigned i=0;i<5;i++){set_state(60+i);assert(state_save(i)==STATE_SAVED);}
  for(unsigned i=0;i<5;i++){set_state(0);assert(state_load(i)==STATE_SAVED);check(60+i);}
  fail_read=true;set_state(80);assert(state_load(0)==STATE_IO_ERROR);check(80);
  fail_read=false;puts("PASS native snapshots: 5 slots, RAM/APU, backup recovery, ROM identity, I/O and memory errors leave game intact");
}
