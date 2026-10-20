#!/usr/bin/env python3
"""Matched R2 mechanical set. Previous sources and STL files are read-only.

Uses the verified variable-depth construction and the accepted USB/lanyard
front. Replaces the flawed cap/retainer interface, not the PCB mounting datum.
All geometry is in front-view assembly coordinates, millimetres.
"""
from pathlib import Path
import hashlib
import json
import math
import shutil
import zipfile
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CASE = ROOT.parent
OUT = ROOT/'output'
R = json.loads((ROOT/'parameters.json').read_text())
protected = [p for p in CASE.rglob('*') if p.is_file() and ROOT not in p.parents
             and '__pycache__' not in p.parts]
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
before = {p:digest(p) for p in protected}

# Stop before the adapter's validation/publication section: no parent outputs
# are overwritten. Its own baseline pre-publication tests still execute.
vfile = CASE/'variable-depth/build_variable.py'
scope = {'__file__': str(vfile)}
exec(compile(vfile.read_text().split('\ndef disjoint(')[0], str(vfile), 'exec'), scope)
ns = scope['ns']
box,cyl,union,pill,cross,rounded,mesh_of,solid = (
    ns[k] for k in ('box','cylinder','union','pill','cross','rounded_rectangle','mesh_of','solid'))
P = ns['P']
front = solid(trimesh.load_mesh(CASE/'usb-c-top/output/front-top-usbc-DRAFT.stl',process=True))
parent_front = front
# Remove the old exterior accent below the display without changing the
# aperture, PCB recess or internal floor. The patch ends inside solid plastic.
accent_bounds=mesh_of(ns['screen_accent']).bounds
front += box(accent_bounds[0,0]-.01,accent_bounds[0,1]-.01,0,
             accent_bounds[1,0]-accent_bounds[0,0]+.02,
             accent_bounds[1,1]-accent_bounds[0,1]+.02,.4)
rear_mesh=trimesh.load_mesh(CASE/'variable-depth/output/rear-variable-DRAFT.stl',process=True)
rear_mesh.vertices[:,1]=150-rear_mesh.vertices[:,1]
rear_mesh.vertices[:,2]=30-rear_mesh.vertices[:,2]
rear=solid(rear_mesh)
# Remove only the old protruding charger fence, stopping at its flat Z20
# backing surface. Reusing the verified STL avoids re-tessellating the entire
# unchanged taper and rear edge rolls in a different boolean operation order.
rear -= box(73.29,35.79,18.49,24.42,19.42,1.51)
pd,cd = R['pilot_diameter'], R['clearance_diameter']

def clear(a,b,label,tol=.002):
    volume = (a ^ b).volume()
    assert volume < tol, (label,volume)
def same(a,b,label,tol=.003):
    assert (a-b).volume()+(b-a).volume()<tol, label

# Remove the old short posts and restore their old blind holes in the floor.
# No front aperture, PCB position, battery seat or exterior contour is moved.
for x,y in P['retainer_mounts']:
    front += cyl(x,y,1.2,7,1.798)
    front -= cyl(x,y,2.998,7.002,1.653)

rf,rt = R['retainer_front'],R['retainer_thickness']
ret_mounts = R['retainer_mounts']
centers = ns['centers']
dx,dy = ns['dx'],ns['dy']
for x,y in ret_mounts:
    front += cyl(x,y,2.9,7,rf-2.9)
    front -= cyl(x,y,rf-3.5,pd,3.6)

# A 3 mm ear consumes half the 6 mm screw. The remaining 3 mm has a 3.5 mm
# blind pilot and a 1.35 mm floor, so fully tightening cannot bottom the tip.
retainer = box(16.5,73,rf,70,50,rt)
retainer -= cross(dx,dy,rf-.1,27.6,10.3,rt+.2)
for name in ('A','B','SELECT','START'):
    x,y = centers[name]
    # Small stem guide/stop land at the front. Larger rear pocket clears the
    # WHOLE tactile switch, rather than asking the cap lip to span a body hole.
    retainer -= cyl(x,y,rf-.1,4.0,rt+.2)
    retainer -= box(x-3.4,y-3.4,5.9,6.8,6.8,rt+rf)
