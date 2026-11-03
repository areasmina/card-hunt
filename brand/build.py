# Card Hunt brand assets, built with Blender (tested on 5.2 LTS).
#   blender -b -P build.py -- logo     -> out/logo-light.png, out/logo-dark.png
#   blender -b -P build.py -- icon     -> out/icon-*.png
#   blender -b -P build.py -- anim     -> out/frames/####.png
#   blender -b -P build.py -- encode   -> out/card-spin.webm (alpha), out/card-spin.mp4
# Every scene is also saved as a .blend in out/ so it can be opened and tweaked.
import bpy, bmesh, math, os, sys, random
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'out')
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
WHICH = ARGS[0] if ARGS else 'all'
FAST = 'fast' in ARGS


def srgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lin(h):
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb(h)) + (1.0,)


ACCENT, LIGHT, DEEP = lin('5433eb'), lin('7c5cff'), lin('3a1fc2')
WHITE, LAV, LAV2, INK = lin('ffffff'), lin('dcd5ff'), lin('a996ff'), lin('1c1238')

FONT_PATHS = [r'C:\Windows\Fonts\segoeuib.ttf', r'C:\Windows\Fonts\arialbd.ttf']


# ---------------------------------------------------------------- basics
def reset(res=(1024, 1024), samples=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 16 if FAST else samples
        sc.eevee.use_raytracing = True
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    w = bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.75, 0.74, 0.82, 1)
    bg.inputs[1].default_value = 0.5
    return sc


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def empty(name, parent=None, loc=(0, 0, 0)):
    e = link(bpy.data.objects.new(name, None))
    e.parent = parent
    e.location = loc
    return e


def set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


def mat(name, color, rough=0.35, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = color
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if coat:
        set_input(p, ('Coat Weight', 'Clearcoat'), coat)
    return m


def gradient_mat(name, c0, c1, rough=0.35):
    """Diagonal gradient: c0 at top-left, c1 at bottom-right (Generated coords)."""
    m = mat(name, c0, rough)
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    sub = nt.nodes.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'
    ma = nt.nodes.new('ShaderNodeMath'); ma.operation = 'MULTIPLY_ADD'
    ma.inputs[1].default_value = 0.5; ma.inputs[2].default_value = 0.5
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = c0
    ramp.color_ramp.elements[1].color = c1
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['X'], sub.inputs[0])
    nt.links.new(sep.outputs['Y'], sub.inputs[1])
    nt.links.new(sub.outputs[0], ma.inputs[0])
    nt.links.new(ma.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m


def image_mat(name, img, flip_x=False, rough=0.3, coat=0.4):
    m = mat(name, WHITE, rough, coat=coat)
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
    tex.interpolation = 'Cubic'
    if flip_x:
        uv = nt.nodes.new('ShaderNodeUVMap')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Location'].default_value[0] = 1.0
        mp.inputs['Scale'].default_value[0] = -1.0
        nt.links.new(uv.outputs[0], mp.inputs['Vector'])
        nt.links.new(mp.outputs[0], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], p.inputs['Base Color'])
    return m


def rrect(name, w, h, r, thick, mats, parent=None, loc=(0, 0, 0), rot=0.0, seg=10, bevel=None):
    """Rounded rectangle in local XY (front face +Z), UVs 0..1 across it, solidified."""
    pts = []
    r = min(r, w / 2 - 1e-4, h / 2 - 1e-4)
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((x, y, 0)) for x, y in pts])
    uv = bm.loops.layers.uv.new('UVMap')
    for l in f.loops:
        l[uv].uv = (l.vert.co.x / w + 0.5, l.vert.co.y / h + 0.5)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler.z = math.radians(rot)
    if thick:
        s = ob.modifiers.new('Solidify', 'SOLIDIFY')
        s.thickness = thick
        s.offset = 0
        s.use_even_offset = True
        if len(mats) > 1:
            s.material_offset = 1
        if len(mats) > 2:
            s.material_offset_rim = 2
        b = ob.modifiers.new('Bevel', 'BEVEL')
        b.width = bevel if bevel is not None else thick * 0.35
        b.segments = 4
        b.limit_method = 'ANGLE'
        b.angle_limit = math.radians(50)
        b.harden_normals = False
    for p in me.polygons:
        p.use_smooth = False
    return ob


