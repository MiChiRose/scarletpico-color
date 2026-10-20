#!/usr/bin/env python3
"""Local R3 edit: four LCD clip posts, 3 mm above the inner front floor.

The published original front is a read-only baseline. All exterior features,
display recesses, button interfaces and other fasteners remain unchanged.
Existing LCD clips are reused; no modified clip STL is necessary.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import manifold3d as m
import trimesh

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parent
OUT=ROOT/'output'
BASE=OUT/'01-front-R3.stl'
DEST=OUT/'01-front-R3-LCD-3mm.stl'
REPORT=OUT/'checks-LCD-3mm.json'
protected={p:hashlib.sha256(p.read_bytes()).hexdigest()
           for p in CASE.rglob('*.stl') if p!=DEST}
source=CASE/'rev2/build_rev2.py'
s={'__file__':str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0],str(source),'exec'),s)
box,cyl,union,solid,mesh_of=(s[k] for k in ('box','cyl','union','solid','mesh_of'))

floor=3.0
post_height=3.0
new_seat=floor+post_height
old_seat=s['R']['lcd_clip_seat']
drop=old_seat-new_seat
clip_grip=s['R']['lcd_clip_thickness']
pilot_depth=3.5
pilot_d=s['R']['pilot_diameter']
mounts=s['R']['lcd_mounts']
original=solid(trimesh.load_mesh(BASE,process=True))
front=original
zones=[]
for x,y in mounts:
    # Cut the complete old 5.5 mm boss down to the new seat, with a very
    # small XY allowance for float32 tessellation of the old round surface.
    front-=box(x-2.8,y-2.8,new_seat,5.6,5.6,old_seat-new_seat+.1)
    # The old pilot began at Z6.8, wholly above the new seat; drill a fresh
    # BLIND pilot. Its floor is Z2.5, well behind the outer face at Z0.
    front-=cyl(x,y,new_seat-pilot_depth,pilot_d,pilot_depth+.1)
    zones.append(box(x-2.81,y-2.81,new_seat-pilot_depth-.01,
                     5.62,5.62,old_seat-(new_seat-pilot_depth)+.12))
allowed=union(zones)

def clear(a,b,label,tol=.005):
    overlap=a ^ b
    assert overlap.volume()<tol,(label,overlap.volume())
def same(a,b,label,tol=.008):
    delta=(a-b).volume()+(b-a).volume()
    assert delta<tol,(label,delta)

assert front.status()==m.Error.NoError and len(front.decompose())==1
clear((original-front)+(front-original),original-allowed,'changes outside four LCD posts')
same(front-allowed,original-allowed,'non-LCD geometry changed')
assert (front-original).volume()<.005,'unexpected added material'
assert np.allclose(mesh_of(front).bounds,mesh_of(original).bounds,atol=.0001)

# Exact working interfaces of all eight tactile positions and six retainer
# seats remain untouched, even though two LCD posts also lie near Y74.
for name,(x,y) in s['centers'].items():
    zone=box(x-6,y-6,-3,12,12,16)
    same(front ^ zone,original ^ zone,'button interface '+name)
for x,y in s['R']['retainer_mounts']:
    zone=cyl(x,y,0,7.01,10)
    same(front ^ zone,original ^ zone,'button retainer seat')

clips=[c.translate([0,0,-drop]) for c in s['lcd_clips']]
old_mechanisms=[s['retainer'],s['dpad'],s['speaker_cap'],*s['caps'].values()]
for x,y in mounts:
    annulus=cyl(x,y,new_seat-.05,5.3,.05)-cyl(x,y,new_seat-.06,2.5,.07)
    same(front ^ annulus,annulus,'missing flat 3 mm post seat')
    clear(front,cyl(x,y,new_seat+.002,5.4,.05),'post too tall')
    clear(front,cyl(x,y,new_seat-pilot_depth+.01,pilot_d-.04,pilot_depth),
          'new blind pilot is obstructed')
    bore_floor=cyl(x,y,new_seat-pilot_depth-.15,pilot_d-.04,.14)
    same(front ^ bore_floor,bore_floor,'blind pilot breaks through floor')
    # New post top is exactly 3 mm above the nominal Z3 inner floor.
    inner_floor=box(x+3,y-.2,floor-.02,.25,.4,.018)
    same(front ^ inner_floor,inner_floor,'local inner-floor datum missing')
    head=cyl(x,y,new_seat+clip_grip,4.5,1.6)
    clear(head,front,'LCD screw head / front')
    for part in old_mechanisms:
        clear(head,part,'LCD screw head / existing mechanism')
for clip in clips:
    clear(clip,front,'lowered LCD clip / front')
    clear(clip,s['ns']['stack'],'lowered LCD clip / button PCB')
    clear(clip,s['scope']['battery']+s['scope']['battery_space'],
          'lowered LCD clip / battery envelope')
    for part in old_mechanisms:clear(clip,part,'lowered LCD clip / existing mechanism')

# Check the current experimental split-button frames as well, including
# independent preloaded/pressed leaf shapes. No STL is regenerated here.
spring_file=CASE/'button-bench-R3/split-spring-test/build_springs.py'
spring={'__file__':str(spring_file)}
exec(compile(spring_file.read_text().split('# Also verify the actually published R3 front')[0],
             str(spring_file),'exec'),spring)
for group,plate in spring['plates'].items():
    clear(plate,front,'split-button frame / lower-post front '+group)
    for clip in clips:clear(plate,clip,'split-button frame / lowered LCD clip '+group)
for name in spring['spec']:
    for q in np.linspace(0,spring['stroke'],5):
        moving=spring['moving'](name,spring['preload']+float(q))
        for clip in clips:clear(moving,clip,'pressed leaf / lowered LCD clip '+name)

engagement=6-clip_grip
assert engagement>=2.5 and pilot_depth-engagement>=.4

mesh=mesh_of(front.simplify(.0003))
mesh.vertices=np.round(mesh.vertices,4)
mesh.merge_vertices();mesh.update_faces(mesh.unique_faces())
mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
mesh.export(DEST)
readback=trimesh.load_mesh(DEST,process=True)
check=solid(readback)
assert check.status()==m.Error.NoError and len(check.decompose())==1
assert readback.is_watertight and readback.is_winding_consistent
same(check-allowed,original-allowed,'STL readback changed exterior / other interfaces',.02)
assert np.allclose(readback.bounds,mesh_of(original).bounds,atol=.0001)
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='CAD CHECKED / PHYSICAL LCD FIT NOT VERIFIED',
            source=BASE.name,source_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
            file=DEST.name,sha256=hashlib.sha256(DEST.read_bytes()).hexdigest(),
            bodies=1,watertight=True,dimensions_mm=readback.extents.round(3).tolist(),
            floor_z_mm=floor,post_height_above_inner_floor_mm=post_height,
            old_post_height_above_inner_floor_mm=old_seat-floor,
            new_clip_seat_z_mm=new_seat,shortened_by_mm=drop,
            mounting_centers_xy_mm=mounts,
            clip_toe_contact_z_mm=s['R']['lcd_clip_toe_front']-drop,
            existing_LCD_clip_STL_reused=True,
            screw='M2 x 6 self-tapping, without a washer',
            screw_grip_mm=clip_grip,thread_engagement_mm=engagement,
            pilot_diameter_mm=pilot_d,pilot_depth_mm=pilot_depth,
            pilot_floor_z_mm=new_seat-pilot_depth,
            pilot_bottom_margin_mm=pilot_depth-engagement,
            all_other_existing_STL_unchanged=True,
            checks=['only four local post/pilot regions changed',
                    'exterior, display recess, all button interfaces and six button seats unchanged',
                    'flat post top, empty pilot, blind floor verified',
                    'existing LCD clip shape reused at new height',
                    'lowered clips clear front, old mechanisms, split spring frames and leaves',
                    'lowered clips clear nominal battery and button PCB envelopes',
                    '6 mm screw has 3 mm grip, 3 mm engagement, 0.5 mm bottom margin',
                    'STL readback is one closed body; unchanged global bounds'],
            limitations=['Bare rear PCB contact height is approximated by user, not precisely measured.',
                         'Broad 95 x 59 x 8 mm LCD envelope is NOT a solid PCB model; clip-to-LCD contact and actual component clearance need physical verification.',
                         'Do not bend the LCD PCB by tightening against a height mismatch.',
                         'Washers lift the clip and reduce thread engagement with the same M2 x 6 screw; verify screw length if washers are later needed.'])
REPORT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
