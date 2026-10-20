"""Probe the pinned image's real allocator/video startup, no hardware writes."""
import os, struct, hashlib
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
ROOT=Path(__file__).resolve().parents[1]
raw=Path(os.environ.get('SCARLET_HEAP_IMAGE',str(ROOT/'build-video-shadow-addon/patched.bin'))).read_bytes()
compact=raw[0x8b24:0x8b28]!=bytes.fromhex('02f0d2fe')
insn=next(Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[0x8b24:0x8b28],0x10008b24))
assert insn.mnemonic=='bl'
optional_alloc=int(insn.op_str.lstrip('#'),16)
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0x10000000,0x200000);u.mem_write(0x10000000,raw)
u.mem_map(0x20000000,0x42000)
R=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
END=0x1007fff0
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def reset():
 u.mem_write(0x20000000,bytes(0x42000))
 # Exact CRT .data copy source/destination/end, not another build's ELF.
 source,dest,end=struct.unpack_from('<III',raw,0x238)
 u.mem_write(dest,raw[source-0x10000000:source-0x10000000+end-dest])
def ret(v=None):
 if v is not None:u.reg_write(R[0],v)
 u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def hook(u,a,size,data):
 if a==0x1000d0f4 and os.environ.get('SCARLET_HEAP_DEBUG'):print('SBRK',hex(u.reg_read(R[0])),'FROM',hex(word(0x2001d738)))
 if a in (0x10020460,0x10020340,0x1001c494,0x1001c4a4,0x1000f94c):ret()
 if a==0x1000b948:
  p,v,n=[u.reg_read(r) for r in R[:3]];u.mem_write(p,bytes([v&255])*n);ret(p)
u.hook_add(UC_HOOK_CODE,hook)
def call(a,*args):
 u.reg_write(UC_ARM_REG_SP,0x20042000);u.reg_write(UC_ARM_REG_LR,END|1)
 for i,r in enumerate(R):u.reg_write(r,args[i] if i<len(args) else 0)
 u.emu_start(a|1,END,count=2000000)
 assert u.reg_read(UC_ARM_REG_PC)==END,hex(u.reg_read(UC_ARM_REG_PC))
 return u.reg_read(R[0])
for save in [0,8192,32768,65536,80000,100000]:
 reset()
 ram=call(0x1000b8cc,save) if save else 0
 if save:assert ram
 result=call(0x10008af0,5)
 previous=word(0x2001db4c);producer=word(0x200035bc)
 if compact:
  expected=4 if save<=32768 else 2 if save==65536 else 0
  assert (u.mem_read(previous,1)[0] if previous else 0)==expected,(save,hex(previous))
  assert result==(save<100000)
  assert u.mem_read(0x2001e260,1)[0]==(5 if result else 0)
 print('SAVE',save,'START',result,'BUFFER1',hex(word(0x200035bc)),
       'PREVIOUS',hex(previous),'BITS',u.mem_read(previous,1)[0] if compact and previous else 0,
       'HEAP_END',hex(word(0x2001d738)))
 initial=(producer,previous,word(0x2001d738))
 # Exact free() path used by stop, then reallocate repeatedly: no surrogate
 # allocator, and no leak of either producer or compact comparison buffer.
 for _ in range(5):
  if previous:call(0x1000b918,previous)
  if producer:call(0x1000b918,producer)
  producer=call(0x1000b8cc,46080)
  # Execute the real optional allocation call site only if producer succeeded.
  if producer:
   previous=call(optional_alloc,46080)
  else:previous=0
  if os.environ.get('SCARLET_HEAP_DEBUG'):print('REUSE',_,hex(producer),hex(previous),'END',hex(word(0x2001d738)))
  if compact:assert (u.mem_read(previous,1)[0] if previous else 0)==expected
  assert (producer,previous,word(0x2001d738))==initial,'Allocation leak or unexpected growth'
 if previous:call(0x1000b918,previous)
 if producer:call(0x1000b918,producer)
 # Cartridge SRAM remains owned by the emulator during pause/video stop.
 # The next reset isolates this allocation-pressure scenario.
print('PASS real pinned malloc/free: low-memory 16 -> 4-colour -> null fallback; producer OOM; repeated video release/reallocate without leaks')
print('IMAGE_SHA256',hashlib.sha256(raw).hexdigest())
