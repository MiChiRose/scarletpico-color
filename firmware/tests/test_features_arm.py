"""Execute the shipped ARM instructions, with explicit peripheral/FatFs mocks.
No device flashing or physical FPS claim. Includes baseline UI/audio regression,
five-slot corruption/failure tests, real emulator deterministic state replay,
large-ROM paging and the original main-loop input bridge.
"""
import os,struct,zlib,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build-features-v2_2_2-addon'
os.environ['SCARLET_TEST_FIRMWARE']=str(ROOT/'build-loader-addon/patched.bin')
os.environ['SCARLET_TEST_UI_ELF']=str(ROOT/'build-ui-addon/ui.elf')
import test_ui_arm as t
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm_const import *
with (BUILD/'features.elf').open('rb') as f:
 e=ELFFile(f);s={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols()}
t.sym.update(s)
t.uc.mem_write(0x10000000,Path(os.environ.get('SCARLET_FEATURE_IMAGE',str(BUILD/'patched.bin'))).read_bytes())
# Baseline UI tests already translated boot/main blocks. Invalidate their
# JIT cache after replacing flash so integration tests execute NEW hooks.
t.uc.ctl_remove_cache(0x10000000,0x10200000)
t.uc.mem_map(0x40060000,0x10000)
t.uc.mem_write(s['__features_bss_start'],bytes(s['__features_bss_end']-s['__features_bss_start']))
t.stubs[0x1000b954]=lambda dest,src,n,_:(t.uc.mem_write(dest,bytes(t.uc.mem_read(src,n))),t.ret(dest))
t.stub('original_video_wait_idle',lambda *_:t.ret())
t.stub('original_guard_pause',lambda *_:t.ret(1))
t.stub('original_guard_resume',lambda *_:t.ret())
def CALL(name,*args):
 t.install_stubs()
 t.uc.reg_write(UC_ARM_REG_SP,0x20042000);t.uc.reg_write(UC_ARM_REG_LR,t.RETURN|1)
 for i,r in enumerate(t.R):t.uc.reg_write(r,args[i] if i<len(args) else 0)
 for i,r in enumerate(t.CALLEE):t.uc.reg_write(r,0x12340000+i)
 t.uc.emu_start(s[name]|1,t.RETURN,count=100000000)
 assert t.uc.reg_read(UC_ARM_REG_PC)==t.RETURN,(name,hex(t.uc.reg_read(UC_ARM_REG_PC)))
 assert t.uc.reg_read(UC_ARM_REG_SP)==0x20042000
 for i,r in enumerate(t.CALLEE):assert t.uc.reg_read(r)==0x12340000+i,(name,i)
 return t.uc.reg_read(t.R[0])
ADDR=0x20044000
def cstr(p):
 out=bytearray()
 while True:
  x=t.uc.mem_read(p,1)[0];p+=1
  if not x:return out.decode()
  out.append(x)
text_calls=[]
strict_text=True
def observe_text(u,address,size,data):
 x,y,p,_=[u.reg_read(r) for r in t.R]
 text=cstr(p);text_calls.append((x,y,text))
 scale=t.read32(u.reg_read(UC_ARM_REG_SP)+4)
 limit=t.read32(u.reg_read(UC_ARM_REG_SP)+8)
 if strict_text:assert len(text)<=limit,(text,limit) # New screens must not clip.
 assert x+min(len(text),limit)*6*scale<=480 and y+8*scale<=320
t.uc.hook_add(UC_HOOK_CODE,observe_text,begin=s['ui_text']&~1,end=s['ui_text']&~1)

# Track full 480x320 output of the real renderer for visual inspection.
pixels=[0]*(480*320);window_state=None;row=0
def rect(x,y,w,h):
 assert x+w<=480 and y+h<=320
 t.rects.append((x,y,w,h))
 c=t.read32(t.uc.reg_read(UC_ARM_REG_SP))&65535
 for yy in range(y,y+h):pixels[yy*480+x:yy*480+x+w]=[c]*w
 t.ret()
def window(x,y,x1,y1):
 global window_state,row
 assert x<=x1<480 and y<=y1<320
 window_state=(x,y,x1,y1);row=0;t.ret()
