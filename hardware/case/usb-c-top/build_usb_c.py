#!/usr/bin/env python3
"""USB-C retrofit derivative of the already printed variable-depth case.

Adds a shallow top-wall pocket, connector opening and short fastener slots,
plus a recessed internal bottom-left lanyard anchor. A separate carrier and two
sliding thread blocks make the hole pitch adjustable. Does not overwrite the
parent case.
"""
from pathlib import Path
import hashlib
import json
import math

import manifold3d as m
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import trimesh

ROOT = Path(__file__).resolve().parent
CASE = ROOT.parent
OUT = ROOT / 'output'
P = json.loads((ROOT / 'parameters.json').read_text())
FRONT = CASE / 'variable-depth/output/front-variable-DRAFT.stl'
REAR = CASE / 'variable-depth/output/rear-variable-DRAFT.stl'
PROTECTED = [FRONT, REAR, CASE/'build_case.py', CASE/'parameters.json',
             CASE/'variable-depth/build_variable.py', CASE/'variable-depth/parameters.json',
             *sorted((CASE/'output').glob('*'))]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = {str(p): digest(p) for p in PROTECTED if p.is_file()}
assert digest(FRONT) == '286644c5224bac52551649f89f5e9fd786dcd6e80c6c2a7284b71c41bd7adbc9', \
    'Parent front changed: review USB-C position before rebuilding'
assert digest(REAR) == 'f9e79063791c3d3597dee31123b74a9738d2c49827259f0bf303bf375f52b2eb', \
    'Parent rear changed: review mounting clearances before rebuilding'


def solid(mesh):
    s = m.Manifold(m.Mesh(np.asarray(mesh.vertices, dtype=np.float32),
                          np.asarray(mesh.faces, dtype=np.uint32)))
    assert s.status() == m.Error.NoError
    return s


def mesh_of(s):
    data = s.to_mesh()
    return trimesh.Trimesh(vertices=data.vert_properties[:, :3],
                           faces=data.tri_verts, process=False)


def box(x, y, z, w, d, h):
    return m.Manifold.cube([w, d, h]).translate([x, y, z])


def cylinder_y(x, y, z, diameter, length):
    return m.Manifold.cylinder(length, diameter/2, circular_segments=64) \
        .rotate([-90, 0, 0]).translate([x, y, z])


def union(parts):
    s = parts[0]
    for p in parts[1:]:
        s += p
    return s


def slot_y(x0, x1, y, z, diameter, length):
    return (cylinder_y(x0, y, z, diameter, length) +
            cylinder_y(x1, y, z, diameter, length)).hull()


def no_overlap(a, b, label, tol=.001):
    v = (a ^ b).volume()
    assert v < tol, (label, v)


original = solid(trimesh.load_mesh(FRONT, process=True))
rear_mesh = trimesh.load_mesh(REAR, process=True)
# The rear STL is already turned over for printing, not assembly.
rear_mesh.vertices[:, 1] = 150 - rear_mesh.vertices[:, 1]
rear_mesh.vertices[:, 2] = 30 - rear_mesh.vertices[:, 2]
rear = solid(rear_mesh)

cx, cz = P['port_center_xz']
fw, fh, ft = P['flange_user_measured']
gap, pocket_depth = P['pocket_clearance_per_side'], P['pocket_depth']
wall = P['top_wall_inner_y']
ow, oh = P['connector_through_opening_xz']
min_offset, max_offset = np.array(P['mount_hole_pitch_range']) / 2
hole_d = P['mount_passage_diameter']
recess = box(cx-fw/2-gap, -.01, cz-fh/2-gap, fw+2*gap, pocket_depth+.01, fh+2*gap)
throat = box(cx-ow/2, -.1, cz-oh/2, ow, wall+.2, oh)
passages = [slot_y(cx-max_offset, cx-min_offset, -.1, cz, hole_d, wall+.2),
            slot_y(cx+min_offset, cx+max_offset, -.1, cz, hole_d, wall+.2)]
front = original - recess - throat - union(passages)

