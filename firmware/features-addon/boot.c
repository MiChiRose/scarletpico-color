/* One-shot boot identity. No emulator/APU state, clocks or SD are touched.
 * The existing 1072-byte PCM scratch is reused sequentially: first for a
 * single RGB565 scanline, then for synthesized audio. Core 1 is not running.
 * Audio's independent DMA blocks/queue never refer to this scratch directly. */
#include "features.h"
extern int16_t original_audio_pcm[536];
extern volatile uint32_t original_audio_queue[514];
extern void original_audio_submit(const int16_t *,size_t);

enum { LOGO_W=304, LOGO_H=72, LOGO_X=88, LOGO_Y=124,
       DESCENT_US=1800000, FRAME_US=33333, SOUND_FRAMES=11264,
       CHIME_FRAMES=11520, CHIME_MS=720 };
_Static_assert(LOGO_W*2<=sizeof original_audio_pcm,"Boot scanline must fit PCM scratch");
_Static_assert(128*4<=sizeof original_audio_pcm,"Chime block must fit PCM scratch");
/* SCARLETPICO, the same compact pixel-letter vocabulary as our launcher. */
static const uint8_t letters[11][5]={
 {0x46,0x49,0x49,0x49,0x31},{0x3e,0x41,0x41,0x41,0x22},
 {0x7e,0x11,0x11,0x11,0x7e},{0x7f,9,0x19,0x29,0x46},
 {0x7f,0x40,0x40,0x40,0x40},{0x7f,0x49,0x49,0x49,0x41},
 {1,1,0x7f,1,1},{0x7f,9,9,9,6},{0,0x41,0x7f,0x41,0},
 {0x3e,0x41,0x41,0x41,0x22},{0x3e,0x41,0x41,0x41,0x3e}
};
static void pixel(uint8_t *p,unsigned x,uint16_t c) {p[2*x]=c>>8;p[2*x+1]=c;}
static void logo_row(uint8_t *p,int y) {
 for(unsigned x=0;x<LOGO_W;x++)pixel(p,x,UI_BG);
 if(y<0 || y>=LOGO_H)return;
 int dy=2*y-(LOGO_H-1);
 for(int x=0;x<LOGO_W;x++) {
  int dx=x<36?71-2*x:x>=LOGO_W-36?2*x-535:0;
  unsigned d=dx*dx+dy*dy;
  if(d<=71*71 && d>=65*65)pixel(p,x,UI_ACCENT);
 }
 if(y>=22 && y<50) {
  unsigned bit=1u<<((y-22)/4);
  for(unsigned ch=0;ch<11;ch++)for(unsigned col=0;col<5;col++)
   if(letters[ch][col]&bit)for(unsigned k=0;k<4;k++)
    pixel(p,22+ch*24+col*4+k,ch<7?UI_ACCENT:UI_TEXT);
 }
}
void features_boot_draw(int previous_y,int y) {
 int top=previous_y<y?previous_y:y;
 int bottom=(previous_y>y?previous_y:y)+LOGO_H;
 if(top<0)top=0;
 if(bottom>320)bottom=320;
 if(bottom<=top)return;
 uint8_t *line=(uint8_t *)original_audio_pcm;
 /* Send the union of old/new bounds in one pass. No clear-then-draw flash,
  * no full-screen frame buffer, no writes elsewhere on the screen. */
 ui_pixels_begin(LOGO_X,(unsigned)top,LOGO_W,(unsigned)(bottom-top));
 for(int row=top;row<bottom;row++) {
  logo_row(line,row-y);ui_pixels_row(line,LOGO_W*2);
 }
 ui_pixels_end();
}
static int pulse(uint32_t phase,uint32_t step) {
 /* Four centred sub-samples soften the edges of a 50% duty pulse at 16 kHz.
  * This is a small box filter, not an emulator/APU or a new audio buffer. */
 int sum=0;
 phase+=step/8;
 for(unsigned k=0;k<4;k++,phase+=step/4)sum+=(phase>>31)?-1:1;
 return sum;
}
void features_chime_block(unsigned first) {
 for(unsigned i=0;i<128;i++) {
  unsigned n=first+i;
  int value=0;
  if(n<SOUND_FRAMES) {
   /* Game Boy-style pulse ping: periods 0x783/0x7c1 -> 1048.576/2080.508 Hz.
    * Reference: SameBoy/BootROMs/cgb_boot.asm (NR11=$80, NR12=$f3).
    * Independent synthesis, no boot ROM or recorded audio is embedded.
    * The second note begins at 84 ms and now rings out to 704 ms.
    * 1 ms attack, 100 ms final fade, then 16 ms of actual silent PCM before
    * stopping I2S. The old 400 ms chime released too abruptly. */
   unsigned at=n<1344?n:n-1344,duration=n<1344?1344:SOUND_FRAMES-1344;
   uint32_t step=n<1344?281474977u:558482097u;
   unsigned level=15-at/750; /* Envelope falls one step per 3/64 second. */
   unsigned remaining=duration-1-at,release=n<1344?32:1600;
   unsigned env=at<16?at*16:256;
   if(remaining<release)env=remaining*256/release;
   value=pulse(at*step,step)*(int)(level*80*env)/256;
  }
  original_audio_pcm[2*i]=original_audio_pcm[2*i+1]=(int16_t)value;
 }
}
static unsigned queued(void) {
 return original_audio_queue[512]-original_audio_queue[513];
}
static bool wait_queue(unsigned maximum) {
 uint32_t start=(uint32_t)time_us_64();
 while(queued()>maximum) {
  /* A failed DMA/IRQ must never strand the user on the boot screen. */
  if((uint32_t)((uint32_t)time_us_64()-start)>=100000u)return false;
  sleep_ms(1);
 }
 return true;
}
bool features_boot_chime(void) {
 if(!ui_volume){sleep_ms(CHIME_MS);return true;}
 if(!original_audio_start())return false;
 bool ok=true;
 for(unsigned first=0;first<CHIME_FRAMES;first+=128) {
  if(!wait_queue(512-128)){ok=false;break;}
  features_chime_block(first);original_audio_submit(original_audio_pcm,128);
 }
 if(ok)ok=wait_queue(0);
 if(ok)sleep_ms(18); /* Finish the two 8 ms DMA blocks, then quiet GPIO. */
 original_audio_stop();return ok;
}
void features_boot_ui_init(const uint8_t *record) {
 features_ui_init(record); /* Restore language, brightness and volume first. */
 ui_rect(0,0,480,320,UI_BG);
 uint32_t start=(uint32_t)time_us_64();
 int previous=-LOGO_H;
 bool skipped=false;
 for(;;) {
  if(feature_keys()&UI_START){skipped=true;break;}
  unsigned elapsed=(uint32_t)((uint32_t)time_us_64()-start);
  if(elapsed>DESCENT_US)elapsed=DESCENT_US;
  unsigned ms=elapsed/1000u;
  /* Gentle ease-out. Integer-only, monotonic, exactly centred at the end. */
  int y=-LOGO_H+(int)((LOGO_Y+LOGO_H)*ms*(3600u-ms)/3240000u);
  if(y!=previous){features_boot_draw(previous,y);previous=y;}
  if(elapsed==DESCENT_US)break;
  unsigned next=(elapsed/FRAME_US+1)*FRAME_US;
  while((uint32_t)((uint32_t)time_us_64()-start)<next) {
   if(feature_keys()&UI_START){skipped=true;break;}
   sleep_ms(1);
  }
  if(skipped)break;
 }
 if(previous!=LOGO_Y)features_boot_draw(previous,LOGO_Y);
 ui_text(210,208,"COLOR",UI_TEAL,UI_BG,2,5);
 if(!skipped){features_boot_chime();sleep_ms(350);}
 else sleep_ms(80);
 /* Start skips the entrance (also a no-motion boot option). Consume it so
  * it cannot launch the first game; other original boot shortcuts survive. */
 if(feature_keys()&UI_START)feature_release();
 ui_invalidate();
}
