"""Append UI polish to hardware-accepted 2.2.6; never access a USB device."""
import argparse,hashlib,json,struct,subprocess,zipfile,shutil
from pathlib import Path
from uf2_audio_patch import bl

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'releases/2026-10-20-rp2040-legacy222-battery/ScarletPico-v2_2_6-RP2040-LEGACY222-GP29.uf2'
EXPECTED='e8c6c99223e571fd450ec213446bff1e702ce57671c3b994cbff59e9cbc92209'
BUILD=ROOT/'build-ui-polish-addon'
OUT=ROOT/'releases/2026-10-20-rp2040-ui-polish'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):
 p=subprocess.run([str(a) for a in args],capture_output=True,text=True)
 if p.stderr:
  with (BUILD/'toolchain.log').open('a') as f:f.write(p.stderr)
  lines=[line for line in p.stderr.splitlines() if 'Forcing branch to absolute symbol' not in line]
  if lines:print('\n'.join(lines))
 if p.returncode:raise RuntimeError('Compiler failed; see '+str(BUILD/'toolchain.log'))
 return p.stdout
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--arm-bin',type=Path,required=True);a=p.parse_args()
 BUILD.mkdir(exist_ok=True);assert sha(SOURCE)==EXPECTED
 raw=SOURCE.read_bytes();old=bytearray()
 for off in range(0,len(raw),512):
  b=raw[off:off+512]
  assert struct.unpack_from('<8I',b)==(0xa324655,0x9e5d5157,0x2000,0x10000000+off//2,256,off//512,len(raw)//512,0xe48bff56)
  assert struct.unpack_from('<I',b,508)[0]==0xab16f30;old+=b[32:288]
 assert len(old)==0x38900
 obj=BUILD/'ui.o';elf=BUILD/'ui.elf'
 flags=['-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11','-ffreestanding','-fno-builtin','-fno-jump-tables',
        '-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror']
 run([a.arm_bin/'arm-none-eabi-gcc',*flags,'-c',ROOT/'ui-polish-addon/ui.c','-o',obj])
 exports=['polished_header','polished_invalidate','polished_menu_draw','polished_boot']
 run([a.arm_bin/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib','-Wl,--gc-sections',
      *['-Wl,--undefined='+s for s in exports],'-Wl,-Map='+str(BUILD/'ui.map'),'-T',ROOT/'ui-polish-addon/ui.ld',obj,'-o',elf])
 run([a.arm_bin/'arm-none-eabi-objcopy','-O','binary',elf,BUILD/'ui.bin'])
 (BUILD/'ui.dis').write_text(run([a.arm_bin/'arm-none-eabi-objdump','-d',elf]))
 symbols={p[2]:int(p[0],16) for line in run([a.arm_bin/'arm-none-eabi-nm','-n',elf]).splitlines() if len(p:=line.split())==3}
 addition=(BUILD/'ui.bin').read_bytes();data=old+addition;changes=[]
 def change(at,before,after,purpose):
  pos=at-0x10000000;assert old[pos:pos+len(before)]==before and len(before)==len(after),(hex(at),purpose)
  data[pos:pos+len(after)]=after
  changes.append(dict(address=hex(at),before=before.hex(),after=after.hex(),purpose=purpose))
 for at,entry,name in [(0x10030814,'7fb50021f022184c','polished_header'),
                        (0x100308cc,'0023034a1370034a','polished_invalidate'),
                        (0x10030b20,'0022f0b5964b95b0','polished_menu_draw')]:
  assert at%4==0
  change(at,bytes.fromhex(entry),bytes.fromhex('004b1847')+struct.pack('<I',symbols[name]|1),name)
 change(0x10031354,bl(0x10031354,0x100332a0),bl(0x10031354,symbols['polished_boot']),'600ms boot entrance, original chime, Start skips')
 for at in [0x10007aa6,0x10032c60,0x10032f24,0x10036a24]:
  assert old[at-0x10000000+2:at-0x10000000+6]==bl(at+2,0x10009c20)
  change(at,bytes.fromhex('1920'),bytes.fromhex('0c20'),'UI-only stable recheck: 25ms to 12ms')
 for at in [0x10000270,0x1000d124]:
  change(at,struct.pack('<I',0x2001f9b8),struct.pack('<I',symbols['__polish_bss_end']),'Reserve/zero UI cache, keep original allocator')
 change(0x100223a0,struct.pack('<I',0x10038817),struct.pack('<I',0x10000000+len(data)),'Complete image size')
 assert old.count(b'v2.2.6')==1
 change(0x10000000+old.index(b'v2.2.6'),b'v2.2.6',b'v2.2.7','About version')
 allowed=set()
 for c in changes:
  p=int(c['address'],16)-0x10000000;allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
 diff={i for i,(x,y) in enumerate(zip(old,data)) if x!=y};assert diff<=allowed
 for lo,hi in [(0x318,0x2018),(0x23f8,0x7164),(0x88b0,0x8d10),(0x37800,0x38400),(0x38400,0x38900)]:
  assert data[lo:hi]==old[lo:hi],('LCD/core/worker/codec/battery changed',hex(lo))
 data.extend(bytes(-len(data)%256));(BUILD/'patched.bin').write_bytes(data)
 out=bytearray();count=len(data)//256
 for i in range(count):
  out+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
  out+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
 OUT.mkdir(exist_ok=True);target=OUT/'ScarletPico-v2_2_7-RP2040-UI-POLISH.uf2';target.write_bytes(out)
 audit=dict(version='2.2.7-legacy-ui-polish',source_sha256=EXPECTED,uf2_sha256=sha(target),
            rollback_path=str(SOURCE.relative_to(ROOT)),automatically_flashed=False,hardware_new_build_tested=False,
            appended_code_bytes=len(addition),added_static_ram=symbols['__polish_bss_end']-0x2001f9b8,
            new_heap_allocations=0,changed_base_bytes=len(diff),changes=changes,
            lcd_core_clocks_audio_worker_battery_byte_identical=True,game_size=[356,320],ui_debounce_ms=12,
            boot_entrance_ms=600,boot_hold_ms=120,original_chime_unchanged=True,
            elf_sha256=sha(elf),image_sha256=sha(BUILD/'patched.bin'))
 (OUT/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 metrics=BUILD/'metrics.json'
 if metrics.exists() and json.loads(metrics.read_text()).get('uf2_sha256')==audit['uf2_sha256']:
  shutil.copy2(metrics,OUT/'metrics.json')
 for name in ['library-en.png','library-ru.png']:
  if (BUILD/name).exists():shutil.copy2(BUILD/name,OUT/name)
 with zipfile.ZipFile(OUT/'ScarletPico-v2_2_7-ui-source.zip','w',zipfile.ZIP_DEFLATED) as z:
  for f in [ROOT/'ui-polish-addon/ui.c',ROOT/'ui-polish-addon/ui.ld',ROOT/'ui-addon/ui.h',Path(__file__),
            ROOT/'tools/uf2_audio_patch.py',ROOT/'tests/test_ui_polish_arm.py',ROOT/'tests/test_legacy_battery_arm.py',
            ROOT/'tests/test_video_heap_arm.py',SOURCE,SOURCE.parent/'build-audit.json',
            ROOT/'build-battery-legacy-addon/battery.elf',ROOT/'build-battery-legacy-addon/patched.bin',
            ROOT/'build-features-v2_2_2-addon/features.elf',ROOT/'build-pause-ui-addon/pause-ui.elf']:
   if f.exists():z.write(f,'firmware/'+str(f.resolve().relative_to(ROOT)))
  for name in ['README-RU.md','VALIDATION.md','build-audit.json','metrics.json']:
   if (OUT/name).exists():z.write(OUT/name,name)
 print(json.dumps(audit,indent=2));print(target)
if __name__=='__main__':main()