pivot = ns['retainer'] ^ box(dx-13,dy-13,6.2,26,26,2.001)
retainer += pivot
for name in ('UP','DOWN','LEFT','RIGHT'):
    x,y = centers[name]
    retainer -= box(x-3.3,y-3.3,5.95,6.6,6.6,6.3)
for x,y in ret_mounts:
    if x<16.5 or x>86.5:
        edge = 17 if x<16.5 else 86
        retainer += (cyl(x,y,rf,7,rt)+cyl(edge,y,rf,7,rt)).hull()
    retainer -= cyl(x,y,rf-.1,cd,rt+.2)

caps = {}
for name in ('A','B','SELECT','START'):
    x,y = centers[name]
    w,h = (8,8) if name in ('A','B') else (7,3.5)
    flange_top = R['cap_flange_front']+R['cap_flange_thickness']
    cap = pill(x,y,-R['cap_protrusion'],w,h,flange_top+R['cap_protrusion'])
    if name in ('A','B'):
        flange = cyl(x,y,R['cap_flange_front'],10.4,R['cap_flange_thickness'])
    else:
        # Broad rectangular lip cannot slip/tilt into the old 7.2 mm square.
        flange = rounded(x,y,R['cap_flange_front'],9.4,8.6,.8,R['cap_flange_thickness'])
    cap += flange
    cap += cyl(x,y,4.0,3,R['cap_stem_tip']-4.0)
    caps[name] = cap
dpad = ns['dpad'] + cross(dx,dy,-R['dpad_protrusion'],23.8,6.5,R['dpad_protrusion']-1.19)

# Two new through-lid fasteners at the actual midpoints of both sidewalls.
# Retainer ears clear both the closure posts and the moving D-pad flange.
closure = [*ns['lid_mounts'],*R['middle_case_mounts']]
for x,y in R['middle_case_mounts']:
    front += cyl(x,y,2.9,6.5,25.1)
    front -= cyl(x,y,22,pd,6.2)
for x,y in R['middle_case_mounts']:
    rear -= cyl(x,y,27.9,cd,2.2)

# Preserve the successful battery seat exactly. New 19 x 29 bay turns the
# 17 x 27 charger upright. A flat internal plinth over the rear transition
# keeps this longer PCB level without moving the battery or the slide switch.
cx,cy = R['charger_center']
cw,ch = R['charger_bay_xy']
rail = rounded(cx,cy,18.5,cw+2.4,ch+2.4,2,1.51)-box(cx-cw/2,cy-ch/2,18.4,cw,ch,1.8)
# Both short ends are open for the input/output pads after the 90 degree turn.
for yy in (cy-ch/2-1.3,cy+ch/2-.1):
    rail -= box(cx-6,yy,18.4,12,1.5,1.8)
rear += rail
plinth = box(cx-cw/2-1.2,cy-ch/2-1.2,20,cw+2.4,ch+2.4,10)
rear += plinth ^ scope['inner_below'].translate([0,0,1])
charger_bay = box(cx-cw/2,cy-ch/2,16,cw,ch,4)
charger = box(cx-8.5,cy-13.5,18.5,17,27,1)
diode = box(*R['diode_reserve_origin'],10,12,8)

# Speaker: screw-mounted open-centre cap, with its lower toes only over the
# rigid outer basket. The existing front gasket gap is retained; no adhesive
# is required for retention. A soft loose rim gasket may be used for acoustics.
spx,spy=75.5,135
sf,st = R['speaker_cap_front'],R['speaker_cap_thickness']
speaker_cap = rounded(spx,spy,sf,33.2,23.2,1.6,st)-rounded(spx,spy,sf-.1,25,15,1,st+.2)
speaker_toes=[]
for x,y,w,h in [(71,125.4,9,1.3),(71,143.3,9,1.3)]:
    toe=box(x,y,7.55,w,h,.46)
    speaker_cap+=toe
    speaker_toes.append(toe)
