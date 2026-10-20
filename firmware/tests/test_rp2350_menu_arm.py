"""Execute the compiled Cortex-M33 menu, pause and snapshot bindings.

Only peripheral/SD I/O is stubbed. This is not a physical LCD/FPS test.
"""
from pathlib import Path
import argparse
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rp2040',action='store_true')
parser.add_argument('--elf',type=Path)
parser.add_argument('--battery',action='store_true')
parser.add_argument('--battery-adc',action='store_true')
parser.add_argument('--expected-lcd-hz',type=int,help='Check the baud request from actual display_game_speed code.')
parser.add_argument('--preview',type=Path,help='Write actual compiled UI output as PPM (with --battery-adc).')
args=parser.parse_args();rp2040=args.rp2040
elf=ELFFile((args.elf or ROOT/('build-rp2040-native/scarlet2040.elf' if rp2040 else 'build-rp2350-source/scarlet2350.elf')).open('rb'))
uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
# macOS must allow Unicorn's local JIT mappings; a restricted execution
# sandbox may trap on mem_map. Tests never connect to USB hardware.
uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M0 if rp2040 else UC_CPU_ARM_CORTEX_M33)
uc.mem_map(0x10000000,0x400000);uc.mem_map(0x20000000,0x42000 if rp2040 else 0x84000)
uc.mem_map(0x40000000,0x1000000);uc.mem_map(0x50000000,0x1000000)
uc.mem_map(0xd0000000,0x10000);uc.mem_map(0xe0000000,0x100000)
for section in elf.iter_sections():
    a=section['sh_addr'];n=section['sh_size']
    if n and section['sh_flags']&2 and section['sh_type']!='SHT_NOBITS':
        uc.mem_write(a,section.data())
