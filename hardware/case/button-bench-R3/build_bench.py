#!/usr/bin/env python3
"""Standalone, fixed-height ALL-button fit bench for the R2/R3 mechanism.

The production cap, pivot, retainer and board datums remain unchanged.
Only the disposable front coupon and open rear fixture are new.
"""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CASE = ROOT.parent
OUT = ROOT / 'output'
protected = {p: hashlib.sha256(p.read_bytes()).hexdigest()
             for folder in ('rev2', 'rev3-split', 'variable-depth', 'usb-c-top')
             for p in (CASE / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}

# Evaluate the existing builder only up to its validation/publication boundary.
# Its definition of front, retainer, caps and pivot is the single source of truth.
source = CASE / 'rev2/build_rev2.py'
s = {'__file__': str(source)}
exec(compile(source.read_text().split('# Component and motion validation')[0], str(source), 'exec'), s)
box, cyl, union, mesh_of, solid = (s[k] for k in ('box', 'cyl', 'union', 'mesh_of', 'solid'))
R, ns = s['R'], s['ns']
rf, rt = R['retainer_front'], R['retainer_thickness']
retainer, dpad, caps = s['retainer'], s['dpad'], s['caps']
centers, dx, dy = s['centers'], s['dx'], s['dy']
pd, cd = R['pilot_diameter'], R['clearance_diameter']
closure = [(10.5, 69), (92.5, 69), (10.5, 127), (92.5, 127)]
x0, y0, width, height = 6.5, 65.5, 90., 65.
back = 28.

def clear(a, b, name, tol=.003):
    v = (a ^ b).volume()
    assert v < tol, (name, v)

def same(a, b, name, tol=.003):
    v = (a-b).volume() + (b-a).volume()
    assert v < tol, (name, v)

# Cut a real front-panel fragment containing ALL moving interfaces and all
# six original retainer seats. Upper/lower margins are fixture-only extensions.
working_zone = box(x0, 70.5, -.01, width, 53.5, rf+.02)
front = s['front'] ^ working_zone
front += box(x0, y0, 0, width, 5.1, 2.998)
front += box(x0, 123.9, 0, width, y0+height-123.9, 2.998)
for x, y in closure:
    front += cyl(x, y, 2.9, 7, back-2.9)
    front -= cyl(x, y, back-5, pd, 5.1)

# Open rear frame at exactly the SAME Z and board-contact datums as the case.
# The rails sit behind the full 7 mm module projection, not on components.
rear = box(x0, y0, back, width, height, 2)
rear -= box(x0+4, y0+4, back-.1, width-8, height-8, 2.2)
for yy in (75.5, 120.5):
    rear += box(x0, yy-4.5, back, width, 9, 2)
for support in ns['rear_supports']:
    rear += support
for x, y in ns['mounts']:
    rear -= cyl(x, y, ns['REAR_PCB_Z']-.1,
                ns['P']['rear_board_clearance_diameter'], 11)
for x, y in closure:
    rear -= cyl(x, y, back-.1, cd, 2.2)

# The important contact surfaces match the production parts, not an arbitrary
# finger-held arrangement. Fixture margins do not enter the working region.
interface_zones = [box(dx-15,dy-15,-.01,30,30,rf+.02)]
interface_zones += [box(x-6,y-6,-.01,12,12,rf+.02)
                    for name,(x,y) in centers.items() if name in caps]
interface_zones += [box(x-3.5,y-3.5,-.01,7,7,rf+.02) for x,y in R['retainer_mounts']]
for zone in interface_zones:
    same(front ^ zone, s['front'] ^ zone, 'working front interfaces changed')
for x, y in ns['mounts']:
    seat = box(x-3.6, y-3.6, ns['REAR_PCB_Z'], 7.2, 7.2, .2)
    same(rear ^ seat, union(ns['rear_supports']) ^ seat, 'board seat changed')

parts = [('front coupon', front), ('rear frame', rear), ('retainer', retainer),
         ('dpad', dpad), *caps.items()]
for i, (name, a) in enumerate(parts):
    assert a.status() == m.Error.NoError and len(a.decompose()) == 1, name
    for other, b in parts[:i]:
        clear(a, b, name+' / '+other)

pcb = ns['stack']
for name, part in parts:
    clear(pcb, part, 'board / '+name)
modules = box(16.5, 73, ns['REAR_PCB_Z'], 70, 50, 7)
modules -= union([cyl(x, y, ns['REAR_PCB_Z']-.1, 7.1, 7.2) for x, y in ns['mounts']])
clear(modules, rear, 'module clearance / rear frame')
clear(modules, front, 'module clearance / front towers')
for name, (x, y) in centers.items():
    tact = box(x-3, y-3, 6.05, 6, 6, 6)
    clear(tact, front, 'tact / front '+name)
    clear(tact, retainer, 'tact / retainer '+name)
    if name in caps:
        clear(tact, caps[name], 'neutral actuator gap '+name)
for name, cap in caps.items():
    for travel in np.linspace(0, .749, 16):
        moving = cap.translate([0, 0, float(travel)])
        clear(moving, front, 'cap / front '+name)
        clear(moving, retainer, 'cap / retainer '+name)
    assert (cap.translate([0, 0, .77]) ^ retainer).volume() > .001, 'cap stop '+name
    assert (cap.translate([0, 0, -.05]) ^ front).volume() > .001, 'cap retention '+name
for ax, ay in [(-3.2,0), (3.2,0), (0,-3.2), (0,3.2), (-3,-3), (-3,3), (3,-3), (3,3)]:
    moving = dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(moving, front, 'rocking / front')
    clear(moving, retainer, 'rocking / retainer')
for step in np.linspace(0, 30, 31):
    moved = rear.translate([0, 0, float(step)])
    for name, part in parts:
        if name != 'rear frame':
            clear(moved, part, 'closing / '+name)
    clear(moved, pcb, 'closing / PCB')
for x, y in closure:
    clear(cyl(x,y,back+.01,cd-.05,1.98), rear, 'rear screw passage')
    clear(cyl(x,y,back-4,pd-.05,3.99), front, 'front pilot engagement')
    clear(cyl(x,y,30,4.5,1.6), pcb+retainer, 'rear screw head clearance')
for x, y in R['retainer_mounts']:
    clear(cyl(x,y,rf+.01,cd-.05,rt-.02), retainer, 'retainer passage')
    clear(cyl(x,y,rf-3,pd-.05,2.99), front, 'retainer pilot engagement')
    clear(cyl(x,y,rf+rt,4.5,1.6), pcb, 'retainer head / PCB')

OUT.mkdir(parents=True, exist_ok=True)
files = []
def publish(part, filename, rear_print=False, components=1):
    mesh = mesh_of(part.simplify(.0003))
    if rear_print:
        # Proper 180-degree rotation: rear outside down, four board posts up.
        mesh.vertices[:,1] *= -1
        mesh.vertices[:,2] *= -1
    mesh.apply_translation(-mesh.bounds[0])
    mesh.vertices = np.round(mesh.vertices,4)
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10))
    mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    path = OUT / filename
    mesh.export(path)
    check = trimesh.load_mesh(path, process=True)
    assert check.is_watertight and check.is_winding_consistent and check.volume > 0
    assert len(solid(check).decompose()) == components
    files.append(dict(file=filename, dimensions_mm=check.extents.round(3).tolist(),
                      volume_cm3=round(check.volume/1000,3), watertight=True,
                      STL_readback_validated=True, components=components))