for x,y in R['speaker_mounts']:
    near_x = 60 if x<spx else 91
    speaker_cap += (cyl(x,y,sf,5,st)+cyl(near_x,y,sf,5,st)).hull()
    speaker_cap -= cyl(x,y,sf-.1,cd,st+.2)
    front += cyl(x,y,2.9,5,sf-2.9)
    front -= cyl(x,y,sf-3.9,pd,4.0)
speaker_wire=box(89.5,133,3,7,4,10)
speaker_cap -= speaker_wire
# Two flat lands under the rigid long edges maintain the 0.5 mm acoustic
# clearance above the front grille without requiring a glued gasket.
for yy in (125.15,143.95):
    front += box(71,yy,2.99,9,.9,.51)

# Four independent corner hold-downs avoid the rear FPC, central ICs and the
# soldered left-edge signal wires. Do NOT use overall LCD thickness as an
# invented measurement of its bare rear PCB plane. Captured optional pads
# take up that unknown gap; both feet always screw down against hard posts.
lcd_clips=[]
toe_centers=[]
lf,lt=R['lcd_clip_seat'],R['lcd_clip_thickness']
for x,y in R['lcd_mounts']:
    top = y<11
    ty = 12.3 if top else 68.7
    toe_centers.append((x,ty))
    plate=(cyl(x,y,lf,6,lt)+cyl(x,ty,lf,5,lt)).hull()
    plate += box(x-2,ty-1.5,R['lcd_clip_toe_front'],4,3,lf-R['lcd_clip_toe_front']+.02)
    plate -= cyl(x,y,lf-.1,cd,lt+.2)
    # Registration hole for an optional shim pin (not a screw through LCD).
    plate -= cyl(x,ty,lf-.3,2.4,lt+.5)
    lcd_clips.append(plate)
    front += cyl(x,y,2.9,5.5,lf-2.9)
    front -= cyl(x,y,lf-3.5,pd,3.6)

# Light engraving only on an internal solid patch below the button plate.
# Draw letter strokes as vector rectangles/cross-sections, no external labels.
def engraved_text(text,x,y,z,size=.5,depth=.25):
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',36)
    mask=Image.new('1',(600,48)); draw=ImageDraw.Draw(mask)
    draw.text((1,-3),text,font=font,fill=1,stroke_width=1)
    a=np.array(mask); cuts=[]
    for row in range(a.shape[0]):
        ids=np.flatnonzero(a[row]); groups=np.split(ids,np.where(np.diff(ids)>1)[0]+1)
        for g in groups:
            # Overlap raster runs: diagonally touching pixels must not make
            # zero-width corners/non-manifold engraved cavities in the STL.
            if len(g): cuts.append(box(x+g[0]*size-.012,y+row*size-.012,z,len(g)*size+.024,size+.024,depth))
    return union(cuts)
engraving=engraved_text('SCARLETPICO  R2',23,126,2.75,size=.095,depth=.3)
# XY is defined from the OUTSIDE front view. Looking into the front shell
# from its rear reverses X: mirror the cutter so the INTERNAL text reads normally.
engraving_bounds=mesh_of(engraving).bounds
engraving=engraving.mirror([1,0,0]).translate([engraving_bounds[0,0]+engraving_bounds[1,0],0,0])
front -= engraving

front_before_side_decor=front
side_decor=R.get('side_decor',{})
side_decor_wall_samples=[]
if side_decor.get('enabled',False):
    radius=side_decor['radius']; depth=side_decor['depth']
    z0,z1=side_decor['z_range']
    cutters=[]
    for x in (depth-radius,103+radius-depth):
        for y in side_decor['centers_y']:
            cutters.append(cyl(x,y,z0,2*radius,z1-z0))
            cutters.append(m.Manifold.sphere(radius,48).translate([x,y,z0]))
            cutters.append(m.Manifold.sphere(radius,48).translate([x,y,z1]))
    front-=union(cutters)
    # These are blind outer-wall grooves, not vents or changes to the cavity.
    removed=front_before_side_decor-front
    allowed=box(-.01,97,3,.37,16,21)+box(102.64,97,3,.37,16,21)
    assert (removed-allowed).volume()<.001,'side decor outside approved patches'
    assert (front-front_before_side_decor).volume()<.001
    for y in side_decor['centers_y']:
        for x in (-.01,97):
            sample=front ^ box(x,y-.005,10,6.01,.01,.01)
            thickness=float(mesh_of(sample).extents[0])
            assert thickness>2.6,('side wall too thin',x,y,thickness)
            side_decor_wall_samples.append(round(thickness,4))

