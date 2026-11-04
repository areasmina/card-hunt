"""B, The Rooftop Thief: native pixel art, built pixel by pixel at 160x128 (never downscaled).

Every part is drawn at its final pixel size: colour ramps of 3-5 shades, form shading quantised to
the ramp with ordered dither only at band edges, coloured (selective) outlines, single-pixel stars
and window lights. Output: art/B-art-native.png (160x128), B-art.png (x8), B-sprite* (the monkey alone).

python3 pixel.py
"""
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'art'); os.makedirs(OUT, exist_ok=True)

HEX = {
    'out': '#0a0806',
    'n0': '#0c0a14', 'n1': '#161428', 'n2': '#221d3a', 'n3': '#33284c', 'n4': '#4a3658',
    'm0': '#b8a478', 'm1': '#e8d8a8', 'm2': '#fff2c8',
    'g0': '#5a2e2a', 'g1': '#9a4a2a', 'g2': '#d0782e', 'g3': '#f2b04c',
    'b0': '#0f0c10', 'b1': '#1e1820', 'b2': '#33282c', 'b3': '#4a3a36', 'b4': '#6e5446',
    'd0': '#3e2a12', 'd1': '#6a4a1c', 'd2': '#9a7028', 'd3': '#c89a3e', 'd4': '#f0d070',
    'f0': '#1e120a', 'f1': '#3a2214', 'f2': '#5e3a20', 'f3': '#8a5a32', 'f4': '#b07a44',
    's0': '#5e3c2a', 's1': '#8e6248', 's2': '#bc8c68', 's3': '#e0b48c',
    'h0': '#3e3420', 'h1': '#6e5e3a', 'h2': '#a08c5a', 'h3': '#d0bc86',
    'r0': '#3a0e0c', 'r1': '#6e1c16', 'r2': '#a8382a', 'r3': '#d86040',
    'k0': '#0c0c0c', 'k1': '#2a2620', 'w0': '#d8c8a0',
}
NAMES = list(HEX)
ID = {k: i for i, k in enumerate(NAMES)}
RGB = np.array([[int(HEX[k][i:i + 2], 16) for i in (1, 3, 5)] for k in NAMES], np.uint8)
RAMP = {k: [ID[f'{k}{i}'] for i in range(10) if f'{k}{i}' in ID] for k in 'nmgbdfshr'}