def font():
    for f in FONT_PATHS:
        if os.path.exists(f):
            return bpy.data.fonts.load(f)
    return None


def text(body, size, m, parent=None, loc=(0, 0, 0), extrude=0.0, bevel=0.0,
         align='CENTER', valign='CENTER', rot=(0, 0, 0), spacing=1.0):
    cu = bpy.data.curves.new('Text', 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    cu.align_x = align
    cu.align_y = valign
    cu.space_character = spacing
    fnt = font()
    if fnt:
        cu.font = fnt
    ob = link(bpy.data.objects.new('Text', cu))
    ob.data.materials.append(m)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, energy, size, target=(0, 0, 0), color=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA')
    l.energy = energy
    l.size = size
    l.color = color
    o = link(bpy.data.objects.new(name, l))
    o.location = loc
    look_at(o, target)
    return o


def camera(loc, target=(0, 0, 0), lens=50, ortho=None):
    c = bpy.data.cameras.new('Camera')
    c.lens = lens
    if ortho:
        c.type = 'ORTHO'
        c.ortho_scale = ortho
    o = link(bpy.data.objects.new('Camera', c))
    o.location = loc
    look_at(o, target)
    bpy.context.scene.camera = o
    return o


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('wrote', path)


def save_blend(name):
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, name), compress=True)


# ---------------------------------------------------------------- the mark
def mark(parent, mats):
    """Card Hunt mark: two stacked cards and a magnifier, in local XY, ~2.2 units tall."""
    root = empty('Mark', parent)
    rrect('BackCard', 1.25, 1.7, 0.14, 0.07, [mats['back']] * 3, root, (-0.32, 0.06, 0.0), rot=11)
    rrect('FrontCard', 1.25, 1.7, 0.14, 0.07, [mats['card']] * 3, root, (0.08, 0.0, 0.16))
    rrect('Art', 0.98, 0.72, 0.08, 0.03, [mats['art']] * 3, root, (0.08, 0.32, 0.21))
    rrect('Line1', 0.78, 0.1, 0.05, 0.025, [mats['art']] * 3, root, (-0.02, -0.26, 0.205))
    rrect('Line2', 0.56, 0.1, 0.05, 0.025, [mats['art']] * 3, root, (-0.13, -0.46, 0.205))
    c = Vector((0.62, -0.5, 0.42))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.34, minor_radius=0.075, major_segments=64,
                                     minor_segments=24, location=c)
    ring = bpy.context.active_object
    ring.name = 'Ring'
    ring.data.materials.append(mats['ring'])
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.29, depth=0.04, location=c)
    lens = bpy.context.active_object
    lens.name = 'Lens'
    lens.data.materials.append(mats['lens'])
    d = Vector((math.cos(math.radians(-45)), math.sin(math.radians(-45)), 0))
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.075, depth=0.42, location=c + d * 0.6,
                                        rotation=(0, math.radians(90), math.radians(-45)))
    handle = bpy.context.active_object
    handle.name = 'Handle'
    handle.data.materials.append(mats['ring'])
    bev = handle.modifiers.new('Bevel', 'BEVEL'); bev.width = 0.04; bev.segments = 6
    for o in (ring, lens, handle):
        o.parent = root
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_smooth()
    return root


def mark_mats():
    return {
        'back': mat('BackCard', LAV2, 0.4, coat=0.3),
        'card': mat('Card', WHITE, 0.35, coat=0.4),
        'art': mat('Art', lin('c9bdff'), 0.4),
        'ring': mat('Ring', WHITE, 0.2, coat=0.6),
        'lens': mat('Lens', ACCENT, 0.15, coat=0.8),
    }