# Component and motion validation in actual assembly, not STL bed positions.
lcd=box(4,11,2.002,95,59,7.998); battery=scope['battery']+scope['battery_space']
stack=ns['stack']; speaker=ns['speaker_proxy']; switch=scope['switch']
usb_carrier=box(38.5,3,10.8,26,4.8,8.4)
usb_reserve=box(46.3,0,12.8,10.4,12,4.4)
assemblies=[('front',front),('rear',rear),('button retainer',retainer),('dpad',dpad),
            *caps.items(),('speaker cap',speaker_cap),
            *[(f'lcd clip {i+1}',p) for i,p in enumerate(lcd_clips)]]
for i,(name,a) in enumerate(assemblies):
    for other,b in assemblies[:i]: clear(a,b,name+' / '+other)
components=[('LCD envelope',lcd),('battery with free space',battery),('PCB stack',stack),
            ('speaker envelope',speaker),('charger bay',charger_bay),('diode reserve',diode),
            ('switch reserve',switch),('USB carrier envelope',usb_carrier),('USB body reserve',usb_reserve)]
for slot in ns['slots']:
    clear(slot,front,'speaker grille remains open')
clear(speaker_wire,front,'speaker wire exit/front')
clear(speaker_wire,speaker_cap,'speaker wire exit/cap')
for label,part in components:
    for name,a in assemblies: clear(part,a,label+' / '+name)
for label,part in [('charger bay',charger_bay),('diode reserve',diode)]:
    for name,a in components:
        if name not in (label,'USB carrier envelope','USB body reserve'): clear(part,a,label+' / '+name)
assert (charger-charger_bay).volume()<.001
for name,(x,y) in centers.items():
    tact=box(x-3,y-3,6.05,6,6,6)
    clear(tact,retainer,'tact/retainer '+name)
    if name in caps: clear(tact,caps[name],'unpressed switch '+name)
for name,cap in caps.items():
    assert (cap.translate([0,0,-.05]) ^ front).volume()>.001,'cap can escape through front '+name
    for travel in np.linspace(0,.749,16):
        moving=cap.translate([0,0,float(travel)])
        clear(moving,front,'cap/front travel '+name)
        clear(moving,retainer,'cap/retainer travel '+name)
    assert (cap.translate([0,0,.77]) ^ retainer).volume()>.001, 'missing stop '+name
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    rocked=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(rocked,front,'dpad rocking/front')
    clear(rocked,retainer,'dpad rocking/retainer')
same(scope['battery_rail'],rear ^ scope['battery_rail'],'battery rails changed')
for y in [17,35,53]:
    zone=box(12,y-.1,13,56,.2,8)
    same(rear ^ zone,scope['lid'] ^ zone,'battery area changed')
assert np.allclose(mesh_of(front).bounds,mesh_of(parent_front).bounds,atol=.001)
accent_fill=ns['screen_accent'] ^ box(0,0,0,103,150,.31)
assert (accent_fill-front).volume()<.001,'exterior accent not fully filled'

# The back, including its battery, can approach straight from behind. This
# checks new LCD/speaker clamps against power parts throughout closure.
for step in np.linspace(0,30,61):
    for name,a in [('rear',rear),('battery',battery),('charger bay',charger_bay)]:
        moved=a.translate([0,0,float(step)])
        for other,b in assemblies:
            if other!='rear': clear(moved,b,'closing '+name+' / '+other)

