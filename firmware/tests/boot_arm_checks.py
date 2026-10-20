"""Actual ARM boot/synthesis/mixer; simulated LCD, timer and DMA consumption.
No hardware writes. Called by the full firmware regression suite.
"""
import math,struct,wave
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_PC

def run_boot_checks(t,s,call,pixels,preview,build):
 BG=0x10a3;PCM=s['original_audio_pcm'];QUEUE=s['original_audio_queue']
 def patch_word(p,n):t.uc.mem_write(p,struct.pack('<I',n&0xffffffff))
 def signed(n):return n-0x100000000 if n>=0x80000000 else n
 # One clipped sprite strip at a time; compare moving vs standalone image.
 before_guard=bytes(t.uc.mem_read(PCM-8,8));after_guard=bytes(t.uc.mem_read(PCM+1072,8))
 t.uc.mem_write(PCM-8,b'\xa5'*8);t.uc.mem_write(PCM+1072,b'\x5a'*8)
 pixels[:]=[BG]*(480*320)
 old=-72
 for y in [-72,-35,0,30,90,124]:
  call('features_boot_draw',old&0xffffffff,y&0xffffffff);old=y
  assert all(c==BG for i,c in enumerate(pixels) if not (88<=i%480<392 and max(y,0)<=i//480<y+72))
  preview('boot-top' if y==0 else 'boot-middle' if y==90 else 'boot-center' if y==124 else 'boot-clipped')
 moved=pixels.copy();pixels[:]=[BG]*(480*320)
 call('features_boot_draw',124,124)
 assert pixels==moved and any(c!=BG for c in pixels)
 assert t.uc.mem_read(PCM-8,8)==b'\xa5'*8 and t.uc.mem_read(PCM+1072,8)==b'\x5a'*8
 # Source PCM is generated on the real CPU, in the already reserved scratch.
 source=[]
 for n in range(0,11520,128):
  call('features_chime_block',n)
  block=struct.unpack('<256h',t.uc.mem_read(PCM,512))
  assert block[::2]==block[1::2]
  source.extend(block[::2])
 assert source[0]==source[1343]==source[1344]==source[-1]==0
 assert max(map(abs,source))<=4800 and sum(x!=0 for x in source)>9500
 assert all(x==0 for x in source[11264:]) # Real silent tail before I2S stop.
 assert any(source[6400:9600]) # The second note no longer ends at 400 ms.
 # Measure actual ARM output, independently of the phase accumulator: two
 # nearly octave-spaced pitches and a pulse (not the previous triangle).
 def frequency(begin,end):
  positive=[];last=0
  for n in range(begin,end):
   if source[n]>0 and last<0:positive.append(n)
   if source[n]:last=source[n]
  return 16000*(len(positive)-1)/(positive[-1]-positive[0])
 low=frequency(64,1200);high=frequency(1400,4800)
 assert abs(low-1048.576)<3 and abs(high-2080.508)<3,(low,high)
 assert 1.97<high/low<2.00
 plateau=source[200:700]
 rms=lambda xs:math.sqrt(sum(x*x for x in xs)/len(xs))
 assert .85*max(map(abs,plateau))<rms(plateau)<=max(map(abs,plateau))
 assert rms(source[-320:])<rms(source[2000:3000])/4
 call('features_chime_block',11520)
 assert not any(t.uc.mem_read(PCM,512))
 assert t.uc.mem_read(PCM-8,8)==b'\xa5'*8 and t.uc.mem_read(PCM+1072,8)==b'\x5a'*8

 t.uc.mem_write(PCM-8,before_guard);t.uc.mem_write(PCM+1072,after_guard)
 samples=[];events=[];consume=True;elapsed_dma=0;capture_frames=False;frames=[];positions=[]
 sleep_address=s['sleep_ms']&~1;old_sleep=t.stubs[sleep_address]
 def sleep(n,*_):
  nonlocal elapsed_dma
  t.advance(n*1000)
  if consume and t.uc.mem_read(t.sym['playing'],1)[0]:
   elapsed_dma+=n*1000
   while elapsed_dma>=8000:
    elapsed_dma-=8000
    write=t.read32(QUEUE+2048);read=t.read32(QUEUE+2052)
    patch_word(QUEUE+2052,read+min(128,(write-read)&0xffffffff))
  t.ret()
 def queue_write(u,access,address,size,value,data):
  assert size==4
  left=value&65535;right=(value>>16)&65535;assert left==right
  samples.append(left-65536 if left>=32768 else left)
 def observe_audio(u,address,size,data):
  events.append((address,t.ticks))
 def observe_draw(u,address,size,data):
  positions.append((signed(u.reg_read(t.R[0])),signed(u.reg_read(t.R[1])),t.ticks))
 def observe_pixels_end(u,address,size,data):
  if capture_frames:frames.append((t.ticks,pixels.copy()))
 hooks=[t.uc.hook_add(UC_HOOK_MEM_WRITE,queue_write,begin=QUEUE,end=QUEUE+2047),
        t.uc.hook_add(UC_HOOK_CODE,observe_audio,begin=s['original_audio_start']&~1,end=s['original_audio_start']&~1),
        t.uc.hook_add(UC_HOOK_CODE,observe_audio,begin=s['original_audio_stop']&~1,end=s['original_audio_stop']&~1),
        t.uc.hook_add(UC_HOOK_CODE,observe_draw,begin=s['features_boot_draw']&~1,end=s['features_boot_draw']&~1),
        t.uc.hook_add(UC_HOOK_CODE,observe_pixels_end,begin=s['ui_pixels_end']&~1,end=s['ui_pixels_end']&~1)]
 t.stubs[sleep_address]=sleep
 t.stub('clock_get_hz',lambda *_:t.ret(125000000))
 t.sequence=[];t.set_keys(0)
 for volume in [0,50,100]:
  samples.clear();events.clear();elapsed_dma=0;t.ticks=0
  t.uc.mem_write(s['ui_volume'],bytes([volume]))
  assert call('features_boot_chime')==1
  if volume:
   assert len(samples)==11520
   expected=[int(x*volume/100) for x in source]
   assert samples==expected # The unchanged real signed PCM gain/mixer runs.
   assert t.uc.mem_read(t.sym['active'],1)==b'\0'
   assert t.read32(0x502000c8)==31250<<8 # I2S at the boot/menu clock.
   assert 720000<=t.ticks<=770000
   with wave.open(str(build/'previews'/f'boot-chime-{volume}.wav'),'wb') as f:
    f.setparams((1,2,16000,0,'NONE','not compressed'))
    f.writeframes(struct.pack('<11520h',*samples))
  else:assert not samples and not events and t.ticks==720000
 # Broken IRQ/DMA drains: bounded wait, audio off, boot can continue.
 consume=False;t.ticks=0;samples.clear()
 assert call('features_boot_chime')==0 and t.ticks<=110000
 assert t.uc.mem_read(t.sym['active'],1)==b'\0'
 consume=True
 address=s['original_audio_start']&~1
 t.stubs[address]=lambda *_:t.ret(0)
 samples.clear();t.ticks=0
 assert call('features_boot_chime')==0 and not samples and t.ticks==0
 t.stubs.pop(address)

 # Boot integration: restored settings BEFORE drawing/chime, single initial
 # screen clear; final centered pose is reached before the sound starts.
 record=0x20044000
 for volume in [0,50]:
  p=bytearray(b'SPUI\x01\x01'+bytes([volume,60]));p+=bytes(x^255 for x in p)
  t.uc.mem_write(record,bytes(p)+bytes(16));t.ticks=0;t.sequence=[];t.set_keys(0)
  elapsed_dma=0;samples.clear();events.clear();positions.clear();frames.clear()
  t.rects.clear();t.erase_ops.clear();t.program_ops.clear()
  capture_frames=volume==50
  before_core=bytes(t.uc.mem_read(0x20003600,0xc324))
  before_apu=bytes(t.uc.mem_read(0x2001f2c0,312))
  call('features_boot_ui_init',record)
  capture_frames=False
  assert bytes(t.uc.mem_read(s['ui_settings'],3))==bytes([1,volume,60])
  assert t.read32(0x40050000+5*20+12)&65535==600
  assert not t.erase_ops and not t.program_ops
  assert t.rects==[(0,0,480,320)]
  assert positions[-1][1]==124 and all(-72<=p[1]<=124 for p in positions)
  assert all(b[1]>=a[1] for a,b in zip(positions,positions[1:]))
  assert 2870000<=t.ticks<=2940000
  if volume:assert len(samples)==11520 and events[0][1]>=positions[-1][2]
  else:assert not samples and not events
  assert bytes(t.uc.mem_read(0x20003600,0xc324))==before_core
  assert bytes(t.uc.mem_read(0x2001f2c0,312))==before_apu
  preview('boot-final')
  if volume:
   # Actual ARM frame sequence, for optional GIF preview without a second UI.
   out=build/'previews/boot-frames';out.mkdir(exist_ok=True)
   for i,(ticks,frame) in enumerate(frames):
    rgb=bytearray()
    for c in frame:rgb.extend(((c>>11)*255//31,((c>>5)&63)*255//63,(c&31)*255//31))
    (out/f'{i:03d}-{ticks}.ppm').write_bytes(b'P6\n480 320\n255\n'+rgb)
 # Start skips at power-on or mid-descent; releases cannot launch a game.
 for begin,end in [(0,300000),(600000,900000)]:
  t.ticks=0;t.sequence=[(begin,end,8)];t.set_keys(8 if begin==0 else 0)
  samples.clear();events.clear();positions.clear()
  call('features_boot_ui_init',record)
  assert not samples and not events and positions[-1][1]==124
  assert end<=t.ticks<end+100000
  assert t.read32(0xd0000004)&(1<<27)
 # Real boot caller: patched settings-init BL then original missing-card UI.
 # Recovery/retry still works after one splash, even with volume zero.
 p=bytearray(b'SPUI\x01\x00\x00\x64');p+=bytes(x^255 for x in p)
 t.uc.mem_write(0x1007f000,bytes(p)+bytes(16))
 t.ticks=0;t.sequence=[(3300000,3400000,1)];t.set_keys(0);t.mounts[:]=[1]
 samples.clear();positions.clear()
 s['test_boot_display']=t.sym['ui_boot_display'];call('test_boot_display',0)
 assert t.uc.reg_read(t.R[0])==1 and not t.mounts and not samples
 assert positions[-1][1]==124 and sum(y==124 for _,y,_ in positions)==1

 # Run the original main loop with the NEW boot hook all the way through
 # DOWN -> A, stopping immediately before the selected game is loaded.
 t.ticks=0;t.sequence=[(3400000,3470000,128),(3650000,3730000,1)]
 t.set_keys(0);t.write32(0x2001e220,0);positions.clear();t.mounts[:]=[]
 t.install_stubs();t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
 t.uc.emu_start(0x10007835,0x10007c72,count=100000000)
 assert t.uc.reg_read(UC_ARM_REG_PC)==0x10007c72
 assert t.read32(0x2001e220)==1
 assert positions[-1][1]==124 and sum(y==124 for _,y,_ in positions)==1

 for hook in hooks:t.uc.hook_del(hook)
 t.stubs[sleep_address]=old_sleep
 t.stub('clock_get_hz',lambda *_:t.ret(200000000))
 t.sequence=[];t.set_keys(0);call('features_ui_init',0)
 print('PASS boot: clipped/centred capsule, no trails, one full clear, 1.8 s descent, Start skip/release, missing-card recovery, core/APU untouched')
 print('PASS chime: actual ARM synthesis + unchanged mixer at 0/50/100%, 11520 frames, longer decay + silent tail, scratch guards, bounded DMA/start failure, audio shutdown')
