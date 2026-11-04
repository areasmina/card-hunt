"""Card Hunt classic card art: an airbrushed night scene in the manner of 1993-95 card illustration.

Composed by hand as shapes (sky, moon, city, ledge and the monkey's silhouette), lit with rim light
and glow, then given board grain and a soft print. No 3D render and no paint filter underneath.
python3 art.py [blue|black|white|artifact] -> art-<v>.png (1476x1180)
"""
import sys, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
V = sys.argv[1] if len(sys.argv) > 1 else 'blue'
W, H = 1476, 1180                 # final art window (2x of a 738x590 card art box)
SS = 2                            # supersample for clean silhouettes
U = W / 1000                      # design space is 1000 wide, 800 tall
rng = np.random.default_rng(7)

# sky palettes per frame colour: (top, mid, low, horizon, glow), rim colours (sky side, card side)
SKY = {
    'blue':     (('#070b24', '#1b2160', '#6a2f6e', '#d9542a', '#f6b04a'), '#ff9a48', '#9fc4ff'),
    'black':    (('#07060a', '#1a0d10', '#5a1a12', '#c2401c', '#f08a2e'), '#ff7a2e', '#7aa8ff'),
    'white':    (('#3a4a6a', '#8a8aa8', '#d8b8a0', '#f4d8a8', '#fff0c8'), '#ffe2a8', '#ffffff'),
    'artifact': (('#0b1416', '#1d3434', '#4f6a52', '#b88a3a', '#f0d070'), '#f0c060', '#c8f0d0'),
}[V]


def hexf(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


def blur(a, r):
    if r <= 0:
        return a
    im = Image.fromarray((np.clip(a, 0, 1) * 65535).astype(np.uint16).astype(np.int32), 'I')
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im).astype(np.float32) / 255


def blurf(a, r):
    """float blur keeping precision: blur in 3 bands"""
    out = np.zeros_like(a)
    lo = np.clip(a, 0, 1)
    return blur(lo, r)


