#!/usr/bin/env python3
"""Replacement plate only after the R2/R3 printed button test failed.

Retain the six existing screw seating planes, screws, front panel, caps and
D-pad. Recess and thin the working sheet; eliminate short-stem guide bores.
This is a physical fit-test candidate, not an accepted production revision.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parents[1]
source=CASE/'rev2/build_rev2.py'
protected={p:hashlib.sha256(p.read_bytes()).hexdigest()
           for folder in (CASE/'rev2',CASE/'rev3-split') for p in folder.rglob('*.stl')}
s={'__file__':str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0],str(source),'exec'),s)
box,cyl,cross,rounded,union,mesh_of,solid=(s[k] for k in
    ('box','cyl','cross','rounded','union','mesh_of','solid'))
R=s['R'];caps=s['caps'];dpad=s['dpad'];dx,dy=s['dx'],s['dy'];centers=s['centers']
front=s['front']
seat=R['retainer_front']
back=seat+R['retainer_thickness']
sheet_thickness=1.2
sheet_front=back-sheet_thickness
clear_d=R['clearance_diameter']

# One thin working sheet. Its front is recessed 1.8 mm relative to the old
# stop plane; its back remains exactly at 7.85 mm, avoiding changes to PCB
# clearance or the under-head seating height of any screw.
plate=box(16.5,73,sheet_front,70,50,sheet_thickness)
plate-=cross(dx,dy,sheet_front-.1,27.6,10.3,sheet_thickness+.2)
for name in ('A','B','SELECT','START'):
    x,y=centers[name]
    # Whole 6x6 tactile body passes into a generous rounded 7x7 window.
    # No small blind guide hole can grip the printed central stem.
    plate-=rounded(x,y,sheet_front-.1,7,7,1,sheet_thickness+.2)

# Preserve the D-pad's front fulcrum and diagonals. Trim ONLY the rear 0.35 mm
# of this region to make all back faces coplanar for support-free plate print.
pivot_zone=box(dx-13,dy-13,6.2,26,26,back-6.2)
plate+=s['retainer'] ^ pivot_zone
for name in ('UP','DOWN','LEFT','RIGHT'):
    x,y=centers[name]
    plate-=box(x-3.3,y-3.3,5.95,6.6,6.6,6.3)

# Thick screw pads are local islands, not a thick working plate. Same 3 mm
# screw grip => same 3 mm engagement and 0.5 mm pilot-bottom margin as R2.
for x,y in R['retainer_mounts']:
    if x<16.5 or x>86.5:
        edge=17 if x<16.5 else 86
        plate+=(cyl(x,y,sheet_front,7,sheet_thickness)+
                cyl(edge,y,sheet_front,7,sheet_thickness)).hull()
    plate+=cyl(x,y,seat,7,back-seat)
    plate-=cyl(x,y,seat-.1,clear_d,back-seat+.2)

def clear(a,b,label,tol=.003):
    v=(a ^ b).volume()
    assert v<tol,(label,v)
def same(a,b,label,tol=.003):
    v=(a-b).volume()+(b-a).volume()
    assert v<tol,(label,v)

assert plate.status()==m.Error.NoError and len(plate.decompose())==1
clear(plate,front,'new plate / existing panel')
clear(plate,s['ns']['stack'],'new plate / nominal board stack')
clear(plate,dpad,'new plate / existing D-pad')
same(plate ^ pivot_zone,s['retainer'] ^ pivot_zone,'D-pad support front region changed')
for x,y in R['retainer_mounts']:
    zone=cyl(x,y,seat,6.99,3)
    same(plate ^ zone,s['retainer'] ^ zone,'screw pad geometry changed')
    clear(cyl(x,y,back,4.5,1.6),s['ns']['stack'],'screw head / PCB')
assert abs((6-(back-seat))-3)<1e-9

flange_top=R['cap_flange_front']+R['cap_flange_thickness']
nominal_free_travel=sheet_front-flange_top
assert abs(nominal_free_travel-2.55)<1e-6
for name,cap in caps.items():
    clear(cap,plate,'neutral cap / plate '+name)
    assert (cap.translate([0,0,-.05]) ^ front).volume()>.001,'cap can escape '+name
    for travel in np.linspace(0,nominal_free_travel-.001,40):
        moved=cap.translate([0,0,float(travel)])
        clear(moved,plate,'cap free travel / plate '+name)
        clear(moved,front,'cap free travel / front '+name)
    assert (cap.translate([0,0,nominal_free_travel+.02]) ^ plate).volume()>.001, 'missing cap stop '+name
    # Geometric allowance, NOT a prediction of PETG stiffness or tolerance.
    # Assume 0.4 mm extra flange thickness and 0.4 mm stem oversize.
    x,y=centers[name]
    if name in ('A','B'):
        excess=cyl(x,y,3,10.8,1.5)
    else:
        excess=rounded(x,y,3,9.8,9,.8,1.5)
    excess+=cyl(x,y,4,3.4,1.75)
    for travel in np.linspace(0,1.5,16):
        clear((cap+excess).translate([0,0,float(travel)]),plate,'oversize cap / plate '+name)
for name,(x,y) in centers.items():
    clear(box(x-3,y-3,6.05,6,6,6),plate,'tactile body / plate '+name)
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    moved=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(moved,plate,'D-pad rocking / plate')

# Print flat BACK side on the bed. All screw pad backs and the sheet back
# coincide, with no floating wide sheet requiring support under its surface.
mesh=mesh_of(plate.simplify(.0003))
mesh.vertices[:,1]*=-1
mesh.vertices[:,2]*=-1
mesh.apply_translation(-mesh.bounds[0])
mesh.vertices=np.round(mesh.vertices,4)
mesh.merge_vertices();mesh.update_faces(mesh.unique_faces())
mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
path=ROOT/'03-button-retainer-THIN-TEST.stl'
mesh.export(path)
readback=trimesh.load_mesh(path,process=True)
assert readback.is_watertight and readback.is_winding_consistent and len(solid(readback).decompose())==1
print_solid=solid(readback)
for z in np.linspace(.051,2.95,60):
    overhang=(print_solid.slice(float(z))-print_solid.slice(float(z-.05))).area()
    assert overhang<.01,('unsupported plate section',z,overhang)

# A precise top/back view plus a side view of the actual plate. These show the
# small thick screw islands separately from the thin working sheet.
im=Image.new('RGB',(1500,1050),'#f3f4f6');pixels=np.asarray(im).copy()
def render(items,center,scale,origin,basis,rect):
    depth=np.full((1050,1500),-np.inf);basis=np.array(basis)
    for geom,color in items:
        mm=mesh_of(geom);vv=(mm.vertices-np.array(origin))@basis.T
        for face,normal in zip(mm.faces,mm.face_normals):
            p=vv[face];xy=p[:,:2]*scale+center
            lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),rect[:2])
            hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),np.array(rect[2:])-1)
            if np.any(hi<lo):continue
            a,b,c=xy;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10:continue
            yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wc=1-wa-wb
            zz=wa*p[0,2]+wb*p[1,2]+wc*p[2,2];db=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>db);db[mask]=zz[mask]
            shade=.66+.32*abs(float(normal@np.array([.25,-.4,.88])))
            pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=tuple(int(v*shade) for v in color)
blue=(61,128,166);red=(172,67,76);dark=(53,59,68)
render([(plate,blue)],[750,410],10,[51.5,98,6],[[1,0,0],[0,.94,.342],[0,.342,-.94]],[30,130,1470,730])
light_front=front ^ box(6.5,70.5,-.01,90,53.5,4.87)
render([(light_front,red),(plate,blue),*[(c,dark) for c in caps.values()],(dpad,dark)],
       [750,800],12,[51.5,98,4],[[1,0,0],[0,0,-1],[0,1,0]],[30,730,1470,925])
im.paste(Image.fromarray(pixels));draw=ImageDraw.Draw(im)
font='/System/Library/Fonts/Supplemental/Arial.ttf'
title=ImageFont.truetype(font,30);small=ImageFont.truetype(font,23)
draw.text((30,25),'THIN TEST / замена только прижимной пластины',font=title,fill='#192a3b')
draw.text((30,75),'Полотно 1,2 мм; шесть посадок саморезов по 3 мм. Панель и накладки прежние.',font=small,fill='#526170')
draw.text((30,935),'Без платы: номинальный свободный ход накладок 2,55 мм вместо 0,75 мм.',font=small,fill='#192a3b')
draw.text((30,975),'Это не ход микрокнопки и не подтверждение физической посадки. Проверить печатью.',font=small,fill='#9a3f3f')
im.save(ROOT/'preview-thin-test.png')
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='TEST CANDIDATE / NOT PHYSICALLY VERIFIED',production_parts_changed=False,
            prior_test='R2/R3 plate physically failed: A/B and Start/Select bind; caps move freely with plate removed.',
            sheet_thickness_mm=sheet_thickness,original_sheet_thickness_mm=3,
            screw_seat_front_z_mm=seat,screw_pad_thickness_mm=3,screw_seat_back_z_mm=back,
            screw='six existing M2 x 6 self-tappers; original screw grip and pilot engagement retained',
            nominal_free_cap_travel_without_PCB_mm=nominal_free_travel,
            original_free_cap_travel_without_PCB_mm=.75,
            tiny_stem_guide_holes_removed=True,tactile_body_windows_mm=[7,7],
            Dpad_front_pivot_z_mm=6.2,Dpad_rear_support_trimmed_mm=.35,
            caps_and_front_panel_reused=True,PCB_height_not_fixed_by_light_test=True,
            tests=['nominal cap travel and stops','oversize-cap geometric clearance',
                   'nominal tactile and PCB clearance','original screw seating regions',
                   'D-pad rocking','STL readback watertight single solid','no unsupported growth in sampled print sections',
                   'production STL hashes unchanged'],
            print_orientation='flat back on bed, recessed screw-pad/toe side up; assembly: this recessed side faces front panel',
            STL_dimensions_mm=readback.extents.round(3).tolist(),
            volume_cm3=round(readback.volume/1000,3),
            old_retainer_volume_cm3=round(s['retainer'].volume()/1000,3),
            limitations=['Actual source of the printed binding is localized to plate/cap interaction but not independently measured.',
                         'Geometric oversize checks are not force, PETG fatigue or physical fit tests.',
                         'No change to real tactile switch stroke; no promise of automatic return without PCB.'])
(ROOT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
