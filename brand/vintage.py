"""Card Hunt vintage brand set: the monkey card hunter on a 1993-95 style card, built from the
scan-made frame tiles (textures/hires) and the pixel monkey (vintage/monkey-*.png, from monkey.py).

blender -b -P vintage.py -- cards|wordmark|icon|anim|encode   (comma list ok)   -> out/vintage/
"""
import bpy, os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textures as T                     # helpers only (its own steps don't run for these args)
from mathutils import Vector

ROOT = T.ROOT
OUT = os.path.join(ROOT, 'out', 'vintage'); os.makedirs(OUT, exist_ok=True)
STEPS = (T.ARGS[0] if T.ARGS else 'cards').split(',')
tex = lambda n: os.path.join(ROOT, 'textures', 'hires', n + '.jpg')
PIXART = lambda n: os.path.join(ROOT, 'vintage', n + '.png')
TILE = 0.83                               # one frame tile = a third of the card width

THEME = {   # frame, box, burn, title ink, body ink, bevel
    'dark':  ('frame-black', 'box-black', 0.4, '#f1e9d8', '#1a1208', '#3a3a38'),
    'light': ('frame-white', 'box-white', 0.0, '#1a1814', '#1a1814', '#8a877f'),
}


def pix_mat(name, path):
    """Pixel art, sharp pixels (Closest), alpha respected."""
    m = bpy.data.materials.new(name)
    nt = T.NT(m)
    t = nt.n('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True)
    t.interpolation = 'Closest'; t.extension = 'CLIP'
    e = nt.n('ShaderNodeEmission'); nt.l(t.outputs['Color'], e.inputs['Color'])
    tr = nt.n('ShaderNodeBsdfTransparent')
    mix = nt.n('ShaderNodeMixShader')
    nt.l(t.outputs['Alpha'], mix.inputs[0]); nt.l(tr.outputs[0], mix.inputs[1]); nt.l(e.outputs[0], mix.inputs[2])
    nt.l(mix.outputs[0], nt.out.inputs['Surface'])
    try:
        m.surface_render_method = 'BLENDED'
    except AttributeError:
        m.blend_method = 'BLEND'
    return m


def fonts():
    return T.load_font(T.SERIF), T.load_font(T.SERIF_I)


def cost(x, y, z=0.01):
    for i, cx in enumerate((x, x - 0.22)):
        T.rr_obj(f'Cost{i}', 0.17, 0.17, 0.085, T.flat('CostDisc', '#efe6d2'), (cx, y, z))
        T.rr_obj(f'CostRing{i}', 0.09, 0.09, 0.045, T.flat('CostInk', '#1a1814'), (cx - 0.01, y + 0.01, z + 0.01))
        T.rr_obj(f'CostHole{i}', 0.05, 0.05, 0.025, T.flat('CostDisc2', '#efe6d2'), (cx - 0.01, y + 0.01, z + 0.02))


def render(sc, name):
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    print('wrote', name, flush=True)


# ---------------------------------------------------------------- the logo card (front + back)
def card_front(theme):
    ft, bt, burn, title, body, bev = THEME[theme]
    sc = T.reset((1000, 1400), transparent=True)
    T.camera_top(3.5)
    bold, ital = fonts()
    inv, ink, bevel = T.flat('Title', title), T.flat('Body', body), T.flat('Bevel', bev)
    T.rr_obj('Edge', 2.5, 3.5, 0.13, T.flat('Edge', '#0b0b0b'), (0, 0, -0.02))
    T.rr_obj('Frame', 2.3, 3.3, 0.06, T.img_mat('Frame', tex(ft), (2.3 / TILE, 3.3 / TILE)), (0, 0, -0.01))
    T.txt('Card Hunt', 0.17, inv, (-1.02, 1.47, 0.01), bold)
    cost(0.98, 1.48)
    T.rr_obj('ArtBevel', 2.0, 1.62, 0.02, bevel, (0, 0.53, 0.0))
    T.rr_obj('Art', 1.92, 1.536, 0.002, pix_mat('Art', PIXART('monkey-art')), (0, 0.53, 0.01))   # 80x64 = 1.25:1
    T.txt('Legendary Creature — Monkey Hunter', 0.105, inv, (-0.98, -0.4, 0.01), bold)
    T.rr_obj('BoxBevel', 2.0, 1.12, 0.03, bevel, (0, -1.05, 0.0))
    T.rr_obj('Box', 1.94, 1.06, 0.03, T.img_mat('Box', tex(bt), (1.94 / TILE, 1.06 / TILE), vignette=burn), (0, -1.05, 0.01))
    T.txt('Search every store at once.\nKeep the cheapest copy.', 0.1, ink, (-0.88, -0.74, 0.02), bold, valign='TOP')
    T.txt('"No card stays hidden for long."', 0.095, ink, (-0.88, -1.28, 0.02), ital)
    T.txt('Illus. Card Hunt', 0.075, inv, (-1.0, -1.7, 0.01), bold)
    T.txt('1/1', 0.13, inv, (1.02, -1.69, 0.01), bold, align='RIGHT')
    render(sc, f'logo-card-{theme}.png')


def card_back():
    """Our own back: black frame, the monkey, the name. (Not the real card back.)"""
    sc = T.reset((1000, 1400), transparent=True)
    T.camera_top(3.5)
    bold, ital = fonts()
    T.rr_obj('Edge', 2.5, 3.5, 0.13, T.flat('Edge', '#0b0b0b'), (0, 0, -0.02))
    T.rr_obj('Frame', 2.3, 3.3, 0.06, T.img_mat('Frame', tex('frame-black'), (2.3 / TILE, 3.3 / TILE)), (0, 0, -0.01))
    T.rr_obj('Bevel', 1.9, 1.9, 0.94, T.flat('Bevel', '#c9a23e'), (0, 0.35, 0.0), seg=24)
    T.rr_obj('Disc', 1.8, 1.8, 0.89, pix_mat('Icon', PIXART('monkey-icon')), (0, 0.35, 0.01), seg=24)
    T.txt('Card Hunt', 0.34, T.flat('Ink', '#f1e9d8'), (0, -1.05, 0.01), bold, align='CENTER')
    T.txt('singles · sealed · decks', 0.13, T.flat('Ink2', '#c9a23e'), (0, -1.42, 0.01), ital, align='CENTER')
    render(sc, 'logo-card-back.png')


# ---------------------------------------------------------------- wordmark
def wordmark(theme):
    ft, _, _, title, _, bev = THEME[theme]
    sc = T.reset((2400, 900), transparent=True)
    T.camera_top(6.4)
    bold, ital = fonts()
    T.rr_obj('Edge', 6.3, 2.3, 0.22, T.flat('Edge', '#0b0b0b'), (0, 0, -0.02))
    T.rr_obj('Frame', 6.06, 2.06, 0.12, T.img_mat('Frame', tex(ft), (6.06 / 1.4, 2.06 / 1.4)), (0, 0, -0.01))
    T.rr_obj('ArtBevel', 1.86, 1.86, 0.03, T.flat('Bevel', bev), (-2.0, 0, 0.0))
    T.rr_obj('Art', 1.76, 1.76, 0.002, pix_mat('Icon', PIXART('monkey-icon')), (-2.0, 0, 0.01))
    T.txt('Card Hunt', 0.86, T.flat('Title', title), (-0.85, 0.2, 0.01), bold)
    T.txt('Every store, one search', 0.27, T.flat('Tag', title), (-0.82, -0.55, 0.01), ital)
    render(sc, f'logo-wordmark-{theme}.png')


# ---------------------------------------------------------------- app icons
ICONS = [('icon-1024.png', 1024, 0.80), ('icon-512.png', 512, 0.80), ('icon-192.png', 192, 0.80),
         ('icon-maskable-512.png', 512, 0.62), ('apple-touch-icon.png', 180, 0.72)]


def icons():
    for name, size, art in ICONS:
        sc = T.reset((size, size), transparent=False)
        T.camera_top(2.0)
        T.rr_obj('Frame', 2.0, 2.0, 0.002, T.img_mat('Frame', tex('frame-black'), 2.0 / 1.2), (0, 0, -0.01))
        b = 2.0 * art
        T.rr_obj('Bevel', b + 0.08, b + 0.08, 0.04, T.flat('Bevel', '#c9a23e'), (0, 0, 0.0))
        T.rr_obj('Art', b, b, 0.002, pix_mat('Icon', PIXART('monkey-icon')), (0, 0, 0.01))
        render(sc, name)


# ---------------------------------------------------------------- spinning pixel card
PIX, UP = 200, 4          # rendered at 200 px, shown at 800 px with chunky pixels
PALETTE = ['#0b0b0b', '#1a1410', '#161d18', '#262d28', '#3b4642', '#4a2c1a', '#7a4a2a', '#a46c3e',
           '#e6bc90', '#c08a62', '#cdb47c', '#97804f', '#a8402a', '#f4ecda', '#a9cfd8', '#c9a23e',
           '#d0643a', '#f0a050', '#e0b78e', '#c59b77', '#211c3c', '#3a2a58', '#6a3458', '#a84a4a', '#f8d68c']
PAL = np.array([[int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)] for h in PALETTE], np.float32)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16 - 0.5


