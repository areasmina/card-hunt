"""Card Hunt, Arabian Nights direction: the monkey card hunter as a 3D scene in Blender.

The monkey (pith hat, brass magnifier, holding up a card) sits on a hoard of gold coins and old
cards beside an oil lamp, with a crescent moon, dunes and a domed city behind. All modelled
here from primitives and metaballs, so it's original art.

blender -b -P scene.py -- art|mascot|both   -> renders/scene-art.png (1500x1200, full scene)
                                               renders/scene-mascot.png (1600x1600, transparent)
"""
import bpy, os, sys, math, random
from mathutils import Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'renders'); os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
WHICH = ARGS[0] if ARGS else 'both'
CARD_FACE = os.path.join(HERE, '..', '..', 'logo-card-dark.png')


def lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def look(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


# ---------------------------------------------------------------- materials
def mat(name, col, rough=0.6, metal=0.0, bump=0.0, bump_scale=40.0, sheen=0.0, var=0.0, var_col=None, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = N['Principled BSDF']
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if 'Sheen Weight' in p.inputs:
        p.inputs['Sheen Weight'].default_value = sheen
    base = lin(col)
    if var:
        # painterly colour variation: big soft noise between two tones
        tc = N.new('ShaderNodeTexCoord')
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 4.0
        nz.inputs['Detail'].default_value = 6
        L.new(tc.outputs['Object'], nz.inputs['Vector'])
        mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
        mix.inputs['Factor'].default_value = var
        L.new(nz.outputs['Fac'], mix.inputs['Factor'])
        mix.inputs[6].default_value = base
        mix.inputs[7].default_value = lin(var_col or col)
        L.new(mix.outputs[2], p.inputs['Base Color'])
    else:
        p.inputs['Base Color'].default_value = base
    if bump:
        tc = N.new('ShaderNodeTexCoord')
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = bump_scale
        nz.inputs['Detail'].default_value = 8
        L.new(tc.outputs['Object'], nz.inputs['Vector'])
        b = N.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump
        L.new(nz.outputs['Fac'], b.inputs['Height']); L.new(b.outputs['Normal'], p.inputs['Normal'])
    if emit:
        p.inputs['Emission Color'].default_value = base
        p.inputs['Emission Strength'].default_value = emit
    return m


def image_mat(name, path):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; p = nt.nodes['Principled BSDF']; p.inputs['Roughness'].default_value = 0.35
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path)
    nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    return m


# ---------------------------------------------------------------- primitives
def prim(kind, name, loc, scale=(1, 1, 1), rot=(0, 0, 0), m=None, **kw):
    getattr(bpy.ops.mesh, 'primitive_' + kind + '_add')(location=loc, rotation=rot, **kw)
    ob = bpy.context.active_object; ob.name = name; ob.scale = scale
    if m:
        ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def capsule(mb, a, b, r):
    a, b = Vector(a), Vector(b)
    e = mb.elements.new(type='CAPSULE')
    e.co = (a + b) / 2; e.radius = r
    e.size_x = (b - a).length / 2
    e.rotation = Vector((1, 0, 0)).rotation_difference((b - a).normalized())
    return e


def ball(mb, c, r, size=None):
    e = mb.elements.new(type='ELLIPSOID' if size else 'BALL')
    e.co = c; e.radius = r
    if size:
        e.size_x, e.size_y, e.size_z = size
    return e


# ---------------------------------------------------------------- the monkey
def monkey():
    fur = mat('Fur', '#6b3f22', rough=0.85, bump=0.35, bump_scale=120, sheen=0.6, var=0.6, var_col='#3e2312')
    skin = mat('Skin', '#d9a57a', rough=0.55, bump=0.08, bump_scale=60, var=0.4, var_col='#b98058')
    dark = mat('Eye', '#0a0806', rough=0.08)

    mb = bpy.data.metaballs.new('Fur'); mb.resolution = 0.03; mb.render_resolution = 0.012
    ball(mb, (0, 0.02, 0.55), 0.5, (0.62, 0.52, 0.7))            # body
    ball(mb, (0, -0.02, 1.13), 0.33)                              # head
    ball(mb, (0, 0.0, 1.27), 0.25)                                # brow/skull
    for s in (-1, 1):
        ball(mb, (s * 0.31, 0.02, 1.14), 0.12)                    # ears
        capsule(mb, (s * 0.17, -0.06, 0.3), (s * 0.3, -0.42, 0.32), 0.12)   # thighs
        capsule(mb, (s * 0.3, -0.42, 0.3), (s * 0.31, -0.48, 0.08), 0.09)   # shins
    capsule(mb, (-0.27, 0.0, 0.82), (-0.43, -0.15, 0.55), 0.085)  # left upper arm
    capsule(mb, (-0.43, -0.15, 0.55), (-0.5, -0.3, 0.38), 0.075)  # left forearm
    capsule(mb, (0.27, 0.0, 0.84), (0.47, -0.08, 1.12), 0.085)    # right upper arm (raised)
    capsule(mb, (0.47, -0.08, 1.12), (0.56, -0.12, 1.42), 0.075)  # right forearm
    for i in range(14):                                           # tail: a curl at the back right
        t = i / 13
        a = math.pi * (0.1 + 1.6 * t)
        r = 0.45 - 0.28 * t
        ball(mb, (0.35 + r * math.cos(a) * 0.9, 0.35 + 0.1 * t, 0.2 + r * math.sin(a)), 0.06 - 0.025 * t)
    fo = link(bpy.data.objects.new('Fur', mb)); fo.data.materials.append(fur)

    sk = bpy.data.metaballs.new('Skin'); sk.resolution = 0.02; sk.render_resolution = 0.008
    ball(sk, (0, -0.25, 1.03), 0.16, (0.95, 0.7, 0.72))           # muzzle
    for s in (-1, 1):
        ball(sk, (s * 0.1, -0.22, 1.18), 0.13, (0.8, 0.6, 0.85))  # eye mask
        ball(sk, (s * 0.31, -0.04, 1.14), 0.065)                  # inner ear
        ball(sk, (s * 0.31, -0.55, 0.06), 0.09, (0.9, 1.3, 0.55)) # feet
    ball(sk, (0, -0.17, 0.52), 0.32, (0.8, 0.45, 1.0))            # belly
    ball(sk, (-0.51, -0.33, 0.36), 0.07)                          # left hand
    ball(sk, (0.57, -0.14, 1.45), 0.07)                           # right hand
    so = link(bpy.data.objects.new('Skin', sk)); so.data.materials.append(skin)

    for s in (-1, 1):
        prim('uv_sphere', 'Eye', (s * 0.095, -0.34, 1.19), (0.042, 0.03, 0.05), m=dark, segments=24, ring_count=12)
        prim('uv_sphere', 'Nostril', (s * 0.03, -0.4, 1.07), (0.012, 0.01, 0.01), m=dark, segments=12, ring_count=6)
        prim('cylinder', 'Brow', (s * 0.1, -0.31, 1.27), (0.07, 0.015, 0.012), (0, 0, s * -0.25),
             m=mat('Brow', '#3e2312', 0.9), vertices=12)
    smile = prim('torus', 'Smile', (0, -0.39, 1.0), (1, 1, 1), (math.radians(80), 0, 0), m=dark,
                 major_radius=0.06, minor_radius=0.008, major_segments=32, minor_segments=8)
    # keep the lower half of the torus only: a smile
    import bmesh
    bm = bmesh.new(); bm.from_mesh(smile.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.01], context='VERTS')
    bm.to_mesh(smile.data); bm.free()

    # pith hat
    khaki = mat('Khaki', '#bba36a', rough=0.8, bump=0.15, bump_scale=200, var=0.5, var_col='#8d7748')
    crown = prim('uv_sphere', 'Crown', (0, -0.03, 1.36), (0.29, 0.31, 0.24), m=khaki, segments=48, ring_count=24)
    bm = bmesh.new(); bm.from_mesh(crown.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.05], context='VERTS')
    bm.to_mesh(crown.data); bm.free()
    prim('cylinder', 'Brim', (0, -0.05, 1.34), (0.46, 0.48, 0.012), (math.radians(-6), 0, 0), m=khaki, vertices=64)
    prim('cylinder', 'Band', (0, -0.03, 1.38), (0.292, 0.312, 0.035), m=mat('Band', '#7a2a1a', 0.7), vertices=64)
    prim('uv_sphere', 'Knob', (0, -0.03, 1.6), (0.035, 0.035, 0.025), m=khaki, segments=16, ring_count=8)

    # brass magnifier in the left hand
    brass = mat('Brass', '#b08a3a', rough=0.28, metal=1.0, bump=0.05, var=0.4, var_col='#6e5222')
    prim('cylinder', 'Handle', (-0.55, -0.36, 0.26), (0.025, 0.025, 0.13), (math.radians(20), math.radians(-25), 0),
         m=mat('Wood', '#3a2010', 0.6), vertices=16)
    prim('torus', 'Rim', (-0.66, -0.42, 0.52), (1, 1, 1), (math.radians(80), 0, math.radians(15)), m=brass,
         major_radius=0.14, minor_radius=0.018, major_segments=48, minor_segments=12)
    glass = bpy.data.materials.new('Glass'); glass.use_nodes = True
    gp = glass.node_tree.nodes['Principled BSDF']
    gp.inputs['Base Color'].default_value = lin('#cfe6e6'); gp.inputs['Roughness'].default_value = 0.05
    gp.inputs['Transmission Weight'].default_value = 0.9; gp.inputs['Alpha'].default_value = 0.35
    try:
        glass.surface_render_method = 'BLENDED'
    except AttributeError:
        pass
    prim('cylinder', 'Lens', (-0.66, -0.42, 0.52), (0.13, 0.13, 0.006), (math.radians(80), 0, math.radians(15)),
         m=glass, vertices=48)

    # the card held up in the right hand, face to the viewer
    card = prim('cube', 'Card', (0.6, -0.2, 1.68), (0.13, 0.003, 0.18), (0, 0, math.radians(-8)),
                m=mat('CardEdge', '#0b0b0b', 0.5))
    if os.path.exists(CARD_FACE):
        face = prim('plane', 'CardFace', (0.6, -0.205, 1.68), (0.125, 0.175, 1),
                    (math.radians(90), 0, math.radians(-8)), m=image_mat('CardFace', CARD_FACE))


