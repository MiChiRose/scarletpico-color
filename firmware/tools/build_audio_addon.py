#!/usr/bin/env python3
"""Compile an audio-only extension without rebuilding the original firmware.

Uses the existing SDK build for headers. Recovered original SDK entry points
are frozen in base-symbols.ld and valid only for the SHA-pinned input.
"""
from pathlib import Path
import re
import shlex
import subprocess
import sys
from uf2_audio_patch import read_uf2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build-audio-addon'
ARM = Path('/tmp/arm-gnu/bin')

def run(args):
    return subprocess.check_output([str(a) for a in args], text=True)

def symbols(path):
    result = {}
    for line in run([ARM/'arm-none-eabi-nm', '-S', '-n', path]).splitlines():
        p = line.split()
        if len(p) == 4:
            result[p[3]] = (int(p[0], 16), int(p[1], 16), p[2])
        elif len(p) == 3:
            result[p[2]] = (int(p[0], 16), 0, p[1])
    return result

def build(source):
    OUT.mkdir(exist_ok=True)
    original = read_uf2(source)
    (OUT/'original.bin').write_bytes(original)
    commands = run(['/opt/homebrew/bin/ninja', '-C', ROOT/'build', '-t', 'commands'])
    command = next(c for c in commands.splitlines() if '/src/emulator.c' in c and ' -c ' in c)
    tokens = shlex.split(command)
    includes = []
    for i, token in enumerate(tokens):
        if token.startswith('-I') or token.startswith('-D'):
            includes.append(token)
        if token == '-isystem':
            includes += [token, tokens[i+1]]
    apu = ROOT/'vendor/Peanut-GB-CGB/examples/sdl2/minigb_apu'
    common = ['-mcpu=cortex-m0plus', '-mthumb', '-O3', '-std=c11', '-DNDEBUG',
              '-ffunction-sections', '-fdata-sections', '-ffreestanding', '-fno-builtin',
              '-fstack-usage', '-Wall', '-Wextra', '-I'+str(OUT), '-I'+str(apu)]
    run(['/tmp/pico-sdk-tools/pioasm/pioasm', '-o', 'c-sdk', ROOT/'src/audio_i2s.pio', OUT/'audio_i2s.pio.h'])
    objects = []
    for src in [ROOT/'src/audio_output.c', ROOT/'audio-addon/addon.c', apu/'minigb_apu.c']:
        obj = OUT/(src.stem+'.o')
        run([ARM/'arm-none-eabi-gcc', *includes, *common, '-c', src, '-o', obj])
        objects.append(obj)
    undefined = set()
    defined = set()
    for obj in objects:
        undefined.update(line.split()[-1] for line in run([ARM/'arm-none-eabi-nm', '-u', obj]).splitlines())
        defined.update(symbols(obj))
    undefined -= defined
    imports = ROOT/'audio-addon/base-symbols.ld'
    mapped = set(re.findall(r'^(\w+) = 0x[0-9a-f]+;', imports.read_text(), re.M))
    assert undefined <= mapped, f'Unmapped imports: {undefined-mapped}'
    elf = OUT/'addon.elf'
    run([ARM/'arm-none-eabi-gcc', '-mcpu=cortex-m0plus', '-mthumb', '-nostdlib',
         '-Wl,--gc-sections', '-Wl,--undefined=addon_frame', '-Wl,--undefined=addon_stop',
         '-Wl,--undefined=audio_read', '-Wl,--undefined=audio_write',
         '-Wl,-Map='+str(OUT/'addon.map'), '-T', ROOT/'audio-addon/addon.ld',
         '-T', imports, *objects, '-o', elf])
    run([ARM/'arm-none-eabi-objcopy', '-O', 'binary', elf, OUT/'addon.bin'])
    (OUT/'addon.dis').write_text(run([ARM/'arm-none-eabi-objdump', '-d', elf]))
    print(run([ARM/'arm-none-eabi-size', elf]))

if __name__ == '__main__':
    build(sys.argv[1])