# ---------------------------------------------------------------- logo
def build_logo():
    for variant, txt_color in (('light', ACCENT), ('dark', WHITE)):
        sc = reset(res=(2400, 900))
        root = empty('Logo')
        mm = mark_mats()
        if variant == 'dark':
            mm['card'] = mat('Card', WHITE, 0.35, coat=0.4)
        # chip behind the mark so it reads on any background
        chip = rrect('Chip', 2.3, 2.3, 0.55, 0.16, [gradient_mat('Chip', LIGHT, DEEP)] * 3, root, (0, 0, -0.12),
                     bevel=0.06)
        m = mark(root, mm)
        m.scale = (0.78, 0.78, 0.78)
        m.location = (-0.12, 0.05, 0)
        tm = mat('Word', txt_color, 0.25, coat=0.6)
        text('Card Hunt', 1.25, tm, root, (1.55, -0.02, -0.05), extrude=0.14, bevel=0.018, align='LEFT', spacing=1.0)
        root.rotation_euler = (math.radians(90), 0, 0)
        root.location = (-1.85, 0, 0)
        camera((-1.6, -26, 2.4), (0, 0, 0.05), lens=115)
        area('Key', (-6, -8, 7), 1400, 6)
        area('Fill', (7, -9, 1), 500, 8)
        area('Rim', (2, 6, 5), 900, 5)
        render(os.path.join(OUT, f'logo-{variant}.png'))
        save_blend(f'logo-{variant}.blend')


# ---------------------------------------------------------------- icon
def build_icon():
    variants = [
        # name, size, full-bleed background, mark scale
        ('icon-1024.png', 1024, False, 0.62),
        ('icon-512.png', 512, False, 0.62),
        ('icon-192.png', 192, False, 0.62),
        ('icon-maskable-512.png', 512, True, 0.5),
        ('apple-touch-icon.png', 180, True, 0.56),
    ]
    for name, size, bleed, scale in variants:
        sc = reset(res=(size, size), samples=96)
        root = empty('Icon')
        if bleed:
            rrect('Tile', 2.6, 2.6, 0.01, 0.2, [gradient_mat('Tile', LIGHT, DEEP)] * 3, root, (0, 0, -0.1))
            sc.render.film_transparent = False
            sc.world.node_tree.nodes['Background'].inputs[0].default_value = DEEP
        else:
            rrect('Tile', 2.0, 2.0, 0.45, 0.2, [gradient_mat('Tile', LIGHT, DEEP)] * 3, root, (0, 0, -0.1),
                  bevel=0.07)
        m = mark(root, mark_mats())
        m.scale = (scale, scale, scale)
        m.location = (-0.06 * scale / 0.62, 0.04, 0.02)
        camera((0, 0, 12), (0, 0, 0), ortho=2.04)
        area('Key', (-4, 5, 8), 900, 5)
        area('Fill', (5, -4, 6), 220, 6)
        render(os.path.join(OUT, name))
        if name == 'icon-1024.png':
            save_blend('icon.blend')