cw, cd, ch = P['carrier_size_xyz']
lip = P['carrier_front_lip']
sw, sd, sh = P['slider_size_xyz']
sg = P['slider_sliding_clearance_per_side']
carrier = box(cx-cw/2, wall, cz-ch/2, cw, cd, ch)
carrier = carrier - box(cx-ow/2, wall-.1, cz-oh/2, ow, cd+.2, oh)
for sign in [-1, 1]:
    left = cx-max_offset if sign < 0 else cx+min_offset
    right = cx-min_offset if sign < 0 else cx+max_offset
    # Pockets open at the back; install the blocks before offering the carrier
    # up to the wall. Tightened blocks bear on the carrier's front lip.
    cavity = box(left-sw/2-sg, wall+lip, cz-sh/2-sg,
                 right-left+sw+2*sg, cd-lip+.1, sh+2*sg)
    carrier = carrier - cavity - slot_y(left, right, wall-.1, cz, hole_d, lip+.2)


def slider_at(x):
    y = wall+lip
    block = box(x-sw/2, y, cz-sh/2, sw, sd, sh)
    return block-cylinder_y(x, y-.01, cz, P['slider_pilot_diameter'],
                            P['slider_pilot_depth']+.01)


nominal_offset = (min_offset+max_offset)/2
sliders = [slider_at(cx-nominal_offset), slider_at(cx+nominal_offset)]
flange_proxy = box(cx-fw/2, pocket_depth-ft, cz-fh/2, fw, ft, fh)-throat
for sign in [-1, 1]:
    flange_proxy -= cylinder_y(cx+sign*nominal_offset, -.1, cz, hole_d, ft+.2)
rw, rd, rh = P['connector_body_reserved_xyz']
connector_reserve = box(cx-rw/2, P['connector_reserve_front_y'], cz-rh/2, rw, rd, rh)

# These are measured/reserved component envelopes from the parent variant.
lcd = box(4, 11, 0, 95, 59, 10)
battery = box(16, 17.5, 15.5, 50, 35, 4)
battery_front_space = box(16, 17.5, 13.5, 50, 35, 2)
charger_bay = box(74.5, 37, 16, 22, 17, 4)
diode_bay = box(70, 19, 12, 10, 12, 8)

# Check the mechanism at minimum, nominal and maximum pitch, including physical
# clearance for the screw shank, bottoming and clamping against the front lip.
engagement = P['screw_under_head_length'] - ft - (wall-pocket_depth) - lip
assert 2 <= engagement < P['slider_pilot_depth']-.2, engagement
checked_pitches = []
for offset in np.linspace(min_offset, max_offset, 7):
    for sign in [-1, 1]:
        x = cx+sign*float(offset)
        block = slider_at(x)
        no_overlap(block, carrier, 'slider/frame travel')
        no_overlap(block, front, 'slider/front')
        no_overlap(block, connector_reserve, 'slider/connector reserve')
        shank = cylinder_y(x, pocket_depth, cz,
                           P['screw_nominal_diameter']+.04, wall+lip-pocket_depth+.01)
        no_overlap(shank, front+carrier, 'screw through passages')
        stop_face = box(x-sw/2, wall+lip-.05, cz-sh/2, sw, .04, sh)
        assert (stop_face ^ carrier).volume() > .05, 'missing carrier clamping lip'
    checked_pitches.append(round(2*float(offset), 3))

for label, component in [('LCD', lcd), ('battery', battery+battery_front_space),
                         ('TP4056', charger_bay), ('diode', diode_bay)]:
    for name, part in [('carrier', carrier), ('blocks', union(sliders)),
                       ('connector reserve', connector_reserve)]:
        no_overlap(part, component, name+'/'+label)
for name, part in [('carrier', carrier), ('blocks', union(sliders)), ('flange', flange_proxy)]:
    no_overlap(part, front, name+'/front')
    no_overlap(part, rear, name+'/rear lid')
no_overlap(connector_reserve, front, 'connector/front passage')
no_overlap(front, rear, 'front/rear')
no_overlap(front-original, front, 'unexpected material added')
change_region = box(cx-fw/2-gap-.1, -.1, cz-fh/2-gap-.1,
                    fw+2*gap+.2, wall+.3, fh+2*gap+.2)