def anim():
    sc = T.reset((PIX, PIX), transparent=True)
    sc.render.fps = 15
    sc.frame_start, sc.frame_end = 1, 48
    sc.render.filter_size = 0.5
    W, H, TH = 2.5, 3.5, 0.05
    spin = bpy.data.objects.new('Spin', None); T.link(spin)
    tilt = bpy.data.objects.new('Tilt', None); T.link(tilt); tilt.parent = spin
    tilt.rotation_euler = (math.radians(90 - 6), 0, 0)

    def face(name, path, z, flip):
        m = bpy.data.materials.new(name); nt = T.NT(m)
        t = nt.n('ShaderNodeTexImage'); t.image = bpy.data.images.load(path)
        p = nt.n('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.5
        nt.l(t.outputs['Color'], p.inputs['Base Color'])
        tr = nt.n('ShaderNodeBsdfTransparent'); mix = nt.n('ShaderNodeMixShader')
        nt.l(t.outputs['Alpha'], mix.inputs[0]); nt.l(tr.outputs[0], mix.inputs[1]); nt.l(p.outputs[0], mix.inputs[2])
        nt.l(mix.outputs[0], nt.out.inputs['Surface'])
        try:
            m.surface_render_method = 'DITHERED'
        except AttributeError:
            pass
        me = bpy.data.meshes.new(name)
        xs = (-W / 2, W / 2) if not flip else (W / 2, -W / 2)
        me.from_pydata([(xs[0], -H / 2, z), (xs[1], -H / 2, z), (xs[1], H / 2, z), (xs[0], H / 2, z)], [], [[0, 1, 2, 3]])
        uv = me.uv_layers.new()
        for i, l in enumerate(me.loops):
            uv.data[i].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][l.vertex_index]
        me.materials.append(m)
        ob = T.link(bpy.data.objects.new(name, me)); ob.parent = tilt
        return ob

    face('Front', os.path.join(OUT, 'logo-card-dark.png'), TH / 2, False)
    face('Back', os.path.join(OUT, 'logo-card-back.png'), -TH / 2, True)
    T.rr_obj('Core', W - 0.02, H - 0.02, 0.12, T.flat('Core', '#0b0b0b'), (0, 0, 0)).parent = tilt

    spin.rotation_euler.z = 0; spin.keyframe_insert('rotation_euler', index=2, frame=1)
    spin.rotation_euler.z = math.radians(360); spin.keyframe_insert('rotation_euler', index=2, frame=49)
    act = spin.animation_data.action
    curves = list(getattr(act, 'fcurves', []) or [])
    if not curves:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    curves += list(bag.fcurves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

    cam = bpy.data.cameras.new('Cam'); cam.lens = 125
    co = T.link(bpy.data.objects.new('Cam', cam)); co.location = (0, -15.5, 1.2)
    co.rotation_euler = (Vector((0, 0, 0)) - co.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = co
    for nm, loc, e, s in (('Key', (-5, -7, 6), 900, 5), ('Fill', (6, -6, 0), 350, 7), ('Rim', (0, 7, 4), 900, 6)):
        l = bpy.data.lights.new(nm, 'AREA'); l.energy = e; l.size = s
        o = T.link(bpy.data.objects.new(nm, l)); o.location = loc
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    raw = os.path.join(OUT, 'raw'); os.makedirs(raw, exist_ok=True)
    sc.render.filepath = os.path.join(raw, '####')
    bpy.ops.render.render(animation=True)
    pixelate(raw, os.path.join(OUT, 'frames'))


def pixelate(src, dst):
    """Snap to the card palette with ordered dither, 1px dark outline, nearest-neighbour x4."""
    os.makedirs(dst, exist_ok=True)
    for f in sorted(os.listdir(src)):
        if not f.endswith('.png'):
            continue
        im = bpy.data.images.load(os.path.join(src, f))
        w, h = im.size
        a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a); bpy.data.images.remove(im)
        a = a.reshape(h, w, 4)
        th = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w, None]
        rgb = np.clip(a[..., :3] + th * 0.12, 0, 1)
        d = ((rgb[:, :, None, :] - PAL[None, None]) ** 2).sum(-1)
        out = PAL[d.argmin(-1)]
        alpha = a[..., 3] > 0.5
        pad = np.pad(alpha, 1)
        inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
        out[alpha & ~inner] = PAL[0]
        o = np.zeros((h, w, 4), np.float32); o[..., :3] = out; o[..., 3] = alpha
        o = np.repeat(np.repeat(o, UP, 0), UP, 1)
        oi = bpy.data.images.new('px', w * UP, h * UP, alpha=True)
        oi.pixels.foreach_set(o.ravel())
        oi.filepath_raw = os.path.join(dst, f); oi.file_format = 'PNG'; oi.save()
        bpy.data.images.remove(oi)
    print('pixelated', dst, flush=True)


