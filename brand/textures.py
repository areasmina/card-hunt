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
def t_parchment_ivory(nt):
    base = nt.ramp(nt.noise(5, 10, 0.6), [(0.3, '#d8ccb2'), (0.55, '#ebe2cd'), (0.75, '#f5efe1')])
    blot = nt.ramp(nt.noise(2.2, 4, 0.5, offset=3), [(0.45, '#ffffff'), (0.75, '#cdbd9a')])
    fib = nt.ramp(nt.noise(70, 3, 0.7, offset=7), [(0.35, '#e4dccb'), (0.65, '#ffffff')])
    c = nt.mixc(0.55, base, blot, 'MULTIPLY')
    nt.emit(nt.mixc(0.35, c, fib, 'MULTIPLY'))


def t_grey_mottle(nt):
    base = nt.ramp(nt.noise(9, 14, 0.68), [(0.32, '#8d8a84'), (0.5, '#bdb9b1'), (0.68, '#e2dfd8')])
    fleck = nt.ramp(nt.noise(55, 6, 0.6, offset=5), [(0.66, '#ffffff'), (0.72, '#6e6b66')])
    nt.emit(nt.mixc(0.6, base, fleck, 'MULTIPLY'))


def t_parchment_orange(nt):
    base = nt.ramp(nt.noise(4, 12, 0.62), [(0.28, '#b85a22'), (0.5, '#df9248'), (0.72, '#f2c27f')])
    blot = nt.ramp(nt.noise(1.8, 5, 0.5, offset=9), [(0.4, '#ffffff'), (0.78, '#9c4618')])
    fib = nt.ramp(nt.noise(80, 3, 0.7, offset=2), [(0.35, '#e8c59a'), (0.65, '#ffffff')])
    nt.emit(nt.mixc(0.3, nt.mixc(0.6, base, blot, 'MULTIPLY'), fib, 'MULTIPLY'))


def t_blue_marble(nt):
    n = nt.noise(2.4, 7, 0.55, distortion=1.6)
    vein = nt.math('SINE', nt.math('MULTIPLY', n, 34.0))
    v01 = nt.math('MULTIPLY_ADD', vein, 0.5, None)
    nd = nt.t.nodes[-1]; nd.inputs[2].default_value = 0.5
    col = nt.ramp(v01, [(0.0, '#1d5c96'), (0.35, '#2f8bc6'), (0.62, '#5fb3e2'), (0.8, '#8fd0ef'),
                        (0.93, '#6c58a8'), (1.0, '#3e2f7a')])
    shade = nt.ramp(nt.noise(3, 4, 0.5, offset=4), [(0.3, '#b9c7d8'), (0.7, '#ffffff')])
    nt.emit(nt.mixc(0.5, col, shade, 'MULTIPLY'))


def t_bronze(nt):
    base = nt.ramp(nt.noise(7, 14, 0.66), [(0.3, '#3d2718'), (0.5, '#5e3f28'), (0.7, '#8a6444')])
    wear = nt.ramp(nt.noise(26, 8, 0.6, offset=6), [(0.6, '#000000'), (0.72, '#a47e58')])
    nt.emit(nt.mixc(0.5, base, wear, 'SCREEN'))


def t_black_stone(nt):
    """Dark mottled stone with glossy raised bubbles (lit, so the bubbles catch light)."""
    v, w = nt.torus(10)
    vo = nt.n('ShaderNodeTexVoronoi'); vo.voronoi_dimensions = '4D'
    vo.inputs['Scale'].default_value = 1.0
    vo.inputs['Randomness'].default_value = 1.0
    nt.l(v, vo.inputs['Vector']); nt.l(w, vo.inputs['W'])
    sep = nt.n('ShaderNodeSeparateColor'); nt.l(vo.outputs['Color'], sep.inputs[0])
    r = nt.math('MULTIPLY_ADD', sep.outputs[0], 0.16, None)
    nt.t.nodes[-1].inputs[2].default_value = 0.14                     # bubble radius 0.14..0.30
    q = nt.math('DIVIDE', vo.outputs['Distance'], r)
    h = nt.math('SQRT', nt.math('MAXIMUM', nt.math('SUBTRACT', 1.0, nt.math('MULTIPLY', q, q)), 0.0))
    inside = nt.math('GREATER_THAN', h, 0.0)
    ground = nt.ramp(nt.noise(6, 12, 0.65), [(0.3, '#070707'), (0.55, '#151515'), (0.75, '#2a2a28')])
    bub = nt.ramp(nt.noise(4, 6, 0.5, offset=3), [(0.3, '#121212'), (0.7, '#262624')])
    col = nt.mixc(inside, ground, bub)
    bump = nt.n('ShaderNodeBump'); bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 0.08
    nt.l(h, bump.inputs['Height'])
    p = nt.n('ShaderNodeBsdfPrincipled')
    nt.l(col, p.inputs['Base Color'])
    nt.l(nt.math('SUBTRACT', 0.55, nt.math('MULTIPLY', inside, 0.35)), p.inputs['Roughness'])
    nt.l(bump.outputs[0], p.inputs['Normal'])
    nt.l(p.outputs[0], nt.out.inputs['Surface'])


