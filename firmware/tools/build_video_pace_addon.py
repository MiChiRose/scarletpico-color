#!/usr/bin/env python3
"""SHA-pinned SHADOW + bounded optional rendering. Never flashes a device."""
from pathlib import Path
import hashlib, json, os, struct, subprocess
from uf2_audio_patch import bl
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build-video-pace-addon'
SOURCE = ROOT / 'releases/scarletpico-v2_2_2-video16-SHADOW-TEST.uf2'
EXPECTED = '477a17199b835994c46f6dab2dd6eccb14f757836a6521821c945c628fea1084'
RELEASE = ROOT / 'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2'
ARM = Path(os.environ.get('ARM_GCC_BIN', '/tmp/arm-gnu/bin'))
def run(args):
    return subprocess.check_output([str(x) for x in args], text=True)
def main():
    OUT.mkdir(exist_ok=True)
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    old = bytearray()
    for i in range(0, len(raw), 512):
        block = raw[i:i+512]
        assert struct.unpack_from('<8I', block) == (0xa324655, 0x9e5d5157, 0x2000,
            0x10000000+i//2, 256, i//512, len(raw)//512, 0xe48bff56)
        assert struct.unpack_from('<I', block, 508)[0] == 0xab16f30
        old.extend(block[32:288])
    assert len(old) == 0x36500
    link = OUT / 'pace.ld'
    link.write_text('''MEMORY {
 FLASH (rx) : ORIGIN = 0x10036500, LENGTH = 0x48a00
 RAM (rw) : ORIGIN = 0x2001f960, LENGTH = 0x104
}
SECTIONS {
 .text : { *(.text*) *(.rodata*) } > FLASH
 .data : { *(.data*) } > RAM
 .bss (NOLOAD) : { *(.bss*) *(COMMON) . = ALIGN(8); __pace_bss_end = .; } > RAM
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
original_features_frame = 0x10034135;
original_video_ready = 0x10008bd5;
original_audio_submit = 0x1002ec39;
sleep_us = 0x10009b69;
previous_perf = 0x10036429;
original_printf = 0x1000d545;
time_us_64 = 0x10009e3d;
clock_get_hz = 0x1000a08d;
__aeabi_uidiv = 0x1000aab1;
ASSERT(SIZEOF(.data)==0,"No initialized data")
ASSERT(__pace_bss_end<=0x2001fa64,"RAM budget")
ASSERT(ADDR(.text)+SIZEOF(.text)<0x1007f000,"Settings boundary")
''')
    objects = []
    for name in ['video_pace.c', 'video_pace.S']:
        obj = OUT / (name + '.o')
        run([ARM/'arm-none-eabi-gcc', '-mcpu=cortex-m0plus', '-mthumb', '-O3',
             '-ffreestanding', '-fno-builtin', '-fno-jump-tables', '-fdata-sections',
             '-ffunction-sections', '-fstack-usage', '-Wall', '-Wextra', '-Werror',
             '-c', ROOT/'video-fast-addon'/name, '-o', obj])
        objects.append(obj)
    elf = OUT / 'pace.elf'
    run([ARM/'arm-none-eabi-gcc', '-mcpu=cortex-m0plus', '-mthumb', '-nostdlib',
         '-Wl,--gc-sections', *['-Wl,--undefined='+n for n in
         ['video_pace_entry', 'video_pace_ready', 'video_pace_perf', 'video_pace_audio_submit']],
         '-Wl,-Map='+str(OUT/'pace.map'), '-T', link, *objects, '-o', elf])
    run([ARM/'arm-none-eabi-objcopy', '-O', 'binary', elf, OUT/'pace.bin'])
    (OUT/'pace.dis').write_text(run([ARM/'arm-none-eabi-objdump', '-d', elf]))
    sym = {p[2]: int(p[0], 16) for line in run([ARM/'arm-none-eabi-nm', '-n', elf]).splitlines()
           if len(p := line.split()) == 3}
    code = (OUT/'pace.bin').read_bytes()
    data = old + code
    changes = []
    def change(at, expected, new, reason):
        p = at - 0x10000000
        assert len(new) == len(expected) and old[p:p+len(expected)] == expected, hex(at)
        data[p:p+len(new)] = new
        changes.append(dict(address=hex(at), before=expected.hex(), after=new.hex(), purpose=reason))
    for at, target, name in [(0x1000809c, 0x10034134, 'video_pace_entry'),
                             (0x100080cc, 0x10008bd4, 'video_pace_ready'),
                             (0x10008374, 0x10036428, 'video_pace_perf'),
                             (0x1002ee40, 0x1002ec38, 'video_pace_audio_submit')]:
        change(at, bl(at, target), bl(at, sym[name]), name)
    change(0x100080a0, bytes.fromhex('071e'), bytes.fromhex('0028'),
           'Preserve explicit R7 frame_waiting; compare success without setting it')
    for at in [0x10000270, 0x1000d124]:
        change(at, struct.pack('<I', 0x2001f960), struct.pack('<I', sym['__pace_bss_end']),
               'Zero pacing BSS at boot and exclude it from heap')
    change(0x100223a0, struct.pack('<I', 0x100364c0), struct.pack('<I', 0x10000000+len(data)),
           'Image end metadata')
    allowed = set()
    for c in changes:
        p = int(c['address'], 16) - 0x10000000
        allowed.update(range(p, p+len(bytes.fromhex(c['before']))))
    assert {i for i, (a, b) in enumerate(zip(old, data)) if a != b} <= allowed
    for a, b in [(0x23f8, 0x7164), (0x88b8, 0x8d10), (0x2e800, 0x2ee40),
                 (0x2ee44, len(old))]:
        assert old[a:b] == data[a:b], 'Core/audio/video/UI/features bytes changed'
    data.extend(bytes(-len(data) % 256))
    (OUT/'patched.bin').write_bytes(data)
    uf2 = bytearray()
    count = len(data)//256
    for i in range(count):
        uf2 += struct.pack('<8I', 0xa324655, 0x9e5d5157, 0x2000, 0x10000000+i*256,
                          256, i, count, 0xe48bff56)
        uf2 += data[i*256:(i+1)*256] + bytes(220) + struct.pack('<I', 0xab16f30)
    RELEASE.write_bytes(uf2)
    report = dict(version='2.2.2-video16-paced-test', source_sha256=EXPECTED,
                  output_sha256=hashlib.sha256(uf2).hexdigest(), changes=changes,
                  appended_code=len(code), added_static_ram=sym['__pace_bss_end']-0x2001f960,
                  full_height_356x320=True, fixed_30_fps_cap=False,
                  core_apu_ui_video_clocks_byte_identical=True,
                  changes_optional_render_scheduling_and_bounded_audio_enqueue=True,
                  physical_performance_and_sound_not_yet_verified=True)
    RELEASE.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(run([ARM/'arm-none-eabi-size', elf]))
    print(json.dumps(report, indent=2))
if __name__ == '__main__':
    main()
