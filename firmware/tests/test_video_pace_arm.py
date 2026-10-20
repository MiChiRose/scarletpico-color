"""Execute new ARM scheduler + original main branches; timing is MODELLED.
Physical FPS/audio are not inferred from this test. No device access.
"""
from pathlib import Path
import hashlib, struct, sys, os
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build-video-pace-addon'
raw = Path(os.environ.get('SCARLET_PACE_IMAGE',str(BUILD/'patched.bin'))).read_bytes()
sys.path.insert(0,str(ROOT/'tools'))
from uf2_audio_patch import bl
with (BUILD/'pace.elf').open('rb') as f:
    elf = ELFFile(f)
    sym = {s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
u.mem_map(0x10000000, 0x200000); u.mem_write(0x10000000, raw)
# Mock feature callback's continuation: execute the REAL queue wrapper after
# modelled frame cost, then return success. No re-entrant emu_start callbacks.
CONTINUE=0x1007f100
u.mem_write(CONTINUE,bytes.fromhex('10b5')+bl(CONTINUE+2,sym['video_pace_audio_submit'])+
            bytes.fromhex('012010bd'))
u.mem_map(0x20000000, 0x42000)
R = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
SAVED = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R8,
         UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]
SP = 0x20041000
END = 0x1007fff0
QWRITE, QREAD, UNDERRUN, DROPPED = 0x2001ee80, 0x2001ee84, 0x2001e268, 0x2001e264
def word(a): return struct.unpack('<I', u.mem_read(a,4))[0]
def put(a,x): u.mem_write(a,struct.pack('<I',x&0xffffffff))
def ret(x=0):
    u.reg_write(R[0],x&0xffffffff); u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def cstr(p):
    b=bytearray()
    while u.mem_read(p,1)[0]: b+=u.mem_read(p,1);p+=1
    return b.decode()
now=0; rcost=18800; scost=5500; video_time=0; video_done=0
frame_calls=[]; submits=[]; prints=[]; ready_calls=0; result=True; pause=False
dma_at=None; fraction=0; model_audio=False
audio_submits=[]
def advance(target):
    global now,dma_at
    if model_audio and dma_at is not None:
        while dma_at<=target:
            n=min(128,word(QWRITE)-word(QREAD))
            put(QREAD,word(QREAD)+n)
            if n<128: put(UNDERRUN,word(UNDERRUN)+1)
            dma_at+=8000
    now=target
def submit_audio(pcm,frames):
    global dma_at
    audio_submits.append((pcm,frames))
    n=min(frames,512-(word(QWRITE)-word(QREAD)))
    put(QWRITE,word(QWRITE)+n);put(DROPPED,word(DROPPED)+frames-n)
    if dma_at is None and word(QWRITE)-word(QREAD)>=256:
        put(QREAD,word(QREAD)+256);dma_at=now+8000;u.mem_write(0x2001e26d,b'\1')