assert ((original-front)-change_region).volume() < .001, 'cut outside USB-C patch'
assert np.allclose(mesh_of(front).bounds, mesh_of(original).bounds, atol=.0002)
# The floor remains 2 mm thick away from the throat and screw slots.
floor_sample = box(cx-3, pocket_depth, cz+oh/2+.1, 6, wall-pocket_depth-.02, .5)
assert (floor_sample-front).volume() < .001, 'pocket floor thinned below 2 mm'

# Recessed strap mount is built locally against Y=0, then placed against the
# selected end wall. The bottom-left margin is clear of the buttons/speaker.
# The post and open-backed guard grow directly from the front/end walls.
lug_config = P.get('lanyard_lug')
lug_report = None
if lug_config:
    assert lug_config['type'] == 'internal_corner_tunnel'
    lug_edge = lug_config.get('edge', 'top')
    assert lug_edge in ('top','bottom')
    def place_strap(part):
        return part if lug_edge == 'top' else part.mirror([0,1,0]).translate([0,150,0])
    lx, ly = lug_config['anchor_center_xy']
    radius = lug_config['anchor_diameter']/2
    x0, y0, gw, gd = lug_config['guard_outer_xywh']
    z0, z1 = lug_config['z_range']
    g = lug_config['guard_wall_thickness']
    height = z1-z0
    anchor = m.Manifold.cylinder(height, radius, circular_segments=96).translate([lx,ly,z0])
    guard = union([box(x0,y0,z0,g,gd,height),
                   box(x0+gw-g,y0,z0,g,gd,height),
                   box(x0,y0+gd-g,z0,gw,g,height)])
    lug = place_strap(anchor+guard)
    root_overlap = (lug ^ front).volume()
    assert root_overlap > 15, ('Insufficient internal anchor attachment', root_overlap)
    old_front = front
    front += lug
    hole_chamfer = lug_config['entrance_chamfer']
    hole_radius = lug_config['hole_diameter']/2
    hz = lug_config['entrance_center_z']
    tangent = hole_radius/math.sqrt(2)
    # Local 2D coordinates are (X,-Z); a 45 degree roof above the circular bore
    # avoids a horizontal ceiling when the front panel is printed face down.
    section = (m.CrossSection.circle(hole_radius, circular_segments=96) +
               m.CrossSection([[[-tangent,-tangent], [0,-hole_radius*math.sqrt(2)],
                                 [tangent,-tangent]]]))
    entrances = []
    for x in lug_config['entrance_centers_x']:
        hole = section.extrude(wall+.4).rotate([-90,0,0]).translate([x,-.1,hz])
        wide = section.offset(hole_chamfer, circular_segments=96).extrude(.001).rotate([-90,0,0])
        narrow = section.extrude(.001).rotate([-90,0,0]).translate([0,hole_chamfer,0])
        mouth = (wide+narrow).hull().translate([x,-.001,hz])
        entrances.append(hole+mouth)
    cord_cuts = place_strap(union(entrances))
    front -= cord_cuts
    no_overlap(front, cord_cuts, 'internal strap entrances obstructed')
    strap_region = place_strap(box(x0-.5,-.5,z0-.1,gw+1,gd+1,height+.2))
    assert ((old_front-front)-strap_region).volume() < .001, 'Unexpected strap cut'
    speaker_envelope = box(58.8,123.3,3,33.4,23.4,5)
    button_stack_envelope = box(16.5,73,0,70,50,28)
    for label, component in [('rear',rear),('LCD',lcd),('battery',battery+battery_front_space),
                              ('carrier',carrier),('USB reserve',connector_reserve),
                              ('TP4056',charger_bay),('diode',diode_bay),
                              ('speaker',speaker_envelope),('buttons and PCB',button_stack_envelope)]:
        no_overlap(lug, component, 'lanyard/'+label)
    for px,py in [(5,5),(98,5),(5,143),(98,143)]:
        shaft = m.Manifold.cylinder(30,1.1,circular_segments=64).translate([px,py,0])
        no_overlap(lug,shaft,'lanyard blocks a case fastener')
    # A 2 mm cord has a continuous path behind the rounded post and can be
    # threaded with the rear cover removed. This models clearance, not load.
    cord_y = ly+radius+1.1
    cord_path = box(lug_config['entrance_centers_x'][0]-.1,cord_y-.9,hz-.9,
                    lug_config['entrance_centers_x'][1]-lug_config['entrance_centers_x'][0]+.2,
                    1.8,1.8)
    no_overlap(place_strap(cord_path),front,'cord return path behind post')
    assert np.allclose(mesh_of(front).bounds,mesh_of(original).bounds,atol=.0002), \
        'Internal strap mount protrudes beyond original case envelope'
    lug_report = {'position':lug_edge+'-left margin, two recessed end-wall entrances',
                  'hole_diameter_mm':2*hole_radius,'anchor_diameter_mm':2*radius,
                  'guard_z_range_mm':[z0,z1], 'protrusion_beyond_case_mm':0,
                  'guard_assembly_bounds_mm':mesh_of(lug).bounds.round(3).tolist(),
                  'root_overlap_volume_mm3':round(root_overlap,3),
                  'component_envelopes_clear':True,
                  'case_envelope_unchanged':True,
                  'load_rating_physically_tested':False}