publish(front, '01-all-buttons-front-TEST.stl')
publish(rear, '02-open-board-frame-TEST.stl', rear_print=True)
for filename in ('03-button-retainer-R2.stl','04-dpad-R2.stl','05-four-caps-R2.stl'):
    src = CASE / 'rev3-split/output' / filename
    shutil.copyfile(src, OUT / filename)
    assert (OUT / filename).read_bytes() == src.read_bytes()
    files.append(dict(file=filename, byte_identical_to_production=True))

# One import, one build plate: EIGHT independent printable bodies. No sprues
# join the actual parts. Use the same orientations as the separate exports.
layout = []
def place(part, x, y, flip=False):
    if flip:
        part = part.rotate([180,0,0])
    lo = mesh_of(part).bounds[0]
    part = part.translate([-lo[0]+x,-lo[1]+y,-lo[2]])
    for other in layout:
        # Check XY bounding rectangles, including all tall fixture towers.
        a,b = mesh_of(part).bounds,mesh_of(other).bounds
        gap = np.maximum(a[0,:2]-b[1,:2],b[0,:2]-a[1,:2])
        assert max(gap)>=4.9, ('build-plate spacing',gap)
    layout.append(part)
place(front,0,0)
place(rear,96,0,flip=True)
place(retainer,0,71)
place(dpad,96,71)
place(caps['A'],128,71)
place(caps['B'],144,71)
place(caps['SELECT'],128,89)
place(caps['START'],144,89)
all_on_bed = union(layout)
assert len(all_on_bed.decompose()) == 8
assert np.all(mesh_of(all_on_bed).extents[:2] < 210), 'does not fit K1C build plate'
publish(all_on_bed,'00-ALL-BUTTONS-TEST-ONE-PLATE.stl',components=8)

