#include "audio_queue.h"
#include "minigb_apu.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    audio_queue_t q = {0};
    int16_t in[1200];
    uint32_t out[600];
    for (unsigned i=0; i<600; ++i) { in[2*i]=20000; in[2*i+1]=-4000; }
    assert(audio_queue_push(&q,in,600,50)==512);
    assert(audio_queue_push(&q,in,1,50)==0);
    assert(audio_queue_pop(&q,out,512)==512);
    for (unsigned i=0; i<512; ++i) assert(out[i]==0x0fa00fa0u); /* mix, then 50% */
    assert(audio_queue_pop(&q,out,1)==0);
    q.read=q.write=UINT32_MAX-100;
    for (unsigned i=0; i<10000; ++i) {
        unsigned n=i%500+1;
        assert(audio_queue_push(&q,in,n,50)==n);
        assert(audio_queue_pop(&q,out,n)==n);
        assert(q.read==q.write);
    }
    audio_init();
    audio_write(0xff26,0);
    audio_write(0xff30,0xab);
    assert(audio_read(0xff30)==0xab);
    audio_write(0xff12,0xf0);
    assert(audio_read(0xff12)==0);
    audio_write(0xff26,0x80);
    audio_write(0xff24,0x77);
    audio_write(0xff25,0x11);
    audio_write(0xff11,0x80);
    audio_write(0xff12,0xf0);
    audio_write(0xff13,0x80);
    audio_write(0xff14,0x83);
    int16_t pcm[540];
    memset(pcm,0x55,sizeof pcm);
    audio_callback(NULL,(uint8_t *)pcm,267*4);
    assert(pcm[534]==0x5555 && pcm[539]==0x5555);
    unsigned nonzero=0;
    for (unsigned i=0;i<534;++i) nonzero+=pcm[i]!=0;
    assert(nonzero>400);
    audio_write(0xff26,0);
    audio_callback(NULL,(uint8_t *)pcm,268*4);
    for (unsigned i=0;i<536;++i) assert(!pcm[i]);
    uint32_t random=1;
    for (unsigned i=0;i<10000;++i) {
        random=random*1664525u+1013904223u;
        audio_write(0xff10+(random%48),(uint8_t)(random>>24));
        audio_callback(NULL,(uint8_t *)pcm,4*(i%268+1));
        for (unsigned a=0xff10;a<=0xff3f;++a) (void)audio_read(a);
    }
    audio_init();
    uint8_t regs[48];
    for(unsigned i=0;i<48;++i) regs[i]=audio_read(0xff10+i);
    audio_init();
    for(unsigned i=0;i<48;++i) assert(regs[i]==audio_read(0xff10+i));
    puts("PASS: audio queue overflow/wrap, mono 50%, APU bounds/reset/power/tone/random registers");
}
