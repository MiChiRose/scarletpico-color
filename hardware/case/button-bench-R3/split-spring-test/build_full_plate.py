#!/usr/bin/env python3
"""Strict old rectangular outline and ears, with internal spring mechanisms.

Straight A leaves inside the old outline; symmetric D-pad windows.
The central D-pad fulcrum and all six mounting seats remain unchanged.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import manifold3d as m
import trimesh

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parents[1]
DEST=ROOT/'00-RECTANGULAR-SYMMETRIC-DPAD-RETAINER.stl'
protected={p:hashlib.sha256(p.read_bytes()).hexdigest()
           for p in CASE.rglob('*.stl') if p!=DEST}
src=ROOT/'reinforce_springs.py'
s={'__file__':str(src)}
exec(compile(src.read_text().split('files=[export')[0],str(src),'exec'),s)
box,cyl,union,mesh_of,solid,clear,equal=(s[k] for k in
    ('box','cyl','union','mesh_of','solid','clear','equal'))
seat,back=s['seat'],s['back'];dx,dy=s['dx'],s['dy']
plates=s['plates'];fixed=s['fixed'];mounts=s['mounts']
spec=s['s']['spec'];old_moving=s['moving'];caps=s['caps'];dpad=s['dpad']
preload,stroke=s['preload'],s['stroke'];centers=s['centers']

# Exact original main rectangle and lateral ear profiles, used as a hard
# envelope, not just an extra sheet below protruding V2 frames.
envelope=box(16.5,73,seat,70,50,back-seat)
for x,y in sum(mounts.values(),[]):
    if x<16.5 or x>86.5:
        edge=17 if x<16.5 else 86
        envelope+=(cyl(x,y,seat,7,3)+cyl(edge,y,seat,7,3)).hull()
blank=envelope

# A's roots are inside the old rectangle. Use straight leaves as requested;
# the 8.3 mm span is shorter than the original 10.3 mm, so the force may rise.
# Thickness, ring, cap, actuator and press-stop heights remain unchanged.
a_roots=[(74,74.4),(82.8,74.4)]
a_tips=spec['A']['tips']
target_length=8.3
def a_beam(root,tip,delta,trim_root=False):
    return s['s']['beam'](root,tip,delta,trim_root)

def moving(name,delta,trim_roots=False):
    if name!='A':return old_moving(name,delta,trim_roots)
    return s['s']['ring'](name,delta)+union([
        a_beam(r,t,delta,trim_roots) for r,t in zip(a_roots,a_tips)])

fixed={g:(part ^ envelope) for g,part in fixed.items()}
curve_clear=union([a_beam(r,t,0) for r,t in zip(a_roots,a_tips)])
curve_clear=curve_clear.project().offset(.6,circular_segments=24).extrude(3.2).translate([0,0,seat-.1])
fixed['AB']-=curve_clear
fixed['AB']+=box(72.3,73,seat,12.2,1.4,3)
# Close the artificial through-slit below the local D-pad carrier at the
# REAR only. Its front-side rocked-flange clearance remains a shallow pocket.
dpad_rear_bridge=box(18,100.45,6.45,28,1.55,1.4)
fixed['DPAD']+=dpad_rear_bridge
for name in spec:
    clear(moving(name,0)-envelope,box(0,0,-5,150,160,20),
          'moving mechanism outside strict old outline '+name)
base=union(list(fixed.values()))+union([moving(n,0) for n in spec])

def through(profile):
    return profile.extrude(back-seat+.2).translate([0,0,seat-.1])

# No new broad-sheet material anywhere in the D-pad working region.
dpad_zone=box(18,73.5,seat-.1,28,27,3.2)
blank-=dpad_zone
rock_angles=[(0,0),(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]
for ax,ay in rock_angles:
    rocked=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    blank-=through(rocked.project().offset(.35,circular_segments=24))
slot_masks=[]
for name,p in spec.items():
    x,y=centers[name]
    # Full platforms, not only the 7.2 mm tactile holes. Leave 0.6 mm extra
    # around both long spring spans, including their original root joint.
    outline=moving(name,0).project().offset(.6,circular_segments=24)
    platform=(cyl(x,y,0,12,1) if p['shape']=='round' else
              s['s']['rounded'](x,y,0,11.2,10.4,1.4,1))
    mask=through(outline)+through(platform.project())
    blank-=mask
    slot_masks.append(mask)

# Clear nominal tactile bodies and adjacent components independently of
# spring masks. These cuts affect only the added broad sheet, never V2.
for name,tact in s['tacts']:
    blank-=through(tact.project().offset(.3,circular_segments=24))
obstacles=[(s['front'],'current LCD-3mm front'),(s['old_front'],'prior front'),
           (s['stack'],'button PCB'),(s['speaker'],'speaker retainer'),
           *[(q,'lowered LCD clip') for q in s['clips']]]
for obstacle,label in obstacles:
    # Do not project the front-panel screw posts just below the seating
    # interface: that made needless annular slits around all screw pads.
    local=obstacle ^ box(6.5,69.5,seat+.01,90,54,back-seat-.02)
    if local.volume()>.0001:
        blank-=through(local.project().offset(.3,circular_segments=24))
for x,y in sum(mounts.values(),[]):blank-=cyl(x,y,seat-.1,2.3,3.2)

joined=base+blank
# The clipped local V2 carrier and added rear bridge had unequal distances
# from the D-pad centre. Take the UNION of existing voids under all quarter
# turns: enlarge the small windows to match, never shrink the larger ones.
# Restrict this to the D-pad cross so no button or screw geometry changes.
dpad_cross=s['s']['cross'](dx,dy,seat,27.6,10.3,back-seat)
old_dpad_solid=joined ^ dpad_cross
def quarter_turn(part,angle):
    return part.translate([-dx,-dy,0]).rotate([0,0,angle]).translate([dx,dy,0])
dpad_z_breaks=[seat,5.95,6.2,6.45,6.65,back]
cross_profile=dpad_cross.slice((seat+back)/2)
void_layers=[];solid_layers=[]
for z0,z1 in zip(dpad_z_breaks,dpad_z_breaks[1:]):
    free=cross_profile-joined.slice((z0+z1)/2)
    symmetric=free
    for angle in (90,180,270):
        symmetric+=free.translate([-dx,-dy]).rotate(angle).translate([dx,dy])
    # Materialize lazy CrossSection Boolean expressions before extrusion.
    symmetric=m.CrossSection(symmetric.to_polygons(),m.FillRule.Positive)
    kept=m.CrossSection((cross_profile-symmetric).to_polygons(),m.FillRule.Positive)
    assert abs(symmetric.area()+kept.area()-cross_profile.area())<.002
    # Build simple 2D extrusions instead of intersecting four nearly
    # coplanar 3D web meshes; this avoids fragile diagonal junction slivers.
    # Empty CrossSection.extrude returns InvalidConstruction in this
    # Manifold build; never include such a layer in a later Boolean union.
    if symmetric.area()>1e-6:
        void_layers.append(symmetric.extrude(z1-z0).translate([0,0,z0]))
    if kept.area()>1e-6:
        # Overlap the patch into existing material by 0.02 mm at its OUTER
        # seam; subtract the same void again so no window is made smaller.
        # Exact butt joints otherwise split off a narrow side-rim island
        # because of float rounding along the cross boundary.
        lapped=kept.offset(.02,circular_segments=24)-symmetric
        solid_layers.append(lapped.extrude(z1-z0).translate([0,0,z0]))
symmetric_void=union(void_layers)
symmetric_local=union(solid_layers)
dpad_removed=(joined ^ symmetric_void).volume()
joined=(joined-dpad_cross)+symmetric_local
base-=symmetric_void
blank-=symmetric_void
fixed={g:part-symmetric_void for g,part in fixed.items()}
new_dpad_solid=symmetric_local
for angle in (90,180,270):
    equal(new_dpad_solid,quarter_turn(new_dpad_solid,angle),
          'D-pad solid not quarter-turn symmetric',.005)
# Manifold.project() can leave asymmetric shadow slivers from coplanar
# triangle edges even when the solid is symmetric. The local D-pad is a
# union of constant-section extrusions at these exact Z breakpoints. Union
# one interior slice per interval to measure its true through footprint.
def dpad_footprint(part):
    result=m.CrossSection()
    for z0,z1 in zip(dpad_z_breaks,dpad_z_breaks[1:]):
        result+=part.slice((z0+z1)/2)
    return result
through_holes=cross_profile-dpad_footprint(new_dpad_solid)
windows=through_holes.decompose()
assert len(windows)==4,('expected four separate through windows',len(windows))
window_areas=[float(q.area()) for q in windows]
assert max(window_areas)-min(window_areas)<.002,'D-pad window areas unequal'
for angle in (90,180,270):
    rotated=through_holes.translate([-dx,-dy]).rotate(angle).translate([dx,dy])
    assert (through_holes-rotated).area()+(rotated-through_holes).area()<.002
# A U-shaped pair of spring slots may enclose an unattached scrap of sheet.
# Remove only these new islands; require every original mechanism to remain
# in the single retained component.
components=joined.decompose()
joined=max(components,key=lambda q:q.volume())
assert (base-joined).volume()<.004,'a working mechanism became disconnected'
removed_island_volume=sum(q.volume() for q in components)-joined.volume()
blank=blank ^ joined
added=joined-base
rigid=union(list(fixed.values()))+blank
assert joined.status()==m.Error.NoError and len(joined.decompose())==1
assert (base-joined).volume()<.004,'original V2 material removed'
assert added.volume()>3000,'broad sheet not restored'
assert (joined-envelope).volume()<.004,'protrusion beyond old rectangle/ears'
clear(added,dpad_zone,'D-pad local carrier modified')
for obstacle,label in obstacles:clear(joined,obstacle,'full outline / '+label)
for name,tact in s['tacts']:clear(joined,tact,'full outline / tactile '+name)
for group,points in mounts.items():
    for x,y in points:
        zone=cyl(x,y,seat,6.99,3)
        equal(joined ^ zone,union(list(plates.values())) ^ zone,'six original screw seats changed')
        clear(cyl(x,y,back,4.5,1.6),joined,'screw head / full plate')
        # Only actual spring slots may approach the seating pad. No
        # circular projection-derived isolation groove is permitted.
        expected=(cyl(x,y,seat,7.6,3) ^ envelope)-cyl(x,y,seat-.1,2.3,3.2)
        expected-=union(slot_masks)
        assert (expected-joined).volume()<.004,'unnecessary slit around screw seat'
assert ((dpad_rear_bridge-symmetric_void)-joined).volume()<.004,'D-pad rear joining bridge missing'

for name in spec:
    # Added material must not touch even the undeformed whole leaf; only
    # original fixed headers and root joints determine its clamped length.
    clear(added,moving(name,0),'added sheet / original spring '+name)
    for q in np.linspace(0,stroke-.001,15):
        q=float(q);delta=preload+q
        clear(caps[name].translate([0,0,q]),rigid,'cap travel / full plate '+name)
        clear(s['s']['ring'](name,delta),rigid,'moving platform / full plate '+name)
        clear(moving(name,delta,True),rigid,'free working leaves / full plate '+name)
    assert (s['s']['ring'](name,preload+stroke+.025) ^ rigid).volume()>.001
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    rocked=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(rocked,joined,'D-pad nominal rocking / full plate')
pivot_zone=cyl(dx,dy,6.19,4.4,.15)
equal(joined ^ pivot_zone,union(list(plates.values())) ^ pivot_zone,'central fulcrum changed')

offset=mesh_of(joined).bounds[0]
layout=[joined.translate(-offset)]
# Do not independently simplify symmetric diagonal junctions: topology
# simplification can choose different vertices in the four rotated copies.
mesh=mesh_of(layout[0])
# Preserve native float32 coordinates. Decimal rounding collapses valid
# narrow triangles at the diagonal joints and opens an otherwise closed mesh.
mesh.merge_vertices(digits_vertex=8)
mesh.update_faces(mesh.unique_faces())
mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
mesh.export(DEST)
readback=trimesh.load_mesh(DEST,process=True)
assert readback.is_watertight and readback.is_winding_consistent
assert len(solid(readback).decompose())==1
equal(solid(readback).translate(offset),joined,'export geometry changed',.04)
assert (solid(readback).translate(offset)-envelope).volume()<.01,'STL protrudes outside old contour'
exported_dpad=solid(readback).translate(offset)
# Verify the read-back mesh via all Z intervals in 2D, not by repeated 3D
# Boolean clipping at its nearly coplanar cross boundaries. Float32 STL
# boundary faces can otherwise give spurious 3D symmetric-difference volume.
exported_section_residuals=[]
for z0,z1 in zip(dpad_z_breaks,dpad_z_breaks[1:]):
    profile=exported_dpad.slice((z0+z1)/2) ^ cross_profile
    for angle in (90,180,270):
        rotated=profile.translate([-dx,-dy]).rotate(angle).translate([dx,dy])
        residual=(profile-rotated).area()+(rotated-profile).area()
        exported_section_residuals.append(float(residual))
        assert residual<.002,('exported D-pad section lost symmetry',z0,z1,residual)
exported_windows=(cross_profile-dpad_footprint(exported_dpad)).decompose()
assert len(exported_windows)==4
exported_window_areas=[float(q.area()) for q in exported_windows]
assert max(exported_window_areas)-min(exported_window_areas)<.005
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='ONE BROAD CONNECTED PLATE / CAD CHECKED / PHYSICAL TEST REQUIRED',
            file=DEST.name,bodies=1,watertight=True,
            dimensions_mm=readback.extents.round(3).tolist(),
            volume_cm3=round(readback.volume/1000,3),
            added_static_volume_cm3=round(added.volume()/1000,3),
            removed_loose_sheet_island_volume_mm3=round(removed_island_volume,3),
            sha256=hashlib.sha256(DEST.read_bytes()).hexdigest(),
            outline='STRICT old R2 70 x 50 mm main rectangle and lateral ears; no other protrusions',
            outside_old_outline_volume_mm3=round((joined-envelope).volume(),7),
            dpad_central_pivot_unchanged=True,
            dpad_four_windows_quarter_turn_symmetric=True,
            dpad_through_window_areas_mm2=[round(q,4) for q in window_areas],
            exported_dpad_through_window_areas_mm2=[round(q,4) for q in exported_window_areas],
            exported_max_rotated_section_area_residual_mm2=round(max(exported_section_residuals),7),
            dpad_material_removed_to_enlarge_windows_mm3=round(dpad_removed,4),
            dpad_symmetry_method='union of prior voids under rotations 0/90/180/270 degrees; smaller openings enlarged, not larger openings filled',
            dpad_extra_through_slit_closed_at_rear=True,
            unnecessary_mount_annular_slits_removed=True,
            working_leaf_geometry_unchanged=['B','START','SELECT'],
            A_leaf_change=dict(roots_xy_mm=a_roots,shape='straight',
                               developed_length_mm=target_length,thickness_mm=.8,
                               reason='old straight spring roots protruded above the rectangle'),
            leaf_thickness_mm=.8,
            platform_thickness_mm=1.2,additional_slot_clearance_mm=.6,
            fixed_sheet_thickness_mm=3,preload_mm=preload,cap_stop_travel_mm=stroke,
            six_mounts_xy_mm=mounts,screw='six original M2 x 6; same 3 mm grip',
            caps_reprint_required=False,front_changed=False,
            dpad_preload_insert_included=False,
            print_orientation='front down; already oriented; Raft 0',
            support_note='Local manual supports under D-pad central X/fulcrum only; no support under four thin spring mechanisms.',
            checks=['single watertight connected STL, readback geometry verified',
                    'strict old rectangular/ear envelope checked before and after STL export',
                    'B/Start/Select working springs unchanged; A rerouted inside rectangle',
                    'four equal through-window areas and quarter-turn symmetry before and after STL export',
                    'D-pad windows only enlarged; central fulcrum unchanged',
                    'all 6 screw seats identical and screw heads clear',
                    'all 6 surrounding mounting annuli filled except actual spring slots',
                    'D-pad artificial through-slit closed at rear; rocked flange clearance verified',
                    '15 sampled press positions per cap; working spring clearance and hard stops',
                    'nominal D-pad cardinal and diagonal rocking',
                    'current front, prior front, LCD clips, PCB, tacts and speaker clearance',
                    'pre-existing STL hashes unchanged'],
            limitations=['Straight A leaves have an 8.3 mm span instead of 10.3 mm; they may feel firmer at the same 0.8 mm thickness.',
                         'Physical fit and return require a printed test with PCB fixed at nominal height.'])
(ROOT/'checks-symmetric-dpad.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
