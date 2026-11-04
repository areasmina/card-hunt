"""Card Hunt badge in Blender: a hand bursts through a torn hole in the badge and reaches for the card.
bpy (Blender 5.2) headless, Cycles CPU.  python hunt.py <out_dir> [frames|still] [res]
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Quaternion, Matrix

OUT = sys.argv[1]; MODE = sys.argv[2] if len(sys.argv) > 2 else 'still'; RES = int(sys.argv[3]) if len(sys.argv) > 3 else 256
HERE = os.path.dirname(os.path.abspath(__file__))
N = 72
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = RES; sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'


def mat(name, rgb, rough=.8, sss=0.0, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss; b.inputs['Subsurface Radius'].default_value = (1, .4, .25)
        b.inputs['Subsurface Scale'].default_value = .08
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = 1
    return m


def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)


M_FACE = mat('face', srgb('#2f3536'), .9)
_nt = M_FACE.node_tree; _tc = _nt.nodes.new('ShaderNodeTexCoord'); _mp = _nt.nodes.new('ShaderNodeMapping'); _mp.inputs['Scale'].default_value = (.22, .22, .22)
_ti = _nt.nodes.new('ShaderNodeTexImage'); _ti.image = bpy.data.images.load(os.path.join(HERE, 'frame-tutor.jpg'))
_nt.links.new(_tc.outputs['Object'], _mp.inputs['Vector']); _nt.links.new(_mp.outputs['Vector'], _ti.inputs['Vector'])
_mx = _nt.nodes.new('ShaderNodeMix'); _mx.data_type = 'RGBA'; _mx.inputs['Factor'].default_value = .3
_mx.inputs['A'].default_value = (*srgb('#2b3031'), 1); _nt.links.new(_ti.outputs['Color'], _mx.inputs['B'])
_nt.links.new(_mx.outputs['Result'], _nt.nodes['Principled BSDF'].inputs['Base Color'])   # the beaded black-card frame on the badge face
M_TORN = mat('torn', srgb('#59605f'), .95)
M_CORE = mat('core', srgb('#cdb48f'), .95)
M_RIM = mat('rim', srgb('#b59a6e'), .6)
M_RIM2 = mat('rim2', srgb('#3a3326'), .7)
M_VOID = mat('void', (0, 0, 0), 1)
M_SKIN = mat('skin', srgb('#d9a383'), .55, sss=.25)
M_EDGE = mat('cardedge', srgb('#1c1a16'), .6)

# ---------------- badge: rim ring + face with a torn hole pushed out toward the camera ----------------
R = 3.2
bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=.22, major_segments=96, minor_segments=16, location=(0, 0, 0))
rim = bpy.context.object; rim.data.materials.append(M_RIM)
bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_cylinder_add(radius=R + .05, depth=.2, vertices=96, location=(0, 0, -.25))
back = bpy.context.object; back.data.materials.append(M_RIM2)

HC = Vector((.85, .85))        # hole centre: up and right, half behind the card
HR = 1.3
bm = bmesh.new()
outer = [bm.verts.new((R * math.cos(a), R * math.sin(a), 0)) for a in [i / 96 * 2 * math.pi for i in range(96)]]
K = 16
mid, inner = [], []
for i in range(K):
    a = i / K * 2 * math.pi
    r_mid = HR * (1.05 + .08 * random.random())
    tip = i % 2 == 0
    r_in = HR * ((.55 + .25 * random.random()) if tip else (.85 + .1 * random.random()))
    mid.append(bm.verts.new((HC.x + r_mid * math.cos(a), HC.y + r_mid * math.sin(a), .02)))
    # torn flaps: pushed toward the camera and outward, like paper burst from behind
    push = (.55 + .35 * random.random()) if tip else .2
    rr = r_in + (.25 if tip else .05)
    inner.append(bm.verts.new((HC.x + rr * math.cos(a), HC.y + rr * math.sin(a), push)))
bm.verts.ensure_lookup_table()
# face between outer circle and mid ring: fan through nearest-angle stitching
def ang(v, c):
    return math.atan2(v.co.y - c[1], v.co.x - c[0]) % (2 * math.pi)
faces_face = []
oi = 0
for i in range(K):
    j = (i + 1) % K
    a0, a1 = i / K * 2 * math.pi, (i + 1) / K * 2 * math.pi
    # outer verts whose angle (around hole centre) falls in [a0, a1)
    seg = [v for v in outer if a0 <= ang(v, HC) < a1 or (j == 0 and ang(v, HC) >= a0)]
    seg.sort(key=lambda v: ang(v, HC))
    faces_face.append(bm.faces.new([mid[i], mid[j]] + ([] if not seg else []) ))  if False else None
bm.free()

# simpler + robust: build the face as a grid disc, then carve the hole with a boolean, then add flaps separately
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=R, fill_type='NGON', location=(0, 0, 0))
face = bpy.context.object; face.data.materials.append(M_FACE)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=1); bpy.ops.object.mode_set(mode='OBJECT')
# hole cutter: jagged prism
bm = bmesh.new()
pts = []
for i in range(K):
    a = i / K * 2 * math.pi
    r = HR * (.82 + .34 * random.random())
    pts.append((HC.x + r * math.cos(a), HC.y + r * math.sin(a)))
bot = [bm.verts.new((x, y, -1)) for x, y in pts]; top = [bm.verts.new((x, y, 1)) for x, y in pts]
bm.faces.new(bot[::-1]); bm.faces.new(top)
for i in range(K):
    j = (i + 1) % K; bm.faces.new([bot[i], bot[j], top[j], top[i]])
me = bpy.data.meshes.new('cut'); bm.to_mesh(me); bm.free()
cut = bpy.data.objects.new('cut', me); sc.collection.objects.link(cut)
bpy.context.view_layer.objects.active = face
md = face.modifiers.new('hole', 'BOOLEAN'); md.object = cut; md.operation = 'DIFFERENCE'; md.solver = 'EXACT'
bpy.ops.object.modifier_apply(modifier='hole'); cut.hide_render = True; cut.hide_viewport = True
sol = face.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = .06

# flaps: one triangle-ish shard per edge segment, hinged on the hole edge, bent outward toward the camera
bm = bmesh.new()
for i in range(K):
    j = (i + 1) % K
    (x0, y0), (x1, y1) = pts[i], pts[j]
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    d = Vector((mx - HC.x, my - HC.y)).normalized()
    if random.random() < .3: continue
    L = .12 + .6 * random.random() ** 1.5
    # torn paper pushed out from behind: a broad flap bent outward and toward the camera, a little twisted
    tw = random.uniform(-.12, .12); sh = .55 + .25 * random.random()
    o0 = (x0 + d.x * L * .5 + (mx - x0) * (1 - sh) + tw, y0 + d.y * L * .5 + (my - y0) * (1 - sh) - tw, L * .8)
    o1 = (x1 + d.x * L * .5 + (mx - x1) * (1 - sh) + tw, y1 + d.y * L * .5 + (my - y1) * (1 - sh) - tw, L * (.6 + .4 * random.random()))
    vs = [bm.verts.new((x0, y0, .03)), bm.verts.new((x1, y1, .03)), bm.verts.new(o1), bm.verts.new(o0)]
    bm.faces.new(vs)
me = bpy.data.meshes.new('flaps'); bm.to_mesh(me); bm.free()
flaps = bpy.data.objects.new('flaps', me); sc.collection.objects.link(flaps); flaps.data.materials.append(M_TORN); flaps.data.materials.append(M_CORE)
fs = flaps.modifiers.new('t', 'SOLIDIFY'); fs.thickness = .04; fs.material_offset_rim = 1   # torn edges show the light paper core
# the void behind the hole
bpy.ops.mesh.primitive_cylinder_add(radius=HR * 1.25, depth=6, vertices=48, location=(HC.x, HC.y, -3.05))
tun = bpy.context.object; tun.data.materials.append(M_VOID)

# ---------------- card ----------------
img = bpy.data.images.load(os.path.join(HERE, 'cardface.png'))
CW, CH = 2.25, 2.25 * 748 / 512
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
cardf = bpy.context.object; cardf.scale = (CW, CH, 1)
mf = bpy.data.materials.new('cardface'); mf.use_nodes = True
nt = mf.node_tree; bsdf = nt.nodes['Principled BSDF']; tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img; tx.interpolation = 'Closest'
nt.links.new(tx.outputs['Color'], bsdf.inputs['Base Color']); bsdf.inputs['Roughness'].default_value = .45
bsdf.inputs['Emission Color'].default_value = (1, 1, 1, 1); nt.links.new(tx.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = .25
cardf.data.materials.append(mf)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -.026))
cardb = bpy.context.object; cardb.scale = (CW * 1.0, CH * 1.0, .05); cardb.data.materials.append(M_EDGE)
card = bpy.data.objects.new('card', None); sc.collection.objects.link(card)
cardf.parent = card; cardb.parent = card

# ---------------- hand: a skin-modifier skeleton (wrist, palm, knuckles, finger joints) + a rounded palm slab ----------------
hand = bpy.data.objects.new('hand', bpy.data.meshes.new('hand0')); sc.collection.objects.link(hand)
hand.data.materials.append(M_SKIN)
sk = hand.modifiers.new('skin', 'SKIN'); sk.use_smooth_shade = True; ss = hand.modifiers.new('sub', 'SUBSURF'); ss.levels = ss.render_levels = 2
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, .95, 0))
palm = bpy.context.object; palm.scale = (1.55, 1.45, .5); palm.parent = hand; palm.data.materials.append(M_SKIN)
bv = palm.modifiers.new('bv', 'BEVEL'); bv.width = .22; bv.segments = 3
ps = palm.modifiers.new('sub', 'SUBSURF'); ps.levels = ps.render_levels = 2
bpy.context.view_layer.objects.active = palm; bpy.ops.object.shade_smooth()


def build_hand(curl, spread):
    """local space: wrist at origin, fingers toward +y, palm facing +z. curl 0 = open claw, 1 = gripping."""
    V, E, RAD = [], [], []
    def v(p, r):
        V.append(tuple(p)); RAD.append(r); return len(V) - 1
    w = v((0, .15, -.05), (.55, .32))
    # forearm back into the hole
    a1 = v((0, -1.2, -1.0), (.5, .45)); E.append((w, a1))
    a2 = v((0, -2.6, -2.6), (.55, .5)); E.append((a1, a2))
    pc = v((0, .95, 0), (.7, .25)); E.append((w, pc))
    fingers = [(-.6, 1.62, -.26, .62, .42, .34, .17), (-.2, 1.72, -.08, .72, .48, .38, .19), (.2, 1.70, .08, .68, .46, .36, .185), (.58, 1.58, .26, .54, .36, .3, .155)]
    for (x, y, ang0, l1, l2, l3, r) in fingers:
        a = ang0 * (.5 + 1.0 * spread)
        dirv = Vector((math.sin(a), math.cos(a), 0)); axis = Vector((dirv.y, -dirv.x, 0))
        p = Vector((x, y, 0)); kn = v(p, (r * 1.15, r)); E.append((pc, kn))
        cur = dirv.copy(); prev = kn
        bends = [.25 + .5 * curl, .45 + .8 * curl, .35 + .6 * curl]
        for seg, (ln, bnd) in enumerate(zip((l1, l2, l3), bends)):
            cur = Quaternion(axis, -bnd) @ cur
            p = p + cur * ln
            rr = r * (1 - .1 * (seg + 1)); n = v(p, (rr, rr)); E.append((prev, n)); prev = n
    # thumb: from the base of the palm, out to the side and forward
    t0 = Vector((.62, .45, .12)); tb = v(t0, (.26, .24)); E.append((w, tb))
    td = Vector((.8, .5, .3)).normalized(); prev = tb; p = t0
    for seg, (ln, bnd) in enumerate(zip((.5, .4, .32), (.05, .25 + .5 * curl, .3 + .5 * curl))):
        td = Quaternion(Vector((.2, -.5, 1)).normalized(), bnd) @ td
        p = p + td * ln; n = v(p, (.22 - .025 * seg, .2 - .025 * seg)); E.append((prev, n)); prev = n
    old = hand.data
    me = bpy.data.meshes.new('hand'); me.from_pydata(V, E, []); me.update()
    hand.data = me; me.materials.append(M_SKIN)
    if not me.skin_vertices:
        with bpy.context.temp_override(object=hand, active_object=hand): bpy.ops.mesh.customdata_skin_add()
    sv = me.skin_vertices[0].data
    for i, r in enumerate(RAD): sv[i].radius = r
    sv[a2].use_root = True
    if old.users == 0: bpy.data.meshes.remove(old)


# ---------------- camera + light ----------------
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -2.2, 13.5); cam.rotation_euler = (math.radians(9), 0, 0); cam.data.lens = 70
k = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA')); sc.collection.objects.link(k)
k.data.energy = 1150; k.data.size = 4; k.location = (-5, 5, 9); k.rotation_euler = Vector((5, -5, -9)).to_track_quat('-Z', 'Y').to_euler()
f = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'AREA')); sc.collection.objects.link(f)
f.data.energy = 220; f.data.size = 6; f.location = (6, -3, 8); f.rotation_euler = Vector((-6, 3, -8)).to_track_quat('-Z', 'Y').to_euler()
rimL = bpy.data.objects.new('rimL', bpy.data.lights.new('rimL', 'POINT')); sc.collection.objects.link(rimL)
rimL.data.energy = 60; rimL.data.color = (1, .55, .3); rimL.location = (HC.x, HC.y, -.8)      # warm glow from inside the hole
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Strength'].default_value = .15


def smooth(x):
    x = min(max(x, 0), 1); return x * x * (3 - 2 * x)


def pose(i):
    t = i / N
    # timeline: rest -> the hand bursts out and reaches -> grabs the card's top -> tugs -> lets go and sinks back
    if t < .12:   k = 0
    elif t < .42: k = smooth((t - .12) / .30)
    elif t < .66: k = 1
    elif t < .86: k = 1 - smooth((t - .66) / .20)
    else:         k = 0
    grip = smooth((t - .44) / .08) * (1 - smooth((t - .60) / .06))
    tug = grip
    # card floats in front of the hole, swaying in 3D; tugged up and back toward the hand while gripped
    card.location = (-.2 + .12 * tug, -.45 + .1 * math.sin(t * 4 * math.pi) + .25 * tug, 1.4 - .3 * tug)
    card.rotation_euler = (math.radians(-6 + 5 * math.sin(t * 2 * math.pi) + 4 * tug), math.radians(14 * math.sin(t * 2 * math.pi) + 6 * tug), math.radians(-4 + 5 * tug))
    build_hand(curl=.1 + .85 * grip, spread=1 - .45 * grip)
    s = .5 + .5 * k
    hand.scale = (s, s, s)
    # from deep inside the hole to just behind the card's top right corner; the fingers curl over its top edge
    hand.location = (HC.x + .3 - .3 * k, HC.y - .7 + .3 * k - .15 * grip, -2.8 + 2.9 * k)
    hand.rotation_euler = (math.radians(-5 + 14 * k + 6 * grip), math.radians(-6 * k), math.radians(12 + 16 * k))
    hand.hide_render = k < .02


if MODE == 'hand':
    for o in list(sc.objects):
        if o.name not in ('hand', 'cam', 'key', 'fill') and o.type != 'LIGHT': o.hide_render = True
    hand.location = (0, 0, 0); hand.scale = (1, 1, 1); hand.rotation_euler = (0, 0, 0)
    cam.location = (0, .6, 9); cam.rotation_euler = (0, 0, 0)
    for j, (c, sp) in enumerate([(.15, 1), (.9, .5)]):
        build_hand(c, sp); sc.render.filepath = os.path.join(OUT, f'hand{j}.png'); bpy.ops.render.render(write_still=True)
        cam.location = (5, .6, 6); cam.rotation_euler = (0, math.radians(40), 0)
        sc.render.filepath = os.path.join(OUT, f'hand{j}s.png'); bpy.ops.render.render(write_still=True)
        cam.location = (0, .6, 9); cam.rotation_euler = (0, 0, 0)
    sys.exit()
frames = range(N) if MODE == 'frames' else [int(N * x) for x in (.25, .4, .52, .75)]
for i in frames:
    pose(i)
    sc.render.filepath = os.path.join(OUT, f'f{i:03d}.png')
    bpy.ops.render.render(write_still=True)
print('done')
