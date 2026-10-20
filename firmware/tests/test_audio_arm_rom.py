"""Smoke-test the real ARM emulator and sound hooks with a local ROM.
SDK/memory-allocation stubs are the only host substitutions; no LCD device.
"""
import test_audio_arm as t
from pathlib import Path
import sys
import struct

t.stubs.pop(t.sym['original_emulator_frame'] & ~1)
heap=0x20020000
def malloc(size,*_):
    global heap
    out=heap; heap=(heap+size+7)&~7
    assert heap<0x20040000
    t.ret(out)
t.stubs[0x1000b8cc]=malloc
t.stubs[0x1000b918]=lambda *_:t.ret()
rom=Path(sys.argv[1]).read_bytes()
t.uc.mem_write(0x10081000,rom)
t.call(t.sym['addon_stop'])
assert t.call(0x10006eac,0x10081000,len(rom),0)==1,'Original ARM emulator_load failed'
nonzero=0
for i in range(120):
    assert t.call(t.sym['addon_frame'],0xff if i<60 else 0xf7,i%2)==1,f'Frame {i}'
    nonzero+=sum(x!=0 for x in struct.unpack('<536h',t.uc.mem_read(t.sym['pcm'],1072)))
    # Consume two halves/frame, at a simulated rate; no claim about wall FPS.
    t.write32(0x5000041c,(1<<2)|(1<<3))
    t.call(t.irq_handler)
    t.write32(0x5000041c,0)
assert nonzero>1000
t.call(t.sym['addon_stop'])
print(f'PASS actual patched ARM ROM: {Path(sys.argv[1]).name}, 120 frames, nonzero PCM values={nonzero}')
