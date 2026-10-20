"""Exact release ARM: full previous regressions + live pause/settings lifecycle.
GPIO/flash/SPI/DMA/watchdog are mocked; physical sound/FPS are not measured.
"""
import os, hashlib
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build-pause-ui-addon'
RELEASE=Path(os.environ.get('SCARLET_FEATURE_UF2',str(ROOT/'releases/scarletpico-v2_2_2-PAUSE-SETTINGS-TEST.uf2')))
os.environ.setdefault('SCARLET_FEATURE_IMAGE',str(BUILD/'patched.bin'))
os.environ.setdefault('SCARLET_FEATURE_UF2',str(RELEASE))
os.environ['SCARLET_BOTTOM_FPS']='1'
import test_video_pace_features_arm as p
f=p.f;t=f.t
with (BUILD/'pause-ui.elf').open('rb') as stream:
    e=ELFFile(stream)
    s={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols()}
# Keep the old public entrypoints: tests must exercise the actual trampolines.
# Only map private page helpers to the newly linked implementation.
for n in ['pause_draw','pause_row','slots_draw']:f.s[n]=s[n]
f.BUILD=BUILD
for lang in [0,1]:
    t.uc.mem_write(f.s['ui_settings'],bytes([lang]));f.text_calls.clear()
    f.CALL('pause_draw',3)
    assert len([x for x in f.text_calls if x[0]==44])==5
    assert any(x[2]==('НАСТРОЙКИ' if lang else 'SETTINGS') for x in f.text_calls)
    f.preview('pause-settings-ru' if lang else 'pause-settings-en')
    t.rects.clear();f.CALL('pause_row',3,4);f.CALL('pause_row',4,4)
    assert sum(r[2:]==(448,32) for r in t.rects)==2
    assert (0,0,480,320) not in t.rects

# Actual colours used on the small pixel display; do not introduce a new theme.
def luminance(c):
    rgb=[((c>>11)&31)/31,((c>>5)&63)/63,(c&31)/31]
    v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
    return .2126*v[0]+.7152*v[1]+.0722*v[2]
for fg,bg in [(0xf79e,0x10a3),(0xf79e,0x18e5),(0x4e98,0x10a3),(0xfa6c,0x18e5)]:
    a,b=sorted((luminance(fg),luminance(bg)))
    assert (b+.05)/(a+.05)>=4.5
print('PASS pause page: five RU/EN rows fit, selection-only repaint, text/accent contrast >=4.5')

t.sequence=[];t.set_keys(0);f.CALL('features_ui_init',0)
t.uc.mem_write(0x10081000,f.zelda)
assert f.CALL('features_load',0x10081000,len(f.zelda),0)==1
for _ in range(5):assert f.CALL('features_frame',255,0)==1
game_before=bytes(t.uc.mem_read(f.CORE,f.CORE_SIZE))
apu_before=bytes(t.uc.mem_read(f.APU,f.APU_SIZE))
fraction_before=t.read32(t.sym['sample_remainder'])
save_ptr=t.read32(0x2001db8c);save_size=t.read32(0x2001dcb0)
save_before=bytes(t.uc.mem_read(save_ptr,save_size))
state={'video':True,'guard':False,'resumes':0,'frames':0}
def guard_pause(*_):state['guard']=True;t.ret(1)
def guard_resume(value,*_):assert value==1;state['guard']=False;t.ret()
def stop(*_):state['video']=False;t.ret()
def start(scale,*_):assert scale==5;state['video']=True;state['resumes']+=1;t.ret(1)
def frame(keys,render,*_):
    assert keys==255 and render==1
    assert state['video'] and not state['guard']
    assert bytes(t.uc.mem_read(f.CORE,f.CORE_SIZE))==game_before
    assert bytes(t.uc.mem_read(f.APU,f.APU_SIZE))==apu_before
    assert t.read32(t.sym['sample_remainder'])==fraction_before
    assert bytes(t.uc.mem_read(save_ptr,save_size))==save_before
    state['frames']+=1;t.ret(1)
def erase(off,n,*_):
    assert off==0x7f000 and n==4096 and not state['video'] and state['guard']
    assert not t.uc.mem_read(0x2001e26e,1)[0] # I2S stopped before XIP erase
    t.erase(off,n)
def program(off,ptr,n,*_):
    assert off==0x7f000 and n==256 and not state['video'] and state['guard']
    t.program(off,ptr,n,0)
t.stub('original_guard_pause',guard_pause);t.stub('original_guard_resume',guard_resume)
t.stub('original_video_stop',stop);t.stub('original_video_start',start)
t.stub('original_addon_frame',frame)
t.stub('original_flash_erase',erase);t.stub('original_flash_program',program)
# Snapshot meaningful core/APU state at the page boundaries, not only after
# resume. This catches accidental loader/reset calls during settings navigation.
rows=[];settings_pages=[]
def page_hook(u,a,size,_):
    assert state['guard'] and not state['video']
    assert bytes(u.mem_read(f.CORE,f.CORE_SIZE))==game_before
    assert bytes(u.mem_read(f.APU,f.APU_SIZE))==apu_before
    if a==(f.s['feature_settings']&~1):settings_pages.append(t.ticks)
