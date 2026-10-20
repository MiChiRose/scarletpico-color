#!/usr/bin/env python3
"""Render the actual candidate CAD, including its packed print orientation."""
from pathlib import Path
import runpy
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
preload_mode='--dpad-preload' in sys.argv
full_outline='--full-outline' in sys.argv
unified='--unified' in sys.argv or full_outline
v2='--v2' in sys.argv
s=runpy.run_path(str(ROOT/('build_full_plate.py' if full_outline else 'combine_retainers.py' if unified else 'build_dpad_preload.py' if preload_mode else 'reinforce_springs.py' if v2 else 'build_springs.py')))
if v2:s['spec']=s['s']['spec']
box,mesh_of=s['box'],s['mesh_of']
W,H=2000,1450
im=Image.new('RGB',(W,H),'#f3f4f6');pixels=np.asarray(im).copy()
blue,teal,gold,red=(61,123,179),(38,149,131),(211,151,54),(166,65,78)
grey=(209,213,219)

def render(items,center,scale,origin,basis,rect):
    depth=np.full((H,W),-np.inf);basis=np.array(basis,dtype=float)
    for geom,color in items:
        mesh=mesh_of(geom.simplify(.001))
        vv=(mesh.vertices-np.array(origin))@basis.T
        for face,normal in zip(mesh.faces,mesh.face_normals):
            p=vv[face];xy=p[:,:2]*scale+center
            lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),rect[:2])
            hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),np.array(rect[2:])-1)
            if np.any(hi<lo):continue
            a,b,c=xy;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10:continue
            yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wc=1-wa-wb
            zz=wa*p[0,2]+wb*p[1,2]+wc*p[2,2]
            db=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>db);db[mask]=zz[mask]
            shade=.66+.32*abs(float(normal@np.array([.25,-.4,.88])))
            pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=tuple(int(v*shade) for v in color)

if unified:
    colors={'DPAD':blue,'AB':teal,'SS':gold}
    parts=[(s['fixed'][g],colors[g]) for g in colors]
    parts += [(s['moving'](n,s['preload']),colors[p['group']]) for n,p in s['spec'].items()]
    if full_outline:
        parts=[(s['rigid'],blue)]+[(s['moving'](n,0),teal) for n in s['spec']]
    else:
        parts.append((s['links']-s['base'],(76,88,106)))
    render(parts,[1000,500],11.5,[51.5,98,6],
           [[-1,0,0],[0,.985,-.174],[0,.174,.985]],[20,150,1980,880])
    extent=mesh_of(s['layout'][0]).extents
    render([(s['layout'][0],blue)],[1000,1160],7,[extent[0]/2,extent[1]/2,0],
           [[1,0,0],[0,.97,-.243],[0,.243,.97]],[20,960,1980,1380])
    im.paste(Image.fromarray(pixels));d=ImageDraw.Draw(im)
    font='/System/Library/Fonts/Supplemental/Arial.ttf'
    title=ImageFont.truetype(font,34);sub=ImageFont.truetype(font,25);small=ImageFont.truetype(font,22)
    d.text((30,22),'ScarletPico / единая пружинная прижимная пластина',font=title,fill='#192a3b')
    d.text((30,75),'Старый прямоугольник 70 × 50 мм и штатные ушки. Никаких дополнительных выступов.' if full_outline else 'Одна связная деталь: три прежние рамки V2 + две наружные жёсткие связи.',font=sub,fill='#526170')
    d.text((30,120),'D-pad: четыре одинаковых выреза с поворотом на 90°. Пружины и крепления кнопок прежние.' if full_outline else 'Вид изнутри. Серые боковые связи не заходят в рабочие пружины.',font=sub,fill='#192a3b')
    d.text((30,875),'Синий — неподвижная основа. Зелёный — подвижные площадки и тонкие пружины.' if full_outline else 'Синий — D-pad; зелёный — A/B; жёлтый — Start/Select. Цвета только для показа.',font=small,fill='#26394e')
    d.text((30,915),'Шесть прежних креплений M2×6. Кнопки, корпус, ход и центральная опора не изменены.',font=small,fill='#26394e')
    d.text((30,960),f'Положение STL на столе: {extent[0]:g} × {extent[1]:g} × {extent[2]:g} мм. Raft не нужен.',font=sub,fill='#192a3b')
    d.text((30,1385),'Локальные поддержки только под центральной опорой и рёбрами D-pad; не под пружинами A/B и Start/Select.',font=small,fill='#9a3f3f')
    dest=ROOT/('preview-symmetric-dpad.png' if full_outline else 'preview-unified.png');im.save(dest);print(dest)
    raise SystemExit(0)