fasteners=[]
def check_screws(mounts,seat,thickness,pilot_depth,target,part,label):
    engagement=R['screw_length']-thickness
    assert engagement>=2.5 and pilot_depth-engagement>=.4
    for x,y in mounts:
        passage=cyl(x,y,seat-.01,cd-.05,thickness+.02)
        clear(passage,part,label+' passage')
        bore=cyl(x,y,seat-pilot_depth+.01,pd-.04,pilot_depth)
        clear(bore,target,label+' pilot')
        floor=seat-pilot_depth
        assert floor>=1.3
        # Conservative head envelope, outside the plastic bearing surface.
        head=cyl(x,y,seat+thickness,4.5,1.6)
        for name,a in assemblies:
            if name!=label: clear(head,a,label+' screw head/'+name)
        for name,a in components: clear(head,a,label+' screw head/'+name)
    fasteners.append(dict(group=label,count=len(mounts),screw='M2 x 6 self-tapping for plastic',
                          engagement_mm=round(engagement,3),pilot_depth_mm=pilot_depth,
                          bottom_margin_mm=round(pilot_depth-engagement,3)))
check_screws(ret_mounts,rf,rt,3.5,front,retainer,'button retainer')
check_screws(R['speaker_mounts'],sf,st,3.9,front,speaker_cap,'speaker cap')
for i,((x,y),clip) in enumerate(zip(R['lcd_mounts'],lcd_clips)):
    check_screws([[x,y]],lf,lt,3.5,front,clip,f'lcd clip {i+1}')
for x,y in closure:
    z=20 if y<55.5 else 28
    clear(cyl(x,y,z-.05,cd-.05,2.1),rear,'closure passage')
    clear(cyl(x,y,z-5.9,pd-.04,6),front,'closure pilot')
fasteners.append(dict(group='case closure',count=6,engagement_mm=4,pilot_depth_mm=6,bottom_margin_mm=2))

OUT.mkdir(parents=True,exist_ok=True)
files=[]
def publish(part,name,components=1,rear_print=False,turn_over=False):
    assert part.status()==m.Error.NoError,(name,part.status())
    assert len(part.decompose())==components,(name,'components',len(part.decompose()))
    # Remove sub-micron boolean slivers BEFORE the float32 STL conversion.
    mesh=mesh_of(part.simplify(.0003))
    if rear_print:
        mesh.vertices[:,1]=150-mesh.vertices[:,1]
        mesh.vertices[:,2]=30-mesh.vertices[:,2]
    if turn_over:
        mesh.vertices[:,1]*=-1
        mesh.vertices[:,2]*=-1
    mesh.apply_translation(-mesh.bounds[0])
    mesh.vertices=np.round(mesh.vertices,4)
    mesh.merge_vertices(); mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10));mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0,name
    dest=OUT/(name+'.stl');mesh.export(dest)
    check=trimesh.load_mesh(dest,process=True)
    assert check.is_watertight and check.volume>0 and check.is_winding_consistent,name
    assert check.nondegenerate_faces().all(),name
    assert len(solid(check).decompose())==components,name
    files.append(dict(file=dest.name,parts=components,dimensions_mm=check.extents.round(3).tolist(),
                      watertight=True,STL_readback_validated=True,sha256=digest(dest)))
publish(front,'01-front-R2')
publish(rear,'02-rear-R2',rear_print=True)
publish(retainer,'03-button-retainer-R2')
publish(dpad,'04-dpad-R2')
publish(union(list(caps.values())),'05-four-caps-R2',4)
publish(speaker_cap,'06-speaker-retainer-R2',turn_over=True)
# Assembly coordinates stay unchanged above. Only the printable layout is
# packed into a row, with 3 mm between the independent clips.
lcd_print_layout=[]
next_x=0
for clip in lcd_clips:
    bounds=mesh_of(clip).bounds
    lcd_print_layout.append(clip.translate([next_x-bounds[0,0],-bounds[0,1],0]))
    next_x+=bounds[1,0]-bounds[0,0]+3