def export_checked(part, name, components=1, along_y=False, pilot_up=False):
    assert part.status() == m.Error.NoError
    assert len(part.decompose()) == components, (name, 'unexpected components')
    mesh = mesh_of(part)
    if along_y:
        # Carrier: front lip on bed, open rear pockets upwards. Slider: its
        # closed rear face on bed, so the blind front pilot opens UPWARDS.
        if pilot_up:
            mesh.vertices = np.column_stack([mesh.vertices[:,0], mesh.vertices[:,2], -mesh.vertices[:,1]])
        else:
            mesh.vertices = np.column_stack([mesh.vertices[:,0], -mesh.vertices[:,2], mesh.vertices[:,1]])
        mesh.apply_translation(-mesh.bounds[0])
    else:
        mesh.apply_translation([0, 0, -mesh.bounds[0, 2]])
    mesh.vertices = np.round(mesh.vertices, 4)
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10))
    mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    path = OUT/(name+'.stl')
    mesh.export(path)
    reread = trimesh.load_mesh(path, process=True)
    assert reread.is_watertight and reread.is_winding_consistent
    assert reread.volume > 0 and reread.nondegenerate_faces().all()
    return {'file': path.name, 'dimensions_mm': reread.extents.round(3).tolist(),
            'watertight': True, 'positive_volume': True, 'sha256': digest(path),
            'print_orientation': ('closed rear face down; blind pilot open upwards' if pilot_up
                else 'front lip down; open rear pockets upwards')
                if along_y else 'front face down; review slicer supports'}


OUT.mkdir(parents=True, exist_ok=True)
parts = [export_checked(front, 'front-top-usbc-DRAFT'),
         export_checked(carrier, 'usb-c-carrier-DRAFT', along_y=True),
         export_checked(slider_at(cx), 'usb-c-slider-PRINT-TWO', along_y=True, pilot_up=True)]
# Small optional wall coupon lets the actual connector/cable and full 6 mm
# fasteners be tried without cutting the already printed console or printing
# another full shell. It reproduces the actual pocket and residual wall.
fit_sample = front ^ box(cx-cw/2, -.001, cz-ch/2, cw, wall+.002, ch)
sample_info = export_checked(fit_sample, 'usb-c-fit-sample-OPTIONAL', along_y=True, pilot_up=True)
sample_info['print_orientation'] = 'flat inner wall side down; outside recess upwards'
parts.append(sample_info)
report = {'status': 'MECHANICAL FIT-CHECK DRAFT; connector dimensions partly provisional',
          'parameters': P, 'flange_outside_face_y': pocket_depth-ft,
          'recess_xz_mm': [fw+2*gap, fh+2*gap],
          'recess_depth_mm': pocket_depth, 'remaining_recess_floor_mm': wall-pocket_depth,
          'case_envelope_unchanged': True,
          'main_case_envelope_unchanged': True,
          'lanyard_lug': lug_report,
          'screw_thread_engagement_mm': round(engagement, 3),
          'screw_tip_to_pilot_bottom_mm': round(P['slider_pilot_depth']-engagement, 3),
          'hole_pitches_checked_mm': checked_pitches,
          'carrier_min_clearance_from_lcd_z_mm': round(cz-ch/2-10, 3),
          'connector_reserve_to_battery_y_mm': round(17.5-(P['connector_reserve_front_y']+rd),3),
          'compatible_rear': '../variable-depth/output/rear-variable-DRAFT.stl',
          'rear_and_button_parts_unchanged': True,
          'parts': parts}


