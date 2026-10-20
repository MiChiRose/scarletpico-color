#!/usr/bin/env python3
"""Append pause settings + bottom FPS to exact PACED image. Never flash."""
from pathlib import Path
import hashlib, json, os, struct, subprocess
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build-pause-ui-addon'
SOURCE = ROOT / 'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2'
EXPECTED = 'fd376fa8265701282fe4397d8ea6ae3ce193ab2e9fb1046acc568675e495feff'
RELEASE = ROOT / 'releases/scarletpico-v2_2_2-PAUSE-SETTINGS-TEST.uf2'
ARM = Path(os.environ.get('ARM_GCC_BIN', '/tmp/arm-gnu/bin'))
def run(args):
    p = subprocess.run([str(x) for x in args], text=True, capture_output=True)
    if p.stderr:
        with (OUT/'toolchain.log').open('a') as log:log.write(p.stderr)
        messages=[line for line in p.stderr.splitlines() if 'Forcing branch to absolute symbol' not in line]
        if messages:print('\n'.join(messages))
    if p.returncode:raise RuntimeError(str(args))
    return p.stdout
def symbols(path):
    return {p[2]: int(p[0], 16) for line in run([ARM/'arm-none-eabi-nm', '-n', path]).splitlines()
            if len(p := line.split()) == 3}