# ---------------------------------------------------------------- card textures
def _rr_mask(H, W, x0, y0, x1, y1, r):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx = np.clip(xx, x0 + r, x1 - r)
    cy = np.clip(yy, y0 + r, y1 - r)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    inside = (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
    return np.clip(r - d + 0.5, 0, 1) * inside if r > 0 else inside.astype(np.float32)


def _paint(img, mask, color):
    c = np.array(srgb(color) if isinstance(color, str) else color, dtype=np.float32)
    img[..., :3] = img[..., :3] * (1 - mask[..., None]) + c * mask[..., None]


def card_front(W=1000, H=1400):
    img = np.zeros((H, W, 4), np.float32)
    img[..., 3] = 1
    _paint(img, np.ones((H, W), np.float32), '1c1238')
    _paint(img, _rr_mask(H, W, 34, 34, W - 34, H - 34, 40), '2b1d66')
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # title bar
    _paint(img, _rr_mask(H, W, 60, H - 170, W - 60, H - 64, 40), 'efeaff')
    # cost gems in the title bar
    for i, col in enumerate(('7c5cff', 'ff8fcf')):
        cx, cy = W - 120 - i * 74, H - 117
        _paint(img, np.clip(30 - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) + 0.5, 0, 1), col)
    # art window: dusk sky, sun, mountains, stars
    ax0, ay0, ax1, ay1 = 70, 560, W - 70, H - 200
    art = _rr_mask(H, W, ax0, ay0, ax1, ay1, 18)
    t = np.clip((yy - ay0) / (ay1 - ay0), 0, 1)[..., None]
    sky = (1 - t) * np.array(srgb('ff9ad5')) + t * np.array(srgb('5433eb'))
    img[..., :3] = img[..., :3] * (1 - art[..., None]) + sky * art[..., None]
    sun = np.clip(120 - np.sqrt((xx - 640) ** 2 + (yy - 860) ** 2) + 0.5, 0, 1) * art
    _paint(img, sun, 'ffe7a8')
    glow = np.clip(1 - np.sqrt((xx - 640) ** 2 + (yy - 860) ** 2) / 330, 0, 1) ** 2 * art * 0.35
    _paint(img, glow, 'fff3d6')
    rnd = random.Random(7)
    for _ in range(40):
        sx, sy = rnd.uniform(ax0 + 20, ax1 - 20), rnd.uniform(950, ay1 - 20)
        rr = rnd.uniform(1.5, 4)
        _paint(img, np.clip(rr - np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2) + 0.5, 0, 1) * art * 0.9, 'ffffff')
    x = np.arange(W, dtype=np.float32)
    for base, amp, period, phase, col in ((700, 170, 330, 40, '3a1fc2'), (620, 120, 220, 120, '24137a')):
        ridge = base + amp * (1 - np.abs(((x + phase) % period) / period * 2 - 1))
        mnt = (yy <= ridge[None, :]).astype(np.float32) * art
        _paint(img, mnt, col)
    # type line
    _paint(img, _rr_mask(H, W, 60, 470, W - 60, 545, 34), 'efeaff')
    # rules box
    _paint(img, _rr_mask(H, W, 70, 90, W - 70, 450, 18), 'f7f4ff')
    # stat box
    _paint(img, _rr_mask(H, W, W - 230, 50, W - 60, 140, 30), 'efeaff')
    return img


def card_back(W=1000, H=1400):
    img = np.zeros((H, W, 4), np.float32)
    img[..., 3] = 1
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    t = np.clip(d / 1.2, 0, 1)[..., None]
    img[..., :3] = (1 - t) * np.array(srgb('7c5cff')) + t * np.array(srgb('1c1238'))
    e = np.sqrt(((xx - W / 2) / 360) ** 2 + ((yy - H / 2) / 540) ** 2)
    for r0, wd, col in ((1.0, 0.035, 'dcd5ff'), (0.9, 0.012, 'a996ff'), (1.1, 0.012, 'a996ff')):
        _paint(img, np.clip(1 - np.abs(e - r0) / wd, 0, 1), col)
    # rays
    ang = np.arctan2(yy - H / 2, xx - W / 2)
    rays = (np.cos(ang * 16) > 0.92).astype(np.float32) * (e > 1.1) * (e < 1.6) * 0.25
    _paint(img, rays, 'dcd5ff')
    frame = 1 - _rr_mask(H, W, 34, 34, W - 34, H - 34, 40)
    _paint(img, frame, '1c1238')
    return img


def np_image(name, arr):
    H, W = arr.shape[:2]
    im = bpy.data.images.new(name, W, H, alpha=True)
    im.pixels.foreach_set(arr.ravel())
    im.filepath_raw = os.path.join(OUT, name + '.png')
    im.file_format = 'PNG'
    im.save()
    im.pack()
    return im


