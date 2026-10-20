"""Exercise final patched ARM code and real original storage writer.
Also runs all UI/audio ARM regressions. Peripheral/SD stubs are explicit;
transaction counts measure the algorithm, NOT physical transfer time/FPS.
"""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['SCARLET_TEST_FIRMWARE']=str(ROOT/'build-loader-addon/patched.bin')
os.environ['SCARLET_TEST_UI_ELF']=str(ROOT/'build-ui-addon/ui.elf')
import test_ui_arm as t
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_PC
with (ROOT/'build-loader-addon/loader.elf').open('rb') as f:
    elf=ELFFile(f)
    syms={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
t.sym.update(syms)

for at,name in [(0x10007f08,'loader_prepare'),(0x1000853e,'loader_header_read'),(0x100085fe,'loader_page_read')]:
    ins=list(t.cs.disasm(bytes(t.uc.mem_read(at,4)),at))[0]
    assert ins.mnemonic=='bl' and int(ins.op_str.lstrip('#'),16)==syms[name]&~1
assert t.read32(0x10000270)==syms['__loader_bss_end']
assert t.read32(0x1000d124)==syms['__loader_bss_end']

# Guarded 4 KiB allocation. Verify it is never retained beyond loading.
HEAP=0x20028000
requests=[];allocations=[];frees=[]
live=False;oom=False;file_error=False
fail_offset=None;short_offset=None;header_failure=False
rom=b'';cursor=0
def allocate(n,*_):
    global live
    assert n==4096 and not live
    allocations.append(n)
    if oom:t.ret(0);return
    live=True;t.uc.mem_write(HEAP-16,b'\xA5'*(4096+32));t.ret(HEAP)
def free(p,*_):
    global live
    assert p==HEAP and live
    assert bytes(t.uc.mem_read(HEAP-16,16))==b'\xA5'*16
    assert bytes(t.uc.mem_read(HEAP+4096,16))==b'\xA5'*16
    live=False;frees.append(p);t.ret()
t.stub('original_malloc',allocate);t.stub('original_free',free)
def fopen(file,path,mode,_):
    t.write32(file+16,len(rom));t.ret(4 if file_error else 0)
def seek(file,pad,lo,hi):
    global cursor
    assert hi==0;cursor=lo;t.ret(0)
def read(file,p,n,got):
    global cursor
    requests.append((cursor,n))
    if (header_failure and n==28) or (fail_offset==cursor and n!=28):
        t.write32(got,0);t.ret(1);return
    block=rom[cursor:cursor+n]
    if short_offset==cursor and n!=28:block=block[:17]
    t.uc.mem_write(p,block);t.write32(got,len(block));cursor+=len(block)
    t.advance(2000);t.ret(0)
t.stubs[0x100146e4]=fopen;t.stubs[0x100157f0]=seek
t.stub('original_f_read',read)
# Keep the longest transient stack use below the reserved 4 KiB main stack.
min_sp=0x20042000
def watch_stack(u,access,address,size,value,data):
    global min_sp
    sp=u.reg_read(UC_ARM_REG_SP)
    min_sp=min(min_sp,sp)
    assert sp>=0x20041000,hex(sp)
t.uc.hook_add(UC_HOOK_MEM_WRITE,watch_stack,begin=0x20041000,end=0x20041fff)
def reset(n):
    global rom,cursor,live,oom,file_error,fail_offset,short_offset,header_failure
    assert not live
    rom=bytes((i*13+(i>>8)+7)&255 for i in range(n));cursor=0
    oom=file_error=header_failure=False;fail_offset=short_offset=None
    requests.clear();allocations.clear();frees.clear()
    t.erase_ops.clear();t.program_ops.clear();t.rects.clear();t.spi_rates.clear()
    t.sequence=[];t.ticks=0;t.set_keys(0)
    t.uc.mem_write(0x10080000,b'\xff'*4096)
    t.uc.mem_write(t.record,b'0:/roms/test.gb\0')
    t.call(t.sym['ui_invalidate'])

def load():
    return t.call(syms['loader_prepare'],t.record,t.record+64,t.record+68)

for n in [32768,65536,131072,524288,1048576]:
    reset(n)
    assert load()==1
    assert t.read32(t.record+64)==0x10081000 and t.read32(t.record+68)==n
    assert bytes(t.uc.mem_read(0x10081000,n))==rom
    assert len(requests)==1+n//4096 and requests[0]==(0x134,28)
    assert requests[1:]==[(i,4096) for i in range(0,n,4096)]
    assert allocations==[4096] and frees==[HEAP] and not live
    assert t.program_ops==[(0x81000+i,256) for i in range(0,n,256)]+[(0x80000,256)]
    assert bytes(t.uc.mem_read(0x10080000,8))==b'SPROM01\0'
    assert set(t.spi_rates)<={12500000,50000000}
    draws=sum(r[2:]==(7,7) for r in t.rects)//8-1
    sd_configs=t.spi_rates.count(12500000)
    assert sd_configs<=draws+3,(sd_configs,draws)
    print(f'PASS ARM fast load {n//1024} KiB: {len(requests)-1} block reads, {sd_configs} SD setups; payload/pages/metadata exact')

# No ROM-cache hit allocation, erase, reprogram or stale file readahead.
requests.clear();allocations.clear();frees.clear();t.erase_ops.clear();t.program_ops.clear()
assert load()==1 and requests==[(0x134,28)]
assert not allocations and not frees and not t.erase_ops and not t.program_ops
print('PASS ARM: warm cache skips the read buffer and all flash writes')

reset(65536);oom=True
assert load()==1 and allocations==[4096] and not frees and not live
assert len(requests)==1+65536//256
assert bytes(t.uc.mem_read(0x10081000,len(rom)))==rom
print('PASS ARM: out-of-memory falls back to original 256-byte reads, same ROM data')

for failure in ['open','header','first_read','later_read','short_read']:
    reset(65536)
    if failure=='open':file_error=True
    elif failure=='header':header_failure=True
    elif failure=='first_read':fail_offset=0
    elif failure=='later_read':fail_offset=8192
    else:short_offset=8192
    assert load()==0 and not live
    assert len(frees)==len(allocations)
    assert (0x80000,256) not in t.program_ops
    reset(32768);assert load()==1 and bytes(t.uc.mem_read(0x10081000,len(rom)))==rom
print('PASS ARM: open/header/data/short-read errors, no false cache commit, buffer freed; next game/retry succeeds')

# Oversize/zero are still rejected; never erase beyond the original bounds.
for n in [0,0x200000]:
    reset(n);assert load()==0
    assert not allocations and not frees and not t.erase_ops and not t.program_ops
print('PASS ARM: ROM size protection and existing cache/settings layout retained')

# Execute the actual main-loop call instruction, not just an exported helper.
reset(65536);t.install_stubs()
t.uc.reg_write(t.R[0],t.record);t.uc.reg_write(t.R[1],t.record+64);t.uc.reg_write(t.R[2],t.record+68)
t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
t.uc.emu_start(0x10007f09,0x10007f0c,count=10000000)
assert t.uc.reg_read(UC_ARM_REG_PC)==0x10007f0c and t.uc.reg_read(t.R[0])==1
assert allocations==[4096] and frees==[HEAP] and not live
print(f'PASS ARM: real main-loop launch hook, no retained allocation, maximum observed simulated stack {0x20042000-min_sp} bytes')