if preload_mode:
    dp=s['dpad'];carrier=s['plates']['DPAD'];sp=s['spring']
    panel=s['front'] ^ box(5,70,-.01,55,35,4.87)
    render([(sp,gold)],[520,500],14,[31.9,88,3.6],
           [[-1,0,0],[0,.985,-.174],[0,.174,.985]],[20,160,1010,990])
    render([(panel,grey),(sp.translate([0,0,5]),gold),
            (dp.translate([0,0,14]),red),(carrier.translate([0,0,20]),blue)],
           [1500,580],13,[31.9,88,13],
           [[.94,-.342,0],[.171,.47,-.866],[.296,.814,.5]],[1040,160,1980,1180])
    im.paste(Image.fromarray(pixels));d=ImageDraw.Draw(im)
    font='/System/Library/Fonts/Supplemental/Arial.ttf'
    title=ImageFont.truetype(font,34);sub=ImageFont.truetype(font,25);small=ImageFont.truetype(font,22)
    d.text((30,22),'ScarletPico / отдельная пружинящая вставка для D-pad',font=title,fill='#192a3b')
    d.text((30,75),'Убираем свободное осевое перемещение поджимом, а не только усилением рамки.',font=sub,fill='#526170')
    d.line((1020,145,1020,1280),fill='#d3d8df',width=2)
    d.text((30,120),'Четыре упругие лапки под внутренним бортиком',font=sub,fill='#192a3b')
    d.text((1050,120),'Разнесённый вид: детали подняты для показа',font=sub,fill='#192a3b')
    d.text((30,1030),'Кольца надеваются ВОКРУГ двух существующих стоек.',font=small,fill='#26394e')
    d.text((30,1070),'Вставка опирается рамкой на внутреннюю плоскость панели.',font=small,fill='#26394e')
    d.text((30,1110),'Новых винтов, клея и отверстий нет.',font=small,fill='#26394e')
    d.text((1050,1190),'Синий — держатель V2; красный — прежняя крестовина.',font=small,fill='#26394e')
    d.text((1050,1230),'Жёлтый — новая вставка; серый — передняя панель.',font=small,fill='#26394e')
    d.text((30,1310),'Порядок: панель → пружинящая вставка → крестовина → жёсткий держатель V2.',font=sub,fill='#192a3b')
    d.text((30,1370),'Тестовая конструкция. Геометрия проверена; реальная сила поджима и ресурс пока не измерены.',font=small,fill='#9a3f3f')
    dest=ROOT/'preview-DPAD-preload.png';im.save(dest);print(dest)
    raise SystemExit(0)

colors={'DPAD':blue,'AB':teal,'SS':gold}
parts=[(s['fixed'][g],colors[g]) for g in colors]
parts += [(s['moving'](n,s['preload']),colors[p['group']]) for n,p in s['spec'].items()]
front=s['front'] ^ box(6.5,70.5,-.01,90,53.5,4.87)
render([(front,grey),*parts,*[(c,red) for c in s['caps'].values()],(s['dpad'],red)],
       [565,475],10.8,[51.5,98,4],
       [[-1,0,0],[0,.985,-.174],[0,.174,.985]],[20,155,1110,845])

# A real enlarged crop of the A mechanism; the cap is lifted solely along Z.
zone=box(70.8,70,-3,17,22,24)
local=[(s['fixed']['AB'] ^ zone,teal),
       (s['moving']('A',s['preload']),teal),
       (s['caps']['A'].translate([0,0,12]),red)]
if v2:
    render([(s['plates']['DPAD'],blue)],[1560,480],13.5,[31.9,88,6],
           [[.94,-.342,0],[.171,.47,-.866],[.296,.814,.5]],[1140,155,1980,845])
else:
    render(local,[1560,480],28,[78.4,82,10],
           [[.94,-.342,0],[.171,.47,-.866],[.296,.814,.5]],[1140,155,1980,845])

render([(s['layout'][i],col) for i,col in enumerate([blue,teal,gold] if v2 else [blue,teal,gold,red,red,red,red])],
       [1000,1180],5.5,[51.05 if v2 else 83.7,36.2,0],
       [[1,0,0],[0,.97,-.243],[0,.243,.97]],[20,970,1980,1390])
im.paste(Image.fromarray(pixels));d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Supplemental/Arial.ttf'
title=ImageFont.truetype(font,34);sub=ImageFont.truetype(font,25);small=ImageFont.truetype(font,22)
d.text((30,22),'ScarletPico / усиленные рамки V2' if v2 else 'ScarletPico / три независимые прижимные пластины',font=title,fill='#192a3b')
d.text((30,75),'Тестовая конструкция. Рендер реальной CAD-геометрии, не результат физического испытания.',font=sub,fill='#526170')
d.line((1125,145,1125,850),fill='#d3d8df',width=2)
d.text((30,120),'Изнутри панели: прежние шесть мест крепления M2×6',font=sub,fill='#192a3b')
d.text((1150,120),'Крестовина: наружная связь всех четырёх площадок' if v2 else 'Кнопка A: накладка приподнята для показа',font=sub,fill='#192a3b')
d.text((30,850),'Синий — крестовина. Зелёный — A/B. Жёлтый — Start/Select.',font=small,fill='#26394e')
d.text((1150,850),'Центральная опора сохранена; усиление сзади.' if v2 else 'Кольцевая площадка и две тонкие перемычки.',font=small,fill='#26394e')
d.text((30,890),'Упругие перемычки 0,8 мм; площадки 1,2 мм. Рамки и места саморезов жёсткие.',font=sub,fill='#192a3b')
d.line((25,940,1975,940),fill='#d3d8df',width=2)
d.text((30,950),'Раскладка одного STL: только 3 пластины. Накладки из пружинного теста, крестовина и корпус прежние.' if v2 else 'Раскладка одного STL: 3 пластины + 4 новые накладки. Старые панель и крестовину не перепечатывать.',font=small,fill='#26394e')
d.text((30,1400),'Пружины и ход 0,65 мм прежние. Контакт с микрокнопками проверяется с платой на штатной высоте.' if v2 else 'Ход до упора в CAD: 0,65 мм. Упругость PETG и реальный возврат ещё нужно проверить на печатном узле.',font=small,fill='#9a3f3f')
dest=ROOT/('preview-reinforced-V2.png' if v2 else 'preview-split-springs.png')
im.save(dest)
print(dest)
