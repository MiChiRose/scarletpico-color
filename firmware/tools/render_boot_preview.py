#!/usr/bin/env python3
"""Encode the captured ARM LCD frames, not a separately implemented mock."""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build-features-v2_2_2-addon/previews'
paths=sorted((OUT/'boot-frames').glob('*.ppm'))
assert paths,'Run ARM boot checks first'
frames=[Image.new('RGB',(480,320),(16,20,24))]
ticks=[0]
for p in paths:
 frames.append(Image.open(p).convert('RGB'))
 ticks.append(int(p.stem.split('-')[1]))
duration=[max(10,(b-a)//1000) for a,b in zip(ticks,ticks[1:])]+[750]
frames[1].save(OUT/'boot-first.png')
frames[-1].save(OUT/'boot-final.png')
frames[0].save(OUT/'boot-preview.gif',save_all=True,append_images=frames[1:],
               duration=duration,loop=0,disposal=2,optimize=False)
print(OUT/'boot-preview.gif')
