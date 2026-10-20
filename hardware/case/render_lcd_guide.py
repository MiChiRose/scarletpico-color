#!/usr/bin/env python3
"""Illustrate existing R3 LCD mounting; does not alter any printable part."""
from pathlib import Path
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
source=ROOT/'rev2/build_rev2.py'
s={'__file__':str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0],str(source),'exec'),s)
box,cyl,mesh_of,solid=(s[k] for k in ('box','cyl','mesh_of','solid'))
front=solid(trimesh.load_mesh(ROOT/'rev3-split/output/01-front-R3.stl',process=True))
# Exact printable front is cropped only for explanation of its upper area.
front=front ^ box(-1,-1,-.1,105,81,31)
clips=s['lcd_clips']
# This is the measured outside envelope, NOT an invented PCB-component model.
lcd=box(4,11,2.002,95,59,7.998)
def screw(x,y,z):
    part=cyl(x,y,z-6,2,6)+cyl(x,y,z,4.5,1.35)
    return part-box(x-1.5,y-.3,z+.85,3,.6,.7)
fasteners=[screw(x,y,13.3) for x,y in s['R']['lcd_mounts']]

W,H=1850,1260
im=Image.new('RGB',(W,H),'#f3f4f6')
pixels=np.asarray(im).copy()
red,green,gold,metal=(171,66,76),(63,130,129),(231,176,62),(111,121,138)
def render(items,center,scale,origin,basis,rect):
    depth=np.full((H,W),-np.inf)
    basis=np.array(basis,dtype=float)
    def project(xyz):
        return ((np.asarray(xyz)-np.array(origin))@basis.T)[...,:2]*scale+center
    for part,color in items:
        mesh=mesh_of(part)
        vv=(mesh.vertices-np.array(origin))@basis.T
        for face,normal in zip(mesh.faces,mesh.face_normals):
            p=vv[face];xy=p[:,:2]*scale+center
            lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),rect[:2])
            hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),np.array(rect[2:])-1)
            if np.any(hi<lo):continue
            a,b,c=xy
            den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10:continue
            yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
            wc=1-wa-wb
            zz=wa*p[0,2]+wb*p[1,2]+wc*p[2,2]
            db=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>db)
            db[mask]=zz[mask]
            shade=.65+.33*abs(float(normal@np.array([.25,-.4,.88])))
            pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=tuple(int(v*shade) for v in color)
    return project

main=render([(front,red),(lcd,green),*[(c,gold) for c in clips],*[(q,metal) for q in fasteners]],
            [455,515],8.1,[51.5,39,9],
            [[-1,0,0],[0,.985,-.174],[0,.174,.985]],[25,145,905,915])

# Lower-right clip in assembly coordinates, exploded only along its Z axis.
i=3
x,y=s['R']['lcd_mounts'][i];ty=68.7
cut=box(x-3.6,ty-5,-.1,7.2,13.5,19)
local_front=front ^ cut
local_lcd=lcd ^ cut
raised_clip=clips[i].translate([0,0,6])
raised_screw=fasteners[i].translate([0,0,13])
pad=box(x-2,ty-1.5,12,4,3,.5)+cyl(x,ty,12.5,2.2,2.5)
exploded=render([(local_front,red),(local_lcd,green),(raised_clip,gold),
                 (raised_screw,metal),(pad,(238,216,158))],
                [1280,445],14,[x,71,12],
                [[.94,-.342,0],[.171,.47,-.866],[.296,.814,.5]],
                [950,160,1815,725])

# A real central section through the clip/post and an envelope section through
# the LCD. A nominal 0.15 mm gap is left visible instead of pretending that the
# rear component height is the bare PCB contact height.
slab=box(x-.25,63,-.1,.5,17,16)
section=render([((front ^ slab),red),((lcd ^ slab),green),
                ((clips[i] ^ slab),gold),((fasteners[i] ^ slab),metal)],
               [1290,1010],24,[x,70.5,6],
               [[0,1,0],[0,0,-1],[1,0,0]],[955,815,1815,1200])

im.paste(Image.fromarray(pixels))
d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Supplemental/Arial.ttf'
title=ImageFont.truetype(font,34)
sub=ImageFont.truetype(font,25)
small=ImageFont.truetype(font,21)
d.text((30,22),'Дисплей внутри корпуса ScarletPico R3',font=title,fill='#192a3b')
d.text((30,70),'Существующая геометрия корпуса и прижимов. Печатные детали не изменены.',font=sub,fill='#526170')
d.line((925,140,925,1210),fill='#d3d8df',width=2)
d.text((30,115),'1. Вид изнутри: четыре независимых прижима',font=sub,fill='#192a3b')
for n,(xx,yy) in enumerate(s['R']['lcd_mounts'],1):
    p=main([xx,yy,14.65]); p=np.array(p)
    label=p+np.array([35 if xx<50 else -35,-35 if yy<11 else 38])
    d.line((tuple(label),tuple(p)),fill='#26394e',width=2)
    r=16
    d.ellipse((label[0]-r,label[1]-r,label[0]+r,label[1]+r),fill='#fff8e5',outline='#9a6d15',width=2)
    d.text((label[0]-7,label[1]-12),str(n),font=small,fill='#5a3b00')
d.text((45,925),'Золотые детали — 07-four-LCD-clips-R2.stl',font=sub,fill='#62480e')
d.text((45,965),'Четыре прижима + четыре самореза M2×6.',font=sub,fill='#192a3b')
d.text((45,1005),'Прижимы заходят на края платы, а не на стекло.',font=sub,fill='#192a3b')
d.text((45,1050),'Зелёный блок — условный габарит модуля 95×59×8 мм.',font=small,fill='#526170')
d.text((45,1080),'Шлейфы, разъёмы и электронные компоненты не показаны.',font=small,fill='#526170')
d.text((45,1140),'Высоту контакта с голой платой нужно проверить на детали.',font=small,fill='#9a3f3f')
d.text((45,1170),'На компоненты или шлейф прижимать нельзя.',font=small,fill='#9a3f3f')

d.text((955,115),'2. Один прижим: разнесённый вид',font=sub,fill='#192a3b')
def callout(proj,point,label,xy):
    p=proj(point)
    d.line((tuple(p),xy),fill='#3d4b59',width=2)
    d.ellipse((p[0]-3,p[1]-3,p[0]+3,p[1]+3),fill='#3d4b59')
    d.text((xy[0]+7,xy[1]-13),label,font=small,fill='#26394e')
callout(exploded,[x,y,27.2],'Саморез M2×6',(1480,210))
callout(exploded,[x,ty+1,18.8],'Прижим 07',(1480,330))
callout(exploded,[x,ty,12.3],'Подкладка 08 — если есть люфт',(1430,435))
callout(exploded,[x,y,9.5],'Стойка переднего корпуса',(1450,540))
d.text((960,675),'Саморез входит в стойку. Сквозь дисплей он не проходит.',font=small,fill='#526170')
d.text((955,755),'3. Разрез установленного узла',font=sub,fill='#192a3b')
callout(section,[x,67.35,10.15],'Конец прижима над краем платы',(1480,855))
callout(section,[x,74,7.7],'Резьба в пластиковой стойке',(1480,1080))
d.text((955,1215),'Не устранять зазор силовым изгибом прижима или платы.',font=small,fill='#9a3f3f')

OUT=ROOT/'rev3-split/output/lcd-mount-guide-R3.png'
im.save(OUT)
print(OUT)