# ---------------------------------------------------------------- spinning card
def build_anim():
    sc = reset(res=(800, 800), samples=48)
    sc.render.fps = 30
    sc.frame_start, sc.frame_end = 1, 120
    W, H, T = 2.5, 3.5, 0.04
    spin = empty('Spin')
    tilt = empty('Tilt', spin)
    tilt.rotation_euler = (math.radians(90 - 6), 0, 0)
    front = image_mat('Front', np_image('card-front', card_front()))
    back = image_mat('Back', np_image('card-back', card_back()), flip_x=True)
    rim = mat('Rim', lin('2a1f4f'), 0.5)
    rrect('Card', W, H, 0.16, T, [front, back, rim], tilt, bevel=0.012)
    z = T / 2 + 0.003

    def px(x, y):  # texture pixel -> card local coords
        return ((x / 1000 - 0.5) * W, (y / 1400 - 0.5) * H, z)

    ink = mat('Ink', INK, 0.4)
    text('Card Hunt', 0.17, ink, tilt, px(90, 1400 - 117), extrude=0.002, align='LEFT')
    text('Artifact - Seeker', 0.12, ink, tilt, px(90, 507), extrude=0.002, align='LEFT')
    text('Look through every store at once.\nKeep the cheapest copy.', 0.12, ink, tilt, px(100, 415),
         extrude=0.002, align='LEFT', valign='TOP')
    text('"Five shops, one search."', 0.095, mat('Flavor', lin('5b4b8a'), 0.4), tilt, px(100, 170),
         extrude=0.002, align='LEFT')
    text('5/5', 0.13, ink, tilt, px(W * 0 + 855, 95), extrude=0.002)
    bk = mat('BackWord', WHITE, 0.25, coat=0.6)
    text('CARD\nHUNT', 0.42, bk, tilt, (0, 0, -(T / 2 + 0.034)), extrude=0.03, bevel=0.008,
         rot=(0, 180, 0), spacing=1.05)
    # spin: one full turn over 120 frames, linear, loops cleanly
    spin.rotation_euler.z = 0
    spin.keyframe_insert('rotation_euler', index=2, frame=1)
    spin.rotation_euler.z = math.radians(360)
    spin.keyframe_insert('rotation_euler', index=2, frame=121)
    try:
        for fc in spin.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'
    except AttributeError:  # layered actions (Blender 5)
        for layer in spin.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for k in fc.keyframe_points:
                            k.interpolation = 'LINEAR'
    camera((0, -15.5, 1.2), (0, 0, 0), lens=130)
    area('Key', (-5, -7, 6), 1500, 5)
    area('Fill', (6, -6, 0), 500, 7)
    area('Rim', (0, 7, 4), 1500, 6)
    frames = os.path.join(OUT, 'frames')
    os.makedirs(frames, exist_ok=True)
    save_blend('card-spin.blend')
    if 'still' in ARGS:
        for f in (1, 16, 31, 61):
            sc.frame_set(f)
            render(os.path.join(OUT, f'spin-still-{f:03d}.png'))
        return
    sc.render.filepath = os.path.join(frames, '####')
    bpy.ops.render.render(animation=True)


# ---------------------------------------------------------------- encode
def build_encode():
    frames = os.path.join(OUT, 'frames')
    files = sorted(f for f in os.listdir(frames) if f.endswith('.png'))
    for out_name, alpha in (('card-spin.webm', True), ('card-spin.mp4', False)):
        sc = reset(res=(800, 800))
        sc.render.fps = 30
        sc.frame_start, sc.frame_end = 1, len(files)
        ed = sc.sequence_editor_create()
        coll = ed.strips if hasattr(ed, 'strips') else ed.sequences
        if not alpha:
            try:
                bgc = coll.new_effect(name='BG', type='COLOR', channel=1, frame_start=1, length=len(files))
            except TypeError:
                bgc = coll.new_effect(name='BG', type='COLOR', channel=1, frame_start=1,
                                      frame_end=len(files) + 1)
            bgc.color = srgb('f6f6f8')
        st = coll.new_image(name='Frames', filepath=os.path.join(frames, files[0]), channel=2, frame_start=1)
        for f in files[1:]:
            st.elements.append(f)
        st.blend_type = 'ALPHA_OVER'
        im = sc.render.image_settings
        if hasattr(im, 'media_type'):
            im.media_type = 'VIDEO'
        im.file_format = 'FFMPEG'
        ff = sc.render.ffmpeg
        if alpha:
            ff.format, ff.codec = 'WEBM', 'WEBM'
            im.color_mode = 'RGBA'
        else:
            ff.format, ff.codec = 'MPEG4', 'H264'
            im.color_mode = 'RGB'
        ff.constant_rate_factor = 'HIGH'
        sc.render.filepath = os.path.join(OUT, out_name)
        bpy.ops.render.render(animation=True)
        print('wrote', out_name)


if WHICH in ('logo', 'all'):
    build_logo()
if WHICH in ('icon', 'all'):
    build_icon()
if WHICH in ('anim', 'all'):
    build_anim()
if WHICH in ('encode', 'all'):
    build_encode()
