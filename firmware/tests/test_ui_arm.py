"""Real final ARM image + original ROM-loader/menu control flow.
Only hardware/FatFs/clock sources are mocked; no physical flash is touched.
"""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('SCARLET_TEST_FIRMWARE',str(ROOT/'build-ui-addon/patched.bin'))
os.environ.setdefault('SCARLET_TEST_UI_ELF',str(ROOT/'build-ui-addon/ui.elf'))
from test_audio_arm import *
sym.update(ui_syms)
uc.mem_map(0x40030000,0x10000)
uc.mem_map(0x40050000,0x4000)
from unicorn import UC_HOOK_MEM_WRITE
def pwm_alias(u,access,address,size,value,data):
    alias=(address-0x40050000)//4096
    if not alias:return
    target=address-alias*4096
    old=read32(target)
    write32(target,old^value if alias==1 else old|value if alias==2 else old&~value)
uc.hook_add(UC_HOOK_MEM_WRITE,pwm_alias,begin=0x40051000,end=0x40053fff)
ticks=0
sequence=[]
mounts=[]
erase_ops=[]
program_ops=[]
rects=[]
windows=[]
spi_rates=[]
pin_functions=[]
pins=[15,26,28,27,14,2,0,1]
def set_keys(mask):
    value=0xffffffff
    for i,p in enumerate(pins):
        if mask&(1<<i):value &= ~(1<<p)
    write32(0xd0000004,value)
def advance(us):
    global ticks
    ticks+=us
    mask=0
    for begin,end,key in sequence:
        if begin<=ticks<end:mask=key
    set_keys(mask)
def sleep_ms(n,*_):advance(n*1000);ret()
stub('sleep_ms',sleep_ms)
stub('sleep_us',lambda *_:ret())
def clock(*_):uc.reg_write(R[1],0);ret(ticks)
stub('time_us_64',clock)
stub('gpio_set_function',lambda pin,fn,*_:(pin_functions.append((pin,fn)),ret()))
stub('original_display_init',lambda *_:ret())
stub('original_display_select_bus',lambda *_:(spi_rates.append(50000000),ret()))
stub('spi_set_baudrate',lambda spi,rate,*_:(spi_rates.append(rate),ret(rate)))
def rect(x,y,w,h):
    assert x+w<=480 and y+h<=320,(x,y,w,h)
    rects.append((x,y,w,h));ret()
stub('original_fill_rect',rect)
def window(x,y,x1,y1):
    assert x<=x1<480 and y<=y1<320
    windows.append((x,y,x1,y1));ret()
stub('original_lcd_window',window)
stub('spi_write_blocking',lambda spi,p,n,_:ret(n))
def mount(*_):
    result=mounts.pop(0) if mounts else 1
    ret(result)
stub('original_storage_mount',mount)
def erase(offset,n,*_):
    assert offset%4096==0 and n%4096==0 and 0x7f000<=offset<0x200000
    assert offset+n<=0x200000
    erase_ops.append((offset,n));uc.mem_write(0x10000000+offset,b'\xff'*n)
    advance(200000);ret()
stub('original_flash_erase',erase)
def program(offset,p,n,_):
    assert offset%256==0 and n%256==0 and offset>=0x7f000
    program_ops.append((offset,n));uc.mem_write(0x10000000+offset,bytes(uc.mem_read(p,n)));advance(1000);ret()
stub('original_flash_program',program)
record=0x20030000
uc.mem_write(0x1007f000,b'\xff'*4096)
set_keys(0)
call(sym['ui_boot_display'],1)
assert uc.mem_read(sym['ui_volume'],1)==b'\x32'
assert pin_functions[-1]==(10,4)
assert read32(0x40050000+5*20+16)==999 # PWM TOP
assert read32(0x40050000+5*20+12)&0xffff==1000
for v in [0,10,50,100,999]:
    call(sym['ui_apply_brightness'],v)
    assert read32(0x40050000+5*20+12)&0xffff==min(100,max(10,v))*10
assert not erase_ops
print('PASS ARM: persisted defaults, PWM GP10/slice5, brightness clamp 10..100, no CPU clock writes')

# Real settings loop, real debounce/release, actual flash record.
call(sym['ui_init'],0)
ticks=0;sequence=[(60000,120000,128),(160000,220000,16),(260000,320000,2)]
call(sym['ui_menu_input'],16)
assert uc.mem_read(sym['ui_volume'],1)==b'\x3c'
assert erase_ops==[(0x7f000,4096)] and program_ops==[(0x7f000,256)]
call(sym['ui_init'],0x1007f000)
assert uc.mem_read(sym['ui_volume'],1)==b'\x3c'
print('PASS ARM: settings input/debounce, one save on exit, exact reserved sector, reboot restores volume')

# Actual PCM routine + tiny gain-load bridge: 0/50/100, no synthesis changes.
sequence=[];set_keys(0)
for volume in [0,50,100]:
    call(sym['audio_output_start'])
    uc.mem_write(sym['ui_volume'],bytes([volume]))
    uc.mem_write(record,struct.pack('<hhhh',1000,3000,-1000,-3000))
    call(sym['audio_output_submit'],record,2)
    got=struct.unpack('<II',uc.mem_read(sym['queue'],8))
    a=20*volume;b=(-20*volume)&65535
    assert got==(a|(a<<16),b|(b<<16)),(volume,got)
    call(sym['audio_output_stop'])
print('PASS ARM: actual original mixer at mute/50%/100%, signed stereo-to-mono gain')

