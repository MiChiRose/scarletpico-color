"""Actual ARM region pipeline + original diff/worker call sites.
DMA, SPI and time are explicit mocks; no physical FPS claims or flashing.
"""
import hashlib,os,random,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-video-fast-addon'
os.environ['SCARLET_TEST_FIRMWARE']=str(ROOT/'build-loader-addon/patched.bin')
os.environ['SCARLET_TEST_UI_ELF']=str(ROOT/'build-ui-addon/ui.elf')
import test_ui_arm as t
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
with (BUILD/'video.elf').open('rb') as f:
 e=ELFFile(f);s={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols()}
t.uc.mem_write(0x10000000,Path(os.environ.get('SCARLET_VIDEO_IMAGE',str(BUILD/'patched.bin'))).read_bytes())
t.uc.ctl_remove_cache(0x10000000,0x10200000)
SPI=0x4003c000;DMA=0x50000000;SIO=0xd0000000;SRC=0x20024000;PREV=0x20030000
word=t.read32;put=t.write32
def call(address,*args):
 t.install_stubs();sp=0x20041000 # Actual core-1 stack, not core-0's spare RAM.
 t.uc.reg_write(UC_ARM_REG_SP,sp);t.uc.reg_write(UC_ARM_REG_LR,t.RETURN|1)
 for i,r in enumerate(t.R):t.uc.reg_write(r,args[i] if i<len(args) else 0)
 for i,x in enumerate(args[4:]):put(sp+4*i,x)
 for i,r in enumerate(t.CALLEE):t.uc.reg_write(r,0x12340000+i)
 t.uc.emu_start(address|1,t.RETURN,count=10000000)
 assert t.uc.reg_read(UC_ARM_REG_PC)==t.RETURN,hex(t.uc.reg_read(UC_ARM_REG_PC))
 assert t.uc.reg_read(UC_ARM_REG_SP)==sp
 assert all(t.uc.reg_read(r)==0x12340000+i for i,r in enumerate(t.CALLEE))
 return t.uc.reg_read(t.R[0])
claims=[];claim_result=4;pending=None;polls=0;busy=0;rx=0;fault=None
transactions=[];current=None;lcd=[0]*(480*320);prints=[];minimum_sp=0x20041000
def claim(required,*_):assert not required;claims.append(claim_result);t.ret(claim_result)
t.stub('dma_claim_unused_channel',claim)
def timer(*_):t.ticks+=20;t.uc.reg_write(t.R[1],0);t.ret(t.ticks)
t.stub('time_us_64',timer);t.stub('clock_get_hz',lambda *_:t.ret(200000000))
t.stub('sleep_us',lambda *_:t.ret())
t.stubs[0x1000b954]=lambda dest,src,n,_:(t.uc.mem_write(dest,bytes(t.uc.mem_read(src,n))),t.ret(dest))
def window(x,y,x1,y1):
 global current
 assert 0<=x<=x1<480 and 0<=y<=y1<320
 current=[(x,y,x1,y1),bytearray()];transactions.append(current);t.ret()
t.stub('original_lcd_window',window)
def emit(data):
 assert current is not None and len(data)%2==0
 (x,y,x1,y1),collected=current;offset=len(collected)//2;collected.extend(data)
 assert len(collected)<=2*(x1-x+1)*(y1-y+1)
 for j in range(0,len(data),2):
  k=offset+j//2;xx=x+k%(x1-x+1);yy=y+k//(x1-x+1)
  lcd[yy*480+xx]=struct.unpack_from('>H',data,j)[0]
def spi(spi,p,n,_):assert word(SPI)&15==7;emit(t.uc.mem_read(p,n));t.ret(n)
t.stub('spi_write_blocking',spi)
def cstr(p):
 out=bytearray()
 while t.uc.mem_read(p,1)[0]:out+=t.uc.mem_read(p,1);p+=1
 return out.decode()
def printf(fmt,*regs):
 sp=t.uc.reg_read(UC_ARM_REG_SP)
 prints.append((cstr(fmt),list(regs)+[word(sp+i*4) for i in range(4)]));t.ret(123)
