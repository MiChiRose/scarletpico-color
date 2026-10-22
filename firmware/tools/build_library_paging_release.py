"""Extend ONLY the SHA-pinned, working 2.2.7 launcher. Never flash hardware."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'releases/2026-10-20-rp2040-ui-polish/ScarletPico-v2_2_7-RP2040-UI-POLISH.uf2'
EXPECTED='2be5dd4d37001167a77501174ce02ba3d59a21e555b4ff6b87a2620b8c6f34c0'
BUILD=ROOT/'build-library-paging-addon'
OUT=ROOT/'releases/2026-10-22-rp2040-library-paging'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--arm-bin',type=Path,required=True);args=p.parse_args()
 BUILD.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
 def run(command):
  r=subprocess.run([str(c) for c in command],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stdout+r.stderr)
  return r.stdout
 assert sha(SOURCE)==EXPECTED
 raw=SOURCE.read_bytes();old=bytearray()
 for off in range(0,len(raw),512):
  b=raw[off:off+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+off//2,256,off//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30;old+=b[32:288]
 assert len(old)==0x39500
 flags=['-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11','-fshort-enums','-ffreestanding','-fno-builtin',
        '-fno-jump-tables','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror',
        '-I'+str(ROOT/'include'),'-I'+str(ROOT/'vendor/pico-fatfs-sd/lib/fatfs/source'),
        '-I'+str(ROOT/'vendor/pico-fatfs-sd/src/include')]
 objects=[]
 for source,extra in [(ROOT/'library-paging-addon/library.c',[]),
                      (ROOT/'ui-polish-addon/ui.c',['-DSCARLET_LIBRARY_PAGING','-DSCARLET_UI_VERSION="2.2.8"'])]:
  obj=BUILD/(source.stem+'.o');objects.append(obj)
  run([args.arm_bin/'arm-none-eabi-gcc',*flags,*extra,'-c',source,'-o',obj])
 exports=['paged_scan_games','paged_menu_input','paged_repeat_bridge','polished_header','polished_invalidate','polished_menu_draw']
 elf=BUILD/'library.elf'
 run([args.arm_bin/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
      *['-Wl,--undefined='+s for s in exports],'-Wl,-Map='+str(BUILD/'library.map'),
      '-T',ROOT/'library-paging-addon/library.ld',*objects,'-o',elf])
 run([args.arm_bin/'arm-none-eabi-objcopy','-O','binary',elf,BUILD/'library.bin'])
 (BUILD/'library.dis').write_text(run([args.arm_bin/'arm-none-eabi-objdump','-d',elf]))
 symbols={c[2]:int(c[0],16) for line in run([args.arm_bin/'arm-none-eabi-nm','-n',elf]).splitlines() if len(c:=line.split())==3}
 addition=(BUILD/'library.bin').read_bytes();data=old+addition;changes=[]
 def change(address,before,after,purpose):
  pos=address-0x10000000
  assert len(before)==len(after) and old[pos:pos+len(before)]==before,(hex(address),purpose)
  data[pos:pos+len(after)]=after
  changes.append(dict(address=hex(address),before=before.hex(),after=after.hex(),purpose=purpose))
 for at,name,previous in [(0x10030814,'polished_header',0x10038a75),
                          (0x100308cc,'polished_invalidate',0x10038b19),
                          (0x10030b20,'polished_menu_draw',0x10038b3d)]:
  change(at,bytes.fromhex('004b1847')+struct.pack('<I',previous),
         bytes.fromhex('004b1847')+struct.pack('<I',symbols[name]|1),name)
 change(0x10031428,bytes.fromhex('f8b506000f001400'),
        bytes.fromhex('10b5')+bl(0x1003142a,symbols['paged_scan_games'])+bytes.fromhex('10bd'),
        'Bounded globally sorted catalogue; preserve all four scanner arguments')
 change(0x100314be,bl(0x100314be,0x100386c4),bl(0x100314be,symbols['paged_menu_input']),
        'Consume window-boundary key before old navigation')
 change(0x10007bd0,bytes.fromhex('02243d40'),bl(0x10007bd0,symbols['paged_repeat_bridge']),
        'Route held-key repeats through the same boundary handler')
 for at in (0x10000270,0x1000d124):
  change(at,struct.pack('<I',0x2001f9d0),struct.pack('<I',symbols['__library_bss_end']),'Reserve and zero paging/UI state')
 change(0x100223a0,struct.pack('<I',0x1003947c),struct.pack('<I',0x10000000+len(data)),'Image end metadata')
 assert old.count(b'v2.2.7')==1
 version_offset=old.index(b'v2.2.7')
 change(0x10000000+version_offset,b'v2.2.7',b'v2.2.8','About version')
 allowed=set()
 for c in changes:
  pos=int(c['address'],16)-0x10000000;allowed.update(range(pos,pos+len(bytes.fromhex(c['before']))))
 differences={i for i,(a,b) in enumerate(zip(old,data)) if a!=b};assert differences<=allowed
 protected=[(0x318,0x2018),(0x23f8,0x7164),(0x78c0,0x83ac),(0x8470,0x8d10),
            (0x2e800,0x2fe17),(0x32500,0x38400),(0x38400,0x38900)]
 # Exempt just the checked About literal and the exact held-key hook. All
 # neighbouring instructions/data, including loaders and hardware, are pinned.
 exemptions=set(range(version_offset,version_offset+6))|set(range(0x7bd0,0x7bd4))
 for a,b in protected:
  assert all(data[i]==old[i] for i in range(a,b) if i not in exemptions),('Protected hardware/core/loader block changed',hex(a))
 data.extend(bytes(-len(data)%256));(BUILD/'patched.bin').write_bytes(data)
 output=bytearray();count=len(data)//256
 for i in range(count):
  output+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  output+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 target=OUT/'ScarletPico-v2_2_8-RP2040-LIBRARY-PAGING.uf2';target.write_bytes(output)
 audit=dict(version='2.2.8-library-paging',source_sha256=EXPECTED,uf2_sha256=sha(target),
   image_sha256=sha(BUILD/'patched.bin'),elf_sha256=sha(elf),rollback_path=str(SOURCE.relative_to(ROOT)),
   automatically_flashed=False,hardware_tested=False,window_entries=28,original_array_entries=32,
   catalogue_count_bits=32,new_catalogue_heap_allocations=0,
   added_static_ram=symbols['__library_bss_end']-0x2001f9d0,
   appended_code_bytes=len(addition),changes=changes,protected_byte_ranges=protected,
   protected_range_exemptions=[dict(offset=version_offset,length=6,purpose='About version literal only'),
     dict(offset=0x7bd0,length=4,purpose='Held-key input hook only')],
   compiler=run([args.arm_bin/'arm-none-eabi-gcc','--version']).splitlines()[0],
   source_files={str(f.relative_to(ROOT)):sha(f) for f in [ROOT/'library-paging-addon/library.c',
     ROOT/'library-paging-addon/library.ld',ROOT/'ui-polish-addon/ui.c',Path(__file__),
     ROOT/'tests/test_library_paging_arm.py',ROOT/'include/game_library.h',ROOT/'ui-addon/ui.h',
     ROOT/'vendor/pico-fatfs-sd/lib/fatfs/source/ff.h',ROOT/'vendor/pico-fatfs-sd/src/include/ffconf.h']})
 (OUT/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 print(json.dumps({k:v for k,v in audit.items() if k not in ('changes','source_files')},indent=2));print(target)
if __name__=='__main__':main()