def main():
    OUT.mkdir(exist_ok=True)
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    old = bytearray()
    for i in range(0, len(raw), 512):
        b = raw[i:i+512]
        assert struct.unpack_from('<8I', b) == (0xa324655, 0x9e5d5157, 0x2000,
            0x10000000+i//2, 256, i//512, len(raw)//512, 0xe48bff56)
        assert struct.unpack_from('<I', b, 508)[0] == 0xab16f30
        old.extend(b[32:288])
    assert len(old) == 0x36a00
    # Resolve old helper ABI from the retained exact release ELF, never from a
    # new whole-feature rebuild whose addresses could differ.
    base = ROOT/'build-features-v2_2_2-addon'
    syms = symbols(base/'features.elf')
    baseline = (base/'patched.bin').read_bytes()
    assert old[0x32600:len(baseline)] == baseline[0x32600:]
    names = ['feature_tr', 'feature_error', 'feature_keys', 'feature_release',
             'feature_page', 'feature_row', 'feature_footer', 'feature_message',
             'feature_settings', 'state_status', 'state_save', 'state_load',
             'pause_pending', 'exit_requested', 'chord_active', 'chord_latched',
             'chord_since', 'slot_status']
    link = OUT/'pause-ui.ld'
    link.write_text('''MEMORY {
 FLASH (rx) : ORIGIN = 0x10036a00, LENGTH = 0x48600
 RAM (rw) : ORIGIN = 0x2001f998, LENGTH = 0xcc
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data)==0 && SIZEOF(.bss)==0,"No new static RAM allowed")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings boundary")
''' + ''.join(f'{n} = {hex(syms[n] | (1 if syms[n]<0x20000000 else 0))};\n' for n in names))
    flags = ['-mcpu=cortex-m0plus', '-mthumb', '-Os', '-std=c11', '-fshort-enums',
             '-ffreestanding', '-fno-builtin', '-fno-jump-tables', '-ffunction-sections',
             '-fdata-sections', '-fstack-usage', '-Wall', '-Wextra', '-Werror',
             '-I'+str(ROOT/'features-addon'), '-I'+str(ROOT/'ui-addon'),
             '-I'+str(ROOT/'vendor/pico-fatfs-sd/lib/fatfs/source'),
             '-I'+str(ROOT/'vendor/pico-fatfs-sd/src/include')]
    objects = []
    for source, extra in [('features-addon/pause.c', ['-DSCARLET_PAUSE_SETTINGS',
                          '-Dfeatures_frame=pause_ui_frame']), ('pause-ui-addon/hud.c', [])]:
        obj = OUT/(Path(source).stem+'.o')
        run([ARM/'arm-none-eabi-gcc', *flags, *extra, '-c', ROOT/source, '-o', obj])
        objects.append(obj)
    # Prove opt-in source changes do not affect the older reproducible build.
    run([ARM/'arm-none-eabi-gcc', *flags, '-c', ROOT/'features-addon/pause.c',
         '-o', OUT/'historical-pause.o'])
    assert (OUT/'historical-pause.o').read_bytes() == (base/'pause.o').read_bytes(), 'Historical object changed'
    for obj, dest in [(OUT/'historical-pause.o', OUT/'historical-pause.bin'),
                      (base/'pause.o', OUT/'historical-reference.bin')]:
        run([ARM/'arm-none-eabi-objcopy', '-O', 'binary', obj, dest])
    assert (OUT/'historical-pause.bin').read_bytes() == (OUT/'historical-reference.bin').read_bytes()
    elf = OUT/'pause-ui.elf'
    run([ARM/'arm-none-eabi-gcc', '-mcpu=cortex-m0plus', '-mthumb', '-nostdlib',
         '-Wl,--gc-sections', '-Wl,--undefined=pause_ui_frame', '-Wl,--undefined=pause_ui_draw_fps',
         '-Wl,-Map='+str(OUT/'pause-ui.map'), '-T', link,
         '-T', ROOT/'features-addon/base-symbols.ld', *objects, '-o', elf])
    run([ARM/'arm-none-eabi-objcopy', '-O', 'binary', elf, OUT/'pause-ui.bin'])
    (OUT/'pause-ui.dis').write_text(run([ARM/'arm-none-eabi-objdump', '-d', elf]))
    s = symbols(elf); code = (OUT/'pause-ui.bin').read_bytes(); data = old+code
    changes = []
    def change(at, expected, new, purpose):
        p = at-0x10000000
        assert old[p:p+len(expected)] == expected and len(new)==len(expected), hex(at)
        data[p:p+len(new)] = new
        changes.append(dict(address=hex(at), before=expected.hex(), after=new.hex(), purpose=purpose))
    # Aligned Thumb tail trampolines: R0-R2 and LR preserved, R3 is caller-saved.
    # Every existing entry/caller, including PACED, reaches the new function.
    for at, before, name in [(0x10034134, 'f0b5a64b0d001a78', 'pause_ui_frame'),
                             (0x10032f38, '70b586b003ad0400', 'pause_ui_draw_fps')]:
        assert at%4==0
        change(at, bytes.fromhex(before), bytes.fromhex('004b1847')+struct.pack('<I', s[name]|1), name)
    change(0x100223a0, struct.pack('<I', 0x10036976), struct.pack('<I', 0x10000000+len(data)),
           'Image end metadata')
    allowed = set()
    for c in changes:
        p = int(c['address'],16)-0x10000000
        allowed.update(range(p,p+len(bytes.fromhex(c['before']))))
    assert {i for i,(a,b) in enumerate(zip(old,data)) if a!=b} <= allowed
    # No core/APU/pacer/scaler/worker/SPI/clock/settings/snapshot changes.
    for a,b in [(0,0x223a0),(0x223a4,0x32f38),(0x32f40,0x34134),(0x3413c,len(old))]:
        assert old[a:b] == data[a:b]
    data.extend(bytes(-len(data)%256)); (OUT/'patched.bin').write_bytes(data)
    uf2 = bytearray(); count = len(data)//256
    for i in range(count):
        uf2 += struct.pack('<8I',0xa324655,0x9e5d5157,0x2000,0x10000000+i*256,256,i,count,0xe48bff56)
        uf2 += data[i*256:(i+1)*256]+bytes(220)+struct.pack('<I',0xab16f30)
    RELEASE.write_bytes(uf2)
    report = dict(version='2.2.2-pause-settings-test', source_sha256=EXPECTED,
                  output_sha256=hashlib.sha256(uf2).hexdigest(), changes=changes,
                  appended_code=len(code), added_static_ram=0,
                  native_game_size=[160,144], displayed_game_size=[356,320],
                  black_side_rails=62, scaling='unchanged nearest-neighbour',
                  fps_hud='actual LCD completed-transfer count, bottom left, no EMU/LCD label',
                  pause_rows=['resume','save','load','settings','library'],
                  core_apu_video_pacing_clocks_settings_snapshots_byte_identical=True,
                  physical_device_test_required=True)
    RELEASE.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(run([ARM/'arm-none-eabi-size',elf])); print(json.dumps(report,indent=2))
if __name__=='__main__':main()
