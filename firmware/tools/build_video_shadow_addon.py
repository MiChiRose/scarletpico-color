#!/usr/bin/env python3
"""Exact VIDEO16 + lossless compact dirty-frame cache. Same full-height pixels."""
from pathlib import Path
import hashlib,json,os,struct,subprocess
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build-video-shadow-addon'
SOURCE=ROOT/'releases/scarletpico-v2_2_2-video16-TEST.uf2'
EXPECTED='5137a17385011e5997287db167d46d5a82c1ca36e705bad970f265b07eb7e81a'
RELEASE=ROOT/'releases/scarletpico-v2_2_2-video16-SHADOW-TEST.uf2'
ARM=Path(os.environ.get('ARM_GCC_BIN','/tmp/arm-gnu/bin'))
def run(args):return subprocess.check_output([str(x) for x in args],text=True)
def main():
 OUT.mkdir(exist_ok=True);raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 old=bytearray()
 for i in range(0,len(raw),512):
  b=raw[i:i+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30;old.extend(b[32:288])
 assert len(old)==0x35a00
 link=OUT/'shadow.ld'
 link.write_text('''MEMORY {
 FLASH (rx) : ORIGIN = 0x10035a00, LENGTH = 0x49600
 RAM (rw) : ORIGIN = 0x2001f960, LENGTH = 0x104
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
original_malloc = 0x1000b8cd;
original_full = 0x1000157d;
original_select_bus = 0x10000c0d;
video_fast_region = 0x100353a5;
previous_perf = 0x100358b1;
original_printf = 0x1000d545;
__aeabi_uidiv = 0x1000aab1;
__aeabi_uidivmod = 0x1000aab1;
memcpy = 0x1000b955;
ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0,"No permanent RAM additions")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings boundary")
''')
 obj=OUT/'shadow.o';elf=OUT/'shadow.elf'
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-O3','-std=c11',
  '-ffreestanding','-fno-builtin','-fno-jump-tables','-fdata-sections','-ffunction-sections',
  '-fstack-usage','-Wall','-Wextra','-Werror','-c',ROOT/'video-fast-addon/video_shadow.c','-o',obj])
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
  *['-Wl,--undefined='+n for n in ['video_shadow_alloc','video_shadow_seed','video_shadow_changed','video_shadow_perf']],
  '-Wl,-Map='+str(OUT/'shadow.map'),'-T',link,obj,'-o',elf])
 run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'shadow.bin'])
 (OUT/'shadow.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
 sym={p[2]:int(p[0],16) for line in run([ARM/'arm-none-eabi-nm','-n',elf]).splitlines() if len(p:=line.split())==3}
 code=(OUT/'shadow.bin').read_bytes();data=old+code;changes=[]
 def change(at,expected,new,reason):
  p=at-0x10000000;assert len(new)==len(expected) and old[p:p+len(expected)]==expected,hex(at)
  data[p:p+len(new)]=new;changes.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),purpose=reason))
 for at,target,name in [(0x10008b24,0x1000b8cc,'video_shadow_alloc'),
   (0x100089a2,0x1000b954,'video_shadow_seed'),
   (0x1003588e,0x1000160c,'video_shadow_changed'),
   (0x10008374,0x100358b0,'video_shadow_perf')]:
  change(at,bl(at,target),bl(at,sym[name]),name)
 change(0x100223a0,struct.pack('<I',0x10035977),struct.pack('<I',0x10000000+len(data)),'Image end metadata')
 allowed=set()
 for c in changes:
  p=int(c['address'],16)-0x10000000;allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
 assert {i for i,(a,b) in enumerate(zip(old,data)) if a!=b}<=allowed
 for a,b in [(0x23f8,0x7164),(0x2e800,0x35300),(0x353a4,0x35828)]:
  assert old[a:b]==data[a:b],'Core/APU/UI/features/DMA transport changed'
 data.extend(bytes(-len(data)%256));(OUT/'patched.bin').write_bytes(data)
 uf2=bytearray();count=len(data)//256
 for i in range(count):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 RELEASE.write_bytes(uf2)
 report=dict(version='2.2.2-video16-shadow-test',source_sha256=EXPECTED,
  output_sha256=hashlib.sha256(uf2).hexdigest(),appended_code=len(code),added_static_ram=0,
  old_optional_heap_bytes=46080,new_optional_heap_bytes=[23404,9004],changes=changes,
  full_height_356x320=True,lossless_colours=True,core_audio_ui_clocks_unchanged=True,
  physical_fps_not_yet_measured=True)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(run([ARM/'arm-none-eabi-size',elf]));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
