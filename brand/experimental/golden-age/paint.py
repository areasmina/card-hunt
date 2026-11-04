"""Turn the Blender renders into the three art directions.

A  classic : oil-paint look (two Kuwahara brush passes), muted gold/olive grade, canvas weave,
             brush texture, warm varnish and vignette, like a 1993 painted card illustration.
B  pixel   : the painting resampled to 160x128 and snapped to a 20-colour palette with ordered
             dither, stray pixels cleaned into clusters, 1px outline round the monkey, x8.
C  hybrid  : painted monkey and hoard (from the mask) over a pixel-art desert, with a stair-stepped
             pixel edge, canvas on top.

python3 paint.py   (reads renders/scene-art.png, scene-mask.png, scene-mascot.png; writes art/)
"""
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, 'renders')
OUT = os.path.join(HERE, 'art'); os.makedirs(OUT, exist_ok=True)

PALETTE = ['#120e0c', '#2a1c14', '#4a2e1c', '#6e4426', '#9a6232', '#c88a44', '#e8b866', '#f6dc9a',
           '#1c2018', '#353a22', '#5a5a30', '#86803e', '#1a1830', '#2e2648', '#4a3058',
           '#7a2a1a', '#b8481e', '#e07a2c', '#f4ecd0', '#a8b8b0']
PAL = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in PALETTE], np.float32) / 255
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16 - 0.5
RNG = np.random.default_rng(1993)


def load(name):
    return np.asarray(Image.open(os.path.join(R, name)).convert('RGBA')).astype(np.float32) / 255


def save(a, name):
    a = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(a, 'RGBA' if a.shape[2] == 4 else 'RGB').save(os.path.join(OUT, name))
    print('wrote', name)


def box(x, k):
    """Mean over k x k windows anchored top-left (valid region)."""
    c = np.cumsum(np.cumsum(x, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)) + ((0, 0),) * (x.ndim - 2))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def kuwahara(rgb, r):
    H, W = rgb.shape[:2]
    p = np.pad(rgb, ((r, r), (r, r), (0, 0)), mode='reflect')
    lum = p @ np.array([0.3, 0.59, 0.11], np.float32)
    k = r + 1
    m, m2, mc = box(lum, k), box(lum * lum, k), box(p, k)
    best = None; bestv = None
    for oy, ox in ((0, 0), (0, r), (r, 0), (r, r)):
        v = m2[oy:oy + H, ox:ox + W] - m[oy:oy + H, ox:ox + W] ** 2
        c = mc[oy:oy + H, ox:ox + W]
        if best is None:
            best, bestv = c.copy(), v
        else:
            sel = v < bestv
            best[sel] = c[sel]; bestv = np.minimum(bestv, v)
    return best


def blur(x, s):
    r = int(s * 3) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    for ax in (0, 1):
        x = sum(w * np.roll(x, d, axis=ax) for d, w in zip(range(-r, r + 1), k))
    return x


def grade(rgb):
    """Muted 1993 palette: a little less saturation, olive-brown shadows, gold highlights."""
    lum = (rgb @ np.array([0.3, 0.59, 0.11], np.float32))[..., None]
    rgb = lum + (rgb - lum) * 0.82
    shadow = np.array([0.16, 0.15, 0.08], np.float32); light = np.array([0.98, 0.86, 0.6], np.float32)
    rgb = rgb + (shadow - rgb) * (1 - lum) ** 3 * 0.35 + (light - rgb) * lum ** 3 * 0.2
    return rgb


