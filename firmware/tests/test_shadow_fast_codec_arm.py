"""Differential old/new ARM codec and executed-instruction comparison.
LCD/SPI and divider helper are mocked. Counts are NOT RP2040 cycles or FPS.
No raw/native ROM data is needed or exported. No device access.
"""
from pathlib import Path
import hashlib,struct,json,random
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_BLOCK,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-shadow-fast-addon'
raw=(BUILD/'patched.bin').read_bytes()
def syms(path):
 with path.open('rb') as stream:
  e=ELFFile(stream);return {s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
old=syms(ROOT/'build-video-shadow-addon/shadow.elf');new=syms(BUILD/'shadow-fast.elf')
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0x10000000,0x200000);u.mem_write(0x10000000,raw)
u.mem_map(0x20000000,0x42000)
R=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
SAVED=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
SRC=0x20024000;CACHE=0x20031000;SP=0x20041000;END=0x1007fff0
regions=[];instructions=0;divisions=0;min_sp=SP
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);blocks={}
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
def ret(v=0):u.reg_write(R[0],v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def hook(u,a,size,_):
 global divisions
 if a==0x1000aab0:
  x,y=[u.reg_read(r) for r in R[:2]];assert y
  divisions+=1;u.reg_write(R[1],x%y);ret(x//y)
 elif a==0x10000c0c:ret()
 elif a==0x100353a4:
  p,scale,left,top=[u.reg_read(r) for r in R];sp=u.reg_read(UC_ARM_REG_SP)
  right,bottom=word(sp),word(sp+4)
  assert p==SRC and 0<=left<right<=356 and 0<=top<bottom<=320
  regions.append((scale,left,top,right,bottom));ret()
 elif a==0x1000157c:
  assert u.reg_read(R[0])==SRC
  scale=u.reg_read(R[1]);w,h=(356,320) if scale==5 else (320,288)
  regions.append((scale,0,0,w,h));ret()
for a in [0x1000aab0,0x10000c0c,0x100353a4,0x1000157c]:
 u.hook_add(UC_HOOK_CODE,hook,begin=a,end=a)
def block(u,a,size,_):
 global instructions
 if not (0x10035a00<=a<0x10036428 or 0x10037800<=a<0x10000000+len(raw)):return
 key=(a,size)
 if key not in blocks:blocks[key]=len(list(md.disasm(bytes(u.mem_read(a,size)),a)))
 instructions+=blocks[key]
u.hook_add(UC_HOOK_BLOCK,block)
def memory(u,access,a,size,value,_):
 global min_sp
 sp=u.reg_read(UC_ARM_REG_SP);min_sp=min(min_sp,sp)
 assert sp>=SP-4096
 assert a+size<=SRC or a>=SRC+46080,'Source framebuffer mutated'
u.hook_add(UC_HOOK_MEM_WRITE,memory)
def call(address,*args):
 global instructions,divisions
 instructions=divisions=0;regions.clear()
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,END|1)
 for i,r in enumerate(R):u.reg_write(r,args[i] if i<len(args) else 0)
 for i,r in enumerate(SAVED):u.reg_write(r,0x12340000+i)
 u.emu_start(address|1,END,count=10000000)
 assert u.reg_read(UC_ARM_REG_PC)==END and u.reg_read(UC_ARM_REG_SP)==SP
 assert all(u.reg_read(r)==0x12340000+i for i,r in enumerate(SAVED))
 return u.reg_read(R[0]),instructions,divisions,list(regions)
def cache_size(bits):return 364+360*(64 if bits==4 else 24)
def blank(bits):return bytes([bits,0,0,0])+bytes(360)+b'\xa5'*(cache_size(bits)-364)
def set_cache(data):u.mem_write(CACHE-16,b'\x5a'*16+data+b'\x5a'*16)
def get_cache(bits):
 n=cache_size(bits)
 assert u.mem_read(CACHE-16,16)==b'\x5a'*16 and u.mem_read(CACHE+n,16)==b'\x5a'*16
 return bytes(u.mem_read(CACHE,n))
def src(p):u.mem_write(SRC,struct.pack('<23040H',*p))
def verify(cache,p,bits):
 stride=64 if bits==4 else 24;limit=1<<bits
 for tile in range(360):
  x0=tile%20*8;y0=tile//20*8
  expected=[p[(y0+y)*160+x0+x] for y in range(8) for x in range(8)]
  assert bool(cache[4+tile])==(len(set(expected))<=limit)
  if not cache[4+tile]:continue
  data=cache[364+tile*stride:364+(tile+1)*stride]
  palette=struct.unpack('<'+str(limit)+'H',data[:limit*2]);packed=data[limit*2:]
  actual=[palette[(packed[k*bits//8]>>((k*bits)&7))&(limit-1)] for k in range(64)]
  assert actual==expected,(bits,tile)
u.mem_write(0x2001e260,b'\x05')
rng=random.Random(280926);report=[]
for bits in [4,2]:
 palette=[0x1030,0xeeee,0x5522,0x8811]
 base=[palette[(x//4+y//4)%4] for y in range(144) for x in range(160)]
 sprite=base.copy()
 for y in range(55,70):
  for x in range(65,80):sprite[y*160+x]=palette[(x+y)%4]
 scroll=[base[y*160+(x+1)%160] for y in range(144) for x in range(160)]
 noisy=[rng.randrange(65536) for _ in range(23040)]
 scattered=base.copy()
 for _ in range(100):scattered[rng.randrange(23040)]=rng.randrange(65536)
 frames=[('unchanged',base),('sprite',sprite),('scroll',scroll),('scattered',scattered),('overflow',noisy)]
 seed_caches=[];seed_stats=[]
 for symbols,name in [(old,'video_shadow_seed'),(new,'video_shadow_fast_seed')]:
  src(base);set_cache(blank(bits));result=call(symbols[name],CACHE,SRC,46080)
  assert result[0]==CACHE;seed_caches.append(get_cache(bits));seed_stats.append(result[1:3])
  verify(seed_caches[-1],base,bits)
 assert seed_caches[0]==seed_caches[1]
 for label,pixels in frames:
  outputs=[];caches=[]
  for i,(symbols,name) in enumerate([(old,'video_shadow_changed'),(new,'video_shadow_fast_changed')]):
   src(pixels);set_cache(seed_caches[i]);outputs.append(call(symbols[name],SRC,CACHE,5))
   caches.append(get_cache(bits));verify(caches[-1],pixels,bits)
  assert outputs[0][0]==outputs[1][0] and outputs[0][3]==outputs[1][3],(bits,label,outputs)
  entry=dict(bits=bits,scene=label,old_instructions=outputs[0][1],new_instructions=outputs[1][1],
             old_divisions=outputs[0][2],new_divisions=outputs[1][2],pixels_sent=outputs[1][0],
             instruction_reduction=round(1-outputs[1][1]/outputs[0][1],4))
  report.append(entry);print('CODEC',json.dumps(entry),flush=True)
 # Feed several changing frames through each implementation, preserving its
 # own cache (including overflow->cacheable recovery and dirty bounds).
 for frame in range(8):
  pixels=[rng.randrange(1<<bits) if frame%3 else rng.randrange(65536) for _ in range(23040)]
  outputs=[]
  for i,(symbols,name) in enumerate([(old,'video_shadow_changed'),(new,'video_shadow_fast_changed')]):
   src(pixels);set_cache(caches[i]);outputs.append(call(symbols[name],SRC,CACHE,5))
   caches[i]=get_cache(bits);verify(caches[i],pixels,bits)
  assert outputs[0][0]==outputs[1][0] and outputs[0][3]==outputs[1][3]
 print('SEED',bits,'old/new instructions+divider calls',seed_stats,flush=True)
 assert seed_stats[1][0]<seed_stats[0][0]
assert all(x['instruction_reduction']>0 for x in report if x['scene']!='overflow')
(BUILD/'codec-benchmark.json').write_text(json.dumps(dict(unit='executed ARM codec instructions, NOT cycles/FPS',
    excludes='SPI/DMA, SDK division helper and memory-bus timing',results=report,
    output_sha256=hashlib.sha256((ROOT/'releases/scarletpico-v2_2_2-SHADOW-FAST-TEST.uf2').read_bytes()).hexdigest()),indent=2)+'\n')
print('PASS differential codec: exact regions/pixels, both cache modes, first-seen palette order, multi-frame/overflow recovery, cache guards, immutable source, stack and ABI')
print('CODEC_STACK_BYTES',SP-min_sp)
print('FIRMWARE_SHA256',hashlib.sha256((ROOT/'releases/scarletpico-v2_2_2-SHADOW-FAST-TEST.uf2').read_bytes()).hexdigest())