publish(union(lcd_print_layout),'07-four-LCD-clips-R2',4,turn_over=True)
# Six rows, four identical pads per row. Pins register inside clip toe holes;
# pads are mechanically captured between the PCB and fully tightened clip.
shoes=[]
for row,t in enumerate(R['lcd_shoe_thicknesses']):
    for col in range(4):
        x,y=col*7,row*7
        pad=box(x,y,0,4,3,t)+cyl(x+2,y+1.5,t,2.2,2.5)
        shoes.append(pad)
publish(union(shoes),'08-LCD-pad-set-OPTIONAL',24)
# Small, fully screwed Start/Select fixture before spending another full case
# print. Same apertures, stop plane, stem gap and 6 mm screw seating as R2.
coupon_front=front ^ box(34,101,0,36,23,rf)
coupon_retainer=retainer ^ box(34,101,rf,36,23,rt+.4)
for x,y in [(38,112),(66,112)]:
    coupon_front+=cyl(x,y,2.9,7,rf-2.9)
    coupon_front-=cyl(x,y,rf-3.5,pd,3.6)
    coupon_retainer-=cyl(x,y,rf-.1,cd,rt+.2)
for name in ('SELECT','START'):
    for travel in (0,.3,.749):
        clear(caps[name].translate([0,0,travel]),coupon_front,'coupon cap/front')
        clear(caps[name].translate([0,0,travel]),coupon_retainer,'coupon cap/retainer')
clear(coupon_front,coupon_retainer,'coupon fixed parts')
def on_bed(part,x,y):
    return part.translate(-mesh_of(part).bounds[0]).translate([x,y,0])
coupon=on_bed(coupon_front,0,0)+on_bed(coupon_retainer,42,0)
coupon+=on_bed(caps['SELECT'],84,0)+on_bed(caps['START'],97,0)
publish(coupon,'09-Start-Select-FIT-TEST-OPTIONAL',4)
for source in ('usb-c-carrier-DRAFT.stl','usb-c-slider-PRINT-TWO.stl'):
    shutil.copyfile(CASE/'usb-c-top/output'/source,OUT/source)
report=dict(revision=R['revision'],status='CAD CHECKED / PHYSICAL FIT NOT YET TESTED',
            outer_size_mm=[103,150,30],upper_depth_mm=22,lower_depth_mm=30,
            cap_free_travel_mm=.75,cap_to_tact_neutral_gap_mm=.3,
            protrusion_mm=dict(caps=R['cap_protrusion'],dpad=R['dpad_protrusion']),
            switch_travel_and_forces_measured=False,LCD_rear_PCB_contact_height_measured=False,
            battery_seat_preserved=True,charger_rotated_dimensions_mm=[17,27,1],charger_bay_mm=[19,29,4],
            charger_user_height_not_independently_verified=True,assembly_collision_checks='passed',
            straight_rear_closure_path_checked=True,fasteners=fasteners,parts=files,
            prior_files_unchanged=all(digest(p)==v for p,v in before.items()))
report['side_decor']=dict(per_side=len(side_decor.get('centers_y',[])),
                          depth_mm=side_decor.get('depth',0),blind=True,
                          sampled_remaining_wall_mm=side_decor_wall_samples)
assert report['prior_files_unchanged']
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