def hook(u,a,size,data):
    global ready_calls,video_done,fraction
    if a==0x10009e3c:
        u.reg_write(R[1],now>>32);ret(now)
    elif a==0x10034134:
        keys,draw=[u.reg_read(r) for r in R[:2]]
        assert draw in (0,1)
        if pause:
            draw=1;u.mem_write(0x2001f923,b'\0')
            advance(now+2000000) # time in menu must not poison estimates
        frame_calls.append((keys,draw))
        advance(now+(rcost if draw else scost))
        if result:
            u.mem_write(0x2001f2bc,b'\1')
            if model_audio:
                u.mem_write(0x2001e26e,b'\1')
                fraction+=16000*70224
                frames=fraction>>22;fraction&=4194303
                u.reg_write(R[0],0x2001ee88);u.reg_write(R[1],frames)
                u.reg_write(UC_ARM_REG_PC,CONTINUE|1);return
        ret(int(result))
    elif a==0x1002ec38:
        submit_audio(u.reg_read(R[0]),u.reg_read(R[1]));ret()
    elif a==0x10009b68:
        assert u.reg_read(R[1])==0
        advance(now+u.reg_read(R[0]));ret()
    elif a==0x10008bd4:
        ready_calls+=1;ret(int(now>=video_done))
    elif a==0x10008c44:
        assert now>=video_done
        submits.append(now);video_done=now+video_time;ret(1)
    elif a==0x1000a08c: assert u.reg_read(R[0])==5;ret(200000000)
    elif a==0x1000aab0:
        x,y=[u.reg_read(r) for r in R[:2]]
        assert y;u.reg_write(R[1],x%y);ret(x//y)
    elif a==0x10036428:
        sp=u.reg_read(UC_ARM_REG_SP)
        prints.append(('PREVIOUS', [u.reg_read(r) for r in R]+[word(sp),word(sp+4)]));ret(123)
    elif a==0x1000d544:
        sp=u.reg_read(UC_ARM_REG_SP)
        prints.append((cstr(u.reg_read(R[0])),[u.reg_read(r) for r in R[1:]]+
                       [word(sp+i*4) for i in range(10)]));ret(456)
for address in [0x10009e3c,0x10034134,0x10008bd4,0x10008c44,0x1000a08c,
                0x1000aab0,0x10036428,0x1000d544,0x1002ec38,0x10009b68]:
    u.hook_add(UC_HOOK_CODE,hook,begin=address,end=address)
def reset():
    global now,video_done,ready_calls,result,pause,dma_at,fraction,model_audio
    now=video_done=ready_calls=fraction=0;result=True;pause=False;dma_at=None;model_audio=False
    frame_calls.clear();submits.clear();prints.clear();audio_submits.clear()
    u.mem_write(0x20000000,bytes(0x42000))
def tick(due,waiting=0,keys=0):
    """Execute real main argument setup, patched call, return/error branches,
    pending check and original submit path. R7 must track actual buffer state."""
    u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_R7,waiting)
    for i,r in enumerate(SAVED):u.reg_write(r,0x12340000+i)
    put(SP+48,due);put(SP+88,keys);put(SP+104,now);put(SP+108,now>>32)
    u.emu_start(0x10008091,0x100080d6 if result else 0x100082ea,count=100000)
    assert u.reg_read(UC_ARM_REG_PC)==(0x100080d6 if result else 0x100082ea)
    assert u.reg_read(UC_ARM_REG_SP)==SP
    assert all(u.reg_read(r)==0x12340000+i for i,r in enumerate(SAVED))
    return u.reg_read(UC_ARM_REG_R7)

reset();video_time=0
assert tick(0)==0 and frame_calls==[(255,1)] and len(submits)==1
# Deadline miss: game/audio still run, but no unrendered buffer submission and
# no false frame_waiting carried into the following iteration.
advance(100000);before=ready_calls
put(sym['pace']+40,9000)
assert tick(0,keys=1)==0 and frame_calls[-1]==(254,0)
assert len(submits)==1 and ready_calls==before
# An older waiting frame survives skipped rendering, including a busy LCD.
video_done=now+100000
assert tick(now,waiting=1)==1 and frame_calls[-1]==(255,0)
video_done=0
assert tick(now,waiting=1)==0 and len(submits)==2
# Pause recreates buffers and forces a valid first picture even if the
# caller's old flag said there was already a waiting frame.
pause=True;u.mem_write(0x2001f923,b'\1')
assert tick(0,waiting=1)==0 and frame_calls[-1][1]==1 and len(submits)==3
pause=False;result=False
assert tick(now)==0 and len(submits)==3
print('PASS real main ABI: success/failure, deadline skip, no phantom submit, pending-buffer preservation, busy worker, forced pause refresh, stack and live registers')

# Wrap-safe use of the original 64-bit timer's lower half (wrap every ~71 min).
reset();now=(1<<32)-1000
assert tick(now)==0
assert tick(now)==0 and frame_calls[-1][1]==1
assert word(sym['pace']+28)==0
print('PASS timer-low wrap and new-session reset')