def drilling_template():
    # X horizontal and depth from the front panel down the page. Actual size A4.
    x0, z0 = 22, 25
    def slot_svg(a, b):
        return f'<rect x="{x0+a-hole_d/2:.3f}" y="{z0+cz-hole_d/2:.3f}" width="{b-a+hole_d:.3f}" height="{hole_d}" rx="{hole_d/2}" fill="none" stroke="#b4233d" stroke-width="0.15"/>'
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="148mm" height="105mm" viewBox="0 0 148 105">',
           '<rect width="148" height="105" fill="white"/>',
           '<g font-family="Arial" fill="#182333">',
           '<text x="10" y="10" font-size="4">ScarletPico USB-C / TOP EDGE / 1:1</text>',
           '<text x="10" y="17" font-size="2.8">Print at 100%. Check 20 mm ruler. Depth measured from FRONT face.</text>',
           f'<rect x="{x0}" y="{z0}" width="103" height="22" fill="none" stroke="#333" stroke-width="0.2"/>',
           f'<text x="{x0}" y="{z0-2}" font-size="2.5">FRONT FACE (screen side), Z = 0</text>',
           f'<text x="{x0}" y="{z0+26}" font-size="2.5">REAR COVER side, Z = 22 mm</text>',
           f'<rect x="{x0+cx-fw/2-gap}" y="{z0+cz-fh/2-gap}" width="{fw+2*gap}" height="{fh+2*gap}" fill="none" stroke="#27718b" stroke-width="0.15"/>',
           f'<rect x="{x0+cx-ow/2}" y="{z0+cz-oh/2}" width="{ow}" height="{oh}" fill="none" stroke="#b4233d" stroke-width="0.15"/>',
           slot_svg(cx-max_offset, cx-min_offset), slot_svg(cx+min_offset,cx+max_offset),
           f'<path d="M{x0+cx-2},{z0+cz}h4 M{x0+cx},{z0+cz-2}v4" stroke="#333" stroke-width="0.1"/>',
           '<text x="10" y="63" font-size="2.8">Blue: 20.4 x 6.4 mm recess, 1 mm deep. Red: through cuts.</text>',
           f'<text x="10" y="69" font-size="2.8">Centre: X = {cx} mm, Z = {cz} mm. Slot pitch: 15.5..17 mm.</text>',
           '<text x="10" y="75" font-size="2.8">Connector body/cable clearance and real hole spacing must be checked.</text>',
           '<path d="M10,89h20 M10,87v4 M30,87v4" stroke="black" stroke-width="0.3"/>',
           '<text x="10" y="96" font-size="3">20 mm</text>', '</g></svg>']
    (OUT/'top-edge-template-1to1.svg').write_text('\n'.join(svg))


