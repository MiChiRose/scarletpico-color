#!/usr/bin/env python3
"""Reproducible append-only extension of the pinned user-tested Fastload UF2.
No whole-core rebuild. No toolchain lookup through a stale CMake build folder.
ARM_GCC_BIN can override the toolchain directory for another computer.
"""
from pathlib import Path
import hashlib,json,os,re,struct,subprocess
from uf2_audio_patch import bl
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-features-v2_2_2-addon'
ARM=Path(os.environ.get('ARM_GCC_BIN','/tmp/arm-gnu/bin'))
SOURCE=ROOT/'releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1-fastload.uf2'
EXPECTED='57bdbaaa2bedebf3797e103f4fa80e2ff975e481b9504b6bb276bbaa6c6f1964'
RELEASE=ROOT/'releases/scarletpico-features-v2_2_2-experimental.uf2'
def run(args):
 p=subprocess.run([str(x) for x in args],text=True,capture_output=True)
 if p.stderr:
  with (OUT/'toolchain.log').open('a') as f:f.write(p.stderr)
  important=[s for s in p.stderr.splitlines() if 'Forcing branch to absolute symbol' not in s]
  if important:print('\n'.join(important))
 if p.returncode:raise RuntimeError(str(args))
 return p.stdout
def symbols(path):
 result={}
 for line in run([ARM/'arm-none-eabi-nm','-n',path]).splitlines():
  x=line.split()
  if len(x)==3:result[x[2]]=int(x[0],16)
 return result
def main():
 OUT.mkdir(exist_ok=True)
 raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 old=bytearray()
 for i in range(0,len(raw),512):
  b=raw[i:i+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30
  old.extend(b[32:288])
 assert len(old)==0x32600
 # Verify the non-returning error callback by its snprintf + longjmp calls.
 # The adjacent 0x2584 function is cartridge RAM WRITE, never an error exit.
 assert old[0x256c:0x2570]==bl(0x1000256c,0x1000d054)
 assert old[0x2574:0x2578]==bl(0x10002574,0x1001db04)
 (OUT/'baseline.bin').write_bytes(old)
 flags=['-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11','-fshort-enums',
        '-ffreestanding','-fno-builtin','-fno-jump-tables','-ffunction-sections',
        '-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror',
        '-I'+str(ROOT/'ui-addon'),'-I'+str(ROOT/'vendor/pico-fatfs-sd/lib/fatfs/source'),
        '-I'+str(ROOT/'vendor/pico-fatfs-sd/src/include'),'-I'+str(ROOT/'vendor/Peanut-GB-CGB')]
 objects=[]
 for name in ['settings.c','about.c','hud.c','boot.c','rom.c','state.c','pause.c','bridges.S','abi.c']:
  obj=OUT/(Path(name).stem+'.o')
  run([ARM/'arm-none-eabi-gcc',*flags,'-c',ROOT/'features-addon'/name,'-o',obj]);objects.append(obj)
 exports=['features_boot_ui_init','feature_settings','features_game_clock','features_menu_clock',
          'features_prepare','features_load','features_frame','features_stop','features_input_bridge','features_draw_fps']
 elf=OUT/'features.elf'
 run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
      *['-Wl,--undefined='+s for s in exports],'-Wl,-Map='+str(OUT/'features.map'),
      '-T',ROOT/'features-addon/features.ld','-T',ROOT/'features-addon/base-symbols.ld',*objects,'-o',elf])
 run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'features.bin'])
 (OUT/'features.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
 sym=symbols(elf);addition=(OUT/'features.bin').read_bytes();data=old+addition;changes=[]
 def change(at,expected,new,purpose):
  p=at-0x10000000
  assert len(expected)==len(new) and old[p:p+len(expected)]==expected,hex(at)
  data[p:p+len(new)]=new
  changes.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),purpose=purpose))
 def call(at,target,new):change(at,bl(at,target),bl(at,sym[new]),new)
 for at,target,name in [(0x10007f08,0x10032514,'features_prepare'),
                        (0x10007f18,0x10006eac,'features_load'),
                        (0x1000809c,0x1002ee04,'features_frame'),
                        (0x10007f5a,0x1002dc00,'features_game_clock')]:call(at,target,name)
 for at in [0x10007cd0,0x100082ac,0x100082fc]:call(at,0x1002ee74,'features_stop')
 for at in [0x10007e92,0x10008168,0x100082cc]:call(at,0x1002dc00,'features_menu_clock')
 # A single HUD call is redirected; the LCD FPS calculation is untouched.
 call(0x10008a30,0x10001bec,'features_draw_fps')
 for target,name,count in [(0x10030758,'features_boot_ui_init',1),(0x1003102c,'feature_settings',2)]:
  sites=[at for at in range(0x1002ff00,0x1003254c,2) if old[at-0x10000000:at-0x10000000+4]==bl(at,target)]
  assert len(sites)==count,(name,sites)
  for at in sites:call(at,target,name)
 change(0x10008048,bytes.fromhex('1694')+bl(0x1000804a,0x10009e3c),
        bl(0x10008048,sym['features_input_bridge'])+bytes.fromhex('00bf'),'Filtered pause chord + existing clean menu exit')
 change(0x10008490,struct.pack('<I',0x17f000),struct.pack('<I',0x800000),'Scan allows up to 8 MiB, writer limits unchanged')
 end=sym['__features_bss_end']
 for at in [0x10000270,0x1000d124]:
  change(at,struct.pack('<I',0x2001f7e8),struct.pack('<I',end),'Reserve feature state')
 change(0x100223a0,struct.pack('<I',0x1003254c),struct.pack('<I',0x10000000+len(data)),'Firmware end metadata')
 allowed=set()
 for c in changes:
  p=int(c['address'],16)-0x10000000;allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
 changed={i for i,(a,b) in enumerate(zip(old,data)) if a!=b};assert changed<=allowed
 for a,b in [(0x23f8,0x7164),(0x318,0x2018),(0x88b0,0x8a30),(0x8a34,0x8d10),(0x2e800,0x2fe17)]:
  assert data[a:b]==old[a:b],f'Core/render/audio changed at {a:x}'
 data.extend(bytes(-len(data)%256));(OUT/'patched.bin').write_bytes(data)
 uf2=bytearray();count=len(data)//256
 for i in range(count):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 RELEASE.write_bytes(uf2)
 version=re.search(r'#define FEATURES_VERSION "([^"]+)"',(ROOT/'features-addon/features.h').read_text()).group(1)
 report=dict(version=version,source_sha256=EXPECTED,output_sha256=hashlib.sha256(uf2).hexdigest(),
             added_static_ram=end-0x2001f7e8,appended_code=len(addition),
             core_renderer_apu_byte_identical=True,video_worker_only_hud_call_changed=True,
             hud='LCD FPS only; unchanged completed-transfer counter',about_device=True,
             boot='1.8 s capsule descent, 704 ms chime + 16 ms silence, saved volume, Start skips',
             boot_chime='50% duty pulse, 1048.576 then 2080.508 Hz at 84 ms, softened attack/release',
             boot_scratch_reuses_existing_pcm=True,clock_profiles_mhz=[125,170,200],
             default_clock_mhz=200,rom_resident_bytes=0x17f000,rom_max_bytes=0x800000,
             snapshot_slots=5,snapshot_generations_per_slot=2,modified_original_bytes=len(changed),changes=changes)
 RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 print(run([ARM/'arm-none-eabi-size',elf]));print(RELEASE)
 print(json.dumps({k:v for k,v in report.items() if k!='changes'},indent=2))
if __name__=='__main__':main()
