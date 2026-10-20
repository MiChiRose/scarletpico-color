"""Read-only CAD gallery from checked-in binary STL files (numpy + Pillow).

No AI geometry, regenerated print models, GUI renderer or CAD dependency.
"""
from pathlib import Path
import hashlib
import json
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT/'hardware/case'
OUT = ROOT/'docs/assets'
OUT.mkdir(exist_ok=True)
CREAM = np.array([224, 214, 190])
RED = np.array([199, 58, 78])
INK = np.array([30, 38, 45])
TEAL = np.array([68, 152, 148])
SOURCES = {}

def stl(relative):
    path = CASE/relative
    raw = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    n = struct.unpack_from('<I', raw, 80)[0]
    assert len(raw) == 84+50*n
    dtype = np.dtype([('normal', '<f4', 3), ('triangle', '<f4', (3, 3)), ('attr', '<u2')])
    return np.frombuffer(raw, dtype=dtype, count=n, offset=84)['triangle'].astype(float)

def font(size, bold=False):
    stem = 'Arial Bold.ttf' if bold else 'Arial.ttf'
    for base in ['/System/Library/Fonts/Supplemental/', '/usr/share/fonts/truetype/msttcorefonts/']:
        if (p := Path(base)/stem).exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.truetype('DejaVuSans.ttf', size)

def box(lo, hi):
    p = np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
    return p[np.array([[0,4,6],[0,6,2],[1,3,7],[1,7,5],[0,1,5],[0,5,4],
                       [2,6,7],[2,7,3],[0,2,3],[0,3,1],[4,5,7],[4,7,6]])]

def render(items, size, direction):
    w,h = size
    image = np.full((h,w,3), [237,238,233], dtype=np.uint8)
    depth = np.full((h,w), -np.inf)
    view = np.array(direction, dtype=float); view /= np.linalg.norm(view)
    right = np.cross(-view, [0,-1,0]); right /= np.linalg.norm(right)
    down = np.cross(right, view)
    basis = np.array([right,down,view])
    all_points = np.concatenate([tri.reshape(-1,3) for tri,color in items]) @ basis.T
    low,high = all_points.min(0),all_points.max(0)
    scale = min((w-110)/(high[0]-low[0]), (h-100)/(high[1]-low[1]))
    offset = np.array([w/2,h/2])-(low[:2]+high[:2])/2*scale
    light = np.array([-.3,-.5,-1.0]); light /= np.linalg.norm(light)
    for triangles,color in items:
        normals = np.cross(triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0])
        lengths = np.linalg.norm(normals, axis=1)
        normals /= np.maximum(lengths[:,None],1e-12)
        projected = triangles @ basis.T
        for world,p,n in zip(triangles, projected, normals):
            xy = p[:,:2]*scale+offset
            a,b,c = xy
            den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-9: continue
            lo = np.maximum(np.floor(xy.min(0)).astype(int), [0,0])
            hi = np.minimum(np.ceil(xy.max(0)).astype(int), [w-1,h-1])
            if np.any(hi<lo): continue
            yy,xx = np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            aa = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            bb = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
            cc = 1-aa-bb
            zz = aa*p[0,2]+bb*p[1,2]+cc*p[2,2]
            z = depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask = (aa>=-1e-6)&(bb>=-1e-6)&(cc>=-1e-6)&(zz>z)
            z[mask] = zz[mask]
            shade = .58+.40*abs(float(n@light))
            image[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask] = np.clip(color*shade,0,255)
    return Image.fromarray(image)

front = stl('rev3-split/output/01-front-R3-LCD-3mm.stl')
dpad = stl('rev3-split/output/04-dpad-R2.stl')
dpad += [31.9,88,-2.4]-np.array([(dpad[:,:,0].min()+dpad[:,:,0].max())/2,
                               (dpad[:,:,1].min()+dpad[:,:,1].max())/2,dpad[:,:,2].min()])
packed = stl('button-bench-R3/split-spring-test/04-four-matching-caps-SPRING-TEST.stl')
caps = []
for i,xy in enumerate([(78.4,85.3),(70.5,93.1),(47,116.6),(57.5,117)]):
    tri = packed[(packed[:,:,0].mean(1)>=16*i-.01)&(packed[:,:,0].mean(1)<16*i+14)].copy()
    mid = (tri.reshape(-1,3).min(0)+tri.reshape(-1,3).max(0))/2
    tri += [xy[0]-mid[0],xy[1]-mid[1],-2.2-tri[:,:,2].min()]
    caps.append((tri,INK))
screen = box([8,12.5,.4],[95,68.5,1.0])
items = [(front,CREAM),(dpad,INK),(screen,INK),*caps]
# Show real outer geometry; screen block is only an unpowered display envelope.
render(items,(1100,1250),[.48,-.18,-1]).save(OUT/'case-front.png')
render([(front,CREAM)],(1100,1250),[-.4,-.15,1]).save(OUT/'case-inside.png')

whole = stl('rev2/output/02-rear-R2.stl')
split = [stl('rev3-split/output/'+name) for name in
         ['02a-rear-upper-R3.stl','02b-rear-transition-R3.stl','02c-rear-lower-R3.stl']]
# Each part remains in its actual exported printing orientation. This is a
# labelled comparison, not a guessed exploded assembly or new revision.
gallery = Image.new('RGB',(1600,1000),'#edeee9')
d = ImageDraw.Draw(gallery)
d.text((60,35),'Задняя крышка: от цельной к трём секциям',font=font(36,True),fill='#1e262d')
d.text((60,91),'R2 — ранняя цельная версия  /  R3 — текущая секционная',font=font(24),fill='#54616a')
gallery.paste(render([(whole,CREAM)],(610,730),[.4,-.25,-1]),(30,150))
d = ImageDraw.Draw(gallery)
d.text((90,910),'R2 · один STL',font=font(27,True),fill='#1e262d')
for tri,color,xy,view,label in zip(split,[TEAL,RED,CREAM],[(680,155),(1110,155),(810,580)],
                                 [[.35,-.25,1],[.35,.9,-.7],[.35,-.25,1]],
                                 ['R3 · верх','R3 · переход','R3 · низ']):
    gallery.paste(render([(tri,color)],(420,310),view),xy)
    ImageDraw.Draw(gallery).text((xy[0]+30,xy[1]+315),label,font=font(23,True),fill='#1e262d')
gallery.save(OUT/'case-rear-options.png')
(OUT/'cad-provenance.json').write_text(json.dumps({'input_sha256':SOURCES,
    'print_models_modified':False,'screen':'unpowered schematic envelope; no invented gameplay',
    'materials':'illustrative colours; front R3, whole rear R2, split rear R3'},indent=2)+'\n')
print('Rendered actual CAD into docs/assets/case-*.png; STL files unchanged')
