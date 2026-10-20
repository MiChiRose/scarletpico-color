#!/usr/bin/env python3
"""Separate front-side D-pad preload spring; no shell or cap modification.

The original D-pad flange has a 1 mm clearance to the front floor. A rigid
rear carrier alone cannot remove this free float. Four compliant fingers
between floor and flange push the D-pad REARWARD against its central pivot.
This is a unilateral prescribed-contact model, NOT a solved elastic FEA.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import manifold3d as m
import trimesh

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parents[1]
FILES=['04-DPAD-preload-spring-TEST.stl','00-DPAD-holder-and-preload-spring-TEST.stl']
protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in CASE.rglob('*.stl')
           if p not in [ROOT/n for n in FILES]}
src=ROOT/'reinforce_springs.py'
s={'__file__':str(src)}
exec(compile(src.read_text().split('files=[export')[0],str(src),'exec'),s)
box,cyl,union,mesh_of,solid,clear,equal=(s[k] for k in
    ('box','cyl','union','mesh_of','solid','clear','equal'))
dx,dy=s['dx'],s['dy'];dpad=s['dpad'];front=s['front'];plates=s['plates']
floor=3.0;free_top=4.20;leaf_t=.40;shoe_t=.30;leaf_w=1.6
mounts=s['mounts']['DPAD']

# All rear faces are coplanar at Z4.20 for printing that face on the bed.
# Rings locate AROUND the two existing 7 mm posts, not on top of them: screw
# grip, frame seating plane and the six original fasteners remain unchanged.
fixed=box(dx-15.7,dy-15.7,floor,31.4,31.4,free_top-floor)
fixed-=box(dx-14.5,dy-14.5,floor-.1,29,29,free_top-floor+.2)
def link(a,b,width,z=floor,height=free_top-floor):
    return (cyl(*a,z,width,height)+cyl(*b,z,width,height)).hull()
fixed+=link((10.5,96.5),(dx-15.1,96.5),2)
fixed+=link((dx+15.1,77),(55,77),2)
for x,y in mounts:fixed+=cyl(x,y,floor,9.2,free_top-floor)
for x,y in mounts:fixed-=cyl(x,y,floor-.1,7.4,free_top-floor+.2)
fingers=[]
for sx,sy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
    corner=(dx+sx*14.7,dy+sy*14.7)
    anchor=(dx+sx*12.2,dy+sy*12.2)
    fixed+=link(corner,anchor,3)
    fingers.append(dict(root=np.array([dx+sx*11.4,dy+sy*11.4]),
                        tip=np.array([dx+sx*4.1,dy+sy*4.1]),
                        contact=np.array([dx+sx*5.2,dy+sy*5.2])))

def pose(ax=0,ay=0,pull=0):
    a,b=np.radians([ax,ay])
    rx=np.array([[1,0,0],[0,np.cos(a),-np.sin(a)],[0,np.sin(a),np.cos(a)]])
    ry=np.array([[np.cos(b),0,np.sin(b)],[0,1,0],[-np.sin(b),0,np.cos(b)]])
    rot=ry@rx;pivot=np.array([dx,dy,5.2])
    offset=pivot-rot@pivot+np.array([0,0,pull])
    mat=np.column_stack([rot,offset])
    plane_point=rot@np.array([dx,dy,4.0])+offset
    normal=rot[:,2]
    def height(xy):
        return plane_point[2]-np.dot(normal[:2],xy-plane_point[:2])/normal[2]
    grad=-normal[:2]/normal[2]
    return mat,height,grad

def finger(part,ax=0,ay=0,pull=0,natural=False,trim=False):
    root,tip,contact=(part[k] for k in ('root','tip','contact'))
    direction=(tip-root)/np.linalg.norm(tip-root)
    normal=np.array([-direction[1],direction[0]])
    L=np.linalg.norm(tip-root);Lc=np.linalg.norm(contact-root)
    _,height,grad=pose(ax,ay,pull)
    # Last 1.56 mm is a small contact shoe; the active span begins beyond
    # the bonded root. Unloaded fingers cannot pull a raised flange down.
    coords=np.unique(np.r_[np.linspace(1.35 if trim else -.6,L,55),Lc,L])
    vertices=[]
    for t in coords:
        u=np.clip((t-.6)/(Lc-.6),0,1)
        h=3*u*u-2*u*u*u;j=u*u*u-u*u
        width=leaf_w*(1.5-.5*np.clip(t/1.8,0,1))
        # The low-moment contact shoe is 0.3 mm; the actual bending span
        # stays 0.4 mm. This leaves extra floor clearance at diagonal tilt.
        taper=np.clip((t-(Lc-2))/1,0,1)
        thick=leaf_t-(leaf_t-shoe_t)*(3*taper*taper-2*taper*taper*taper)
        for side,dz in [(-1,-thick),(1,-thick),(-1,0),(1,0)]:
            n=normal*side*width/2;xy=root+direction*t+n
            if natural:top=free_top
            elif t>=Lc:
                top=min(free_top,height(xy))
            else:
                target=height(contact+n)
                delta=min(0,target-free_top)
                # A monotone prescribed transition avoids inventing an
                # overshoot into the front floor outside the flange edge.
                # The small contact shoe then follows the tilted plane.
                top=free_top+h*delta
                top=min(top,free_top)
            vertices.append([*xy,top+dz])
    faces=[]
    for k in range(len(coords)-1):
        off=k*4;nxt=off+4
        for a,b in [(0,1),(1,3),(3,2),(2,0)]:
            faces.extend([[off+a,nxt+a,nxt+b],[off+a,nxt+b,off+b]])
    faces.extend([[0,1,3],[0,3,2]])
    off=(len(coords)-1)*4
    faces.extend([[off,off+3,off+1],[off,off+2,off+3]])
    mesh=trimesh.Trimesh(vertices=vertices,faces=faces,process=True)
    if mesh.volume<0:mesh.invert()
    assert mesh.is_watertight and mesh.is_winding_consistent
    return solid(mesh)

natural_leaves=union([finger(p,natural=True) for p in fingers])
spring=fixed+natural_leaves
assert spring.status()==m.Error.NoError and len(spring.decompose())==1
clear(spring,front,'natural preload spring / front')
clear(spring,s['stack'],'preload spring / nominal button PCB')
for group,plate in plates.items():clear(spring,plate,'preload spring / retainer '+group)
for clip in s['clips']:clear(spring,clip,'preload spring / LCD clip')
clear(spring,s['speaker'],'preload spring / speaker retainer')
for cap in s['caps'].values():clear(spring,cap,'preload spring / other caps')
clear(fixed,dpad,'fixed carrier / neutral D-pad')
assert (natural_leaves ^ dpad).volume()>.01,'no intended D-pad preload'

samples=[]
for ax,ay in [(0,0),(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),
              (-3,-3),(-3,3),(3,-3),(3,3)]:
    mat,_,_=pose(ax,ay)
    rocked=dpad.transform(mat)
    deformed=union([finger(p,ax,ay) for p in fingers])
    clear(deformed,front,'deflected D-pad spring / front floor')
    clear(deformed,rocked,'deflected D-pad spring / moving flange',.008)
    clear(fixed,rocked,'fixed preload frame / moving D-pad')
    for group,plate in plates.items():clear(deformed,plate,'D-pad preload / rear retainer '+group)
    for p in fingers:clear(finger(p,ax,ay,trim=True),fixed,'unbonded leaf / fixed spring frame')
    samples.append(dict(angles_xy_deg=[ax,ay],minimum_leaf_z_mm=round(float(mesh_of(deformed).bounds[0,2]),4)))

# Geometry demonstrating why the old empty test floated: the D-pad could
# move forward almost 1 mm without meeting either the floor or the rear pad.
clear(dpad.translate([0,0,-.99]),front,'source free axial gap')
assert (dpad.translate([0,0,-1.01]) ^ front).volume()>.01

def print_part(part,flip=False):
    if flip:part=part.rotate([180,0,0])
    part=part.translate(-mesh_of(part).bounds[0])
    return part
printed_spring=print_part(spring,True)
# No unsupported growth: the thin leaves start ON the bed, and the thicker
# fixed frame grows towards the front floor in the following layers.
for z in np.linspace(.051,1.1,28):
    assert (printed_spring.slice(float(z))-printed_spring.slice(float(z-.05))).area()<.01
printed_holder=print_part(plates['DPAD'],True)
printed_spring=printed_spring.translate([57,0,0])
packed=printed_holder+printed_spring
assert len(packed.decompose())==2 and np.all(mesh_of(packed).extents[:2]<210)

def export(part,name,count=1):
    mesh=mesh_of(part.simplify(.0002));mesh.vertices=np.round(mesh.vertices,4)
    mesh.merge_vertices();mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent
    dest=ROOT/name;mesh.export(dest)
    check=trimesh.load_mesh(dest,process=True)
    assert check.is_watertight and check.is_winding_consistent and len(solid(check).decompose())==count
    return dict(file=name,bodies=count,dimensions_mm=check.extents.round(3).tolist(),
                volume_cm3=round(check.volume/1000,3),sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
files=[export(print_part(spring,True),FILES[0]),export(packed,FILES[1],2)]
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='EXPERIMENTAL D-PAD PRELOAD / PHYSICAL TEST REQUIRED',
            diagnosed_source_free_axial_gap_mm=1.0,
            assembly_order='front panel / thin preload spring / existing D-pad / rigid V2 retainer',
            spring_force_direction='rearward, pressing D-pad ball against fixed rear fulcrum',
            extra_screws=0,existing_screws='two original M2 x 6 for D-pad carrier; original 3 mm grip unchanged',
            front_modified=False,dpad_modified=False,other_button_caps_modified=False,
            floor_z_mm=floor,unstressed_spring_top_z_mm=free_top,
            Dpad_flange_front_z_mm=4.0,nominal_preload_mm=.20,
            leaf_thickness_mm=leaf_t,contact_shoe_thickness_mm=shoe_t,leaf_width_mm=leaf_w,
            locating_ring_inner_diameter_mm=7.4,locating_post_diameter_mm=7,
            layer_height_mm=.10,first_layer_height_mm=.10,
            print_orientation='flat highest rear face down; thin leaves start on bed, not on supports',
            geometry_samples=samples,parts=files,
            limitations=['Prescribed unilateral-contact deformation, not solved FEA or measured spring force.',
                         'Actual PCB/tactile contact still requires fixed-height assembled test.',
                         'Print tolerances, surface roughness, creep and fatigue have not been validated.',
                         'Small lateral running clearance of the unchanged front aperture remains; this targets free axial rattle, not zero XY tolerance.'])
(ROOT/'checks-DPAD-preload.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
