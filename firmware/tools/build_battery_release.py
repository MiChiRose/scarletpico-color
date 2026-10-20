"""Build/package the optional RP2040 battery monitor. Never access USB devices."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile
from build_rp2040_native import read_uf2

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'imported/scarletpico-rp2040-source'
BUILD=ROOT/'build-rp2040-battery'
OUT=ROOT/'releases/2026-10-20-rp2040-battery'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(*args):subprocess.run([str(a) for a in args],check=True)
def main():
    if '#define FEATURES_VERSION "2.2.4-RP2040"' not in (SOURCE/'console.h').read_text():
        raise SystemExit('Historical 2.2.4 packager: restore its frozen source ZIP first; refusing to overwrite the old release.')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--toolchain',type=Path,required=True)
    p.add_argument('--sdk',type=Path,default=ROOT/'vendor/pico-sdk')
    p.add_argument('--pioasm-dir',type=Path,required=True)
    a=p.parse_args()
    run('cmake','-S',SOURCE,'-B',BUILD,'-G','Ninja',
        f'-DPICO_SDK_PATH={a.sdk.resolve()}',f'-DPICO_TOOLCHAIN_PATH={a.toolchain.resolve()}',
        '-DPICO_PLATFORM=rp2040','-DPICO_BOARD=waveshare_rp2040_zero',
        '-DCMAKE_BUILD_TYPE=Release',f'-DPython3_EXECUTABLE={sys.executable}',
        '-DPICO_NO_PICOTOOL=1',f'-Dpioasm_DIR={a.pioasm_dir.resolve()}',
        '-DSCARLET_CPU_KHZ=200000','-DSCARLET_LCD_HZ=100000000','-DSCARLET_SCALE=2')
    run('cmake','--build',BUILD,'--parallel','4')
    raw=(BUILD/'scarlet2040.bin').read_bytes()
    assert raw and len(raw)<0x7f000
    blocks=[];count=(len(raw)+255)//256
    for i in range(count):
        payload=raw[i*256:(i+1)*256].ljust(256,b'\xff')
        header=struct.pack('<8I',0x0a324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
        blocks.append(header+payload+b'\0'*220+struct.pack('<I',0x0ab16f30))
    uf2=BUILD/'scarlet2040.uf2';uf2.write_bytes(b''.join(blocks));read_uf2(uf2)
    attrs=subprocess.check_output([a.toolchain/'bin/arm-none-eabi-readelf','-A',BUILD/'scarlet2040.elf'],text=True)
    assert 'Tag_CPU_arch: v6S-M' in attrs and 'Tag_THUMB_ISA_use: Thumb-1' in attrs
    symbols={}
    for line in subprocess.check_output([a.toolchain/'bin/arm-none-eabi-nm','-n',BUILD/'scarlet2040.elf'],text=True).splitlines():
        parts=line.split()
        if len(parts)==3:symbols[parts[2]]=int(parts[0],16)
    assert symbols['__flash_binary_end']<=0x1007f000
    assert symbols['__bss_end__']+20000<symbols['__HeapLimit']==0x20040000
    for name in ('__gb_step_cpu','__gb_draw_line','gb_run_frame'):
        assert 0x20000000<=symbols[name]<0x20040000
    rollback=ROOT/'releases/2026-10-07-rp2040-native-menu/02-ScarletPico-v2_2_3-RP2040-NATIVE-TEST.uf2'
    read_uf2(rollback)
    baseline=json.loads((rollback.parent/'build-audit.json').read_text())
    assert sha(rollback)==baseline['uf2_sha256']
    assert sha(ROOT/'imported/scarletpico-rp2350-source/third_party/peanut/peanut_gb.h')==baseline['kernel_header_sha256']
    assert sha(ROOT/'imported/scarletpico-rp2350-source/display.c')==baseline['lcd_driver_sha256']
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'ScarletPico-v2_2_4-RP2040-BATTERY-TEST.uf2';shutil.copy2(uf2,target)
    audit={'version':'2.2.4-RP2040-battery-test','hardware_tested':False,'automatically_flashed':False,
        'monitor_default':'OFF; explicit hardware confirmation, persisted extension at settings byte 16',
        'uf2_family':'e48bff56','uf2_sha256':sha(target),'rollback_path':str(rollback.relative_to(ROOT)),
        'rollback_sha256':sha(rollback),'compiler':subprocess.check_output([a.toolchain/'bin/arm-none-eabi-gcc','--version'],text=True).splitlines()[0],
        'flash_end':hex(symbols['__flash_binary_end']),'bss_end':hex(symbols['__bss_end__']),
        'heap_remaining_bytes':symbols['__HeapLimit']-symbols['__bss_end__'],
        'sense_pins':{'adc':29,'isolated_charge_active_low':18,'isolated_done_active_low':19},
        'kernel_sha256':sha(ROOT/'imported/scarletpico-rp2350-source/third_party/peanut/peanut_gb.h'),
        'display_sha256':sha(ROOT/'imported/scarletpico-rp2350-source/display.c')}
    (OUT/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    files=[]
    for folder in (SOURCE,ROOT/'imported/scarletpico-rp2350-source',ROOT/'ui-addon',ROOT/'features-addon',ROOT/'tools',ROOT/'tests'):
        files.extend(f for f in folder.rglob('*') if f.is_file() and f.suffix in ('.c','.h','.py','.sh','.txt','.md','.ld','.pio') and '__pycache__' not in f.parts)
    files.append(ROOT/'src/audio_i2s.pio')
    files.extend((ROOT/'vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu').glob('*.[ch]'))
    with zipfile.ZipFile(OUT/'ScarletPico-v2_2_4-source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(set(files)):z.write(f,'firmware/'+str(f.relative_to(ROOT)))
        for name in ('README-RU.md','build-audit.json'):
            if (OUT/name).exists():z.write(OUT/name,name)
        z.write(ROOT.parent/'docs/HARDWARE-BATTERY.md','docs/HARDWARE-BATTERY.md')
    print(json.dumps(audit,indent=2));print('UF2:',target)
if __name__=='__main__':main()