# ---------------------------------------------------------------- the hoard and the lamp
def hoard():
    gold = mat('Gold', '#c9a04a', rough=0.3, metal=1.0, bump=0.2, bump_scale=30, var=0.5, var_col='#7c5a22')
    prim('uv_sphere', 'Mound', (0, 0.05, -0.32), (1.25, 1.0, 0.4), m=gold, segments=64, ring_count=32)
    rnd = random.Random(3)
    coin = mat('Coin', '#d4ab52', rough=0.25, metal=1.0, var=0.5, var_col='#8a6428')
    for i in range(140):
        a = rnd.uniform(0, 2 * math.pi); r = math.sqrt(rnd.random()) * 1.15
        x, y = r * math.cos(a), 0.05 + r * math.sin(a) * 0.85
        z = -0.32 + 0.4 * math.sqrt(max(0, 1 - (x / 1.25) ** 2 - ((y - 0.05) / 1.0) ** 2)) + 0.01
        if abs(x) < 0.35 and -0.6 < y < 0.35:
            continue                                   # leave room for the monkey
        prim('cylinder', 'Coin', (x, y, z), (0.055, 0.055, 0.008),
             (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), 0), m=coin, vertices=24)
    back = mat('CardBack', '#4a2c1a', 0.6, var=0.5, var_col='#2a1a10')
    for i, (x, y, rz) in enumerate(((-0.9, -0.3, 0.4), (0.85, -0.45, -0.3), (-0.55, -0.7, 1.2))):
        for k in range(5):
            prim('cube', 'Cards', (x + 0.004 * k, y, 0.0 + 0.008 * k), (0.12, 0.17, 0.003),
                 (0, 0, rz + 0.05 * k), m=back)
    # oil lamp, lit
    lamp = mat('Lamp', '#a8782e', rough=0.25, metal=1.0, var=0.5, var_col='#5e4018')
    prim('uv_sphere', 'LampBody', (-0.95, -0.55, 0.12), (0.2, 0.13, 0.09), m=lamp, segments=32, ring_count=16)
    prim('cone', 'Spout', (-0.75, -0.55, 0.15), (0.03, 0.03, 0.12), (0, math.radians(70), 0), m=lamp, vertices=16)
    prim('torus', 'LampHandle', (-1.13, -0.55, 0.16), (1, 1, 1), (math.radians(90), 0, 0), m=lamp,
         major_radius=0.06, minor_radius=0.012)
    prim('uv_sphere', 'Flame', (-0.64, -0.55, 0.26), (0.03, 0.03, 0.07), m=mat('Flame', '#ffb04a', emit=30.0),
         segments=16, ring_count=8)
    l = bpy.data.lights.new('LampLight', 'POINT'); l.energy = 90; l.color = (1.0, 0.62, 0.3); l.shadow_soft_size = 0.05
    lo = link(bpy.data.objects.new('LampLight', l)); lo.location = (-0.64, -0.6, 0.3)