def canvas(H, W, amount=0.06):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    weave = np.sin(x * 2 * np.pi / 4.0) * np.sin(y * 2 * np.pi / 4.0) * 0.5
    paper = blur(RNG.standard_normal((H, W)).astype(np.float32), 1.2)
    paper /= paper.std() + 1e-6
    mottle = blur(RNG.standard_normal((H // 8, W // 8)).astype(np.float32), 3)
    mottle = np.asarray(Image.fromarray(mottle).resize((W, H), Image.BICUBIC))
    mottle /= mottle.std() + 1e-6
    return 1 + amount * (0.4 * weave + 0.35 * paper + 0.6 * mottle)


def strokes(H, W, amount=0.05):
    """Directional brush texture: noise smeared along a slowly turning angle."""
    n = RNG.standard_normal((H, W)).astype(np.float32)
    out = np.zeros_like(n)
    for d in range(-6, 7):
        out += np.roll(np.roll(n, d, 1), d // 2, 0)
    out /= out.std() + 1e-6
    return 1 + amount * out


def varnish(rgb):
    H, W = rgb.shape[:2]
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    v = ((x / W - 0.5) ** 2 + (y / H - 0.5) ** 2) ** 0.5
    vig = 1 - 0.45 * np.clip(v - 0.25, 0, 1) ** 1.5 * 2
    tint = np.array([1.0, 0.94, 0.8], np.float32)
    return rgb * tint * vig[..., None]


def paint(rgb):
    rgb = kuwahara(rgb, 6)
    rgb = kuwahara(rgb, 3)
    rgb = grade(rgb)
    H, W = rgb.shape[:2]
    rgb = rgb * canvas(H, W)[..., None] * strokes(H, W)[..., None]
    return varnish(rgb)


def dither(rgb, spread=0.1):
    H, W = rgb.shape[:2]
    th = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W, None]
    x = np.clip(rgb + th * spread, 0, 1)
    wgt = np.array([0.35, 0.45, 0.2], np.float32)
    d = (((x[:, :, None, :] - PAL[None, None]) ** 2) * wgt).sum(-1)
    return d.argmin(-1)


def clean(idx):
    """Pixels unlike all four neighbours join the most common neighbour: deliberate clusters."""
    n = [np.roll(idx, 1, 0), np.roll(idx, -1, 0), np.roll(idx, 1, 1), np.roll(idx, -1, 1)]
    lonely = (idx != n[0]) & (idx != n[1]) & (idx != n[2]) & (idx != n[3])
    st = np.stack(n, -1)
    pick = np.apply_along_axis(lambda v: np.bincount(v).argmax(), -1, st[lonely]) if lonely.any() else []
    out = idx.copy(); out[lonely] = pick
    return out


def down(a, w, h):
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BOX)).astype(np.float32) / 255


def up(a, k):
    return np.repeat(np.repeat(a, k, 0), k, 1)


def outline(idx, mask, col=0):
    pad = np.pad(mask, 1)
    edge = mask & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    idx = idx.copy(); idx[edge] = col
    return idx


def main():
    art = load('scene-art.png')[..., :3]
    mask = load('scene-mask.png')[..., 0] > 0.5
    H, W = art.shape[:2]

    # A classic
    A = paint(art)
    save(A, 'A-art.png')

    # B pixel: from the painting, so it reads as the same illustration
    w, h = 160, 128
    small = down(A, w, h)
    m = down(mask[..., None].repeat(3, -1).astype(np.float32), w, h)[..., 0] > 0.5
    idx = clean(dither(small, 0.12))
    idx = outline(idx, m, 0)
    save(up(PAL[idx], 8), 'B-art.png')

    # C hybrid: pixel desert behind a painted monkey with a stepped pixel edge
    k = 5
    bg = PAL[clean(dither(down(A, W // k, H // k), 0.1))]
    bg = up(bg, k)[:H, :W]
    ms = down(mask[..., None].repeat(3, -1).astype(np.float32), W // k, H // k)[..., 0] > 0.5
    ring = outline(np.zeros(ms.shape, int) + 1, ms, 0) == 0
    m_up = up(ms, k)[:H, :W]; ring_up = up(ring, k)[:H, :W]
    C = np.where(m_up[..., None], A[:m_up.shape[0], :m_up.shape[1]], bg)
    C[ring_up] = PAL[1]
    C = C * canvas(*C.shape[:2], 0.04)[..., None]
    save(C, 'C-art.png')

    # mascots (transparent, monkey + hoard only)
    if os.path.exists(os.path.join(R, 'scene-mascot.png')):
        ms_ = load('scene-mascot.png'); rgb, al = ms_[..., :3], ms_[..., 3]
        pa = paint(rgb)
        save(np.dstack([pa, al]), 'A-mascot.png')
        s = 160
        sm = down(pa * al[..., None], s, s); sa = down(al[..., None].repeat(3, -1), s, s)[..., 0]
        solid = sa > 0.5
        sm = sm / np.maximum(sa[..., None], 1e-3)
        idx = clean(dither(sm, 0.12)); idx = outline(idx, solid, 0)
        save(np.dstack([up(PAL[idx], 10), up(solid.astype(np.float32), 10)]), 'B-mascot.png')
        k = 8
        sa = down(al[..., None].repeat(3, -1), al.shape[1] // k, al.shape[0] // k)[..., 0] > 0.5
        ring = outline(np.zeros(sa.shape, int) + 1, sa, 0) == 0
        a_up = up(sa, k).astype(np.float32); r_up = up(ring, k)
        Cm = pa.copy(); Cm[r_up] = PAL[1]
        save(np.dstack([Cm, a_up]), 'C-mascot.png')


if __name__ == '__main__':
    main()
