"""Card Hunt badge, 3D version: one circle, the card tilting in front with real thickness and a cast
shadow, and a cartoon glove reaching for it from the depth behind, growing and brightening as it nears.
Native 64x64 pixel art in the card spin's own greys; card and hand are projected in perspective,
supersampled, then snapped to the palette (no smooth gradients survive).
python3 badge3d.py <card-spin frames dir> -> badge3d.webp (x3), badge3d.png, badge3d-sheet.png
"""
import sys, os, math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
N, SS = 64, 4
PAL = [(12, 12, 10), (29, 28, 21), (56, 54, 47), (88, 86, 77), (139, 137, 126), (191, 188, 176), (238, 235, 224)]
P = np.array(PAL, np.float32)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + .5) / 16
FROST = np.array((136, 192, 208), np.float32)

# the glove, reused from the flat badge (k outline, w white, l shade, d sleeve)
from importlib import util
spec = util.spec_from_file_location('flat', os.path.join(HERE, 'badge.py'))
src = open(os.path.join(HERE, 'badge.py')).read()
HAND_OPEN = src.split('HAND_OPEN = """')[1].split('"""')[0]
HAND_GRAB = src.split('HAND_GRAB = """')[1].split('"""')[0]
HC = {'k': (29, 28, 21), 'w': (238, 235, 224), 'l': (191, 188, 176), 'd': (56, 54, 47), 'm': (88, 86, 77)}


def sprite(txt):
    rows = txt.strip('\n').split('\n'); w = max(len(r) for r in rows)
    a = np.zeros((len(rows), w, 4), np.uint8)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in HC:
                a[y, x] = HC[c] + (255,)
    return Image.fromarray(a, 'RGBA')


def snap(rgb, dither=0.0, yy=None, xx=None):
    x = rgb.copy()
    if dither:
        x = x + ((BAYER[yy % 4, xx % 4] - .5) * dither)[..., None]
    d = ((x[..., None, :] - P) ** 2).sum(-1)
    return P[d.argmin(-1)]


def face():
    """the card's front face, taken from the first frame of the spin (it faces the camera there)"""
    im = Image.open(os.path.join(sys.argv[1], 'f001.png')).convert('RGBA').crop((33, 13, 127, 153))
    return im


def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = np.array([c for p in dst for c in p], np.float64)
    return np.linalg.solve(np.array(A, np.float64), b)


def project(pts, ry, rx, cx, cy, f=90.0, dist=90.0):
    out = []
    for x, y, z in pts:
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        s = f / (dist + z)
        out.append((cx + x * s, cy + y * s))
    return out


def warp(img, quad, size):
    """paint img onto quad (4 points, clockwise from top-left) on a size x size canvas"""
    w, h = img.size
    coeffs = homography(quad, [(0, 0), (w, 0), (w, h), (0, h)])
    return img.transform((size, size), Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)