# ---------------------------------------------------------------- desert night
def desert():
    sand = mat('Sand', '#8a5a32', rough=0.95, bump=0.3, bump_scale=80, var=0.6, var_col='#4a2e1a')
    for i, (y, z, s, seed) in enumerate(((3, -0.4, 14, 1), (7, -0.3, 22, 2), (12, -0.2, 30, 3))):
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=30, size=1, location=(0, y, z))
        g = bpy.context.active_object; g.scale = (s, s * 0.35, 1)
        tx = bpy.data.textures.new(f'Dune{i}', 'CLOUDS'); tx.noise_scale = 0.35 + 0.2 * i
        d = g.modifiers.new('D', 'DISPLACE'); d.texture = tx; d.strength = 0.6 + 0.5 * i
        g.data.materials.append(sand)
        for p in g.data.polygons:
            p.use_smooth = True
    # domed city on the horizon
    city = mat('City', '#1f1a1c', 0.9)
    win = mat('Window', '#ffb45a', emit=6.0)
    rnd = random.Random(8)
    for i in range(9):
        x = -6 + i * 1.5 + rnd.uniform(-0.3, 0.3); h = rnd.uniform(0.6, 1.4)
        prim('cube', 'Tower', (x, 14, h / 2 + 0.3), (0.32, 0.3, h / 2), m=city)
        prim('uv_sphere', 'Dome', (x, 14, h + 0.3), (0.34, 0.32, 0.42), m=city, segments=24, ring_count=12)
        prim('cone', 'Spire', (x, 14, h + 0.85), (0.04, 0.04, 0.2), m=city, vertices=8)
        if rnd.random() < 0.6:
            prim('cube', 'Win', (x, 13.68, h * 0.55 + 0.3), (0.05, 0.01, 0.08), m=win)
    for x in (-3.4, 2.6, 5.2):
        prim('cylinder', 'Minaret', (x, 14.2, 1.6), (0.09, 0.09, 1.6), m=city, vertices=12)
        prim('cone', 'MinaretTop', (x, 14.2, 3.4), (0.13, 0.13, 0.3), m=city, vertices=12)
    # crescent moon
    moon = prim('cylinder', 'Moon', (2.6, 18, 5.4), (0.75, 0.75, 0.02), (math.radians(90), 0, 0),
                m=mat('Moon', '#f4e2b0', emit=4.0), vertices=64)
    cut = prim('cylinder', 'MoonCut', (2.95, 17.9, 5.6), (0.68, 0.68, 0.2), (math.radians(90), 0, 0), vertices=64)
    b = moon.modifiers.new('Crescent', 'BOOLEAN'); b.operation = 'DIFFERENCE'; b.object = cut
    cut.hide_render = True; cut.hide_viewport = True
    rnd = random.Random(11)
    star = mat('Star', '#fff1d0', emit=8.0)
    for i in range(160):
        x = rnd.uniform(-12, 12); z = rnd.uniform(2.6, 9)
        s = rnd.uniform(0.012, 0.035)
        prim('uv_sphere', 'Star', (x, 19, z), (s, s, s), m=star, segments=8, ring_count=4)


