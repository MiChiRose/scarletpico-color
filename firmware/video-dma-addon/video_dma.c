/* Experimental transport-only extension of Features 2.2.1.
 * Called ONLY by the two row writes in present_region() on the video worker.
 * The producer/scale/diff algorithm, all clocks and SPI data format stay intact.
 * SD owns the bus only after video_wait_idle(); no outstanding DMA on return.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
extern int dma_claim_unused_channel(bool required);
extern int original_spi_write_blocking(void *spi,const uint8_t *src,size_t len);

#define REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define SPI0 0x4003c000u
#define DMA  0x50000000u
#define BUSY (1u<<24)
/* Zero-initialized; 1..12 are channel+1. 255 = use the original safe path.
 * A single SDK-claimed channel is reused for the lifetime of this boot.
 * Never hard-code a channel that SD or I2S might already own. */
static uint8_t channel_plus_one;

int video_dma_write(void *spi,const uint8_t *src,size_t len) {
 if((uintptr_t)spi!=SPI0 || len<32 || len>960)
  return original_spi_write_blocking(spi,src,len);
 if(!channel_plus_one) {
  int ch=dma_claim_unused_channel(false);
  channel_plus_one=ch>=0 && ch<12?(uint8_t)(ch+1):255;
  if(channel_plus_one!=255) {
   /* No IRQ on this channel; atomically preserve SD/audio IRQ enables. */
   REG(DMA+0x3000+0x404)=1u<<ch;
   REG(DMA+0x3000+0x414)=1u<<ch;
   REG(DMA+0x400)=1u<<ch;
  }
 }
 if(channel_plus_one==255)return original_spi_write_blocking(spi,src,len);
 unsigned ch=channel_plus_one-1;
 uintptr_t c=DMA+ch*0x40;
 uint32_t dmacr=REG(SPI0+0x24);
 REG(SPI0+0x24)=dmacr|2; /* TX DREQ only; restore before shared-bus handoff. */
 REG(c+0x00)=(uintptr_t)src;
 REG(c+0x04)=SPI0+0x08;
 REG(c+0x08)=len;
 /* Byte transfers in original order; fixed DR, increment source, SPI0 TX
  * DREQ=16, CHAIN_TO=self (disabled), quiet, no interrupt or high priority. */
 REG(c+0x0c)=(3u<<29)|(1u<<21)|(16u<<15)|(ch<<11)|(1u<<4)|1u;
 while(REG(c+0x0c)&BUSY) {}
 /* DMA completion means FIFO filled, NOT last pixel shifted onto the wire.
  * Do not let present_region reuse its row buffer or deassert CS early. */
 while(REG(SPI0+0x0c)&4u)(void)REG(SPI0+0x08);
 while(REG(SPI0+0x0c)&16u) {}
 while(REG(SPI0+0x0c)&4u)(void)REG(SPI0+0x08);
 REG(SPI0+0x20)=1; /* Clear RX overrun, exactly as SDK write-only SPI does. */
 REG(SPI0+0x24)=dmacr;
 return (int)len;
}