def render_preview():
    im = Image.new('RGB', (1800, 1180), '#f1f2f5')
    draw = ImageDraw.Draw(im)
    font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
    font = ImageFont.truetype(font_path, 29)
    small = ImageFont.truetype(font_path, 22)
    draw.text((35, 22), 'ScarletPico / top USB-C + recessed bottom lanyard', font=font, fill='#172330')
    draw.text((35, 65), '20 x 6 x 1 mm flange | 1 mm recess | M2 x 6 screws | adjustable 15.5..17 mm pitch', font=small, fill='#465161')

    def panel(items, center, scale, origin, basis, rect):
        pixels = np.array(im)
        zbuf = np.full((im.height, im.width), -np.inf)
        bx0, by0, bx1, by1 = rect
        basis = np.asarray(basis)
        light = np.array([.3,-.8,-.4]); light /= np.linalg.norm(light)
        for part, color in items:
            mesh = mesh_of(part)
            projected = (mesh.vertices-np.asarray(origin)) @ basis.T
            for face, normal in zip(mesh.faces, mesh.face_normals):
                pts = projected[face]
                xy = pts[:,:2]*scale+center
                lo = np.maximum(np.floor(xy.min(axis=0)).astype(int), [bx0,by0])
                hi = np.minimum(np.ceil(xy.max(axis=0)).astype(int), [bx1-1,by1-1])
                if np.any(hi<lo): continue
                a,b,c = xy
                den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(den)<1e-9: continue
                yy,xx = np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                wa = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
                wb = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
                wc = 1-wa-wb
                depth = wa*pts[0,2]+wb*pts[1,2]+wc*pts[2,2]
                dest = zbuf[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                mask = (wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(depth>dest)
                dest[mask] = depth[mask]
                rgb = tuple(int(v*(.62+.36*abs(float(normal@light)))) for v in color)
                pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask] = rgb
        im.paste(Image.fromarray(pixels))

    red=(195,35,63); blue=(53,125,153); amber=(231,172,70); grey=(110,121,137)
    # Focus on the bottom edge, viewed from positive Y.
    basis=[[.98,-.12,0],[.025,.205,1],[-.12,.98,.2]]
    basis=np.array([np.array(row)/np.linalg.norm(row) for row in basis])
    panel([(front,red),(rear,(157,34,58)),(flange_proxy,grey)], (460,260),7.0,
          [51.5,150,15],basis,(25,110,875,405))
    draw=ImageDraw.Draw(im)
    draw.text((40,410), 'BOTTOM LEFT / internal strap anchor, no protrusion', font=small, fill='#172330')
    # Cutaway stops the case 15 mm below its top to expose the internal carrier.
    clip=box(37,-.2,10,29,4.3,10)
    cropped=front ^ clip
    exploded_carrier=carrier.translate([0,5,0])
    exploded_blocks=[p.translate([0,10,0]) for p in sliders]
    panel([(cropped,red),(flange_proxy.translate([0,-3,0]),grey),
           (exploded_carrier,blue),*[(p,amber) for p in exploded_blocks]],
          (1340,280),18,[51.5,3,15],
          [[1,0,0],[0,.7,.7],[0,-.7,.7]],(915,115,1775,650))
    draw=ImageDraw.Draw(im)
    draw.text((940,660), 'EXPLODED / carrier + two sliding thread blocks', font=small, fill='#172330')
    panel([(front,red),(rear,(157,34,58)),(flange_proxy,grey)],
          (460,790),3.0,[51.5,75,10],
          [[.95,.12,.28],[-.05,.92,.39],[-.25,-.39,.88]],(30,465,875,1095))
    draw=ImageDraw.Draw(im)
    draw.text((50,1100), 'Existing variable-depth body and matching rear cover',font=small,fill='#172330')
    # Direct orthographic view is deliberately dimensioned for physical checking.
    x0,y0,sc=1070,820,23
    draw.rounded_rectangle([x0-fw/2*sc,y0-fh/2*sc,x0+fw/2*sc,y0+fh/2*sc],radius=3,
                           fill='#bcc3cb',outline='#344354',width=2)
    draw.rounded_rectangle([x0-ow/2*sc,y0-oh/2*sc,x0+ow/2*sc,y0+oh/2*sc],radius=20,fill='#202a35')
    for sign in [-1,1]:
        x=x0+sign*nominal_offset*sc
        draw.ellipse([x-1.15*sc,y0-1.15*sc,x+1.15*sc,y0+1.15*sc],fill='#f1f2f5',outline='#344354',width=2)
    draw.text((950,920),'Flange: 20 x 6 x 1 mm (user measured)',font=small,fill='#172330')
    draw.text((950,955),'Carrier: 26 x 8.4 mm, depth 4.8 mm',font=small,fill='#172330')
    draw.text((950,990),'Print carrier x1 and slider x2; flat faces down.',font=small,fill='#172330')
    draw.text((950,1030),'Body opening and hole pitch are provisional.',font=small,fill='#8c2940')
    draw.text((950,1065),'Optional small wall sample supplied for a fit check.',font=small,fill='#8c2940')
    draw.text((35,1150),'CAD preview. Grey flange is an envelope, not a verified model of the purchased connector.',font=small,fill='#586271')
    im.save(OUT/'preview.png')


drilling_template()
render_preview()
assert all(digest(Path(path)) == checksum for path,checksum in before.items()), \
    'Parent case or shared mechanism was modified'
(OUT/'checks.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'parts':parts,'screw_engagement_mm':engagement,
                  'protected_parent_files_unchanged':True}, indent=2))
