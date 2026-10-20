#!/usr/bin/env python3
"""Render-only decorative proposals; never exports or changes printable STL.

Actual CAD surfaces, identical cameras and materials. No external lettering,
changed outline, relocated controls, replacement vents or added overhangs.
"""
from pathlib import Path
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import manifold3d as m

ROOT=Path(__file__).resolve().parent
REV=ROOT.parent
source=REV/'build_rev2.py'
protected=[*REV.glob('output/*.stl'),REV/'ScarletPico-case-R2.zip']
before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
s={'__file__':str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0],str(source),'exec'),s)
selected_front,rear=s['front'],s['rear']
front=s.get('front_before_side_decor',selected_front)
box,pill,union,mesh_of=(s[k] for k in ('box','pill','union','mesh_of'))
cream=(218,205,178); charcoal=(48,49,51)
font_path='/System/Library/Fonts/Supplemental/Arial.ttf'
font=ImageFont.truetype(font_path,32)
small=ImageFont.truetype(font_path,25)

def camera(direction):
    d=np.array(direction,dtype=float);d/=np.linalg.norm(d)
    r=np.cross(-d,[0,-1,0]);r/=np.linalg.norm(r)
    down=np.cross(r,d)
    return np.array([r,down,d])

def render(im,items,center,scale,origin,direction,rect,cavity=False):
    pixels=np.array(im);depth=np.full((im.height,im.width),-np.inf)
    bx0,by0,bx1,by1=rect
    light=np.array([.3,-.5,-.8]);light/=np.linalg.norm(light)
    for geom,color in items:
        mesh=mesh_of(geom);vv=(mesh.vertices-np.array(origin))@camera(direction).T
        for face,normal,world in zip(mesh.faces,mesh.face_normals,mesh.triangles_center):
            p=vv[face];xy=p[:,:2]*scale+center
            lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),[bx0,by0])
            hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),[bx1-1,by1-1])
            if np.any(hi<lo):continue
            a,b,c=xy;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-9:continue
            yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wc=1-wa-wb
            zz=wa*p[0,2]+wb*p[1,2]+wc*p[2,2]
            db=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>db)
            db[mask]=zz[mask]
            shade=.58+.4*abs(float(normal@light))
            # A little cavity darkening makes shallow, genuinely modelled
            # recesses legible; all four views use the same lighting rule.
            x,y,z=world
            if cavity and ((25<x<49 and 127<y<144 and .003<z<.351)
                           or (96<y<114 and 3<z<24 and
                               (.003<x<.351 or 102.649<x<102.997))):shade*=.65
            if not cavity and 2.74<z<2.8 and 22<x<58 and 125<y<132:shade*=.55
            pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=tuple(int(c*shade) for c in color)
    im.paste(Image.fromarray(pixels))

face_cuts=union([pill(0,y,-.03,18,1,.38).rotate([0,0,-25]).translate([37,135,0])
                 for y in (-2.7,0,2.7)])
side_parts=[]
for x in (-.75,103.75):
    for y in (100,105,110):
        side_parts.append(m.Manifold.cylinder(17,1.1,circular_segments=48).translate([x,y,5]))
        side_parts.append(m.Manifold.sphere(1.1,48).translate([x,y,5]))
        side_parts.append(m.Manifold.sphere(1.1,48).translate([x,y,22]))
side_cuts=union(side_parts)
options=[front,front-face_cuts,front-side_cuts,front-face_cuts-side_cuts]
labels=[('1. Чистый корпус','Без полоски под экраном; без нового декора.'),
        ('2. Три канавки спереди','Слева внизу: глубина 0,35 мм; НЕ сквозные.'),
        ('3. Канавки на боковинах','По три с каждой стороны; глубина до 0,35 мм.'),
        ('4. Вместе','Лицевые канавки и боковая фактура.')]
