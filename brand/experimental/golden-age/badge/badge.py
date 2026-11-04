"""Card Hunt round badge: a cartoon glove reaches out of a void for the spinning card.
Native pixel art at 64x64 in the card spin's own greys, upscaled by whole numbers only.
python3 badge.py <card-spin frames dir> -> badge.webp (animated, x3), badge.png (still), badge-sheet.png
"""
import sys, os, glob, math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
N = 64
PAL = {'k': (29, 28, 21), 'd': (56, 54, 47), 'm': (88, 86, 77), 'g': (139, 137, 126), 'l': (191, 188, 176), 'w': (238, 235, 224),
       'v': (12, 12, 10), 'f': (136, 192, 208)}           # f = Nord frost, only for the void's rim glow
P = np.array([PAL[c] for c in 'kdmglw'], np.float32)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + .5) / 16

HAND_OPEN = """
...kk..kk..kk.....
..kwwkkwwkkwwk....
..kwwkkwwkkwwk.kk.
..kwwkkwwkkwwkkwwk
..kwwkkwwkkwwkkwwk
..kwwkkwwkkwwkkwwk
..kwwwwwwwwwwkkwwk
kk.kwwwwwwwwwwwwwk
kwwkwwwwwwwwwwwwwk
kwwwwwwwwwwwwwwlk.
.kwwwwwwwwwwwwwlk.
..kwwwwwwwwwwwllk.
...kwwwwwwwwwllk..
....kkkkkkkkkkk...
...kwwwwwwwwwwwk..
..kwwlwwlwwlwwwwk.
..kwwwwwwwwwwwwlk.
...kkkkkkkkkkkkk..
.....kdddddddk....
.....kddmdddk.....
.....kdddddddk....
.....kddddmddk....
"""
HAND_GRAB = """
..................
..................
....kkkkkkkkk.....
...kwwkwwkwwkk....
..kwwkwwkwwkwwk...
..kwwkwwkwwkwwkk..
..kwwwwwwwwwwkwwk.
kk.kwwwwwwwwwwwwk.
kwwkwwwwwwwwwwwwk.
kwwwwwwwwwwwwwwlk.
.kwwwwwwwwwwwwwlk.
..kwwwwwwwwwwwllk.
...kwwwwwwwwwllk..
....kkkkkkkkkkk...
...kwwwwwwwwwwwk..
..kwwlwwlwwlwwwwk.
..kwwwwwwwwwwwwlk.
...kkkkkkkkkkkkk..
.....kdddddddk....
.....kddmdddk.....
.....kdddddddk....
.....kddddmddk....
"""


def sprite(txt):
    rows = [r for r in txt.strip('\n').split('\n')]
    w = max(len(r) for r in rows)
    out = np.zeros((len(rows), w, 4), np.uint8)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in PAL:
                out[y, x] = PAL[c] + (255,)
    return out


def snap(rgb):
    d = ((rgb[..., None, :] - P) ** 2).sum(-1)
    return P[d.argmin(-1)]


def card_frames(src):
    fs = sorted(glob.glob(os.path.join(src, 'f*.png')))
    out = []
    for f in fs:
        im = Image.open(f).convert('RGBA')
        bb = (33, 13, 127, 153)                       # the card's union box in the 160px frames
        im = im.crop(bb).resize((18, 27), Image.BOX)
        a = np.asarray(im).astype(np.float32)
        rgb = snap(a[..., :3]); al = a[..., 3] > 110
        out.append(np.dstack([rgb, al * 255]).astype(np.uint8))
    return out


def paste(dst, spr, x, y):
    h, w = spr.shape[:2]
    for j in range(h):
        for i in range(w):
            if spr[j, i, 3] and 0 <= y + j < N and 0 <= x + i < N:
                dst[y + j, x + i] = spr[j, i, :3]


