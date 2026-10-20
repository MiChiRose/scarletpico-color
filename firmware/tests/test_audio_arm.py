"""Execute the actual patched Thumb code; hardware is explicitly mocked.
Not a physical MAX98357A/FPS test. Requires Unicorn/Capstone/pyelftools.
"""
from pathlib import Path
import json
import re
import struct
import sys
import os
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import *
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-audio-addon'
raw=Path(os.environ.get('SCARLET_TEST_FIRMWARE',str(OUT/'patched.bin'))).read_bytes()
with (OUT/'addon.elf').open('rb') as f:
    elf=ELFFile(f)
    sym={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
uc.mem_map(0x10000000,0x200000)
uc.mem_write(0x10000000,raw)
uc.mem_map(0x20000000,0x50000)
if os.environ.get('SCARLET_TEST_UI_ELF'):
    with open(os.environ['SCARLET_TEST_UI_ELF'],'rb') as f:
        extra=ELFFile(f)
        ui_syms={s.name:s['st_value'] for s in extra.get_section_by_name('.symtab').iter_symbols()}
    uc.mem_write(ui_syms['ui_volume'],b'\x32')  # Boot UI's default, without mocking the mixer hook.
for address,size in [(0x50000000,0x4000),(0x50200000,0x4000),(0xd0000000,0x1000),(0xe000e000,0x2000)]:
    uc.mem_map(address,size)

R=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
CALLEE=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
RETURN=0x1007fff0
def read32(a): return struct.unpack('<I',uc.mem_read(a,4))[0]
def write32(a,x): uc.mem_write(a,struct.pack('<I',x&0xffffffff))
def signed(x): return x if x<0x80000000 else x-0x100000000
def ret(value=None):
    if value is not None: uc.reg_write(R[0],value&0xffffffff)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
stubs={}
def stub(name,fn): stubs[sym[name]&~1]=fn
stub('memset',lambda a,b,n,_: (uc.mem_write(a,bytes([b&255])*n),ret(a)))
def divide(a,b,_,__,sgn=False):
    if sgn: a,b=signed(a),signed(b)
    assert b,'division by zero'
    q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1)
    uc.reg_write(R[1],(a-q*b)&0xffffffff); ret(q)
stub('__aeabi_uidiv',divide)
stub('__aeabi_idiv',lambda *x:divide(*x,sgn=True))
next_dma=2
irq_handler=None
original_frames=[]
stops=[]
def claim_dma(*_):
    global next_dma
    n=next_dma; next_dma+=1; ret(n)
stub('dma_claim_unused_channel',claim_dma)
stub('pio_claim_unused_sm',lambda p,required,_,__: ret(0))
stub('pio_add_program',lambda p,program,_,__: ret(24))
stub('gpio_init',lambda *_:ret())
stub('gpio_set_function',lambda *_:ret())
stub('pio_sm_set_consecutive_pindirs',lambda *_:ret())
stub('clock_get_hz',lambda *_:ret(200000000))
def init_sm(p,sm,offset,cfg):
    # SDK struct order clkdiv/execctrl/shiftctrl/pinctrl.
    uc.mem_write(p+0xc8+sm*24,bytes(uc.mem_read(cfg,12)))
    write32(p+0xdc+sm*24,read32(cfg+12))
    assert offset==24
    ret(0)
stub('pio_sm_init',init_sm)
def add_irq(irq,handler,_,__):
    global irq_handler
    assert irq==12
    irq_handler=handler
    ret()
stub('irq_add_shared_handler',add_irq)
stub('irq_set_enabled',lambda *_:ret())
def frame(keys,render,_,__):
    original_frames.append((keys,render));ret(1)
stub('original_emulator_frame',frame)
stub('original_video_stop',lambda *_:(stops.append(1),ret()))
def code_hook(u,address,size,user):
    if address in stubs: stubs[address](*(u.reg_read(r) for r in R))
installed=set()
def install_stubs():
    for address in stubs.keys()-installed:
        uc.hook_add(UC_HOOK_CODE,code_hook,begin=address,end=address)
        installed.add(address)
def hw_read(u,access,address,size,value,data):
    # DMA abort completion is immediate in this model.
    if address==0x50000444: write32(address,0)
uc.hook_add(UC_HOOK_MEM_READ,hw_read)
def call(address,*args):
    install_stubs()
    uc.reg_write(UC_ARM_REG_SP,0x20042000)
    uc.reg_write(UC_ARM_REG_LR,RETURN|1)
    for i,r in enumerate(R): uc.reg_write(r,args[i] if i<len(args) else 0)
    for i,r in enumerate(CALLEE): uc.reg_write(r,0x12340000+i)
    uc.emu_start(address|1,RETURN,count=10000000)
    assert uc.reg_read(UC_ARM_REG_PC)==RETURN,hex(uc.reg_read(UC_ARM_REG_PC))
    assert uc.reg_read(UC_ARM_REG_SP)==0x20042000
    for i,r in enumerate(CALLEE): assert uc.reg_read(r)==0x12340000+i,(hex(address),i)
    return uc.reg_read(R[0])