t.stubs[0x1000d544]=printf
def write(u,access,a,size,v,data):
 global pending,polls,busy,rx,minimum_sp
 sp=u.reg_read(UC_ARM_REG_SP);minimum_sp=min(minimum_sp,sp)
 assert sp>=0x20040000,hex(sp)
 if pending:
  p,n,snapshot=pending
  assert a+size<=p or a>=p+n,'Modified a DMA-owned scanline'
 if SPI+0x1000<=a<SPI+0x4000:
  alias=(a-SPI)//0x1000;target=a-alias*0x1000;old=word(target)
  put(target,old^v if alias==1 else old|v if alias==2 else old&~v)
 elif a in [SIO+20,SIO+24]:
  put(SIO+16,word(SIO+16)|v if a==SIO+20 else word(SIO+16)&~v)
 elif a in (DMA+0x3404,DMA+0x3414):
  assert v==1<<claim_result;put(a-0x3000,word(a-0x3000)&~v)
 elif a==DMA+0x400:assert v==1<<claim_result
 elif a==DMA+0x444:
  assert fault=='timeout' and v==1<<claim_result;pending=None;busy=rx=0
 elif a==DMA+claim_result*64+12:
  assert pending is None
  assert v&(3<<2)==1<<2 and v&(1<<4) and not v&((1<<5)|(1<<22))
  assert (v>>15)&63==16 and (v>>11)&15==claim_result and v&(1<<21)
  assert word(SPI)&15==15 and word(SPI+36)&2 and word(SPI+4)&2
  assert word(SIO+16)&(1<<8) and not word(SIO+16)&(1<<5)
  c=DMA+claim_result*64;p=word(c);n=word(c+8)*2
  assert word(c+4)==SPI+8 and n<=712 and p%2==0
  pending=(p,n,bytes(u.mem_read(p,n)));polls=3