# Actual triangle renders, no invented hardware or cosmetic surface edits.
def preview():
    im=Image.new('RGB',(1800,1450),'#f0f2f5');draw=ImageDraw.Draw(im)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',26)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
    draw.text((30,20),'ScarletPico R2 / mechanical fit-check',font=font,fill='#172533')
    draw.text((30,60),'103 x 150 mm unchanged | 22 / 30 mm depth | new internal retainers | no exterior labels',font=small,fill='#465567')
    def panel(items,center,scale,origin,basis,rect):
        pixels=np.array(im);depth=np.full((im.height,im.width),-np.inf)
        bx0,by0,bx1,by1=rect
        for geom,color in items:
            mesh=mesh_of(geom);vv=(mesh.vertices-np.array(origin))@np.array(basis).T
            for face,normal in zip(mesh.faces,mesh.face_normals):
                p=vv[face];xy=p[:,:2]*scale+center
                lo=np.maximum(np.floor(xy.min(axis=0)).astype(int),[bx0,by0])
                hi=np.minimum(np.ceil(xy.max(axis=0)).astype(int),[bx1-1,by1-1])
                if np.any(hi<lo):continue
                a,b,c=xy;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(den)<1e-9:continue
                yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
                wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wc=1-wa-wb
                zz=wa*p[0,2]+wb*p[1,2]+wc*p[2,2];db=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                mask=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>db)
                db[mask]=zz[mask]
                shade=.62+.36*abs(float(normal@np.array([.25,-.4,.88])))
                pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=tuple(int(c*shade) for c in color)
        im.paste(Image.fromarray(pixels))
    red=(184,59,66);blue=(66,136,180);amber=(227,175,66);dark=(48,54,65)
    panel([(front,red),(dpad,dark),*[(c,dark) for c in caps.values()],(box(8,12.5,.8,87,56,.5),(25,33,41))],
          (300,445),3.8,[51.5,75,0],[[.96,-.1,.3],[.04,.88,.4],[-.27,-.4,-.85]],(15,100,585,820))
    panel([(front,red),(retainer,blue),(speaker_cap,amber),*[(c,amber) for c in lcd_clips]],
          (900,445),3.8,[51.5,75,0],[[-1,0,0],[0,.94,-.35],[0,.35,.94]],(600,100,1185,820))
    # Rear seen from inside (from front looking toward positive Z).
    panel([(rear,red),(charger,(72,142,170)),(scope['battery'],(159,181,185))],
          (1500,445),3.8,[51.5,75,20],[[1,0,0],[0,.94,.35],[0,.35,-.94]],(1200,100,1785,820))
    draw=ImageDraw.Draw(im)
    for x,title,sub in [(35,'FRONT / taller caps','Same apertures and overall envelope'),(625,'INSIDE FRONT / blue + yellow parts','Blue: button retainer. Yellow: LCD + speaker clips'),(1225,'INSIDE REAR / rotated charger','Battery seat unchanged; 6 case closure points')]:
        draw.text((x,835),title,font=small,fill='#172533');draw.text((x,870),sub,font=small,fill='#465567')
    draw.text((35,990),'BUTTON SECTION / nominal dimensions, mm',font=small,fill='#172533')
    # Dimensioned schematic complements, but does not replace, the triangle renders.
    x,y,sc=60,1340,26
    for z,h,w,col in [(0,3,50,red),(-2.2,6.3,8,dark),(3,1.1,10.4,dark),(4.1,1.65,3,dark),(4.85,1.05,18,blue),(6.05,3,6,(71,157,115))]:
        if col==red:
            draw.rectangle((x,y-(z+h)*sc,x+18*sc,y-z*sc),fill=col)
            draw.rectangle((x+6*sc,y-3*sc,x+12*sc,y),fill='#f0f2f5')
        elif col==blue:
            for xx in (x+1*sc,x+11*sc):draw.rectangle((xx,y-(z+h)*sc,xx+6*sc,y-z*sc),fill=col)
        else:draw.rectangle((x+(9-w/2)*sc,y-(z+h)*sc,x+(9+w/2)*sc,y-z*sc),fill=col)
    draw.text((770,1065),'Cap protrusion 2.2 mm (was 1.0)',font=small,fill='#172533')
    draw.text((770,1110),'Free cap travel 0.75 mm (was 0.35)',font=small,fill='#172533')
    draw.text((770,1155),'Neutral stem / actuator clearance 0.30 mm',font=small,fill='#172533')
    draw.text((770,1235),'Physical fit, tactile force and LCD contact plane',font=small,fill='#9a3f3f')
    draw.text((770,1270),'still need a fit test.',font=small,fill='#9a3f3f')
    im.save(OUT/'preview-R2.png')
preview()
with zipfile.ZipFile(ROOT/'ScarletPico-case-R2.zip','w',compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in [ROOT/'README.md',ROOT/'parameters.json',ROOT/'build_rev2.py',*sorted(OUT.iterdir()),
                 *sorted((ROOT/'decor-preview').rglob('*'))]:
        if path.is_file(): bundle.write(path,arcname=path.relative_to(ROOT))
