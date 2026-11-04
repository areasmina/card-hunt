"""Make the scan-stitched tiles (textures/src, 352 px) sharp enough for the app.

1. Real-ESRGAN x4 on the GPU (tile wrapped 3x3 first, so the seams stay seamless) -> 1408 px
2. Blender relief pass: the upscaled tile lit by a sun through a bump made from its own
   brightness, rendered at 2048 px, then matched back to the scan's colours.

blender -b -P upres.py -- <src dir> <out dir> <path to realesrgan-ncnn-vulkan.exe>
"""
import bpy, os, sys, math, subprocess
import numpy as np
from mathutils import Vector

SRC, OUT, ESR = sys.argv[sys.argv.index('--') + 1:][:3]
SIZE = 2048
# how much of the card stock's relief to bring out (box-white is the embossed one)
RELIEF = {'box-white': 0.35, 'frame-white': 0.18, 'box-artifact': 0.2, 'frame-artifact': 0.15}
os.makedirs(OUT, exist_ok=True)
WORK = os.path.join(OUT, 'work'); os.makedirs(WORK, exist_ok=True)


def read(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def write(a, path):
    h, w = a.shape[:2]
    im = bpy.data.images.new('w', w, h, alpha=False)
    im.pixels.foreach_set(a.astype(np.float32).ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)


def upscale(name):
    t = read(os.path.join(SRC, name + '.png'))
    n = t.shape[0]
    write(np.tile(t, (3, 3, 1)), os.path.join(WORK, name + '-pad.png'))
    out = os.path.join(WORK, name + '-x4.png')
    subprocess.run([ESR, '-i', os.path.join(WORK, name + '-pad.png'), '-o', out,
                    '-n', 'realesrgan-x4plus', '-s', '4'], check=True)
    big = read(out)
    c = big[4 * n:8 * n, 4 * n:8 * n].copy()
    path = os.path.join(WORK, name + '-up.png'); write(c, path)
    return path, t


def relief(name, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.0

    cam = bpy.data.cameras.new('C'); cam.type = 'ORTHO'; cam.ortho_scale = 1.0
    co = bpy.data.objects.new('C', cam); co.location = (0, 0, 5); sc.collection.objects.link(co); sc.camera = co

    m = bpy.data.materials.new('T'); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    bsdf = N['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.85
    tex = N.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path)
    tex.interpolation = 'Cubic'; tex.extension = 'REPEAT'
    L.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bw = N.new('ShaderNodeRGBToBW'); L.new(tex.outputs['Color'], bw.inputs[0])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = RELIEF.get(name, 0.1)
    bump.inputs['Distance'].default_value = 0.002
    L.new(bw.outputs[0], bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    me = bpy.data.meshes.new('P')
    me.from_pydata([(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)], [], [[0, 1, 2, 3]])
    uv = me.uv_layers.new()
    for i, l in enumerate(me.loops):
        uv.data[i].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][l.vertex_index]
    me.materials.append(m)
    sc.collection.objects.link(bpy.data.objects.new('P', me))

    # one sun from the top left, so the light is the same everywhere and the tile stays seamless
    s = bpy.data.lights.new('S', 'SUN'); s.energy = 3.0; s.angle = math.radians(2)
    so = bpy.data.objects.new('S', s); sc.collection.objects.link(so)
    so.rotation_euler = (Vector((0, 0, 0)) - Vector((-1, 1, 1.6))).to_track_quat('-Z', 'Y').to_euler()

    out = os.path.join(WORK, name + '-lit.png'); sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    return out


def match(lit, ref):
    """Keep the relief, put the scan's own colours back (per-channel mean and spread)."""
    a = lit[..., :3]; r = ref[..., :3]
    a = (a - a.mean((0, 1))) / (a.std((0, 1)) + 1e-6) * r.std((0, 1)) + r.mean((0, 1))
    o = lit.copy(); o[..., :3] = a.clip(0, 1); o[..., 3] = 1
    return o


names = sys.argv[sys.argv.index('--') + 4:] or sorted(f[:-4] for f in os.listdir(SRC) if f.endswith('.png'))
for name in names:
    up, src = upscale(name)
    lit = relief(name, up)
    write(match(read(lit), read(up)), os.path.join(OUT, name + '.png'))
    print('UPRES', name, flush=True)
print('UPRES done')