def poly_mask(quad, size):
    m = Image.new('L', (size, size), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(m).polygon(quad, fill=255)
    return m


def frame(i, n, card, hopen, hgrab):
    t = i / n
    S = N * SS
    yy, xx = np.mgrid[0:N, 0:N]
    c = N / 2; r = np.hypot(xx + .5 - c, yy + .5 - c)
    inside = r <= 31.5
    # ---- one circle: deep in the middle, lighter at the rim, so it reads as a tunnel into the dark
    depth = np.clip(r / 31.5, 0, 1)
    lv = 0.2 + 2.6 * depth ** 1.6
    bg = P[np.clip(np.round(lv + (BAYER[yy % 4, xx % 4] - .5) * .8), 0, 6).astype(int)]
    bg[(r > 30.6) & inside] = PAL[1]                                  # the single outline
    # a faint frost glow deep in the centre: the place the hand comes from
    glow = np.exp(-((xx - 34) ** 2 + (yy - 26) ** 2) / 60.0)
    pick = (glow > .45) & (BAYER[yy % 4, xx % 4] < glow * .55)
    bg[pick] = bg[pick] * .4 + FROST * .6

    # ---- timeline: the hand comes out of the depth, grabs at the card, slips back
    if t < .15:      k = 0.0
    elif t < .5:     k = (t - .15) / .35
    elif t < .64:    k = 1.0
    elif t < .82:    k = 1 - (t - .64) / .18
    else:            k = 0.0
    ease = k * k * (3 - 2 * k)
    grabbing = .52 < t < .64
    # card: a slow sway in 3D, leaning back towards the hand while it's held
    ry = math.radians(34 * math.sin(t * 2 * math.pi) + (6 if grabbing else 0))
    rx = math.radians(14 + 6 * math.sin(t * 4 * math.pi) - (6 if grabbing else 0))
    bob = 1.2 * math.sin(t * 2 * math.pi * 2)
    cw, ch, th = 19, 28, 1.6
    ccx, ccy = 30 * SS, (33 + bob + (1.5 if grabbing else 0)) * SS
    corners = [(-cw / 2, -ch / 2, 0), (cw / 2, -ch / 2, 0), (cw / 2, ch / 2, 0), (-cw / 2, ch / 2, 0)]
    front = project(corners, ry, rx, ccx / SS, ccy / SS)
    back = project([(x, y, th) for x, y, _ in corners], ry, rx, ccx / SS, ccy / SS)
    shadow = project([(x, y, 10) for x, y, _ in corners], ry, rx, ccx / SS + 4, ccy / SS + 5)
    F = [(x * SS, y * SS) for x, y in front]; B = [(x * SS, y * SS) for x, y in back]; SH = [(x * SS, y * SS) for x, y in shadow]

    canvas = Image.fromarray(np.dstack([bg, inside * 255]).astype(np.uint8), 'RGBA').resize((S, S), Image.NEAREST)

    # ---- the hand, behind everything that is the card: scale and brightness follow depth
    if ease > .02:
        spr = hgrab if grabbing else hopen
        sc = 0.4 + 0.75 * ease                                         # far = small
        w, h = spr.size
        hs = spr.resize((max(1, round(w * sc * SS)), max(1, round(h * sc * SS))), Image.NEAREST)
        # foreshortening: the hand leans in, so squash it a little and tilt it towards the card
        hs = hs.rotate(-12 + 12 * ease, resample=Image.NEAREST, expand=True)
        a = np.asarray(hs).astype(np.float32)
        fog = 1 - ease                                                  # far = sunk into the dark
        a[..., :3] = a[..., :3] * (1 - .75 * fog) + np.array(PAL[1]) * .75 * fog
        hs = Image.fromarray(a.astype(np.uint8), 'RGBA')
        hx = (33 + 2 * ease) * SS - hs.width / 2                        # drifts up and right, towards the card's top corner
        hy = (30 - 12 * ease + (4 if grabbing else 0)) * SS - hs.height / 2
        canvas.alpha_composite(hs, (int(hx), int(hy)))

    # ---- cast shadow on the tunnel wall, then the card's thickness, then its face
    sh = Image.new('RGBA', (S, S), (12, 12, 10, 150)); canvas.paste(sh, (0, 0), poly_mask(SH, S))
    edge = Image.new('RGBA', (S, S), PAL[2] + (255,))
    canvas.paste(edge, (0, 0), poly_mask(B, S))
    for a_, b_ in zip(range(4), [1, 2, 3, 0]):                          # side walls between front and back
        canvas.paste(edge, (0, 0), poly_mask([F[a_], F[b_], B[b_], B[a_]], S))
    showing_front = (F[1][0] - F[0][0]) * (F[3][1] - F[0][1]) - (F[1][1] - F[0][1]) * (F[3][0] - F[0][0]) > 0
    canvas.alpha_composite(warp(card, F, S))
    # ---- back to native pixels: box down, snap to the palette, crisp alpha, clip to the one circle
    small = canvas.resize((N, N), Image.BOX)
    a = np.asarray(small).astype(np.float32)
    rgb = snap(a[..., :3], 10.0, yy, xx)
    keep = (a[..., 3] > 100) & inside
    rgb[~inside] = 0
    rgb[(r > 30.6) & inside] = PAL[1]
    return Image.fromarray(np.dstack([rgb, keep * 255]).astype(np.uint8), 'RGBA')


def main():
    card = face()
    hopen, hgrab = sprite(HAND_OPEN), sprite(HAND_GRAB)
    n = 72
    fr = [frame(i, n, card, hopen, hgrab) for i in range(n)]
    big = [f.resize((N * 3, N * 3), Image.NEAREST) for f in fr]
    big[0].save(os.path.join(HERE, 'badge3d.webp'), save_all=True, append_images=big[1:], duration=110, loop=0, lossless=True)
    fr[int(n * .58)].resize((N * 3, N * 3), Image.NEAREST).save(os.path.join(HERE, 'badge3d.png'))
    sheet = Image.new('RGBA', (12 * 200, 200), (46, 52, 64, 255))
    for k in range(12):
        sheet.alpha_composite(fr[int(n * k / 12)].resize((192, 192), Image.NEAREST), (k * 200 + 4, 4))
    sheet.save(os.path.join(HERE, 'badge3d-sheet.png'))
    print('ok')


main()