# Inline menu hook preserves r0-r3/r6/r7 and emits the original B-test flags.
for edge in [0,1,2,4,8,64,128]:
    install_stubs()
    uc.reg_write(UC_ARM_REG_SP,0x20042000)
    uc.reg_write(UC_ARM_REG_R5,edge);uc.reg_write(UC_ARM_REG_R7,edge)
    write32(0x2001e258,0)
    for i,r in enumerate(R):uc.reg_write(r,0x88770000+i)
    uc.reg_write(UC_ARM_REG_R6,0xd0000000)
    uc.emu_start(0x10007b25,0x10007b28,count=1000000)
    assert uc.reg_read(UC_ARM_REG_PC)==0x10007b28
    assert uc.reg_read(UC_ARM_REG_R4)==2 and uc.reg_read(UC_ARM_REG_R5)==edge
    assert bool(uc.reg_read(UC_ARM_REG_APSR)&(1<<30))==(not bool(edge&2))
    assert all(uc.reg_read(r)==0x88770000+i for i,r in enumerate(R))
    assert uc.reg_read(UC_ARM_REG_SP)==0x20042000
print('PASS ARM: actual inline input hook ABI and condition flags; game controls untouched')

# Missing card stays on the error screen; released A retries until available.
ticks=0;sequence=[(60000,120000,1),(200000,260000,1)];mounts=[0,1]
erase_ops.clear();program_ops.clear();rects.clear()
assert call(sym['ui_boot_display'],0)==1
assert not mounts and not erase_ops and not program_ops
assert sum(r==(0,0,480,320) for r in rects)==2 # initial error + failed retry, not polling flicker
print('PASS ARM: no-card boot, failed retry, successful retry; no endless redraw or writes')

# Run the unmodified original storage_prepare_rom body, with only FatFs and
# flash hardware mocked. All UI hooks, bus switching and erase chunking run.
sequence=[];set_keys(0);ticks=0;erase_ops.clear();program_ops.clear()
rom=bytes((i*13+7)&255 for i in range(0x20000))
cursor=0
def fopen(file,path,mode,_):
    write32(file+16,len(rom));ret(0)
stubs[0x100146e4]=fopen
def seek(file,pad,lo,hi):
    global cursor
    assert hi==0;cursor=lo;ret(0)
stubs[0x100157f0]=seek
def read(file,p,n,got):
    global cursor
    block=rom[cursor:cursor+n];uc.mem_write(p,block);write32(got,len(block));cursor+=len(block)
    advance(2000);ret(0)
stub('original_f_read',read)
stubs[0x10015770]=lambda *_:ret(0)
stubs[0x1000d544]=lambda *_:ret(0)
def memcmp(a,b,n,_):
    a=bytes(uc.mem_read(a,n));b=bytes(uc.mem_read(b,n));ret(0 if a==b else 1)
stubs[0x1001c97c]=memcmp
write32(0x2001adb4,1);write32(0x2001e220,0)
uc.mem_write(0x2001adb8+256,b'TEST ROM\0')
uc.mem_write(record,b'0:/roms/test.gb\0')
assert call(sym['ui_prepare_rom'],record,record+64,record+68)==1
assert read32(record+64)==0x10081000 and read32(record+68)==len(rom)
assert bytes(uc.mem_read(0x10081000,len(rom)))==rom
assert erase_ops==[(0x80000,65536),(0x90000,65536),(0xa0000,4096)]
assert program_ops[-1]==(0x80000,256)
assert set(spi_rates)<={12500000,50000000}
assert len([r for r in rects if r[2:]==(7,7)])>16
print('PASS ARM: original ROM loader, exact data/cache layout, animated erase/read, correct SPI handoff')

# Cache-hit path must not erase/write again or change the selected game.
erase_ops.clear();program_ops.clear()
assert call(sym['ui_prepare_rom'],record,record+64,record+68)==1
assert not erase_ops and not program_ops
print('PASS ARM: cached ROM load is read-only, no artificial delay')

# The original main loop itself: initial scan, DOWN selection, A launch; then
# a separate run through RIGHT/settings/B-return/A. Stop before game starts.
for address in [0x10008d10,0x1000d3a0,0x10008e64,0x10000c5c,0x10007164,0x1000716c,0x10008dac,0x10008cb0,0x10008dc4]:
    stubs[address]=lambda *_:ret(0)
def scan(g,cap,n,limited):
    assert cap==32
    for i,name in enumerate([b'ALADDIN',b'ZELDA',b'PACMAN']):
        uc.mem_write(g+i*332,bytes(332));uc.mem_write(g+i*332+256,name+b'\0')
    write32(n,3);uc.mem_write(limited,b'\0');ret(0)
stub('original_scan_games',scan)
for settings in [False,True]:
    ticks=0;mounts=[];erase_ops.clear();program_ops.clear()
    uc.mem_write(0x1007f000,b'\xff'*4096);write32(0x2001e220,0)
    if settings:
        sequence=[(350000,430000,16),(520000,590000,128),(680000,750000,16),(850000,920000,2),(1200000,1270000,1)]
    else:sequence=[(350000,430000,128),(550000,620000,1)]
    set_keys(0);install_stubs();uc.reg_write(UC_ARM_REG_SP,0x20042000)
    uc.emu_start(0x10007835,0x10007c72,count=10000000)
    assert uc.reg_read(UC_ARM_REG_PC)==0x10007c72,hex(uc.reg_read(UC_ARM_REG_PC))
    assert read32(0x2001e220)==(0 if settings else 1)
    assert uc.mem_read(sym['ui_volume'],1)==(b'\x3c' if settings else b'\x32')
    assert erase_ops==([(0x7f000,4096)] if settings else [])
print('PASS ARM: original main loop navigates games, opens settings, returns without auto-launch, then launches selected game')
