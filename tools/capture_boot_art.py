"""Capture the actual pinned ARM boot drawing for the project README.

Requires firmware-test requirements and Pillow. Does not access USB or change
firmware/STL files. Hardware is mocked at the LCD write boundary only.
"""
from pathlib import Path
import contextlib
import io
import hashlib
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'firmware/tests'))
with contextlib.redirect_stdout(io.StringIO()):
    import test_legacy_battery_arm as t

OUT = ROOT / 'docs/assets'
OUT.mkdir(exist_ok=True)
fw = ROOT / 'firmware/releases/2026-10-20-rp2040-ui-polish/ScarletPico-v2_2_7-RP2040-UI-POLISH.uf2'
uf2 = fw.read_bytes()
assert hashlib.sha256(uf2).hexdigest() == '2be5dd4d37001167a77501174ce02ba3d59a21e555b4ff6b87a2620b8c6f34c0'
image = b''.join(uf2[i+32:i+288] for i in range(0, len(uf2), 512))
t.uc.mem_write(0x10000000, image)
t.uc.ctl_remove_cache(0x10000000, 0x10200000)
BG, TEAL = 0x10a3, 0x4e98

def capture():
    rgb = bytearray()
    for c in t.screen:
        rgb.extend((((c >> 11) & 31)*255//31, ((c >> 5) & 63)*255//63, (c & 31)*255//31))
    return Image.frombytes('RGB', (480, 320), bytes(rgb))

t.screen[:] = [BG]*(480*320)
frames = [capture()]
previous = -72
for ms in range(0, 601, 32):
    y = -72 + 196*ms*(1200-ms)//360000
    if y != previous:
        t.call(0x10033001, previous, y)
    previous = y
    frames.append(capture())
t.call(0x10033001, previous, 124)
# Actual original pixel font, text call and ROM string scratch, not a new font.
t.uc.mem_write(0x20043000, b'COLOR\0')
t.call(0x100300c5, 210, 208, 0x20043000, TEAL, BG, 2, 5)
final = capture()
final.save(OUT / 'boot-screen.png')
# Wide README crop keeps the exact mark and pixel grid, not a new logo.
final.crop((0, 72, 480, 252)).resize((1440, 540), Image.Resampling.NEAREST).save(OUT / 'scarletpico-banner.png')
frames.append(final)
frames[0].save(OUT / 'boot.gif', save_all=True,
               append_images=frames[1:], duration=[32]*(len(frames)-1)+[2400],
               loop=0, optimize=False, disposal=2)
print('Captured actual ARM boot logo: docs/assets/scarletpico-banner.png, boot-screen.png, boot.gif')
