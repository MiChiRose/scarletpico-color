#!/usr/bin/env python3
"""Adapt the supplied Tinkercad mesh, not an unrelated replacement shell.

Local dependencies: numpy, manifold3d 3.5.4, trimesh 5.1.0, Pillow.
Outputs are millimetres. This is a measurement/fit-check draft, not print-approved.
Original OBJ/MTL and firmware are never modified.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / 'parameters.json').read_text())
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
INPUT = ROOT / 'reference/tinker.obj'
BACK = P['outer_depth'] - P['rear_thickness']
REAR_PCB_Z = P['button_top_depth'] + P['stack_back_to_button_top'] - P['rear_module_protrusion']
REAR_STANDOFF = BACK - REAR_PCB_Z
MODULE_GAP = REAR_STANDOFF - P['rear_module_protrusion']
assert MODULE_GAP > 0, 'Modules reach the rear cover'
FOOT_FLARE_HEIGHT = min(.8, MODULE_GAP*.8)

def original_parts():
    vertices, faces = [], []
    for line in INPUT.read_text().splitlines():
        cols = line.split()
        if not cols:
            continue
        if cols[0] == 'v':
            vertices.append([float(x) for x in cols[1:4]])
        elif cols[0] == 'f':
            ids = [int(x.split('/')[0]) - 1 for x in cols[1:]]
            faces.extend([[ids[0], ids[i], ids[i+1]] for i in range(1, len(ids)-1)])
    parent = list(range(len(vertices)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for f in faces:
        for i in f[1:]:
            parent[find(i)] = find(f[0])
    groups = {}
    for face in faces:
        groups.setdefault(find(face[0]), []).append(face)
    parts = []
    for ff in groups.values():
        mesh = trimesh.Trimesh(vertices=vertices, faces=ff, process=False)
        mesh.remove_unreferenced_vertices()
        assert mesh.is_watertight, 'Input component has an open boundary'
        parts.append(mesh)
    return parts

def solid(mesh):
    result = m.Manifold(m.Mesh(np.asarray(mesh.vertices, dtype=np.float32),
                               np.asarray(mesh.faces, dtype=np.uint32)))
    assert result.status() == m.Error.NoError, result.status()
    return result

def mesh_of(s):
    data = s.to_mesh()
    return trimesh.Trimesh(vertices=data.vert_properties[:, :3], faces=data.tri_verts, process=False)

def box(x, y, z, w, h, d):
    return m.Manifold.cube([w, h, d]).translate([x, y, z])

def cylinder(x, y, z, diameter, height):
    return m.Manifold.cylinder(height, diameter / 2, circular_segments=48).translate([x, y, z])

def union(items):
    result = items[0]
    for item in items[1:]:
        result = result + item
    return result

def pill(x, y, z, w, h, depth):
    if abs(w-h) < 1e-6:
        return cylinder(x, y, z, w, depth)
    return (cylinder(x-(w-h)/2, y, z, h, depth) +
            cylinder(x+(w-h)/2, y, z, h, depth)).hull()

def cross(x, y, z, length, width, depth):
    return box(x-length/2, y-width/2, z, length, width, depth) + \
           box(x-width/2, y-length/2, z, width, length, depth)

def rounded_rectangle(x, y, z, width, height, radius, depth):
    return union([cylinder(x+u*(width/2-radius), y+v*(height/2-radius),
                           z, 2*radius, depth)
                  for u in [-1, 1] for v in [-1, 1]]).hull()

def xy(local):
    return tuple(a+b for a, b in zip(P['button_pcb_top_left'], local))

def exterior_ring(inset=0):
    """Constant-centre arcs give a true inward parallel offset of each corner."""
    tl,tr,br,bl = P['exterior_style']['corner_radii_tl_tr_br_bl']
    points=[]
    for x,y,r,start in [(tl,tl,tl,180),(103-tr,tr,tr,270),
                         (103-br,150-br,br,0),(bl,150-bl,bl,90)]:
        assert r>inset
        for a in np.linspace(start,start+90,25):
            points.append([x+(r-inset)*math.cos(math.radians(a)),
                           y+(r-inset)*math.sin(math.radians(a))])
    return np.array(points)

def rounded_exterior_envelope():
    """Loft exact circular edge profiles; no mesh smoothing of internal seats."""
    style=P['exterior_style']
    rf,rr=style['front_edge_radius'],style['rear_edge_radius']
    depth=P['outer_depth']
    levels=[]
    # Uniform angles give a circular fillet including its near-horizontal end.
    for a in np.linspace(0,math.pi/2,17):
        levels.append((rf-rf*math.cos(a),rf-rf*math.sin(a)))
    for a in np.linspace(0,math.pi/2,17):
        levels.append((depth-rr+rr*math.sin(a),rr-rr*math.cos(a)))
    rings=[np.column_stack([exterior_ring(inset),np.full(100,z)]) for z,inset in levels]
    vertices=np.vstack(rings).tolist()
    faces=[]
    for k in range(len(rings)-1):
        for j in range(100):
            a=k*100+j; b=k*100+(j+1)%100; c=b+100; e=a+100
            faces.extend([[a,b,c],[a,c,e]])
    lo=len(vertices); vertices.append([51.5,75,0])
    hi=len(vertices); vertices.append([51.5,75,depth])
    last=(len(rings)-1)*100
    for j in range(100):
        faces.extend([[lo,(j+1)%100,j],[hi,last+j,last+(j+1)%100]])
    return solid(trimesh.Trimesh(vertices=vertices,faces=faces,process=False))

def export(s, name, rear_print=False):
    assert s.status() == m.Error.NoError, (name, s.status())
    mesh = mesh_of(s)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0, name
    # Put the rear cover's outside face on the bed, posts upward. This is a
    # rotation, not a mirror; the assembly coordinates remain unchanged above.
    if rear_print:
        mesh.vertices[:, 1] = P['outer_height'] - mesh.vertices[:, 1]
        mesh.vertices[:, 2] *= -1
    mesh.apply_translation([0, 0, -mesh.bounds[0, 2]])
    dest = OUT / (name + '.stl')
    mesh.export(dest)
    return dict(file=dest.name, dimensions_mm=mesh.extents.round(3).tolist(),
                watertight=True, positive_volume=True,
                print_orientation='outside face down, posts up' if rear_print else 'front face down',
                sha256=hashlib.sha256(dest.read_bytes()).hexdigest())

parts = original_parts()
body = max(parts, key=lambda x: np.prod(x.extents)).copy()
assert np.allclose(body.extents, [150, 103, 20], atol=.01)
assert (P['outer_width'], P['outer_height']) == (103, 150), 'XY outline is inherited from the OBJ'
body.vertices[:, :2] = np.column_stack([body.vertices[:, 1] + 43, 70 - body.vertices[:, 0]])
# Only lift the existing sidewall rim; preserve user's outer outline/front detail.
body.vertices[np.isclose(body.vertices[:, 2], 20), 2] = BACK
shell = solid(body)
original_shell = shell
clear = P['display_clearance_per_side']
sx, sy = P['display_pcb_top_left']
sw, sh = P['display_pcb']
fx, fy = P['display_frame_top_left']
fw, fh = P['display_frame']
# Repair old 86x57 opening to expose the whole 87x56 black frame. Fill the old
# aperture within the PCB recess, then cut the new opening and clearance pocket.
shell = shell + box(sx, sy, 0, sw, sh, 2.001)
shell = shell - box(sx-clear, sy-clear, 2.001, sw+2*clear, sh+2*clear, 1.2)
shell = shell - box(fx-clear, fy-clear, -.2, fw+2*clear, fh+2*clear, 3.5)
# The supplied case already has a cross opening at the wrong location. Close it
# before moving the opening to the soldered board; otherwise holes merge.
shell = shell + box(10, 75, 0, 26, 26, 2.998)
centers = {name: xy(pos) for name, pos in P['button_centers_on_pcb'].items()}
dx, dy = xy(P['dpad_center_on_pcb'])
gap = P['moving_clearance_per_side']
dgap = P['dpad_clearance_per_side']
shell = shell - cross(dx, dy, -.2, P['dpad_length']+2*dgap,
                      P['dpad_bar_width']+2*dgap, 3.5)
for name in ['A', 'B', 'SELECT', 'START']:
    x, y = centers[name]
    width, height = (8, 8) if name in ['A', 'B'] else (7, 3.5)
    shell = shell - pill(x, y, -.2, width+2*gap, height+2*gap, 3.5)

mounts = [xy(pos) for pos in P['mounts_on_pcb']]
stop = P['retainer_front_depth']
rt = P['retainer_thickness']
pcb_z = P['button_top_depth'] + P['button_total_height']
# The occupied PCB corner holes now belong exclusively to the rear-cover mount.
# Retainer screws go through new side ears, not through either PCB.
retainer_mounts = P['retainer_mounts']
for x, y in retainer_mounts:
    shell = shell + cylinder(x, y, 2.9, 7, stop-2.9)
    shell = shell - cylinder(x, y, 1.2, P['fastener_pilot_diameter'], stop)

bx, by = P['button_pcb_top_left']
bw, bh = P['button_pcb']
retainer = box(bx, by, stop, bw, bh, rt)
flange_length = P['dpad_length'] + 2.8
flange_width = P['dpad_bar_width'] + 2.8
retainer = retainer - cross(dx, dy, stop-.1, flange_length+1, flange_width+1, rt+.2)
for name, (x, y) in centers.items():
    if name not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
        # Clear the 6x6 switch body; cap flange contacts this plate as a stop.
        retainer = retainer - box(x-3.6, y-3.6, stop-.1, 7.2, 7.2, rt+.2)
# Diagonal webs support a fixed central pivot, clear of the four actuator tips.
pivot = cylinder(dx, dy, 6.2, 4.5, 2)
for u, v in [(-10, -10), (10, -10), (-10, 10), (10, 10)]:
    web = (cylinder(dx, dy, 6.2, 2, 2) + cylinder(dx+u, dy+v, 6.2, 2, 2)).hull()
    pivot = pivot + web
retainer = retainer + pivot
for name in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
    x,y = centers[name]
    # Clearance for the entire switch body, not only its narrower actuator.
    retainer = retainer - box(x-3.3,y-3.3,P['button_top_depth']-.1,6.6,6.6,6.2)
for x, y in retainer_mounts:
    edge = bx+.5 if x < bx else bx+bw-.5
    ear = (cylinder(x,y,stop,7,rt) + cylinder(edge,y,stop,7,rt)).hull()
    retainer = retainer + ear
    retainer = retainer - cylinder(x,y,stop-.1,P['fastener_clearance_diameter'],rt+.2)

dpad = cross(dx, dy, -1.2, P['dpad_length'], P['dpad_bar_width'], 6.4)
dpad = dpad + cross(dx, dy, 4.0, flange_length, flange_width, 1.2)
dpad = dpad + m.Manifold.sphere(1, 32).translate([dx, dy, 5.2])
for name in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
    x, y = centers[name]
    dpad = dpad + cylinder(x, y, 4.9, 3, 1)

caps = {}
for name in ['A', 'B', 'SELECT', 'START']:
    x, y = centers[name]
    w, h = (8, 8) if name in ['A', 'B'] else (7, 3.5)
    cap = pill(x, y, -1, w, h, 5.3)
    cap = cap + pill(x, y, 3.1, w+2.4, h+2.4, 1.2)
    cap = cap + cylinder(x, y, 4.2, 3, 1.75)
    caps[name] = cap

# Flat rear lid matches the real outline via a horizontal cut of the original rim.
rim = original_shell.slice(10)
outer = rim.to_polygons()
contour = max(outer, key=lambda a: abs(np.dot(a[:,0], np.roll(a[:,1],1)) - np.dot(a[:,1], np.roll(a[:,0],1))))
lid = m.CrossSection([contour]).extrude(P['rear_thickness']).translate([0, 0, BACK])
# Corner fasteners stay clear of display and control boards. Their exact type,
# screw length and pilot diameter must be selected for the printer/material.
lid_mounts = [(5, 5), (98, 5), (5, 143), (98, 143)]
for x, y in lid_mounts:
    shell = shell + cylinder(x, y, 2.9, 6.5, BACK-2.9)
    shell = shell - cylinder(x, y, BACK-6, P['fastener_pilot_diameter'], 6.2)
    lid = lid - cylinder(x, y, BACK-.1, P['fastener_clearance_diameter'], P['rear_thickness']+.2)

# Four non-threaded posts bear against the rear PCB at its existing corner
# holes. Long screws enter from outside and engage the original brass spacers.
# 7 mm module projection is subtracted from the measured 21 mm total, not added.
rear_supports = []
for x,y in mounts:
    post = cylinder(x,y,REAR_PCB_Z,P['rear_standoff_diameter'],REAR_STANDOFF+.01)
    # Widen the root only ABOVE the maximum module height; do not claim that
    # the straight post footprints are clear until their XY pads are measured.
    foot = m.Manifold.cylinder(FOOT_FLARE_HEIGHT,P['rear_standoff_diameter']/2,
                               P['rear_standoff_base_diameter']/2,
                               circular_segments=48).translate([x,y,BACK-FOOT_FLARE_HEIGHT])
    bore = cylinder(x,y,REAR_PCB_Z-.1,P['rear_board_clearance_diameter'],
                    REAR_STANDOFF+P['rear_thickness']+.2)
    rear_supports.append((post+foot)-bore)
    lid = (lid+post+foot)-bore

# Speaker occupies a separate XY bay BELOW the PCB, not behind the 21 mm stack.
# Rectangular clearance is intentional: the photographed speaker's corner radii
# are unknown. The nominal full bounding box must fit, not only an assumed oval.
spx, spy = P['speaker_center']
spw, sph, spt = P['speaker_size']
spclear = P['speaker_clearance_per_side']
spwall = P['speaker_wall']
spiw, spih = spw+2*spclear, sph+2*spclear
spow, spoh = spiw+2*spwall, spih+2*spwall
spfront, sptop = P['speaker_front_depth'], P['speaker_fence_top_depth']
speaker_proxy = box(spx-spw/2, spy-sph/2, spfront, spw, sph, spt)
fence = rounded_rectangle(spx,spy,2.9,spow,spoh,spwall+.4,sptop-2.9)
fence = fence-rounded_rectangle(spx,spy,2.8,spiw,spih,.4,sptop-2.8+.1)
# Right short-end wire notch is open all the way to the panel's inside surface.
# No printed latch: a soft, rim-only adhesive gasket provides Z retention.
wire_exit = box(spx+spiw/2-.2,spy-P['speaker_wire_exit_width']/2,2.998,
                spwall+.5,P['speaker_wire_exit_width'],sptop-2.998+.1)
fence = fence-wire_exit
shell = shell+fence
grille = P['speaker_grille']
grille_y = [spy+(i-(grille['count']-1)/2)*grille['pitch'] for i in range(grille['count'])]
slots = [pill(0,y-spy,-.2,grille['length'],grille['width'],3.8)
         .rotate([0,0,grille['angle_deg']]).translate([spx,spy,0]) for y in grille_y]
for slot in slots:
    shell = shell-slot

# Rear-mounted power components. All coordinates remain front-view assembly
# coordinates; only the STL export flips the lid into its print orientation.
pre_power_shell,pre_power_lid = shell,lid
batw,bath,batt = P['battery_dimensions']
batx,baty = P['battery_center']
batgap = P['battery_clearance_per_side']
batback = BACK-P['battery_rear_adhesive_allowance']
batfront = batback-batt
biw,bih = batw+2*batgap,bath+2*batgap
railwall = P['battery_rail_wall']
batrailz = BACK-P['battery_rail_height']
battery_rail = rounded_rectangle(batx,baty,batrailz,biw+2*railwall,bih+2*railwall,
                                 railwall+.8,P['battery_rail_height']+.01)
battery_rail = battery_rail-rounded_rectangle(batx,baty,batrailz-.1,biw,bih,.8,
                                              P['battery_rail_height']+.2)
battery_wire = box(batx+biw/2-.2,baty-P['battery_wire_exit_width']/2,batrailz-.1,
                   railwall+.4,P['battery_wire_exit_width'],P['battery_rail_height']+.2)
battery_rail = battery_rail-battery_wire
lid = lid+battery_rail
battery_proxy = box(batx-batw/2,baty-bath/2,batfront,batw,bath,batt)
# Include 2 mm free space in front, not a rigid strap over the pouch.
battery_front_space = box(batx-batw/2,baty-bath/2,batfront-P['battery_front_keepout_extra'],
                           batw,bath,P['battery_front_keepout_extra'])

chx,chy = P['charger_bay_center']
chw,chh,chd = P['charger_bay_dimensions']
chz = BACK-P['charger_rail_height']
charger_rail = rounded_rectangle(chx,chy,chz,chw+2*railwall,chh+2*railwall,
                                 railwall+.8,P['charger_rail_height']+.01)
# Square inner corners preserve the stated full rectangular reservation.
charger_rail = charger_rail-box(chx-chw/2,chy-chh/2,chz-.1,chw,chh,P['charger_rail_height']+.2)
charger_wire = box(chx-chw/2-railwall-.1,chy-6,chz-.1,railwall+.3,12,P['charger_rail_height']+.2)
charger_rail = charger_rail-charger_wire
lid = lid+charger_rail
charger_keepout = box(chx-chw/2,chy-chh/2,BACK-chd,chw,chh,chd)
# Illustrative module size only; no claim that all TP4056 carriers are identical.
charger_proxy = box(chx-(chw-2)/2,chy-(chh-2)/2,BACK-chd+.5,chw-2,chh-2,chd-1)
diode_keepout = box(*P['diode_keepout_origin'],*P['diode_keepout_size'])
lcd_keepout = box(sx,sy,0,sw,sh,P['lcd_rear_keepout_depth'])

# Panel-mounted slide switch, on the upper RIGHT side. Repair/flatten only its
# mounting pad within the existing outer contour, then cut the slot and screws.
pw = P['power_switch']
assert pw['side']=='right'
pwy,pwz = pw['center_yz']
pwx = pw['flange_inner_plane_x']
pwlength,pwwidth = pw['flange_yz']
pad = box(pwx,pwy-pwlength/2-2,pwz-pwwidth/2-1.25,
          P['outer_width']-pwx,pwlength+4,pwwidth+2.5)
shell = shell+pad
aplen,apwidth = pw['aperture_yz']
switch_slot = box(pwx-.1,pwy-aplen/2,pwz-apwidth/2,P['outer_width']-pwx+.3,aplen,apwidth)
shell = shell-switch_slot
switch_bores = []
for y in [pwy-pw['mount_pitch']/2,pwy+pw['mount_pitch']/2]:
    bore = cylinder(0,0,0,pw['mount_clearance_diameter'],P['outer_width']-pwx+.3)
    bore = bore.rotate([0,90,0]).translate([pwx-.1,y,pwz])
    switch_bores.append(bore)
    shell = shell-bore
switch_flange = box(pwx-.5,pwy-pwlength/2,pwz-pwwidth/2,.5,pwlength,pwwidth)
switch_body = box(pwx-pw['inward_depth_with_terminals'],pwy-pw['body_length_y']/2,pwz-pwwidth/2,
                  pw['inward_depth_with_terminals'],pw['body_length_y'],pwwidth)
switch_wire = box(pwx-pw['inward_depth_with_terminals']-pw['wire_reserve_inward'],
                  pwy-pw['body_length_y']/2,pwz-pwwidth/2,
                  pw['wire_reserve_inward'],pw['body_length_y'],pwwidth)
switch_proxy = switch_flange+switch_body+switch_wire
acty,actz = pw['actuator_size_yz']
actuator_envelope = box(pwx,pwy-(acty+pw['assumed_travel'])/2,pwz-actz/2,
                        pw['actuator_height'],acty+pw['assumed_travel'],actz)

# Exterior-only redesign. Preserve the baseline internal geometry; broad fillet
# algorithms applied to the whole STL would also change button/display seats.
pre_style_shell,pre_style_lid = shell,lid
style=P['exterior_style']
style_envelope=rounded_exterior_envelope()
shell = shell ^ style_envelope
lid = lid ^ style_envelope
inside_contour = min(outer,key=lambda a: abs(np.dot(a[:,0],np.roll(a[:,1],1))-np.dot(a[:,1],np.roll(a[:,0],1))))
inner_area = m.CrossSection([inside_contour[::-1]])
assert inner_area.area()>13000, 'Interior contour is empty or wrongly oriented'
outer_area = m.CrossSection([contour]) ^ m.CrossSection([exterior_ring()])
wall_protection=inner_area.offset(style['minimum_sidewall_after_rounding'],circular_segments=96)
assert (wall_protection-outer_area).area()<.0001, 'Rounded corner thins existing sidewall excessively'

# Broad, shallow diagonal bevel at the speaker corner. Only the EXTERNAL face
# is sloped; the speaker's internal support plane stays at its previous Z.
diagonal=style['speaker_slope_diagonal_start']
slope=style['speaker_slope_gradient']
triangle=[(diagonal-150,150),(103,diagonal-103),(103,150)]
slope_points=[[x,y,z] for x,y in triangle for z in [-.1,slope*(x+y-diagonal)]]
speaker_face_cut=m.Manifold.hull_points(slope_points)
speaker_face_cut = speaker_face_cut ^ box(0,0,-.1,103,150,style['speaker_slope_max_depth']+.1)
shell = shell-speaker_face_cut
# Under-screen engraved line and rear blind grip comb: no extra external bulk.
screen_accent=pill(51.5,71.25,-.1,76,.65,style['screen_accent_depth']+.1)
shell=shell-screen_accent
grip_y=[style['rear_grip_first_y']+i*style['rear_grip_pitch'] for i in range(style['rear_grip_count'])]
grip_cuts=[pill(51.5,y,P['outer_depth']-style['rear_grip_depth'],
                style['rear_grip_length'],style['rear_grip_width'],style['rear_grip_depth']+.1) for y in grip_y]
for cut in grip_cuts:
    lid=lid-cut

report = {'status': P['status'], 'source_obj_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(),
          'source_component_sizes': [p.extents.round(3).tolist() for p in parts],
          'rear_clearance_to_stack_mm': BACK-P['button_top_depth']-P['stack_back_to_button_top'],
          'rear_module_protrusion_mm': P['rear_module_protrusion'],
          'rear_pcb_contact_depth_mm': REAR_PCB_Z,
          'rear_standoff_height_mm': REAR_STANDOFF,
          'longer_screw_extra_length_mm': REAR_STANDOFF+P['rear_thickness'],
          'rear_plastic_through_hole_mm': P['rear_board_clearance_diameter'],
          'rear_thread_confirmed': False,
          'mounting_hole_pitch_mm': [65,45],
          'module_footprint_clearance_checked': False,
          'not_validated': P['unfinished'], 'parts': []}

# Geometrical checks on the neutral mechanism; no claim about real printer fit.
for name, cap in [('dpad', dpad), *caps.items()]:
    assert (shell ^ cap).volume() < 0.0001, 'Neutral housing collision: '+name
    assert (retainer ^ cap).volume() < 0.0001, 'Neutral retainer collision: '+name
assert (shell ^ retainer).volume() < 0.0001, 'Retainer/housing collision'
for name, geometry in [('shell',shell),('lid',lid),('retainer',retainer),('dpad',dpad)]:
    assert len(geometry.decompose()) == 1, ('Disconnected part',name)
for name, (x,y) in centers.items():
    switch = box(x-3,y-3,P['button_top_depth'],6,6,P['button_total_height'])
    assert (switch ^ retainer).volume() < .0001, ('Switch/retainer collision',name)
# The 8 mm board/brass-spacer envelope is distinct from the 7 mm modules. A
# full rectangular 21 mm envelope would incorrectly classify posts as collisions
# with modules in the otherwise free corners. Actual module XY is unmeasured.
assert 0 < P['rear_module_protrusion'] < P['stack_back_to_button_top']-P['button_total_height']
assert REAR_STANDOFF > P['rear_module_protrusion']
stack = box(bx,by,pcb_z,bw,bh,REAR_PCB_Z-pcb_z)
assert (stack ^ shell).volume() < .0001 and (stack ^ lid).volume() < .0001
assert (shell ^ lid).volume() < .0001
assert (retainer ^ lid).volume() < .0001
# Power component exclusions and lid closing path. The LCD exclusion is an
# explicit provisional limit, not a measurement derived from a photograph.
power_envelopes = [('battery',battery_proxy+battery_front_space),('TP4056 bay',charger_keepout),
                   ('diode bay',diode_keepout),('slide switch',switch_proxy)]
for i,(name,geom) in enumerate(power_envelopes):
    for obstacle,other in [('front',shell),('rear',lid),('retainer',retainer),('stack',stack),
                           ('speaker',speaker_proxy),('LCD exclusion',lcd_keepout),
                           ('dpad',dpad),*caps.items()]:
        assert (geom ^ other).volume()<.0001, ('Power layout collision',name,obstacle)
    for name2,geom2 in power_envelopes[:i]:
        assert (geom ^ geom2).volume()<.0001, ('Power component collision',name,name2)
for step in np.linspace(0,30,31):
    # Open lid is displaced towards the back (+Z); closing must not sweep the
    # attached battery, charger or locating rails into the side switch.
    for name,geom in [('battery',battery_proxy),('charger',charger_keepout),('lid',lid)]:
        assert (geom.translate([0,0,float(step)]) ^ switch_proxy).volume()<.0001, ('Lid closing collision',name,step)
    for name,geom in [('battery',battery_proxy),('charger',charger_keepout),
                       ('battery rails',battery_rail),('charger rails',charger_rail)]:
        moved = geom.translate([0,0,float(step)])
        for obstacle,other in [('front',shell),('LCD exclusion',lcd_keepout),
                               ('retainer',retainer),('PCB stack',stack),('speaker',speaker_proxy)]:
            assert (moved ^ other).volume()<.0001, ('Power part closing collision',name,obstacle,step)
for geom in [switch_slot,*switch_bores,actuator_envelope]:
    assert (geom ^ shell).volume()<.0001, 'Switch aperture/screw/travel blocked'
assert (battery_wire ^ (lid ^ box(0,0,0,103,150,BACK-.001))).volume()<.0001, 'Battery lead notch blocked'
assert (charger_wire ^ (lid ^ box(0,0,0,103,150,BACK-.001))).volume()<.0001, 'Charger lead notch blocked'
assert np.allclose(mesh_of(shell).bounds,[[0,0,0],[103,150,BACK]],atol=.01), 'Changed front outer envelope'
assert mesh_of(lid).bounds[1,2] <= P['outer_depth']+.001, 'Changed rear outer envelope'
shell_change = (pre_style_shell-pre_power_shell)+(pre_power_shell-pre_style_shell)
assert (shell_change-pad).volume()<.0001, 'Front edit escaped the switch mounting area'
assert (pre_power_lid-pre_style_lid).volume()<.0001, 'Power rails removed material from existing lid'
# Styling may remove outer material, but it must NEVER add material into the
# existing cavity or alter mounting surfaces/bosses. Protect all internal posts.
assert (shell-pre_style_shell).volume()<.0001 and (lid-pre_style_lid).volume()<.0001
removed_shell=pre_style_shell-shell
removed_lid=pre_style_lid-lid
assert (removed_shell ^ inner_area.extrude(BACK-2.9).translate([0,0,2.9])).volume()<.0001, 'Styling touched internal front features'
assert (removed_lid ^ inner_area.extrude(BACK+.001)).volume()<.0001, 'Styling touched inside rear surface'
for support in rear_supports:
    assert (removed_lid ^ support).volume()<.0001, 'Styling changed a rear PCB support'
display_seat_region=box(sx-clear,sy-clear,0,sw+2*clear,sh+2*clear,3.3)
assert (removed_shell ^ display_seat_region).volume()<.0001, 'Styling changed the LCD aperture/recess'
for name,(x,y) in centers.items():
    assert (removed_shell ^ box(x-5,y-5,0,10,10,3.3)).volume()<.0001, ('Styling changed a button opening',name)
for x,y in lid_mounts:
    boss=cylinder(x,y,2.9,6.5,BACK-2.9)
    assert (removed_shell ^ boss).volume()<.0001, 'Rounding trimmed a closure boss'
    head_seat=cylinder(x,y,BACK,5,P['rear_thickness'])
    assert (removed_lid ^ head_seat).volume()<.0001, 'Rounding removed lid screw bearing area'
for slot in slots:
    b=mesh_of(slot).bounds
    assert b[0,0]>spx-spw/2 and b[1,0]<spx+spw/2
    assert b[0,1]>spy-sph/2 and b[1,1]<spy+sph/2
assert P['rear_thickness']-style['rear_grip_depth']>=1.6
def outer_section_area(geometry,z):
    contours=geometry.slice(z).to_polygons()
    boundary=max(contours,key=lambda a: abs(np.dot(a[:,0],np.roll(a[:,1],1))-np.dot(a[:,1],np.roll(a[:,0],1))))
    return m.CrossSection([boundary])
front_mating_outline=outer_section_area(shell,BACK-.001)
rear_mating_outline=outer_section_area(lid,BACK+.001)
assert (front_mating_outline-rear_mating_outline).area()<.001
assert (rear_mating_outline-front_mating_outline).area()<.001
report['exterior_style']={
    'outer_dimensions_mm':[103,150,P['outer_depth']],
    'corner_radii_tl_tr_br_bl_mm':style['corner_radii_tl_tr_br_bl'],
    'front_rear_edge_radii_mm':[style['front_edge_radius'],style['rear_edge_radius']],
    'minimum_sidewall_xy_mm':style['minimum_sidewall_after_rounding'],
    'material_added_by_styling_mm3':0,
    'internal_features_and_closure_bosses_changed':False,
    'speaker_translation_from_previous_mm':[24,0,0],
    'speaker_pocket_size_changed':False,
    'diagonal_front_max_depth_mm':style['speaker_slope_max_depth'],
    'front_thickness_floor_under_speaker_excluding_vents_mm':2.998-style['speaker_slope_max_depth'],
    'rear_blind_grooves':len(grip_cuts),
    'rear_remaining_thickness_under_grooves_mm':P['rear_thickness']-style['rear_grip_depth'],
    'mating_outer_outlines_match':True, 'display_and_button_apertures_unchanged':True,
    'same_inner_cavity_preserved':True}
report['power_layout'] = {
    'battery_body_mm':P['battery_dimensions'], 'battery_center_xy_mm':P['battery_center'],
    'battery_pocket_xy_mm':[biw,bih], 'battery_body_z_mm':[batfront,batback],
    'battery_front_extra_space_mm':P['battery_front_keepout_extra'],
    'battery_side_gap_mm':batgap, 'battery_rigid_top_clamp':False,
    'charger_reserved_bay_mm':P['charger_bay_dimensions'], 'charger_module_measured':False,
    'diode_reserved_mm':P['diode_keepout_size'],
    'lcd_exclusion_depth_mm':P['lcd_rear_keepout_depth'], 'lcd_depth_measured':False,
    'switch_reference':pw['reference'], 'switch_aperture_yz_mm':pw['aperture_yz'],
    'switch_mount_pitch_mm':pw['mount_pitch'], 'switch_actual_model_confirmed':False,
    'switch_min_lcd_exclusion_gap_mm':round(pwz-pwwidth/2-P['lcd_rear_keepout_depth'],3),
    'switch_actuator_outside_projection_mm':round(pw['actuator_height']-(103-pwx),3),
    'collisions_in_assumed_envelopes':'none', 'lid_switch_closing_steps_checked':31,
    'power_mount_changes_confined_to_switch_pad_before_styling':True,
    'power_mounts_preserve_existing_lid_before_styling':True,
    'outer_shell_dimensions_mm':[103,150,P['outer_depth']],
    'physical_fit_electrical_safety_thermal_behavior_validated':False}
# Check the full speaker box and straight rear-to-front insertion path, with
# shell/retainer installed and rear lid removed. Wires and gasket are not meshes.
speaker_insertion = box(spx-spw/2,spy-sph/2,spfront,spw,sph,BACK-spfront)
for name, geom in [('front',shell),('retainer',retainer),('rear',lid),('PCB stack',stack),
                   ('dpad',dpad), *caps.items()]:
    assert (speaker_proxy ^ geom).volume() < .0001, ('Speaker collision',name)
    if name != 'rear':
        assert (speaker_insertion ^ geom).volume() < .0001, ('Speaker insertion blocked',name)
assert spy-spoh/2 > by+bh, 'Speaker fence overlaps button PCB in XY'
assert sptop >= spfront+spt and spfront > 3, 'Speaker depth insufficient'
assert grille['pitch'] > grille['width'], 'Grille ribs missing'
assert grille['length'] < spw and grille['pitch']*(grille['count']-1)+grille['width'] < sph
for slot in slots:
    assert (slot ^ shell).volume() < .0001, 'Grille slot is obstructed'
assert (wire_exit ^ shell).volume() < .0001, 'Speaker wire notch blocked'
assert (shell ^ fence).volume() > fence.volume()-.0001, 'Fence not retained in shell'
report['speaker'] = {
    'body_mm': P['speaker_size'], 'center_xy_mm': P['speaker_center'],
    'pocket_xy_mm': [round(spiw,3),round(spih,3)],
    'fence_outer_xy_mm': [round(spow,3),round(spoh,3)],
    'fence_gap_below_pcb_mm': round(spy-spoh/2-(by+bh),3),
    'body_z_mm': [spfront,spfront+spt], 'nominal_front_gasket_mm': round(spfront-3,3),
    'grille': grille, 'wire_exit_width_mm': P['speaker_wire_exit_width'],
    'bounding_box_and_insertion_collisions': 'none', 'outer_dimensions_changed': False,
    'retention': 'rim-only soft adhesive gasket, not printed latch',
    'physical_fit_and_membrane_clearance_verified': False}
for x,y in mounts:
    # A conservative 7 mm diameter, 3 mm high head on the button-side PCB.
    # Its exact size still needs checking, but removed posts cannot hit it.
    head = cylinder(x,y,pcb_z-3,7,3)
    assert (head ^ retainer).volume() < .0001 and (head ^ shell).volume() < .0001
    # Printed bore is straight/continuous from outside through the entire post.
    passage = cylinder(x,y,REAR_PCB_Z-.1,P['rear_board_clearance_diameter']-.05,
                        REAR_STANDOFF+P['rear_thickness']+.2)
    assert (passage ^ lid).volume() < .0001
for x,y in retainer_mounts:
    assert x+3.5 < bx or x-3.5 > bx+bw, 'Retainer mount intrudes on PCB'
for ax, ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    rocked = dpad.translate([-dx,-dy,-5.2]).rotate([ax,ay,0]).translate([dx,dy,5.2])
    assert (shell ^ rocked).volume() < .0001, ('Dpad shell collision',ax,ay)
    assert (retainer ^ rocked).volume() < .0001, ('Dpad pivot collision',ax,ay)
for name in caps:
    for distance in [0, .1, .25, .34]:
        assert (retainer ^ caps[name].translate([0, 0, distance])).volume() < 0.0001, name
    assert (retainer ^ caps[name].translate([0, 0, .4])).volume() > 0, 'Missing cap travel stop'
report['neutral_collisions'] = 'none'
report['single_cap_stop_travel_mm'] = round(stop-4.3, 3)
report['dpad_motion_checked_deg'] = 'cardinal +/-3.2; diagonal +/-3 on each axis'
# Publish only after all geometry checks pass. Reuse filenames, not dated copies.
report['parts'].append(export(shell, 'front-DRAFT'))
report['parts'].append(export(lid, 'rear-DRAFT', rear_print=True))
report['parts'].append(export(retainer, 'button-retainer-DRAFT'))
report['parts'].append(export(dpad, 'dpad-DRAFT'))
report['parts'].append(export(union(list(caps.values())), 'four-caps-DRAFT'))
(OUT/'checks.json').write_text(json.dumps(report, indent=2)+'\n')

# A4, exact 1:1 vector template. No camera distortion, scaling or image editing.
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
       '<rect width="210" height="297" fill="white"/>',
       '<g font-family="Arial,sans-serif" fill="#111">',
       '<text x="15" y="13" font-size="5">ScarletPico — FIT CHECK, NOT FINAL</text>',
       '<text x="15" y="20" font-size="3.3">Print at 100% / Actual size. Disable Fit to page.</text>',
       '<g transform="translate(53.5 30)" stroke="#222" stroke-width=".25" fill="none">',
       '<polygon points="'+' '.join(f'{x:.4f},{y:.4f}' for x,y in exterior_ring())+'"/>',
       f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" stroke="#357"/>',
       f'<rect x="{fx-clear}" y="{fy-clear}" width="{fw+2*clear}" height="{fh+2*clear}"/>',
       f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" stroke="#357"/>']
for name, (x, y) in centers.items():
    svg += [f'<circle cx="{x}" cy="{y}" r="1.5"/>',
            f'<path d="M{x-2.5},{y}h5 M{x},{y-2.5}v5"/>',
            f'<text x="{x+3}" y="{y+1}" stroke="none" fill="#111" font-size="2.6">{name}</text>']
for x, y in mounts:
    svg += [f'<circle cx="{x}" cy="{y}" r="{P["rear_board_clearance_diameter"]/2}" stroke="#b50"/>']
svg += [f'<rect x="{spx-spw/2}" y="{spy-sph/2}" width="{spw}" height="{sph}" stroke="#357" stroke-dasharray="1 1"/>',
        f'<rect x="{spx-spow/2}" y="{spy-spoh/2}" width="{spow}" height="{spoh}" rx="{spwall+.4}" stroke="#357"/>']
svg.append(f'<g transform="rotate({grille["angle_deg"]} {spx} {spy})">')
for y in grille_y:
    svg.append(f'<rect x="{spx-grille["length"]/2}" y="{y-grille["width"]/2}" width="{grille["length"]}" height="{grille["width"]}" rx="{grille["width"]/2}"/>')
svg.append('</g>')
svg += [f'<rect x="{batx-biw/2}" y="{baty-bih/2}" width="{biw}" height="{bih}" rx=".8" stroke="#07848f" stroke-dasharray="1 1"/>',
        f'<rect x="{batx-batw/2}" y="{baty-bath/2}" width="{batw}" height="{bath}" stroke="#07848f"/>',
        f'<text x="{batx-batw/2+3}" y="{baty}" stroke="none" fill="#07848f" font-size="3">BATTERY 50 x 35</text>',
        f'<rect x="{chx-chw/2}" y="{chy-chh/2}" width="{chw}" height="{chh}" stroke="#a66a00" stroke-dasharray="1 1"/>',
        f'<text x="{chx-chw/2+1}" y="{chy}" stroke="none" fill="#a66a00" font-size="2.4">CHARGER BAY</text>',
        f'<rect x="{pw["flange_inner_plane_x"]}" y="{pwy-pwlength/2}" width="{103-pwx}" height="{pwlength}" stroke="#555"/>']
svg += ['</g>', '<text x="15" y="191" font-size="3.5">Verify each crosshair over the actual button centre.</text>',
        '<text x="15" y="197" font-size="3.5">Orange: EXISTING corner holes, 65 x 45 mm pitch. Verify!</text>',
        f'<text x="15" y="202" font-size="3.5">Bottom-right: 30 x 20 speaker, centre X {spx} / Y {spy}.</text>',
        '<text x="15" y="207" font-size="3.5">Button PCB origin: its upper-left corner, front view.</text>']
for i, (name, (x, y)) in enumerate(P['button_centers_on_pcb'].items()):
    col, row = divmod(i, 4)
    svg.append(f'<text x="{15+col*96}" y="{214+row*6}" font-size="3.4">{name}: X {x:.1f} / Y {y:.1f} mm</text>')
svg += ['<path d="M15 250h50 M15 247v6 M65 247v6" fill="none" stroke="#111" stroke-width=".35"/>',
        '<text x="15" y="259" font-size="4">This line must measure exactly 50 mm.</text>',
        '<text x="15" y="267" font-size="3">Cyan / amber: REAR-mounted power parts shown in FRONT projection.</text>',
        '<text x="15" y="273" font-size="3">Right-side switch: 12 x 5.2 aperture; two 2.3 mm holes, pitch 19.</text>',
        '<text x="15" y="279" font-size="3">Switch centre: 23 mm from top, 22.5 mm behind outside front face.</text>',
        '<text x="15" y="285" font-size="3">Battery position uses full envelope including seams. Verify before printing.</text>', '</g></svg>']
(OUT/'button-layout-1to1.svg').write_text('\n'.join(svg))

def preview():
    # Orthographic engineering preview rasterized from actual triangles, not AI art.
    image = Image.new('RGB', (2100, 1050), '#f1f2f4')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 27)
    small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 20)
    draw.text((35, 23), 'ScarletPico / softened retro shell, diagonal speaker grille', fill='#18212c', font=font)
    draw.text((35, 66), 'Still 103 x 150 x 30 mm / internal seats unchanged / speaker pocket moved 24 mm right, same size and depth', fill='#5d6069', font=small)
    def panel(items, center, scale, inside=False, side=False):
        angle = math.radians(25)
        if side:
            basis = np.array([[0,1,0],[0,0,1],[1,0,0]])
        elif inside:
            basis = np.array([[math.cos(angle), .4*math.sin(angle), .4*math.sin(angle)],
                              [0, .80, -.7],[-.4, .6, .75]])
        else:
            basis = np.array([[.93, -.14, .35], [.06, .84, .55], [-.30, -.51, -.8]])
        # Per-pixel depth prevents painter-sort artifacts on large front faces.
        depth = np.full((image.height, image.width), -np.inf)
        pixels = np.array(image)
        for geom, color in items:
            mesh = mesh_of(geom)
            vv = mesh.vertices - np.array([51.5, 75, 0])
            projected = vv @ basis.T
            for face, norm in zip(mesh.faces, mesh.face_normals):
                pts = projected[face]
                shade = .65 + .3*abs(float(norm @ np.array([.25, -.4, .88])))
                rgb = tuple(int(min(255, c*shade)) for c in color)
                screen = pts[:,:2]*scale + np.asarray(center)
                lo = np.maximum(np.floor(screen.min(axis=0)).astype(int), [0,0])
                hi = np.minimum(np.ceil(screen.max(axis=0)).astype(int), [image.width-1,image.height-1])
                if np.any(hi < lo):
                    continue
                a,b,c = screen
                den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(den) < 1e-9:
                    continue
                yy,xx = np.mgrid[lo[1]:hi[1]+1, lo[0]:hi[0]+1]
                wa = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
                wb = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
                wc = 1-wa-wb
                zz = wa*pts[0,2]+wb*pts[1,2]+wc*pts[2,2]
                ds = depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                mask = (wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>ds)
                ds[mask] = zz[mask]
                pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask] = rgb
        image.paste(Image.fromarray(pixels))
    # Dark rectangle is a visual placeholder for the supplied black LCD frame,
    # not a new printed part or a claim about the active display area.
    screen_placeholder=box(fx,fy,.5,fw,fh,.7)
    panel([(shell, (195, 35, 63)), (dpad, (56, 59, 70)),
           (screen_placeholder,(32,39,43)),
           *[(c, (56,59,70)) for c in caps.values()]], (340, 435), 4.0)
    rear_outside=lid.rotate([0,180,0]).translate([103,0,30])
    panel([(rear_outside,(195,35,63))],(1040,435),3.8)
    # Inside lid, with explicitly schematic battery/module envelopes. Labels use
    # the front-view coordinate system to avoid a silent mirrored mounting plan.
    panel([(lid.translate([0,0,-BACK]), (195,35,63)),
           (battery_proxy.translate([0,0,-BACK]),(108,202,216)),
           (charger_proxy.translate([0,0,-BACK]),(227,176,76)),
           (diode_keepout.translate([0,0,-BACK]),(157,163,173))], (1740,435), 3.8)
    draw.text((100, 790), 'FRONT / shallow diagonal speaker bevel', fill='#18212c', font=small)
    draw.text((100, 825), 'Dark screen is a visual placeholder, not an STL part.', fill='#5d6069', font=small)
    draw.text((790, 790), 'REAR / five blind decorative grip grooves', fill='#18212c', font=small)
    draw.text((790, 825), '0.35 mm deep; 1.65 mm lid material remains.', fill='#5d6069', font=small)
    draw.text((1490, 790), 'INSIDE / battery and charger seats unchanged', fill='#18212c', font=small)
    draw.text((1490, 825), 'Component blocks are illustrative envelopes.', fill='#5d6069', font=small)
    draw.text((35, 895), 'Corners R7.5 / lower-right R10. Front and back edge rolls R1.2. No exterior growth or smaller internal cavity.', fill='#18212c', font=font)
    draw.text((35, 944), 'Speaker stays flat inside: only the outer face is beveled. Button mechanism, mounts and switch opening remain unchanged.', fill='#5d6069', font=small)
    draw.text((35, 982), 'FIT-CHECK DRAFT: actual LCD depth, TP4056, fasteners, battery leads and printed fit still require physical verification.', fill='#5d6069', font=small)
    image.save(OUT/'preview.png')

preview()
print(json.dumps(report, indent=2))
