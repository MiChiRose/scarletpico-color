// Hardware-independent checks. This does not certify GPIO, SPI timing or FPS.
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PEANUT_FULL_GBC_SUPPORT 1
#define ENABLE_SOUND 0
#include "peanut_gb.h"
#include "video_math.h"
static uint8_t rom[32768];
static unsigned lines;
static uint8_t read_rom(struct gb_s *g,uint_fast32_t a) {
  assert(a<sizeof(rom));return rom[a];
}
static uint8_t read_ram(struct gb_s *g,uint_fast32_t a){return 0xff;}
static void write_ram(struct gb_s *g,uint_fast32_t a,uint8_t v){}
static void error(struct gb_s *g,enum gb_error_e e,uint16_t a){assert(!"emulation error");}
static void line(struct gb_s *g,const uint8_t *p,uint_fast8_t y) {
  assert(y<144);for(unsigned x=0;x<160;x++)assert((p[x]&63)<64);
  lines++;
}
static void core_smoke(int cgb) {
  memset(rom,0,sizeof(rom));memcpy(rom+0x134,"LCDTEST",7);
  rom[0x143]=cgb?0x80:0;
  rom[0x100]=0xc3;rom[0x101]=0x50;rom[0x102]=1;
  // LD A,$91; LDH ($40),A; JR -2. An original minimal, self-contained test ROM.
  uint8_t program[]={0x3e,0x91,0xe0,0x40,0x18,0xfe};
  memcpy(rom+0x150,program,sizeof(program));
  uint8_t sum=0;for(unsigned a=0x134;a<=0x14c;a++)sum=sum-rom[a]-1;
  rom[0x14d]=sum;
  struct gb_s g;
  assert(gb_init(&g,read_rom,read_ram,write_ram,error,NULL)==GB_INIT_NO_ERROR);
  assert(g.cgb.cgbMode==cgb);gb_init_lcd(&g,line);lines=0;
  if(cgb) {
    __gb_write(&g,0xff68,0xbf);__gb_write(&g,0xff69,0x12);
    assert(g.cgb.BGPaletteID==0&&g.cgb.BGPalette[63]==0x12);
    __gb_write(&g,0xff6a,0xbf);__gb_write(&g,0xff6b,0x34);
    assert(g.cgb.OAMPaletteID==0&&g.cgb.OAMPalette[63]==0x34);
  }
  for(unsigned f=0;f<120;f++)gb_run_frame(&g);
  assert(lines>=119*144&&lines<=121*144);
  printf("%s: 120 frames, %u scanlines, no invalid memory access\n",cgb?"GBC":"GB",lines);
}
int main(void) {
  assert(color555_to565(0x7c00)==0xf800);
  assert(color555_to565(0x03e0)==0x07e0);
  assert(color555_to565(0x001f)==0x001f);
  assert(color555_to565(0x7fff)==0xffff);
  for(unsigned x=0;x<320;x++)assert(scaled_source(x,160,320)==x/2);
  for(unsigned y=0;y<288;y++)assert(scaled_source(y,144,288)==y/2);
  const unsigned sizes[][2]={{160,144},{240,216},{320,288},{356,320}};
  for(unsigned i=0;i<4;i++) {
    for(unsigned x=0;x<sizes[i][0];x++)assert(scaled_source(x,160,sizes[i][0])<160);
    for(unsigned y=0;y<sizes[i][1];y++)assert(scaled_source(y,144,sizes[i][1])<144);
  }
  core_smoke(0);core_smoke(1);puts("RGB565 conversion and all scaling modes: PASS");
}