def read(u,access,a,size,v,data):
 global pending,polls,busy,rx,fault
 if a==DMA+0x444:put(a,0)
 elif a==DMA+claim_result*64+12 and pending:
  polls-=1
  if polls or fault=='timeout':put(a,(word(a)&~(3<<29))|(1<<24));return
  p,n,snapshot=pending;assert bytes(u.mem_read(p,n))==snapshot
  wire=bytearray()
  for k in range(0,n,2):wire+=snapshot[k:k+2][::-1]
  error=fault=='error'
  emit(wire[:len(wire)//4*2] if error else wire)
  pending=None;put(a,(word(a)&~((3<<29)|(1<<24)))|((1<<29) if error else 0))
  busy=2;rx=2
 elif a==SPI+12:
  put(a,2|(4 if rx else 0)|(16 if busy else 0))
  if not rx and busy:busy-=1
 elif a==SPI+8:
  assert rx;rx-=1
wh=t.uc.hook_add(UC_HOOK_MEM_WRITE,write)
rh=t.uc.hook_add(UC_HOOK_MEM_READ,read)
def reset(ch=4,fail=None):
 global pending,polls,busy,rx,claim_result,fault,current
 pending=None;polls=busy=rx=0;claim_result=ch;fault=fail;current=None
 claims.clear();transactions.clear();prints.clear();lcd[:]=[0]*(480*320)
 t.uc.mem_write(0x2001f928,bytes(s['__video_bss_end']-0x2001f928))
 t.uc.mem_write(0x2001e25b,b'\xff')
 put(SPI,7);put(SPI+4,2);put(SPI+16,4);put(SPI+36,3);put(SIO+16,1<<5)
 put(DMA+0x404,0xaaf);put(DMA+0x414,0x55f)
def unchanged():
 assert pending is None and not rx and not busy
 assert (word(SPI),word(SPI+4),word(SPI+16),word(SPI+36))==(7,2,4,3)
 assert word(SIO+16)&(1<<5)
def expected(pixels,scale,region):
 w,h=(356,320) if scale==5 else (scale*80,scale*72) if 2<=scale<=4 else (160,144)
 left,top,right,bottom=region;out=[0]*(480*320)
 for y in range(top,bottom):
  for x in range(left,right):out[((320-h)//2+y)*480+(480-w)//2+x]=pixels[y*144//h*160+x*160//w]
 return out
rng=random.Random(240928);pixels=[rng.randrange(65536) for _ in range(23040)]
t.uc.mem_write(SRC,struct.pack('<23040H',*pixels))
for ch in [0,4,11,-1]:
 for scale,w,h in [(1,160,144),(2,160,144),(3,240,216),(4,320,288),(5,356,320)]:
  reset(ch)
  for region in [(0,0,w,h),(0,0,1,1),(5,7,8,9),(w-19,h-17,w,h)]:
   lcd[:]=[0]*(480*320)
   call(s['video_fast_region'],SRC,scale,*region)
   assert lcd==expected(pixels,scale,region),(ch,scale,region)
   unchanged()
  assert claims==[ch]
  if ch>=0:
   assert word(DMA+0x404)==0xaaf&~(1<<ch) and word(DMA+0x414)==0x55f&~(1<<ch)
print('PASS VIDEO16: every pixel at all scales, partial/narrow windows, DMA channel 0/4/11, no-channel fallback, no writes to in-flight scanline, SPI mode/clock restoration, IRQ isolation')
for error in ['error','timeout']:
 reset(4,error);region=(3,5,40,17)
 call(s['video_fast_region'],SRC,5,*region)
 assert lcd==expected(pixels,5,region);unchanged()
 assert t.uc.mem_read(s['channel_plus_one'],1)==b'\xff'
 assert word(s['transport'])==2
 assert len(transactions)==2 # Entire region safely redrawn, not a corrupt append.
print('PASS VIDEO16 fault handling: DMA error/5 ms timeout -> abort/drain -> whole-window redraw via original driver, subsequent fallback')

# Real full-frame and dirty-rectangle entrypoints, not a surrogate algorithm.
reset();call(s['video_fast_full'],SRC,5);unchanged()
assert lcd==expected(pixels,5,(0,0,356,320))
assert tuple(struct.unpack('<7I',t.uc.mem_read(s['latest'],28)))[0:3]==(0,113920,1)
baseline=lcd.copy();t.uc.mem_write(PREV,bytes(t.uc.mem_read(SRC,46080)));transactions.clear()
assert call(s['video_fast_changed'],SRC,PREV,5)==0 and not transactions
assert lcd==baseline
for y,x in [(0,0),(12,14),(60,80),(143,159)]:pixels[y*160+x]^=65535
t.uc.mem_write(SRC,struct.pack('<23040H',*pixels));transactions.clear()
sent=call(s['video_fast_changed'],SRC,PREV,5);unchanged()
assert 0<sent<100 and lcd==expected(pixels,5,(0,0,356,320)),sent
assert t.uc.mem_read(PREV,46080)==t.uc.mem_read(SRC,46080)
sample=struct.unpack('<7I',t.uc.mem_read(s['latest'],28))
assert sample[0]==1 and sample[1]==sent and sample[2]==len(transactions) and sample[5:]==(50000000,1)
# Core-0 serial wrapper: exact old PERF arguments + consistent extra sample.
fmt=0x2003e000;t.uc.mem_write(fmt,b'PERF TEST\0')
assert call(s['video_fast_perf'],fmt,11,59,19,12000,49000)==123
assert prints[0][1][:5]==[11,59,19,12000,49000]
assert prints[1][1]==list(sample)
put(s['sequence'],1);prints.clear();call(s['video_fast_perf'],fmt,11,59,19,12000,49000)
assert len(prints)==1
print('PASS original full/diff + telemetry: unchanged frame sends zero, sparse edits send <100 pixels, exact previous-buffer update, seqlock read, old PERF ABI')
print('STACK_BYTES_OBSERVED',0x20041000-minimum_sp)
print('FIRMWARE_SHA256',hashlib.sha256(Path(os.environ.get('SCARLET_VIDEO_UF2',str(ROOT/'releases/scarletpico-v2_2_2-video16-TEST.uf2'))).read_bytes()).hexdigest())