# Load profiles exercise the actual machine code, not a rewritten policy.
# The DMA model follows the existing 128-sample/8ms block-refill contract.
for rcost,scost in [(11000,4000),(18800,5500),(25000,8000),(38000,12000),(21000,18000)]:
    reset();model_audio=True;video_time=0;due=0;steady_underruns=0
    for i in range(900):
        advance(max(now,due))
        assert tick(due,keys=i&255)==0
        due+=16743
        if i==119:steady_underruns=word(UNDERRUN)
    speed=900*1e6/now;draws=sum(draw for _,draw in frame_calls)
    print('MODEL raw render',rcost,'skip',scost,'draws',draws,'EMU',speed,
          'underruns',word(UNDERRUN),'steady',word(UNDERRUN)-steady_underruns,'dropped',word(DROPPED))
    assert len(frame_calls)==900 and [k for k,_ in frame_calls]==[(~i)&255 for i in range(900)]
    assert len(submits)==draws
    assert len(audio_submits)==900
    assert word(DROPPED)==0
    assert word(sym['pace']+36)==0 # no wait timeout with a consuming device
    if rcost==11000:assert draws>=898 # startup audio reserve, no fixed cap
    if rcost==18800:assert speed>=59.5 and draws>450
    if scost<16743:assert speed>=59.4
    assert draws>=900//13 # no permanent visual starvation
    print('MODEL ONLY render_us',rcost,'skip_us',scost,'EMU',round(speed,2),
          'draws',draws,'steady_underruns',word(UNDERRUN)-steady_underruns)
print('PASS workload adaptation: all game/audio ticks retained; fast scenes uncapped; overloaded logic is not misreported as full speed')

# Never starve graphics after an exceptionally expensive rendered frame.
reset();rcost=45000;scost=4000;due=0
for _ in range(160):
    advance(max(now,due));tick(due);due+=16743
assert sum(d for _,d in frame_calls)>=5
print('PASS costly scenes resume drawing after timing recovery')

def call_audio(frames=267):
    u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,END|1)
    u.reg_write(R[0],0x2001ee88);u.reg_write(R[1],frames)
    u.emu_start(sym['video_pace_audio_submit']|1,END,count=100000)
    assert u.reg_read(UC_ARM_REG_PC)==END and u.reg_read(UC_ARM_REG_SP)==SP
# DMA stalled: bounded fallback, never a frozen foreground or disabled IRQs.
reset();u.mem_write(0x2001e26d,b'\1\1');put(QWRITE,512)
call_audio();assert now==24000 and word(sym['pace']+36)==1
assert len(audio_submits)==1 and word(DROPPED)==267
for active,playing in [(0,0),(1,0),(0,1)]:
    reset();u.mem_write(0x2001e26d,bytes([playing,active]));put(QWRITE,512)
    call_audio();assert now==0
# Counters wrap, but occupancy and 24ms timeout remain unsigned-correct.
reset();now=(1<<32)-100;u.mem_write(0x2001e26d,b'\1\1')
put(QWRITE,256);put(QREAD,0xffffff00)
call_audio();assert now==(1<<32)-100+24000 and word(sym['pace']+36)==1
print('PASS real audio enqueue wrapper: exact PCM pointer/count, startup/inactive bypass, stalled-DMA timeout, timer and ring-counter wrap')

# Existing PERF ABI and audio metrics include real CPU clock and raw counters;
# no sound-register writes, queue consumption or fabricated LCD FPS.
reset();rcost=11000;scost=4000;tick(0)
put(QWRITE,800);put(QREAD,512);put(UNDERRUN,7);put(DROPPED,3)
u.mem_write(0x20030000,b'PERF TEST\0');u.mem_write(0x20030100,b'FIT HEIGHT\0')
u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,END|1)
for r,value in zip(R,[0x20030000,0x20030100,59,40]):u.reg_write(r,value)
put(SP,12345);put(SP+4,23456)
u.emu_start(sym['video_pace_perf']|1,END,count=100000)
assert u.reg_read(UC_ARM_REG_PC)==END and u.reg_read(R[0])==123
assert prints[0]==('PREVIOUS',[0x20030000,0x20030100,59,40,12345,23456])
assert prints[1][0].startswith('PACE cpu=')
assert prints[1][1]==[200000000,1,0,0,11000,0,0,288,7,3,0,0,0],prints[1]
assert (word(QWRITE),word(QREAD),word(UNDERRUN),word(DROPPED))==(800,512,7,3)
assert not any(u.mem_read(sym['pace'],40))
print('PASS telemetry ABI, actual clock/audio counters, interval reset')
print('FIRMWARE_SHA256',hashlib.sha256(Path(os.environ.get('SCARLET_PACE_UF2',str(ROOT/'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2'))).read_bytes()).hexdigest())