# Preferred quick test: no rear frame, no tall frame towers. This checks
# printed-part movement, not the fixed-height PCB stack.
light_front = s['front'] ^ working_zone
assert len(light_front.decompose()) == 1
clear(light_front, retainer, 'light front / retainer')
for name, cap in caps.items():
    for travel in np.linspace(0,.749,16):
        clear(cap.translate([0,0,float(travel)]), light_front, 'light cap / front '+name)
    assert (cap.translate([0,0,-.05]) ^ light_front).volume()>.001, 'light cap retention '+name
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    moving=dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    clear(moving,light_front,'light dpad rocking / front')
layout = []
place(light_front,0,0)
place(retainer,96,0)
place(dpad,0,60)
place(caps['A'],33,60)
place(caps['B'],49,60)
place(caps['SELECT'],65,60)
place(caps['START'],81,60)
light_layout = list(layout)
light_on_bed = union(light_layout)
publish(light_on_bed,'00-ALL-BUTTONS-LIGHT-ONE-PLATE.stl',components=7)

# Small orthographic triangle renderer: actual CAD meshes, not generated art.
def preview():
    im = Image.new('RGB', (1600,950), '#f1f3f6')
    pixels = np.asarray(im).copy()
    def panel(items, center, scale, origin, basis, rect):
        depth = np.full((950,1600), -np.inf)
        basis = np.array(basis)
        for part, color in items:
            mesh = mesh_of(part)
            vv = (mesh.vertices-np.array(origin)) @ basis.T
            for face, normal in zip(mesh.faces, mesh.face_normals):
                p = vv[face]
                xy = p[:,:2]*scale + center
                lo = np.maximum(np.floor(xy.min(axis=0)).astype(int),rect[:2])
                hi = np.minimum(np.ceil(xy.max(axis=0)).astype(int),np.array(rect[2:])-1)
                if np.any(hi<lo): continue
                a,b,c = xy
                den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(den)<1e-10: continue
                yy,xx = np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                wa = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
                wb = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
                wc = 1-wa-wb
                zz = wa*p[0,2]+wb*p[1,2]+wc*p[2,2]
                db = depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                mask = (wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>db)
                db[mask] = zz[mask]
                shade = .66+.30*abs(float(normal@np.array([.3,-.4,.86])))
                pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask] = tuple(int(v*shade) for v in color)
    red, blue, yellow = (177,67,73),(56,130,171),(222,174,69)
    dark, green = (50,57,68),(71,141,107)
    controls = [(dpad,dark),*[(v,dark) for v in caps.values()]]
    # Camera along negative Z to show every button in the assembled front.
    panel([(front,red),(retainer,blue),(rear,yellow),*controls], [380,295], 6.0,
          [51.5,98,12], [[1,0,0],[0,.90,.436],[0,.436,-.90]], [20,90,790,550])
    # Exploded from behind: separate fixed layers while preserving XY mapping.
    panel([(front,red),(retainer.translate([0,0,9]),blue),
           (rear.translate([0,0,30]),yellow),*controls], [1170,355], 5.4,
          [51.5,98,30], [[-1,0,0],[0,.80,-.60],[0,.60,.80]], [805,90,1580,650])
    # Rear frame view with board-sized proxy and actuator bodies for context.
    for i, (part, col) in enumerate([(front,red),(rear,yellow)]):
        item = part
        if i==1:
            item = part.rotate([180,0,0])
        bd = mesh_of(item).bounds
        item = item.translate(-bd[0])
        panel([(item,col)], [195+i*360,740], 3.3, [45,32.5,0],
              [[1,0,0],[0,.94,-.34],[0,.34,.94]], [20+i*360,585,365+i*360,920])
    im.paste(Image.fromarray(pixels))
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',27)
    small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',21)
    draw.text((30,20),'ALL-BUTTON BENCH / R2-R3 mechanism unchanged',font=font,fill='#172533')
    draw.text((30,57),'D-pad + A/B + Start/Select | fixed PCB height | 90 x 65 mm fixture footprint',font=small,fill='#465567')
    draw.text((45,535),'Assembled front / all controls',font=small,fill='#172533')
    draw.text((830,665),'Exploded: red front, blue retainer, yellow rear frame',font=small,fill='#172533')
    draw.text((55,911),'New front coupon',font=small,fill='#172533')
    draw.text((405,911),'New open rear frame',font=small,fill='#172533')
    draw.text((830,735),'Production retainer + caps + D-pad are reused.',font=small,fill='#465567')
    draw.text((830,775),'Not a finished enclosure or an electrical insulation cover.',font=small,fill='#465567')
    draw.text((830,815),'CAD clearances checked. Physical fit is not yet tested.',font=small,fill='#9a3f3f')
    im.save(OUT / 'preview-all-buttons.png')
    pixels[:] = (241,243,246)
    palette = [red,blue,dark,dark,dark,dark,dark]
    panel(list(zip(light_layout,palette)),[800,475],7.5,[92.5,43.3,0],
          [[1,0,0],[0,1,0],[0,0,1]],[25,100,1575,850])
    im.paste(Image.fromarray(pixels))
    draw=ImageDraw.Draw(im)
    draw.text((30,20),'QUICK BUTTON TEST / ONE STL / 7 separate parts',font=font,fill='#172533')
    draw.text((30,60),'No rear frame or tall towers. Front + unchanged retainer + D-pad + A/B + Start/Select.',font=small,fill='#465567')
    for x,label in [(60,'D-pad'),(320,'A'),(440,'B'),(560,'Select'),(680,'Start')]:
        draw.text((x,720),label,font=small,fill='#172533')
    draw.text((30,880),'185 x 86.6 mm layout. Scale 100%. Original six M2 x 6 retainer mounts retained.',font=small,fill='#465567')
    draw.text((30,915),'Checks free motion and retention; does not fix PCB height or prove no electrical preload.',font=small,fill='#9a3f3f')
    im.save(OUT/'preview-light-one-plate.png')
