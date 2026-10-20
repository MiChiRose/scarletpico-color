/* Experimental lossless, bounded previous-frame cache for the pinned VIDEO16 image.
 * Each 8x8 tile has an actual RGB565 palette + packed indices. A tile with
 * too many colours is ALWAYS redrawn, never approximated or hash-compared.
 * Only the optional previous-frame allocation changes; both producer buffers,
 * emulator, audio, clocks and original worker lifetime remain untouched. */
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
extern void *original_malloc(size_t);
extern void original_full(const uint16_t *,unsigned);
extern void original_select_bus(void);
extern void video_fast_region(const uint16_t *,unsigned,unsigned,unsigned,unsigned,unsigned);
extern int previous_perf(const char *,const char *,unsigned,unsigned,unsigned,unsigned);
extern int original_printf(const char *,...);
enum { COLS=20, ROWS=18, TILES=COLS*ROWS, HEADER=4+TILES };
typedef struct { uint8_t bits,scale; uint16_t reserved; uint8_t valid[TILES]; uint8_t data[]; } shadow;
_Static_assert(sizeof(shadow)==HEADER,"Cache layout");
typedef struct {uint8_t left,top,right,bottom;} rect;
static unsigned stride(unsigned bits){return bits==4?64:24;}
static unsigned bytes(unsigned bits){return HEADER+TILES*stride(bits);}
static unsigned width(unsigned scale){return scale==5?356:scale>=2&&scale<=4?scale*80:160;}
static unsigned height(unsigned scale){return scale==5?320:scale>=2&&scale<=4?scale*72:144;}

void *video_shadow_alloc(size_t requested) {
 if(requested!=46080)return original_malloc(requested);
 shadow *s=original_malloc(bytes(4));unsigned bits=4;
 if(!s){s=original_malloc(bytes(2));bits=2;}
 if(s) {
  s->bits=bits;s->scale=0;s->reserved=0;
  for(unsigned i=0;i<TILES;i++)s->valid[i]=0;
 }
 return s; /* NULL retains the original full-frame fallback. */
}
static void encode(shadow *s,unsigned tile,const uint16_t *p) {
 unsigned bits=s->bits,limit=1u<<bits,used=0;
 uint16_t *palette=(uint16_t *)(s->data+tile*stride(bits));
 uint8_t *packed=(uint8_t *)(palette+limit);
 s->valid[tile]=0;
 unsigned x0=(tile%COLS)*8,y0=(tile/COLS)*8;
 for(unsigned y=0,k=0;y<8;y++)for(unsigned x=0;x<8;x++,k++) {
  uint16_t color=p[(y0+y)*160+x0+x];unsigned i=0;
  while(i<used && palette[i]!=color)i++;
  if(i==used){if(used==limit)return;palette[used++]=color;}
  unsigned shift=(k*bits)&7,index=k*bits/8;
  if(!shift)packed[index]=0;
  packed[index]|=(uint8_t)(i<<shift);
 }
 s->valid[tile]=1;
}
/* Replaces ONLY the worker's post-full-frame memcpy(previous, p, 46080).
 * Original stop still frees this ordinary malloc pointer, including pause. */
void *video_shadow_seed(void *dest,const uint16_t *p,size_t n) {
 (void)n;shadow *s=dest;
 s->scale=*(volatile uint8_t *)0x2001e260;
 for(unsigned tile=0;tile<TILES;tile++)encode(s,tile,p);
 return dest;
}
static rect changed_tile(const uint16_t *p,shadow *s,unsigned tile) {
 unsigned x0=tile%COLS*8,y0=tile/COLS*8;
 if(!s->valid[tile])return (rect){x0,y0,x0+8,y0+8};
 unsigned bits=s->bits,limit=1u<<bits;
 const uint16_t *palette=(const uint16_t *)(s->data+tile*stride(bits));
 const uint8_t *packed=(const uint8_t *)(palette+limit);
 rect r={0,0,0,0};
 for(unsigned y=0,k=0;y<8;y++)for(unsigned x=0;x<8;x++,k++) {
  unsigned i=(packed[k*bits/8]>>((k*bits)&7))&(limit-1);
  if(p[(y0+y)*160+x0+x]==palette[i])continue;
  unsigned xx=x0+x,yy=y0+y;
  if(!r.right)r=(rect){xx,yy,xx+1,yy+1};
  else {if(xx<r.left)r.left=xx;if(xx+1>r.right)r.right=xx+1;r.bottom=yy+1;}
 }
 return r;
}
static unsigned send(const uint16_t *p,unsigned scale,rect r) {
 unsigned w=width(scale),h=height(scale);
 unsigned l=(r.left*w+159)/160,rr=(r.right*w+159)/160;
 unsigned t=(r.top*h+143)/144,b=(r.bottom*h+143)/144;
 video_fast_region(p,scale,l,t,rr,b);return (rr-l)*(b-t);
}
unsigned video_shadow_changed(const uint16_t *p,void *cache,unsigned scale) {
 shadow *s=cache;
 if(!s || s->scale!=scale) {
  original_full(p,scale);
  if(s){for(unsigned tile=0;tile<TILES;tile++)encode(s,tile,p);s->scale=scale;}
  return width(scale)*height(scale);
 }
 /* Same tight bounds and neighbour/vertical-span merging policy as the old
  * dirty renderer, but compare against exact compressed colours. */
 rect active[COLS],next[COLS];unsigned active_count=0,sent=0;bool selected=false;
 for(unsigned band=0;band<ROWS;band++) {
  unsigned count=0;
  for(unsigned col=0;col<COLS;col++) {
   unsigned tile=band*COLS+col;rect r=changed_tile(p,s,tile);
   if(!r.right)continue;
   encode(s,tile,p);
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
int video_shadow_perf(const char *fmt,const char *scale,unsigned emu,unsigned lcd,unsigned cpu,unsigned video) {
 int r=previous_perf(fmt,scale,emu,lcd,cpu,video);
 /* Runs on core 0, the owner of allocation/free; core 1 never changes bits. */
 const shadow *s=*(shadow *volatile *)0x2001db4c;
 original_printf("VSHADOW bits=%u bytes=%u save_ram=%u heap_end=%08x\n",
  s?s->bits:0,s?bytes(s->bits):0,*(volatile unsigned *)0x2001dcb0,
  *(volatile unsigned *)0x2001d738);
 return r;
}
