#!/usr/bin/env python3
"""Unify the three V2 retainers using only two rigid outer side rails.

Moving leaves, rings, hard stops, D-pad pivot, cap datums and screw seats are
unchanged. No experimental front-side D-pad preload insert is incorporated.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import manifold3d as m
import trimesh

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parents[1]
DEST=ROOT/'00-UNIFIED-SPRING-RETAINER.stl'
protected={p:hashlib.sha256(p.read_bytes()).hexdigest()
           for p in CASE.rglob('*.stl') if p!=DEST}
src=ROOT/'reinforce_springs.py'
s={'__file__':str(src)}
exec(compile(src.read_text().split('files=[export')[0],str(src),'exec'),s)
box,cyl,union,mesh_of,solid,clear,equal=(s[k] for k in
    ('box','cyl','union','mesh_of','solid','clear','equal'))
seat,back=s['seat'],s['back'];dx,dy=s['dx'],s['dy']
plates=s['plates'];fixed=dict(s['fixed']);mounts=s['mounts']
caps=s['caps'];dpad=s['dpad'];moving=s['moving'];preload=s['preload'];stroke=s['stroke']
spec=s['s']['spec'];front=s['front'];clips=s['clips'];stack=s['stack'];speaker=s['speaker']
base=union(list(plates.values()))
assert len(base.decompose())==3

def rail(a,b):
    return (cyl(*a,seat,3,3)+cyl(*b,seat,3,3)).hull()
raw_links=rail((10.5,96.5),(10.5,113))+rail((92.5,84),(92.5,113))
links=raw_links
for x,y in sum(mounts.values(),[]):links-=cyl(x,y,seat-.1,2.3,3.2)
joined=base+links
rigid=union(list(fixed.values()))+links
assert joined.status()==m.Error.NoError and len(joined.decompose())==1
equal(joined-base,links-base,'unexpected modification outside side rails')
assert (base-joined).volume()<.004,'existing V2 material was removed'

for obstacle,label in [(front,'current LCD-3mm front'),(s['old_front'],'prior front'),
                       (stack,'button PCB'),(speaker,'speaker retainer'),
                       *[(q,'LCD clip') for q in clips],*[(q,'tact '+n) for n,q in s['tacts']]]:
    clear(joined,obstacle,'unified retainer / '+label)
for group,points in mounts.items():
    for x,y in points:
        zone=cyl(x,y,seat,6.99,3)
        equal(joined ^ zone,base ^ zone,'six original mounting seats changed')
        clear(cyl(x,y,back,4.5,1.6),joined,'screw head / unified retainer')

for name in spec:
    for q in np.linspace(0,stroke-.001,15):
        q=float(q);delta=preload+q
        cap=caps[name].translate([0,0,q])
        spring=moving(name,delta)
        clear(cap,rigid,'cap / joined rigid frame '+name)
        clear(s['s']['ring'](name,delta),rigid,'ring / joined rigid frame '+name)
        clear(moving(name,delta,True),rigid,'working leaf / joined frame '+name)
        clear(cap,spring,'cap / spring '+name)
    assert (s['s']['ring'](name,preload+stroke+.025) ^ rigid).volume()>.001
    # The entire working element stays exactly the V2 definition, while
    # the added rail volume is disjoint from the ring and free beam spans.
    clear(links-base,moving(name,0,True),'new material in working element '+name)
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    rocked=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(rocked,joined,'D-pad nominal rocking / unified retainer')
equal(joined ^ cyl(dx,dy,6.19,4.4,.15),base ^ cyl(dx,dy,6.19,4.4,.15),
      'D-pad central contact changed')

# FRONT down is necessary for the four thin spring platforms to begin on
# the bed. The D-pad central X/fulcrum begins 1.35 mm above that plane and
# needs local support/bridge review; flipping the complete part would put
# unsupported thin A/B and SS platforms above the bed instead.
offset=mesh_of(joined).bounds[0]
layout=[joined.translate(-offset)]
assert np.all(mesh_of(layout[0]).extents[:2]<210)
dp_region=box(dx-13,dy-13,seat,26,26,3.1)
dp_print=(joined ^ dp_region).translate([0,0,-seat])
growth=(dp_print.slice(1.36)-dp_print.slice(1.30)).area()
assert growth>1,'expected D-pad support condition was not detected'

mesh=mesh_of(layout[0].simplify(.0003))
mesh.vertices=np.round(mesh.vertices,4);mesh.merge_vertices()
mesh.update_faces(mesh.unique_faces())
mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
mesh.export(DEST)
readback=trimesh.load_mesh(DEST,process=True)
assert readback.is_watertight and readback.is_winding_consistent
assert len(solid(readback).decompose())==1
# Verify the actually exported mesh in assembly coordinates, not just the
# higher precision CSG before STL rounding.
assembled=solid(readback).translate(offset)
equal(assembled,joined,'STL export changed unified geometry',.025)
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='ONE CONNECTED BODY / CAD CHECKED / PHYSICAL TEST REQUIRED',
            file=DEST.name,bodies=1,watertight=True,
            dimensions_mm=readback.extents.round(3).tolist(),
            volume_cm3=round(readback.volume/1000,3),
            sha256=hashlib.sha256(DEST.read_bytes()).hexdigest(),
            source='three V2 retainers from reinforce_springs.py; read-only',
            added_connections=[dict(from_xy=[10.5,96.5],to_xy=[10.5,113],width_mm=3),
                               dict(from_xy=[92.5,84],to_xy=[92.5,113],width_mm=3)],
            changes='two rigid outside side rails only; no material removed from V2 parts',
            six_original_mounts_xy_mm=mounts,screw='six original M2 x 6, 3 mm grip',
            leaf_geometry_unchanged=True,leaf_thickness_mm=.8,ring_thickness_mm=1.2,
            preload_mm=preload,cap_stop_travel_mm=stroke,
            dpad_pivot_unchanged=True,front_changed=False,caps_changed=False,
            dpad_preload_insert_included=False,
            print_orientation='front down, spring platforms on bed; already oriented',
            raft_layers=0,
            support_note='Manual support only under D-pad central fulcrum/diagonal X, starting 1.35 mm above bed. Do NOT support moving AB/SS platforms or fill flexure gaps.',
            detected_Dpad_cross_section_growth_mm2=round(growth,3),
            checks=['single connected body; watertight STL readback',
                    'six mounting seats and screw-head clearance unchanged',
                    'only outside rails added; all original V2 geometry retained',
                    '15 sampled press positions per cap and nominal hard stops',
                    'D-pad cardinal and diagonal rocking; central pivot unchanged',
                    'current front with 3 mm LCD posts, lowered clips, PCB, tacts and speaker clearance',
                    'all pre-existing STL hashes unchanged'],
            limitations=['Joining rigid frames can alter their overall compliance; identical spring geometry does not prove identical measured finger force.',
                         'A single joined part cannot retain the three parts different print orientations; local D-pad support is needed.',
                         'Physical fit and tactile action with PCB fixed at nominal height still need verification.'])
(ROOT/'checks-unified.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
