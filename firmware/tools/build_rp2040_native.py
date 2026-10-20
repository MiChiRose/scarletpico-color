"""Build the native RP2040 port, audit its target/memory, package; never flash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile
from build_rp2350_native import function

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'imported/scarletpico-rp2040-source'
NATIVE=ROOT/'imported/scarletpico-rp2350-source'
OUT=ROOT/'releases/2026-10-07-rp2040-native-menu'
ROLLBACK_SHA='98b80f2827d626e697b83034d426b77e5fe028e1792f30edaec50a80ab963089'
KERNEL_SHA='6244f56ee63933987b4bbfb7401c1ddef9d8e2610b9a78a882776e785631e551'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(*args):subprocess.run([str(a) for a in args],check=True)
def read_uf2(path):
    raw=path.read_bytes();assert raw and len(raw)%512==0
    blocks=[]
    for offset in range(0,len(raw),512):
        block=raw[offset:offset+512]
        m0,m1,flags,addr,n,index,count,family=struct.unpack_from('<8I',block)
        assert (m0,m1)==(0x0a324655,0x9e5d5157) and struct.unpack_from('<I',block,508)[0]==0x0ab16f30
        assert flags==0x2000 and family==0xe48bff56,'UF2 is not ordinary RP2040 flash firmware'
        assert n==256 and count==len(raw)//512 and index==offset//512
        assert addr==0x10000000+index*256,'Non-contiguous UF2'
        blocks.append(block[32:32+n])
    image=b''.join(blocks);assert len(image)<0x7f000
    stack,reset=struct.unpack_from('<II',image,256)
    assert stack==0x20042000 and reset&1 and 0x10000100<=reset<0x10000000+len(image)
    assert image[:256]!=b'\0'*256,'Missing standard SDK boot2'
    return image
def main():
    if '#define FEATURES_VERSION "2.2.3-RP2040"' not in (SOURCE/'console.h').read_text():
        raise SystemExit('This historical packager only accepts 2.2.3 sources. For the current battery build use tools/build_battery_release.py; old release files were not overwritten.')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk',type=Path,default=Path(os.environ.get('PICO_SDK_PATH',ROOT/'vendor/pico-sdk')))
    p.add_argument('--toolchain',type=Path,default=Path(os.environ.get('PICO_TOOLCHAIN_PATH','/tmp/scarlet-arm-gnu')))
    p.add_argument('--picotool',type=Path,default=Path('/tmp/scarlet-picotool-build/picotool'))
    p.add_argument('--pioasm-dir',type=Path,default=Path('/tmp/scarlet-pioasm-install/lib/cmake/pioasm'))
    p.add_argument('--incoming-source',type=Path)
    p.add_argument('--rollback',type=Path,default=ROOT/'releases/2026-09-28-shadow-fast-test/02-SHADOW-FAST-TEST.uf2')
    a=p.parse_args();build=ROOT/'build-rp2040-native'
    cmake=shutil.which('cmake');assert cmake,'CMake is required'
    args=[cmake,'-S',SOURCE,'-B',build,'-G','Ninja',
        f'-DPICO_SDK_PATH={a.sdk.resolve()}',f'-DPICO_TOOLCHAIN_PATH={a.toolchain.resolve()}',
        '-DPICO_PLATFORM=rp2040','-DPICO_BOARD=waveshare_rp2040_zero',
        '-DCMAKE_BUILD_TYPE=Release',f'-DPython3_EXECUTABLE={os.sys.executable}',
        '-DPICO_DEFAULT_BOOT_STAGE2=boot2_w25q080','-DSCARLET_CPU_KHZ=200000',
        '-DSCARLET_LCD_HZ=100000000','-DSCARLET_SCALE=2']
    if a.picotool.exists():args.append(f'-DSCARLET_PICOTOOL={a.picotool.resolve()}')
    if a.pioasm_dir.exists():args.append(f'-Dpioasm_DIR={a.pioasm_dir.resolve()}')
    run(*args);run(cmake,'--build',build,'--parallel','4')
    uf2=build/'scarlet2040.uf2';image=read_uf2(uf2)
    symbols={}
    for line in subprocess.check_output([str(a.toolchain/'bin/arm-none-eabi-nm'),'-n',str(build/'scarlet2040.elf')],text=True).splitlines():
        parts=line.split()
        if len(parts)==3:symbols[parts[2]]=int(parts[0],16)
    attrs=subprocess.check_output([str(a.toolchain/'bin/arm-none-eabi-readelf'),'-A',str(build/'scarlet2040.elf')],text=True)
    assert 'Tag_CPU_arch: v6S-M' in attrs and 'Tag_THUMB_ISA_use: Thumb-1' in attrs,attrs
    assert symbols['__flash_binary_end']<=0x1007f000
    assert symbols['__bss_end__']+20000<symbols['__HeapLimit']==0x20040000
    for name in ('__gb_step_cpu','__gb_draw_line','gb_run_frame'):
        assert 0x20000000<=symbols[name]<0x20040000,(name,'core is not in RAM')
    assert sha(NATIVE/'third_party/peanut/peanut_gb.h')==KERNEL_SHA
    assert sha(a.rollback)==ROLLBACK_SHA,'Wrong RP2040 rollback'
    read_uf2(a.rollback)
    audit={'version':'2.2.3-RP2040-test','hardware_tested':False,'automatically_flashed':False,
        'platform':'RP2040 Cortex-M0+ ARMv6-M','uf2_family':'e48bff56','uf2_sha256':sha(uf2),
        'rollback_sha256':ROLLBACK_SHA,'kernel_header_sha256':KERNEL_SHA,
        'boot2':'standard Pico SDK boot2_w25q080; factory ROM unchanged',
        'cpu_mhz':200,'lcd_requested_mhz':100,'sd_requested_mhz':12,'game_size':[320,288],
        'audio':'MAX98357A I2S GP11/12/13, DMA IRQ1, 16 kHz mono mix, default 50%',
        'max_entries':64,'frame_buffers':2,'frame_buffer_bytes':92160,'cart_ram_bytes':32768,
        'snapshot_payload_max_bytes':83036,'snapshot_format':'20400003',
        'flash_cache_bytes':1572864,'largest_standard_rom_bytes':1048576,'large_rom_streaming':False,
        'flash_end':hex(symbols['__flash_binary_end']),'bss_end':hex(symbols['__bss_end__']),
        'heap_limit':hex(symbols['__HeapLimit']),'heap_remaining_bytes':symbols['__HeapLimit']-symbols['__bss_end__'],
        'native_functions_preserved':[]}
    if a.incoming_source:
        with zipfile.ZipFile(a.incoming_source) as z:
            prefix='scarletpico-rp2350-source/'
            assert z.read(prefix+'third_party/peanut/peanut_gb.h')==(NATIVE/'third_party/peanut/peanut_gb.h').read_bytes()
            old_display=z.read(prefix+'display.c').decode()
            new_display=(NATIVE/'display.c').read_text()
            # Only the bottom FPS label and added menu drawing adapters differ.
            assert old_display.split('void display_status(')[0]==new_display.split('void display_status(')[0],'Native LCD transfer driver changed'
            audit['lcd_driver_sha256']=sha(NATIVE/'display.c')
            audit['lcd_only_frontend_changes']='Bottom FPS label; menu dirty-region drawing adapters'
            audit['incoming_archive_sha256']=sha(a.incoming_source)
            for file,names in [('display.c',['display_frame','window','send_row','bus_idle','finish_window','display_game_speed','display_sd_speed','display_init']),('main.c',['draw_line','video_worker'])]:
                old=z.read(prefix+file).decode();new=((NATIVE if file=='display.c' else SOURCE)/file).read_text()
                for name in names:
                    original=function(old,name);ported=function(new,name)
                    if name=='video_worker':original=original.replace('i<3','i<FRAME_BUFFERS')
                    assert original==ported,(file,name,'unexpected native rendering change')
                    audit['native_functions_preserved'].append(name)
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'02-ScarletPico-v2_2_3-RP2040-NATIVE-TEST.uf2';shutil.copy2(uf2,target)
    shutil.copy2(a.rollback,OUT/'01-ScarletPico-v2_2_2-RP2040-ROLLBACK.uf2')
    (OUT/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    files=[f for folder in (SOURCE,NATIVE) for f in folder.rglob('*') if f.is_file() and not any(part.startswith('build-') for part in f.relative_to(folder).parts)]
    shared=['ui-addon/ui.c','ui-addon/ui.h','features-addon/features.h','features-addon/boot.c','features-addon/pause.c',
        'src/audio_i2s.pio','tools/build_rp2040_native.py','tools/build_rp2350_native.py','tools/rp2350_binary.py',
        'tests/test_rp2350_states.c','tests/test_rp2350_menu_arm.py','tests/test_rp2350_roms.c',
        'tests/test_ui.c','tests/test_partition_mount.c','tests/run_rp2040_native_tests.sh','tests/stubs/pico/stdlib.h']
    files.extend(ROOT/f for f in shared)
    files.extend(f for f in (ROOT/'vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu').glob('*') if f.is_file())
    with zipfile.ZipFile(OUT/'ScarletPico-v2_2_3-RP2040-source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in files:z.write(f,'firmware/'+str(f.relative_to(ROOT)))
        for name in ('README-RU.md','VALIDATION.md','build-audit.json'):
            if (OUT/name).exists():z.write(OUT/name,name)
    print(json.dumps(audit,indent=2));print('UF2:',target)
if __name__=='__main__':main()