def base():
    yy, xx = np.mgrid[0:N, 0:N] + .5
    c = N / 2; r = np.hypot(xx - c, yy - c)
    img = np.zeros((N, N, 3), np.float32); alpha = (r <= 31.5)
    # inside: dark slate, lighter towards the top (dithered bands, no gradients)
    t = np.clip((yy - 6) / 52, 0, 1)
    lv = 1.9 - 1.6 * t + (BAYER[yy.astype(int) % 4, xx.astype(int) % 4] - .5) * .55
    img[:] = P[np.clip(np.round(lv), 0, 5).astype(int)]
    # the void: a black hole in the lower half, with a thin frost rim and dithered falloff
    vx, vy, rx, ry = c, 30.5, 17, 17
    e = ((xx - vx) / rx) ** 2 + ((yy - vy) / ry) ** 2
    img[e < 1] = PAL['v']
    rim = (e >= 1) & (e < 1.35)
    img[rim & ((xx.astype(int) + yy.astype(int)) % 2 == 0)] = PAL['f']
    img[(e >= 1.35) & (e < 2.0) & (BAYER[yy.astype(int) % 4, xx.astype(int) % 4] > .7)] = PAL['m']
    # ring: black outline, light band with a dither, dark inner line
    img[(r > 28.5) & (r <= 31.5)] = PAL['l']
    img[(r > 29.5) & (r <= 30.5) & (BAYER[yy.astype(int) % 4, xx.astype(int) % 4] > .55)] = PAL['g']
    img[(r > 30.6)] = PAL['k']
    img[(r > 27.6) & (r <= 28.5)] = PAL['k']
    # four little studs on the ring, like the old card back
    for a in (0, 90, 180, 270):
        sx, sy = int(c + 30 * math.cos(math.radians(a))), int(c + 30 * math.sin(math.radians(a)))
        img[sy - 1:sy + 1, sx - 1:sx + 1] = PAL['w']
    return img, alpha, e


def frame(i, n, cards, hopen, hgrab):
    img, alpha, e = base()
    t = i / n
    # card: floats, spins at its own pace, and lifts a little when the hand gets close
    reach = max(0.0, math.sin(min(1, t / .6) * math.pi)) if t < .6 else 0.0        # 0..1..0 over the first 60%
    tug = 2 if .42 < t < .52 else 0                                                    # the hand pulls the card down a little
    lift = -tug
    bob = round(1.2 * math.sin(t * 2 * math.pi * 2))
    cf = cards[int(((t - .47) % 1) * len(cards))]          # faces front just as the hand grabs
    cx, cy = 23, 19 + bob - lift
    # hand: rises out of the void, opens, tries to grab under the card, slips back
    rise = reach
    hy = round(48 - 35 * rise)
    hand = hgrab if .42 < t < .55 else hopen
    canvas = img.copy()
    hl = np.zeros((N, N, 3), np.float32); hm = np.zeros((N, N), bool)
    h, w = hand.shape[:2]
    for j in range(h):
        for k in range(w):
            y, x = hy + j, 23 + k
            if hand[j, k, 3] and 0 <= y < N and 0 <= x < N:
                hl[y, x] = hand[j, k, :3]; hm[y, x] = True
    # the arm vanishes into the void: only draw hand pixels above the void's back edge or outside it
    yy, xx = np.mgrid[0:N, 0:N] + .5
    hide = e >= 0.92                       # the hand only exists inside the void
    m = hm & ~hide if reach > .08 else np.zeros_like(hm)
    canvas[m] = hl[m]
    paste(canvas, cf, cx, cy)               # the card sits in front: the hand comes from behind it
    canvas[~alpha] = 0
    # little sparkle near the card while it's being sought
    if .2 < t < .6 and (i % 4) < 2:
        canvas[max(0, cy - 3), cx + 20] = PAL['w']; canvas[cy + 6, cx - 3] = PAL['w']
    out = np.dstack([canvas, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def main():
    src = sys.argv[1]
    cards = card_frames(src)
    n = 72
    hopen, hgrab = sprite(HAND_OPEN), sprite(HAND_GRAB)
    frames = [frame(i, n, cards, hopen, hgrab) for i in range(n)]
    big = [f.resize((N * 3, N * 3), Image.NEAREST) for f in frames]
    big[0].save(os.path.join(HERE, 'badge.webp'), save_all=True, append_images=big[1:], duration=110, loop=0, lossless=True)
    frames[int(n * .45)].resize((N * 3, N * 3), Image.NEAREST).save(os.path.join(HERE, 'badge.png'))
    sheet = Image.new('RGBA', (N * 4 * 6, N * 4), (46, 52, 64, 255))
    for k, i in enumerate(range(0, n, n // 6)):
        sheet.alpha_composite(frames[i].resize((N * 4, N * 4), Image.NEAREST), (k * N * 4, 0))
    sheet.save(os.path.join(HERE, 'badge-sheet.png'))
    print('ok', len(frames))


main()