TILES = {
    'parchment-ivory': t_parchment_ivory,
    'grey-mottle': t_grey_mottle,
    'parchment-orange': t_parchment_orange,
    'blue-marble': t_blue_marble,
    'bronze': t_bronze,
    'black-stone': t_black_stone,
}


def build_tiles(size):
    for name, fn in TILES.items():
        sc = reset((size, size))
        camera_top(1.0)
        m = bpy.data.materials.new(name)
        fn(NT(m))
        plane('Tile', 1, 1, m)
        if name == 'black-stone':
            for nm, loc, e in (('Key', (-3, 3, 4), 60), ('Fill', (3, -2, 3), 8)):
                l = bpy.data.lights.new(nm, 'AREA'); l.energy = e; l.size = 3
                o = link(bpy.data.objects.new(nm, l)); o.location = loc
                o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, f'{name}.png')
        bpy.ops.render.render(write_still=True)
        print('wrote', name)


# ---------------------------------------------------------------- frame mockups
def img_mat(name, path, repeat=1.0, vignette=0.0, tint='#ffffff'):
    m = bpy.data.materials.new(name)
    nt = NT(m)
    uv = nt.n('ShaderNodeUVMap')
    mp = nt.n('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (repeat, repeat, 1)
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


def build_mock():
    tex = lambda n: os.path.join(OUT, f'{n}.png')
    for theme in ('dark', 'light'):
        sc = reset((1000, 1400))
        camera_top(3.5)
        bold, ital = load_font(SERIF), load_font(SERIF_I)
        if theme == 'dark':
            frame = img_mat('Frame', tex('black-stone'), 1.4)
            box = img_mat('Box', tex('parchment-orange'), 1.0, vignette=1.0)
            ink, inv = flat('Ink', '#1a1208'), flat('InkLight', '#f1e9d8')
            bevel = flat('Bevel', '#3a3a38')
        else:
            frame = img_mat('Frame', tex('grey-mottle'), 1.2)
            box = img_mat('Box', tex('parchment-ivory'), 1.0, vignette=0.35)
            ink, inv = flat('Ink', '#1a1814'), flat('InkDark', '#1a1814')
            bevel = flat('Bevel', '#8a877f')
        rr_obj('Edge', 2.5, 3.5, 0.13, flat('Edge', '#0b0b0b'), (0, 0, -0.02))
        rr_obj('Frame', 2.3, 3.3, 0.06, frame, (0, 0, -0.01))
        # title and cost symbols
        txt('Card Hunt', 0.17, inv, (-1.02, 1.47, 0.01), bold)
        for i, cx in enumerate((0.98, 0.76)):
            rr_obj(f'Cost{i}', 0.17, 0.17, 0.085, flat('CostDisc', '#efe6d2'), (cx, 1.48, 0.01))
            # our own symbol: a tiny magnifier
            rr_obj(f'CostRing{i}', 0.09, 0.09, 0.045, flat('CostInk', '#1a1814'), (cx - 0.01, 1.49, 0.02))
            rr_obj(f'CostHole{i}', 0.05, 0.05, 0.025, flat('CostDisc2', '#efe6d2'), (cx - 0.01, 1.49, 0.03))
        # art window with a simple original painting placeholder
        rr_obj('ArtBevel', 2.0, 1.62, 0.02, bevel, (0, 0.53, 0.0))
        rr_obj('Art', 1.92, 1.54, 0.015, img_mat('Art', tex('blue-marble'), 0.6, tint='#c9a6e8'), (0, 0.53, 0.01))
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
