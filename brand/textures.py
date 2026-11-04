# Card Hunt "vintage card" texture set. Original, procedural, seamless tiles.
#   blender -b -P textures.py -- tiles [size]   -> out/tex/<name>.png  (default 2048, try 8192)
#   blender -b -P textures.py -- mock           -> out/tex/mock-light.png, out/tex/mock-dark.png
# Seamless trick: UV is wrapped onto a torus and fed to 4D noise/voronoi, so the edges meet.
import bpy, math, os, sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'out', 'tex')
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
WHICH = ARGS[0] if ARGS else 'tiles'
SIZE = int(ARGS[1]) if len(ARGS) > 1 and ARGS[1].isdigit() else 2048


def lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def reset(res, transparent=False):
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
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 16
    except AttributeError:
        pass
    w = bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.05, 0.05, 0.05, 1)
    return sc


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera_top(scale, aspect_y=1.0):
    c = bpy.data.cameras.new('Cam'); c.type = 'ORTHO'; c.ortho_scale = scale
    o = link(bpy.data.objects.new('Cam', c)); o.location = (0, 0, 10)
    bpy.context.scene.camera = o
    return o


def plane(name, w, h, m, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [[0, 1, 2, 3]])
    me.uv_layers.new(name='UVMap')
    for i, uv in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        me.uv_layers[0].data[i].uv = uv
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    return ob


