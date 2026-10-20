/* Existing minigb APU + I2S. RP2040 audio uses DMA IRQ1; SD uses IRQ0. */
#include "console.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/pio.h"
#include "hardware/sync.h"
#include "audio_i2s.pio.h"
#include <string.h>
#undef MIN
#undef MAX
#include "../../vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu/minigb_apu.c"

int16_t original_audio_pcm[536];
volatile uint32_t original_audio_queue[514];
static uint32_t blocks[2][128];
static int sm,channels[2];
static unsigned offset;
static PIO const audio_pio=pio1;
static bool allocated,active,playing,failed;
static uint32_t remainder;
static volatile unsigned underruns;
static unsigned dropped;
static void block_fill(unsigned i) {
  uint32_t head=original_audio_queue[512],tail=original_audio_queue[513];
  unsigned n=0;
  while(n<128&&tail!=head)blocks[i][n++]=original_audio_queue[(tail++)&511];
  if(n<128){memset(blocks[i]+n,0,(128-n)*sizeof(uint32_t));underruns++;}
  __dmb();original_audio_queue[513]=tail;
}
static void audio_irq(void) {
  for(unsigned i=0;i<2;i++){
    if(!dma_irqn_get_channel_status(1,channels[i]))continue;
    dma_irqn_acknowledge_channel(1,channels[i]);
    if(!active)continue;
    block_fill(i);dma_channel_set_read_addr(channels[i],blocks[i],false);
    dma_channel_set_trans_count(channels[i],128,false);
  }
}
void original_audio_stop(void) {
  if(!allocated)return;
  uint32_t irq=save_and_disable_interrupts();active=playing=false;
  pio_sm_set_enabled(audio_pio,sm,false);
  for(unsigned i=0;i<2;i++){
    dma_irqn_set_channel_enabled(1,channels[i],false);
    hw_clear_bits(&dma_hw->ch[channels[i]].ctrl_trig,DMA_CH0_CTRL_TRIG_EN_BITS);
  }
  for(unsigned i=0;i<2;i++){
    dma_channel_abort(channels[i]);dma_irqn_acknowledge_channel(1,channels[i]);
  }
  pio_sm_clear_fifos(audio_pio,sm);
  original_audio_queue[512]=original_audio_queue[513]=0;
  restore_interrupts(irq);
  for(unsigned pin=11;pin<=13;pin++){gpio_init(pin);gpio_put(pin,0);gpio_set_dir(pin,GPIO_OUT);}
}
bool original_audio_start(void) {
  original_audio_stop();if(failed)return false;
  if(!allocated){
    sm=pio_claim_unused_sm(audio_pio,false);
    if(sm<0){failed=true;return false;}
    channels[0]=dma_claim_unused_channel(false);channels[1]=dma_claim_unused_channel(false);
    if(channels[0]<0||channels[1]<0||!pio_can_add_program(audio_pio,&scarlet_i2s_program)){
      if(channels[0]>=0)dma_channel_unclaim(channels[0]);
      if(channels[1]>=0)dma_channel_unclaim(channels[1]);
      pio_sm_unclaim(audio_pio,sm);failed=true;return false;
    }
    offset=pio_add_program(audio_pio,&scarlet_i2s_program);
    irq_add_shared_handler(DMA_IRQ_1,audio_irq,PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
    allocated=true;
  }
  for(unsigned pin=11;pin<=13;pin++)pio_gpio_init(audio_pio,pin);
  pio_sm_set_consecutive_pindirs(audio_pio,sm,11,3,true);
  pio_sm_config cfg=scarlet_i2s_program_get_default_config(offset);
  sm_config_set_out_pins(&cfg,13,1);sm_config_set_sideset_pins(&cfg,11);
  sm_config_set_out_shift(&cfg,false,true,32);sm_config_set_fifo_join(&cfg,PIO_FIFO_JOIN_TX);
  uint32_t div256=clock_get_hz(clk_sys)/4000u;
  sm_config_set_clkdiv_int_frac8(&cfg,div256>>8,div256&255u);
  pio_sm_init(audio_pio,sm,offset,&cfg);pio_sm_exec(audio_pio,sm,pio_encode_set(pio_x,14));
  original_audio_queue[512]=original_audio_queue[513]=0;underruns=dropped=0;
  for(unsigned i=0;i<2;i++){
    dma_channel_config dc=dma_channel_get_default_config(channels[i]);
    channel_config_set_transfer_data_size(&dc,DMA_SIZE_32);
    channel_config_set_read_increment(&dc,true);channel_config_set_write_increment(&dc,false);
    channel_config_set_dreq(&dc,pio_get_dreq(audio_pio,sm,true));
    channel_config_set_chain_to(&dc,channels[1-i]);
    dma_channel_configure(channels[i],&dc,&audio_pio->txf[sm],blocks[i],128,false);
    dma_irqn_acknowledge_channel(1,channels[i]);dma_irqn_set_channel_enabled(1,channels[i],true);
  }
  active=true;irq_set_enabled(DMA_IRQ_1,true);return true;
}
static void start_prefilled(void) {
  if(playing||original_audio_queue[512]-original_audio_queue[513]<384)return;
  uint32_t irq=save_and_disable_interrupts();
  block_fill(0);block_fill(1);playing=true;
  dma_start_channel_mask(1u<<channels[0]);pio_sm_set_enabled(audio_pio,sm,true);
  restore_interrupts(irq);
}
void original_audio_submit(const int16_t *pcm,size_t frames) {
  if(!active)return;
  for(unsigned i=0;i<frames;i++){
    uint32_t head=original_audio_queue[512],tail=original_audio_queue[513];
    if(head-tail>=512){dropped+=frames-i;break;}
    /* MAX98357A is mono: preserve both Game Boy channels whatever SD_MODE. */
    int32_t mono=((int32_t)pcm[2*i]+pcm[2*i+1])*ui_volume/200;
    uint32_t sample=(uint16_t)(int16_t)mono;
    original_audio_queue[head&511]=(sample<<16)|sample;
    __dmb();original_audio_queue[512]=head+1;start_prefilled();
  }
}
void console_apu_init(void){audio_init();remainder=0;}
void console_audio_frame(void) {
  remainder+=16000u*70224u;unsigned frames=remainder>>22;remainder&=4194303u;
  audio_callback(NULL,(uint8_t *)original_audio_pcm,frames*4);
  original_audio_submit(original_audio_pcm,frames);
}
unsigned console_apu_size(void){return sizeof audio_mem+sizeof chans+sizeof vol_l+sizeof vol_r+4;}
void console_apu_snapshot(uint8_t *p) {
  memcpy(p,audio_mem,sizeof audio_mem);p+=sizeof audio_mem;
  memcpy(p,chans,sizeof chans);p+=sizeof chans;
  memcpy(p,&vol_l,4);memcpy(p+4,&vol_r,4);memcpy(p+8,&remainder,4);
}
void console_apu_restore(const uint8_t *p) {
  memcpy(audio_mem,p,sizeof audio_mem);p+=sizeof audio_mem;
  memcpy(chans,p,sizeof chans);p+=sizeof chans;
  memcpy(&vol_l,p,4);memcpy(&vol_r,p+4,4);memcpy(&remainder,p+8,4);
}
