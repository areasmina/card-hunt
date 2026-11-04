"""Card flip for each golden-age direction, rendered in Blender.

blender -b -P flip.py -- A|B|C    (needs <D>/card-front.png and <D>/card-back.png from compose.py)
  A: smooth 800 px, 30 fps, 2.4 s, warm lamplight
  B: 200 px render snapped to the 20-colour palette with dither + 1 px outline, x4, 15 fps (the original idea)
  C: 400 px render with palette dither (no outline), x2, 15 fps
-> <D>/frames/*.png, <D>/card-flip.webm (transparent), <D>/card-flip.mp4 (on #120e0c)
"""
import bpy, os, sys, math
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'A'
OD = os.path.join(HERE, D)
CFG = {'A': (800, 1, 30, 72, None), 'B': (200, 4, 15, 48, True), 'C': (400, 2, 15, 48, False)}
PIX, UP, FPS, N, OUTLINE = CFG[D]
PALETTE = ['#120e0c', '#2a1c14', '#4a2e1c', '#6e4426', '#9a6232', '#c88a44', '#e8b866', '#f6dc9a',
           '#1c2018', '#353a22', '#5a5a30', '#86803e', '#1a1830', '#2e2648', '#4a3058',
           '#7a2a1a', '#b8481e', '#e07a2c', '#f4ecd0', '#a8b8b0']
PAL = np.array([[int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)] for h in PALETTE], np.float32)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16 - 0.5


def link(o):
    bpy.context.scene.collection.objects.link(o); return o


def look(o, t):
    o.rotation_euler = (Vector(t) - o.location).to_track_quat('-Z', 'Y').to_euler()


def reset(res, transparent):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.15
    return sc


def face(name, path, z, flip, W, H, parent):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes
    p = N['Principled BSDF']; p.inputs['Roughness'].default_value = 0.45
    if 'Coat Weight' in p.inputs:
        p.inputs['Coat Weight'].default_value = 0.15
    t = N.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path)
    nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    nt.links.new(t.outputs['Alpha'], p.inputs['Alpha'])
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
    o = link(bpy.data.objects.new(name, me)); o.parent = parent
    return o


def anim():
    sc = reset(PIX, True)
    sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N
    try:
        sc.render.filter_size = 0.5 if UP > 1 else 1.0
        sc.eevee.taa_render_samples = 16 if UP > 1 else 64
    except AttributeError:
        pass
    W, H, T = 2.5, 3.5, 0.04
    spin = link(bpy.data.objects.new('Spin', None))
    tilt = link(bpy.data.objects.new('Tilt', None)); tilt.parent = spin
    tilt.rotation_euler = (math.radians(90 - 6), 0, 0)
    face('Front', os.path.join(OD, 'card-front.png'), T / 2, False, W, H, tilt)
    face('Back', os.path.join(OD, 'card-back.png'), -T / 2, True, W, H, tilt)
    # a gentle bob and a full turn that eases at front and back, like a card turned in the hand
    for fr, rz, lz in ((1, 0, 0), (N // 2 + 1, 180, 0.08), (N + 1, 360, 0)):
        sc.frame_set(fr)
        spin.rotation_euler.z = math.radians(rz); spin.location.z = lz
        spin.keyframe_insert('rotation_euler', index=2); spin.keyframe_insert('location', index=2)
    cam = bpy.data.cameras.new('C'); cam.lens = 125
    co = link(bpy.data.objects.new('C', cam)); co.location = (0, -15.5, 1.2); look(co, (0, 0, 0)); sc.camera = co
    for nm, loc, e, s, col in (('Key', (-5, -7, 4), 900, 4, (1.0, 0.75, 0.48)),
                               ('Fill', (6, -6, 0), 160, 7, (0.6, 0.68, 0.9)),
                               ('Rim', (0, 7, 4), 900, 6, (1.0, 0.85, 0.6))):
        l = bpy.data.lights.new(nm, 'AREA'); l.energy = e; l.size = s; l.color = col
        o = link(bpy.data.objects.new(nm, l)); o.location = loc; look(o, (0, 0, 0))
    raw = os.path.join(OD, 'raw'); os.makedirs(raw, exist_ok=True)
    sc.render.filepath = os.path.join(raw, '####')
    bpy.ops.render.render(animation=True)
    return raw


def process(src, dst):
    os.makedirs(dst, exist_ok=True)
    for f in sorted(os.listdir(src)):
        if not f.endswith('.png'):
            continue
        im = bpy.data.images.load(os.path.join(src, f))
        w, h = im.size
        a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a); bpy.data.images.remove(im)
        a = a.reshape(h, w, 4)
        if OUTLINE is not None:
            th = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w, None]
            x = np.clip(a[..., :3] + th * 0.1, 0, 1)
            d = (((x[:, :, None, :] - PAL[None, None]) ** 2) * np.array([0.35, 0.45, 0.2])).sum(-1)
            rgb = PAL[d.argmin(-1)]
            alpha = a[..., 3] > 0.5
            if OUTLINE:
                pad = np.pad(alpha, 1)
                inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
                rgb[alpha & ~inner] = PAL[0]
            a = np.dstack([rgb, alpha.astype(np.float32)])
            a = np.repeat(np.repeat(a, UP, 0), UP, 1)
        H2, W2 = a.shape[:2]
        oi = bpy.data.images.new('px', W2, H2, alpha=True)
        oi.pixels.foreach_set(a.astype(np.float32).ravel())
        oi.filepath_raw = os.path.join(dst, f); oi.file_format = 'PNG'; oi.save()
        bpy.data.images.remove(oi)


def encode(frames):
    files = sorted(f for f in os.listdir(frames) if f.endswith('.png'))
    size = PIX * UP
    for name, bg in (('card-flip.webm', None), ('card-flip.mp4', '#120e0c')):
        sc = reset(size, bg is None)
        sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, len(files)
        ed = sc.sequence_editor_create()
        coll = ed.strips if hasattr(ed, 'strips') else ed.sequences
        if bg:
            try:
                c = coll.new_effect(name='BG', type='COLOR', channel=1, frame_start=1, length=len(files))
            except TypeError:
                c = coll.new_effect(name='BG', type='COLOR', channel=1, frame_start=1, frame_end=len(files) + 1)
            c.color = tuple(int(bg[i:i + 2], 16) / 255 for i in (1, 3, 5))
        st = coll.new_image(name='F', filepath=os.path.join(frames, files[0]), channel=2, frame_start=1)
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
        sc.render.filepath = os.path.join(OD, name)
        bpy.ops.render.render(animation=True)
        print('FLIP wrote', D, name, flush=True)


raw = anim()
frames = os.path.join(OD, 'frames')
process(raw, frames)
encode(frames)
print('FLIP done', D, flush=True)
