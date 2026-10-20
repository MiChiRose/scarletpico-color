#!/usr/bin/env python3
"""Exact v2.2.2 + isolated pipelined 16-bit display experiment. No flashing."""
from pathlib import Path
import hashlib,json,os,struct,subprocess
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build-video-fast-addon'
SOURCE=ROOT/'releases/scarletpico-features-v2_2_2-experimental.uf2'
EXPECTED='886c59515a443abc64c0f12adc12579eca37eaf41c0a029ddcfd8ad4c563a657'
RELEASE=ROOT/'releases/scarletpico-v2_2_2-video16-TEST.uf2'
ARM=Path(os.environ.get('ARM_GCC_BIN','/tmp/arm-gnu/bin'))
def run(args):return subprocess.check_output([str(x) for x in args],text=True)
def main():
 OUT.mkdir(exist_ok=True);raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 old=bytearray()
 for i in range(0,len(raw),512):
  b=raw[i:i+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30;old.extend(b[32:288])
 assert len(old)==0x35300
 link=OUT/'video.ld'
 link.write_text('''MEMORY {
 FLASH (rx) : ORIGIN = 0x10035300, LENGTH = 0x49c00
 RAM (rw) : ORIGIN = 0x2001f928, LENGTH = 0x13c
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : { *(.bss*) *(COMMON) . = ALIGN(8); __video_bss_end = .; } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
dma_claim_unused_channel = 0x1001b389;
original_region = 0x100004a9;
original_window = 0x1000039d;
original_full = 0x1000157d;
original_changed = 0x1000160d;
original_printf = 0x1000d545;
time_us_64 = 0x10009e3d;
clock_get_hz = 0x1000a08d;
__aeabi_uidiv = 0x1000aab1;
memcpy = 0x1000b955;
ASSERT(SIZEOF(.data)==0,"No initialized data")
ASSERT(__video_bss_end<=0x2001fa64,"RAM budget")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings boundary")
''')
 obj=OUT/'video.o';elf=OUT/'video.elf'
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-O3','-std=c11',
  '-ffreestanding','-fno-builtin','-fno-jump-tables','-fdata-sections','-ffunction-sections',
  '-fstack-usage','-Wall','-Wextra','-Werror','-c',ROOT/'video-fast-addon/video_fast.c','-o',obj])
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
  *['-Wl,--undefined='+n for n in ['video_fast_region','video_fast_full','video_fast_changed','video_fast_perf']],
  '-Wl,-Map='+str(OUT/'video.map'),'-T',link,obj,'-o',elf])
 run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'video.bin'])
 (OUT/'video.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
 sym={p[2]:int(p[0],16) for line in run([ARM/'arm-none-eabi-nm','-n',elf]).splitlines() if len(p:=line.split())==3}
 code=(OUT/'video.bin').read_bytes();data=old+code;changes=[]
 def change(at,expected,new,reason):
  p=at-0x10000000;assert len(new)==len(expected) and old[p:p+len(expected)]==expected,hex(at)
  data[p:p+len(new)]=new;changes.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),purpose=reason))
 sites=[at for at in range(0x10000318,0x10002018,2) if old[at-0x10000000:at-0x10000000+4]==bl(at,0x100004a8)]
 assert sites==[0x100015d6,0x1000187c,0x10001914,0x10001a42,0x10001b16,0x10001b86,0x10001f12]
 for at in sites:change(at,bl(at,0x100004a8),bl(at,sym['video_fast_region']),'Pipelined 16-bit region transport')
 for at,target,name in [(0x1000898e,0x1000157c,'video_fast_full'),(0x10008946,0x1000160c,'video_fast_changed'),(0x10008374,0x1000d544,'video_fast_perf')]:
  change(at,bl(at,target),bl(at,sym[name]),name)
 for at in [0x10000270,0x1000d124]:
  change(at,struct.pack('<I',0x2001f928),struct.pack('<I',sym['__video_bss_end']),'Reserve video state outside heap')
 change(0x100223a0,struct.pack('<I',0x10035298),struct.pack('<I',0x10000000+len(data)),'Image end metadata')
 allowed=set()
 for c in changes:
  p=int(c['address'],16)-0x10000000;allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
 assert {i for i,(a,b) in enumerate(zip(old,data)) if a!=b}<=allowed
 for a,b in [(0x23f8,0x7164),(0x2e800,len(old))]:assert old[a:b]==data[a:b],'Core/APU/UI/features changed'
 data.extend(bytes(-len(data)%256));(OUT/'patched.bin').write_bytes(data)
 uf2=bytearray();count=len(data)//256
 for i in range(count):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 RELEASE.write_bytes(uf2)
 report=dict(version='2.2.2-video16-test',source_sha256=EXPECTED,output_sha256=hashlib.sha256(uf2).hexdigest(),
  appended_code=len(code),added_static_ram=sym['__video_bss_end']-0x2001f928,changes=changes,
  core_audio_ui_features_byte_identical=True,clocks_unchanged=True,display_pixel_bytes_unchanged=True,
  physical_fps_not_yet_measured=True)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(run([ARM/'arm-none-eabi-size',elf]));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
