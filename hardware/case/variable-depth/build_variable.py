#!/usr/bin/env python3
"""Separate variable-depth derivative. Never publishes into the baseline folder.

Reuse the existing builder's geometry AND pre-publication tests via its explicit
publication boundary, with an AST replacement of parameters/output path only.
Original source and output files remain byte-identical. This avoids copying the
button mechanism into a second, eventually divergent 700-line implementation.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import numpy as np
import manifold3d as m
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
OUT = ROOT / 'output'
V = json.loads((ROOT / 'parameters.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protected = [BASE/'build_case.py', BASE/'parameters.json', BASE/'README.md',
             *sorted((BASE/'output').glob('*')), *sorted((BASE/'reference').glob('*'))]
before = {str(p.relative_to(BASE)): digest(p) for p in protected if p.is_file()}
P = json.loads((BASE/'parameters.json').read_text())
P['exterior_style']['front_edge_radius'] = V['front_edge_radius']
if V.get('speaker_face_flat', False):
    # Disable ONLY the external diagonal speaker cut in the reused builder.
    # Its cutter now ends at Z=0, outside the solid; grille, seat and edge roll
    # remain unchanged. Keep the historical baseline source/output untouched.
    P['exterior_style']['speaker_slope_gradient'] = 0
    P['exterior_style']['speaker_slope_max_depth'] = 0
P['battery_center'] = V['battery_center']
P['charger_bay_dimensions'] = V['charger_bay_dimensions']
P['charger_bay_center'] = V['charger_bay_center']
P['power_switch']['center_yz'] = V['switch_center_yz']
P['diode_keepout_origin'] = V['diode_keepout_origin']
P['diode_keepout_size'] = V['diode_keepout_size']
P['lcd_rear_keepout_depth'] = V['display_measured_thickness'] + V['display_front_recess_allowance']

source = (BASE/'build_case.py').read_text()
assert digest(BASE/'build_case.py') == 'ee82d3f2d28047a88e2dc4ecb6f374a7ffad490536aa7d5c3a0eb0b467eea594', \
    'Baseline builder changed: review variant adapter before rebuilding'
assert digest(BASE/'parameters.json') == '0c057bcc10b97d0ac5a8a7e66d6703b322f7dfede55d01f2102d3046a674abc5', \
    'Baseline dimensions changed: review variant fit before rebuilding'
marker = '# Publish only after all geometry checks pass.'
assert source.count(marker) == 1, 'Baseline publication boundary changed: review adapter'
tree = ast.parse(source.split(marker)[0], filename=str(BASE/'build_case.py'))
replaced = set()
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        name = node.targets[0].id
        if name in ('P', 'OUT'):
            node.value = ast.Name(id='_variant_' + name, ctx=ast.Load())
            replaced.add(name)
assert replaced == {'P', 'OUT'}
OUT.mkdir(parents=True, exist_ok=True)
ns = {'__file__': str(BASE/'build_case.py'), '_variant_P': P, '_variant_OUT': OUT}
exec(compile(ast.fix_missing_locations(tree), str(BASE/'build_case.py'), 'exec'), ns)

box, cylinder, union = (ns[k] for k in ('box', 'cylinder', 'union'))
mesh_of, solid, pill = (ns[k] for k in ('mesh_of', 'solid', 'pill'))
WIDTH, HEIGHT = P['outer_width'], P['outer_height']
UPPER, LOWER = V['upper_depth'], V['lower_depth']
WALL = V['rear_normal_thickness']
BACK = LOWER-WALL
UPPER_BACK = UPPER-WALL
SHIFT = UPPER-LOWER
assert LOWER == P['outer_depth'] and UPPER < LOWER and WALL == P['rear_thickness']


def depth_at(y):
    t = np.clip((np.asarray(y)-V['transition_start_y']) /
                (V['transition_end_y']-V['transition_start_y']), 0, 1)
    return UPPER+(LOWER-UPPER)*(3*t*t-2*t*t*t)


def yz_solid(section):
    # CrossSection is (Y,Z); extrusion axis becomes X (positive permutation).
    return section.extrude(WIDTH+2).transform([[0,0,1,-1],[1,0,0,0],[0,1,0,0]])


# The inner back is a TRUE 2 mm inward offset in YZ, not simply Z minus 2:
# that would leave only ~1.56 mm normal thickness on the steepest slope.
profile_y = np.unique(np.r_[[-40,0,V['transition_start_y']],
                           np.linspace(V['transition_start_y'], V['transition_end_y'], 241),
                           [HEIGHT, HEIGHT+40]])
top_curve = np.column_stack([profile_y, depth_at(profile_y)])
outer_profile = m.CrossSection([np.vstack([[[-40,-10],[HEIGHT+40,-10]],top_curve[::-1]])])
inner_profile = outer_profile.offset(-WALL, circular_segments=128)
outer_below, inner_below = yz_solid(outer_profile), yz_solid(inner_profile)


def rounded_envelope():
    """Circular front edge and rear edge roll following the variable back."""
    rf, rr = V['front_edge_radius'], P['exterior_style']['rear_edge_radius']
    def ring(inset):
        xy=ns['exterior_ring'](inset)
        # Subdivide the long straight sides at EVERY taper sample. Otherwise
        # a mesh edge would interpolate one long ramp between corner vertices.
        ys=np.linspace(V['transition_start_y'],V['transition_end_y'],241)
        right=np.column_stack([np.full(len(ys),WIDTH-inset),ys])
        left=np.column_stack([np.full(len(ys),inset),ys[::-1]])
        return np.vstack([xy[:50],right,xy[50:],left])
    rings = []
    for a in np.linspace(0,math.pi/2,17):
        xy = ring(rf-rf*math.sin(a))
        rings.append(np.column_stack([xy,np.full(len(xy),rf-rf*math.cos(a))]))
    for a in np.linspace(0,math.pi/2,17):
        xy = ring(rr-rr*math.cos(a))
        rings.append(np.column_stack([xy,depth_at(xy[:,1])-rr+rr*math.sin(a)]))
    verts = np.vstack(rings).tolist()
    faces = []
    n = len(rings[0])
    for k in range(len(rings)-1):
        for j in range(n):
            a=k*n+j; b=k*n+(j+1)%n; c=b+n; d=a+n
            faces.extend([[a,b,c],[a,c,d]])
    lo=len(verts); verts.append([WIDTH/2,HEIGHT/2,0])
    # Rear is not planar: an interior fan would be wrong over the taper.
    # Close it ABOVE the curved surface; intersect with outer_below afterwards.
    top_start=len(verts)
    xy=ring(rr)
    verts.extend(np.column_stack([xy,np.full(n,LOWER+1)]).tolist())
    last=(len(rings)-1)*n
    for j in range(n):
        a=last+j; b=last+(j+1)%n; c=top_start+(j+1)%n; d=top_start+j
        faces.extend([[a,b,c],[a,c,d],[lo,(j+1)%n,j]])
    hi=len(verts); verts.append([WIDTH/2,HEIGHT/2,LOWER+1])
    for j in range(n):
        faces.append([hi,top_start+j,top_start+(j+1)%n])
    return solid(trimesh.Trimesh(vertices=verts, faces=faces, process=False))


envelope = rounded_envelope()
shell = ns['shell'] ^ inner_below ^ envelope
# The original upper closure pilots started at Z22 and disappeared in the cut.
# Recut them at exactly the same XY, into the now-shorter bosses.
for x,y in ns['lid_mounts']:
    z = UPPER_BACK if y < V['transition_start_y'] else BACK
    shell = shell-cylinder(x,y,z-6,P['fastener_pilot_diameter'],6.2)

lid_skin = (outer_below-inner_below) ^ ns['outer_area'].extrude(LOWER+1) ^ envelope
lid = lid_skin
for x,y in ns['lid_mounts']:
    z = UPPER_BACK if y < V['transition_start_y'] else BACK
    lid = lid-cylinder(x,y,z-.1,P['fastener_clearance_diameter'],WALL+.2)
for support in ns['rear_supports']:
    lid = lid+support
# Reopen support bores through the new skin, not just through their posts.
for x,y in ns['mounts']:
    lid = lid-cylinder(x,y,ns['REAR_PCB_Z']-.1,P['rear_board_clearance_diameter'],LOWER)
battery_rail = ns['battery_rail'].translate([0,0,SHIFT])
charger_rail = ns['charger_rail'].translate([0,0,SHIFT])
lid = lid+battery_rail+charger_rail
for cut in ns['grip_cuts']:
    lid = lid-cut

battery = ns['battery_proxy'].translate([0,0,SHIFT])
battery_space = ns['battery_front_space'].translate([0,0,SHIFT])
charger_bay = ns['charger_keepout'].translate([0,0,SHIFT])
cw,ch,ct = V['charger_measured_dimensions']
cx,cy = V['charger_bay_center']
charger = box(cx-cw/2,cy-ch/2,UPPER_BACK-V['charger_rear_insulation_allowance']-ct,cw,ch,ct)
diode = ns['diode_keepout']
switch = ns['switch_proxy']
lcd = ns['lcd_keepout']
retainer, dpad, caps = (ns[k] for k in ('retainer','dpad','caps'))


def disjoint(a,b,label):
    volume = (a ^ b).volume()
    assert volume < .0001, (label,volume)


def same(a,b,label):
    disjoint(a-b,a,label+' removed')
    disjoint(b-a,b,label+' added')


def valid(s,name,components=1):
    assert s.status() == m.Error.NoError, (name,s.status())
    mesh = mesh_of(s)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0, name
    assert len(s.decompose()) == components, (name,'component count',len(s.decompose()))


for name,s in [('front',shell),('rear',lid),('retainer',retainer),('dpad',dpad)]:
    valid(s,name)
valid(union(list(caps.values())), 'caps', 4)
speaker_plane_checks = 0
if V.get('speaker_face_flat', False):
    # Inspect downward-facing triangles over the speaker, safely inside the
    # R2.4 perimeter roll. At least one triangle used to lie on the bevel here.
    front_mesh = mesh_of(shell)
    triangles = front_mesh.triangles
    region = np.all((triangles[:, :, 0] >= 56) & (triangles[:, :, 0] <= 98) &
                    (triangles[:, :, 1] >= 122) & (triangles[:, :, 1] <= 146), axis=1)
    facing = front_mesh.face_normals[:, 2] < -.9
    near_front = np.max(triangles[:, :, 2], axis=1) < 1
    speaker_faces = triangles[region & facing & near_front]
    assert len(speaker_faces), 'No speaker front surface was checked'
    assert np.max(np.abs(speaker_faces[:, :, 2])) < .0001, 'Speaker face is not flat at Z=0'
    speaker_plane_checks = len(speaker_faces)
for name,part in [('button-retainer-DRAFT',retainer),('dpad-DRAFT',dpad),
                  ('four-caps-DRAFT',union(list(caps.values())))]:
    mesh=mesh_of(part)
    mesh.apply_translation([0,0,-mesh.bounds[0,2]])
    encoded=mesh.export(file_type='stl')
    assert hashlib.sha256(encoded).hexdigest()==digest(BASE/'output'/(name+'.stl')), \
        ('Shared button mechanism differs from existing STL',name)
disjoint(shell,lid,'front/rear contact')
disjoint(lid,retainer,'rear/retainer')
disjoint(lid,ns['stack'],'rear/PCB stack')
disjoint(shell,ns['stack'],'front/PCB stack')

# Lower housing, internal PCB support surfaces and every front aperture remain
# exactly the same as the parameterized baseline; no scaled buttons or board.
lower_zone = box(-1,V['transition_end_y']+.001,-2,WIDTH+2,HEIGHT,LOWER+4)
same(shell ^ lower_zone, ns['shell'] ^ lower_zone, 'lower front')
same(lid ^ lower_zone, ns['lid'] ^ lower_zone, 'lower rear')
seat = ns['display_seat_region']
same(shell ^ seat, ns['shell'] ^ seat, 'LCD aperture/recess')
for x,y in ns['centers'].values():
    region=box(x-5,y-5,0,10,10,3.3)
    same(shell ^ region,ns['shell'] ^ region,'button aperture')
for support in ns['rear_supports']:
    assert (support-lid).volume()<.0001, 'PCB support shortened'
for name,part in [('dpad',dpad),*caps.items()]:
    disjoint(shell,part,'button neutral '+name)
    disjoint(lid,part,'lid/button '+name)
for ax,ay in [(-3.2,0),(3.2,0),(0,-3.2),(0,3.2),(-3,-3),(-3,3),(3,-3),(3,3)]:
    rocked=dpad.translate([-ns['dx'],-ns['dy'],-5.2]).rotate([ax,ay,0]).translate([ns['dx'],ns['dy'],5.2])
    disjoint(shell,rocked,'rocked dpad')

power=[('battery+front space',battery+battery_space),('charger bay',charger_bay),
       ('diode reserve',diode),('switch+wire reserve',switch)]
for i,(name,part) in enumerate(power):
    for other_name,other in [('front',shell),('rear',lid),('LCD envelope',lcd),
                            ('retainer',retainer),('PCB stack',ns['stack']),('speaker',ns['speaker_proxy']),*power[:i]]:
        disjoint(part,other,name+' / '+other_name)
assert (charger-charger_bay).volume()<.0001, 'TP4056 does not fit bay'
for aperture in [ns['switch_slot'],*ns['switch_bores'],ns['actuator_envelope']]:
    disjoint(aperture,shell,'switch aperture')
for notch in [ns['battery_wire'],ns['charger_wire']]:
    moved=notch.translate([0,0,SHIFT]) ^ box(0,0,0,WIDTH,HEIGHT,UPPER_BACK-.001)
    disjoint(moved,lid,'wire notch')

# Include full assembled module height away from the four known mounting pads.
# This does not pretend to validate actual XY component clearances at the posts.
modules=box(ns['bx'],ns['by'],ns['REAR_PCB_Z'],ns['bw'],ns['bh'],P['rear_module_protrusion'])
for x,y in ns['mounts']:
    modules=modules-cylinder(x,y,0,P['rear_standoff_diameter']+.02,LOWER)
disjoint(modules,lid,'rear module envelope')

for step in np.linspace(0,30,121):
    for name,part in [('lid',lid),('battery',battery+battery_space),('charger bay',charger_bay)]:
        moved=part.translate([0,0,float(step)])
        for other_name,other in [('shell',shell),('switch',switch),('LCD',lcd),('PCB',ns['stack']),
                                ('retainer',retainer),('speaker',ns['speaker_proxy'])]:
            disjoint(moved,other,'closing '+name+' / '+other_name+' at '+str(step))

for x,y in ns['lid_mounts']:
    z=UPPER_BACK if y < V['transition_start_y'] else BACK
    passage=cylinder(x,y,z-.1,P['fastener_clearance_diameter']-.05,WALL+.2)
    disjoint(lid,passage,'closure screw bore')
    bearing=cylinder(x,y,z,5,WALL)-cylinder(x,y,z-.1,P['fastener_clearance_diameter'],WALL+.2)
    assert (bearing-lid).volume()<.0001, 'Closure screw bearing lost'
    pilot=cylinder(x,y,z-5.9,P['fastener_pilot_diameter']-.02,6)
    disjoint(pilot,shell,'closure pilot')
    annulus=cylinder(x,y,z-.4,6.3,.4)-cylinder(x,y,z-.5,2,.6)
    assert (annulus-shell).volume()<.0001, 'Closure boss mating face missing'

# Verify the taper's minimum normal wall thickness numerically against all
# inner-profile segments. Excludes intended outer edge rolls and screw holes.
def point_segment_distances(points, poly):
    a=poly; b=np.roll(poly,-1,axis=0); ab=b-a
    ap=points[:,None,:]-a[None,:,:]
    t=np.clip(np.sum(ap*ab,axis=2)/np.sum(ab*ab,axis=1),0,1)
    delta=ap-t[:,:,None]*ab
    return np.sqrt(np.sum(delta*delta,axis=2)).min(axis=1)

outer_test=np.column_stack([np.linspace(0,HEIGHT,901),depth_at(np.linspace(0,HEIGHT,901))])
inner_polys=inner_profile.to_polygons()
min_wall=min(float(point_segment_distances(outer_test,p).min()) for p in inner_polys)
assert min_wall>1.999, ('rear normal thickness',min_wall)
assert np.allclose(mesh_of(shell).bounds,[[0,0,0],[WIDTH,HEIGHT,BACK]],atol=.01)
assert mesh_of(lid).bounds[1,2] <= LOWER+.001
for y,target in [(20,UPPER),(45,UPPER),(90,LOWER),(135,LOWER)]:
    section=lid ^ box(40,y-.005,0,1,.01,40)
    assert abs(mesh_of(section).bounds[1,2]-target)<.001

# Bracket the shared seam with a 0.005 mm closing displacement. Exact coplanar
# booleans on triangulated curved surfaces can produce zero-volume fragments;
# require one joined wall after this sub-print-resolution overlap, and no
# positive interference at the true assembly position (tested above).
for y in np.linspace(1,149,149):
    # A Y slice at the left straight wall, outside screw/battery mounts.
    slab=box(.01,y-.005,0,.10,.01,35)
    total=(shell+lid.translate([0,0,-.005])) ^ slab
    if not total.is_empty():
        assert len([c for c in total.decompose() if c.volume()>1e-9])==1, ('split outer sidewall at',y)

report={
    'status':'FIT-CHECK DRAFT / physical fit and electrical safety not validated',
    'variant':V, 'base_source_sha256':before['build_case.py'],
    'assembled_plastic_envelope_mm':[WIDTH,HEIGHT,LOWER],
    'upper_lower_depth_mm':[UPPER,LOWER],
    'upper_depth_reduction_mm':-SHIFT,
    'speaker_face_flat':V.get('speaker_face_flat',False),
    'speaker_front_plane_triangles_checked':speaker_plane_checks,
    'speaker_front_bevel_depth_mm':P['exterior_style']['speaker_slope_max_depth'],
    'rear_normal_thickness_min_in_taper_mm':round(min_wall,6),
    'rear_remaining_under_lower_grip_grooves_mm':WALL-P['exterior_style']['rear_grip_depth'],
    'display_rear_reserved_z_mm':P['lcd_rear_keepout_depth'],
    'display_measurement_mm':V['display_measured_thickness'],
    'battery_z_mm':mesh_of(battery).bounds[:,2].round(4).tolist(),
    'battery_to_lcd_reserved_gap_mm':round(mesh_of(battery).bounds[0,2]-P['lcd_rear_keepout_depth'],3),
    'battery_additional_front_space_mm':P['battery_front_keepout_extra'],
    'switch_to_lcd_reserved_gap_mm':round(mesh_of(switch).bounds[0,2]-P['lcd_rear_keepout_depth'],3),
    'switch_to_inner_rear_gap_mm':round(UPPER_BACK-mesh_of(switch).bounds[1,2],3),
    'lower_pcb_support_height_mm':ns['REAR_STANDOFF'],
    'lower_module_to_rear_gap_mm':ns['MODULE_GAP'],
    'lid_closing_positions_checked':121,
    'lower_geometry_and_front_seats_preserved':True,
    'lower_geometry_comparison_note':'Compared with baseline using this variant\'s R2.4 roll and speaker face style; mechanical seats do not change.',
    'mechanism_unchanged':True, 'positive_watertight_connected_meshes':True,
    'caps_in_separate_combined_file':4,
    'notes':['22 mm top assumes full measured LCD thickness including rear connectors; 2 mm front recess additionally reserved.',
             'Switch reference remains unconfirmed; aperture moved 7.5 mm toward front.',
             'Battery and charger retain low locating rails, require removable retention and underside insulation.',
             'The curved rear lid is not bed-flat: slicer support/orientation required.',
             'LCD retention, charge/USB/microSD openings, fasteners and real cable routes remain unfinished.'],
    'parts':[]}

# Publish only after all variant checks; baseline files are never written.
def export_checked(part,name,rear=False):
    mesh=mesh_of(part)
    if rear:
        mesh.vertices[:,1]=HEIGHT-mesh.vertices[:,1]
        mesh.vertices[:,2]*=-1
    mesh.apply_translation([0,0,-mesh.bounds[0,2]])
    # Float32 STL can collapse distinct near-coplanar Boolean vertices into
    # zero-area triangles. Weld on a 0.0001 mm grid, remove ONLY duplicate or
    # degenerate faces, then prove the serialized file is still a manifold.
    # Maximum grid displacement is <0.000087 mm, below 0.1 micrometre.
    old_volume=mesh.volume
    mesh.vertices=np.round(mesh.vertices,4)
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10))
    mesh.remove_unreferenced_vertices()
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
    assert abs(mesh.volume-old_volume)<.1, ('Export cleanup volume change',name)
    dest=OUT/(name+'.stl')
    mesh.export(dest)
    reread=trimesh.load_mesh(dest,process=True)
    assert reread.is_watertight and reread.is_winding_consistent and reread.volume>0, name
    assert reread.nondegenerate_faces().all(), ('Export contains degenerate faces',name)
    valid(solid(reread),name+' reread')
    return {'file':dest.name,'dimensions_mm':reread.extents.round(3).tolist(),
            'watertight':True,'positive_volume':True,'STL_readback_validated':True,
            'degenerate_faces_after_readback':0,'export_weld_grid_mm':.0001,
            'export_volume_delta_mm3':round(float(reread.volume-old_volume),6),
            'print_orientation':'lower outside face down; raised upper back needs supports; review slicer'
                if rear else 'front face down',
            'sha256':digest(dest)}


for name,part,rear in [('front-variable-DRAFT',shell,False),('rear-variable-DRAFT',lid,True)]:
    report['parts'].append(export_checked(part,name,rear))
for name in ['button-retainer-DRAFT','dpad-DRAFT','four-caps-DRAFT']:
    report['parts'].append({'file':'../../output/'+name+'.stl','unchanged_shared_part':True,
                            'sha256':digest(BASE/'output'/(name+'.stl'))})


def render_preview():
    image=Image.new('RGB',(2100,1350),'#f1f2f4')
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',29)
    small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
    tiny=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
    draw=ImageDraw.Draw(image)
    draw.text((40,24),'ScarletPico / variable-depth shell',font=font,fill='#172330')
    draw.text((40,72),'22 mm behind the screen / 30 mm at the controls / same 103 x 150 mm footprint',font=small,fill='#555d67')

    def panel(items,center,scale,basis):
        zbuf=np.full((image.height,image.width),-np.inf)
        pixels=np.array(image)
        for part,color in items:
            mesh=mesh_of(part)
            projected=(mesh.vertices-np.array([51.5,75,0])) @ np.array(basis).T
            for face,normal in zip(mesh.faces,mesh.face_normals):
                pts=projected[face]
                rgb=tuple(int(c*(.64+.34*abs(float(normal @ np.array([.25,-.4,.88]))))) for c in color)
                screen=pts[:,:2]*scale+center
                lo=np.maximum(np.floor(screen.min(axis=0)).astype(int),[0,0])
                hi=np.minimum(np.ceil(screen.max(axis=0)).astype(int),[image.width-1,image.height-1])
                if np.any(hi<lo): continue
                a,b,c=screen
                den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(den)<1e-9: continue
                yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
                wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
                wc=1-wa-wb
                zz=wa*pts[0,2]+wb*pts[1,2]+wc*pts[2,2]
                dest=zbuf[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
                mask=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)&(zz>dest)
                dest[mask]=zz[mask]
                pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=rgb
        image.paste(Image.fromarray(pixels))

    scarlet=(195,35,63); charcoal=(55,60,70)
    basis=[[.93,-.14,.35],[.06,.84,.55],[-.30,-.51,-.8]]
    screen=box(ns['fx'],ns['fy'],.5,ns['fw'],ns['fh'],.7)
    panel([(shell,scarlet),(lid,(168,32,53)),(screen,(30,39,44)),(dpad,charcoal),
           *[(part,charcoal) for part in caps.values()]],(345,425),3.6,basis)
    rear_out=lid.rotate([0,180,0]).translate([WIDTH,0,LOWER])
    front_out=shell.rotate([0,180,0]).translate([WIDTH,0,LOWER])
    panel([(rear_out,scarlet),(front_out,(168,32,53))],(1030,425),3.6,basis)
    panel([(lid.translate([0,0,-UPPER_BACK]),scarlet),
           (battery.translate([0,0,-UPPER_BACK]),(102,202,215)),
           (charger.translate([0,0,-UPPER_BACK]),(229,179,76)),
           (diode.translate([0,0,-UPPER_BACK]),(140,150,160))],(1715,425),3.6,basis)
    draw.text((105,758),'FRONT / flat speaker face, R2.4 edge' if V.get('speaker_face_flat',False)
              else 'FRONT / R2.4 softened edge',font=small,fill='#172330')
    draw.text((790,758),'REAR / thinner top, smooth transition',font=small,fill='#172330')
    draw.text((1475,758),'INSIDE / measured component envelopes',font=small,fill='#172330')
    draw.text((1475,791),'Cyan: cell   Amber: TP4056   Grey: diode reserve',font=tiny,fill='#555d67')

    # Side-view comparison, plotted directly from the numerical CAD profile.
    x0,y0,scale=130,990,10
    coords=[(x0+float(y)*scale,y0+float(z)*scale) for y,z in top_curve if 0<=y<=HEIGHT]
    frontline=[(x0,y0),(x0+HEIGHT*scale,y0)]
    old=[(x0,y0),(x0+HEIGHT*scale,y0),(x0+HEIGHT*scale,y0+LOWER*scale),(x0,y0+LOWER*scale)]
    draw.polygon(old,fill='#d7dbe2')
    draw.polygon(frontline+coords[::-1],fill='#bf2945')
    draw.line([(x0,y0+LOWER*scale),(x0+HEIGHT*scale,y0+LOWER*scale)],fill='#8d97a4',width=2)
    draw.text((40,876),'SIDE PROFILE / screen on the left, button block on the right',font=font,fill='#172330')
    draw.text((40,923),'Grey = previous 30 mm envelope. Red = new shell. This drawing shows the profile, not component installation.',font=small,fill='#555d67')
    for y,z,label in [(20,UPPER,'22 mm'),(112,LOWER,'30 mm')]:
        x=x0+y*scale
        draw.line([(x,y0+8),(x,y0+z*scale-8)],fill='white',width=3)
        draw.line([(x-7,y0+8),(x+7,y0+8)],fill='white',width=3)
        draw.line([(x-7,y0+z*scale-8),(x+7,y0+z*scale-8)],fill='white',width=3)
        draw.text((x+15,y0+z*scale/2-12),label,font=small,fill='white')
    draw.text((1700,1020),'Width: 103 mm',font=small,fill='#172330')
    draw.text((1700,1060),'Height: 150 mm',font=small,fill='#172330')
    draw.text((1700,1100),'Top: 8 mm thinner',font=small,fill='#172330')
    draw.text((1700,1180),'FIT-CHECK DRAFT',font=small,fill='#a1233e')
    draw.text((1700,1215),'Not yet print-approved.',font=tiny,fill='#555d67')
    image.save(OUT/'preview.png')


render_preview()
after={str(p.relative_to(BASE)):digest(p) for p in protected if p.is_file()}
assert before==after, 'Baseline was unexpectedly modified'
report['baseline_files_unchanged']=True
report['baseline_sha256']=before
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('baseline_sha256','variant')},indent=2))
