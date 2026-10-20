"""Execute DMA addon and the original game's scaled-row renderer on ARM.
Peripheral DMA/SPI timing is simulated; these are NOT physical FPS results.
"""
from pathlib import Path
import hashlib,os,random,struct
os.environ['SCARLET_TEST_FIRMWARE']=str(Path(__file__).resolve().parents[1]/'build-loader-addon/patched.bin')
os.environ['SCARLET_TEST_UI_ELF']=str(Path(__file__).resolve().parents[1]/'build-ui-addon/ui.elf')
import test_ui_arm as t
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-video-dma-addon'
with (BUILD/'video.elf').open('rb') as f:
 elf=ELFFile(f);s={x.name:x['st_value'] for x in elf.get_section_by_name('.symtab').iter_symbols()}
t.uc.mem_write(0x10000000,(BUILD/'patched.bin').read_bytes())
t.uc.ctl_remove_cache(0x10000000,0x10200000)
SPI=0x4003c000;DMA=0x50000000;SRC=0x20030000
def word(p):return t.read32(p)
def put(p,x):t.write32(p,x)
pack=lambda x:struct.pack('<I',x)
def call(address,*args):
 t.install_stubs();sp=0x20042000
 t.uc.reg_write(UC_ARM_REG_SP,sp);t.uc.reg_write(UC_ARM_REG_LR,t.RETURN|1)
 for i,r in enumerate(t.R):t.uc.reg_write(r,args[i] if i<len(args) else 0)
 for i,x in enumerate(args[4:]):put(sp+4*i,x)
 for i,r in enumerate(t.CALLEE):t.uc.reg_write(r,0x12340000+i)
 t.uc.emu_start(address|1,t.RETURN,count=10000000)
 assert t.uc.reg_read(UC_ARM_REG_PC)==t.RETURN
 assert t.uc.reg_read(UC_ARM_REG_SP)==sp
 assert all(t.uc.reg_read(r)==0x12340000+i for i,r in enumerate(t.CALLEE))
 return t.uc.reg_read(t.R[0])

claims=[];claim_result=4;payloads=[];fallback=[];transactions=[];current=None
pending=None;remaining_polls=0;busy_polls=0;rx_words=0
def claim(required,*_):
 assert not required;claims.append(claim_result);t.ret(claim_result)
t.stub('dma_claim_unused_channel',claim)
def emit(data):
 payloads.append(bytes(data))
 if current is not None:current[1].extend(data)
def blocking(spi,p,n,_):
 fallback.append((spi,p,n));emit(t.uc.mem_read(p,n));t.ret(n)
t.stub('spi_write_blocking',blocking)
def window(x,y,x1,y1):
 global current
 assert 0<=x<=x1<480 and 0<=y<=y1<320
 current=[(x,y,x1,y1),bytearray()];transactions.append(current);t.ret()
t.stub('original_lcd_window',window)
t.stub('sleep_us',lambda *_:t.ret())
def dma_write(u,access,a,size,v,data):
 global pending,remaining_polls
 if a in (DMA+0x3404,DMA+0x3414):
  assert v==1<<claim_result
  put(a-0x3000,word(a-0x3000)&~v)
 elif a==DMA+0x400:
  assert v==1<<claim_result
 elif DMA<=a<DMA+12*64 and (a-DMA)%64==12:
  ch=(a-DMA)//64
  assert ch==claim_result and pending is None
  assert (v>>15)&63==16 and (v>>11)&15==ch
  assert v&1 and v&(1<<4) and v&(1<<21)
  assert v&((1<<1)|(3<<2)|(1<<5)|(15<<6)|(1<<10)|(1<<22))==0
  c=DMA+ch*64
  assert word(c+4)==SPI+8 and word(SPI+0x24)&2
  p=word(c);n=word(c+8)
  assert 32<=n<=960
  pending=(p,n);remaining_polls=3
def hw_read(u,access,a,size,v,data):
 global pending,remaining_polls,busy_polls,rx_words
 if a==DMA+claim_result*64+12 and pending:
  remaining_polls-=1
  if remaining_polls:
   put(a,(word(a)&~(3<<29))|(1<<24))
  else:
   p,n=pending;emit(u.mem_read(p,n));pending=None
   put(a,word(a)&~((3<<29)|(1<<24)))
   put(a-12,p+n);put(a-4,0)
   busy_polls=2;rx_words=2
 elif a==SPI+12:
  # Finish SPI *after* DMA, with a receive FIFO that needs draining.
  put(a,2|(4 if rx_words else 0)|(16 if busy_polls else 0))
  if not rx_words and busy_polls:busy_polls-=1
 elif a==SPI+8:
  assert rx_words;rx_words-=1
