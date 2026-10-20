/* Experimental video transport: same pixels, same clocks, same dirty regions.
 * No emulator changes. Core 1 owns SPI until the entire region is drained.
 * Two bounded scanlines live on its 4 KiB stack, not in permanent RAM/heap. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
extern int dma_claim_unused_channel(bool);
extern void original_region(const uint16_t *,unsigned,unsigned,unsigned,unsigned,unsigned);
extern void original_window(unsigned,unsigned,unsigned,unsigned);
extern void original_full(const uint16_t *,unsigned);
extern unsigned original_changed(const uint16_t *,uint16_t *,unsigned);
extern uint64_t time_us_64(void);
extern uint32_t clock_get_hz(unsigned);
extern int original_printf(const char *,...);
#define REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define SPI 0x4003c000u
#define DMA 0x50000000u
#define SIO 0xd0000000u
#define BUSY (1u<<24)
static uint8_t channel_plus_one;
static unsigned pixels_sent,regions,build_us,transport;
struct sample {unsigned mode,pixels,regions,total_us,build_us,spi_hz,transport;};
static volatile struct sample latest;
static volatile unsigned sequence;
static uint32_t now(void){return (uint32_t)time_us_64();}
static void barrier(void){__asm volatile("dmb" ::: "memory");}
static bool wait_dma(uintptr_t c,unsigned ch) {
 uint32_t start=now();
 while(REG(c+12)&BUSY) {
  if((uint32_t)(now()-start)>=5000) {
   REG(DMA+0x444)=1u<<ch;
   /* Keep stack/source alive until abort really completes. The existing
    * core-0 video watchdog covers an unresponsive DMA fabric. IRQs are off. */
   while(REG(DMA+0x444)&(1u<<ch)) {}
   return false;
  }
 }
 return !(REG(c+12)&(3u<<29));
}
static void drain(void) {
 while(REG(SPI+12)&4u)(void)REG(SPI+8);
 while(REG(SPI+12)&16u) {}
 while(REG(SPI+12)&4u)(void)REG(SPI+8);
 REG(SPI+32)=1;
}
void video_fast_region(const uint16_t *pixels,unsigned scale,
 unsigned left,unsigned top,unsigned right,unsigned bottom) {
 unsigned width=scale==5?356:scale>=2&&scale<=4?scale*80:160;
 unsigned height=scale==5?320:scale>=2&&scale<=4?scale*72:144;
 if(left>=right || top>=bottom || right>width || bottom>height)return;
 regions++;pixels_sent+=(right-left)*(bottom-top);
 if(!channel_plus_one) {
  int ch=dma_claim_unused_channel(false);
  channel_plus_one=ch>=0&&ch<12?(uint8_t)(ch+1):255;
  if(channel_plus_one!=255) {
   REG(DMA+0x3404)=1u<<ch;REG(DMA+0x3414)=1u<<ch;
   REG(DMA+0x400)=1u<<ch;
  }
 }
 if(channel_plus_one==255) {
  transport=0;original_region(pixels,scale,left,top,right,bottom);return;
 }
 /* Reuse the pinned renderer's lookup tables; only core 1 touches them. */
 uint8_t *xmap=(uint8_t *)0x2001dcb4,*ymap=(uint8_t *)0x2001de18;
 uint8_t *mapped=(uint8_t *)0x2001e25b;
 if(*mapped!=scale) {
  for(unsigned x=0;x<width;x++)xmap[x]=x*160/width;
  for(unsigned y=0;y<height;y++)ymap[y]=y*144/height;
  *mapped=scale;
 }
 unsigned x0=(480-width)/2,y0=(320-height)/2;
 original_window(x0+left,y0+top,x0+right-1,y0+bottom-1);
 drain();
 uint32_t cr0=REG(SPI),cr1=REG(SPI+4),dmacr=REG(SPI+36);
 REG(SPI+4)=cr1&~2u;REG(SPI)=(cr0&~15u)|15u;REG(SPI+4)=cr1;
 REG(SPI+36)=dmacr|2u;
 REG(SIO+20)=1u<<8;REG(SIO+24)=1u<<5; /* DC=data, CS=low */
 uint16_t lines[2][356];
 unsigned ch=channel_plus_one-1,count=right-left,slot=0,last_row=144;
 uintptr_t c=DMA+ch*64;
 uint32_t ctrl=(3u<<29)|(1u<<21)|(16u<<15)|(ch<<11)|(1u<<4)|(1u<<2)|1u;
 bool pending=false,ok=true;
 for(unsigned y=top;y<bottom;y++) {
  unsigned row=ymap[y];
  if(row!=last_row) {
   /* Never modify the line DMA is currently reading. The other line is
    * expanded while the preceding one is on the wire. */
   slot^=1;
   uint32_t start=now();
   const uint16_t *src=pixels+row*160;
   for(unsigned x=left;x<right;x++)lines[slot][x-left]=src[xmap[x]];
   build_us+=now()-start;
   last_row=row;
  }
  if(pending && !wait_dma(c,ch)){ok=false;break;}
  REG(c)=(uintptr_t)lines[slot];REG(c+4)=SPI+8;REG(c+8)=count;
  REG(c+12)=ctrl;pending=true;
 }
 if(ok && pending)ok=wait_dma(c,ch);
 drain();REG(SIO+20)=1u<<5;
 REG(SPI+4)=cr1&~2u;REG(SPI)=cr0;REG(SPI+4)=cr1;REG(SPI+36)=dmacr;
 transport=1;
 if(!ok) {
  /* A partial DMA row cannot be repaired by appending arbitrary bytes.
   * Reissue the whole address window through the unchanged old renderer. */
  channel_plus_one=255;transport=2;
  original_region(pixels,scale,left,top,right,bottom);
 }
}
static void finish(unsigned mode,uint32_t start) {
 unsigned total=now()-start;
 unsigned divisor=(REG(SPI+16)&255u)*(((REG(SPI)>>8)&255u)+1u);
 unsigned hz=divisor?clock_get_hz(6)/divisor:0;
 sequence++;barrier();
 latest=(struct sample){mode,pixels_sent,regions,total,build_us,hz,transport};
 barrier();sequence++;
}
void video_fast_full(const uint16_t *p,unsigned scale) {
 pixels_sent=regions=build_us=transport=0;uint32_t start=now();
 original_full(p,scale);finish(0,start);
}
unsigned video_fast_changed(const uint16_t *p,uint16_t *previous,unsigned scale) {
 pixels_sent=regions=build_us=transport=0;uint32_t start=now();
 unsigned result=original_changed(p,previous,scale);finish(1,start);return result;
}
/* Original core-0 PERF call site, with its exact six-argument ABI. No serial
 * printing from core 1 and no extra display overlays. Snapshot can be skipped
 * if the other core is publishing; never block either core for diagnostics. */
int video_fast_perf(const char *format,const char *scale,unsigned emu,unsigned lcd,
 unsigned cpu_us,unsigned lcd_us) {
 int result=original_printf(format,scale,emu,lcd,cpu_us,lcd_us);
 unsigned seq=sequence;if(seq&1)return result;
 barrier();struct sample s=latest;barrier();
 if(seq==sequence)
  original_printf("VIDEO16 mode=%u pixels=%u regions=%u total=%u build=%u spi=%u path=%u\n",
   s.mode,s.pixels,s.regions,s.total_us,s.build_us,s.spi_hz,s.transport);
 return result;
}
