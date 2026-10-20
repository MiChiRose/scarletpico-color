"""Lossless shadow + actual pinned DMA16/worker instructions, mocked peripherals."""
import hashlib,struct,random,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-video-shadow-addon'
os.environ.pop('SCARLET_VIDEO_IMAGE',None);os.environ.pop('SCARLET_VIDEO_UF2',None)
import test_video_fast_arm as v
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_R9
t=v.t
with (BUILD/'shadow.elf').open('rb') as f:
 e=ELFFile(f);s={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols()}
t.uc.mem_write(0x10000000,Path(os.environ.get('SCARLET_SHADOW_IMAGE',str(BUILD/'patched.bin'))).read_bytes());t.uc.ctl_remove_cache(0x10000000,0x10200000)
CACHE=0x20031000;allocations=[];cap=23404
def alloc(n,*_):
 allocations.append(n);p=CACHE if n<=cap else 0
 if p:t.uc.mem_write(p-16,b'\xa5'*(n+32))
 t.ret(p)
t.stubs[0x1000b8cc]=alloc
def guards(n):
 assert bytes(t.uc.mem_read(CACHE-16,16))==b'\xa5'*16
 assert bytes(t.uc.mem_read(CACHE+n,16))==b'\xa5'*16
def new_cache(bits):
 global cap
 cap=23404 if bits==4 else 9004 if bits==2 else 0
 allocations.clear();p=v.call(s['video_shadow_alloc'],46080)
 assert p==(CACHE if bits else 0)
 assert allocations==([23404] if bits==4 else [23404,9004])
 if bits:
  assert t.uc.mem_read(CACHE,1)[0]==bits
  assert not any(t.uc.mem_read(CACHE+4,360));guards(cap)
 return p
def write_pixels(p):t.uc.mem_write(v.SRC,struct.pack('<23040H',*p))
def seed():
 # Execute exact patched worker memcpy call with the real ABI, not just helper.
 t.install_stubs();t.uc.reg_write(UC_ARM_REG_SP,0x20041000)
 for reg,value in zip(t.R,[CACHE,v.SRC,46080,0]):t.uc.reg_write(reg,value)
 t.uc.emu_start(0x100089a3,0x100089a6,count=10000000)
 assert t.uc.reg_read(UC_ARM_REG_PC)==0x100089a6
 assert t.uc.reg_read(t.R[0])==CACHE
def full(p,scale=5):
 write_pixels(p);t.uc.mem_write(0x2001e260,bytes([scale]))
 v.call(v.s['video_fast_full'],v.SRC,scale);seed();v.unchanged();guards(cap)
def diff(p,scale=5):
 write_pixels(p);v.transactions.clear()
 n=v.call(v.s['video_fast_changed'],v.SRC,CACHE,scale)
 v.unchanged();guards(cap)
 w,h=(356,320) if scale==5 else (320,288)
 assert v.lcd==v.expected(p,scale,(0,0,w,h))
 return n

