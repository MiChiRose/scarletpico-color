"""Append GP29 battery to the exact user-working 2.2.2. Never flash a device."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,zipfile
from uf2_audio_patch import bl

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'releases/2026-10-07-rp2040-native-menu/01-ScarletPico-v2_2_2-RP2040-ROLLBACK.uf2'
EXPECTED='98b80f2827d626e697b83034d426b77e5fe028e1792f30edaec50a80ab963089'
BUILD=ROOT/'build-battery-legacy-addon'
OUT=ROOT/'releases/2026-10-20-rp2040-legacy222-battery'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):
 p=subprocess.run([str(a) for a in args],text=True,capture_output=True)
 if p.stderr:
  with (BUILD/'toolchain.log').open('a') as log:log.write(p.stderr)
  lines=[s for s in p.stderr.splitlines() if 'Forcing branch to absolute symbol' not in s]
  if lines:print('\n'.join(lines))
 if p.returncode:raise RuntimeError('Toolchain failed; see '+str(BUILD/'toolchain.log'))
 return p.stdout
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--arm-bin',type=Path,required=True);a=p.parse_args()
 BUILD.mkdir(exist_ok=True);raw=SOURCE.read_bytes();assert sha(SOURCE)==EXPECTED
 old=bytearray()
 for off in range(0,len(raw),512):
  block=raw[off:off+512]
  assert struct.unpack_from('<8I',block)==(0xa324655,0x9e5d5157,0x2000,0x10000000+off//2,256,off//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',block,508)[0]==0xab16f30;old+=block[32:288]
 assert len(old)==0x38400
 flags=['-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11','-ffreestanding','-fno-builtin',
        '-fno-jump-tables','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror']
 objects=[]
 for src in [ROOT/'battery-legacy-addon/battery.c',ROOT/'imported/scarletpico-rp2040-source/battery_model.c']:
  obj=BUILD/(src.stem+'.o');run([a.arm_bin/'arm-none-eabi-gcc',*flags,'-c',src,'-o',obj]);objects.append(obj)
 elf=BUILD/'battery.elf'
 exports=['legacy_battery_header','legacy_battery_menu_input','legacy_battery_frame','legacy_battery_hud']
 run([a.arm_bin/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
      *['-Wl,--undefined='+n for n in exports],'-Wl,-Map='+str(BUILD/'battery.map'),
      '-T',ROOT/'battery-legacy-addon/battery.ld',*objects,'-o',elf])
 run([a.arm_bin/'arm-none-eabi-objcopy','-O','binary',elf,BUILD/'battery.bin'])
 (BUILD/'battery.dis').write_text(run([a.arm_bin/'arm-none-eabi-objdump','-d',elf]))
 s={v[2]:int(v[0],16) for line in run([a.arm_bin/'arm-none-eabi-nm','-n',elf]).splitlines() if len(v:=line.split())==3}
 addition=(BUILD/'battery.bin').read_bytes();data=old+addition;changes=[]
 def change(at,before,after,purpose):
  pos=at-0x10000000
  assert old[pos:pos+len(before)]==before and len(before)==len(after),(hex(at),purpose)
  data[pos:pos+len(after)]=after
  changes.append(dict(address=hex(at),before=before.hex(),after=after.hex(),purpose=purpose))
 for at,target,name in [(0x10030876,0x10031264,'legacy_battery_header'),
                         (0x100314be,0x100313ec,'legacy_battery_menu_input'),
                         (0x100368d4,0x10036500,'legacy_battery_frame'),
                         (0x10008a30,0x10032f38,'legacy_battery_hud')]:
  change(at,bl(at,target),bl(at,s[name]),name)
 for at in [0x10000270,0x1000d124]:
  change(at,struct.pack('<I',0x2001f998),struct.pack('<I',s['__battery_bss_end']),'Reserve/zero only battery state outside the original heap')
 change(0x100223a0,struct.pack('<I',0x100383a0),struct.pack('<I',0x10000000+len(data)),'Complete image length')
 version=b'v2.2.2';assert old.count(version)==1
 at=0x10000000+old.index(version);change(at,version,b'v2.2.6','About version only')
 allowed=set()
 for c in changes:
  pos=int(c['address'],16)-0x10000000;allowed.update(range(pos,pos+len(bytes.fromhex(c['before']))))
 diff={i for i,(x,y) in enumerate(zip(old,data)) if x!=y};assert diff<=allowed
 # These original LCD transports, init and CPU core ranges must remain exact.
 for lo,hi in [(0x318,0x2018),(0x23f8,0x7164),(0x2e800,0x2fe17)]:assert data[lo:hi]==old[lo:hi]
 data.extend(bytes(-len(data)%256));(BUILD/'patched.bin').write_bytes(data)
 uf2=bytearray();count=len(data)//256
 for i in range(count):
  uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 OUT.mkdir(exist_ok=True)
 release=OUT/'ScarletPico-v2_2_6-RP2040-LEGACY222-GP29.uf2';release.write_bytes(uf2)
 audit=dict(version='2.2.6-legacy222-gp29',source_sha256=EXPECTED,uf2_sha256=sha(release),
            source_path=str(SOURCE.relative_to(ROOT)),hardware_base_confirmed=True,hardware_new_build_tested=False,
            automatically_flashed=False,appended_code_bytes=len(addition),added_static_ram=s['__battery_bss_end']-0x2001f998,
            added_heap_allocations=0,changed_base_bytes=len(diff),changes=changes,
            original_lcd_init_transport_core_audio_clocks_preserved=True,
            original_scaling=[356,320],gpios_added=[29],charger_signals=False,
            menu_indicator=[400,0,80,44],game_indicator=[418,0,62,44],sample_interval_us=1000000,
            elf_sha256=sha(elf),image_sha256=sha(BUILD/'patched.bin'))
 (OUT/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 with zipfile.ZipFile(OUT/'ScarletPico-v2_2_6-legacy-battery-source.zip','w',zipfile.ZIP_DEFLATED) as z:
  files=[ROOT/'battery-legacy-addon/battery.c',ROOT/'battery-legacy-addon/battery.ld',Path(__file__),
         ROOT/'tools/uf2_audio_patch.py',ROOT/'imported/scarletpico-rp2040-source/battery_model.c',
         ROOT/'imported/scarletpico-rp2040-source/battery_model.h',ROOT/'tests/test_legacy_battery_arm.py',SOURCE]
  for f in files:
   if f.exists():z.write(f,'firmware/'+str(f.resolve().relative_to(ROOT)))
  for name in ['README-RU.md','build-audit.json','VALIDATION.md']:
   if (OUT/name).exists():z.write(OUT/name,name)
 print(json.dumps(audit,indent=2));print(release)
if __name__=='__main__':main()