preview()

assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in protected.items())
report = dict(status='CAD CHECKED / PHYSICAL FIT NOT YET TESTED',
              production_geometry_unchanged=True, protected_files_unchanged=True,
              PCB_front_z_mm=12.05, PCB_rear_contact_z_mm=ns['REAR_PCB_Z'],
              module_rear_limit_z_mm=ns['REAR_PCB_Z']+7,
              frame_inner_z_mm=28, board_mount_pitch_mm=[65,45],
              cap_free_travel_mm=.75, nominal_neutral_actuator_gap_mm=.3,
              case_screws=dict(count=4,type='M2 x 6 plastic self-tapping',engagement_mm=4,pilot_depth_mm=5),
              retainer_screws=dict(count=6,type='M2 x 6 plastic self-tapping',engagement_mm=3,pilot_depth_mm=3.5),
              board_screws='Reuse the four existing matching case-to-brass-spacer screws; not M2 self-tappers.',
              board_support_geometry_identical=True,
              limitations=['Photo-derived board hole centers and nominal 6 mm tactile height are not newly measured.',
                           'Open fixture does not protect loose powered components.',
                           'No measured switch forces, physical PETG fit or fatigue test.'],
              preferred_file='00-ALL-BUTTONS-LIGHT-ONE-PLATE.stl',
              light_test_independent_bodies=7,light_test_fixes_PCB_height=False,
              full_fixture_one_plate_independent_bodies=8, parts=files)
(OUT / 'checks.json').write_text(json.dumps(report,indent=2)+'\n')
with zipfile.ZipFile(ROOT / 'ScarletPico-all-buttons-TEST.zip','w',zipfile.ZIP_DEFLATED) as bundle:
    for p in [ROOT / 'README.md', ROOT / 'build_bench.py', *sorted(OUT.iterdir())]:
        if p.is_file(): bundle.write(p, p.relative_to(ROOT))
print(json.dumps(report,indent=2))
