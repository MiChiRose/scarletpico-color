"""Execute the release's actual Cortex-M0+ catalogue/UI, mock card I/O only.

No USB, flashing, or card writes. Optional mounted-card check reads filenames
and headers, never distributes ROM data. Run after build_library_paging_release.
"""
from pathlib import Path
import hashlib, json, random, struct
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
import test_legacy_battery_arm as t

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build-library-paging-addon'
OUT = ROOT / 'releases/2026-10-22-rp2040-library-paging'
audit = json.loads((OUT / 'build-audit.json').read_text())
raw = (BUILD / 'patched.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == audit['image_sha256']
with (BUILD / 'library.elf').open('rb') as f:
    elf = ELFFile(f)
    s = {x.name: x['st_value'] for x in elf.get_section_by_name('.symtab').iter_symbols() if x.name}
t.uc.mem_write(0x10000000, raw)
t.uc.ctl_remove_cache(0x10000000, 0x10200000)
def reject_flash_write(u,access,address,size,value,data):
    raise AssertionError(('catalogue wrote to flash',hex(address),size))
t.uc.hook_add(UC_HOOK_MEM_WRITE,reject_flash_write,begin=0x10000000,end=0x101fffff)
GAMES, COUNT, SELECTED, ERROR, LIMITED = 0x2001adb8, 0x2001adb4, 0x2001e220, 0x2001e258, 0x2001e257
UP, DOWN, SELECT, B = 64, 128, 4, 2
files = []; cursors = {}; opened = {}; read_calls = 0; close_calls = 0
mount_ok = True; open_error = 0; directory_error = None; close_error = 0
record = lambda name, header=None, size=32768, attr=0: dict(name=name, header=header, size=size, attr=attr)

def header(color=False, mbc=0):
    h = bytearray(0x150)
    h[0x134:0x13b] = b'TESTROM'; h[0x143] = 0x80 if color else 0
    h[0x147] = mbc; h[0x14d] = (-sum(h[0x134:0x14d])-25) & 255
    return bytes(h)

def opendir(p, path, *_):
    assert t.cstr(path) == '0:/roms'
    if not open_error: cursors[p] = 0
    t.ret(open_error)

def readdir(p, info, *_):
    index = cursors[p]; cursors[p] += 1
    if directory_error is not None and index >= directory_error:
        t.ret(1); return
    t.uc.mem_write(info, bytes(288))
    if index < len(files):
        item = files[index]
        t.uc.mem_write(info, struct.pack('<Q', item['size']))
        t.uc.mem_write(info+12, bytes([item['attr']]))
        name = item['name'].encode(); assert len(name) <= 255
        t.uc.mem_write(info+26, name+b'\0')
    t.ret()

def closedir(p, *_):
    assert p in cursors; del cursors[p]; t.ret(close_error)

def fopen(p, path, mode, *_):
    assert mode == 1, 'catalogue must never open for writing'
    name = t.cstr(path); assert name.startswith('0:/roms/')
    item = next(x for x in files if x['name'] == name[8:])
    if item.get('read_error') == 'open': t.ret(1); return
    opened[p] = item; t.ret()

def fread(p, dest, length, got):
    global read_calls
    assert length == 0x150
    item = opened[p]; h = item['header'] if item['header'] is not None else header()
    t.uc.mem_write(dest, h[:length]); t.put(got, min(length, len(h))); read_calls += 1
    t.ret(1 if item.get('read_error') == 'read' else 0)

def fclose(p, *_):
    global close_calls
    item = opened.pop(p); close_calls += 1
    t.ret(1 if item.get('read_error') == 'close' else 0)

t.stub(s['original_storage_mount'], lambda *_: t.ret(mount_ok))
t.stub(s['original_sd_bus'], lambda *_: t.ret())
for name, fn in [('f_opendir', opendir), ('f_readdir', readdir), ('f_closedir', closedir),
                 ('f_open', fopen), ('f_read', fread), ('f_close', fclose)]: t.stub(s[name], fn)

def call(name, *args): return t.call(s[name] if isinstance(name, str) else name, *args)
def names(): return [t.cstr(GAMES+i*332) for i in range(t.word(COUNT))]
def total(): return call('library_total_count')
def offset(): return call('library_window_offset')
def reset(items):
    global files, read_calls, close_calls, mount_ok, open_error, directory_error, close_error
    files = list(items); read_calls = close_calls = 0
    mount_ok = True; open_error = close_error = 0; directory_error = None
    cursors.clear(); opened.clear()
    t.uc.mem_write(s['__library_bss_start'], bytes(s['__library_bss_end']-s['__library_bss_start']))
    t.uc.mem_write(GAMES, bytes(32*332)); t.uc.mem_write(GAMES+28*332, b'\xa5'*(4*332))
    t.put(COUNT, 0); t.put(SELECTED, 0); t.uc.mem_write(ERROR, b'\0')
    t.reset_battery(); t.uc.mem_write(s['ui_settings'], bytes([0, 70, 100]))

def scan():
    # Enter at the original legacy scanner address, exercising its new jump.
    r = call(0x10031428, GAMES, 32, COUNT, LIMITED)
    t.uc.mem_write(ERROR, bytes([r])); assert not cursors and not opened
    assert t.uc.mem_read(GAMES+28*332, 4*332) == b'\xa5'*(4*332), 'legacy array/heap overrun'
    assert not t.uc.mem_read(LIMITED, 1)[0]
    return r

def edge(key):
    result = call('paged_menu_input', key)
    assert not cursors and not opened
    assert t.uc.mem_read(GAMES+28*332, 4*332) == b'\xa5'*(4*332)
    # Same small-index arithmetic as the unchanged launcher, after the bridge.
    if result & UP: t.put(SELECTED, (t.word(SELECTED)-1) % t.word(COUNT))
    elif result & (DOWN|SELECT): t.put(SELECTED, (t.word(SELECTED)+1) % t.word(COUNT))
    return result

def sorted_names(items):
    return sorted((x['name'] for x in items if not x['name'].startswith('.') and
                   not x['attr'] & (2|4|16) and x['name'].lower().endswith(('.gb', '.gbc'))),
                  key=lambda x: (x.lower().encode(), x.encode()))

def verify_walk(items):
    reset(items); assert scan() == 0
    wanted = sorted_names(items); assert total() == len(wanted)
    assert names() == wanted[:28] and offset() == 0
    if not wanted: return
    for step in range(len(wanted)+1):
        assert names()[t.word(SELECTED)] == wanted[step % len(wanted)], (step, offset(), names())
        assert offset()+t.word(SELECTED) == step % len(wanted)
        edge(DOWN if step % 2 else SELECT)
    # Reverse traversal including wrap from the first element.
    t.put(SELECTED, 0)
    # Refresh guarantees first window, regardless of previous forward walk.
    assert call('paged_menu_input', B) & B; assert scan() == 0
    for step in range(len(wanted)+1):
        edge(UP)
        index = (-step-1) % len(wanted)
        assert names()[t.word(SELECTED)] == wanted[index], (step, index, offset())
        assert offset()+t.word(SELECTED) == index
    assert read_calls == close_calls

rng = random.Random(228)
# Catalogue traversal is independent of LCD transport; exercise its renderer
# separately below instead of repainting thousands of duplicate test screens.
t.stub(s['polished_menu_draw'],lambda *_:t.ret())
for count in [0, 1, 7, 27, 28, 29, 32, 47, 56, 57, 128]:
    items = [record(f'Game {i:04d}.gbc' if i%2 else f'Game {i:04d}.GB', header(i%2)) for i in range(count)]
    rng.shuffle(items)
    items += [record('._Ghost.gb'), record('bad.zip'), record('folder.gb', attr=16),
              record('hidden.gb', attr=2), record('system.gbc', attr=4)]
    verify_walk(items)
    print('PASS complete forward/reverse/wrap ARM navigation:', count, 'ROMs', flush=True)

items = [record(f'Game {i:04d}.gb') for i in range(1000)]
rng.shuffle(items); reset(items); assert scan() == 0
assert names() == sorted_names(items)[:28] and total() == 1000 and read_calls == 28
print('PASS 1000-ROM unsorted directory: exact global first 28, full count, only 28 headers read', flush=True)

# Keep selection/window on game exit; B explicitly resets to the first window.
reset([record(f'Game {i:03d}.gb') for i in range(75)]); scan()
t.put(SELECTED, 27); edge(DOWN); t.put(SELECTED, 14)
before = names(); identity = bytes(t.uc.mem_read(GAMES+14*332, 332))
assert scan() == 0 and names() == before and offset() == 28 and t.word(SELECTED) == 14
assert bytes(t.uc.mem_read(GAMES+14*332, 332)) == identity
assert call('paged_menu_input', B) & B; scan(); assert offset() == 0
print('PASS game-exit rescan preserves window, filename/signature/size; B refresh starts at first window', flush=True)
t.hooks.pop(s['polished_menu_draw']&~1)

# Verify the actual hooked caller preserves registers and condition flags.
t.put(SELECTED, 27)
t.uc.reg_write(UC_ARM_REG_SP, 0x20042000)
for i, reg in enumerate(t.R): t.uc.reg_write(reg, 0x88770000+i)
t.uc.reg_write(UC_ARM_REG_R5, DOWN)
t.uc.reg_write(UC_ARM_REG_R6, 0xd0000000)
t.uc.emu_start(0x10007b25, 0x10007b28, count=10000000)
assert t.uc.reg_read(UC_ARM_REG_PC) == 0x10007b28
assert t.uc.reg_read(UC_ARM_REG_SP) == 0x20042000
assert t.uc.reg_read(UC_ARM_REG_R5) == 0 and t.uc.reg_read(UC_ARM_REG_R4) == B
assert all(t.uc.reg_read(reg) == 0x88770000+i for i,reg in enumerate(t.R))
assert t.uc.reg_read(UC_ARM_REG_R6) == 0xd0000000
assert t.uc.reg_read(UC_ARM_REG_APSR) & (1 << 30)
assert offset() == 28 and t.word(SELECTED) == 0
conversions = t.conversions; t.ticks += 1000000; edge(0)
assert t.conversions == conversions+17, 'working battery input wrapper bypassed'
print('PASS actual legacy input bridge: boundary consumed once, registers/flags/stack and 1Hz GP29 polling preserved', flush=True)

# Actual held-key caller path, including the old repeat arithmetic/flags.
reset([record(f'Game {i:03d}.gb') for i in range(47)]); scan()
for key, selected, expected_offset, expected_selected in [
        (DOWN,27,28,0), (UP,0,0,27), (UP,0,28,18), (DOWN,18,0,0), (DOWN,4,0,4)]:
    t.put(SELECTED,selected); t.uc.reg_write(UC_ARM_REG_SP,0x20042000)
    for i,reg in enumerate(t.R): t.uc.reg_write(reg,0x88990000+i)
    t.uc.reg_write(UC_ARM_REG_R5,key); t.uc.reg_write(UC_ARM_REG_R7,key)
    t.uc.reg_write(UC_ARM_REG_R6,0xd0000000)
    t.uc.emu_start(0x10007bd1,0x10007bda,count=10000000)
    assert t.uc.reg_read(UC_ARM_REG_PC)==0x10007bda
    assert t.uc.reg_read(UC_ARM_REG_SP)==0x20042000
    assert all(t.uc.reg_read(reg)==0x88990000+i for i,reg in enumerate(t.R))
    assert t.uc.reg_read(UC_ARM_REG_R6)==0xd0000000
    assert t.uc.reg_read(UC_ARM_REG_APSR)&(1<<30)
    assert t.uc.reg_read(UC_ARM_REG_R5)==(key if selected==4 else 0),(key,selected,offset(),t.uc.reg_read(UC_ARM_REG_R5))
    assert (offset(),t.word(SELECTED))==(expected_offset,expected_selected)
settings_visits=[]
t.stub(0x10032c20,lambda *_:(settings_visits.append(1),t.ret()))
assert call('paged_menu_input',16)==0 and settings_visits==[1]
print('PASS actual held-key repeat boundary/wrap and unchanged Right-to-settings route',flush=True)

# I/O errors clear the catalogue, never leave an old selectable record.
for kind in ['mount', 'folder', 'readdir', 'closedir']:
    reset([record('A.gb'), record('B.gbc')]); scan()
    if kind == 'mount': mount_ok = False
    elif kind == 'folder': open_error = 5
    elif kind == 'readdir': directory_error = 1
    else: close_error = 1
    assert scan() != 0 and t.word(COUNT) == total() == offset() == 0
    assert not opened
print('PASS no card, missing folder, mid-directory failure, close failure: no stale playable records', flush=True)

reset([record('A.gb'), record('B.gb', b'bad'), record('C.gb', header(mbc=0x20)),
       record('D.gbc', header(True)), record('E.gb', size=65536), record('Ёжик.GBC')])
files[0]['read_error'] = 'open'
scan(); assert [t.uc.mem_read(GAMES+i*332+329, 1)[0] for i in range(6)] == [4,1,3,0,1,0]
assert t.uc.mem_read(GAMES+3*332+328, 1)[0] == 1
reset([record('x'*252+'.gb')]); scan(); assert names() == ['x'*252+'.gb']
print('PASS launch status ABI, mixed/uppercase extensions, UTF-8 and maximum 255-byte filenames', flush=True)

# Optional actual user's 47-ROM card inventory; reads headers only.
card = Path('/Volumes/SCARLETPICO/roms')
card_count = None
if card.is_dir():
    items = []
    for path in card.iterdir():
        if path.is_file() and not path.name.startswith('.') and path.suffix.lower() in ('.gb','.gbc'):
            with path.open('rb') as f: h = f.read(0x150)
            items.append(record(path.name, h, path.stat().st_size))
    verify_walk(items); card_count = len(items)
    assert all(x['name'] for x in items)
    print('PASS mounted card, read-only:', card_count, 'ROMs reachable in both directions', flush=True)

# Pixel-level check on the real new renderer and pinned original font code.
def observe_ui_text(u,a,n,d):
    x,y,p,color=[u.reg_read(reg) for reg in t.R]
    scale=t.word(u.reg_read(UC_ARM_REG_SP)+4)
    limit=t.word(u.reg_read(UC_ARM_REG_SP)+8)
    label=t.cstr(p); t.texts.append((x,y,label,color,scale))
    assert x+min(len(label),limit)*6*scale<=480 and y+7*scale<=320,(x,y,label,scale)
t.uc.hook_add(UC_HOOK_CODE,observe_ui_text,begin=s['ui_text']&~1,end=s['ui_text']&~1)
reset([record(f'Game {i:03d}.gb') for i in range(47)]); scan()
for language in (0, 1):
    t.uc.mem_write(s['ui_settings'], bytes([language]))
    for index in [0,1,6,7,13,14,20,21,27]:
        t.put(SELECTED,index); call('polished_menu_draw',0); image=list(t.screen)
        call('polished_invalidate'); call('polished_menu_draw',1)
        assert t.screen == image, ('dirty/full render mismatch', index)
    edge(DOWN); assert offset() == 28
    t.texts.clear(); call('polished_invalidate'); call('polished_menu_draw',1)
    assert any(x[2] == '29 / 47' for x in t.texts)
    for index in [1,6,7,13,14,18]:
        t.put(SELECTED,index); call('polished_menu_draw',0); image=list(t.screen)
        call('polished_invalidate'); call('polished_menu_draw',1); assert t.screen == image
    t.rects.clear(); t.texts.clear(); call('polished_menu_draw',0)
    assert not t.rects and not t.texts, 'idle redraw regression'
    call('paged_menu_input',B); scan()
print('PASS RU/EN real LCD/font render: global 29/47, all page edges, dirty pixels equal full redraw, idle 0', flush=True)
for full_count in (1000,4294967295):
    t.put(s['total_count'],full_count); t.put(s['window_offset'],full_count-28)
    t.put(SELECTED,27); t.texts.clear()
    call('polished_invalidate'); call('polished_menu_draw',1)
    assert any(x[2]==f'{full_count} / {full_count}' for x in t.texts)
print('PASS global counter renderer: 4-digit and maximum uint32 values fit inside the LCD',flush=True)

metrics = dict(uf2_sha256=audit['uf2_sha256'], actual_arm=True, hardware_tested=False,
               tested_counts=[0,1,7,27,28,29,32,47,56,57,128,1000], mounted_card_roms=card_count,
               added_static_ram_bytes=audit['added_static_ram'], new_catalogue_heap_allocations=0,
               minimum_observed_test_stack=hex(t.minimum_sp))
(OUT/'test-results.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics,indent=2))
