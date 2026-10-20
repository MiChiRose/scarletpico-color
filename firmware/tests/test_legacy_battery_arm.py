"""Execute final legacy-2.2.2 battery ARM image, mocking peripherals only."""
from pathlib import Path
import hashlib,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-battery-legacy-addon'
OUT=ROOT/'releases/2026-10-20-rp2040-legacy222-battery'
audit=json.loads((OUT/'build-audit.json').read_text())
raw=(BUILD/'patched.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()==audit['image_sha256']
uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M0)
for a,n in [(0x10000000,0x200000),(0x20000000,0x50000),(0x40000000,0x1000000),(0x50000000,0x1000000),(0xd0000000,0x10000),(0xe0000000,0x100000)]:uc.mem_map(a,n)
uc.mem_write(0x10000000,raw)
with (BUILD/'battery.elf').open('rb') as f:
 e=ELFFile(f);s={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols() if x.name}
R=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
CALLEE=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
END=0x1007fff0;hooks={};ticks=0;sample=2358;adc_failure=False;conversions=0;writes=[];texts=[];rects=[]
screen=[0]*(480*320);window=None;row=0;minimum_sp=0x20042000
def word(a):return struct.unpack('<I',uc.mem_read(a,4))[0]
def put(a,v):uc.mem_write(a,struct.pack('<I',v&0xffffffff))
def ret(v=0):uc.reg_write(R[0],v&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def stub(a,fn):hooks[(s[a] if isinstance(a,str) else a)&~1]=fn
def cstr(a):
 b=bytearray()
 while (c:=uc.mem_read(a,1)[0]):b.append(c);a+=1
 return b.decode('utf-8')
def hook(u,a,n,d):
 global minimum_sp
 minimum_sp=min(minimum_sp,u.reg_read(UC_ARM_REG_SP))
 if a in hooks:hooks[a](*(u.reg_read(r) for r in R))
uc.hook_add(UC_HOOK_CODE,hook)
def call(a,*args,core1=False,check_abi=True):
 sp=0x20041000 if core1 else 0x20042000
 uc.reg_write(UC_ARM_REG_SP,sp);uc.reg_write(UC_ARM_REG_LR,END|1)
 for r,v in zip(R,list(args[:4])+[0]*4):uc.reg_write(r,v)
 for i,v in enumerate(args[4:]):put(sp+4*i,v)
 for i,r in enumerate(CALLEE):uc.reg_write(r,0x12340000+i)
 uc.emu_start((s[a] if isinstance(a,str) else a)|1,END,count=10000000)
 assert uc.reg_read(UC_ARM_REG_PC)==END,(a,hex(uc.reg_read(UC_ARM_REG_PC)))
 assert uc.reg_read(UC_ARM_REG_SP)==sp
 if check_abi:assert all(uc.reg_read(r)==0x12340000+i for i,r in enumerate(CALLEE)),a
 return uc.reg_read(R[0])
def hw_write(u,access,a,n,v,d):
 global conversions
 writes.append((a,v))
 if a==0x4004e000 and v&4:conversions+=1
 if 0x40000000<=a<0x41000000 and (a>>12)&3:
  base=a-((a>>12)&3)*4096;old=word(base);alias=(a>>12)&3
  put(base,old^v if alias==1 else old|v if alias==2 else old&~v)
uc.hook_add(UC_HOOK_MEM_WRITE,hw_write,begin=0x40000000,end=0x40ffffff)
def hw_read(u,access,a,n,v,d):
 if a==0x4004c000:put(a,(word(a)&~(1<<8)) if adc_failure else word(a)|(1<<8))
 if a==0x4004c004:put(a,sample)
 if a==0x4000c008:put(a,1)
uc.hook_add(UC_HOOK_MEM_READ,hw_read,begin=0x40000000,end=0x40ffffff)
def clock(*_):uc.reg_write(R[1],ticks>>32);ret(ticks)
stub('time_us_64',clock)
stub('memcpy',lambda dst,src,n,*_:(uc.mem_write(dst,bytes(uc.mem_read(src,n))),ret(dst)))
stub(0x1000b948,lambda dst,v,n,*_:(uc.mem_write(dst,bytes([v&255])*n),ret(dst)))
def divide(a,b,*_):assert b;uc.reg_write(R[1],a%b);ret(a//b)
stub('__aeabi_uidiv',divide)
def rectangle(x,y,w,h):
 assert w and h and x+w<=480 and y+h<=320,(x,y,w,h)
 color=word(uc.reg_read(UC_ARM_REG_SP))&65535;rects.append((x,y,w,h,color))
 for yy in range(y,y+h):screen[yy*480+x:yy*480+x+w]=[color]*w
 ret()
stub('old_rect',rectangle)
def text_observe(u,a,n,d):
 x,y,p,c=[u.reg_read(r) for r in R];scale=word(u.reg_read(UC_ARM_REG_SP)+4)
 texts.append((x,y,cstr(p),c,scale))
uc.hook_add(UC_HOOK_CODE,text_observe,begin=s['old_text']&~1,end=s['old_text']&~1)
def begin(x,y,x1,y1):
 global window,row
 assert x<=x1<480 and y<=y1<320,(x,y,x1,y1)
 window=(x,y,x1,y1);row=0;ret()
def spi(spi,p,n,*_):
 global row
 if window:
  x,y,x1,y1=window;assert n==(x1-x+1)*2 and y+row<=y1
  screen[(y+row)*480+x:(y+row)*480+x1+1]=struct.unpack('>'+str(n//2)+'H',uc.mem_read(p,n));row+=1
 ret(n)
stub(0x1000039c,begin);stub(0x200016a0,spi)
stub(0x10000c0c,lambda *_:ret());stub(0x100312e4,lambda *_:ret())
stub(0x10009b68,lambda *_:ret())

call('legacy_battery_poll');assert conversions==17
assert word(s['battery_snapshot'])&8191==3800
assert word(s['battery_snapshot'])>>13&7==3
assert word(s['battery_snapshot'])&(1<<16)
allowed={0x400140ec,0x4001c078,0x40008060,0x40008064,0x4000f000,0x4004c000,0x4004e000}
assert all(a in allowed for a,v in writes),writes
assert word(0x400140ec)==31 and not word(0x4001c078)&0x4c
assert word(0x40008060)==0x800 and word(0x40008064)==0x100
for ticks in (1,500000,999999):call('legacy_battery_poll')
assert conversions==17
ticks=1000000;call('legacy_battery_poll');assert conversions==34
for sample in (0,3103):
 ticks+=1000000;call('legacy_battery_poll');assert not word(s['battery_snapshot'])&(1<<16)
adc_failure=True;ticks+=1000000
before=conversions;call('legacy_battery_poll')
assert not word(s['battery_snapshot'])&(1<<16) and conversions==before
adc_failure=False;sample=2141
for _ in range(5):ticks+=1000000;call('legacy_battery_poll')
assert word(s['battery_snapshot'])&(1<<17)
sample=2607
for _ in range(30):ticks+=1000000;call('legacy_battery_poll')
assert not word(s['battery_snapshot'])&(1<<17) and word(s['battery_snapshot'])>>13&7==5
print('PASS real ARM ADC MMIO: GP29 only, no LCD/CPU/SPI writes, 17 conversions, 1 Hz, invalid voltage/timeout recovery, low warning/hysteresis')

def reset_battery():
 global ticks,sample
 uc.mem_write(s['__battery_bss_start'],bytes(s['__battery_bss_end']-s['__battery_bss_start']))
 ticks=0;sample=2358
reset_battery();call(0x10030758,0)
put(0x2001adb4,3);put(0x2001e220,0);uc.mem_write(0x2001e258,b'\0')
for i,name in enumerate([b'ZELDA',b'TETRIS',b'MARIO']):
 a=0x2001adb8+i*332;uc.mem_write(a,bytes(332));uc.mem_write(a+256,name+b'\0')
def patches(after):
 for c in audit['changes']:
  uc.mem_write(int(c['address'],16),bytes.fromhex(c['after' if after else 'before']))
 uc.ctl_remove_cache(0x10000000,0x10200000)
patches(False);call(0x100308cc);call(0x10030b20,1);baseline=list(screen)
patches(True);reset_battery();call(0x100308cc);call(0x10030b20,1)
assert any(x==410 and y==28 and text=='3.80V' and scale==2 for x,y,text,c,scale in texts)
for y in range(320):
 for x in range(480):
  if x<400 or y>=44:assert screen[y*480+x]==baseline[y*480+x],(x,y)
assert screen!=baseline
print('PASS real original menu/font render: all pixels outside 80x44 indicator match hardware-working 2.2.2; voltage below battery')
def ppm(name):
 rgb=bytearray()
 for c in screen:rgb.extend((((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31))
 (BUILD/name).write_bytes(b'P6\n480 320\n255\n'+rgb)
ppm('menu.ppm')

put(0xd0000004,0xffffffff);rects.clear();texts.clear()
for edge in (0,1,2,4,8,64,128):
 uc.reg_write(UC_ARM_REG_SP,0x20042000)
 for i,r in enumerate(R):uc.reg_write(r,0x88770000+i)
 uc.reg_write(UC_ARM_REG_R5,edge);uc.reg_write(UC_ARM_REG_R7,edge)
 uc.reg_write(UC_ARM_REG_R6,0xd0000000)
 uc.emu_start(0x10007b25,0x10007b28,count=1000000)
 assert uc.reg_read(UC_ARM_REG_PC)==0x10007b28
 assert uc.reg_read(UC_ARM_REG_R5)==edge and uc.reg_read(UC_ARM_REG_R4)==2
 assert bool(uc.reg_read(UC_ARM_REG_APSR)&(1<<30))==(not bool(edge&2))
 assert all(uc.reg_read(r)==0x88770000+i for i,r in enumerate(R))
 assert uc.reg_read(UC_ARM_REG_SP)==0x20042000
assert not rects
print('PASS actual original input bridge: return/flags/registers preserved, unchanged idle draws nothing')

pace_calls=[];pace_result=3
stub('old_pace_frame',lambda k,o,d,*_:(pace_calls.append((k,o,d)),ret(pace_result)))
for pace_result in (0,1,3):
 sp=0x20041f80;uc.reg_write(UC_ARM_REG_SP,sp);put(sp+0x30,123456)
 uc.reg_write(UC_ARM_REG_LR,END|1);uc.reg_write(R[0],0xa5);uc.reg_write(R[1],1)
 uc.emu_start(0x100368d1,END,count=1000000)
 assert pace_calls[-1]==(0xa5,1,123456)
 assert uc.reg_read(R[0])==pace_result&1 and uc.reg_read(UC_ARM_REG_R7)==pace_result>>1
 assert uc.reg_read(UC_ARM_REG_SP)==sp
print('PASS actual PACED bridge: keys/offered/due and return bitset/R7 frame-ready ABI unchanged')

reset_battery();call('legacy_battery_poll')
screen[:]=[0x1234]*(480*320);before=list(screen);texts.clear();rects.clear()
uc.reg_write(UC_ARM_REG_SP,0x20041000)
for r,v in zip(R,[23,59,5,0]):uc.reg_write(r,v)
for i,r in enumerate(CALLEE):uc.reg_write(r,0x12340000+i)
uc.emu_start(0x10008a31,0x10008a34,count=1000000)
assert uc.reg_read(UC_ARM_REG_PC)==0x10008a34
assert uc.reg_read(UC_ARM_REG_SP)==0x20041000
assert all(uc.reg_read(r)==0x12340000+i for i,r in enumerate(CALLEE))
assert any(x==434 and y==28 and text=='3.80V' and scale==1 for x,y,text,c,scale in texts)
for y in range(320):
 for x in range(62,418):assert screen[y*480+x]==before[y*480+x],(x,y)
assert all((x+w<=62 or x>=418) for x,y,w,h,c in rects)
assert minimum_sp>=0x20040000,hex(minimum_sp)
assert any('FPS' in text for x,y,text,c,scale in texts)
ppm('game-rail.ppm')
print('PASS original core1 FPS+voltage text: game 356x320 untouched, right 62px rail only, stack remains in reserved core1 bank')
reset_battery();ticks=0xfffffff0;call('legacy_battery_poll');count=conversions
ticks=(0xfffffff0+999999)&0xffffffff;call('legacy_battery_poll');assert conversions==count
ticks=(0xfffffff0+1000000)&0xffffffff;call('legacy_battery_poll');assert conversions==count+17
print('PASS 32-bit timer wrap: sampling continues at one second across timer-low rollover')
print('FIRMWARE_SHA256',audit['uf2_sha256'])
