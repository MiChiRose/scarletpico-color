/* Same lossless 8x8 palette cache and allocator as SHADOW, cheaper codec.
 * No hashes, discarded colours, additional RAM, or changes to the core/DMA.
 * RP2040 little-endian, malloc/framebuffer/tile rows are word aligned. */
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
extern void original_full(const uint16_t *,unsigned);
extern void original_select_bus(void);
extern void video_fast_region(const uint16_t *,unsigned,unsigned,unsigned,unsigned,unsigned);
enum { COLS=20, ROWS=18, TILES=COLS*ROWS, HEADER=4+TILES };
typedef struct { uint8_t bits,scale; uint16_t reserved; uint8_t valid[TILES]; uint8_t data[]; } shadow;
typedef struct {uint8_t left,top,right,bottom;} rect;
typedef uint32_t alias32 __attribute__((may_alias));
typedef uint16_t alias16 __attribute__((may_alias));
_Static_assert(sizeof(shadow)==HEADER && HEADER%4==0,"Pinned cache ABI/alignment");
static unsigned width(unsigned scale){return scale==5?356:scale>=2&&scale<=4?scale*80:160;}
static unsigned height(unsigned scale){return scale==5?320:scale>=2&&scale<=4?scale*72:144;}

/* One packed word per row (halfword in low-memory mode). Constant bit widths
 * remove per-pixel bit-count multiplies, read/modify/write and generic shifts.
 * Adjacent equal pixels reuse their index. Palette order stays first-seen. */
#define ENCODER(BITS, TYPE) \
static void encode##BITS(uint8_t *data,uint8_t *valid,const uint16_t *p) { \
 uint16_t *palette=(uint16_t *)data; TYPE *packed=(TYPE *)(palette+(1u<<BITS)); \
 unsigned used=0,last=0;uint16_t last_color=0;*valid=0; \
 for(unsigned y=0;y<8;y++,p+=160) { \
  uint32_t row=0; \
  for(unsigned x=0;x<8;x++) { \
   uint16_t color=p[x]; \
   if(!used || color!=last_color) { \
    unsigned i=0;while(i<used && palette[i]!=color)i++; \
    if(i==used){if(used==(1u<<BITS))return;palette[used++]=color;} \
    last=i;last_color=color; \
   } \
   row|=last<<(x*BITS); \
  } \
  packed[y]=(TYPE)row; \
 } \
 *valid=1; \
}
ENCODER(4,alias32)
ENCODER(2,alias16)

/* Test aligned pairs against exact reconstructed RGB565 words. Only changed
 * rows update bounds; unchanged pixels do not repeatedly update rectangles. */
#define COMPARER(BITS, TYPE) \
static rect compare##BITS(const uint16_t *p,const uint8_t *data) { \
 const uint16_t *palette=(const uint16_t *)data; \
 const TYPE *packed=(const TYPE *)(palette+(1u<<BITS)); \
 unsigned columns=0,top=8,bottom=0; \
 for(unsigned y=0;y<8;y++,p+=160) { \
  unsigned codes=packed[y],mask=0; \
  for(unsigned pair=0;pair<4;pair++,codes>>=BITS*2) { \
   uint32_t expected=palette[codes&((1u<<BITS)-1)] | \
           (uint32_t)palette[(codes>>BITS)&((1u<<BITS)-1)]<<16; \
   uint32_t diff=((const alias32 *)p)[pair]^expected; \
   if(diff) { \
    if(diff&65535u)mask|=1u<<(pair*2); \
    if(diff>>16)mask|=2u<<(pair*2); \
   } \
  } \
  if(mask){columns|=mask;if(top==8)top=y;bottom=y+1;} \
 } \
 if(!columns)return (rect){0,0,0,0}; \
 unsigned left=0,right=8; \
 while(!(columns&(1u<<left)))left++; \
 while(!(columns&(1u<<(right-1))))right--; \
 return (rect){left,top,right,bottom}; \
}
COMPARER(4,alias32)
COMPARER(2,alias16)

static void seed(shadow *s,const uint16_t *p,unsigned scale) {
 unsigned tile=0;uint8_t *data=s->data;unsigned stride=s->bits==4?64:24;
 for(unsigned y=0;y<144;y+=8)for(unsigned x=0;x<160;x+=8,tile++,data+=stride) {
  if(s->bits==4)encode4(data,s->valid+tile,p+y*160+x);
  else encode2(data,s->valid+tile,p+y*160+x);
 }
 s->scale=scale;
}
void *video_shadow_fast_seed(void *dest,const uint16_t *p,size_t n) {
 (void)n;seed(dest,p,*(volatile uint8_t *)0x2001e260);return dest;
}
static unsigned send(const uint16_t *p,unsigned scale,rect r) {
 unsigned w=width(scale),h=height(scale);
 unsigned l=(r.left*w+159)/160,rr=(r.right*w+159)/160;
 unsigned t=(r.top*h+143)/144,b=(r.bottom*h+143)/144;
 video_fast_region(p,scale,l,t,rr,b);return (rr-l)*(b-t);
}
unsigned video_shadow_fast_changed(const uint16_t *p,void *cache,unsigned scale) {
 shadow *s=cache;
 if(!s || s->scale!=scale) {
  original_full(p,scale);if(s)seed(s,p,scale);
  return width(scale)*height(scale);
 }
 rect active[COLS],next[COLS];unsigned active_count=0,sent=0,tile=0;
 unsigned stride=s->bits==4?64:24;uint8_t *data=s->data;bool selected=false;
 for(unsigned band=0;band<ROWS;band++) {
  unsigned count=0;const uint16_t *src=p+band*1280;
  for(unsigned col=0;col<COLS;col++,tile++,data+=stride,src+=8) {
   rect r=s->valid[tile]?(s->bits==4?compare4(src,data):compare2(src,data)):(rect){0,0,8,8};
   if(!r.right)continue;
   if(s->bits==4)encode4(data,s->valid+tile,src);else encode2(data,s->valid+tile,src);
   r.left+=col*8;r.right+=col*8;r.top+=band*8;r.bottom+=band*8;
   if(count && r.left<=next[count-1].right+2u) {
    rect *q=&next[count-1];q->right=r.right;
    if(r.top<q->top)q->top=r.top;
    if(r.bottom>q->bottom)q->bottom=r.bottom;
   }else next[count++]=r;
  }
  if(count && !selected){original_select_bus();selected=true;}
  for(unsigned n=0;n<count;n++)for(unsigned a=0;a<active_count;a++) {
   if(active[a].right && active[a].left==next[n].left &&
      active[a].right==next[n].right && active[a].bottom==next[n].top) {
    next[n].top=active[a].top;active[a].right=0;break;
   }
  }
  for(unsigned a=0;a<active_count;a++)if(active[a].right)sent+=send(p,scale,active[a]);
  for(unsigned n=0;n<count;n++)active[n]=next[n];
  active_count=count;
 }
 for(unsigned a=0;a<active_count;a++)sent+=send(p,scale,active[a]);
 return sent;
}
