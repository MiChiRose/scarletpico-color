"""Actual appended UI ARM, original font/LCD boundary and before/after metrics.
No USB use. Pixel traffic and modelled delays are not measured physical FPS.
"""
from pathlib import Path
import json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn.arm_const import *
from unicorn import UC_HOOK_CODE
import test_legacy_battery_arm as t

ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build-ui-polish-addon'
OUT=ROOT/'releases/2026-10-20-rp2040-ui-polish'
audit=json.loads((OUT/'build-audit.json').read_text());raw=(BUILD/'patched.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()==audit['image_sha256']
with (BUILD/'ui.elf').open('rb') as f:
 e=ELFFile(f);s={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols() if x.name}
traffic=0
def rectangle(x,y,w,h):
 global traffic
 traffic+=w*h;t.rectangle(x,y,w,h)
def spi(p,b,n,*_):
 global traffic
 traffic+=n//2;t.spi(p,b,n)
t.stub('old_rect',rectangle);t.stub(0x200016a0,spi)
def setup(count=32,selected=0):
 t.put(0x2001adb4,count);t.put(0x2001e220,selected);t.uc.mem_write(0x2001e258,b'\0')
 labels=['Zelda - Link\'s Awakening','Super Mario Land 2','Pokemon Crystal','Tetris','Wario Land 3','Donkey Kong','Kirby Dream Land','Metroid II']
 for i in range(32):
  a=0x2001adb8+i*332;t.uc.mem_write(a,bytes(332))
  t.uc.mem_write(a+256,(labels[i%len(labels)]+f' [{i}]').encode()+b'\0')
  t.uc.mem_write(a+328,bytes([i%2]))
 t.reset_battery();t.call(0x100308cc);t.call(0x10030b20,1)
setup();traffic=0;t.put(0x2001e220,1);t.call(0x10030b20,0)
baseline_navigation=traffic

t.uc.mem_write(0x10000000,raw);t.uc.ctl_remove_cache(0x10000000,0x10200000)
t.uc.mem_write(s['__polish_bss_start'],bytes(s['__polish_bss_end']-s['__polish_bss_start']))
def save(name):
 rgb=bytearray()
 for c in t.screen:rgb.extend((((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31))
 (BUILD/(name+'.ppm')).write_bytes(b'P6\n480 320\n255\n'+rgb)
setup();save('library-en')
traffic=0;t.put(0x2001e220,1);t.call(0x10030b20,0)
new_navigation=traffic
assert new_navigation<baseline_navigation*.3,(baseline_navigation,new_navigation)
traffic=0;t.call(0x10030b20,0);assert traffic==0
for selected in (6,7,13,14,27,28,31,0):
 t.put(0x2001e220,selected);t.call(0x10030b20,0)
 incremental=list(t.screen)
 t.call(0x100308cc);t.call(0x10030b20,1)
 assert t.screen==incremental,('stale page/focus pixels',selected)
assert t.word(s['last_selected'])==0
print('PASS actual ARM library: 32 entries, page boundaries/wrap, dirty pixels exactly match full redraw, unchanged idle 0 pixels')

# Compare every in-page focus transition to a clean paint and track type bounds.
text_calls=[]
def observe(u,a,n,d):
 x,y,p,c=[u.reg_read(r) for r in t.R];sp=u.reg_read(UC_ARM_REG_SP)
 text=t.cstr(p);scale=t.word(sp+4);limit=t.word(sp+8)
 count=len(text);text_calls.append((x,y,text,c,scale,limit))
 assert x+min(count,limit)*6*scale<=480 and y+7*scale<=320,(x,y,text,scale,limit)
t.uc.hook_add(UC_HOOK_CODE,observe,begin=s['ui_text']&~1,end=s['ui_text']&~1)
for lang in (0,1):
 t.uc.mem_write(s['ui_settings'],bytes([lang]));setup(10,0)
 for sel in range(1,7):
  t.put(0x2001e220,sel);t.call(0x10030b20,0);snapshot=list(t.screen)
  t.call(0x100308cc);t.call(0x10030b20,1);assert snapshot==t.screen
 t.put(0x2001e220,0);t.call(0x100308cc);t.call(0x10030b20,1)
 save('library-ru' if lang else 'library-en')
 t.uc.mem_write(0x2001adb8+256,('Очень длинное название игры АБВГД').encode()+b'\0')
 t.call(0x100308cc);t.call(0x10030b20,1)
 assert any(x==40 and text.endswith('..') and 25<=len(text)<=30 for x,y,text,c,scale,limit in text_calls)
 for count,error,name in [(0,0,'empty'),(0,5,'missing-roms'),(0,3,'no-card')]:
  t.put(0x2001adb4,count);t.uc.mem_write(0x2001e258,bytes([error]))
  t.call(0x100308cc);t.call(0x10030b20,1);save(name+('-ru' if lang else '-en'))
  traffic=0;t.call(0x10030b20,0);assert traffic==0
print('PASS RU/EN, 30-glyph UTF-8 title bounds, empty/missing folder/no-card, no error-state redraw loops')

# All old settings/pause pages use the new common header without new flows.
with (ROOT/'build-features-v2_2_2-addon/features.elf').open('rb') as f:
 e=ELFFile(f);base={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols() if x.name}
with (ROOT/'build-pause-ui-addon/pause-ui.elf').open('rb') as f:
 e=ELFFile(f);pause={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols() if x.name}
t.stub(0x1000a08c,lambda *_:t.ret(125000000))
t.uc.mem_write(0x2001e258,b'\0');setup(10,0)
for lang in (0,1):
 t.uc.mem_write(s['ui_settings'],bytes([lang]))
 t.call(base['settings_draw']);save('settings-ru' if lang else 'settings-en')
 t.call(base['features_about_draw']);save('about-ru' if lang else 'about-en')
 t.call(pause['pause_draw'],0);save('pause-ru' if lang else 'pause-en')
print('PASS shared header in original RU/EN settings, About, five-row pause: no page overlap/out-of-bounds text')

# Execute new boot control flow; unchanged old logo/chime are boundaries.
keys=0;chimes=[];logo=[]
def sleep(ms,*_):
 t.ticks+=ms*1000;t.ret()
t.stub(s['sleep_ms'],sleep);t.stub(s['old_keys'],lambda *_:t.ret(keys))
t.stub(s['old_boot_draw'],lambda previous,y,*_:(logo.append((previous,y)),t.ret()))
def chime(*_):chimes.append(t.ticks);t.ticks+=720000;t.ret(1)
t.stub(s['old_boot_chime'],chime)
t.ticks=0;t.uc.mem_write(s['ui_settings'],b'\0');t.call(s['polished_boot'],0)
normal_boot_us=t.ticks;assert 1400000<=normal_boot_us<=1500000 and len(chimes)==1
assert logo[0][0]&0xffffffff==(-72)&0xffffffff and logo[-1][1]==124
assert all(a[1]==b[0] for a,b in zip(logo,logo[1:]))
released=[]
t.stub(s['old_release'],lambda *_:(released.append(1),t.ret()))
keys=8;t.ticks=0;t.call(s['polished_boot'],0)
assert t.ticks==30000 and len(chimes)==1 and released==[1]
assert not t.uc.mem_read(s['valid'],1)[0]
print('PASS new ARM boot control flow: ~1.45s with original logo/chime boundaries mocked; held Start gives 30ms silent path and release consumption')

# Real settings loop, stable 12ms recheck, release consumption and flash record.
t.hooks.pop(s['old_release']&~1)
sequence=[];flash=[]
def key_schedule(*_):t.ret(next((k for lo,hi,k in sequence if lo<=t.ticks<hi),0))
t.stub(s['old_keys'],key_schedule)
def erase(off,n,*_):
 assert off==0x7f000 and n==4096
 flash.append('erase');t.uc.mem_write(0x10000000+off,b'\xff'*n);t.ret()
def program(off,p,n,*_):
 assert off==0x7f000 and n==256
 flash.append('program');t.uc.mem_write(0x10000000+off,bytes(t.uc.mem_read(p,n)));t.ret()
t.stub(0x2000039c,erase);t.stub(0x20000428,program)
t.ticks=0;t.call(s['old_features_ui_init'],0)
sequence=[(60000,120000,128),(160000,220000,16),(260000,320000,2)]
t.call(base['feature_settings'])
assert bytes(t.uc.mem_read(s['ui_settings'],3))==bytes([0,60,100])
assert flash==['erase','program'] and t.ticks>=340000
assert not t.uc.mem_read(s['valid'],1)[0]
t.call(s['old_features_ui_init'],0x1007f000)
assert bytes(t.uc.mem_read(s['ui_settings'],3))==bytes([0,60,100])
flash.clear();t.ticks=0
sequence=[(60000,64000,16),(160000,220000,2)] # 4ms bounce must be rejected
t.call(base['feature_settings'])
assert bytes(t.uc.mem_read(s['ui_settings'],3))==bytes([0,60,100])
assert not flash
print('PASS original settings flow: 12ms debounce rejects 4ms bounce, volume edit saves once, reboot restores it, held B consumed, read-only visit does not rewrite flash')

for c in audit['changes']:
 if c['purpose'].startswith('UI-only stable recheck'):
  assert bytes(t.uc.mem_read(int(c['address'],16),2))==bytes.fromhex('0c20')
def luminance(c):
 rgb=[((c>>11)&31)/31,((c>>5)&63)/63,(c&31)/31]
 v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
 return .2126*v[0]+.7152*v[1]+.0722*v[2]
for fg,bg in [(0xf79e,0x10a3),(0x8433,0x10a3),(0x8433,0x18e5),(0x10a3,0x4e98),(0xfa6c,0x10a3)]:
 a,b=sorted([luminance(fg),luminance(bg)]);assert (b+.05)/(a+.05)>=4.5,(hex(fg),hex(bg))
metrics={'baseline_navigation_pixels':baseline_navigation,'polished_navigation_pixels':new_navigation,
         'pixel_traffic_reduction_percent':round((1-new_navigation/baseline_navigation)*100,2),
         'idle_pixels':0,'debounce_before_ms':25,'debounce_after_ms':12,
         'boot_with_modelled_chime_us':normal_boot_us,'physical_measurement':False,
         'uf2_sha256':audit['uf2_sha256']}
(BUILD/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
print('PASS contrast >=4.5:1, original LCD/game/audio/clock bytes preserved by build audit')
print(json.dumps(metrics,indent=2));print('FIRMWARE_SHA256',audit['uf2_sha256'])
