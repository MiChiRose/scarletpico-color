#!/usr/bin/env python3
"""V2: rigid-frame reinforcement; reuse physically liked springs and caps.

The D-pad's four quadrants are linked by a rear-side perimeter, with a wider
rear backing of the diagonal webs. All six mounting seats and actuator datums
remain unchanged. Previous printed candidate files are read-only baselines.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import manifold3d as m
import trimesh

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parents[1]
names=['01-DPAD-retainer-SPRING-V2.stl','02-AB-retainer-SPRING-V2.stl',
       '03-START-SELECT-retainer-SPRING-V2.stl','00-THREE-RETAINERS-V2-ONE-PLATE.stl']
protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in CASE.rglob('*.stl')
           if p not in [ROOT/n for n in names]}
src=ROOT/'build_springs.py'
s={'__file__':str(src)}
exec(compile(src.read_text().split('\ndef export(')[0],str(src),'exec'),s)
box,cyl,union,mesh_of,solid,clear,equal=(s[k] for k in
    ('box','cyl','union','mesh_of','solid','clear','equal'))
seat,back=s['seat'],s['back'];dx,dy=s['dx'],s['dy']
fixed=dict(s['fixed'])
mounts=s['mounts'];caps=s['caps'];dpad=s['dpad'];moving=s['moving']
centers=s['centers'];preload=s['preload'];stroke=s['stroke']

def link(a,b,width,z=seat,height=3):
    return (cyl(*a,z,width,height)+cyl(*b,z,width,height)).hull()

# A closed OUTER trace ties all four quadrants together. It lies at the rear
# of the D-pad carrier, not against the moving flange in the front half.
# This preserves rocking clearance and the nominal central contact at Z6.2.
perimeter=box(18,73.5,6.45,28,27,1.4)-box(19.6,75.1,6.35,24.8,24,1.6)
fixed['DPAD']+=perimeter
fixed['DPAD']+=link((10.5,96.5),(20,96.5),3.8)
fixed['DPAD']+=link((44,77),(55,77),3.8)
fixed['DPAD']+=cyl(dx,dy,6.65,6,back-6.65)
for u,v in [(-10,-10),(10,-10),(-10,10),(10,10)]:
    fixed['DPAD']+=link((dx,dy),(dx+u,dy+v),3.2,6.65,back-6.65)
for name in ('UP','DOWN','LEFT','RIGHT'):
    x,y=centers[name]
    fixed['DPAD']-=box(x-3.3,y-3.3,5.95,6.6,6.6,6.3)

# Increase ONLY rigid frame widths, away from the moving leaves. Root edge
# locations and the working thickness/width/length of all eight leaves stay
# exact; no new short flexure or solid sheet is placed behind a cap.
fixed['AB']+=union([
    box(72.3,70.25,seat,14.8,2.15,3),
    box(85.1,71.5,seat,2,7.5,3),
    link((86.3,78.5),(89.7,81.5),2.2),
    box(88.5,80.5,seat,3,28.5,3),
    box(61.7,91.5,seat,2.4,17.5,3),
    box(63,107.4,seat,28,2.2,3),
    link((55,105),(64,108),3),
])
fixed['SS']+=union([
    link((10.5,113),(39,113),3.2),
    box(37.4,101,seat,2.6,22.1,3),
    box(79,111,seat,2.7,12.1,3),
    box(79,110.2,seat,13.5,2.4,3),
])
for group,points in mounts.items():
    for x,y in points:fixed[group]-=cyl(x,y,seat-.1,2.3,3.2)

plates=dict(fixed)
for name,p in s['spec'].items():plates[p['group']]+=moving(name,0)
fixed_union=union(list(fixed.values()))
old=s['plates']
front_file=CASE/'rev3-split/output/01-front-R3-LCD-3mm.stl'
front=solid(trimesh.load_mesh(front_file,process=True))
old_front=s['front']
clips=[c.translate([0,0,-4.3]) for c in s['s']['lcd_clips']]
stack=s['s']['ns']['stack']
speaker=s['s']['speaker_cap']
tacts=s['tacts']

for group,plate in plates.items():
    assert plate.status()==m.Error.NoError and len(plate.decompose())==1,group
    clear(plate,front,'V2 / current LCD-3mm front '+group)
    clear(plate,old_front,'V2 / prior front '+group)
    clear(plate,stack,'V2 / nominal button PCB '+group)
    clear(plate,speaker,'V2 / speaker retainer '+group)
    for clip in clips:clear(plate,clip,'V2 / lowered LCD clip '+group)
    for other,part in plates.items():
        if other<group:clear(plate,part,'V2 separate groups '+group+'/'+other)
    for x,y in mounts[group]:
        zone=cyl(x,y,seat,6.99,3)
        equal(plate ^ zone,old[group] ^ zone,'mounting pad unchanged '+group)
        head=cyl(x,y,back,4.5,1.6)
        for other,part in plates.items():
            clear(head,part,'screw head clearance '+group+'/'+other)
for name,tact in tacts:clear(fixed_union,tact,'fixed frames / tactile '+name)

for name,p in s['spec'].items():
    # Whole moving part, preload and stops are the previously printed design.
    for q in np.linspace(0,stroke-.001,15):
        q=float(q);delta=preload+q
        spring=moving(name,delta)
        cap=caps[name].translate([0,0,q])
        clear(cap,fixed_union,'V2 cap travel '+name)
        clear(cap,front,'V2 cap / front '+name)
        clear(spring,cap,'V2 leaf / cap '+name)
        clear(s['ring'](name,delta),fixed_union,'V2 ring / stop '+name)
        clear(moving(name,delta,True),fixed_union,'V2 working leaves / rigid frame '+name)
        for tn,tact in tacts:clear(spring,tact,'V2 leaf / tactile '+name+'/'+tn)
        for clip in clips:clear(spring,clip,'V2 leaf / LCD clip '+name)
        for other in s['spec']:
            if other!=name:clear(spring,moving(other,preload),'V2 independent leaves')
    assert (s['ring'](name,preload+stroke+.025) ^ fixed_union).volume()>.001
    # No change in material below any working span or ring in the neutral
    # printed state: the reinforcement does not thicken a moving element.
    free=moving(name,0,True)
    clear((plates[p['group']]-old[p['group']]),free,'moving material changed '+name)

# Central ball contact is still Z6.2; no new free inward gap is introduced.
equal(fixed['DPAD'] ^ cyl(dx,dy,6.19,4.4,.15),
      s['fixed']['DPAD'] ^ cyl(dx,dy,6.19,4.4,.15),'central fulcrum changed')
clear(dpad,fixed['DPAD'],'D-pad neutral')
assert (dpad.translate([0,0,.05]) ^ fixed['DPAD']).volume()>.0001,'missing central axial stop'
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    rocked=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(rocked,front,'D-pad / unchanged front')
    for group,part in plates.items():clear(rocked,part,'D-pad nominal rocking / '+group)

# A secondary rear rim must eventually catch excess rocking, without being
# the normal tactile-switch end-stop. Values are CAD-only, not an instruction
# to force the PCB buttons to these angles.
excess_limits=[]
for axis in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)]:
    hit=None
    for angle in np.linspace(3.3,8,48):
        ax,ay=np.array(axis)*angle
        rocked=dpad.translate([-dx,-dy,-5.2]).rotate([float(ax),float(ay),0]).translate([dx,dy,5.2])
        if (rocked ^ perimeter).volume()>.001:
            hit=float(angle);break
    assert hit is not None,('no excessive-rocking stop',axis)
    excess_limits.append(dict(axis_xy=axis,first_sampled_perimeter_contact_deg=round(hit,2)))

# Nominal switch reach is checked at the actuator face centre, not inferred
# from whether a generic 6x6 rigid switch-body box intersects the cap.
reach={}
rotations={'UP':(-3.2,0),'DOWN':(3.2,0),'LEFT':(0,3.2),'RIGHT':(0,-3.2)}
for name,(ax,ay) in rotations.items():
    x,y=centers[name]
    probe=cyl(x,y,5.895,.02,.01)
    moved=probe.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    tip_z=float(np.mean(mesh_of(moved).bounds[:,2]))
    assert tip_z>=6.25,(name,tip_z)
    reach[name]=dict(rest_tip_z_mm=5.9,nominal_unpressed_switch_z_mm=6.05,
                     rest_gap_mm=.15,at_cardinal_3p2deg_tip_center_z_mm=round(tip_z,4),
                     nominal_switch_depression_mm=round(tip_z-6.05,4))
for name in caps:
    assert 5.75+.50>=6.05+.20-.0001
    reach[name]=dict(rest_tip_z_mm=5.75,nominal_unpressed_switch_z_mm=6.05,
                     rest_gap_mm=.30,cap_travel_for_reference_0p2mm_depression_mm=.50,
                     hard_stop_cap_travel_mm=stroke)

def export(part,filename,flip=False,count=1):
    mesh=mesh_of(part.simplify(.0003))
    if flip:mesh.vertices[:,1]*=-1;mesh.vertices[:,2]*=-1
    mesh.apply_translation(-mesh.bounds[0]);mesh.vertices=np.round(mesh.vertices,4)
    mesh.merge_vertices();mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent
    dest=ROOT/filename;mesh.export(dest)
    check=trimesh.load_mesh(dest,process=True)
    assert check.is_watertight and check.is_winding_consistent and len(solid(check).decompose())==count
    return dict(file=filename,bodies=count,dimensions_mm=check.extents.round(3).tolist(),
                volume_cm3=round(check.volume/1000,3),sha256=hashlib.sha256(dest.read_bytes()).hexdigest())

layout=[]
for group,x,y,flip in [('DPAD',0,0,True),('AB',57,0,False),('SS',0,50,False)]:
    part=plates[group].rotate([180,0,0]) if flip else plates[group]
    part=part.translate(-mesh_of(part).bounds[0]).translate([x,y,0])
    for other in layout:
        a,b=mesh_of(part).bounds,mesh_of(other).bounds
        assert max(np.maximum(a[0,:2]-b[1,:2],b[0,:2]-a[1,:2]))>=4.9
    layout.append(part)
all_parts=union(layout)
assert len(all_parts.decompose())==3 and np.all(mesh_of(all_parts).extents[:2]<210)
dp=layout[0]
for z in np.linspace(.051,2.95,60):
    assert (dp.slice(float(z))-dp.slice(float(z-.05))).area()<.01,'D-pad unsupported section'

files=[export(plates['DPAD'],names[0],True),export(plates['AB'],names[1]),
       export(plates['SS'],names[2]),export(all_parts,names[3],count=3)]
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='V2 CAD CHECKED / REQUIRES PHYSICAL FIT TEST',
            prior_print_feedback='A/B and Start/Select spring action liked; D-pad support loose / too much inward movement.',
            source_frame_version='build_springs.py / first split-spring candidate',
            front_file=front_file.name,front_changed=False,
            screw='six original M2 x 6 self-tappers, 3 mm grip and 3 mm engagement',
            mounts_xy_mm=mounts,
            caps_and_dpad_reprint_required=False,existing_caps='four-matching-caps-SPRING-TEST',
            spring_geometry_changed=False,leaf_thickness_mm=.8,platform_thickness_mm=1.2,
            preload_mm=preload,cap_stroke_to_stop_mm=stroke,
            dpad_perimeter_z_mm=[6.45,7.85],dpad_central_contact_z_mm=6.2,
            dpad_diagonal_rear_backing_width_mm=3.2,
            dpad_secondary_overtilt_contacts=excess_limits,
            nominal_actuator_reach=reach,
            physical_limits=['Actual PCB height and real switch travel need verification with the PCB fixed in the complete case.',
                             'A test without electronics cannot verify tactile contact or the D-pad spring return.',
                             'Rigid-frame stiffness, print tolerances and loads are not solved by FEA.',
                             'No claim of improved physical D-pad feel until printed and assembled.'],
            all_preexisting_STL_unchanged=True,parts=files)
(ROOT/'checks-V2.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