def row_hook(u,a,size,_):rows.append((t.ticks,u.reg_read(t.R[0]),u.reg_read(t.R[1])))
hooks=[t.uc.hook_add(UC_HOOK_CODE,page_hook,begin=f.s['feature_settings']&~1,end=f.s['feature_settings']&~1),
       t.uc.hook_add(UC_HOOK_CODE,row_hook,begin=s['pause_row']&~1,end=s['pause_row']&~1)]
def key_sequence(keys,start=60000):
    return [(start+i*120000,start+i*120000+60000,k) for i,k in enumerate(keys)]
def pause_with(seq):
    t.ticks=0;t.sequence=seq;t.set_keys(0);t.rects.clear()
    t.uc.mem_write(f.s['pause_pending'],b'\1');t.uc.mem_write(f.s['exit_requested'],b'\0')
    assert f.CALL('video_pace_frame',255,0,0)==3
    assert not t.uc.mem_read(f.s['pause_pending'],1)[0]
    assert t.read32(p.p['pace']+40)==0 # no pacing debt from minutes in settings
    t.sequence=[];t.set_keys(0)

# Down x3 -> Settings. Increase volume 50->60, brightness 100->90.
# Hold B for a full second; it must not propagate to Pause -> Resume.
seq=key_sequence([128,128,128,1,128,16,128,32])
seq += [(1100000,2100000,2),(2250000,2310000,2)]
t.erase_ops.clear();t.program_ops.clear();rows.clear();settings_pages.clear()
before_clocks=len(f.clock_calls)
print('CHECK live pause -> settings -> volume/brightness -> held B -> resume',flush=True)
pause_with(seq)
assert t.ticks>=2340000 and state['frames']==1 and state['resumes']==1
assert len(settings_pages)==1
assert bytes(t.uc.mem_read(f.s['ui_settings'],3))==bytes([0,60,90])
assert t.uc.mem_read(f.s['ui_volume'],1)==b'\x3c'
assert t.read32(0x40050000+5*20+12)&65535==900
assert t.erase_ops==[(0x7f000,4096)] and t.program_ops==[(0x7f000,256)]
assert len(f.clock_calls)==before_clocks
# Pause -> Settings -> Pause -> game clear, never a full repaint on arrows.
assert sum(r==(0,0,480,320) for r in t.rects)==4
assert [r[1] for r in rows[5:11]]==[0,1,1,2,2,3]
assert [r[2] for r in rows[-5:]]==[3]*5 # focus retained when returning
f.CALL('features_ui_init',0x1007f000)
assert bytes(t.uc.mem_read(f.s['ui_settings'],3))==bytes([0,60,90])
print('PASS live settings: real Zelda core/APU/save RAM/fraction unchanged, 60% gain and 90% PWM, one safe settings-sector write, release latch, focus retained, no clock writes, fresh first frame, pacer debt reset')

# Reopen and leave without changes: no flash wear and no game reset.
t.erase_ops.clear();t.program_ops.clear()
pause_with(key_sequence([128,128,128,8,2,2]))
assert not t.erase_ops and not t.program_ops
assert state['frames']==2

# RU settings, clamp lower/upper bounds using held directions/repeat. Repeated
# input still only repaints the changed row. Back goes to translated pause.
t.uc.mem_write(f.s['ui_settings'],bytes([1,60,90]))
seq=key_sequence([128,128,128,1,128])
seq += [(700000,3000000,32),(3150000,5400000,16),(5550000,5610000,128),
        (5750000,8000000,32),(8150000,8350000,2),(8600000,8700000,2)]
minimum=[100,100];maximum=[0,0]
def bounds_hook(u,a,size,_):
    volume,bright=bytes(u.mem_read(f.s['ui_settings']+1,2))
    assert 0<=volume<=100 and volume%10==0 and 10<=bright<=100 and bright%10==0
    minimum[0]=min(minimum[0],volume);minimum[1]=min(minimum[1],bright)
    maximum[0]=max(maximum[0],volume);maximum[1]=max(maximum[1],bright)
    if t.ticks>7000000 and bright==10:f.preview('in-game-settings-ru')
h=t.uc.hook_add(UC_HOOK_CODE,bounds_hook,begin=f.s['features_settings_key']&~1,end=f.s['features_settings_key']&~1)
pause_with(seq);t.uc.hook_del(h)
assert minimum==[0,10] and maximum[0]==100
assert bytes(t.uc.mem_read(f.s['ui_settings'],3))==bytes([1,100,10])
assert t.read32(0x40050000+5*20+12)&65535==100
assert state['frames']==3 and len(f.clock_calls)==before_clocks
print('PASS real RU in-game settings: held-key repeats, volume 0..100, brightness 10..100, persisted config, unchanged core, no-op exit does not write flash')

# Five-row wrap and exit confirm: UP now lands on row 4 (not Settings).
# Cancel returns to pause; B resumes. A on confirmed exit does not resume.
pause_with(key_sequence([64,1,2,2]));assert state['frames']==4
pause_with(key_sequence([64,1,1]))
assert t.uc.mem_read(f.s['exit_requested'],1)==b'\1'
assert state['frames']==4 and not state['video'] and not state['guard']
assert f.CALL('features_buttons',0)==256
assert not t.uc.mem_read(f.s['exit_requested'],1)[0]
for h in hooks:t.uc.hook_del(h)
print('PASS new five-row pause navigation: Start opens settings, B release, UP wraps to library, exit cancel/confirm and original clean-exit bridge')
print('FIRMWARE_SHA256',hashlib.sha256(RELEASE.read_bytes()).hexdigest())
