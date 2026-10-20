#!/usr/bin/env python3
"""Three independent experimental retainers with four compliant platforms.

Existing front panel, six M2x6 seats, D-pad and tactile-board datum are reused.
New cap internal flanges preload individual leaf springs; external faces and
actuator-tip heights stay unchanged. Geometry/kinematics are NOT physical FEA.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parents[1]
source=CASE/'rev2/build_rev2.py'
s={'__file__':str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0],str(source),'exec'),s)
box,cyl,cross,rounded,pill,union,mesh_of,solid=(s[k] for k in
    ('box','cyl','cross','rounded','pill','union','mesh_of','solid'))
R=s['R'];centers=s['centers'];dx,dy=s['dx'],s['dy'];front=s['front']
old_caps=s['caps'];dpad=s['dpad'];seat=4.85;back=7.85
ring_t=1.2;leaf_t=.8;leaf_width=1.4;preload=.15;stroke=.65
cap_flange_top=seat+preload
ceiling=seat+ring_t+preload+stroke
assert abs(ceiling-6.85)<1e-7
protected={p:hashlib.sha256(p.read_bytes()).hexdigest()
           for f in ('rev2','rev3-split') for p in (CASE/f).rglob('*.stl')}

def clear(a,b,label,tol=.004):
    overlap=a ^ b;v=overlap.volume()
    assert v<tol,(label,v,[(round(p.volume(),4),mesh_of(p).bounds.round(3).tolist()) for p in overlap.decompose()])
def equal(a,b,label,tol=.004):
    v=(a-b).volume()+(b-a).volume()
    assert v<tol,(label,v)
def rail(a,b,width=2.4,height=3):
    return (cyl(*a,seat,width,height)+cyl(*b,seat,width,height)).hull()
def mount(x,y):
    return cyl(x,y,seat,7,3)-cyl(x,y,seat-.1,2.3,3.2)

# Every old mounting point belongs to exactly ONE group: no shared screws,
# stacked ears, extra front-panel holes or guessed PCB fasteners.
mounts={'DPAD':[(10.5,96.5),(55,77)],
        'AB':[(92.5,84),(55,105)],
        'SS':[(10.5,113),(92.5,113)]}
assert sorted(sum(mounts.values(),[]))==sorted(map(tuple,R['retainer_mounts']))

fixed={}
# Keep the existing D-pad fulcrum, diagonal webs and local carrier. Only the
# outer blank sheet is trimmed to give the neighbouring SS group real clearance.
fixed['DPAD']=s['retainer'] ^ box(18,73.5,seat,28,27,back-seat)
fixed['DPAD']+=rail((10.5,96.5),(20,96.5),3)
fixed['DPAD']+=rail((44,77),(55,77),3)

fixed['AB']=union([
    box(72.9,70.8,seat,14.2,1.6,3),
    box(85.5,71.5,seat,1.6,7.5,3),
    rail((86.3,78.5),(89.7,81.5),1.6),
    box(88.5,80.5,seat,2.4,28.5,3),
    box(62.3,91.5,seat,1.8,17.5,3),
    box(63,107.4,seat,27,1.6,3),
    rail((55,105),(64,108),2.4),
    rail((90,84),(92.5,84),3),
    rail((85.2,85.3),(90,85.3),2.4),
])
fixed['SS']=union([
    box(38,101.0,seat,2,22.2,3),
    box(39,101.0,seat,12.5,1.4,3),
    rail((10.5,113),(39,113),2.4),
    box(79,111,seat,2,12.2,3),
    box(79,110.2,seat,13.5,2,3),
    box(39,122,seat,41.8,1.2,3),
    rail((91.5,112),(92.5,113),3),
])

spec={
 'A':dict(group='AB',shape='round',outer=[10.8,10.8],
          roots=[(74.0,72.4),(82.8,72.4)],tips=[(74.0,82.7),(82.8,82.7)],
          stop_dir=(1,0),stop_edge=5.4),
 'B':dict(group='AB',shape='round',outer=[10.8,10.8],
          roots=[(66.1,107.4),(74.9,107.4)],tips=[(66.1,95.7),(74.9,95.7)],
          stop_dir=(-1,0),stop_edge=5.4),
 'SELECT':dict(group='SS',shape='rect',outer=[10,9.2],
          roots=[(43.5,102.4),(50.5,102.4)],tips=[(43.5,112.5),(50.5,112.5)],
          stop_dir=(0,1),stop_edge=4.6),
 'START':dict(group='SS',shape='rect',outer=[10,9.2],
          roots=[(79,113.2),(79,120.8)],tips=[(61.7,113.2),(61.7,120.8)],
          stop_dir=(0,1),stop_edge=4.6),
}

def stop(name):
    x,y=centers[name];p=spec[name];e=p['stop_edge'];a,b=p['stop_dir']
    # A 45-degree rising root and a short 0.8 mm horizontal stop lip.
    # The lip contacts the BACK of the moving platform, not the cap shaft.
    contour=[[e+1,seat],[e+1.8,seat],[e+1.8,back],
             [e-.8,back],[e-.8,ceiling],[e,ceiling],[e+1,ceiling-1]]
    shape=m.CrossSection([contour]).extrude(2.0)
    nx,ny=b,-a
    return shape.transform([[a,0,nx,x-nx],[b,0,ny,y-ny],[0,1,0,0]])

def ring(name,delta):
    x,y=centers[name];p=spec[name]
    if p['shape']=='round':
        part=cyl(x,y,seat+delta,p['outer'][0],ring_t)
    else:
        part=rounded(x,y,seat+delta,*p['outer'],.8,ring_t)
    return part-rounded(x,y,seat+delta-.1,7.2,7.2,1,ring_t+.2)

def beam(root,tip,delta,trim_root=False):
    """Prescribed fixed-guided cubic bending shape, not a solved FEA state."""
    root,tip=np.array(root,dtype=float),np.array(tip,dtype=float)
    v=tip-root;L=np.linalg.norm(v);direction=v/L;normal=np.array([-direction[1],direction[0]])
    # 0.45 mm overlap into fixed header; broad, tapered root reduces a sharp
    # width step. Trimmed diagnostic mesh excludes this intentional joint.
    coords=np.linspace(1.35 if trim_root else -.45,L,45)
    vertices=[]
    for t in coords:
        u=np.clip(t/L,0,1);f=3*u*u-2*u*u*u
        z=seat+delta*f
        w=leaf_width*(2-min(max(t,0)/2,1))
        xy=root+direction*t
        for side,dz in [(-1,0),(1,0),(-1,leaf_t),(1,leaf_t)]:
            q=xy+normal*side*w/2
            vertices.append([q[0],q[1],z+dz])
    faces=[]
    # Rectangle order at each section is 0,1,3,2 when seen along its axis.
    for k in range(len(coords)-1):
        off=k*4;nxt=off+4
        for a,b in ((0,1),(1,3),(3,2),(2,0)):
            faces.extend([[off+a,nxt+a,nxt+b],[off+a,nxt+b,off+b]])
    faces.extend([[0,1,3],[0,3,2]])
    off=(len(coords)-1)*4
    faces.extend([[off,off+3,off+1],[off,off+2,off+3]])
    mesh=trimesh.Trimesh(vertices=vertices,faces=faces,process=True)
    if mesh.volume<0:mesh.invert()
    assert mesh.is_watertight and mesh.is_winding_consistent
    return solid(mesh)

def moving(name,delta,trim_roots=False):
    p=spec[name]
    return ring(name,delta)+union([beam(r,t,delta,trim_roots) for r,t in zip(p['roots'],p['tips'])])

for name in spec:fixed[spec[name]['group']]+=stop(name)
for group,points in mounts.items():
    for x,y in points:fixed[group]+=mount(x,y)
    for x,y in points:fixed[group]-=cyl(x,y,seat-.1,2.3,3.2)

caps={}
for name in spec:
    x,y=centers[name];w,h=(8,8) if name in ('A','B') else (7,3.5)
    cap=pill(x,y,-2.2,w,h,cap_flange_top+2.2)
    if name in ('A','B'):
        cap+=cyl(x,y,3,10.4,cap_flange_top-3)
    else:
        cap+=rounded(x,y,3,9.4,8.6,.8,cap_flange_top-3)
    cap+=cyl(x,y,4,3,1.75)
    caps[name]=cap
    # The user's already free-moving external guide and face remain exact.
    external=box(x-7,y-7,-2.21,14,14,5.209)
    equal(cap ^ external,old_caps[name] ^ external,'external cap shape changed '+name)

plates=dict(fixed)
for name,p in spec.items():plates[p['group']]+=moving(name,0)
for group,part in plates.items():
    assert part.status()==m.Error.NoError and len(part.decompose())==1,(group,len(part.decompose()))
    clear(part,front,'plate / existing panel '+group)
    clear(part,s['ns']['stack'],'plate / PCB '+group)
    clear(part,s['speaker_cap'],'plate / speaker retainer '+group)
    for clip in s['lcd_clips']:clear(part,clip,'plate / LCD clip '+group)
    for other in plates:
        if other<group:clear(part,plates[other],'separate plates '+group+'/'+other)
    for x,y in mounts[group]:
        clear(cyl(x,y,back,4.5,1.6),s['ns']['stack'],'screw head / board')
        equal(part ^ cyl(x,y,seat,6.99,3),s['retainer'] ^ cyl(x,y,seat,6.99,3),f'old M2 grip changed {group} {x,y}')

# Also verify the actually published R3 front, not only its R2 source ancestor.
published_front=solid(trimesh.load_mesh(CASE/'rev3-split/output/01-front-R3.stl',process=True))
for group,part in plates.items():clear(part,published_front,'plate / published R3 '+group)
for group,points in mounts.items():
    for x,y in points:
        head=cyl(x,y,back,4.5,1.6)
        for other,part in plates.items():
            if other!=group:clear(head,part,'screw head / adjacent plate '+group+'/'+other)

fixed_union=union(list(fixed.values()))
tacts=[(name,box(x-3,y-3,6.05,6,6,6)) for name,(x,y) in centers.items()]
for name,tact in tacts:
    clear(tact,fixed_union,'tact / fixed carriers '+name)
    if name in caps:clear(tact,caps[name],'unpressed cap / nominal tactile '+name)
assert abs(6.05-5.75-.30)<1e-7
for name in spec:
    # Rest is slightly preloaded: cap flange 5.00, leaf underside 4.85.
    for q in np.linspace(0,stroke-.001,15):
        delta=preload+float(q)
        cap=caps[name].translate([0,0,float(q)])
        spring=moving(name,delta)
        clear(cap,front,'cap / panel '+name)
        clear(cap,fixed_union,'cap / fixed carriers '+name)
        clear(cap,spring,'cap / deflected leaf '+name)
        clear(ring(name,delta),fixed_union,'moving platform / stop '+name)
        # Roots merge with their own fixed carrier; exclude the bonded end
        # before testing undesired collisions of deformed beam spans.
        clear(moving(name,delta,True),fixed_union,'moving span / fixed carriers '+name)
        for tn,tact in tacts:clear(spring,tact,'deflected leaf / tactile '+name+'/'+tn)
        for other in spec:
            if other!=name:
                clear(spring,moving(other,preload),'independent springs '+name+'/'+other)
                clear(cap,caps[other],'independent caps '+name+'/'+other)
    assert (ring(name,preload+stroke+.025) ^ fixed_union).volume()>.001,'stop missing '+name
    assert (caps[name].translate([0,0,-.05]) ^ front).volume()>.001,'cap outward retention '+name
    assert 2.2-stroke>1.5,'cap can disappear below front face'
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    moved=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    for name,part in plates.items():clear(moved,part,'D-pad rocking / '+name)

def export(part,filename,count=1,flip=False):
    mesh=mesh_of(part.simplify(.0003))
    if flip:mesh.vertices[:,1]*=-1;mesh.vertices[:,2]*=-1
    mesh.apply_translation(-mesh.bounds[0]);mesh.vertices=np.round(mesh.vertices,4)
    mesh.merge_vertices();mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
    dest=ROOT/filename;mesh.export(dest)
    check=trimesh.load_mesh(dest,process=True)
    assert check.is_watertight and check.is_winding_consistent and len(solid(check).decompose())==count
    return dict(file=filename,bodies=count,dimensions_mm=check.extents.round(3).tolist(),
                volume_cm3=round(check.volume/1000,3),sha256=hashlib.sha256(dest.read_bytes()).hexdigest())

files=[]
files.append(export(plates['DPAD'],'01-DPAD-retainer-SPRING-TEST.stl',flip=True))
files.append(export(plates['AB'],'02-AB-retainer-SPRING-TEST.stl'))
files.append(export(plates['SS'],'03-START-SELECT-retainer-SPRING-TEST.stl'))
cap_layout=[]
for i,name in enumerate(spec):
    part=caps[name];lo=mesh_of(part).bounds[0]
    cap_layout.append(part.translate(-lo).translate([i*16,0,0]))
files.append(export(union(cap_layout),'04-four-matching-caps-SPRING-TEST.stl',4))

layout=[]
def place(part,x,y,flip=False):
    if flip:part=part.rotate([180,0,0])
    lo=mesh_of(part).bounds[0];p=part.translate(-lo).translate([x,y,0])
    for other in layout:
        a,b=mesh_of(p).bounds,mesh_of(other).bounds
        gap=np.maximum(a[0,:2]-b[1,:2],b[0,:2]-a[1,:2])
        assert max(gap)>=4.9,('print spacing',gap)
    layout.append(p)
place(plates['DPAD'],0,0,flip=True)
place(plates['AB'],57,0)
place(plates['SS'],0,50)
for i,name in enumerate(spec):place(caps[name],110+i*16,36)
full=union(layout)
assert np.all(mesh_of(full).extents[:2]<210)
files.append(export(full,'00-THREE-RETAINERS-AND-CAPS-ONE-PLATE.stl',7))

# A sampling check of the flat-down D-pad carrier: no floating layer grows
# beyond the preceding footprint. AB/SS have only the intentional short lips.
dp=plates['DPAD'].rotate([180,0,0]);dp=dp.translate(-mesh_of(dp).bounds[0])
for z in np.linspace(.051,2.95,60):
    assert (dp.slice(float(z))-dp.slice(float(z-.05))).area()<.01,'D-pad carrier floating section'

# Reference calculations for straight fixed-guided beams; no claim of fatigue
# life or calibrated finger force. PETG flexural E=1.7 GPa is a comparison
# value from Prusament's printed-specimen datasheet, NOT the user's measured E.
reference={}
for name,p in spec.items():
    lengths=[float(np.linalg.norm(np.array(t)-r)) for r,t in zip(p['roots'],p['tips'])]
    k=sum(1700*leaf_width*leaf_t**3/L**3 for L in lengths)
    eps=max(3*leaf_t*(preload+stroke)/L**2 for L in lengths)
    reference[name]=dict(reference_lengths_mm=lengths,reference_N_per_mm=k,
                         reference_preload_N=k*preload,reference_full_stop_force_N=k*(preload+stroke),
                         reference_max_surface_strain=eps,
                         note='Uniform fixed-guided beam reference only; real roots, ring rotation, stop contact and print anisotropy are not solved.')
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report=dict(status='EXPERIMENTAL / PHYSICAL RETURN AND FORCE NOT VERIFIED',
            old_production_STL_unchanged=True,front_panel_unchanged=True,
            three_groups={k:list(v) for k,v in mounts.items()},new_caps_required=True,
            outside_cap_geometry_unchanged=True,cap_tip_z_mm=5.75,
            spring_ring_thickness_mm=ring_t,leaf_thickness_mm=leaf_t,
            cap_preload_mm=preload,design_stop_stroke_mm=stroke,
            min_nominal_cap_protrusion_mm=2.2-stroke,
            mechanical_stop_contacts='rear of each moving ring, not electronics',
            simulation='prescribed cubic fixed-guided beam kinematics; not FEA, not force calibration',
            material_reference='https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf',
            beam_reference_calculations=reference,parts=files,
            existing_dpad_reused=True,packed_body_count=7,
            print_note='DPAD flat back down, AB/SS flat front down; already oriented. Inspect short 0.8 mm stop-lip overhangs; caps need local support under flange.',
            geometry_checks=['three single-body retainers; watertight STL readback',
                             'published R3 front, PCB, LCD clips, speaker retainer clearance',
                             'six original screw seats and adjacent screw-head clearance',
                             '15 sampled press positions per button; modelled independent leaf bending',
                             'hard stops engage after nominal travel; external cap profile and tip height unchanged',
                             'D-pad cardinal and diagonal rocking',
                             'flat-down D-pad carrier sampled sections',
                             'packed XY spacing at least 4.9 mm and bed footprint below 210 x 210 mm',
                             'production STL hashes unchanged'],
            limitations=['No measured physical spring force or printed return test.',
                         'PETG creep, friction, fatigue, tolerances and actual tactile stroke not validated.',
                         'The light bench does not constrain the electronic PCB height.'])
(ROOT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