def world(sc):
    w = bpy.data.worlds.new('Sky'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; N = nt.nodes; L = nt.links
    bg = N['Background']
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = N.new('ShaderNodeValToRGB')
    L.new(sep.outputs['Z'], ramp.inputs[0])
    els = ramp.color_ramp.elements
    els[0].position = 0.0; els[0].color = lin('#c8642e')
    els[1].position = 0.45; els[1].color = lin('#0e1022')
    for pos, col in ((0.06, '#9a4a2c'), (0.14, '#4a2a3a'), (0.25, '#1c1a34')):
        e = els.new(pos); e.color = lin(col)
    L.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.9


# ---------------------------------------------------------------- scene, lights, camera
def setup(res, transparent):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    for k, v in (('taa_render_samples', 64), ('use_raytracing', True), ('use_shadows', True)):
        try:
            setattr(sc.eevee, k, v)
        except AttributeError:
            pass
    world(sc)
    return sc


def lights():
    def area(name, loc, energy, size, col, target=(0, -0.1, 0.8)):
        l = bpy.data.lights.new(name, 'AREA'); l.energy = energy; l.size = size; l.color = col
        o = link(bpy.data.objects.new(name, l)); o.location = loc; look(o, target)
    area('Key', (-2.2, -2.6, 2.6), 260, 1.6, (1.0, 0.78, 0.55))         # warm lamplight key
    area('Fill', (2.6, -2.8, 1.0), 70, 3.0, (0.55, 0.62, 0.8))          # cool moonlit fill
    area('Rim', (1.5, 2.5, 2.8), 420, 1.5, (0.75, 0.85, 1.0))           # moon rim on the fur
    area('Bounce', (0, -1.2, -0.3), 40, 2.0, (1.0, 0.7, 0.35), (0, 0, 1))  # gold bounce from the hoard


def camera(loc, target, lens):
    c = bpy.data.cameras.new('Cam'); c.lens = lens
    o = link(bpy.data.objects.new('Cam', c)); o.location = loc; look(o, target)
    bpy.context.scene.camera = o


def render(sc, name):
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    print('SCENE wrote', name, flush=True)


if WHICH in ('art', 'both'):
    sc = setup((1500, 1200), False)
    monkey(); hoard(); desert(); lights()
    camera((0.15, -4.6, 1.15), (0.05, 0, 0.82), 52)
    render(sc, 'scene-art.png')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'))
if WHICH in ('mascot', 'both'):
    sc = setup((1600, 1600), True)
    monkey(); hoard(); lights()
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
    camera((0.1, -5.2, 1.0), (0.0, 0, 0.72), 50)
    render(sc, 'scene-mascot.png')
print('SCENE done', flush=True)