def noise(scale, octaves=4, seed=0):
    g = np.random.default_rng(seed)
    acc = np.zeros((H, W), np.float32); amp = 1; tot = 0
    for o in range(octaves):
        s = max(2, int(scale / (2 ** o)))
        n = g.random((H // s + 2, W // s + 2)).astype(np.float32)
        n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((W + 2 * s, H + 2 * s), Image.BICUBIC))[:H, :W] / 255
        acc += n * amp; tot += amp; amp *= 0.5
    return acc / tot


class Mask:
    """A supersampled drawing surface in design units (1000 x 800)."""
    def __init__(self):
        self.im = Image.new('L', (W * SS, H * SS), 0); self.d = ImageDraw.Draw(self.im)

    def p(self, x, y):
        return (x * U * SS, y * U * SS)

    def poly(self, pts, fill=255):
        self.d.polygon([self.p(*q) for q in pts], fill=fill)

    def ell(self, cx, cy, rx, ry=None, fill=255, rot=0):
        ry = rx if ry is None else ry
        if rot == 0:
            a, b = self.p(cx - rx, cy - ry), self.p(cx + rx, cy + ry); self.d.ellipse([a, b], fill=fill); return
        pts = [(cx + rx * math.cos(t) * math.cos(rot) - ry * math.sin(t) * math.sin(rot),
                cy + rx * math.cos(t) * math.sin(rot) + ry * math.sin(t) * math.cos(rot)) for t in np.linspace(0, 2 * math.pi, 90)]
        self.poly(pts, fill)

    def stroke(self, pts, radii, fill=255, n=200):
        """tapered organic stroke through control points (Catmull-Rom), radius interpolated"""
        P = np.array(pts, np.float32); R = np.array(radii, np.float32)
        P = np.vstack([P[0], P, P[-1]])
        out = []
        for i in range(1, len(P) - 2):
            for t in np.linspace(0, 1, n // (len(P) - 3), endpoint=False):
                p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
                q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
                out.append(q)
        out.append(P[-2])
        rr = np.interp(np.linspace(0, 1, len(out)), np.linspace(0, 1, len(R)), R)
        for q, r in zip(out, rr):
            self.ell(q[0], q[1], r, fill=fill)

    def arr(self):
        return np.asarray(self.im.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255


def lerp_ramp(t, cols, stops):
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        m = (t >= a) & (t <= b)
        k = ((t - a) / (b - a))[m][:, None]
        out[m] = cols[i] * (1 - k) + cols[i + 1] * k
    return out


def over(img, col, a):
    a = np.clip(a, 0, 1)[..., None]
    return img * (1 - a) + np.asarray(col, np.float32) * a


def shift(a, dx, dy):
    return np.roll(np.roll(a, int(dy), 0), int(dx), 1)


# ---------------------------------------------------------------- sky
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
yd, xd = yy / U, xx / U                                  # design coords
top, mid, low, hor, glow = [hexf(c) for c in SKY[0]]
mott = noise(260, 4, 1)
t = (yd / 600) + (mott - 0.5) * 0.07
img = lerp_ramp(t, [top, mid, low, hor, glow], [0, 0.45, 0.72, 0.92, 1.0])
# a glow pooled behind the figure and the horizon
g = np.exp(-(((xd - 560) / 420) ** 2 + ((yd - 610) / 160) ** 2))
img = img + (glow - img) * (g[..., None] * 0.55)
# airbrushed cloud bands, soft and horizontal
for i, (cy, amp, th) in enumerate(((470, .35, 26), (520, .28, 18), (395, .2, 14))):
    band = np.exp(-((yd - cy - (noise(300, 3, 10 + i) - .5) * 60) / th) ** 2) * (noise(160, 4, 20 + i) > .48)
    band = blur(band.astype(np.float32), 10)
    img = over(img, hor * .7 + top * .3, band * amp)

# stars
sm = Mask()
for _ in range(170):
    x, y = rng.uniform(0, 1000), rng.uniform(0, 420) ** 1.0
    r = rng.choice([0.9, 1.1, 1.4, 2.0], p=[.5, .3, .15, .05])
    sm.ell(x, y, r)
st = sm.arr() * np.clip(1.15 - yd / 430, 0, 1)
img = over(img, (1, .97, .9), st)
img = over(img, (1, .95, .85), blur(st, 3) * .5)

# moon, upper left, with soft halo and faint maria
mx, my, mr = 205, 120, 52
md = np.sqrt((xd - mx) ** 2 + (yd - my) ** 2)
img = over(img, hexf('#f2e8c8') * .9 + glow * .1, np.exp(-((md - mr) / 120).clip(0) ** 1.3) * .22)
moon = blur(np.clip((mr - md) * U / 1.2, 0, 1), 1)
mc = np.ones_like(img) * hexf('#efe4c0')
maria = blur((noise(40, 3, 33) > .56).astype(np.float32), 4) * .25
mc = mc * (1 - maria[..., None] * np.array([.35, .35, .25]))
mc = mc * (1 - .25 * np.clip((xd - mx + 10) / mr, 0, 1)[..., None])        # shaded right limb
img = img * (1 - moon[..., None]) + mc * moon[..., None]

# ---------------------------------------------------------------- distant city (two depths)
def city(seed, base, hmin, hmax, step):
    m = Mask(); r = np.random.default_rng(seed); x = -20
    while x < 1020:
        w = r.uniform(step * .6, step * 1.5); h = r.uniform(hmin, hmax); kind = r.random()
        m.poly([(x, 800), (x, base - h), (x + w, base - h), (x + w, 800)])
        if kind < .28:                                   # onion dome
            cx = x + w / 2; rw = w * .55
            m.ell(cx, base - h - rw * .55, rw, rw * .85)
            m.poly([(cx - 2, base - h - rw * 1.3), (cx, base - h - rw * 2.1), (cx + 2, base - h - rw * 1.3)])
        elif kind < .45:                                 # minaret
            cx = x + w / 2
            m.poly([(cx - 7, base - h), (cx - 6, base - h - 90), (cx + 6, base - h - 90), (cx + 7, base - h)])
            m.ell(cx, base - h - 92, 11, 7); m.poly([(cx - 4, base - h - 98), (cx, base - h - 130), (cx + 4, base - h - 98)])
        elif kind < .6:                                  # battlement
            for k in range(int(w // 10)):
                m.poly([(x + k * 10, base - h), (x + k * 10, base - h - 8), (x + k * 10 + 5, base - h - 8), (x + k * 10 + 5, base - h)])
        x += w + r.uniform(-4, 6)
    return m.arr()


far = city(3, 640, 20, 70, 34)
img = over(img, top * .55 + hor * .25, far * .9)
near = city(5, 690, 30, 110, 46)
img = over(img, top * .35, near)
# a scatter of lit windows on the near city
wm = Mask()
for _ in range(60):
    x, y = rng.uniform(0, 1000), rng.uniform(600, 780)
    wm.poly([(x, y), (x + 3, y), (x + 3, y + 5), (x, y + 5)])
win = wm.arr() * near * (yd > 610)
img = over(img, hexf('#ffc860'), win)
img = over(img, hexf('#ff9a40'), blur(win, 4) * .6)

# ---------------------------------------------------------------- foreground ledge
lm = Mask()
edge = [(0, 652)]
for x in np.linspace(0, 640, 30)[1:]:
    edge.append((x, 650 + rng.uniform(-3, 3) + (6 if 300 < x < 360 else 0)))
edge += [(652, 664), (660, 700), (690, 800), (0, 800)]
lm.poly(edge)
for x in (40, 160, 280, 420, 540):                     # block joints are cut later
    pass
ledge = lm.arr()
lc = top * .25 + np.array([.02, .02, .03])
img = over(img, lc, ledge)
# stone joints and a lit top lip
jm = Mask()
for x in (90, 230, 370, 510):
    jm.poly([(x, 662), (x + 2, 662), (x + 3, 800), (x + 1, 800)])
for y in (712, 760):
    jm.poly([(0, y), (640, y + 4), (640, y + 6), (0, y + 2)])
img = over(img, lc * 1.8 + hexf(SKY[1]) * .06, jm.arr() * ledge * .5)
lip = np.clip(ledge - shift(ledge, 0, 5 * U), 0, 1)
img = over(img, hexf(SKY[1]), blur(lip, 1.2) * .75)

# ---------------------------------------------------------------- the monkey
mk = Mask()
# tail first (behind), a long S that ends in a curl
mk.stroke([(338, 585), (285, 620), (220, 610), (180, 560), (190, 500), (232, 478), (262, 500), (250, 530), (226, 524)],
          [12, 11, 10, 9, 8, 7, 6, 5, 4], n=420)
# far leg (behind), crouched
mk.stroke([(352, 560), (300, 575), (318, 640)], [30, 18, 11], n=120)
mk.stroke([(312, 640), (290, 652), (270, 653)], [9, 7, 5], n=60)
# torso, leaning forward
mk.stroke([(355, 565), (368, 500), (395, 440), (428, 395)], [44, 50, 46, 38], n=200)
# near leg: thigh up to knee, shin down to the foot gripping the lip
mk.stroke([(372, 560), (440, 528), (472, 520)], [36, 26, 18], n=160)
mk.stroke([(472, 520), (462, 585), (448, 640)], [17, 13, 10], n=140)
mk.stroke([(445, 645), (475, 652), (505, 654)], [10, 8, 5], n=80)
mk.stroke([(470, 650), (480, 664)], [4, 3], n=20)        # toes over the edge
mk.stroke([(490, 652), (500, 667)], [4, 3], n=20)
# neck and head, tilted up towards the card
mk.stroke([(430, 398), (452, 360)], [26, 24], n=40)
mk.ell(466, 332, 38, 37)                               # cranium
mk.ell(496, 326, 14, 10, rot=-0.4)                    # brow ridge
mk.ell(518, 336, 25, 17, rot=-0.35)                    # muzzle
mk.ell(539, 326, 9, 8, rot=-0.35)                      # nose
mk.stroke([(498, 352), (528, 348)], [9, 6], n=20)      # jaw
mk.ell(424, 354, 15, 17)                               # ear, below the brim
# pith helmet: dome plus a wide brim tilted back
mk.ell(462, 284, 44, 44, rot=-0.26)                    # tall helmet dome
mk.ell(470, 244, 6, 5)                                 # top button
mk.ell(466, 312, 74, 15, rot=-0.26)                    # brim, all the way round
mk.ell(466, 318, 66, 9, rot=-0.26)                     # brim droops a little
mk.stroke([(410, 330), (418, 318)], [5, 5], n=10)      # chin strap hint
# raised arm, long, to the card
mk.stroke([(430, 405), (500, 392), (556, 350), (628, 280), (684, 226)], [20, 15, 12, 9, 8], n=260)
mk.ell(692, 220, 14, 11, rot=-0.7)                     # hand
for k in range(3):
    mk.stroke([(694 + k * 3, 212 - k * 3), (704 + k * 4, 196 - k * 4)], [4, 3], n=12)
# lower arm, holding the magnifier out in front
mk.stroke([(410, 420), (446, 485), (502, 478)], [19, 14, 10], n=140)
mk.ell(510, 476, 11, 9)
body = mk.arr()

# magnifier: brass ring with glass and a handle
gm = Mask(); gm.stroke([(512, 474), (560, 448)], [5, 4], n=40)
handle = gm.arr()
lx, ly, lr = 590, 432, 30
ld = np.sqrt((xd - lx) ** 2 + (yd - ly) ** 2)
ring = np.clip((lr + 4 - ld) * U, 0, 1) * np.clip((ld - (lr - 4)) * U, 0, 1)
glass = np.clip((lr - 4 - ld) * U, 0, 1)

# the card, held up and glowing
cx, cy, cw, ch, ca = 716, 180, 58, 82, math.radians(14)
def card_mask(pad=0):
    m = Mask(); c, s = math.cos(ca), math.sin(ca)
    pts = [(-cw / 2 - pad, -ch / 2 - pad), (cw / 2 + pad, -ch / 2 - pad), (cw / 2 + pad, ch / 2 + pad), (-cw / 2 - pad, ch / 2 + pad)]
    m.poly([(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]); return m.arr()
card = card_mask(); card_in = card_mask(-6)

# --- light: a big golden bloom from the card, rays, and its light on the sky
cd = np.sqrt((xd - cx) ** 2 + (yd - cy) ** 2)
ang = np.arctan2(yd - cy, xd - cx)
rays = (0.5 + 0.5 * np.cos(ang * 9 + 0.6)) ** 6 * np.exp(-cd / 260) * (0.6 + 0.4 * noise(90, 2, 44))
img = over(img, hexf('#ffd890'), np.exp(-cd / 110) * .5 + rays * .14)

# --- the figure: deep blue-black body, fur texture, then rims
fur = noise(14, 2, 55)
bodyc = (top * .5 + np.array([.03, .03, .05])) * (0.85 + 0.3 * fur[..., None])
img = img * (1 - body[..., None]) + bodyc * body[..., None]
# sky-side rim (warm, from the horizon glow below-left) and card-side rim (cool-gold, from above-right)
def rim(m, dx, dy, w):
    e = np.clip(m - shift(m, dx * U, dy * U), 0, 1)
    return blur(e, w) * m
# rims from real edge normals, so each light only catches the edges that face it
def rims(m, L, width, power):
    bm = blur(m, 2.2 * U)
    gy, gx = np.gradient(blur(m, 4 * U))
    nl = np.sqrt(gx ** 2 + gy ** 2) + 1e-6
    nx, ny = -gx / nl, -gy / nl                          # outward normal
    band = np.clip((1 - blur(m, width * U)) * 2.4, 0, 1) * m
    return band * np.clip(nx * L[0] + ny * L[1], 0, 1) ** power
L_card = np.array([.72, -.69]); L_sky = np.array([-.55, .83])
bb = blur(body, 18 * U)
form = np.clip((bb - shift(bb, -14 * U, 14 * U)) * 1.6, 0, 1) * body * (1 - bb * .4)
img = over(img, hexf('#6a5070'), form * .35)
img = over(img, hexf(SKY[1]), rims(body, L_sky, 5, 1.6) * 1.0)
img = over(img, hexf('#ffe6a0'), rims(body, L_card, 5, 2) * np.clip(1.6 - cd / 460, 0, 1))
# a little modelling inside the silhouette: the face catches the card light
fm = Mask()
fm.ell(512, 336, 26, 18, rot=-0.35); fm.ell(500, 330, 15, 13); fm.ell(530, 330, 13, 10, rot=-0.35)
fm.d.line([fm.p(533, 346), fm.p(512, 349)], fill=0, width=int(3 * U * SS))
facem = blur(fm.arr(), 1.5) * body
shade = np.clip(((xd - 488) / 50) * .6 + ((330 - yd) / 30) * .4 + .4, .25, 1)
img = over(img, hexf('#c08a58') * shade[..., None] + hexf('#3a2030') * (1 - shade[..., None]), facem * .92)
ear = np.clip((10 - np.sqrt((xd - 426) ** 2 + (yd - 355) ** 2)) * U, 0, 1)
img = over(img, hexf('#6a3a3a'), blur(ear, 1.5) * .6)
hat = np.exp(-(((xd - 482) / 50) ** 2 + ((yd - 272) / 34) ** 2)) * body
img = over(img, hexf('#c89a58'), hat * .35)
# the eye: one small amber point under the brim, looking up at the card
for ex, ey, er in ((505, 331, 3.6),):
    e = np.clip((er - np.sqrt((xd - ex) ** 2 + (yd - ey) ** 2)) * U, 0, 1)
    img = over(img, hexf('#ffcc55'), blur(e, 3) * .8); img = over(img, hexf('#fff4c0'), e)

# magnifier on top of the body
img = over(img, bodyc.mean((0, 1)) * 1.2, handle)
img = over(img, hexf('#ffd890') * .35 + top * .5, glass * .55)
hl = np.clip((lr * .55 - np.sqrt((xd - lx + 10) ** 2 + (yd - ly + 10) ** 2)) * U / 3, 0, 1)
img = over(img, (1, .95, .8), blur(hl, 4) * .35 * glass)
img = over(img, hexf('#a87a30'), ring)
img = over(img, hexf('#ffe0a0'), ring * np.clip((ly - yd) / lr + .3, 0, 1) * .8)

# the card itself: dark frame, bright face
img = over(img, hexf('#1a1208'), card)
lit = np.clip(1 - np.abs((xd - cx) * math.cos(ca) + (yd - cy) * math.sin(ca)) / 40, 0, 1)
img = over(img, hexf('#ffe8a8') * .7 + hexf('#fffaf0') * .3, card_in)
img = over(img, hexf('#e8a040'), card_in * np.clip((yd - (cy - 20)) / 60, 0, 1) * .45)
img = over(img, (1, 1, .95), blur(card, 10) * .45)

# ---------------------------------------------------------------- finish: board grain, soft print
grain = (rng.random((H, W)).astype(np.float32) - .5)
board = noise(6, 2, 77) - .5
img = img * (1 + (board * .08 + grain * .05)[..., None])
img = np.clip(img, 0, 1)
out = Image.fromarray((img * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.6))
path = os.path.join(HERE, f'art-{V}.png'); out.save(path); print('wrote', path)