# Exact colours even with more than 16 colours per frame, as long as each tile
# has <=16. RGB565 palettes differ per tile, never a global colour approximation.
rng=random.Random(280926)
for bits in [4,2]:
 for scale in [5,4]:
  v.reset();new_cache(bits)
  palettes=[[rng.randrange(65536) for _ in range(1<<bits)] for _ in range(360)]
  p=[palettes[y//8*20+x//8][(y+x)%(1<<bits)] for y in range(144) for x in range(160)]
  full(p,scale);assert all(t.uc.mem_read(CACHE+4,360))
  assert diff(p,scale)==0 and not v.transactions
  for y,x in [(0,0),(12,14),(60,80),(143,159)]:
   p[y*160+x]=palettes[y//8*20+x//8][(y+x+1)%(1<<bits)]
  sent=diff(p,scale);assert 0<sent<100,sent
  assert diff(p,scale)==0
  for frame in range(4):
   # Includes many disjoint regions, neighbouring tiles, changed palette colours.
   for _ in range(35):
    tile=rng.randrange(360);y=tile//20*8+rng.randrange(8);x=tile%20*8+rng.randrange(8)
    p[y*160+x]=rng.randrange(65536)
   diff(p,scale)
  # Clear previous geometry exactly as a real mode switch would do.
  v.lcd[:]=[0]*(480*320);new_scale=4 if scale==5 else 5
  assert diff(p,new_scale)==(92160 if new_scale==4 else 113920)
print('PASS SHADOW lossless: 4/16-colour tile caches, per-tile RGB565 palettes, full-height/2x geometry, zero unchanged transfers, sparse <100-pixel updates, random edits, colour-overflow and scale-change redraws, cache guards')

# Every tile exceeds the palette: fallback must send accurate original colours
# on EVERY frame, including transitions back into a cacheable image.
for bits in [4,2]:
 v.reset();new_cache(bits)
 p=[(y*160+x)&65535 for y in range(144) for x in range(160)]
 full(p);assert not any(t.uc.mem_read(CACHE+4,360))
 assert diff(p)==113920
 p=[0x10c1]*23040;assert diff(p)==113920
 assert all(t.uc.mem_read(CACHE+4,360))
 assert diff(p)==0
print('PASS SHADOW palette overflow: exact uncompressed tile redraw, no dropped colours/hashes, recovers caching when colours fit')

# No cache possible: original worker's null check retains the unmodified full
# frame branch. On DMA failure, existing whole-region redraw remains exact.
v.reset();assert not new_cache(0)
for fault in ['error','timeout']:
 v.reset();new_cache(4);p=[1]*23040;full(p)
 v.fault=fault;p[1000]=2;assert diff(p)>0
 assert t.uc.mem_read(v.s['channel_plus_one'],1)==b'\xff'
print('PASS SHADOW low-memory and DMA-error fallbacks')

# Execute multiple actual worker iterations including first-copy, differential
# branch, completed counter and last_presented pointer, not isolated wrappers.
v.reset();new_cache(4);p=[0x1234]*23040;write_pixels(p)
t.uc.mem_write(0x2001e260,b'\5');t.write32(0x2001db4c,CACHE)
t.write32(0x2001db44,v.SRC);t.write32(0x2001db48,59)
t.uc.mem_write(0x2001e261,b'\0');t.uc.mem_write(0x2001e25e,b'\1')
t.write32(0x200035d4,0);done=0;totals=[]
def atomic_add(p,n,*_):
 old=t.read32(p);t.write32(p,old+n);t.ret(old)
t.stubs[0x1000b960]=atomic_add
def iteration(u,a,size,data):
 global done
 totals.append(sum(len(x[1])//2 for x in v.transactions));v.transactions.clear();done+=1
 if done==3:u.emu_stop();return
 if done==2:p[5*160+6]^=1;write_pixels(p)
 # Original atomic clear+SEV+branch still execute, then next job is published
 # at the worker loop entry by the hook below.
def publish(u,a,size,data):t.uc.mem_write(0x2001e25e,b'\1')
h=t.uc.hook_add(UC_HOOK_CODE,iteration,begin=0x1000897e,end=0x1000897e)
h2=t.uc.hook_add(UC_HOOK_CODE,publish,begin=0x100088f2,end=0x100088f2)
t.install_stubs();t.uc.reg_write(UC_ARM_REG_SP,0x20041000)
t.uc.emu_start(0x100088b9,0x10008928,count=30000000)
t.uc.hook_del(h);t.uc.hook_del(h2)
assert done==3 and totals[0]==113920 and totals[1]==0 and 0<totals[2]<=9,totals
assert t.read32(0x200035d4)==2
assert v.lcd==v.expected(p,5,(0,0,356,320));guards(cap)
print('PASS actual worker: full seed -> unchanged zero traffic -> small dirty region; completed LCD count 2, not inflated for unchanged frame')

v.prints.clear();t.uc.mem_write(0x2003e000,b'PERF TEST\0')
t.write32(0x2001dcb0,8192);t.write32(0x2001d738,0x20038000)
assert v.call(s['video_shadow_perf'],0x2003e000,11,59,23,11000,40000)==123
assert v.prints[0][1][:5]==[11,59,23,11000,40000]
assert v.prints[-1][0].startswith('VSHADOW')
assert v.prints[-1][1][:4]==[4,23404,8192,0x20038000]
print('PASS SHADOW telemetry: original PERF ABI + coherent VIDEO16 + cache type/size and actual save RAM')
print('STACK_BYTES_OBSERVED',0x20041000-v.minimum_sp)
print('FIRMWARE_SHA256',hashlib.sha256(Path(os.environ.get('SCARLET_SHADOW_UF2',str(ROOT/'releases/scarletpico-v2_2_2-video16-SHADOW-TEST.uf2'))).read_bytes()).hexdigest())
