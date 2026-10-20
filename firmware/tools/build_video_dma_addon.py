#!/usr/bin/env python3
"""SHA-pinned, separate DMA experiment. No core rebuild or device flashing."""
from pathlib import Path
import hashlib,json,os,struct,subprocess
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-video-dma-addon'
SOURCE=ROOT/'releases/scarletpico-features-v2_2_1-experimental.uf2'
EXPECTED='b359348d8b119e2b17a61edb7ef53ed0017785b0b365aa54b7cead081962b0b4'
RELEASE=ROOT/'releases/scarletpico-v2_2_1-video-dma-TEST.uf2'
ARM=Path(os.environ.get('ARM_GCC_BIN','/tmp/arm-gnu/bin'))
def run(args):return subprocess.check_output([str(x) for x in args],text=True)
def main():
 OUT.mkdir(exist_ok=True)
 raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 old=bytearray()
 for i in range(0,len(raw),512):
  b=raw[i:i+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30
  old.extend(b[32:288])
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
original_spi_write_blocking = 0x200016a1;
ASSERT(SIZEOF(.data)==0,"No initialized data")
ASSERT(__video_bss_end<=0x2001fa64,"RAM budget")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings boundary")
''')
 obj=OUT/'video.o';elf=OUT/'video.elf'
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11',
      '-ffreestanding','-fno-builtin','-fdata-sections','-ffunction-sections',
      '-fstack-usage','-Wall','-Wextra','-Werror','-c',ROOT/'video-dma-addon/video_dma.c','-o',obj])
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib',
      '-Wl,--gc-sections','-Wl,--undefined=video_dma_write','-Wl,-Map='+str(OUT/'video.map'),
      '-T',link,obj,'-o',elf])
 run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'video.bin'])
 (OUT/'video.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
 sym={p[2]:int(p[0],16) for line in run([ARM/'arm-none-eabi-nm','-n',elf]).splitlines() if len(p:=line.split())==3}
 code=(OUT/'video.bin').read_bytes();data=old+code;changes=[]
 def change(at,expected,new,reason):
  p=at-0x10000000
  assert len(new)==len(expected) and old[p:p+len(expected)]==expected,hex(at)
  data[p:p+len(new)]=new
  changes.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),purpose=reason))
 for at in [0x100005aa,0x100005ee]:
  change(at,bl(at,0x100203b0),bl(at,sym['video_dma_write']),'Only scaled game-row SPI transfer')
 for at in [0x10000270,0x1000d124]:
  change(at,struct.pack('<I',0x2001f928),struct.pack('<I',sym['__video_bss_end']),'Reserve channel state outside heap')
 change(0x100223a0,struct.pack('<I',0x10035298),struct.pack('<I',0x10000000+len(data)),'Image end metadata')
 allowed=set()
 for c in changes:
  p=int(c['address'],16)-0x10000000;allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
 assert {i for i,(a,b) in enumerate(zip(old,data)) if a!=b}<=allowed
 for a,b in [(0x23f8,0x7164),(0x7834,0x88b0),(0x88b0,0x8d10),(0x2e800,len(old))]:
  assert old[a:b]==data[a:b],f'Core/main/worker/audio/UI/features changed at {a:x}'
 data.extend(bytes(-len(data)%256));(OUT/'patched.bin').write_bytes(data)
 uf2=bytearray();count=len(data)//256
 for i in range(count):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 RELEASE.write_bytes(uf2)
 report=dict(version='2.2.1-video-dma-test',source_sha256=EXPECTED,
  output_sha256=hashlib.sha256(uf2).hexdigest(),appended_code=len(code),
  added_static_ram=sym['__video_bss_end']-0x2001f928,changes=changes,
  core_main_worker_audio_ui_features_byte_identical=True,clocks_unchanged=True,
  lcd_format_resolution_unchanged=True,physical_fps_not_yet_measured=True)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(run([ARM/'arm-none-eabi-size',elf]));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
