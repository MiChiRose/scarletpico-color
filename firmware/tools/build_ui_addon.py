#!/usr/bin/env python3
"""Append a launcher-only extension to the exact, user-tested audio50 UF2.
No core rebuild. Every changed input byte is listed in the output manifest.
"""
from pathlib import Path
import hashlib
import json
import re
import shlex
import struct
import subprocess
from uf2_audio_patch import bl

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-ui-addon'
ARM=Path('/tmp/arm-gnu/bin')
SOURCE=ROOT/'releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-audio50.uf2'
EXPECTED='692a06aeea11e97b0b03f29418703e024ac91deaeb26f0e9a2eebc05e8e07907'
RELEASE=ROOT/'releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1.uf2'
def run(args):
 p=subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.stderr:
  (OUT/'toolchain.log').open('a').write(p.stderr)
 if p.returncode:
  print(p.stderr);raise SystemExit('Command failed: '+str(args[0]))
 return p.stdout
def read():
 raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 chunks=[]
 for i in range(0,len(raw),512):
  b=raw[i:i+512];h=struct.unpack_from('<8I',b)
  assert h==(0xa324655,0x9e5d5157,0x2000,0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30
  chunks.append(b[32:288])
 data=b''.join(chunks);assert len(data)==0x2ff00
 return data
def build():
 OUT.mkdir(exist_ok=True)
 old=read();(OUT/'baseline.bin').write_bytes(old)
 commands=run(['/opt/homebrew/bin/ninja','-C',ROOT/'build','-t','commands'])
 tokens=shlex.split(next(c for c in commands.splitlines() if '/src/emulator.c' in c and ' -c ' in c))
 includes=[]
 for i,t in enumerate(tokens):
  if t.startswith(('-I','-D')): includes.append(t)
  if t=='-isystem': includes += [t,tokens[i+1]]
 flags=['-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11','-fshort-enums',
        '-ffreestanding','-fno-builtin','-fno-jump-tables','-ffunction-sections','-fdata-sections',
        '-fstack-usage','-Wall','-Wextra','-Werror',
        '-I'+str(ROOT/'vendor/pico-sdk/src/rp2_common/hardware_pwm/include')]
 objects=[]
 for name in ['ui.c','ui_hw.c','bridges.S']:
  obj=OUT/(name.split('.')[0]+'.o')
  run([ARM/'arm-none-eabi-gcc',*includes,*flags,'-c',ROOT/'ui-addon'/name,'-o',obj]);objects.append(obj)
 exports=['ui_boot_bridge','ui_input_bridge','ui_volume_bridge','ui_menu_full','ui_menu_update',
          'ui_legacy_clear','ui_legacy_text','ui_prepare_rom','ui_rom_read','ui_rom_erase','ui_scan_games']
 elf=OUT/'ui.elf'
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib',
      '-Wl,--gc-sections',*['-Wl,--undefined='+s for s in exports],
      '-Wl,-Map='+str(OUT/'ui.map'),'-T',ROOT/'ui-addon/ui.ld',
      '-T',ROOT/'ui-addon/base-symbols.ld',*objects,'-o',elf])
 run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'ui.bin'])
 (OUT/'ui.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
 sym={}
 for line in run([ARM/'arm-none-eabi-nm','-n',elf]).splitlines():
  p=line.split()
  if len(p)==3:sym[p[2]]=int(p[0],16)
 code=(OUT/'ui.bin').read_bytes();data=bytearray(old+code);changes=[]
 assert len(data)<0x7f000
 def change(at,expected,new,purpose):
  pos=at-0x10000000
  assert old[pos:pos+len(expected)]==expected,f'Hook mismatch {at:#x}'
  assert len(expected)==len(new)
  data[pos:pos+len(new)]=new
  changes.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),purpose=purpose))
 def call(at,target,name):change(at,bl(at,target),bl(at,sym[name]),name)
 call(0x10007890,0x10000c70,'ui_boot_bridge')
 change(0x10007b24,bytes.fromhex('02242c42'),bl(0x10007b24,sym['ui_input_bridge']),'Menu-only input filter; preserves original B-test flags')
 for at in [0x10007a34,0x10007c56,0x10007c9e]:
  call(at,0x1002dd00,'ui_menu_full')
 call(0x10007b50,0x1002df50,'ui_menu_update')
 change(0x1002ec88,bytes.fromhex('32230400'),bl(0x1002ec88,sym['ui_volume_bridge']),'Replace only fixed 50% PCM gain load with validated setting; mixer/APU unchanged')
 # Redirect system-message drawing calls ONLY in launcher/save prompts.
 for at in range(0x100076e8,0x100083ac,2):
  for target,name in [(0x10001324,'ui_legacy_clear'),(0x10001500,'ui_legacy_text'),(0x10008494,'ui_prepare_rom'),(0x10008424,'ui_scan_games')]:
   if old[at-0x10000000:at-0x10000000+4]==bl(at,target):call(at,target,name)
 call(0x1000853e,0x10014f34,'ui_rom_read')
 call(0x100085fe,0x10014f34,'ui_rom_read')
 call(0x10008586,0x10020410,'ui_rom_erase')
 end=sym['__ui_bss_end'];assert end<=0x2001fa64 and end%8==0
 for at in [0x10000270,0x1000d124]:
  change(at,struct.pack('<I',0x2001f3f8),struct.pack('<I',end),'Reserve/initialize UI BSS without touching existing audio state')
 change(0x100223a0,struct.pack('<I',0x1002fe17),struct.pack('<I',0x10000000+len(data)),'Complete firmware length')
 allowed=set()
 for c in changes:
  start=int(c['address'],16)-0x10000000
  allowed.update(range(start,start+len(bytes.fromhex(c['before']))))
 changed={i for i,(a,b) in enumerate(zip(old,data)) if a!=b};assert changed<=allowed
 # Primary invariants: exact emulator, game scaling/video, original APU,
 # IRQ/DMA/I2S, CPU and both SPI frequency literals, ROM/save layout.
 for a,b in [(0x2518,0x7164),(0x318,0x2018),(0x88b0,0x8d10),(0x2e800,0x2ec88),(0x2ec8c,0x2fe17)]:
  assert data[a:b]==old[a:b],f'Core changed: {a:#x}..{b:#x}'
 clocks=[0x718,0x80c,0xa50,0xc08,0xc58,0x1080,0x13dc,0x14fc,0x1608,0x1be4,0x1ff0,
         0x7e6c,0x822c,0x8398,0x8da4,0x8414,0x848c,0x86b0,0x87ac,0x88ac,0x2cee8]
 for at in clocks+[0x7e92,0x7f5a,0x8168,0x82cc]:assert data[at:at+4]==old[at:at+4]
 data.extend(bytes(-len(data)%256));total=len(data)//256;uf2=bytearray()
 for i in range(total):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,total,0xe48bff56)+data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 RELEASE.write_bytes(uf2);(OUT/'patched.bin').write_bytes(data)
 report=dict(source_sha256=EXPECTED,output_sha256=hashlib.sha256(uf2).hexdigest(),
             modified_original_bytes=len(changed),ui_ram_bytes=end-0x2001f3f8,ui_flash_bytes=len(code),
             settings_sector='0x7f000..0x7ffff',rom_cache='0x80000',
             core_byte_identical=True,clocks_byte_identical=True,changes=changes)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(run([ARM/'arm-none-eabi-size',elf]));print(RELEASE);print(json.dumps({k:v for k,v in report.items() if k!='changes'},indent=2))
if __name__=='__main__':build()
