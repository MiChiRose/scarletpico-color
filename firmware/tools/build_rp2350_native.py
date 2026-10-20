"""Rebuild native RP2350 source + our shared UI. Never flash a USB device."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from rp2350_binary import read_image

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'imported/scarletpico-rp2350-source'
OUT=ROOT/'releases/2026-10-07-rp2350-native-menu'
BASE_SHA='168d797c856a7a8651c5a1795ac0822b303f4af3f56920f18dbf0581ddc73761'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(*args):subprocess.run([str(a) for a in args],check=True)
def function(s,name):
    m=re.search(r'(?:__not_in_flash_func\('+name+r'\)|\b'+name+r')\([^;{]*\)\s*\{',s);assert m,name
    start=m.end()-1;level=0
    for end in range(start,len(s)):
        if s[end]=='{':level+=1
        elif s[end]=='}':
            level-=1
            if not level:return s[start:end+1]
    raise ValueError(name)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk',type=Path,default=Path(os.environ.get('PICO_SDK_PATH',ROOT/'vendor/pico-sdk')))
    p.add_argument('--toolchain',type=Path,default=Path(os.environ.get('PICO_TOOLCHAIN_PATH','/tmp/scarlet-arm-gnu')))
    p.add_argument('--picotool',type=Path,default=Path('/tmp/scarlet-picotool-build/picotool'))
    p.add_argument('--pioasm-dir',type=Path,default=Path('/tmp/scarlet-pioasm-install/lib/cmake/pioasm'))
    p.add_argument('--incoming-source',type=Path)
    p.add_argument('--rollback',type=Path)
    a=p.parse_args();build=ROOT/'build-rp2350-source'
    cmake=shutil.which('cmake');assert cmake,'CMake is required'
    args=[cmake,'-S',SOURCE,'-B',build,'-G','Ninja',
          f'-DPICO_SDK_PATH={a.sdk.resolve()}',f'-DPICO_TOOLCHAIN_PATH={a.toolchain.resolve()}',
          '-DCMAKE_BUILD_TYPE=Release','-DPICO_NO_PICOTOOL=0',
          f'-DPython3_EXECUTABLE={os.sys.executable}',
          '-DPICO_DEFAULT_BOOT_STAGE2=boot2_w25q080',
          '-DSCARLET_CPU_KHZ=200000','-DSCARLET_LCD_HZ=100000000','-DSCARLET_SCALE=2',
          '-DSCARLET_RETARGET_COMPAT=OFF']
    if a.picotool.exists():args.append(f'-DSCARLET_PICOTOOL={a.picotool.resolve()}')
    if a.pioasm_dir.exists():args.append(f'-Dpioasm_DIR={a.pioasm_dir.resolve()}')
    run(*args);run(cmake,'--build',build,'--parallel','4')
    uf2=build/'scarlet2350.uf2';data,ignored,digest=read_image(uf2)
    assert len(data)<0x7f000 and len(ignored)==1,'Flash/settings overlap or wrong UF2 target'
    symbols={}
    nm=a.toolchain/'bin/arm-none-eabi-nm'
    for line in subprocess.check_output([str(nm),'-n',str(build/'scarlet2350.elf')],text=True).splitlines():
        parts=line.split()
        if len(parts)==3:symbols[parts[2]]=int(parts[0],16)
    for name in ('__gb_step_cpu','__gb_draw_line','gb_run_frame'):
        assert 0x20000000<=symbols[name]<0x20080000,(name,'core is not in RAM')
    assert symbols['__flash_binary_end']<=0x1007f000
    assert symbols['__bss_end__']<symbols['__StackLimit'],'RAM/stack overlap'
    audit={'hardware_tested':False,'version':'3.0-RP2350-test','sha256':digest,
           'platform':'RP2350 ARM Secure','cpu_mhz':200,'lcd_requested_mhz':100,
           'game_size':[320,288],'audio':'MAX98357A I2S GP11/12/13, 16 kHz mono mix',
           'ram_core':True,'rom_limit_bytes':3670016,'snapshot_format':'23500002',
           'native_functions_preserved':[],
           'flash_end':hex(symbols['__flash_binary_end']),
           'bss_end':hex(symbols['__bss_end__']),'stack_limit':hex(symbols['__StackLimit'])}
    if a.incoming_source:
        with zipfile.ZipFile(a.incoming_source) as z:
            prefix='scarletpico-rp2350-source/'
            original=z.read(prefix+'third_party/peanut/peanut_gb.h')
            assert original==(SOURCE/'third_party/peanut/peanut_gb.h').read_bytes()
            audit['kernel_header_sha256']=hashlib.sha256(original).hexdigest()
            audit['incoming_archive_sha256']=sha(a.incoming_source)
            for file,names in [('display.c',['display_frame','window','send_row','bus_idle','finish_window','display_game_speed','display_sd_speed','display_init']),
                               ('main.c',['publish_frame','video_worker','draw_line'])]:
                old=z.read(prefix+file).decode();new=(SOURCE/file).read_text()
                for name in names:
                    assert function(old,name)==function(new,name),(file,name,'native rendering changed')
                    audit['native_functions_preserved'].append(name)
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'02-ScarletPico-v3_0-RP2350-OUR-MENU.uf2';shutil.copy2(uf2,target)
    if a.rollback:
        assert sha(a.rollback)==BASE_SHA,'Not the native B rollback'
        shutil.copy2(a.rollback,OUT/'01-RP2350-NATIVE-B-ROLLBACK.uf2')
    (OUT/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    # Complete portable source subset: SDK/toolchain and game ROMs are excluded.
    files=list(SOURCE.rglob('*'))
    files=[f for f in files if f.is_file() and not any(part.startswith('build-') for part in f.relative_to(SOURCE).parts)]
    shared=['ui-addon/ui.c','ui-addon/ui.h','features-addon/features.h',
            'features-addon/boot.c','features-addon/pause.c','src/audio_i2s.pio',
            'tools/build_rp2350_native.py','tools/rp2350_binary.py',
            'tests/test_rp2350_states.c','tests/test_rp2350_menu_arm.py','tests/test_rp2350_roms.c',
            'tests/test_ui.c','tests/test_partition_mount.c','tests/run_rp2350_tests.sh','tests/stubs/pico/stdlib.h']
    files += [ROOT/f for f in shared]
    files += list((ROOT/'vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu').glob('*'))
    with zipfile.ZipFile(OUT/'ScarletPico-v3_0-RP2350-source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,'firmware/'+str(f.relative_to(ROOT)))
        for name in ('README-RU.md','VALIDATION.md','build-audit.json'):
            if (OUT/name).exists():z.write(OUT/name,name)
    print(json.dumps(audit,indent=2));print('UF2:',target)
if __name__=='__main__':main()
