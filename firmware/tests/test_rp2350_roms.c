/* Real native core/APU with supplied local games; no files are changed. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <setjmp.h>
#include "minigb_apu.h"
#define PEANUT_FULL_GBC_SUPPORT 1
#define ENABLE_SOUND 1
#include "peanut_gb.h"
static uint8_t *rom,ram[131072];static size_t size;
static unsigned lines;static jmp_buf escape;
static uint8_t rr(struct gb_s *g,uint_fast32_t a){assert(a<size);return rom[a];}
static uint8_t cr(struct gb_s *g,uint_fast32_t a){assert(a<sizeof ram);return ram[a];}
static void cw(struct gb_s *g,uint_fast32_t a,uint8_t v){assert(a<sizeof ram);ram[a]=v;}
static void err(struct gb_s *g,enum gb_error_e e,uint16_t a){fprintf(stderr,"CORE ERROR %u AT %04X\n",e,a);longjmp(escape,1);}
static void line(struct gb_s *g,const uint8_t *p,uint_fast8_t y){assert(y<144);for(unsigned i=0;i<160;i++)assert((p[i]&63)<64);lines++;}
int main(int argc,char **argv){
  assert(argc>1);alarm(45);
  for(int r=1;r<argc;r++){
    FILE *f=fopen(argv[r],"rb");assert(f);fseek(f,0,SEEK_END);size=ftell(f);rewind(f);
    rom=malloc(size);assert(rom&&fread(rom,1,size,f)==size);fclose(f);
    struct gb_s g;audio_init();memset(ram,255,sizeof ram);
    assert(gb_init(&g,rr,cr,cw,err,NULL)==GB_INIT_NO_ERROR);gb_init_lcd(&g,line);
    assert(!setjmp(escape));uint32_t remainder=0;unsigned long long nonzero=0,samples=0;lines=0;
    for(unsigned frame=0;frame<1800;frame++){
      g.direct.joypad=255;
      if(frame>180&&frame%240<4)g.direct.joypad&=~8;
      if(frame>400&&frame%120<8)g.direct.joypad&=~1;
      if(frame>700)g.direct.joypad&=~(1u<<(4+(frame/60)%4));
      gb_run_frame(&g);
      int16_t pcm[536];remainder+=16000u*70224u;unsigned n=remainder>>22;remainder&=4194303u;
      assert(n<=268);audio_callback(NULL,(uint8_t *)pcm,n*4);samples+=n;
      for(unsigned i=0;i<n*2;i++)nonzero+=pcm[i]!=0;
    }
    assert(nonzero>1000);assert(samples==((unsigned long long)1800*16000*70224>>22));
    printf("PASS native ROM %s: %s, 1800 frames, %u scanlines, %llu nonzero PCM samples\n",argv[r],g.cgb.cgbMode?"GBC":"GB",lines,nonzero);fflush(stdout);free(rom);
  }
}
