"""Existing full feature/APU/state regression on PACED, plus real pause hook.
Peripherals are mocked. A stalled simulated DMA advances time during the new
bounded wait, exercising timeout fallback instead of hanging a fake timer.
"""
import os, hashlib
from pathlib import Path
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build-video-pace-addon'
os.environ['SCARLET_TEST_FIRMWARE']=str(ROOT/'build-loader-addon/patched.bin')
os.environ['SCARLET_TEST_UI_ELF']=str(ROOT/'build-ui-addon/ui.elf')
os.environ.setdefault('SCARLET_FEATURE_IMAGE',str(BUILD/'patched.bin'))
os.environ.setdefault('SCARLET_FEATURE_UF2',str(ROOT/'releases/scarletpico-v2_2_2-video16-PACED-TEST.uf2'))
import test_ui_arm as t
def wait(us,hi,*_):
    assert hi==0
    t.advance(us);t.ret()
t.stub('sleep_us',wait)
import test_features_arm as f
with (BUILD/'pace.elf').open('rb') as stream:
    elf=ELFFile(stream)
    p={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
f.s.update(p)
t.uc.mem_write(0x10081000,f.zelda)
assert f.CALL('features_load',0x10081000,len(f.zelda),0)==1
t.uc.mem_write(p['pace'],bytes(52))
t.uc.mem_write(f.s['exit_requested'],b'\0')
t.uc.mem_write(f.s['pause_pending'],b'\1')
t.ticks=0;t.sequence=[(60000,120000,2)]
before=len(f.events)
assert f.CALL('video_pace_frame',255,0,0)==3
assert f.events[before:]==['video-stop','video-start']
assert not t.uc.mem_read(f.s['pause_pending'],1)[0]
assert t.read32(p['pace']+40)==0 # time in the real menu is not CPU debt
t.sequence=[];t.set_keys(0)
fraction=t.read32(t.sym['sample_remainder'])
t.write32(p['pace']+40,9000)
assert f.CALL('video_pace_frame',255,1,t.ticks)==1
assert t.read32(t.sym['sample_remainder'])==(fraction+16000*70224)&4194303
assert t.uc.mem_read(t.sym['active'],1)==b'\1'
f.CALL('features_stop')
print('PASS PACED + real feature pause/resume: refreshed first frame, debt reset, next no-pixel frame still generates original fractional audio, clean stop')
print('FIRMWARE_SHA256',hashlib.sha256(Path(os.environ['SCARLET_FEATURE_UF2']).read_bytes()).hexdigest())