sym={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
R=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
END=0x10000300
hooks={};ticks=0;sequence=[];rects=[];windows=[];brightness=[];flash_ops=[];events=[]
def read32(a):return struct.unpack('<I',uc.mem_read(a,4))[0]
def write32(a,v):uc.mem_write(a,struct.pack('<I',v&0xffffffff))
def alias_write(u,access,a,n,v,data):
    alias=(a>>12)&3
    if not alias:return
    target=a-alias*4096;old=read32(target)
    write32(target,old^v if alias==1 else old|v if alias==2 else old&~v)
uc.hook_add(UC_HOOK_MEM_WRITE,alias_write,begin=0x40000000,end=0x40ffffff)
uc.hook_add(UC_HOOK_MEM_WRITE,alias_write,begin=0x50000000,end=0x50ffffff)
def ret(v=0):
    uc.reg_write(R[0],v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def stub(name,fn):hooks[sym[name]&~1]=fn
def hook(u,a,n,d):
    if a in hooks:hooks[a](*(u.reg_read(r) for r in R))
uc.hook_add(UC_HOOK_CODE,hook)
def call(name,*args):
    stack=0x20041fc0 if rp2040 else 0x20081000
    uc.reg_write(UC_ARM_REG_SP,stack);uc.reg_write(UC_ARM_REG_LR,END|1)
    for r,v in zip(R,args[:4]):uc.reg_write(r,v)
    for i,v in enumerate(args[4:]):write32(stack+4*i,v)
    uc.emu_start(sym[name]|1,END,count=20000000)
    assert uc.reg_read(UC_ARM_REG_PC)==END,(name,hex(uc.reg_read(UC_ARM_REG_PC)))
    return uc.reg_read(R[0])
def key(*_):
    k=next((k for lo,hi,k in sequence if lo<=ticks<hi),0);ret(k)
def sleep(ms,*_):
    global ticks
    ticks+=ms*1000;ret()
def time(*_):uc.reg_write(R[1],ticks>>32);ret(ticks&0xffffffff)
def rect(x,y,w,h):
    assert w and h and x+w<=480 and y+h<=320,(x,y,w,h)
    rects.append((x,y,w,h));ret()
def begin(x,y,w,h):
    assert w and h and x+w<=480 and y+h<=320
    windows.append((x,y,w,h));ret()
stub('feature_keys',key);stub('sleep_ms',sleep);stub('time_us_64',time)
stub('display_rect',rect);stub('display_ui_begin',begin)
stub('display_ui_row',lambda p,n,*_:(bytes(uc.mem_read(p,n)),ret()))
stub('display_ui_end',lambda *_:ret())
stub('ui_apply_brightness',lambda v,*_:(brightness.append(v),ret()))
stub('display_width',lambda *_:ret(320));stub('display_height',lambda *_:ret(288))
labels=0x20039800 if rp2040 else 0x20070000
entry_count=64 if rp2040 else 192
for i in range(entry_count):uc.mem_write(labels+i*40,f'Game {i:03d}.gb'.encode()+b'\0')
stub('native_game_count',lambda *_:ret(entry_count))
stub('native_game_label',lambda i,*_:ret(labels+i*40))
stub('native_game_color',lambda i,*_:ret(i==1))
stub('native_game_folder',lambda i,*_:ret(i==0))
stub('original_audio_stop',lambda *_:(events.append('audio_stop'),ret()))
stub('original_audio_start',lambda *_:(events.append('audio_start'),ret(1)))
stub('native_video_stop',lambda *_:(events.append('video_stop'),ret()))
stub('native_video_start',lambda *_:(events.append('video_start'),ret()))
def erase(off,n,*_):
    assert off==0x7f000 and n==4096
    flash_ops.append('erase');uc.mem_write(0x10000000+off,b'\xff'*n);ret()
def program(off,p,n,*_):
    assert off==0x7f000 and n==256
    flash_ops.append('program');uc.mem_write(0x10000000+off,bytes(uc.mem_read(p,n)));ret()
stub('flash_range_erase',erase);stub('flash_range_program',program)
uc.mem_write(0x1007f000,b'\xff'*4096)
if rp2040:
    # RP2040 SDK calls factory ROM memory functions and its hardware divider.
    # Simulate only these platform services, not menu/core/APU application code.
    stub('__wrap_memcpy',lambda dest,src,n,*_:(uc.mem_write(dest,bytes(uc.mem_read(src,n))),ret(dest)))
    stub('__wrap_memset',lambda dest,v,n,*_:(uc.mem_write(dest,bytes([v&255])*n),ret(dest)))
    def divide(a,b,*_):
        assert b
        uc.reg_write(R[1],a%b);ret(a//b)
    stub('__wrap___aeabi_uidivmod',divide)
    def signed_divide(a,b,*_):
        a=a if a<2**31 else a-2**32;b=b if b<2**31 else b-2**32
        assert b;q=abs(a)//abs(b);q=-q if (a<0)!=(b<0) else q
        uc.reg_write(R[1],(a-q*b)&0xffffffff);ret(q&0xffffffff)
    stub('__wrap___aeabi_idivmod',signed_divide)
    # SDK spin locks are peripherals; grant a lock without simulating a core1.
    for i in range(32):write32(0xd0000100+4*i,1)
    uc.hook_add(UC_HOOK_MEM_READ,lambda u,access,a,n,v,d:write32(a,1),begin=0xd0000100,end=0xd000017f)
call('features_ui_init',0)
assert bytes(uc.mem_read(sym['ui_volume'],1))==b'\x32' and brightness[-1]==100

# Actual menu loop: select the next game. Full paint once; key navigation must
# stay in the list/metadata strips, never clear the entire display again.
ticks=0;sequence=[(60000,120000,4),(180000,240000,1)]
rects.clear();windows.clear();assert call('console_menu',0)==1
assert sum(r==(0,0,480,320) for r in rects)==1
call('ui_menu_draw',0);before=len(rects);call('ui_menu_draw',0);assert len(rects)==before
# All configured entries accessible, not clamped to the historical 32.
ticks=0;sequence=[(60000,120000,1)];assert call('console_menu',entry_count-1)==entry_count-1
print(f'PASS ARM menu: original UI, idle is unchanged, no full redraw on selection, {entry_count} entries')

# Settings from a real menu: Right, volume up, brightness down, B, then launch.
ticks=0;sequence=[(60000,120000,16),(180000,240000,16),(300000,360000,128),
 (420000,480000,32),(540000,600000,2),(660000,720000,1)]
assert call('console_menu',0)==0
assert uc.mem_read(sym['ui_volume'],1)==b'\x3c' and uc.mem_read(sym['ui_settings']+2,1)==b'\x5a'
# The same-TU brightness call is inlined by GCC: verify the actual PWM CC,
# not the separately stubbed call ui_init uses during reboot.
assert read32(0x40050070 if rp2040 else 0x400a8070)&65535==900
assert flash_ops==['erase','program']
call('features_ui_init',0x1007f000)
assert uc.mem_read(sym['ui_volume'],1)==b'\x3c' and brightness[-1]==90
print('PASS ARM settings: volume/brightness, safe reserved flash sector, reboot persistence')

# Real chord filtering, 1.5 seconds, consume release, individual keys unchanged.
call('console_input_reset');ticks=0;sequence=[]
assert call('features_buttons',12)==0;ticks=1499999
assert call('features_buttons',12)==0 and uc.mem_read(sym['pause_pending'],1)==b'\0'
ticks=1500000;assert call('features_buttons',12)==0
assert uc.mem_read(sym['pause_pending'],1)==b'\1'
events.clear();sequence=[(ticks+60000,ticks+120000,2)]
assert call('features_frame',255,1)==1
assert events==['audio_stop','video_stop','video_start','audio_start'],events
assert uc.mem_read(sym['pause_pending'],1)==b'\0'
assert call('features_buttons',8)==8 and call('features_buttons',4)==4
print('PASS ARM pause: chord withheld from game, halt/resume order, buttons consumed')

# Exit is confirmed explicitly. The worker is not restarted just to exit.
call('console_input_reset');uc.mem_write(sym['pause_pending'],b'\1')
ticks=0;sequence=[(60000,120000,64),(180000,240000,1),(300000,360000,1)]
events.clear();assert call('features_frame',255,1)==1
assert uc.mem_read(sym['exit_requested'],1)==b'\1'
assert events==['audio_stop','video_stop'],events
uc.mem_write(sym['exit_requested'],b'\0')
print('PASS ARM exit: explicit confirmation, stopped worker, no automatic launch')

# The actual native state helpers strip and reinstall live function pointers.
size=call('native_core_size');assert size==0xc320
gb=sym['gb'];scratch=sym['frames'] if rp2040 else 0x20070000
uc.mem_write(gb,b'\x11'*size);call('native_core_copy',scratch)
assert bytes(uc.mem_read(scratch,28))==b'\0'*28
assert uc.mem_read(scratch+28,1)==b'\x11'
call('native_core_restore',scratch)
assert read32(gb)==sym['rom_read']|1 and read32(gb+12)==sym['emulation_error']|1
assert read32(gb+16)==0 and read32(gb+20)==0 and read32(gb+24)==0
assert uc.mem_read(gb+0xc319,1)==b'\xff'
print('PASS ARM native snapshot ABI: actual structure size, strip/restore callbacks, joypad release')

# Actual producer and APU, while physical DMA clocks are deliberately stubbed.
uc.mem_write(sym['active'],b'\1');uc.mem_write(sym['playing'],b'\1')
queue=sym['original_audio_queue'];pcm=0x2003a800 if rp2040 else 0x20070000
uc.mem_write(pcm,struct.pack('<hhhh',1000,3000,-1000,-3000))
for vol in (0,50,100):
    uc.mem_write(sym['ui_volume'],bytes([vol]));write32(queue+2048,0);write32(queue+2052,0)
    call('original_audio_submit',pcm,2)
    v=20*vol;nv=(-v)&65535
    assert struct.unpack('<II',uc.mem_read(queue,8))==(v|(v<<16),nv|(nv<<16))
call('console_apu_init');write32(queue+2048,0);write32(queue+2052,0)
samples=0
for i in range(120):
    write32(queue+2048,0);write32(queue+2052,0);call('console_audio_frame')
    n=read32(queue+2048);assert n in (267,268);samples+=n
assert samples==(120*16000*70224>>22)
print('PASS ARM audio: mono preserves both channels at 0/50/100%, exact 59.7275 Hz PCM sample scheduling')

# Run the actual I2S startup/configuration with SDK allocation functions mocked.
# Channel 0 (LCD), 1/2 (SD) are reserved; this code must claim 3/4 and IRQ 2.
hooks.pop(sym['original_audio_start']&~1)
claimed=[3,4];configs=[];irq_handlers=[];pins=[]
stub('dma_claim_unused_channel',lambda required,*_:ret(claimed.pop(0)))
stub('pio_claim_unused_sm',lambda *_:ret(0))
stub('pio_can_add_program',lambda *_:ret(1));stub('pio_add_program',lambda *_:ret(24))
stub('gpio_set_function',lambda pin,fn,*_:(pins.append(pin),ret()))
stub('pio_sm_set_consecutive_pindirs',lambda p,sm,pin,count:ret())
stub('pio_sm_init',lambda p,sm,off,cfg:(configs.append((p,sm,off,bytes(uc.mem_read(cfg,16)))),ret()))
stub('irq_add_shared_handler',lambda irq,p,*_:(irq_handlers.append(irq),ret()))
stub('irq_set_enabled',lambda *_:ret());stub('clock_get_hz',lambda *_:ret(200000000))
uc.mem_write(sym['playing'],b'\0');uc.mem_write(sym['active'],b'\0')
write32(0x5000000c,0x13579);assert call('original_audio_start')==1
assert claimed==[] and pins==[11,12,13] and irq_handlers==[12]
assert configs[0][:3]==(0x50300000,0,24)
clkdiv,execctrl,shiftctrl,pinctrl=struct.unpack('<4I',configs[0][3])
assert clkdiv==50000<<8 and (pinctrl&31)==13 and (pinctrl>>10&31)==11
assert read32(0x50000414 if rp2040 else 0x50000424)&24==24
for i,ch in enumerate((3,4)):
    ctrl=read32(0x50000010+64*ch)
    assert ctrl&1 and (ctrl>>(11 if rp2040 else 13)&15)==(4 if i==0 else 3) and (ctrl>>(15 if rp2040 else 17)&63)==8
    assert read32(0x50000004+64*ch)==0x50300010
uc.mem_write(sym['ui_volume'],b'\x32');uc.mem_write(pcm,struct.pack('<hh',1000,3000)*384)
call('original_audio_submit',pcm,384)
assert read32(queue+2048)==384 and read32(queue+2052)==256
assert read32(0x50000430 if rp2040 else 0x50000450)==8 and read32(0x50300000)&1
write32(0x5000041c if rp2040 else 0x5000042c,8);call('audio_irq')
assert read32(queue+2052)==384 and read32(0x50000008+3*64)==128
assert read32(0x5000000c)==0x13579
print(f'PASS ARM I2S: separate claimed DMA 3/4 + IRQ{1 if rp2040 else 2}, 16 kHz divider, 384-frame prefill, completed-half refill, LCD DMA untouched')

if rp2040:
    symbols={s.name:s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
    assert symbols['frames']['st_size']==92160 and symbols['cart_ram']['st_size']==32768
    assert symbols['states']['st_size']==2
    assert sym['__bss_end__']<sym['__HeapLimit']==0x20040000
    write32(sym['frame_lock'],0xd0000178)
    for previous,expected,drops,next_writing in [([1,0],[2,1],0,1),([1,3],[1,3],1,0),([1,2],[2,1],1,1),([3,1],[3,1],1,1)]:
        uc.mem_write(sym['states'],bytes(previous));write32(sym['writing'],previous.index(1));write32(sym['drop_count'],0)
        call('publish_frame')
        assert list(uc.mem_read(sym['states'],2))==expected
        assert read32(sym['drop_count'])==drops and read32(sym['writing'])==next_writing
    print('PASS ARM RP2040 buffers: fits 264 KiB SRAM, two frames, busy display never overwritten, no producer wait')

    # Execute the actual ARMv6-M core/line callback with our original minimal
    # GB and GBC ROMs. No Nintendo boot ROM or commercial game is embedded.
    for cgb in (0,1):
        rom=bytearray(32768);rom[0x134:0x13b]=b'LCDTEST';rom[0x143]=0x80 if cgb else 0
        rom[0x100:0x103]=bytes([0xc3,0x50,1]);rom[0x150:0x156]=bytes([0x3e,0x91,0xe0,0x40,0x18,0xfe])
        rom[0x14d]=(-sum(rom[0x134:0x14d])-25)&255
        uc.mem_write(0x10080000,bytes(rom));write32(sym['rom_size'],len(rom));write32(sym['save_size'],0)
        assert call('gb_init',gb,sym['rom_read']|1,sym['ram_read']|1,sym['ram_write']|1,sym['emulation_error']|1,0)==0
        call('native_core_copy',scratch);call('native_core_restore',scratch)
        write32(sym['writing'],0);uc.mem_write(sym['frames'],b'\xa5'*46080)
        for i in range(3):call('gb_run_frame',gb)
        assert read32(sym['error_code'])==0
        assert uc.mem_read(sym['frames'],46080)!=b'\xa5'*46080
    print('PASS ARM RP2040 core: real GB and GBC ARMv6-M execution, RGB565 callback writes a frame')

if args.battery:
    assert rp2040 and 'console_power_init' in sym
    power_record=0x2003d000
    uc.mem_write(power_record,b'\xff'*256)
    reads=[];pin_state=0;raw_sample=2358;texts=[]
    stub('adc_init',lambda *_:ret())
    stub('console_power_read_sample',lambda *_:(reads.append(ticks),ret(raw_sample)))
    stub('console_power_charge_pins',lambda *_:ret(pin_state))
    def capture_text(x,y,p,*_):
        data=bytes(uc.mem_read(p,90)).split(b'\0',1)[0]
        texts.append(data.decode('ascii'));ret()
    stub('ui_text',capture_text)
    def shown():
        texts.clear();call('console_power_header');return '|'.join(texts)
    call('console_power_init',power_record)
    call('console_power_poll');assert not reads and 'MONITOR OFF' in shown()
    call('console_power_record',power_record)
    assert bytes(uc.mem_read(power_record+16,6))==b'BAT1\x00\xff'
    uc.mem_write(power_record+20,b'\x01\xfe');ticks=0
    call('console_power_init',power_record);call('console_power_poll')
    assert '3.80 V' in shown() and 'IDLE/UNKNOWN' in shown()
    assert len(reads)==1
    pin_state=1
    for ticks in (100000,200000,300000):call('console_power_poll')
    assert 'CHARGING' not in shown()  # Require four consecutive status samples.
    ticks=400000;call('console_power_poll');assert 'CHARGING' in shown()
    assert len(reads)==1  # GPIO debounce must not re-read ADC every 100 ms.
    pin_state=2
    for ticks in (500000,600000,700000,800000):call('console_power_poll')
    assert 'CHARGE DONE' in shown()
    # Charge-complete indication does not force the voltage estimate to 100%.
    assert (read32(sym['snapshot'])>>13)&7==3
    pin_state=3
    for ticks in (900000,1000000,1100000,1200000):call('console_power_poll')
    assert 'CHECK SIGNALS' in shown() and len(reads)==2
    raw_sample=3103;ticks=2000000;call('console_power_poll')
    assert 'SENSOR CHECK' in shown() and not read32(sym['snapshot'])&(1<<21)
    raw_sample=2141;pin_state=0;ticks=0
    call('console_power_init',power_record)
    for ticks in range(0,4000001,100000):call('console_power_poll')
    assert 'LOW - SAVE GAME' in shown()
    rects.clear();call('console_power_game')
    assert rects and all(x+w<=78 and y+h<=33 for x,y,w,h in rects)
    call('console_power_record',power_record)
    assert bytes(uc.mem_read(power_record+16,6))==b'BAT1\x01\xfe'
    uc.mem_write(power_record+21,b'\xff');call('console_power_init',power_record)
    count_reads=len(reads);ticks+=1000000;call('console_power_poll')
    assert len(reads)==count_reads and 'MONITOR OFF' in shown()
    print('PASS ARM battery: safe OFF default/corrupt record, real compiled ADC conversion, status debounce, 1 Hz sampling, complete != 100%, invalid sensor, low warning, game-rail bounds')

if args.battery_adc:
    assert rp2040 and 'console_power_charge_pins' not in sym
    power_record=0x2003d000
    uc.mem_write(power_record,b'\xff'*256)
    reads=[];raw_sample=2358;texts=[];touched_pins=[]
    stub('adc_init',lambda *_:ret())
    stub('gpio_set_function',lambda pin,fn,*_:(touched_pins.append(pin),ret()))
    stub('console_power_read_sample',lambda *_:(reads.append(ticks),ret(raw_sample)))
    original_text=sym['ui_text']&~1
    def capture_text(x,y,p,color):
        text=bytes(uc.mem_read(p,90)).split(b'\0',1)[0].decode('ascii')
        scale=read32(uc.reg_read(UC_ARM_REG_SP)+4)
        texts.append((x,y,text,color,scale));ret()
    stub('ui_text',capture_text)
    def shown():
        texts.clear();rects.clear();call('console_power_header')
        assert all(x>=400 and x+w<=480 and y+h<=44 for x,y,w,h in rects)
        for x,y,text,_,scale in texts:
            assert x>=400 and x+len(text)*6*scale<=480 and y+7*scale<=44
        return '|'.join(t[2] for t in texts)
    ticks=0;call('console_power_init',power_record)
    assert '--.--V' in shown() and not reads
    call('console_power_poll')
    assert shown()=='3.80V' and len(reads)==1
    assert texts[0][:3]==(410,28,'3.80V') and texts[0][4]==2
    assert read32(sym['snapshot'])>>13&7==3
    assert touched_pins==[29],touched_pins
    for ticks in (100000,200000,900000,999999):call('console_power_poll')
    assert len(reads)==1
    ticks=1000000;call('console_power_poll');assert len(reads)==2
    # No invalid-voltage full/empty claim; no invented charger state.
    for raw_sample in (0,3103):
        ticks+=1000000;call('console_power_poll')
        assert '--.--V' in shown() and not read32(sym['snapshot'])&(1<<21)
        assert read32(sym['snapshot'])>>13&7==0
    raw_sample=2141;ticks=0;call('console_power_init',power_record)
    for ticks in range(0,4000001,1000000):call('console_power_poll')
    assert read32(sym['snapshot'])&(1<<22)
    shown();low_color=texts[0][3]
    raw_sample=2607
    for ticks in range(5000000,35000001,1000000):call('console_power_poll')
    assert not read32(sym['snapshot'])&(1<<22) and read32(sym['snapshot'])>>13&7==5
    shown();assert texts[0][3]!=low_color
    # Preserve the original first 16 UI-setting bytes; round-trip BAT2 ON/OFF.
    uc.mem_write(power_record,bytes(range(16)))
    call('console_power_record',power_record)
    assert bytes(uc.mem_read(power_record,16))==bytes(range(16))
    assert bytes(uc.mem_read(power_record+16,6))==b'BAT2\x01\xfe'
    uc.mem_write(power_record+20,b'\x00\xff');call('console_power_init',power_record)
    count=len(reads);ticks+=1000000;call('console_power_poll')
    assert len(reads)==count and shown()=='OFF'
    call('console_power_record',power_record)
    assert bytes(uc.mem_read(power_record+16,6))==b'BAT2\x00\xff'
    # Old BAT1 and corrupt BAT2 default ON in this assembled-hardware release.
    for record in (b'BAT1\x00\xff',b'BAT2\x00\x00'):
        uc.mem_write(power_record+16,record);ticks=0;raw_sample=2358
        call('console_power_init',power_record);call('console_power_poll')
        assert shown()=='3.80V'
    rects.clear();call('console_power_ui_tick');assert not rects
    raw_sample=2400;ticks=1000000;call('console_power_ui_tick')
    assert rects and all(x>=400 and x+w<=480 and y+h<=44 for x,y,w,h in rects)
    rects.clear();call('console_power_game')
    assert rects and all(x>=400 and x+w<=480 and y+h<=44 for x,y,w,h in rects)
    print('PASS ARM GP29: default ON, BAT2 persistence/migration, 472+472 conversion, 1 Hz sampling, invalid sensor, low warning/hysteresis, voltage below icon, right-rail bounds, no charger GPIOs')
    if args.preview:
        # Paint actual compiled menu/icon/text via the peripheral boundaries.
        # No hand-drawn font or mock implementation of the indicator is used.
        hooks.pop(original_text)
        screen=[0]*(480*320);window=[0,0,0,0,0]
        def paint_rect(x,y,w,h):
            rect(x,y,w,h)
            color=read32(uc.reg_read(UC_ARM_REG_SP))&65535
            for row in range(y,y+h):screen[row*480+x:row*480+x+w]=[color]*w
        def paint_begin(x,y,w,h):
            begin(x,y,w,h);window[:]=[x,y,w,h,0]
        def paint_row(p,n,*_):
            x,y,w,h,row=window;assert n==w*2 and row<h
            screen[(y+row)*480+x:(y+row)*480+x+w]=struct.unpack('>'+str(w)+'H',uc.mem_read(p,n))
            window[4]+=1;ret()
        stub('display_rect',paint_rect);stub('display_ui_begin',paint_begin)
        stub('display_ui_row',paint_row)
        raw_sample=2358;ticks=0;call('console_power_init',power_record);call('console_power_poll')
        call('ui_invalidate');call('ui_menu_draw',1)
        rgb=bytearray()
        for c in screen:rgb.extend((((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31))
        args.preview.write_bytes(b'P6\n480 320\n255\n'+rgb)
        print('Actual ARM-rendered preview:',args.preview)

if args.expected_lcd_hz:
    rates=[]
    stub('spi_set_baudrate',lambda spi,rate,*_:(rates.append((spi,rate)),ret(rate)))
    assert call('display_game_speed')==args.expected_lcd_hz
    assert rates==[(0x4003c000,args.expected_lcd_hz)],rates
    print('PASS ARM LCD request:',args.expected_lcd_hz,'Hz (actual wire stability still requires the physical console)')