checks=[]
for i,part in enumerate(options):
    assert part.status()==m.Error.NoError and len(part.decompose())==1
    assert (part-front).volume()<.001
    assert np.allclose(mesh_of(part).bounds,mesh_of(front).bounds,atol=.0001)
    changed=front-part
    roi=box(25,127,-.1,24,17,.5)+box(-.1,96,3,.5,18,21)+box(102.6,96,3,.5,18,21)
    assert (changed-roi).volume()<.001,('outside decorative patches',i)
    for name in ('rear','retainer','dpad','speaker_cap'):
        assert (part ^ s[name]).volume()<.002,(i,name)
    checks.append(dict(option=i+1,envelope_preserved=True,only_subtractive=True,
                       print_STL_exported=False,removed_volume_mm3=round(changed.volume(),3)))

im=Image.new('RGB',(2000,1900),'#f0f2f4')
d=ImageDraw.Draw(im)
d.text((40,20),'ScarletPico / сравнение декора — выбран вариант 3',font=font,fill='#182635')
d.text((40,66),'Все размеры, кнопки и крепления одинаковые. Новых надписей снаружи нет.',font=small,fill='#526171')
screen=box(8,12.5,.8,87,56,.5)
speaker_face=box(60.5,125,3.5,30,20,.3)
for i,(part,(title,subtitle)) in enumerate(zip(options,labels)):
    col,row=i%2,i//2
    x0,y0=col*1000,115+row*870
    ImageDraw.Draw(im).rounded_rectangle((x0+20,y0+5,x0+980,y0+850),radius=20,fill='#e8ebef')
    items=[(part,cream),(rear,cream),(s['dpad'],charcoal),(screen,(26,33,37)),(speaker_face,charcoal),
           *[(c,charcoal) for c in s['caps'].values()]]
    render(im,items,(x0+500,y0+365),4.05,[51.5,75,10],[.48,-.2,-1],
           (x0+25,y0+10,x0+975,y0+745),cavity=True)
    d=ImageDraw.Draw(im)
    d.text((x0+55,y0+750),title,font=font,fill='#182635')
    d.text((x0+55,y0+798),subtitle,font=small,fill='#526171')
d.text((40,1870),'В печатной передней крышке — вариант 3: по три боковые канавки. Варианты 2 и 4 остаются только рендерами.',
       font=ImageFont.truetype(font_path,21),fill='#526171')
im.save(ROOT/'decor-comparison.png')

chosen=Image.new('RGB',(1200,1100),'#f0f2f4')
ImageDraw.Draw(chosen).text((40,25),'ScarletPico R2 / выбранный вариант 3',font=font,fill='#182635')
render(chosen,[(selected_front,cream),(rear,cream),(s['dpad'],charcoal),
              (screen,(26,33,37)),(speaker_face,charcoal),*[(c,charcoal) for c in s['caps'].values()]],
       (600,535),5,[51.5,75,10],[.6,-.15,-1],(30,90,1170,1010),cavity=True)
ImageDraw.Draw(chosen).text((40,1030),'По три несквозные канавки на каждой боковине. Глубина до 0,35 мм.',font=small,fill='#526171')
chosen.save(ROOT/'selected-side-decor.png')

proof=Image.new('RGB',(1400,520),'#eef0f3')
d=ImageDraw.Draw(proof)
d.text((35,20),'Гравировка — исправленный вид ИЗНУТРИ',font=font,fill='#182635')
crop=front ^ box(21,124,0,39,8,4)
render(proof,[(crop,cream)],(700,280),28,[40.5,128,3],[0,0,1],(25,95,1375,450))
ImageDraw.Draw(proof).text((35,475),'Только внутренний участок передней крышки; положение и глубина гравировки сохранены.',font=small,fill='#526171')
proof.save(ROOT/'engraving-inside.png')
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in before.items())
(ROOT/'checks.json').write_text(json.dumps(dict(options=checks,print_files_unchanged=True),indent=2)+'\n')
print('Render-only variants validated; printable files unchanged.')