def encode():
    frames = os.path.join(OUT, 'frames')
    files = sorted(f for f in os.listdir(frames) if f.endswith('.png'))
    size = PIX * UP
    for out_name, bg in (('card-spin.webm', None), ('card-spin-dark.mp4', '#121412'), ('card-spin-light.mp4', '#f1ebdf')):
        sc = T.reset((size, size), transparent=bg is None)
        sc.render.fps = 15
        sc.frame_start, sc.frame_end = 1, len(files)
        ed = sc.sequence_editor_create()
        coll = ed.strips if hasattr(ed, 'strips') else ed.sequences
        if bg:
            try:
                c = coll.new_effect(name='BG', type='COLOR', channel=1, frame_start=1, length=len(files))
            except TypeError:
                c = coll.new_effect(name='BG', type='COLOR', channel=1, frame_start=1, frame_end=len(files) + 1)
            c.color = tuple(int(bg[i:i + 2], 16) / 255 for i in (1, 3, 5))
        st = coll.new_image(name='Frames', filepath=os.path.join(frames, files[0]), channel=2, frame_start=1)
        for f in files[1:]:
            st.elements.append(f)
        st.blend_type = 'ALPHA_OVER'
        im = sc.render.image_settings
        if hasattr(im, 'media_type'):
            im.media_type = 'VIDEO'
        im.file_format = 'FFMPEG'
        ff = sc.render.ffmpeg
        if bg is None:
            ff.format, ff.codec = 'WEBM', 'WEBM'; im.color_mode = 'RGBA'
        else:
            ff.format, ff.codec = 'MPEG4', 'H264'; im.color_mode = 'RGB'
        ff.constant_rate_factor = 'HIGH'
        sc.render.filepath = os.path.join(OUT, out_name)
        bpy.ops.render.render(animation=True)
        print('wrote', out_name, flush=True)


for step in STEPS:
    if step == 'cards':
        card_front('dark'); card_front('light'); card_back()
    elif step == 'wordmark':
        wordmark('dark'); wordmark('light')
    elif step == 'icon':
        icons()
    elif step == 'anim':
        anim()
    elif step == 'encode':
        encode()
print('VINTAGE done', flush=True)