write_hook=t.uc.hook_add(UC_HOOK_MEM_WRITE,dma_write,begin=DMA,end=DMA+0x3fff)
read_hook=t.uc.hook_add(UC_HOOK_MEM_READ,hw_read)

def reset_driver(ch=4):
 global pending,remaining_polls,busy_polls,rx_words,claim_result,current
 claim_result=ch;pending=None;remaining_polls=busy_polls=rx_words=0;current=None
 t.uc.mem_write(s['channel_plus_one'],b'\0')
 claims.clear();fallback.clear();payloads.clear();transactions.clear()
 put(SPI,7);put(SPI+4,2);put(SPI+0x10,4);put(SPI+0x24,3)
 put(DMA+0x404,0xaaf);put(DMA+0x414,0x55f)

reset_driver()
for n in [0,1,2,31,32,33,128,712,960,961]:
 data=bytes((i*73+19)%256 for i in range(n));t.uc.mem_write(SRC,data)
 before=len(payloads)
 assert call(s['video_dma_write'],SPI,SRC,n)==n
 assert b''.join(payloads[before:])==data
 assert pending is None and not busy_polls and not rx_words
 assert word(SPI)==7 and word(SPI+4)==2 and word(SPI+0x10)==4 and word(SPI+0x24)==3
assert claims==[4]
assert [n for _,_,n in fallback]==[0,1,2,31,961]
assert word(DMA+0x404)==0xaaf&~16 and word(DMA+0x414)==0x55f&~16
# Unaligned source works because DMA is deliberately byte-sized.
t.uc.mem_write(SRC+1,bytes(range(128)));assert call(s['video_dma_write'],SPI,SRC+1,128)==128
assert payloads[-1]==bytes(range(128))
assert call(s['video_dma_write'],SPI+0x4000,SRC,128)==128
assert fallback[-1][0]==SPI+0x4000
# No spare channel: don't panic, don't retry claims per row, keep old path.
reset_driver(-1)
dma_before=bytes(t.uc.mem_read(DMA,0x440))
for _ in range(5):assert call(s['video_dma_write'],SPI,SRC,712)==712
assert claims==[-1] and len(fallback)==5 and bytes(t.uc.mem_read(DMA,0x440))==dma_before
print('PASS DMA ARM: byte order/length, unaligned input, SPI register restoration, ABI, FIFO drain after DMA, IRQ isolation, no-channel fallback, one channel per boot')

# Exercise both patched call sites in the actual original renderer, with
# native -> full-height scaling, repeated rows and small changed regions.
reset_driver()
rng=random.Random(937)
pixels=[rng.randrange(65536) for _ in range(160*144)]
t.uc.mem_write(SRC,struct.pack('<23040H',*pixels))
for scale,width,height in [(1,160,144),(2,160,144),(3,240,216),(4,320,288),(5,356,320)]:
 # scale 1 (native/default) and scale 2 (1x) both map to 160x144.
 regions=[(0,0,width,height),(2,3,8,7),(width-17,height-15,width,height)]
 for left,top,right,bottom in regions:
  transactions.clear();payloads.clear()
  call(0x100004a8,SRC,scale,left,top,right,bottom)
  assert len(transactions)==1
  (x,y,x1,y1),actual=transactions[0]
  assert (x,y,x1,y1)==((480-width)//2+left,(320-height)//2+top,(480-width)//2+right-1,(320-height)//2+bottom-1)
  expected=bytearray()
  for yy in range(top,bottom):
   for xx in range(left,right):expected+=struct.pack('>H',pixels[(yy*144//height)*160+xx*160//width])
  assert actual==expected,(scale,left,top,len(actual),len(expected))
  assert pending is None and not busy_polls and not rx_words
assert claims==[4]
print('PASS original renderer + new transport: all pixels/window bounds match at 160x144, 240x216, 320x288, 356x320; full and partial regions, both row-write hooks')
print('FIRMWARE_SHA256',hashlib.sha256((ROOT/'releases/scarletpico-v2_2_1-video-dma-TEST.uf2').read_bytes()).hexdigest())