# Decode ALL branch replacements independently of the patcher's encoders.
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
for at,name in [(0x1000809c,'addon_frame'),(0x10007cd0,'addon_stop'),(0x100082ac,'addon_stop'),(0x100082fc,'addon_stop'),(0x100027cc,'audio_read'),(0x100027d6,'audio_write')]:
    ins=list(cs.disasm(bytes(uc.mem_read(at,4)),at))[0]
    assert ins.mnemonic=='bl' and int(ins.op_str.lstrip('#'),16)==sym[name]&~1

# Actual original __gb_read/__gb_write prologues/epilogues plus audio hooks.
core=0x20003600
call(0x10002874,core,0xff70,1) # gb_reset's default WRAM bank offset
call(sym['audio_init'])
for addr,value in [(0xff26,0),(0xff30,0xab),(0xff26,0x80),(0xff24,0x77),(0xff25,0x11),(0xff11,0x80),(0xff12,0xf0),(0xff13,0x80),(0xff14,0x83)]:
    call(0x10002874,core,addr,value)
assert call(0x100025b0,core,0xff30)==0xab
assert call(0x100025b0,core,0xff12)==0xf0
assert call(0x100025b0,core,0xff26)&1
for addr in [0xc001,0xd010,0xff80,0xfffe]:
    call(0x10002874,core,addr,0x5a)
    got=call(0x100025b0,core,addr)
    assert got==0x5a,(hex(addr),hex(got))
buf=0x20030000
uc.mem_write(buf,bytes([0x55])*1100)
call(sym['audio_callback'],0,buf,267*4)
pcm=struct.unpack('<534h',uc.mem_read(buf,1068))
assert sum(x!=0 for x in pcm)>400
assert bytes(uc.mem_read(buf+1068,32))==b'\x55'*32
print('PASS ARM: patched APU dispatch, original non-APU memory, ABI/stack preservation, PCM boundaries')

# Start from a clean audio state: test the compiled frame/stop wrappers and
# actual driver register writes, using mocked SDK peripherals only.
start,end=sym['__addon_bss_start'],sym['__addon_bss_end']
uc.mem_write(start,bytes(end-start))
call(sym['addon_stop'])
assert stops==[1]
call(sym['addon_frame'],0xfe,0)
assert original_frames==[(0xfe,0)]
assert irq_handler
assert read32(0x502000c8)==50000<<8  # 200MHz / (16000 * 64), 16.8 divider
assert next_dma==4
assert uc.mem_read(sym['initialized'],1)==b'\x01'
# IRQ refill underflows to zero, never stale PCM.
write32(0x5000041c,1<<2)
call(irq_handler)
assert read32(sym['underruns'])==1
assert bytes(uc.mem_read(sym['blocks'],512))==bytes(512)
write32(0x5000041c,0)
call(sym['addon_frame'],0xfd,1)
assert original_frames[-1]==(0xfd,1)
call(sym['addon_stop'])
assert stops==[1,1]
assert uc.mem_read(sym['active'],1)==b'\x00'
assert uc.mem_read(sym['initialized'],1)==b'\x00'
call(sym['addon_frame'],0xff,1)
assert next_dma==4,'Restart leaked DMA channels'
call(sym['addon_stop'])
print('PASS ARM: frame/render passthrough, clock divider, underflow silence, stop/relaunch/resource reuse')

# Execute assembled PIO instruction stream in a small independent bit model.
program=re.findall(r'0x([0-9a-f]{4}),', (OUT/'audio_i2s.pio.h').read_text())[:8]
program=[int(x,16) for x in program]; assert len(program)==8
words=[0x1234fedc,0x80007fff,0x55aaaa55,0x6e819b02]
bits=[]; osr=0; remain=0; word=0; x=14; pc=0; din=0
for tick in range(64*len(words)):
    ins=program[pc]; side=(ins>>11)&3; kind=ins>>13
    if kind==3: # OUT pins,1 with MSB-first auto-pull
        if not remain: osr=words[word]; word+=1; remain=32
        din=osr>>31; osr=(osr<<1)&0xffffffff; remain-=1
    if side&1: bits.append(((side>>1)&1,din))
    if kind==0: # JMP X--
        jump=x!=0; x=(x-1)&0xffffffff
        pc=(ins&31) if jump else pc+1
    elif kind==7: x=ins&31; pc+=1
    else: pc+=1
    if pc==8: pc=0
expected=[(w>>bit)&1 for w in words for bit in range(31,-1,-1)]
assert [b for ws,b in bits]==expected
for i,(ws,bit) in enumerate(bits):
    assert ws==((i+1)//16)%2,'I2S WS must change one bit before next channel MSB'
print('PASS assembled PIO: 16-bit slots, MSB order, I2S one-bit WS delay, 32 BCLK/64 cycles per stereo frame')
