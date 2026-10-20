"""Execute 2x startup/resume/diagnostic instructions and all VIDEO16 tests."""
import os,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['SCARLET_VIDEO_IMAGE']=str(ROOT/'build-video-integer-addon/patched.bin')
os.environ['SCARLET_VIDEO_UF2']=str(ROOT/'releases/scarletpico-v2_2_2-video16-2X-TEST.uf2')
import test_video_fast_arm as v
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_PC
t=v.t
started=[]
t.stubs[0x10008af0]=lambda scale,*_:(started.append(scale),t.ret(1))
t.install_stubs()
for at in [0x10007fa2,0x1003439a]:
 t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
 t.uc.emu_start(at|1,at+6,count=1000)
 assert t.uc.reg_read(UC_ARM_REG_PC)==at+6
assert started==[4,4]
t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
t.uc.emu_start(0x10008335,0x1000833a,count=10000)
assert v.cstr(t.uc.reg_read(t.R[0]))=='LARGE 320X288'

v.reset();v.call(v.s['video_fast_full'],v.SRC,4);v.unchanged()
assert len(v.transactions)==1
assert v.transactions[0][0]==(80,16,399,303)
assert len(v.transactions[0][1])==184320
for y in range(144):
 for x in range(160):
  p=v.pixels[y*160+x]
  assert all(v.lcd[(16+y*2+dy)*480+80+x*2+dx]==p for dx in [0,1] for dy in [0,1])
assert all(not p or 80<=i%480<400 and 16<=i//480<304 for i,p in enumerate(v.lcd))
print('PASS exact 2x: original launch/resume select 4, truthful PERF size, each RGB565 pixel is an identical 2x2 block, 320x288 centred, black margins, exactly 184320 data bytes')