def spi(spi,p,n,_):
 global row
 if window_state:
  x,y,x1,y1=window_state
  assert n==(x1-x+1)*2 and y+row<=y1
  colors=struct.unpack('>'+str(n//2)+'H',t.uc.mem_read(p,n))
  pixels[(y+row)*480+x:(y+row)*480+x1+1]=colors;row+=1
 t.ret(n)
t.stub('original_fill_rect',rect);t.stub('original_lcd_window',window);t.stub('spi_write_blocking',spi)
def preview(name):
 out=BUILD/'previews';out.mkdir(exist_ok=True)
 rgb=bytearray()
 for c in pixels:rgb.extend(((c>>11)*255//31,((c>>5)&63)*255//63,(c&31)*255//31))
 (out/(name+'.ppm')).write_bytes(b'P6\n480 320\n255\n'+rgb)

# Settings record backwards compatibility, partial repaint and clocks.
CALL('features_ui_init',0)
assert t.uc.mem_read(s['cpu_profile'],1)==b'\x02'
CALL('settings_draw');preview('settings-en')
t.rects.clear();CALL('features_settings_key',128)
assert (0,0,480,320) not in t.rects and len([r for r in t.rects if r[2:]==(448,32)])==2
for _ in range(2):CALL('features_settings_key',128)
CALL('features_settings_key',32)
assert t.uc.mem_read(s['cpu_profile'],1)==b'\x01'
CALL('features_settings_key',128);CALL('features_settings_key',128);CALL('features_settings_key',16)
preview('settings-ru')
# About shows the actual menu clock separately from the chosen game clock.
def menu_clock(which,*_):
 assert which==5
 t.ret(125000000)
t.stub('clock_get_hz',menu_clock)
for lang in [0,1]:
 t.uc.mem_write(s['ui_settings'],bytes([lang]))
 for profile,mhz in enumerate([125,170,200]):
  t.uc.mem_write(s['cpu_profile'],bytes([profile]));text_calls.clear()
  CALL('features_about_draw')
  assert (248,155,'125 MHZ') in text_calls
  assert (248,182,f'{mhz} MHZ') in text_calls
  assert (248,101,'v2.2.2') in text_calls
 preview('about-ru' if lang else 'about-en')
CALL('features_ui_init',0);t.uc.mem_write(s['focus'],struct.pack('<I',0))
CALL('settings_draw')
for key,expected in [(64,4),(128,0),(4,1),(4,2),(4,3),(4,4)]:
 t.rects.clear();CALL('features_settings_key',key)
 assert t.read32(s['focus'])==expected
 assert (0,0,480,320) not in t.rects
 assert len([r for r in t.rects if r[2:]==(448,32)])==2
before_settings=bytes(t.uc.mem_read(s['ui_settings'],3))
CALL('features_settings_key',32) # LEFT on About does not edit brightness.
assert bytes(t.uc.mem_read(s['ui_settings'],3))==before_settings
# Real navigation: enter with A/Start/Right, release, B returns to selected row.
# Holding B cannot accidentally exit both About and Settings; no idle redraw.
for key in [1,8,16]:
 t.ticks=0;t.sequence=[(0,60000,key),(160000,400000,2)]
 t.set_keys(key);t.rects.clear();t.erase_ops.clear();t.program_ops.clear()
 assert CALL('features_settings_key',key)==0
 assert t.read32(s['focus'])==4 and t.ticks>=430000
 assert sum(r==(0,0,480,320) for r in t.rects)==2
 assert not t.erase_ops and not t.program_ops
preview('settings-about-en')
# Opening About with an already persisted config does not write flash on exit.
t.ticks=0;t.sequence=[(60000,120000,2)];CALL('feature_settings')
t.erase_ops.clear();t.program_ops.clear()
t.ticks=0;t.sequence=[(60000,120000,64),(160000,220000,1),(300000,420000,2),(510000,590000,2)]
CALL('feature_settings')
assert not t.erase_ops and not t.program_ops
t.sequence=[];t.set_keys(0)
t.stub('clock_get_hz',lambda *_:t.ret(200000000))
print('PASS About: actual vs selected CPU, version, RU/EN, five-row wrap, A/Start/Right/B, release latch, no idle redraw or writes')
CALL('features_ui_init',0)
t.ticks=0;t.sequence=[(60000,120000,128),(160000,220000,128),(260000,320000,128),(360000,420000,32),(480000,550000,2)]
CALL('feature_settings')
assert t.uc.mem_read(s['cpu_profile'],1)==b'\x01'
assert bytes(t.uc.mem_read(0x1007f010,5))==b'SPC\x01\x01'
CALL('features_ui_init',0x1007f000)
assert t.uc.mem_read(s['cpu_profile'],1)==b'\x01'
# Old firmware sees its original record and the same volume/brightness.
t.call(t.sym['ui_init'],0x1007f000)
assert t.uc.mem_read(t.sym['ui_volume'],1)==b'\x32'
t.uc.mem_write(0x1007f01c,b'\0');CALL('features_ui_init',0x1007f000)
assert t.uc.mem_read(s['cpu_profile'],1)==b'\x02'
t.sequence=[];t.set_keys(0)
clock_calls=[]
def pll(vco,p1,p2,_):
 clock_calls.append((vco//p1//p2,(t.read32(0x40064000)>>4)&15));t.ret()
t.stub('set_sys_clock_pll',pll)
# Run the REAL check_sys_clock_khz, including its integer PLL calculation.
for i,mhz in enumerate([125,170,200]):
 t.uc.mem_write(s['cpu_profile'],bytes([i]));CALL('features_game_clock',0,0,0)
 assert clock_calls[-1][0]==mhz*1000000
 assert ((t.read32(0x40064000)>>4)&15)==(11 if i==0 else 12)
 if i:assert clock_calls[-1][1]==12
 t.stub('clock_get_hz',lambda *_:t.ret(clock_calls[-1][0]))
 t.call(t.sym['audio_output_stop']);t.call(t.sym['audio_output_start'])
 assert t.read32(0x502000c8)==(mhz*1000000//4000)<<8
 t.call(t.sym['audio_output_stop'])
CALL('features_menu_clock',1500000000,6,2)
assert clock_calls[-1][0]==125000000 and (t.read32(0x40064000)>>4)&15==11
t.stub('clock_get_hz',lambda *_:t.ret(200000000))
print('PASS settings: five rows, dirty rectangles, RU/EN, persistent 125/170/200, default/invalid record fallback, real PLL feasibility')
strict_text=False

# Execute the new HUD and its real patched call site with a text-output spy.
# No change to the original LCD counter, renderer, APU or display worker flow.
base=(ROOT/'build-loader-addon/patched.bin').read_bytes()
image=(BUILD/'patched.bin').read_bytes()
assert image[0x88b0:0x8a30]==base[0x88b0:0x8a30]
assert image[0x8a34:0x8d10]==base[0x8a34:0x8d10]
assert image[0x318:0x2018]==base[0x318:0x2018]
hud_calls=[]
bottom_fps=os.environ.get('SCARLET_BOTTOM_FPS')=='1'
def draw_hud(x,y,p,fg):
 sp=t.uc.reg_read(UC_ARM_REG_SP)
 hud_calls.append((x,y,cstr(p),fg,t.read32(sp),t.read32(sp+4)));t.ret()
t.stub('original_display_draw_text',draw_hud)
for scale in range(6):
 for lcd in [0,1,9,24,30,60,99,100,999,1000,0xffffffff]:
  for emu in [0,60,999]:
   hud_calls.clear();CALL('features_draw_fps',lcd,emu,scale)
   expected=('' if bottom_fps else 'LCD'+('\n' if scale==5 else ' '))+f'{min(lcd,999):3} FPS'
   assert hud_calls==[(8,310 if bottom_fps or scale!=5 else 268,expected,65535,0,1)]
t.install_stubs();hud_calls.clear()
t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
t.uc.reg_write(t.R[0],27);t.uc.reg_write(t.R[1],60);t.uc.reg_write(t.R[2],5)
t.uc.emu_start(0x10008a31,0x10008a34,count=100000)
assert t.uc.reg_read(UC_ARM_REG_PC)==0x10008a34
assert hud_calls==[(8,310 if bottom_fps else 268,('' if bottom_fps else 'LCD\n')+' 27 FPS',65535,0,1)]
assert t.uc.reg_read(UC_ARM_REG_SP)==0x20042000
t.stubs.pop(s['original_display_draw_text']&~1)
# Execute the unchanged real glyph renderer too (only the SPI peripheral is
# replaced). Digits clear themselves and no pixel can cover the game/old EMU.
t.stubs[0x100203b0]=spi
pixels[:]=[0]*(480*320)
CALL('features_draw_fps',100,60,5);CALL('features_draw_fps',0,60,5)
after_zero=pixels.copy();pixels[:]=[0]*(480*320)
CALL('features_draw_fps',0,60,5)
assert pixels==after_zero
CALL('features_draw_fps',30,60,5);preview('lcd-only-hud')
assert any(pixels)
top,bottom=(310,318) if bottom_fps else (268,284)
assert all(not c or (8<=i%480<50 and top<=i//480<bottom) for i,c in enumerate(pixels))
print('PASS LCD-only HUD: actual patched worker call, LCD independent of EMU, 0..999 clamp, fixed-width overwrite, unchanged counter/render/APU')

from boot_arm_checks import run_boot_checks
run_boot_checks(t,s,CALL,pixels,preview,BUILD)

# RAM allocator with guards and realistic 128 KiB budget. Freed video buffers
# are simulated below; the snapshot must fit without retaining a framebuffer.
live={};oom=False;peak=0
def malloc(n,*_):
 global peak
 if oom:t.ret(0);return
 n=(n+7)&~7;p=0x20020010
 for a,size in sorted(live.items()):
  if p+n+16<=a-16:break
  p=a+size+32
 if p+n+16>0x20040000:t.ret(0);return
 live[p]=n;peak=max(peak,sum(live.values()))
 t.uc.mem_write(p-16,b'\xa5'*(n+32));t.ret(p)
def free(p,*_):
 if p:
  n=live.pop(p)
  assert bytes(t.uc.mem_read(p-16,16))==b'\xa5'*16
  assert bytes(t.uc.mem_read(p+n,16))==b'\xa5'*16
 t.ret()
t.stub('original_malloc',malloc);t.stub('original_free',free)

# In-memory SD with positional FILs, read/write/close/seek fault injection.
files={};handles={};fail_write=False;fail_sync=False;fail_close=False;fail_read=False
read_requests=[];tail_fail=False;mkdir_error=False
def fopen(file,p,mode,_):
 name=cstr(p)
 if mode&8:files[name]=bytearray()
 if name not in files:t.ret(4);return
 handles[file]=[name,0,mode]
 t.uc.mem_write(file+16,struct.pack('<Q',len(files[name])));t.ret(0)
def seek(file,pad,lo,hi):
 assert hi==0
 if file not in handles:t.ret(9);return
 handles[file][1]=lo;t.ret(0)
def read(file,p,n,got):
 name,pos,mode=handles[file];read_requests.append((name,pos,n))
 if fail_read or (tail_fail and name.endswith('big.gbc') and pos>=0x17f000):t.write32(got,0);t.ret(1);return
 b=files[name][pos:pos+n]
 if b:t.uc.mem_write(p,bytes(b))
 handles[file][1]+=len(b);t.write32(got,len(b));t.ret(0)
def write(file,p,n,got):
 name,pos,mode=handles[file]
 assert mode&2
 count=min(n,17) if fail_write else n
 data=files[name]
 if len(data)<pos+count:data.extend(bytes(pos+count-len(data)))
 data[pos:pos+count]=t.uc.mem_read(p,count);handles[file][1]+=count
 t.uc.mem_write(file+16,struct.pack('<Q',len(data)));t.write32(got,count);t.ret(0)
def close(file,*_):
 mode=handles.pop(file)[2];t.ret(1 if fail_close and mode&2 else 0)
t.stub('f_open',fopen);t.stub('f_lseek',seek);t.stub('f_read',read);t.stub('f_write',write);t.stub('f_close',close)
t.stub('f_sync',lambda *_:t.ret(1 if fail_sync else 0))
t.stub('f_mkdir',lambda *_:t.ret(1 if mkdir_error else 8))
# Stack observations include actual core/CRC/format paths (not peripheral C).
minimum_sp=0x20042000
def stack_watch(u,access,address,size,value,data):
 global minimum_sp
 sp=u.reg_read(UC_ARM_REG_SP);minimum_sp=min(minimum_sp,sp)
 assert sp>=0x20041000,hex(sp)
t.uc.hook_add(UC_HOOK_MEM_WRITE,stack_watch,begin=0x20040000,end=0x20041fff)

CORE=0x20003600;APU=0x2001f2c0;CORE_SIZE=0xc324;APU_SIZE=312
# Use the actual core with a user-provided local ROM, not dummy snapshot bytes.
t.stubs.pop(0x10007070)
zelda=next((ROOT.parent/'roms').glob('*Zelda*.gb')).read_bytes()
t.uc.mem_write(0x10081000,zelda)
assert CALL('features_load',0x10081000,len(zelda),0)==1
assert t.read32(CORE+12)==s['original_core_error']
save_data=t.read32(0x2001db8c);save_size=t.read32(0x2001dcb0)
assert save_size==8192
t.uc.mem_write(t.sym['ui_volume'],b'\x32')
for _ in range(12):assert CALL('features_frame',255,0)==1
snapcore=bytes(t.uc.mem_read(CORE,CORE_SIZE));snapram=bytes(t.uc.mem_read(save_data,save_size));snapapu=bytes(t.uc.mem_read(APU,APU_SIZE))
assert CALL('state_status',0)==0
for slot in range(5):assert CALL('state_save',slot)==1
assert len(files)==5 and not handles
saved=bytes(t.uc.mem_read(CORE,CORE_SIZE))
assert saved==snapcore
def replay():
 for key in [247,255,254,255,223,255,239,255]:assert CALL('features_frame',key,0)==1
 return (bytes(t.uc.mem_read(CORE,CORE_SIZE)),bytes(t.uc.mem_read(APU,APU_SIZE)),bytes(t.uc.mem_read(t.read32(0x2001db8c),t.read32(0x2001dcb0))),bytes(t.uc.mem_read(t.sym['pcm'],1072)))
expected=replay()
assert CALL('state_load',0)==1 and bytes(t.uc.mem_read(APU,APU_SIZE))==snapapu
# joypad is deliberately released, callback addresses come from current core.
assert bytes(t.uc.mem_read(CORE,CORE_SIZE))==snapcore
assert replay()==expected
print('PASS real Zelda core: snapshot + CPU/VRAM/WRAM/RAM/APU restore + deterministic input/PCM replay')

# Every slot independent; preserve callbacks from the live runtime on load.
paths=sorted(files)
old_callbacks=bytes(t.uc.mem_read(CORE,28))
for i in range(5):
 t.uc.mem_write(save_data,bytes([i+1]));assert CALL('state_save',i)==1
for i in range(5):
 assert CALL('state_load',i)==1 and t.uc.mem_read(save_data,1)==bytes([i+1])
 assert bytes(t.uc.mem_read(CORE,28))==old_callbacks
# Corrupt newest generation -> recover older valid one, not a partial restore.
slot0=[p for p in files if p.endswith('-1b.sps')][0]
files[slot0][-1]^=1
assert CALL('state_load',0)==1 and bytes(t.uc.mem_read(save_data,save_size))==snapram
good=[p for p in files if p.endswith('-1a.sps')][0]
good_bytes=bytes(files[good])
for fault in ['short_write','sync','close','mkdir','read','oom']:
 files[good]=bytearray(good_bytes);files[slot0]=bytearray(b'broken')
 fail_write=fault=='short_write';fail_sync=fault=='sync';fail_close=fault=='close'
 mkdir_error=fault=='mkdir';fail_read=fault=='read';oom=fault=='oom'
 before=(bytes(t.uc.mem_read(CORE,CORE_SIZE)),bytes(t.uc.mem_read(save_data,save_size)))
 assert CALL('state_save',0)!=1,fault
 assert files[good]==good_bytes and before==(bytes(t.uc.mem_read(CORE,CORE_SIZE)),bytes(t.uc.mem_read(save_data,save_size))),fault
 fail_write=fail_sync=fail_close=mkdir_error=fail_read=oom=False
 assert not handles
# Both corrupt; no live state or callback mutation.
files[good][-1]^=1;files[slot0]=bytearray(b'broken')
before=bytes(t.uc.mem_read(CORE,CORE_SIZE))+bytes(t.uc.mem_read(save_data,save_size))+bytes(t.uc.mem_read(APU,APU_SIZE))
assert CALL('state_load',0)!=1
assert before==bytes(t.uc.mem_read(CORE,CORE_SIZE))+bytes(t.uc.mem_read(save_data,save_size))+bytes(t.uc.mem_read(APU,APU_SIZE))
assert CALL('state_load',5)!=1
assert not handles
print('PASS 5 slots, alternating generations, CRC fallback, all injected I/O failures/OOM, original valid generation preserved')

# Freeze guard, audio/video pause ownership and key suppression.
video_alloc=[];events=[]
def video_start(scale,*_):
 assert scale==int(os.environ.get('SCARLET_GAME_SCALE','5'))
 events.append('video-start');t.ret(1)
def video_stop(*_):events.append('video-stop');t.ret()
t.stub('original_video_start',video_start);t.stub('original_video_stop',video_stop)
t.ticks=100;assert CALL('features_buttons',12)==0
t.ticks+=1499999;assert CALL('features_buttons',12)==0 and not t.uc.mem_read(s['pause_pending'],1)[0]
t.ticks+=1;assert CALL('features_buttons',12)==0 and t.uc.mem_read(s['pause_pending'],1)[0]
assert CALL('features_buttons',4)==0 # Released Start must not leak Select.
assert CALL('features_buttons',0)==0
t.ticks=0;t.sequence=[(60000,120000,2)]
assert CALL('features_frame',255,0)==1
assert events[-2:]==['video-stop','video-start']
assert not t.uc.mem_read(s['pause_pending'],1)[0]
# Pause/slots pages: actual font renderer, native-size image output.
t.sequence=[];t.set_keys(0);CALL('pause_draw',1);preview('pause-en')
t.uc.mem_write(t.sym['ui_settings'],b'\1');CALL('pause_draw',1);preview('pause-ru')
CALL('slots_draw',1,0);preview('slots-ru');t.uc.mem_write(t.sym['ui_settings'],b'\0')
# Leave library via the real assembled bridge, not via a fake emulator error.
t.uc.mem_write(s['exit_requested'],b'\1');t.install_stubs()
t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
for i,r in enumerate([UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7]):t.uc.reg_write(r,0x34500000+i)
t.uc.emu_start(0x10008049,0x10008296,count=1000000)
assert t.uc.reg_read(UC_ARM_REG_PC)==0x10008296 and t.uc.reg_read(UC_ARM_REG_SP)==0x20042000
assert [t.uc.reg_read(r) for r in [UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7]]==[0x34500000,0x34500001,0x34500002]
print('PASS pause chord timing, release latch, pause/resume audio+video boundary, original clean exit jump ABI')
# Normal input bridge stores filtered keys and returns the original timer ABI.
t.ticks=123456;t.uc.reg_write(UC_ARM_REG_R4,1);t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
t.uc.emu_start(0x10008049,0x1000804e,count=1000000)
assert t.read32(0x20042000+88)==1 and t.uc.reg_read(t.R[0])==123456
assert t.uc.reg_read(t.R[1])==0 and t.uc.reg_read(UC_ARM_REG_SP)==0x20042000

# Large ROM backing and exact first 1.496 MiB flash cache. Synthetic tail
# exercises addresses that a short boot smoke test would never reach.
CALL('features_stop');files.clear();assert not handles
rom=bytearray((i*17+(i>>11)+3)&255 for i in range(2*1024*1024));rom[0x148]=6
files['0:/roms/big.gbc']=rom
t.uc.mem_write(ADDR,b'0:/roms/big.gbc\0');t.uc.mem_write(0x10080000,b'\xff'*4096)
t.erase_ops.clear();t.program_ops.clear();read_requests.clear()
assert CALL('features_prepare',ADDR,ADDR+128,ADDR+132)==1
assert t.read32(ADDR+128)==0x10081000 and t.read32(ADDR+132)==len(rom)
assert bytes(t.uc.mem_read(0x10081000,0x17f000))==rom[:0x17f000]
assert t.erase_ops==[(i,65536) for i in range(0x80000,0x200000,65536)]
assert max(o+n for o,n in t.program_ops)<=0x200000
assert t.program_ops[-1]==(0x80000,256)
assert bytes(t.uc.mem_read(0x10080000,8))==b'SPPAGE1\0'
for a in [0,0x134,0x17efff,0x17f000,0x17f010,0x17f800,0x17f011,0x1fffff,len(rom),0x800000]:
 assert CALL('features_rom_read',CORE,a)==(rom[a] if a<len(rom) else 255),hex(a)
assert all(n==2048 for name,off,n in read_requests if off>=0x17f000)
t.erase_ops.clear();t.program_ops.clear()
assert CALL('features_prepare',ADDR,ADDR+128,ADDR+132)==1
assert not t.erase_ops and not t.program_ops
CALL('features_stop');assert not handles
print('PASS 2 MiB ROM: exact resident image, no flash overflow, tail/cache/bounds, warm cache, handle cleanup')

# No partial cache commit on failed initialization, and small games still use
# the original Fastload writer. Read errors after a tail miss must unwind via
# the original emulator escape handler, never return invented ROM bytes.
files['0:/roms/big.gbc']=rom
t.uc.mem_write(0x10080000,b'\xff'*4096)
fail_read=True;t.program_ops.clear()
assert CALL('features_prepare',ADDR,ADDR+128,ADDR+132)==0
assert not handles and not t.program_ops
fail_read=False
files['0:/roms/big.gbc']=bytearray(zelda)
assert CALL('features_prepare',ADDR,ADDR+128,ADDR+132)==1
assert bytes(t.uc.mem_read(0x10081000,len(zelda)))==zelda
assert not handles
print('PASS failed ROM preparation cleanup and unchanged original Fastload path for small ROMs')

collection=Path(os.environ.get('SCARLET_ROM_COLLECTION','/Users/yuramac/Downloads/GameBoy_2139_(7930)_ROMs'))
for relative in ['P/Pokemon - Silver Version (UE) [C][!].gbc',
                 'P/Pokemon - Crystal Version (UE) (V1.1) [C][!].gbc',
                 'W/Wario Land 3 (JU) (M2) [C][!].gbc']:
 p=collection/relative
 if not p.exists():print('SKIP local ROM absent:',p.name);continue
 game=p.read_bytes();assert len(game)>0x17f000
 CALL('features_stop');files['0:/roms/big.gbc']=bytearray(game)
 assert CALL('features_prepare',ADDR,ADDR+128,ADDR+132)==1
 assert CALL('features_load',0x10081000,len(game),0)==1
 assert t.read32(CORE)==s['features_rom_read']|1
 # Worst normal 32 KiB save-RAM footprint plus both video allocations fits.
 t.call(s['original_malloc'],46080);buf1=t.uc.reg_read(t.R[0]);assert buf1
 t.call(s['original_malloc'],46080);buf2=t.uc.reg_read(t.R[0]);assert buf2
 # Model real SDL work as hardware stub; actual core/APU run unmodified.
 for frame in range(int(os.environ.get('SCARLET_TEST_FRAMES','90'))):assert CALL('features_frame',255 if frame<60 else 247,0)==1,(p.name,frame)
 t.call(s['original_free'],buf2);t.call(s['original_free'],buf1)
 statefiles=[x for x in files if x.startswith('0:/states/')]
 before={x:bytes(files[x]) for x in statefiles}
 assert CALL('state_save',4)==1
 expected=replay()
 assert CALL('state_load',4)==1
 assert replay()==expected,p.name
 assert all(bytes(files[x])==b for x,b in before.items())
 # LRU cache never supplies stale or cross-game bank contents.
 for addr in [0x17f000,0x17f7ff,len(game)-1,0x17f800,0x17f100]:
  assert CALL('features_rom_read',CORE,addr)==game[addr]
 print('PASS real paged ARM ROM + state replay:',p.name,'size',len(game),'RAM',t.read32(0x2001dcb0))
 # A failed SD read inside the actual core unwinds through its existing
 # setjmp/longjmp error path; never emulate corrupted/fabricated instructions.
 tail_fail=True
 t.uc.mem_write(CORE+0x24,struct.pack('<H',0x7a)) # switchable ROM bank, uncached tail
 t.uc.mem_write(CORE+0x38,struct.pack('<H',0x4000)) # PC in selected bank
 t.uc.mem_write(CORE+28,b'\0') # awake, IME off, force instruction fetch
 before_reads=len(read_requests)
 error_result=CALL('features_frame',255,0)
 assert error_result==0
 assert len(read_requests)>before_reads
 tail_fail=False
 assert b'CORE ERROR' in bytes(t.uc.mem_read(0x2000f960,80))
 print('PASS paged I/O failure: original core escape, no fabricated ROM bytes')
CALL('features_stop');assert not handles

print(f'PASS feature tests: peak mocked dynamic RAM {peak} bytes; observed mocked stack {0x20042000-minimum_sp} bytes; physical SD timing/FPS not measured')
print('FIRMWARE_SHA256',hashlib.sha256(Path(os.environ.get('SCARLET_FEATURE_UF2',str(ROOT/'releases/scarletpico-features-v2_2_2-experimental.uf2'))).read_bytes()).hexdigest())
