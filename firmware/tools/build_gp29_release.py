"""Build the assembled GP29-only RP2040 monitor. Never access USB devices."""
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
BUILD=ROOT/'build-rp2040-gp29'
OUT=ROOT/'releases/2026-10-20-rp2040-gp29'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(*args):subprocess.run([str(a) for a in args],check=True)
def main():
    if '#define FEATURES_VERSION "2.2.5-RP2040"' not in (SOURCE/'console.h').read_text():
        raise SystemExit('This packager requires the frozen 2.2.5 source version.')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--toolchain',type=Path,required=True)
    p.add_argument('--sdk',type=Path,default=ROOT/'vendor/pico-sdk')
    p.add_argument('--pioasm-dir',type=Path,required=True)
    p.add_argument('--lcd-hz',type=int,choices=(12500000,100000000),default=100000000,
                   help='12.5 MHz creates a separate display-check bundle; never overwrites the normal release.')
    a=p.parse_args()
    check=a.lcd_hz==12500000
    build=ROOT/'build-rp2040-gp29-lcd12' if check else BUILD
    out=ROOT/'releases/2026-10-20-rp2040-gp29-lcd12-check' if check else OUT
    run('cmake','-S',SOURCE,'-B',build,'-G','Ninja',
        f'-DPICO_SDK_PATH={a.sdk.resolve()}',f'-DPICO_TOOLCHAIN_PATH={a.toolchain.resolve()}',
        '-DPICO_PLATFORM=rp2040','-DPICO_BOARD=waveshare_rp2040_zero',
        '-DCMAKE_BUILD_TYPE=Release',f'-DPython3_EXECUTABLE={sys.executable}',
        '-DPICO_NO_PICOTOOL=1',f'-Dpioasm_DIR={a.pioasm_dir.resolve()}',
        '-DSCARLET_CPU_KHZ=200000',f'-DSCARLET_LCD_HZ={a.lcd_hz}','-DSCARLET_SCALE=2')
    run('cmake','--build',build,'--parallel','4')
    raw=(build/'scarlet2040.bin').read_bytes()
    assert raw and len(raw)<0x7f000
    blocks=[];count=(len(raw)+255)//256
    for i in range(count):
        payload=raw[i*256:(i+1)*256].ljust(256,b'\xff')
        header=struct.pack('<8I',0x0a324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
        blocks.append(header+payload+b'\0'*220+struct.pack('<I',0x0ab16f30))
    uf2=build/'scarlet2040.uf2';uf2.write_bytes(b''.join(blocks));read_uf2(uf2)
    attrs=subprocess.check_output([a.toolchain/'bin/arm-none-eabi-readelf','-A',build/'scarlet2040.elf'],text=True)
    assert 'Tag_CPU_arch: v6S-M' in attrs and 'Tag_THUMB_ISA_use: Thumb-1' in attrs
    symbols={}
    for line in subprocess.check_output([a.toolchain/'bin/arm-none-eabi-nm','-n',build/'scarlet2040.elf'],text=True).splitlines():
        parts=line.split()
        if len(parts)==3:symbols[parts[2]]=int(parts[0],16)
    assert symbols['__flash_binary_end']<=0x1007f000
    assert symbols['__bss_end__']+20000<symbols['__HeapLimit']==0x20040000
    assert 'console_power_charge_pins' not in symbols
    for name in ('__gb_step_cpu','__gb_draw_line','gb_run_frame'):
        assert 0x20000000<=symbols[name]<0x20040000
    rollback=ROOT/'releases/2026-10-07-rp2040-native-menu/02-ScarletPico-v2_2_3-RP2040-NATIVE-TEST.uf2'
    read_uf2(rollback)
    baseline=json.loads((rollback.parent/'build-audit.json').read_text())
    assert sha(rollback)==baseline['uf2_sha256']
    kernel=ROOT/'imported/scarletpico-rp2350-source/third_party/peanut/peanut_gb.h'
    display=ROOT/'imported/scarletpico-rp2350-source/display.c'
    assert sha(kernel)==baseline['kernel_header_sha256']
    assert sha(display)==baseline['lcd_driver_sha256']
    out.mkdir(parents=True,exist_ok=True)
    target=out/('ScarletPico-v2_2_5-RP2040-GP29-LCD12-CHECK.uf2' if check else 'ScarletPico-v2_2_5-RP2040-GP29.uf2')
    shutil.copy2(uf2,target)
    audit={'version':'2.2.5-RP2040-GP29','hardware_tested':False,'automatically_flashed':False,
        'monitor_default':'ON for confirmed assembled divider; BAT2 OFF remains respected',
        'uf2_family':'e48bff56','uf2_sha256':sha(target),'rollback_path':str(rollback.relative_to(ROOT)),
        'rollback_sha256':sha(rollback),'compiler':subprocess.check_output([a.toolchain/'bin/arm-none-eabi-gcc','--version'],text=True).splitlines()[0],
        'flash_end':hex(symbols['__flash_binary_end']),'bss_end':hex(symbols['__bss_end__']),
        'heap_remaining_bytes':symbols['__HeapLimit']-symbols['__bss_end__'],
        'sense_pins':{'adc':29,'charger_status':None},'divider_ohms':[4700,4700],
        'adc_reference_nominal_mv':3300,'sample_interval_us':1000000,
        'indicator_rectangle':[400,0,80,44],'voltage_text_y':28,
        'cpu_hz':200000000,'lcd_requested_hz':a.lcd_hz,'display_check_only':check,
        'kernel_sha256':sha(kernel),'display_sha256':sha(display)}
    (out/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    files=[]
    for folder in (SOURCE,ROOT/'imported/scarletpico-rp2350-source',ROOT/'ui-addon',ROOT/'features-addon',ROOT/'tools',ROOT/'tests'):
        files.extend(f for f in folder.rglob('*') if f.is_file() and f.suffix in ('.c','.h','.py','.sh','.txt','.md','.ld','.pio') and '__pycache__' not in f.parts)
    files.append(ROOT/'src/audio_i2s.pio')
    files.extend((ROOT/'vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu').glob('*.[ch]'))
    with zipfile.ZipFile(out/'ScarletPico-v2_2_5-source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(set(files)):z.write(f,'firmware/'+str(f.relative_to(ROOT)))
        for name in ('README-RU.md','build-audit.json','VALIDATION.md'):
            if (out/name).exists():z.write(out/name,name)
        z.write(ROOT.parent/'docs/HARDWARE-BATTERY.md','docs/HARDWARE-BATTERY.md')
    print(json.dumps(audit,indent=2));print('UF2:',target)
if __name__=='__main__':main()
