#!/usr/bin/env python3
"""SHA-pinned PAUSE SETTINGS plus cheaper exact shadow codec. Never flash."""
from pathlib import Path
import hashlib,json,os,struct,subprocess
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build-shadow-fast-addon'
SOURCE=ROOT/'releases/scarletpico-v2_2_2-PAUSE-SETTINGS-TEST.uf2'
EXPECTED='1d1533f76eed256e7b81cc45b78b0afd9852689795fa6f51a58b510a99de2821'
RELEASE=ROOT/'releases/scarletpico-v2_2_2-SHADOW-FAST-TEST.uf2'
ARM=Path(os.environ.get('ARM_GCC_BIN','/tmp/arm-gnu/bin'))
def run(args):
 p=subprocess.run([str(x) for x in args],text=True,capture_output=True)
 if p.stderr:
  with (OUT/'toolchain.log').open('a') as log:log.write(p.stderr)
  lines=[s for s in p.stderr.splitlines() if 'Forcing branch to absolute symbol' not in s]
  if lines:print('\n'.join(lines))
 if p.returncode:raise RuntimeError(str(args))
 return p.stdout
def main():
 OUT.mkdir(exist_ok=True);raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 old=bytearray()
 for i in range(0,len(raw),512):
  b=raw[i:i+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30;old.extend(b[32:288])
 assert len(old)==0x37800
 link=OUT/'shadow-fast.ld'
 link.write_text('''MEMORY {
 FLASH (rx) : ORIGIN = 0x10037800, LENGTH = 0x47800
 RAM (rw) : ORIGIN = 0x2001f998, LENGTH = 0xcc
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
original_full = 0x1000157d;
original_select_bus = 0x10000c0d;
video_fast_region = 0x100353a5;
__aeabi_uidiv = 0x1000aab1;
__aeabi_uidivmod = 0x1000aab1;
ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0,"No new static RAM")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings boundary")
''')
 obj=OUT/'shadow-fast.o';elf=OUT/'shadow-fast.elf'
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-O3','-std=c11',
      '-ffreestanding','-fno-builtin','-fno-jump-tables','-fdata-sections','-ffunction-sections',
      '-fstack-usage','-Wall','-Wextra','-Werror','-c',ROOT/'video-fast-addon/video_shadow_fast.c','-o',obj])
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
      '-Wl,--undefined=video_shadow_fast_seed','-Wl,--undefined=video_shadow_fast_changed',
      '-Wl,-Map='+str(OUT/'shadow-fast.map'),'-T',link,obj,'-o',elf])
 run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'shadow-fast.bin'])
 (OUT/'shadow-fast.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
 s={p[2]:int(p[0],16) for line in run([ARM/'arm-none-eabi-nm','-n',elf]).splitlines() if len(p:=line.split())==3}
 code=(OUT/'shadow-fast.bin').read_bytes();data=old+code;changes=[]
 def change(at,expected,new,purpose):
  pos=at-0x10000000;assert old[pos:pos+len(expected)]==expected and len(new)==len(expected)
  data[pos:pos+len(new)]=new
  changes.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),purpose=purpose))
 for at,target,name in [(0x100089a2,0x10035bdc,'video_shadow_fast_seed'),
                        (0x1003588e,0x10035c08,'video_shadow_fast_changed')]:
  change(at,bl(at,target),bl(at,s[name]),name)
 change(0x100223a0,struct.pack('<I',0x10037734),struct.pack('<I',0x10000000+len(data)),
        'Image end metadata')
 allowed=set()
 for c in changes:
  pos=int(c['address'],16)-0x10000000;allowed.update(range(pos,pos+len(bytes.fromhex(c['before']))))
 assert {i for i,(a,b) in enumerate(zip(old,data)) if a!=b}<=allowed
 for a,b in [(0,0x89a2),(0x89a6,0x223a0),(0x223a4,0x3588e),(0x35892,len(old))]:
  assert old[a:b]==data[a:b],'Protected core/APU/UI/clock/pacing/allocator/DMA bytes'
 data.extend(bytes(-len(data)%256));(OUT/'patched.bin').write_bytes(data)
 uf2=bytearray();count=len(data)//256
 for i in range(count):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 RELEASE.write_bytes(uf2)
 report=dict(version='2.2.2-shadow-fast-test',source_sha256=EXPECTED,
             output_sha256=hashlib.sha256(uf2).hexdigest(),changes=changes,
             appended_code=len(code),added_static_ram=0,added_heap_bytes=0,
             cache_format_and_region_policy_unchanged=True,full_height_356x320=True,
             core_audio_ui_clocks_pacing_dma_unchanged=True,physical_fps_not_yet_measured=True)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(run([ARM/'arm-none-eabi-size',elf]));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
