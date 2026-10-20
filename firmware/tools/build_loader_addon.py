#!/usr/bin/env python3
"""Produce a separate fast-load build; never overwrite the UI v1 rollback.
The whole existing UI/audio/game payload is preserved, except three loader
call sites, BSS/heap bounds and firmware-length metadata. No core rebuild.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
from uf2_audio_patch import bl

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-loader-addon'
ARM=Path('/tmp/arm-gnu/bin')
SOURCE=ROOT/'releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1.uf2'
EXPECTED='40063b38b3413c9fd7ed7c0aebe92ad59f0942546a2292b3efb527b626d8c9ee'
RELEASE=ROOT/'releases/scarletpico-v0_9-B-200mhz-lcd50-sd12-ui-v1-fastload.uf2'
BUNDLE=ROOT/'releases/2026-09-28-rollback-and-fastload'

def run(args):
    p=subprocess.run([str(a) for a in args],text=True,capture_output=True)
    if p.stderr:
        with (OUT/'toolchain.log').open('a') as f:f.write(p.stderr)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout

def read_uf2():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==EXPECTED,'Rollback hash mismatch'
    parts=[]
    for i in range(0,len(raw),512):
        block=raw[i:i+512]
        assert struct.unpack_from('<8I',block)==(0xa324655,0x9e5d5157,0x2000,
            0x10000000+i//2,256,i//512,len(raw)//512,0xe48bff56)
        assert struct.unpack_from('<I',block,508)[0]==0xab16f30
        parts.append(block[32:288])
    data=b''.join(parts)
    assert len(data)==0x32400
    return data

def symbols(path):
    result={}
    for line in run([ARM/'arm-none-eabi-nm','-n',path]).splitlines():
        p=line.split()
        if len(p)==3:result[p[2]]=int(p[0],16)
    return result

def main():
    OUT.mkdir(exist_ok=True)
    old=read_uf2()
    (OUT/'baseline.bin').write_bytes(old)
    # Validate the UI ELF used by our regression harness against the payload.
    ui_elf=ROOT/'build-ui-addon/ui.elf'
    run([ARM/'arm-none-eabi-objcopy','-O','binary',ui_elf,OUT/'verified-ui.bin'])
    ui=(OUT/'verified-ui.bin').read_bytes()
    assert old[0x2ff00:0x2ff00+len(ui)]==ui
    ui_symbols=symbols(ui_elf)
    for name,value in {'ui_prepare_rom':0x10031450,'ui_spinner_tick':0x10030e74,
                       'sd_bus':0x10031190,'loading':0x2001f401,
                       'spinner_time':0x2001f3fc,'__ui_bss_end':0x2001f7d8}.items():
        assert ui_symbols[name]==value
    # These SDK allocation wrappers contain no panic-on-OOM path.
    assert old[0xb8cc:0xb8ea].hex()=='70b50400064d280014f0c4fd200010f0e1fa0400280014f02dfd200070bd'
    assert old[0xb918:0xb932].hex()=='70b50400054d280014f09efd200010f0c5fa280014f008fd70bd'
    flags=['-mcpu=cortex-m0plus','-mthumb','-Os','-std=c11','-fshort-enums',
           '-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections',
           '-fstack-usage','-Wall','-Wextra','-Werror']
    run([ARM/'arm-none-eabi-gcc',*flags,'-c',ROOT/'loader-addon/loader.c','-o',OUT/'loader.o'])
    elf=OUT/'loader.elf'
    exports=['loader_prepare','loader_header_read','loader_page_read']
    run([ARM/'arm-none-eabi-gcc','-mcpu=cortex-m0plus','-mthumb','-nostdlib',
         '-Wl,--gc-sections',*['-Wl,--undefined='+n for n in exports],
         '-Wl,-Map='+str(OUT/'loader.map'),'-T',ROOT/'loader-addon/loader.ld',
         '-T',ROOT/'loader-addon/base-symbols.ld',OUT/'loader.o','-o',elf])
    run([ARM/'arm-none-eabi-objcopy','-O','binary',elf,OUT/'loader.bin'])
    (OUT/'loader.dis').write_text(run([ARM/'arm-none-eabi-objdump','-d',elf]))
    syms=symbols(elf)
    addition=(OUT/'loader.bin').read_bytes()
    data=bytearray(old+addition)
    changes=[]
    def change(at,before,after,purpose):
        p=at-0x10000000
        assert len(before)==len(after) and old[p:p+len(before)]==before,hex(at)
        data[p:p+len(after)]=after
        changes.append(dict(address=hex(at),before=before.hex(),after=after.hex(),purpose=purpose))
    for at,old_target,new in [(0x10007f08,0x10031450,'loader_prepare'),
                              (0x1000853e,0x10031470,'loader_header_read'),
                              (0x100085fe,0x10031470,'loader_page_read')]:
        change(at,bl(at,old_target),bl(at,syms[new]),new)
    end=syms['__loader_bss_end']
    assert end-0x2001f7d8==16
    for at in [0x10000270,0x1000d124]:
        change(at,struct.pack('<I',0x2001f7d8),struct.pack('<I',end),'Reserve 16 bytes loader state; temporary read buffer is freed')
    change(0x100223a0,struct.pack('<I',0x1003230c),struct.pack('<I',0x10000000+len(data)),'Firmware end metadata')
    allowed=set()
    for c in changes:
        p=int(c['address'],16)-0x10000000
        allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
    changed={i for i,(a,b) in enumerate(zip(old,data)) if a!=b}
    assert changed<=allowed
    # Stronger than selected-function hashes: EVERY other original byte,
    # including the complete UI, APU/mixer, clocks, IRQs/DMA and renderer.
    assert data[0x2e000:len(old)]==old[0x2e000:]
    assert len(data)<0x7f000
    data.extend(bytes(-len(data)%256))
    uf2=bytearray();total=len(data)//256
    for i in range(total):
        uf2+=struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,total,0xe48bff56)
        uf2+=data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
    RELEASE.write_bytes(uf2)
    (OUT/'patched.bin').write_bytes(data)
    report=dict(source_sha256=EXPECTED,output_sha256=hashlib.sha256(uf2).hexdigest(),
                modified_original_bytes=len(changed),appended_flash_bytes=len(addition),
                added_static_ram_bytes=end-0x2001f7d8,temporary_read_buffer_bytes=4096,
                core_audio_video_ui_clocks_byte_identical=True,
                rom_cache_offset='0x80000',rom_data_offset='0x81000',settings_offset='0x7f000',changes=changes)
    RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    BUNDLE.mkdir(exist_ok=True)
    rollback=BUNDLE/'01-current-ui-v1-ROLLBACK.uf2'
    if rollback.exists():assert hashlib.sha256(rollback.read_bytes()).hexdigest()==EXPECTED
    else:shutil.copyfile(SOURCE,rollback)
    shutil.copyfile(RELEASE,BUNDLE/'02-ui-v1-FASTLOAD.uf2')
    shutil.copyfile(RELEASE.with_suffix('.json'),BUNDLE/'02-ui-v1-FASTLOAD.json')
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED
    print(run([ARM/'arm-none-eabi-size',elf]))
    print(json.dumps({k:v for k,v in report.items() if k!='changes'},indent=2))
    print(BUNDLE)

if __name__=='__main__':main()
