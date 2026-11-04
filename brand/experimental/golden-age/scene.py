"""Card Hunt, golden-age (1993-98) direction: the monkey card hunter as a 3D scene in Blender.

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
CARD_BACK = os.path.join(HERE, '..', '..', 'logo-card-back.png')


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


def sphere(name, c, scale, m=None):
    return prim('uv_sphere', name, c, scale, m=m, segments=32, ring_count=16)


def tube(name, a, b, r, m=None, ends=True):
    """Cylinder from a to b with round ends (a capsule made of meshes)."""
    a, b = Vector(a), Vector(b)
    q = Vector((0, 0, 1)).rotation_difference((b - a).normalized())
    ob = prim('cylinder', name, (a + b) / 2, (r, r, (b - a).length / 2), q.to_euler(), m=m, vertices=24)
    parts = [ob]
    if ends:
        parts += [sphere(name, a, (r, r, r), m), sphere(name, b, (r, r, r), m)]
    return parts


def fuse(name, parts, voxel, m, smooth=4):
    """Join overlapping primitives and voxel-remesh them into one organic surface."""
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.active_object; ob.name = name
    r = ob.modifiers.new('Remesh', 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = voxel
    r.use_smooth_shade = True
    sm = ob.modifiers.new('Smooth', 'SMOOTH'); sm.factor = 0.6; sm.iterations = smooth
    ob.data.materials.clear(); ob.data.materials.append(m)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return ob


# ---------------------------------------------------------------- the monkey
# A lean, clever little beast (not a plush mascot): long limbs, long tail, small knowing eyes.
L_SH, L_EL, L_HA = (-0.22, 0.0, 0.88), (-0.4, -0.17, 0.62), (-0.5, -0.33, 0.45)
R_SH, R_EL, R_HA = (0.22, 0.0, 0.9), (0.44, -0.1, 1.1), (0.52, -0.16, 1.38)


def hand(c, toward, r, m, parts):
    c, t = Vector(c), Vector(toward)
    parts.append(sphere('palm', c, (r * 1.1, r * 0.8, r * 1.2), m))
    d = (t - c).normalized()
    side = d.cross(Vector((0, 1, 0))).normalized()
    for k in (-1, 0, 1):
        a = c + side * k * r * 0.6
        parts += tube('finger', a, a + d * r * 1.6 + Vector((0, -r * 0.5, 0)), r * 0.28, m)


def monkey():
    import bmesh
    fur = mat('Fur', '#4a2c18', rough=0.9, bump=0.5, bump_scale=160, sheen=0.3, var=0.7, var_col='#24140a')
    skin = mat('Skin', '#a8785a', rough=0.6, bump=0.12, bump_scale=70, var=0.5, var_col='#6e4a34')
    dark = mat('Pupil', '#050403', rough=0.05)
    amber = mat('Iris', '#b8801e', rough=0.08, emit=0.3)

    P = [sphere('b', (0, 0.1, 0.62), (0.26, 0.24, 0.38)),
         sphere('chest', (0, 0.0, 0.8), (0.24, 0.2, 0.18)),
         sphere('h', (0, -0.04, 1.12), (0.25, 0.24, 0.26)),
         sphere('s', (0, 0.0, 1.2), (0.23, 0.23, 0.2)),
         sphere('brow', (0, -0.2, 1.19), (0.19, 0.07, 0.05)),
         sphere('cheekL', (-0.15, -0.13, 1.07), (0.1, 0.1, 0.1)),
         sphere('cheekR', (0.15, -0.13, 1.07), (0.1, 0.1, 0.1))]
    for sx in (-1, 1):
        P.append(sphere('e', (sx * 0.25, 0.0, 1.13), (0.08, 0.04, 0.09)))
        P += tube('t', (sx * 0.14, -0.02, 0.34), (sx * 0.26, -0.4, 0.34), 0.09)
        P += tube('s', (sx * 0.26, -0.4, 0.34), (sx * 0.28, -0.46, 0.1), 0.07)
    P += tube('a', L_SH, L_EL, 0.062) + tube('a', L_EL, L_HA, 0.052)
    P += tube('a', R_SH, R_EL, 0.062) + tube('a', R_EL, R_HA, 0.052)
    pts = []
    for i in range(48):                                         # long tail rising behind, curled tip
        t = i / 47
        if t < 0.7:
            u = t / 0.7
            pts.append((0.12 + 0.6 * u, 0.32 + 0.2 * u, 0.32 + 0.9 * u * u))
        else:
            u = (t - 0.7) / 0.3; a = math.pi * 1.6 * u; r = 0.13 * (1 - 0.5 * u)
            pts.append((0.72 + r * math.sin(a), 0.52, 1.22 + r * (1 - math.cos(a))))
    for k in range(len(pts) - 1):
        P += tube('tail', pts[k], pts[k + 1], 0.042 - 0.02 * k / 47)
    fuse('Fur', P, 0.014, fur)

    S = [sphere('m', (0, -0.25, 1.03), (0.12, 0.11, 0.09)),
         sphere('chin', (0, -0.22, 0.97), (0.08, 0.08, 0.05)),
         sphere('belly', (0, -0.12, 0.6), (0.17, 0.12, 0.24))]
    hand(L_HA, (-0.62, -0.4, 0.5), 0.05, None, S)
    hand(R_HA, (0.56, -0.2, 1.52), 0.05, None, S)
    for sx in (-1, 1):
        S += [sphere('mask', (sx * 0.075, -0.2, 1.14), (0.08, 0.06, 0.07)),
              sphere('ear', (sx * 0.25, -0.03, 1.13), (0.05, 0.025, 0.06)),
              sphere('foot', (sx * 0.29, -0.55, 0.06), (0.07, 0.14, 0.04))]
        for k in (-1, 0, 1):
            S += tube('toe', (sx * 0.29 + k * 0.035, -0.62, 0.05), (sx * 0.29 + k * 0.045, -0.72, 0.03), 0.016)
    fuse('Skin', S, 0.008, skin)

    for sx in (-1, 1):
        sphere('Iris', (sx * 0.072, -0.255, 1.15), (0.026, 0.016, 0.022), amber)
        sphere('Pupil', (sx * 0.072, -0.268, 1.15), (0.011, 0.006, 0.013), dark)
        sphere('Nostril', (sx * 0.022, -0.355, 1.06), (0.01, 0.008, 0.008), dark)
    sphere('Mouth', (0, -0.348, 1.0), (0.05, 0.008, 0.006), dark)

    # weathered pith hat
    khaki = mat('Khaki', '#9c8656', rough=0.85, bump=0.25, bump_scale=220, var=0.7, var_col='#5e4e2e')
    crown = prim('uv_sphere', 'Crown', (0, -0.02, 1.32), (0.25, 0.27, 0.21), (0, math.radians(-6), 0), m=khaki,
                 segments=48, ring_count=24)
    bm = bmesh.new(); bm.from_mesh(crown.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.05], context='VERTS')
    bm.to_mesh(crown.data); bm.free()
    prim('cylinder', 'Brim', (0, -0.04, 1.31), (0.39, 0.41, 0.01), (math.radians(-9), math.radians(-6), 0),
         m=khaki, vertices=64)
    prim('cylinder', 'Band', (0, -0.02, 1.34), (0.262, 0.282, 0.03), (0, math.radians(-6), 0),
         m=mat('Band', '#5a1e14', 0.8), vertices=64)

    # tarnished brass magnifier in the left hand
    brass = mat('Brass', '#8a6a2a', rough=0.4, metal=1.0, bump=0.1, var=0.6, var_col='#3e3018')
    tube('Handle', (-0.5, -0.34, 0.38), (-0.6, -0.41, 0.5), 0.022, mat('Wood', '#2a160a', 0.6))
    rot = (math.radians(80), 0, math.radians(15))
    prim('torus', 'Rim', (-0.63, -0.44, 0.64), (1, 1, 1), rot, m=brass,
         major_radius=0.14, minor_radius=0.017, major_segments=48, minor_segments=12)
    glass = bpy.data.materials.new('Glass'); glass.use_nodes = True
    gn = glass.node_tree.nodes; gn.clear()
    gl = gn.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = 0.05
    gt = gn.new('ShaderNodeBsdfTransparent')
    gm = gn.new('ShaderNodeMixShader'); gm.inputs[0].default_value = 0.25
    go = gn.new('ShaderNodeOutputMaterial')
    glass.node_tree.links.new(gt.outputs[0], gm.inputs[1]); glass.node_tree.links.new(gl.outputs[0], gm.inputs[2])
    glass.node_tree.links.new(gm.outputs[0], go.inputs['Surface'])
    try:
        glass.surface_render_method = 'BLENDED'
    except AttributeError:
        glass.blend_method = 'BLEND'
    prim('cylinder', 'Lens', (-0.63, -0.44, 0.64), (0.13, 0.13, 0.003), rot, m=glass, vertices=48)

    # the card held up, face to the viewer
    rz = math.radians(-6)
    prim('cube', 'Card', (0.55, -0.2, 1.56), (0.13, 0.003, 0.18), (0, 0, rz), m=mat('CardEdge', '#0b0b0b', 0.5))
    if os.path.exists(CARD_FACE):
        prim('plane', 'CardFace', (0.55, -0.205, 1.56), (0.125, 0.175, 1), (math.radians(90), 0, rz),
             m=image_mat('CardFace', CARD_FACE))


# ---------------------------------------------------------------- the hoard and the lamp
def hoard():
    gold = mat('Gold', '#c9a04a', rough=0.3, metal=1.0, bump=0.2, bump_scale=30, var=0.5, var_col='#7c5a22')
    prim('uv_sphere', 'Mound', (0, 0.05, -0.32), (1.25, 1.0, 0.4), m=gold, segments=64, ring_count=32)
    gold.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.5
    rnd = random.Random(3)
    coin = mat('Coin', '#d4ab52', rough=0.25, metal=1.0, var=0.5, var_col='#8a6428')
    for i in range(320):
        a = rnd.uniform(0, 2 * math.pi); r = math.sqrt(rnd.random()) * 1.15
        x, y = r * math.cos(a), 0.05 + r * math.sin(a) * 0.85
        z = -0.32 + 0.4 * math.sqrt(max(0, 1 - (x / 1.25) ** 2 - ((y - 0.05) / 1.0) ** 2)) + 0.01
        if abs(x) < 0.35 and -0.6 < y < 0.35:
            continue                                   # leave room for the monkey
        prim('cylinder', 'Coin', (x, y, z), (0.055, 0.055, 0.008),
             (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), 0), m=coin, vertices=24)
    back = mat('CardBack', '#2a1a10', 0.6)
    face = image_mat('StackTop', CARD_BACK) if os.path.exists(CARD_BACK) else back
    for i, (x, y, rz) in enumerate(((-0.9, -0.3, 0.4), (0.85, -0.45, -0.3), (-0.55, -0.7, 1.2))):
        for k in range(5):
            prim('cube', 'Cards', (x + 0.004 * k, y, 0.0 + 0.008 * k), (0.12, 0.17, 0.003),
                 (0, 0, rz + 0.05 * k), m=back)
        prim('plane', 'StackTop', (x + 0.016, y, 0.036), (0.12, 0.17, 1), (0, 0, rz + 0.2), m=face)
    # oil lamp, lit
    lamp = mat('Lamp', '#a8782e', rough=0.25, metal=1.0, var=0.5, var_col='#5e4018')
    prim('uv_sphere', 'LampBody', (-0.95, -0.55, 0.12), (0.2, 0.13, 0.09), m=lamp, segments=32, ring_count=16)
    prim('cone', 'Spout', (-0.75, -0.55, 0.15), (0.03, 0.03, 0.12), (0, math.radians(70), 0), m=lamp, vertices=16)
    prim('torus', 'LampHandle', (-1.13, -0.55, 0.16), (1, 1, 1), (math.radians(90), 0, 0), m=lamp,
         major_radius=0.06, minor_radius=0.012)
    flame = bpy.data.materials.new('Flame'); flame.use_nodes = True
    fn = flame.node_tree.nodes; fn.clear()
    fe = fn.new('ShaderNodeEmission'); fe.inputs['Color'].default_value = lin('#ff8a2a'); fe.inputs['Strength'].default_value = 2.5
    fo = fn.new('ShaderNodeOutputMaterial'); flame.node_tree.links.new(fe.outputs[0], fo.inputs['Surface'])
    prim('uv_sphere', 'Flame', (-0.64, -0.55, 0.26), (0.03, 0.03, 0.07), m=flame,
         segments=16, ring_count=8)
    l = bpy.data.lights.new('LampLight', 'POINT'); l.energy = 160; l.color = (1.0, 0.62, 0.3); l.shadow_soft_size = 0.05
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
                m=mat('Moon', '#f4e2b0', emit=2.0), vertices=64)
    cut = prim('cylinder', 'MoonCut', (2.95, 17.9, 5.6), (0.68, 0.68, 0.2), (math.radians(90), 0, 0), vertices=64)
    b = moon.modifiers.new('Crescent', 'BOOLEAN'); b.operation = 'DIFFERENCE'; b.object = cut
    cut.hide_render = True; cut.hide_viewport = True
    rnd = random.Random(11)
    star = mat('Star', '#fff1d0', emit=3.0)
    for i in range(90):
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
    bg.inputs['Strength'].default_value = 0.45
    vol = N.new('ShaderNodeVolumePrincipled'); vol.inputs['Density'].default_value = 0.0025
    vol.inputs['Color'].default_value = lin('#c89060')
    L.new(vol.outputs[0], N['World Output'].inputs['Volume'])


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
    # chiaroscuro: one warm low key, a cold moon rim, almost no fill
    area('Key', (-2.0, -2.2, 1.2), 220, 0.8, (1.0, 0.7, 0.42))
    area('Fill', (2.6, -2.8, 1.0), 12, 3.0, (0.45, 0.55, 0.8))
    area('Rim', (1.4, 2.4, 2.6), 700, 1.2, (0.7, 0.82, 1.0))
    area('Rim2', (-1.6, 2.2, 1.8), 260, 1.0, (0.9, 0.7, 0.5))
    area('Bounce', (0, -1.0, -0.3), 25, 2.0, (1.0, 0.65, 0.3), (0, 0, 1))


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
    camera((0.12, -3.9, 0.95), (0.05, 0, 0.86), 50)
    render(sc, 'scene-art.png')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'))
if WHICH in ('art', 'both', 'mask'):
    # silhouette of the monkey + hoard from the same camera, for the hybrid direction
    sc = setup((1500, 1200), False)
    monkey(); hoard()
    keep = set(o.name for o in bpy.data.objects)
    desert()
    for o in bpy.data.objects:
        if o.name not in keep and o.type == 'MESH':
            o.hide_render = True
    for o in [o for o in bpy.data.objects if o.type == 'LIGHT']:
        o.hide_render = True
    white = bpy.data.materials.new('White'); white.use_nodes = True
    n = white.node_tree.nodes; n.clear()
    e = n.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (1, 1, 1, 1)
    out = n.new('ShaderNodeOutputMaterial'); white.node_tree.links.new(e.outputs[0], out.inputs['Surface'])
    bpy.context.view_layer.material_override = white
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    sc.view_settings.view_transform = 'Standard'
    camera((0.12, -3.9, 0.95), (0.05, 0, 0.86), 50)
    render(sc, 'scene-mask.png')
if WHICH in ('mascot', 'both'):
    sc = setup((1600, 1600), True)
    monkey(); hoard(); lights()
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
    camera((0.1, -5.2, 1.0), (0.0, 0, 0.72), 50)
    render(sc, 'scene-mascot.png')
print('SCENE done', flush=True)