class NT:
    """Tiny node-tree helper."""
    def __init__(self, m):
        m.use_nodes = True
        self.t = m.node_tree
        self.t.nodes.clear()
        self.out = self.n('ShaderNodeOutputMaterial')

    def n(self, kind, **inputs):
        node = self.t.nodes.new(kind)
        for k, v in inputs.items():
            if k.startswith('_'):
                setattr(node, k[1:], v)
            else:
                node.inputs[k].default_value = v
        return node

    def l(self, a, b):
        self.t.links.new(a, b)

    def math(self, op, a, b=None, v=None):
        m = self.n('ShaderNodeMath'); m.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                m.inputs[i].default_value = x
            else:
                self.l(x, m.inputs[i])
        return m.outputs[0]

    def torus(self, scale, offset=0.0):
        """Seamless 4D coordinate from UV: returns (vector socket, w socket)."""
        uv = self.n('ShaderNodeUVMap')
        sep = self.n('ShaderNodeSeparateXYZ'); self.l(uv.outputs[0], sep.inputs[0])
        R = scale / (2 * math.pi)
        au = self.math('MULTIPLY', sep.outputs['X'], 2 * math.pi)
        av = self.math('MULTIPLY', sep.outputs['Y'], 2 * math.pi)
        comb = self.n('ShaderNodeCombineXYZ')
        self.l(self.math('MULTIPLY', self.math('COSINE', au), R), comb.inputs[0])
        self.l(self.math('MULTIPLY', self.math('SINE', au), R), comb.inputs[1])
        self.l(self.math('ADD', self.math('MULTIPLY', self.math('COSINE', av), R), offset), comb.inputs[2])
        w = self.math('MULTIPLY', self.math('SINE', av), R)
        return comb.outputs[0], w

    def noise(self, scale, detail=8, rough=0.55, distortion=0.0, offset=0.0, lacunarity=2.0):
        v, w = self.torus(scale, offset)
        nz = self.n('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'
        nz.inputs['Scale'].default_value = 1.0
        nz.inputs['Detail'].default_value = detail
        nz.inputs['Roughness'].default_value = rough
        nz.inputs['Lacunarity'].default_value = lacunarity
        nz.inputs['Distortion'].default_value = distortion
        self.l(v, nz.inputs['Vector']); self.l(w, nz.inputs['W'])
        return nz.outputs['Fac']

    def ramp(self, fac, stops):
        r = self.n('ShaderNodeValToRGB')
        el = r.color_ramp.elements
        while len(el) < len(stops):
            el.new(0.5)
        for e, (pos, col) in zip(el, stops):
            e.position = pos
            e.color = lin(col)
        self.l(fac, r.inputs['Fac'])
        return r.outputs['Color']

    def mixc(self, fac, a, b, blend='MIX'):
        m = self.n('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = blend
        for sock, x in ((m.inputs[0], fac), (m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(x, (int, float)):
                sock.default_value = x
            elif isinstance(x, tuple):
                sock.default_value = x
            else:
                self.l(x, sock)
        return m.outputs[2]

    def emit(self, color):
        e = self.n('ShaderNodeEmission'); self.l(color, e.inputs['Color'])
        self.l(e.outputs[0], self.out.inputs['Surface'])


# ---------------------------------------------------------------- the tiles
# Colour targets measured from the reference scans: luminance quantiles 3/20/50/80/97 %.
# Each grey pattern below is rank-mapped onto these, so contrast and colour match the cards.
TARGET = {
    'box-blue':     ['#94c7d3', '#9fcddb', '#a6d0df', '#b3d6e0', '#d5e6ea'],
    'box-black':    ['#c59b77', '#d2a882', '#dcb189', '#e0b78e', '#e6bf96'],
    'frame-artifact': ['#403023', '#594737', '#6a5747', '#7c6655', '#977e68'],
    'box-artifact': ['#c8c3b6', '#cdc9bc', '#d3cebf', '#d7d3c4', '#dedacb'],
    'frame-white':  ['#a4998f', '#c0b2a5', '#cdbfb3', '#d9c9be', '#e7ded5'],
    'box-white':    ['#afa7a5', '#c4bcba', '#d2cac8', '#ded6d4', '#ede5e3'],
    'frame-black':  ['#161d18', '#1d221d', '#202621', '#262d28', '#3b4642'],
}
# One tile = about 20 mm of a real card (a third of its width).


def torus2(nt, su, sv, offset=0.0):
    """Like NT.torus but with separate scales across and down (for streaky textures)."""
    uv = nt.n('ShaderNodeUVMap')
    sep = nt.n('ShaderNodeSeparateXYZ'); nt.l(uv.outputs[0], sep.inputs[0])
    au = nt.math('MULTIPLY', sep.outputs['X'], 2 * math.pi)
    av = nt.math('MULTIPLY', sep.outputs['Y'], 2 * math.pi)
    ru, rv = su / (2 * math.pi), sv / (2 * math.pi)
    comb = nt.n('ShaderNodeCombineXYZ')
    nt.l(nt.math('MULTIPLY', nt.math('COSINE', au), ru), comb.inputs[0])
    nt.l(nt.math('MULTIPLY', nt.math('SINE', au), ru), comb.inputs[1])
    nt.l(nt.math('ADD', nt.math('MULTIPLY', nt.math('COSINE', av), rv), offset), comb.inputs[2])
    return comb.outputs[0], nt.math('MULTIPLY', nt.math('SINE', av), rv)


def noise2(nt, su, sv, detail=8, rough=0.55, distortion=0.0, offset=0.0):
    v, w = torus2(nt, su, sv, offset)
    nz = nt.n('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = detail
    nz.inputs['Roughness'].default_value = rough
    nz.inputs['Distortion'].default_value = distortion
    nt.l(v, nz.inputs['Vector']); nt.l(w, nz.inputs['W'])
    return nz.outputs['Fac']


def grey(nt, *terms):
    """Weighted sum of scalar sockets -> emission grey."""
    acc = None
    for sock, wgt in terms:
        t = nt.math('MULTIPLY', sock, wgt)
        acc = t if acc is None else nt.math('ADD', acc, t)
    c = nt.n('ShaderNodeCombineColor')
    for i in range(3):
        nt.l(acc, c.inputs[i])
    nt.emit(c.outputs[0])


def lit_relief(nt, height, strength=0.6, rough=0.6):
    bump = nt.n('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = 0.004
    nt.l(height, bump.inputs['Height'])
    p = nt.n('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1)
    p.inputs['Roughness'].default_value = rough
    nt.l(bump.outputs[0], p.inputs['Normal'])
    nt.l(p.outputs[0], nt.out.inputs['Surface'])


def p_frame_white(nt):
    grey(nt, (nt.noise(5, 12, 0.5), 0.75), (nt.noise(30, 5, 0.55, offset=4), 0.12), (nt.noise(110, 2, 0.6, offset=8), 0.13))


def p_box_white(nt):
    # pebbled, embossed card stock: voronoi crinkle lit from the top left
    v, w = nt.torus(48)
    warp = nt.noise(10, 4, 0.5, offset=2)
    vo = nt.n('ShaderNodeTexVoronoi'); vo.voronoi_dimensions = '4D'
    vo.feature = 'DISTANCE_TO_EDGE'
    vo.inputs['Scale'].default_value = 1.0
    vv = nt.n('ShaderNodeVectorMath'); vv.operation = 'ADD'
    nt.l(v, vv.inputs[0])
    wv = nt.n('ShaderNodeCombineXYZ'); [nt.l(warp, wv.inputs[i]) for i in range(3)]
    sc = nt.n('ShaderNodeVectorMath'); sc.operation = 'SCALE'; sc.inputs['Scale'].default_value = 3.0
    nt.l(wv.outputs[0], sc.inputs[0]); nt.l(sc.outputs[0], vv.inputs[1])
    nt.l(vv.outputs[0], vo.inputs['Vector']); nt.l(w, vo.inputs['W'])
    h = nt.math('ADD', nt.math('MINIMUM', vo.outputs['Distance'], 0.25), nt.math('MULTIPLY', nt.noise(6, 8, 0.6, offset=8), 0.25))
    lit_relief(nt, h, 0.8, 0.7)


def p_box_black(nt):
    grey(nt, (nt.noise(3.5, 12, 0.45), 0.6), (nt.noise(16, 6, 0.5, offset=3), 0.12), (nt.noise(120, 2, 0.6, offset=7), 0.28))


def p_frame_artifact(nt):
    grey(nt, (nt.noise(9, 10, 0.62), 0.45), (nt.noise(95, 3, 0.7, offset=5), 0.4),
         (nt.noise(30, 6, 0.6, offset=9), 0.15))


def p_box_artifact(nt):
    grey(nt, (nt.noise(5, 8, 0.6), 0.6), (nt.noise(40, 6, 0.6, offset=6), 0.4))


def p_box_blue(nt):
    # watery sky: long horizontal cloud streaks
    grey(nt, (noise2(nt, 2.5, 9, 8, 0.62, distortion=0.6), 0.75), (noise2(nt, 12, 40, 4, 0.6, offset=3), 0.25))


def t_frame_blue(nt):
    """Paper-marbling: turquoise with thin indigo/purple veins flowing in long curves."""
    n = noise2(nt, 1.3, 2.4, 5, 0.5, distortion=1.3)
    s = nt.math('ABSOLUTE', nt.math('SINE', nt.math('MULTIPLY', n, 17.0)))
    vein = nt.ramp(s, [(0.0, '#3b3f99'), (0.07, '#4a5aa8'), (0.16, '#2c7f9c'), (0.4, '#2fa3b8'),
                       (0.75, '#3cb3c4'), (1.0, '#57bcc6')])
    shade = nt.ramp(nt.noise(3, 5, 0.55, offset=4), [(0.3, '#7d93a0'), (0.6, '#ffffff')])
    speck = nt.ramp(nt.noise(60, 4, 0.6, offset=11), [(0.3, '#b8c4c8'), (0.6, '#ffffff')])
    nt.emit(nt.mixc(0.35, nt.mixc(0.5, vein, shade, 'MULTIPLY'), speck, 'MULTIPLY'))


def p_frame_black(nt):
    """Near-black green stone; the glossy beads are added afterwards in add_beads()."""
    grey(nt, (nt.noise(6, 12, 0.6), 0.7), (nt.noise(60, 4, 0.65, offset=12), 0.3))


def add_beads(path, count=12, rmin=0.022, rmax=0.04, seed=5):
    """Paint raised glossy beads, wrapping round the edges so the tile stays seamless."""
    import numpy as np
    rng = np.random.default_rng(seed)
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    L = np.array([-0.55, 0.55, 0.63]); L /= np.linalg.norm(L)
    H = L + np.array([0, 0, 1.0]); H /= np.linalg.norm(H)
    base = np.array([0.09, 0.115, 0.10])
    pts = []
    while len(pts) < count:                       # loose Poisson-disc spacing
        p = rng.random(2)
        if all(min(abs(p[0] - q[0]), 1 - abs(p[0] - q[0])) ** 2 + min(abs(p[1] - q[1]), 1 - abs(p[1] - q[1])) ** 2
               > 0.18 ** 2 for q in pts):
            pts.append(p)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for (px, py) in pts:
        r = rng.uniform(rmin, rmax) * w
        cx, cy = px * w, py * h
        for ox in (-w, 0, w):
            for oy in (-h, 0, h):
                dx, dy = xx - (cx + ox), yy - (cy + oy)
                # soft shadow, down-right
                sd = np.sqrt((dx - r * 0.35) ** 2 + (dy + r * 0.35) ** 2) / (r * 1.25)
                shadow = np.clip(1 - sd, 0, 1) ** 1.5 * 0.55
                a[..., :3] *= (1 - shadow)[..., None]
                d2 = (dx ** 2 + dy ** 2) / r ** 2
                inside = d2 < 1
                if not inside.any():
                    continue
                nz = np.sqrt(np.clip(1 - d2, 0, 1))
                nx, ny = dx / r, dy / r            # image y grows upward in Blender pixels
                diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
                spec = np.clip(nx * H[0] + ny * H[1] + nz * H[2], 0, 1) ** 60
                rim = np.clip(1 - nz, 0, 1) ** 3 * 0.35
                col = base * (0.35 + 0.9 * diff)[..., None] + (spec * 0.95)[..., None] + (rim * 0.12)[..., None]
                edge = np.clip((1 - np.sqrt(d2)) * r, 0, 1)[..., None]   # 1px antialias
                a[..., :3] = np.where(inside[..., None], a[..., :3] * (1 - edge) + col * edge, a[..., :3])
    im.pixels.foreach_set(a.ravel())
    im.save()
    bpy.data.images.remove(im)


TILES = {
    'frame-blue': (t_frame_blue, None),
    'box-blue': (p_box_blue, 'box-blue'),
    'frame-black': (p_frame_black, 'frame-black'),
    'box-black': (p_box_black, 'box-black'),
    'frame-white': (p_frame_white, 'frame-white'),
    'box-white': (p_box_white, 'box-white'),
    'frame-artifact': (p_frame_artifact, 'frame-artifact'),
    'box-artifact': (p_box_artifact, 'box-artifact'),
}
LIT = {'box-white'}


def rank_map(path, stops):
    """Histogram-match a rendered grey tile onto measured colour quantiles."""
    import numpy as np
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a)
    a = a.reshape(-1, 4)
    lum = a[:, 0] * 0.3 + a[:, 1] * 0.59 + a[:, 2] * 0.11
    rank = np.empty(len(lum), np.float32); rank[np.argsort(lum, kind='stable')] = np.linspace(0, 1, len(lum))
    cols = np.array([[int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)] for c in stops], np.float32)
    lo, hi = cols[0] - (cols[1] - cols[0]) * 0.4, cols[-1] + (cols[-1] - cols[-2]) * 0.4
    if len(cols) == 6:            # last stop is a highlight for the top 0.4 %
        glint = cols[5]; cols = cols[:5]
        lo = cols[0] - (cols[1] - cols[0]) * 0.4
        xs = np.array([0, .03, .2, .5, .8, .97, .996, 1], np.float32)
        ys = np.vstack([lo, cols, cols[4] * 1.15, glint]).clip(0, 1)
    else:
        xs = np.array([0, .03, .2, .5, .8, .97, 1], np.float32)
        ys = np.vstack([lo, cols, hi]).clip(0, 1)
    for c in range(3):
        a[:, c] = np.interp(rank, xs, ys[:, c])
    a[:, 3] = 1
    im.pixels.foreach_set(a.ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)


def stats(path):
    import numpy as np
    im = bpy.data.images.load(path)
    a = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(a)
    px = a.reshape(-1, 4)[:, :3] * 255
    lum = px @ np.array([.3, .59, .11]); o = np.argsort(lum); n = len(o)
    qs = ['#%02x%02x%02x' % tuple(px[o[int(q * (n - 1))]].astype(int)) for q in (.03, .2, .5, .8, .97)]
    print('STATS', os.path.basename(path), qs, 'std', round(float(lum.std()), 1))


def build_tiles(size):
    for name, (fn, target) in TILES.items():
        sc = reset((size, size))
        camera_top(1.0)
        m = bpy.data.materials.new(name)
        fn(NT(m))
        plane('Tile', 1, 1, m)
        if name in LIT:
            # sun = same light everywhere, so the tile stays seamless
            l = bpy.data.lights.new('Sun', 'SUN'); l.energy = 4.0; l.angle = math.radians(3)
            o = link(bpy.data.objects.new('Sun', l)); o.location = (0, 0, 5)
            o.rotation_euler = (Vector((0, 0, 0)) - Vector((-1, 1, 0.9))).to_track_quat('-Z', 'Y').to_euler()
        path = os.path.join(OUT, f'{name}.png')
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        if target:
            rank_map(path, TARGET[target])
        if name == 'frame-black':
            add_beads(path)
        stats(path)


# ---------------------------------------------------------------- frame mockups
def img_mat(name, path, repeat=1.0, vignette=0.0, tint='#ffffff'):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = nt.n('ShaderNodeUVMap')
    rx, ry = repeat if isinstance(repeat, tuple) else (repeat, repeat)
    mp = nt.n('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (rx, ry, 1)
    nt.l(uv.outputs[0], mp.inputs['Vector'])
    tex = nt.n('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path, check_existing=True)
    nt.l(mp.outputs[0], tex.inputs['Vector'])
    col = nt.mixc(1.0, tex.outputs['Color'], lin(tint), 'MULTIPLY')
    if vignette:
        # burnt edges: darken towards the border of the UV square
        sep = nt.n('ShaderNodeSeparateXYZ'); nt.l(uv.outputs[0], sep.inputs[0])
        ex = nt.math('ABSOLUTE', nt.math('SUBTRACT', sep.outputs['X'], 0.5))
        ey = nt.math('ABSOLUTE', nt.math('SUBTRACT', sep.outputs['Y'], 0.5))
        e = nt.math('POWER', nt.math('MULTIPLY', nt.math('MAXIMUM', ex, ey), 2.0), 6.0)
        burn = nt.ramp(e, [(0.0, '#ffffff'), (0.6, '#d08a4a'), (1.0, '#5a2408')])
        col = nt.mixc(vignette, col, burn, 'MULTIPLY')
    nt.emit(col)
    return m


def flat(name, hexcol):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    rgb = nt.n('ShaderNodeRGB'); rgb.outputs[0].default_value = lin(hexcol)
    nt.emit(rgb.outputs[0])
    return m


def rr_obj(name, w, h, r, m, loc, seg=10):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, 0) for x, y in pts], [], [list(range(len(pts)))])
    uvl = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, _ = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (x / w + 0.5, y / h + 0.5)
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    return ob


SERIF = [r'C:\Windows\Fonts\GOUDOSB.TTF', r'C:\Windows\Fonts\ANTQUAB.TTF', r'C:\Windows\Fonts\palab.ttf',
         r'C:\Windows\Fonts\georgiab.ttf']
SERIF_I = [r'C:\Windows\Fonts\GOUDOSI.TTF', r'C:\Windows\Fonts\ANTQUAI.TTF', r'C:\Windows\Fonts\palai.ttf',
           r'C:\Windows\Fonts\georgiai.ttf']


def load_font(paths):
    for p in paths:
        if os.path.exists(p):
            return bpy.data.fonts.load(p)
    return None


def txt(body, size, m, loc, f, align='LEFT', valign='CENTER'):
    cu = bpy.data.curves.new('T', 'FONT'); cu.body = body; cu.size = size
    cu.align_x = align; cu.align_y = valign
    if f:
        cu.font = f
    ob = link(bpy.data.objects.new('T', cu)); ob.location = loc
    ob.data.materials.append(m)
    return ob


def sky_mat():
    m = bpy.data.materials.new('Sky')
    nt = NT(m)
    uv = nt.n('ShaderNodeUVMap')
    sep = nt.n('ShaderNodeSeparateXYZ'); nt.l(uv.outputs[0], sep.inputs[0])
    nt.emit(nt.ramp(sep.outputs['Y'], [(0.0, '#e2733a'), (0.25, '#c8553a'), (0.55, '#4a3a6e'), (1.0, '#141c3c')]))
    return m


def hills(m, y0, x0, x1, z):
    import random
    rnd = random.Random(3)
    pts = [(x0, y0 - 0.2)]
    n = 14
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        pts.append((x, y0 + rnd.uniform(0.02, 0.22) + (0.25 if 9 <= i <= 11 else 0)))
    pts.append((x1, y0 - 0.2))
    me = bpy.data.meshes.new('Hills')
    me.from_pydata([(x, y, 0) for x, y in pts], [], [list(range(len(pts)))])
    me.materials.append(m)
    ob = link(bpy.data.objects.new('Hills', me)); ob.location = (0, 0, z)


THEMES = {
    #        frame tile,        box tile,       box burn, title ink, rule ink, bevel
    'dark':     ('frame-black', 'box-black',    0.4, '#f1e9d8', '#1a1208', '#3a3a38'),
    'light':    ('frame-white', 'box-white',    0.0, '#1a1814', '#1a1814', '#8a877f'),
    'blue':     ('frame-blue',  'box-blue',     0.0, '#f4f8fb', '#10202a', '#24525e'),
    'artifact': ('frame-artifact', 'box-artifact', 0.0, '#f1e9d8', '#1a1814', '#3d2c1e'),
}


def build_mock():
    tex = lambda n: os.path.join(os.environ.get('TEX', OUT), f'{n}.png')  # TEX=out/upres for the scan tiles
    T = 0.83                                  # one tile = a third of the card width
    for theme, (ft, bt, burn, title, rule, bev) in THEMES.items():
        sc = reset((1000, 1400))
        camera_top(3.5)
        bold, ital = load_font(SERIF), load_font(SERIF_I)
        frame = img_mat('Frame', tex(ft), (2.3 / T, 3.3 / T))
        box = img_mat('Box', tex(bt), (1.94 / T, 1.06 / T), vignette=burn)
        inv, ink, bevel = flat('Title', title), flat('Rule', rule), flat('Bevel', bev)
        rr_obj('Edge', 2.5, 3.5, 0.13, flat('Edge', '#0b0b0b'), (0, 0, -0.02))
        rr_obj('Frame', 2.3, 3.3, 0.06, frame, (0, 0, -0.01))
        txt('Card Hunt', 0.17, inv, (-1.02, 1.47, 0.01), bold)
        for i, cx in enumerate((0.98, 0.76)):
            rr_obj(f'Cost{i}', 0.17, 0.17, 0.085, flat('CostDisc', '#efe6d2'), (cx, 1.48, 0.01))
            rr_obj(f'CostRing{i}', 0.09, 0.09, 0.045, flat('CostInk', '#1a1814'), (cx - 0.01, 1.49, 0.02))
            rr_obj(f'CostHole{i}', 0.05, 0.05, 0.025, flat('CostDisc2', '#efe6d2'), (cx - 0.01, 1.49, 0.03))
        rr_obj('ArtBevel', 2.0, 1.62, 0.02, bevel, (0, 0.53, 0.0))
        rr_obj('Art', 1.92, 1.54, 0.015, sky_mat(), (0, 0.53, 0.01))
        hills(flat('Hill', '#0e0e12'), -0.05, -0.96, 0.96, 0.015)
        txt('Artifact', 0.12, inv, (-0.98, -0.4, 0.01), bold)
        rr_obj('BoxBevel', 2.0, 1.12, 0.03, bevel, (0, -1.05, 0.0))
        rr_obj('Box', 1.94, 1.06, 0.03, box, (0, -1.05, 0.01))
        txt('Search every store at once.\nKeep the cheapest copy.', 0.1, ink, (-0.88, -0.74, 0.02), bold, valign='TOP')
        txt('"Five shops, one search."', 0.095, ink, (-0.88, -1.28, 0.02), ital)
        txt('Illus. Card Hunt', 0.075, inv, (-1.0, -1.7, 0.01), bold)
        sc.render.filepath = os.path.join(OUT, f'mock-{theme}.png')
        bpy.ops.render.render(write_still=True)
        print('wrote mock', theme)


if WHICH == 'tiles':
    build_tiles(SIZE)
elif WHICH == 'mock':
    build_mock()
