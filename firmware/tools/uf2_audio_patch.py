#!/usr/bin/env python3
"""Inspect/build the sound-only addon for one SHA-pinned v0.9 image."""
import hashlib
import pathlib
import struct
import sys
import json
import subprocess

BASE = 0x10000000
EXPECTED = '6d8dda2c26f1f909d47b913bcf5ad6caa92777a89fa3842916fbfc8edb88aad2'

def read_uf2(path):
    raw = pathlib.Path(path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED, 'Wrong source firmware'
    pieces = {}
    for i in range(0, len(raw), 512):
        b = raw[i:i+512]
        a, magic, flags, address, length, num, total, family = struct.unpack_from('<8I', b)
        assert (a, magic, flags, length, num, total, family) == (0x0a324655, 0x9e5d5157, 0x2000, 256, i//512, len(raw)//512, 0xe48bff56)
        assert struct.unpack_from('<I', b, 508)[0] == 0x0ab16f30
        assert address not in pieces
        pieces[address] = b[32:32+length]
    assert sorted(pieces) == list(range(BASE, BASE + len(pieces)*256, 256))
    return b''.join(pieces[a] for a in sorted(pieces))

def bl(address, target):
    delta = (target & ~1) - address - 4
    assert delta % 2 == 0 and -0x400000 <= delta < 0x400000
    return struct.pack('<HH', 0xf000 | ((delta >> 12) & 0x7ff), 0xf800 | ((delta >> 1) & 0x7ff))

def branch(address, target):
    delta = target - address - 4
    assert delta % 2 == 0 and -2048 <= delta <= 2046
    return struct.pack('<H', 0xe000 | ((delta >> 1) & 0x7ff))

def patch(source, addon_dir, output):
    addon_dir = pathlib.Path(addon_dir)
    old = read_uf2(source)
    code = (addon_dir/'addon.bin').read_bytes()
    assert len(old) == 0x2e800
    data = bytearray(old + code)
    assert len(data) < 0x80000, 'ROM cache overlap'
    syms = {}
    nm = subprocess.check_output(['/tmp/arm-gnu/bin/arm-none-eabi-nm', '-n', str(addon_dir/'addon.elf')], text=True)
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) == 3: syms[parts[2]] = int(parts[0], 16)
    changes = []
    def change(address, expected, replacement, purpose):
        index = address - BASE
        assert len(expected) == len(replacement)
        assert old[index:index+len(expected)] == expected, f'Mismatched hook at {address:#x}'
        data[index:index+len(expected)] = replacement
        changes.append({'address':hex(address), 'length':len(expected), 'before':expected.hex(),
                        'after':replacement.hex(), 'purpose':purpose})
    read_hook = struct.pack('<H', 0x4608) + bl(0x100027cc, syms['audio_read']) + struct.pack('<H', 0xbd10)
    write_hook = struct.pack('<HH', 0x4608, 0x4611) + bl(0x100027d6, syms['audio_write']) + branch(0x100027da, 0x1000289c)
    change(0x100027ca, bytes.fromhex('174b40189c46274b60440078cb5c1843fae6'), read_hook+write_hook,
           'APU register read/write dispatch only; non-audio memory paths unchanged')
    change(0x10002974, bytes.fromhex('54e2'), branch(0x10002974, 0x100027d2), 'APU-only write branch')
    change(0x1000809c, bl(0x1000809c, 0x10007070), bl(0x1000809c, syms['addon_frame']),
           'Call original frame, then generate PCM, without changing render choice/pacing')
    for address in [0x10007cd0, 0x100082ac, 0x100082fc]:
        change(address, bl(address, 0x10008ce4), bl(address, syms['addon_stop']),
               'Stop audio before original video-stop/menu/flash transition')
    end = syms['__addon_bss_end']
    assert syms['__addon_bss_start'] == 0x2001e264 and end <= 0x2001fa64 and end % 8 == 0
    for address in [0x10000270, 0x1000d124]:
        change(address, struct.pack('<I',0x2001e264), struct.pack('<I',end),
               'Zero audio BSS at boot / reserve it outside original heap')
    change(0x100223a0, struct.pack('<I',0x1002d950), struct.pack('<I',BASE+len(data)),
           'Report complete firmware size to picotool, including addon')
    allowed = set()
    for c in changes:
        i = int(c['address'],16)-BASE
        allowed.update(range(i,i+c['length']))
    changed = {i for i,(a,b) in enumerate(zip(old,data)) if a != b}
    assert changed <= allowed
    assert data[0x2da00:0x2e800] == old[0x2da00:0x2e800], 'Original custom menu changed'
    # Every byte outside audited audio hook/memory metadata ranges is identical,
    # including all CPU/LCD/SD frequencies, input, scaling and menu assets.
    data.extend(b'\x00' * (-len(data) % 256))
    total = len(data)//256
    uf2 = bytearray()
    for i in range(total):
        header = struct.pack('<8I',0x0a324655,0x9e5d5157,0x2000,BASE+i*256,256,i,total,0xe48bff56)
        uf2 += header + data[i*256:(i+1)*256] + bytes(220) + struct.pack('<I',0x0ab16f30)
    output = pathlib.Path(output)
    output.write_bytes(uf2)
    (addon_dir/'patched.bin').write_bytes(data)
    report = {'source_sha256':EXPECTED, 'output_sha256':hashlib.sha256(uf2).hexdigest(),
              'modified_original_bytes':len(changed), 'audio_ram_bytes':end-0x2001e264,
              'audio_flash_bytes':len(code), 'volume_percent':50, 'pcm_sample_rate':16000,
              'original_menu_byte_identical':True, 'changes':changes}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    if len(sys.argv) == 3:
        source, target = sys.argv[1:3]
        data = read_uf2(source)
        pathlib.Path(target).write_bytes(data)
        print(f'Validated original UF2: {len(data)} bytes, end {BASE+len(data):#x}')
    else:
        patch(*sys.argv[1:4])
