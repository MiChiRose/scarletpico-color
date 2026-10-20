#!/usr/bin/env python3
"""R3: three support-friendly rear sections, plus smaller fastener passages.

Preserves R2 as a complete rollback set. All calculations use assembly XYZ,
front view: X right, Y down the case, Z from the front towards the rear.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import shutil
import zipfile
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
CASE=ROOT.parent
R2=CASE/'rev2'
OUT=ROOT/'output'
Q=json.loads((ROOT/'parameters.json').read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected=[p for folder in (R2,CASE/'variable-depth',CASE/'usb-c-top',CASE/'reference',CASE/'output')
           for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
before={p:digest(p) for p in protected}
source=R2/'build_rev2.py'
s={'__file__':str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0],str(source),'exec'),s)
box,cyl,pill,union,solid,mesh_of=(s[k] for k in ('box','cyl','pill','union','solid','mesh_of'))
def load(path,rear=False):
    mesh=trimesh.load_mesh(path,process=True)
    if rear:
        mesh.vertices[:,1]=150-mesh.vertices[:,1]
        mesh.vertices[:,2]=30-mesh.vertices[:,2]
    return solid(mesh)
front_parent=load(R2/'output/01-front-R2.stl')
rear_parent=load(R2/'output/02-rear-R2.stl',True)
front,rear=front_parent,rear_parent
legacy_seam_overlap=front_parent ^ rear_parent
assert legacy_seam_overlap.volume()<.05,'parent seam changed beyond sub-micron STL weld allowance'
def clear(a,b,label,tol=.008):
    volume=(a ^ b).volume()
    assert volume<tol,(label,volume)
def same(a,b,label,tol=.008):
    volume=(a-b).volume()+(b-a).volume()
    assert volume<tol,(label,volume)
def axial(point,direction,start,length,diameter):
    direction=np.array(direction,dtype=float);direction/=np.linalg.norm(direction)
    p=np.array(point)+direction*start
    # Our axes all lie in YZ; rotating a Z-cylinder around X is sufficient.
    angle=math.degrees(math.atan2(-direction[1],direction[2]))
    return m.Manifold.cylinder(length,diameter/2,circular_segments=64).rotate([angle,0,0]).translate(p)
def along_y(x,y,z,d,length):return axial([x,y,z],[0,1,0],0,length,d)
def slot_y(x0,x1,y,z,d,length):
    return (along_y(x0,y,z,d,length)+along_y(x1,y,z,d,length)).hull()

# Narrow ONLY the fastener holes; never fill the connector/actuator windows.
up=json.loads((CASE/'usb-c-top/parameters.json').read_text())
cx,cz=up['port_center_xz'];a,b=np.array(up['mount_hole_pitch_range'])/2
hole_d=Q['connector_mount_passage_diameter']
usb_rings=[];usb_passages=[]
for lo,hi in ((cx-b,cx-a),(cx+a,cx+b)):
    small=slot_y(lo,hi,1,cz,hole_d,1.997)
    # Overlap the old rounded STL bore, rather than joining a mathematically
    # tangent annulus to its float32 approximation (which creates slivers).
    patch=box(lo-1.25,1,cz-1.25,hi-lo+2.5,1.997,2.5)
    usb_rings.append(patch)
    usb_passages.append(slot_y(lo,hi,-.1,cz,hole_d,3.3))
front+=union(usb_rings)
for passage in usb_passages:front-=passage
pw=s['P']['power_switch'];pwy,pwz=pw['center_yz']
switch_rings=[];switch_passages=[]
for y in (pwy-pw['mount_pitch']/2,pwy+pw['mount_pitch']/2):
    def bore(d):
        return cyl(0,0,0,d,3.2).rotate([0,90,0]).translate([99.8,y,pwz])
    switch_rings.append(bore(2.5))
    switch_passages.append(bore(hole_d))
front+=union(switch_rings)
for passage in switch_passages:front-=passage
for passage in usb_passages+switch_passages:clear(front,passage,'smaller fastener passage')

# Give the new mechanical revision its own correctly oriented internal mark.
bb=mesh_of(s['engraving']).bounds
front+=box(bb[0,0]-.02,bb[0,1]-.02,2.74,bb[1,0]-bb[0,0]+.04,bb[1,1]-bb[0,1]+.04,.258)
mark=s['engraved_text']('SCARLETPICO  R3',23,126,2.75,size=.095,depth=.3)
mb=mesh_of(mark).bounds
mark=mark.mirror([1,0,0]).translate([mb[0,0]+mb[1,0],0,0])
front-=mark

# New closure supports start ABOVE the measured LCD envelope. Their tapered
# roots grow from the sidewalls, not through the display PCB or the battery.
pd=Q['pilot_diameter'];diam=Q['boss_diameter'];root_z=Q['boss_root_z']
new_fasteners=[]
for x,y in Q['upper_extra_mounts_xy']:
    foot_x=1.5 if x<50 else 101.5
    foot=cyl(foot_x,y,root_z,2.6,.3)
    post=cyl(x,y,16,diam,4)
    support=(foot+post).hull()
    front+=support
    front-=cyl(x,y,20-Q['new_pilot_depth'],pd,Q['new_pilot_depth']+.1)
    rear-=cyl(x,y,19.9,Q['rear_clearance_diameter'],2.2)
    new_fasteners.append(dict(section='upper',point=[x,y,22],normal=[0,0,1],
                              head_seat=[x,y,22],engagement_mm=4,pilot_depth_mm=5))

def depth(y):return float(s['scope']['depth_at'](y))
def slope(y):
    t=np.clip((y-55.5)/15,0,1)
    return float(8/15*(6*t-6*t*t))
inner_below=s['scope']['inner_below']
for x,y in Q['transition_mounts_xy']:
    p=np.array([x,y,depth(y)])
    n=np.array([0,-slope(y),1]);n/=np.linalg.norm(n)
    foot_x=1.5 if x<50 else 101.5
    foot=cyl(foot_x,y+3,root_z,2.6,.3)
    barrel=axial(p,n,-8.5,9,diam)
    support=(foot+barrel).hull() ^ inner_below.translate([0,0,-.02])
    front+=support
    front-=axial(p,n,-7,5.2,pd)
    # A shallow normal-axis spot gives the pan head a flat bearing face,
    # rather than forcing the screw to bear on the sloping curved surface.
    spot=Q['transition_head_spot_depth']
    rear-=axial(p,n,-spot,3,Q['transition_head_spot_diameter'])
    rear-=axial(p,n,-4,5,Q['rear_clearance_diameter'])
    new_fasteners.append(dict(section='transition',point=p.tolist(),normal=n.tolist(),
                              head_seat=(p-n*spot).tolist(),engagement_mm=4.13,
                              pilot_depth_mm=5,head_spot_depth_mm=spot))

# Three independently fastened sections. No cantilever lap tabs are added:
# those would introduce new unsupported surfaces on otherwise bed-flat parts.
y0,y1=Q['rear_split_y'];gap=Q['seam_gap']
upper=rear ^ box(-1,-1,-1,105,y0-gap/2+1,40)
transition=rear ^ box(-1,y0+gap/2,-1,105,y1-y0-gap,40)
lower=rear ^ box(-1,y1+gap/2,-1,105,151-y1-gap/2,40)
pieces=[('upper',upper),('transition',transition),('lower',lower)]
assembled=union([v for _,v in pieces])
gaps=box(-1,y0-gap/2,-1,105,gap,40)+box(-1,y1-gap/2,-1,105,gap,40)
same(assembled,rear-gaps,'split changed material outside the two seams')
for i,(name,part) in enumerate(pieces):
    assert len(part.decompose())==1,(name,'disconnected section')
    for other,q in pieces[:i]:clear(part,q,'rear sections overlap '+name+'/'+other)
    clear(front-legacy_seam_overlap,part,'new front/'+name)
assert np.allclose(mesh_of(front).bounds,mesh_of(front_parent).bounds,atol=.001)
assert np.allclose(mesh_of(assembled).bounds,mesh_of(rear_parent).bounds,atol=.001)

# Reuse all electronics exclusions and mechanical datums. The broad LCD box
# begins behind its existing front recess, not at the outer face of the case.
v=s['scope'];ns=s['ns']
components=[('LCD',box(4,11,2.002,95,59,7.998)),('battery + front allowance',v['battery']+v['battery_space']),
            ('TP4056 bay',s['charger_bay']),('diode',s['diode']),('switch + leads',v['switch']),
            ('PCB stack',ns['stack']),('speaker',ns['speaker_proxy'])]
mechanisms=[('button retainer',s['retainer']),('dpad',s['dpad']),('speaker retainer',s['speaker_cap']),
            *s['caps'].items(),*[(f'LCD clip {i+1}',q) for i,q in enumerate(s['lcd_clips'])]]
for name,a in [('front',front),*pieces]:
    for other,b in components+mechanisms:clear(a,b,name+'/'+other)
for name,part in mechanisms:clear(front,part,'mechanism/front '+name)
# Prove the successful battery seat and its surrounding floor were not split.
battery_region=box(12,15,13,58,39.8,10)
same(upper ^ battery_region,rear_parent ^ battery_region,'battery seat changed')
same(front ^ box(7,73,0,89,51,9),front_parent ^ box(7,73,0,89,51,9),'button area changed')
for aperture in [s['ns']['switch_slot'],s['ns']['actuator_envelope']]:
    clear(front,aperture,'switch actuator opening changed')
clear(front,box(46.3,-.1,12.8,10.4,3.2,4.4),'USB body opening changed')
for passage in usb_passages+switch_passages:clear(front,passage,'connector fastener passage')

# Newly placed screw heads/shanks do not hit the electronics. Pilot holes
# remain blind and the full 6 mm shank fits before reaching the hole bottom.
for f in new_fasteners:
    p=np.array(f['point']);n=np.array(f['normal']);seat=np.array(f['head_seat'])
    head=axial(seat,n,0,1.6,4.5)
    shaft=axial(seat,n,-6,6,2.0)
    for name,other in components+mechanisms:
        clear(head+shaft,other,'new fastener/'+name)
    clear(head,front,'screw head/front')
    clear(shaft,assembled,'screw shank/rear clearance')
    if f['section']=='upper':
        clear(cyl(p[0],p[1],15.01,pd-.04,5),front,'upper pilot')
    else:clear(axial(p,n,-6.99,5,pd-.04),front,'transition pilot')
    assert Q['new_pilot_depth']-f['engagement_mm']>.4

for step in np.linspace(0,30,61):
    for name,part in pieces:
        moved=part.translate([0,0,float(step)])
        for other,q in [('front',front),*components,*mechanisms]:
            # Rear-mounted electronics travel with their own rear section;
            # they are not stationary obstacles during closure.
            if other in ('battery + front allowance','TP4056 bay','diode'):continue
            obstacle=q-legacy_seam_overlap if other=='front' and step==0 else q
            clear(moved,obstacle,'closing '+name+'/'+other)

# Manufacturing orientation checks. Large flat exterior surfaces sit at Z0.
# The transition grows from Y55.1 upwards; the charger plinth is already
# present at its first layer, not introduced as a new overhanging shelf later.
def print_mesh(part,orientation):
    mesh=mesh_of(part.simplify(.0003))
    if orientation=='outside-down':
        mesh.vertices[:,1]*=-1;mesh.vertices[:,2]*=-1
    elif orientation=='upper-cut-end-down':
        mesh.vertices=np.column_stack([mesh.vertices[:,0],-mesh.vertices[:,2],mesh.vertices[:,1]])
    mesh.apply_translation(-mesh.bounds[0])
    mesh.vertices=np.round(mesh.vertices,4)
    mesh.merge_vertices();mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
    return mesh
manufacturing=[]
for name,part in pieces:
    orientation='upper-cut-end-down' if name=='transition' else 'outside-down'
    mesh=print_mesh(part,orientation)
    bottom_faces=mesh.triangles[np.max(mesh.triangles[:,:,2],axis=1)<.0002]
    bed_area=float(sum(np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))/2 for t in bottom_faces))
    assert bed_area>(150 if name=='transition' else 4000),(name,bed_area)
    manufacturing.append(dict(section=name,orientation=orientation,bed_contact_area_mm2=round(bed_area,2),
                              print_dimensions_mm=mesh.extents.round(3).tolist()))
max_slope=max(abs(slope(y)) for y in np.linspace(55.1,70.9,501))
assert max_slope<1

OUT.mkdir(parents=True,exist_ok=True)
files=[]
def publish(part,name,orientation='front-down',components=1):
    assert part.status()==m.Error.NoError and len(part.decompose())==components,name
    mesh=print_mesh(part,orientation)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0,name
    dest=OUT/(name+'.stl');mesh.export(dest)
    reread=trimesh.load_mesh(dest,process=True)
    assert reread.is_watertight and reread.is_winding_consistent and reread.volume>0,name
    assert reread.nondegenerate_faces().all(),name
    assert len(solid(reread).decompose())==components,name
    files.append(dict(file=dest.name,orientation=orientation,watertight=True,
                      STL_readback_validated=True,dimensions_mm=reread.extents.round(3).tolist(),sha256=digest(dest)))
publish(front,'01-front-R3')
publish(upper,'02a-rear-upper-R3','outside-down')
publish(transition,'02b-rear-transition-R3','upper-cut-end-down')
publish(lower,'02c-rear-lower-R3','outside-down')
# An optional small left-edge fixture reproduces both new screw directions
# and the upper seam. Three bodies are already bed-oriented and packed nearby.
test_region=box(-.01,46,-.1,10.01,24,40)
test_parts=[(front ^ test_region,'front-down'),(upper ^ test_region,'outside-down'),
            (transition ^ test_region,'upper-cut-end-down')]
test_bodies=[];offset=0
for part,orientation in test_parts:
    mesh=print_mesh(part,orientation)
    test_bodies.append(solid(mesh).translate([offset,0,0]));offset+=mesh.extents[0]+3
publish(union(test_bodies),'10-seam-fastener-FIT-TEST-OPTIONAL',components=3)
for path in sorted((R2/'output').glob('*.stl')):
    if path.name.startswith(('01-','02-')):continue
    shutil.copyfile(path,OUT/path.name)
    assert digest(OUT/path.name)==digest(path)
report=dict(revision=Q['revision'],physical_fit_verified=False,assembled_case_mm=[103,150,30],
            rear_sections=3,seam_gap_mm=gap,closure_screws_total=10,
            closure_per_section=dict(upper=4,transition=2,lower=4),new_fasteners=new_fasteners,
            new_fastener_type='M2 x 6 pan-head self tapping for plastic',
            connector_fastener_passages_mm=hole_d,connector_windows_unchanged=True,
            battery_seat_preserved=True,TP4056_bay_crosses_upper_joint=True,
            curved_band_max_surface_shift_per_print_height=round(max_slope,4),
            curved_band_max_overhang_from_vertical_deg=round(math.degrees(math.atan(max_slope)),2),
            manufacturing=manufacturing,parts=files,
            test_coupon='10-seam-fastener-FIT-TEST-OPTIONAL.stl',
            old_R2_files_unchanged=all(digest(p)==v for p,v in before.items()))
report['parent_STL_weld_seam_overlap_mm3']=round(legacy_seam_overlap.volume(),6)
report['no_new_seam_interference']=True
assert report['old_R2_files_unchanged']
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')

# Reuse only the deterministic CAD rasterizer, not the R2 preview script body.
tree=ast.parse((R2/'decor-preview/render_decor.py').read_text())
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('camera','render')]
render_ns={'np':np,'mesh_of':mesh_of,'Image':Image}
exec(compile(ast.Module(body=functions,type_ignores=[]),'<CAD rasterizer>','exec'),render_ns)
render=render_ns['render']
font_path='/System/Library/Fonts/Supplemental/Arial.ttf'
font=ImageFont.truetype(font_path,29);small=ImageFont.truetype(font_path,22)
cream=(218,205,178);blue=(73,132,166);warm=(173,143,105);dark=(45,50,56)

def preview():
    im=Image.new('RGB',(1900,1250),'#eef0f3');draw=ImageDraw.Draw(im)
    draw.text((35,20),'ScarletPico R3 / задняя крышка из трёх секций',font=font,fill='#192938')
    draw.text((35,65),'Габариты 103 × 150 × 30 мм сохранены. Каждая секция крепится прямо к передней части.',font=small,fill='#526171')
    render(im,[(front,cream),(upper,blue),(transition,warm),(lower,cream)],(350,430),3.6,[51.5,75,15],
           [.4,-.3,1],(20,110,640,810))
    draw=ImageDraw.Draw(im);draw.text((40,830),'В сборе / 4 + 2 + 4 самореза M2×6',font=small,fill='#192938')
    exploded=[(upper.translate([0,-5,4]),blue),(transition.translate([0,0,10]),warm),(lower.translate([0,5,4]),cream)]
    render(im,exploded,(1030,430),3.6,[51.5,75,15],[.3,-.5,1],(670,110,1350,810))
    draw=ImageDraw.Draw(im);draw.text((710,830),'Разнесённый вид / два стыка по 0,2 мм',font=small,fill='#192938')
    # Actual STL bed orientations, translated to one shared print-bed scene.
    bed_items=[]
    offset=0
    for (name,part),color in zip(pieces,(blue,warm,cream)):
        mesh=print_mesh(part,'upper-cut-end-down' if name=='transition' else 'outside-down')
        geom=solid(mesh).translate([0,offset,0])
        bed_items.append((geom,color));offset+=mesh.extents[1]+12
    render(im,bed_items,(1595,430),3,[51.5,offset/2,0],[.15,-.4,1],(1370,110,1880,810))
    draw=ImageDraw.Draw(im);draw.text((1380,830),'Ориентация на столе',font=small,fill='#192938')
    draw.text((40,925),'Верх и низ: наружной плоскостью на стол.',font=font,fill='#192938')
    draw.text((40,980),'Переход: поперечным торцом на стол; рекомендуется brim 5–8 мм.',font=font,fill='#192938')
    draw.text((40,1040),'Крупная наружная поверхность перехода больше не опирается на поддержки.',font=small,fill='#526171')
    draw.text((40,1090),'Два винта перехода входят перпендикулярно скосу, в подготовленные посадки.',font=small,fill='#526171')
    draw.text((40,1140),'Посадка TP4056 пересекает верхний стык; батарейная посадка остаётся целиком на верхней секции.',font=small,fill='#526171')
    draw.text((40,1190),'CAD-проверки пройдены. Физическая примерка R3 и печать без поддержек пока не проверены.',font=small,fill='#934d3c')
    im.save(OUT/'preview-R3.png')
preview()
with zipfile.ZipFile(ROOT/'ScarletPico-case-R3-split.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for path in [ROOT/'README.md',ROOT/'parameters.json',ROOT/'build_split.py',*sorted(OUT.iterdir())]:
        if path.is_file():z.write(path,path.relative_to(ROOT))
print(json.dumps(report,indent=2))