W, H = 160, 128
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
B4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16
BAY = np.tile(B4, (H // 4 + 1, W // 4 + 1))[:H, :W]
LIGHT = np.array([0.55, -0.62, 0.56]); LIGHT /= np.linalg.norm(LIGHT)   # the moon, upper right
RIM = np.array([-0.7, 0.6, 0.3]); RIM /= np.linalg.norm(RIM)            # lanterns, low left

img = np.full((H, W), ID['n0'], np.int32)
owner = np.zeros((H, W), np.int32)      # which part owns a pixel (for selective outlines)
PARTS = {}


def ramp_pick(ramp, t, dither=0.22):
    """Map light 0..1 to a ramp index; dither only near band edges (authentic band transitions)."""
    n = len(ramp)
    v = np.clip(t, 0, 0.999) * n
    base = np.floor(v); frac = v - base
    up = (frac > 1 - dither) & (BAY[:t.shape[0], :t.shape[1]] < (frac - (1 - dither)) / dither * 0.5)
    i = np.clip(base + up, 0, n - 1).astype(int)
    return np.array(ramp)[i]


def put(mask, col, part=0):
    img[mask] = col if np.isscalar(col) else col[mask]
    if part:
        owner[mask] = part


def ellipse_n(cx, cy, rx, ry, rot=0.0):
    c, s = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
    u = (dx * c + dy * s) / rx; v = (-dx * s + dy * c) / ry
    r2 = u * u + v * v
    nx = u * c - v * s; ny = u * s + v * c
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    return r2 <= 1, np.dstack([nx, ny, nz])


def capsule_n(a, b, r):
    a, b = np.array(a, np.float32), np.array(b, np.float32)
    p = np.dstack([xx + 0.5, yy + 0.5])
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    q = a + t[..., None] * ab
    d = (p - q) / r
    r2 = (d ** 2).sum(-1)
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    return r2 <= 1, np.dstack([d[..., 0], d[..., 1], nz])


def shade(mask, n, ramp, part, rim_col=None, amb=0.18, gain=0.95):
    lit = np.clip(n @ LIGHT, 0, 1) * gain + amb
    col = ramp_pick(ramp, lit)
    if rim_col is not None:
        rim = (n @ RIM) > 0.62
        col = np.where(rim, rim_col, col)
    put(mask, col, part)
    PARTS[part] = ramp


def blob(cx, cy, rx, ry, rot, ramp, part, rim=None, mask_extra=None, **kw):
    m, n = ellipse_n(cx, cy, rx, ry, rot)
    if mask_extra is not None:
        m &= mask_extra
    shade(m, n, ramp, part, rim, **kw)
    return m


def limb(a, b, r, ramp, part, rim=None, **kw):
    m, n = capsule_n(a, b, r)
    shade(m, n, ramp, part, rim, **kw)
    return m


# ---------------------------------------------------------------- sky, moon, stars
def sky():
    bands = [(0, 'n0'), (22, 'n1'), (44, 'n2'), (64, 'n3'), (80, 'n4'), (90, 'g0')]
    for (y0, c0), (y1, c1) in zip(bands, bands[1:]):
        sel = (yy >= y0) & (yy < y1)
        t = (yy - y0) / (y1 - y0)
        img[sel & (BAY > t)] = ID[c0]; img[sel & (BAY <= t)] = ID[c1]
    img[yy >= 90] = ID['g0']
    # moon halo, dithered rings
    d = np.hypot(xx - 122, yy - 30)
    img[(d < 30) & (d >= 24) & (BAY < 0.35) & (yy < 80)] = ID['n3']
    img[(d < 24) & (BAY < 0.5)] = ID['n4']
    # crescent: disc minus offset disc, ramp from the lit outer edge
    disc = d <= 17
    cut = np.hypot(xx - 129, yy - 25) <= 14.5
    cres = disc & ~cut
    img[cres] = ID['m1']
    img[cres & (d >= 15.5)] = ID['m0']
    img[cres & (np.hypot(xx - 129, yy - 25) <= 16.5)] = ID['m0']
    img[cres & (d < 14) & (np.hypot(xx - 129, yy - 25) > 17.5)] = ID['m2']
    for x, y in ((112, 38), (116, 42), (110, 30)):            # craters
        if cres[y, x]:
            img[y, x] = ID['m0']
    rng = np.random.default_rng(42)
    for _ in range(70):
        x, y = rng.integers(0, W), rng.integers(0, 70)
        if np.hypot(x - 122, y - 30) > 26:
            img[y, x] = ID['m2'] if rng.random() < 0.3 else ID['m0']
    for x, y in ((22, 14), (64, 8), (148, 60), (40, 40)):     # twinkles
        img[y, x] = ID['m2']
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            img[y + dy, x + dx] = ID['m0']


# ---------------------------------------------------------------- the city
def city():
    rng = np.random.default_rng(7)
    base = 96
    xs = list(range(-4, W + 8, 13))
    for x in xs:
        h = int(rng.integers(6, 16)); w = int(rng.integers(8, 12))
        top = base - h
        bodyr = (xx >= x) & (xx < x + w) & (yy >= top) & (yy < base + 8)
        img[bodyr] = ID['b1']
        img[bodyr & (xx == x + w - 1)] = ID['b2']                  # moonlit edge
        if rng.random() < 0.7:
            dm = ((xx - (x + w / 2)) / (w / 2 + 1)) ** 2 + ((yy - top) / 6) ** 2 <= 1
            dm &= yy <= top
            img[dm] = ID['b1']
            img[dm & (xx >= x + w / 2 + 1) & (BAY < 0.5)] = ID['b2']
            img[(xx == int(x + w / 2)) & (yy >= top - 9) & (yy < top - 5)] = ID['b1']
        for _ in range(int(rng.integers(0, 3))):
            wx, wy = x + int(rng.integers(1, w - 1)), top + int(rng.integers(2, max(3, h)))
            if 0 <= wx < W and 0 <= wy < H:
                img[wy, wx] = ID['g3']
    for mx in (34, 118):                                           # minarets
        img[(xx >= mx) & (xx < mx + 3) & (yy >= 66) & (yy < 96)] = ID['b1']
        img[(xx == mx + 2) & (yy >= 66) & (yy < 96)] = ID['b2']
        img[(np.abs(xx - mx - 1) <= (yy - 58) / 3) & (yy >= 58) & (yy < 66)] = ID['b1']
        img[(xx >= mx - 1) & (xx < mx + 4) & (yy == 74)] = ID['b2']
        img[70, mx + 1] = ID['g3']
    # haze over the far city (dithered)
    img[(yy >= 92) & (yy < 100) & (BAY < 0.3)] = ID['g0']


# ---------------------------------------------------------------- foreground roofs
def roofs():
    # big gold dome, bottom left, lit by the moon from the upper right
    m, n = ellipse_n(26, 124, 34, 26)
    m &= yy <= 124
    shade(m, n, RAMP['d'], 1, rim_col=ID['g1'], amb=0.02, gain=0.78)
    PARTS[1] = RAMP['d']
    for k in range(-30, 31, 10):                                   # ribs
        rib = m & (np.abs((xx - 26) - k * np.sqrt(np.clip(1 - ((yy - 124) / 26) ** 2, 0, 1))) < 0.6)
        img[rib] = ID['d1']
    img[(xx >= 25) & (xx <= 27) & (yy >= 92) & (yy < 99)] = ID['d2']   # finial
    img[(xx == 26) & (yy >= 86) & (yy < 92)] = ID['d3']
    img[86, 26] = ID['d4']
    m2, n2 = ellipse_n(26, 96, 3, 3)
    shade(m2, n2, RAMP['d'], 1)
    # flat roof with parapet, bottom right, and a glowing arched window
    wall = (xx >= 104) & (yy >= 108)
    img[wall] = ID['b3']
    img[wall & (yy >= 108) & (yy < 110)] = ID['b4']
    img[wall & (xx == 104)] = ID['b2']
    for bx in range(108, W, 8):                                    # crenellations
        img[(xx >= bx) & (xx < bx + 4) & (yy >= 104) & (yy < 108)] = ID['b3']
        img[(xx >= bx) & (xx < bx + 4) & (yy == 104)] = ID['b4']
    win = (xx >= 122) & (xx < 132) & (yy >= 114) & (yy < 128)
    win |= (((xx - 127) / 5) ** 2 + ((yy - 114) / 5) ** 2 <= 1) & (yy < 114)
    img[win] = ID['g2']
    img[win & (np.abs(xx - 127) < 2.5) & (yy >= 116)] = ID['g3']
    # lantern string from the dome finial to the roof
    for x in range(27, 108):
        t = (x - 27) / 81
        y = int(round(87 + (106 - 87) * t + 14 * np.sin(np.pi * t)))
        img[y, x] = ID['b0']
        if x % 9 == 4:
            img[y + 1, x] = ID['g3']; img[y + 2, x] = ID['g2']
            for dx, dy in ((-1, 1), (1, 1), (0, 3)):
                if BAY[y + dy, x + dx] < 0.6:
                    img[y + dy, x + dx] = ID['g1']


# ---------------------------------------------------------------- the monkey, mid-leap
K, C0, C1 = 1.4, (80, 62), (74, 58)       # monkey scale and placement


def T(p):
    return (C1[0] + (p[0] - C0[0]) * K, C1[1] + (p[1] - C0[1]) * K)


def mlimb(a, b, r, *aa, **kw):
    return limb(T(a), T(b), r * K, *aa, **kw)


def mblob(cx, cy, rx, ry, *aa, **kw):
    x, y = T((cx, cy))
    return blob(x, y, rx * K, ry * K, *aa, **kw)


def mpx(y, x, col):
    X, Y = T((x + 0.5, y + 0.5))
    img[int(Y), int(X)] = col


def monkey():
    F, S, Hh, R, D = RAMP['f'], RAMP['s'], RAMP['h'], RAMP['r'], RAMP['d']
    warm = ID['g1']
    # tail first (behind), curling up and back, holding the magnifier
    pts = []
    for i in range(30):
        t = i / 29
        a = np.pi * (1.05 + 1.25 * t)
        r = 16 - 9 * t
        pts.append((60 + r * np.cos(a) * 1.1, 52 + r * np.sin(a) * 0.9 - 6 * t))
    for k in range(len(pts) - 1):
        mlimb(pts[k], pts[k + 1], 1.9 - 0.7 * k / 29, F, 10, warm)
    tip = T(pts[-1]); lc = (tip[0] - 4 * K, tip[1] - 6 * K)
    m, n = ellipse_n(lc[0], lc[1], 5 * K, 5 * K)
    lens = ellipse_n(lc[0], lc[1], 3.6 * K, 3.6 * K)[0]
    shade(m & ~lens, n, D, 11)
    img[lens] = ID['n3']; owner[lens] = 11
    img[lens & (np.hypot(xx - lc[0] + 1.5 * K, yy - lc[1] + 1.5 * K) < 1.2 * K)] = ID['m1']
    img[int(lc[1] - 2 * K), int(lc[0] - 1 * K)] = ID['m2']
    # far leg (trailing back, darker)
    mlimb((72, 70), (64, 78), 2.6, F[:-1], 12, warm, amb=0.08, gain=0.7)
    mlimb((64, 78), (57, 81), 2.2, F[:-1], 12, warm, amb=0.08, gain=0.7)
    mblob(55, 81, 3, 2, -10, S[:-1], 13, amb=0.1, gain=0.7)
    # scarf streaming back
    for i in range(26):
        t = i / 25
        x = 88 - 30 * t; y = 58 - 6 * t + 2.5 * np.sin(t * 7)
        mlimb((x, y), (x - 1.5, y + 0.3), 2.2 - 0.9 * t, R, 14, ID['r3'])
    # body, at a rising diagonal
    mblob(78, 64, 11, 7, -18, F, 15, warm)
    mblob(80, 66, 6, 4, -18, S, 16, amb=0.25)                     # belly
    # near leg, stretched back
    mlimb((70, 67), (61, 71), 3.2, F, 17, warm)
    mlimb((61, 71), (52, 70), 2.6, F, 17, warm)
    mblob(49, 70, 3.4, 2.2, 10, S, 18)
    # reaching arm, toward the next roof
    mlimb((86, 60), (96, 64), 2.4, F, 19, warm)
    mlimb((96, 64), (104, 63), 2.0, F, 19, warm)
    mblob(106, 63, 2.6, 2.2, 0, S, 20)
    # the card clutched to the chest
    (cx0, cy0), (cx1, cy1) = T((82, 60)), T((89, 70))
    cx0, cy0, cx1, cy1 = int(cx0), int(cy0), int(cx1), int(cy1)
    card = (xx >= cx0) & (xx < cx1) & (yy >= cy0) & (yy < cy1)
    img[card] = ID['k0']; owner[card] = 21
    ah = cy0 + 1 + (cy1 - cy0) * 4 // 10
    img[(xx > cx0) & (xx < cx1 - 1) & (yy > cy0) & (yy < ah)] = ID['g2']
    img[(xx > cx0) & (xx < cx1 - 1) & (yy == cy0 + 1)] = ID['g3']
    img[(xx > cx0) & (xx < cx1 - 1) & (yy == cy0 + 2) & (xx > cx1 - 4)] = ID['m2']
    img[(xx > cx0) & (xx < cx1 - 1) & (yy > ah) & (yy < cy1 - 1)] = ID['w0']
    for r_ in range(ah + 2, cy1 - 2, 2):
        img[r_, cx0 + 2:cx1 - 3] = ID['k1']
    mlimb((84, 70), (88, 67), 1.9, F, 22, warm)                    # holding arm
    mblob(87, 66, 2.3, 2.0, 0, S, 22)
    # head
    mblob(93, 54, 7, 6.6, 0, F, 23, warm)
    mblob(88, 53, 2.6, 2.6, 0, F, 24)                              # ear
    mpx(53, 88, ID['s1'])
    mblob(97.5, 57, 4.2, 3.2, -8, S, 25)                           # muzzle
    mblob(95.5, 53, 2.8, 2.2, 0, S, 25)                            # eye mask
    ex, ey = T((95.6, 53.2)); ex, ey = int(ex), int(ey)
    img[ey, ex] = ID['g3']; img[ey, ex + 1] = ID['out']; img[ey + 1, ex] = ID['g2']; img[ey + 1, ex + 1] = ID['out']
    img[ey, ex + 1] = ID['out']; img[ey - 1, ex + 1] = ID['m2'] if False else img[ey - 1, ex + 1]
    img[ey, ex] = ID['m2']                                        # glint
    img[ey - 2, ex - 1:ex + 3] = ID['f0']                         # brow, a sly slant
    img[ey - 3, ex + 2] = ID['f0']
    nx_, ny_ = T((100.3, 56.3)); img[int(ny_), int(nx_)] = ID['out']
    gx, gy = T((97.5, 58.5)); gx, gy = int(gx), int(gy)
    img[gy, gx:gx + 3] = ID['s0']; img[gy - 1, gx + 3] = ID['out']; img[gy, gx + 3] = ID['s0']
    # pith hat, tipped forward
    hc = T((93, 49)); bc = T((93, 50))
    crown, nc = ellipse_n(hc[0], hc[1], 7.5 * K, 5.5 * K, -12)
    crown &= (yy - hc[1]) * np.cos(np.radians(12)) - (xx - hc[0]) * np.sin(np.radians(-12)) <= 0.6
    shade(crown, nc, Hh, 26)
    brim, nb = ellipse_n(bc[0], bc[1], 11 * K, 2.2 * K, -12)
    shade(brim, nb, Hh, 27, amb=0.3)
    band = crown & (np.abs((yy - hc[1] + 1.4 * K) - (xx - hc[0]) * np.tan(np.radians(-12))) < 0.9 * K)
    img[band] = ID['r1']


def outlines():
    """Selective outline: a part's edge takes the darkest shade of its own ramp; against sky, near-black."""
    part = owner
    solid = part > 0
    edge = np.zeros_like(solid)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(np.roll(part, dy, 0), dx, 1)
        edge |= solid & (nb == 0)
    out = img.copy()
    for p, ramp in PARTS.items():
        sel = edge & (part == p)
        out[sel] = ramp[0]
    # outer silhouette against the sky gets a true dark line one pixel outside
    ring = np.zeros_like(solid)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= ~solid & np.roll(np.roll(solid & (part >= 10), dy, 0), dx, 1)
    out[ring & (yy < 100)] = ID['out']
    return out


def main():
    sky(); city(); roofs(); monkey()
    final = outlines()
    native = Image.fromarray(RGB[final], 'RGB')
    native.save(os.path.join(OUT, 'B-art-native.png'))
    native.resize((W * 8, H * 8), Image.NEAREST).save(os.path.join(OUT, 'B-art.png'))
    # the monkey alone as a sprite (transparent), cropped tight
    m = owner >= 10
    ys, xs_ = np.where(m)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs_.min() - 2, xs_.max() + 3
    sp = np.zeros((H, W, 4), np.uint8); sp[..., :3] = RGB[final]
    ring = np.zeros_like(m)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= np.roll(np.roll(m, dy, 0), dx, 1)
    sp[..., 3] = (m | ring) * 255
    sp[ring & ~m, :3] = RGB[ID['out']]
    spr = Image.fromarray(sp[y0:y1, x0:x1], 'RGBA')
    spr.save(os.path.join(OUT, 'B-sprite-native.png'))
    spr.resize((spr.width * 10, spr.height * 10), Image.NEAREST).save(os.path.join(OUT, 'B-mascot.png'))
    print('pixel art done', spr.size)


if __name__ == '__main__':
    main()
