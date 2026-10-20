#include "emulator.h"
#include "minigb_apu.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc,char **argv) {
    assert(argc>=2);
    for(int r=1;r<argc;++r) {
        FILE *f=fopen(argv[r],"rb"); assert(f);
        fseek(f,0,SEEK_END); size_t size=ftell(f); rewind(f);
        uint8_t *rom=malloc(size); assert(rom && fread(rom,1,size,f)==size); fclose(f);
        uint64_t expected_hash=0;
        for(unsigned pass=0;pass<2;++pass) {
            audio_init(); assert(emulator_load(rom,size,NULL));
            uint32_t remainder=0;
            uint64_t samples=0, nonzero=0, hash=0;
            int16_t pcm[536];
            for(unsigned frame=0;frame<3600;++frame) {
                uint8_t keys=0xff;
                if(frame>180 && frame%240<4) keys&=(uint8_t)~BUTTON_START;
                if(frame>600 && frame%120<8) keys&=(uint8_t)~BUTTON_A;
                if(frame>900) keys&=(uint8_t)~(1u<<(4+(frame/60)%4));
                assert(emulator_frame_render(keys,pass==0 || frame%4==0));
                remainder+=16000u*70224u; unsigned n=remainder>>22; remainder&=4194303u;
                assert(n<=268); samples+=n;
                audio_callback(NULL,(uint8_t *)pcm,n*4);
                for(unsigned i=0;i<n*2;++i) { nonzero+=pcm[i]!=0; hash=hash*31+(uint16_t)pcm[i]; }
            }
            assert(samples==((uint64_t)3600*16000*70224>>22));
            assert(nonzero>1000);
            if(!pass) expected_hash=hash; else assert(hash==expected_hash);
            printf("PASS audio %s: pass=%u frames=3600 stereo_samples=%llu nonzero=%llu hash=%llx\n",argv[r],pass,(unsigned long long)samples,(unsigned long long)nonzero,(unsigned long long)hash);
            fflush(stdout);
        }
        free(rom);
    }
}
