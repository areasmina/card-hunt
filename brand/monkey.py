"""The Card Hunt mascot: a monkey card hunter (pith hat, magnifier, holding up a card), drawn as
pixel art with a muted early-90s card palette. Original art.

python3 monkey.py <out dir>  ->  monkey-sprite.png (64x64, transparent), monkey-art.png (80x64 scene),
                                  monkey-head.png (48x38, transparent),
                                  monkey-icon.png (52x52 with sunset), plus x12 previews
"""
import sys, os
import numpy as np
from PIL import Image

PAL = {
    'ink': '#1a1410', 'fur_d': '#4a2c1a', 'fur': '#7a4a2a', 'fur_l': '#a46c3e',
    'face': '#e6bc90', 'face_d': '#c08a62', 'hat': '#cdb47c', 'hat_d': '#97804f', 'band': '#a8402a',
    'white': '#f4ecda', 'lens': '#a9cfd8', 'brass': '#c9a23e',
    'card': '#161d18', 'card_art': '#d0643a', 'card_art2': '#f0a050', 'parch': '#e0b78e',
}
NAMES = list(PAL)
IDX = {k: i + 1 for i, k in enumerate(NAMES)}          # 0 = transparent
RGB = np.array([[0, 0, 0]] + [[int(PAL[k][i:i + 2], 16) for i in (1, 3, 5)] for k in NAMES], np.uint8)

W = H = 64
yy, xx = np.mgrid[0:H, 0:W]
c = np.zeros((H, W), np.uint8)


def ell(cx, cy, rx, ry):
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0


def put(mask, col):
    c[mask] = IDX[col]


def thick(p0, p1, r, col):
    for t in np.linspace(0, 1, 40):
        x = p0[0] + (p1[0] - p0[0]) * t; y = p0[1] + (p1[1] - p0[1]) * t
        put(ell(x, y, r, r), col)


def rect(x0, y0, x1, y1, col):
    put((xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1), col)


# tail: a curl behind the body
for t in np.linspace(0, 1, 60):
    a = np.pi * (0.2 + 1.7 * t)
    r = 11 - 6 * t
    x = 49 - r * np.cos(a) * 0.9; y = 50 - r * np.sin(a) * 0.8
    put(ell(x, y, 1.6, 1.6), 'fur_d')

# body, belly, feet
put(ell(31, 47, 12, 12.5), 'fur')
put(ell(31, 49, 7, 8), 'face')
for fx in (23, 39):
    put(ell(fx, 59, 5.5, 3), 'fur_d'); put(ell(fx, 60, 3.5, 1.6), 'face_d')

# left arm down, holding a magnifier
thick((21, 41), (15, 51), 2.2, 'fur')
thick((11, 50), (15, 54), 1.2, 'fur_d')
put(ell(15, 53, 2.4, 2.4), 'face')
put(ell(9, 45, 4.8, 4.8), 'brass'); put(ell(9, 45, 3.3, 3.3), 'lens')
c[43, 8] = c[43, 7] = c[44, 7] = IDX['white']           # glint

# head
for ex in (18, 44):
    put(ell(ex, 25, 4.5, 4.5), 'fur'); put(ell(ex, 25, 2.4, 2.4), 'face_d')
put(ell(31, 25, 12, 11), 'fur')
put(ell(27, 24, 5, 5), 'face'); put(ell(35, 24, 5, 5), 'face')
put(ell(31, 30, 7.5, 5), 'face')
for ex in (27, 35):
    rect(ex - 1, 23, ex, 25, 'ink'); c[23, ex - 1] = IDX['white']

# pith hat
put(ell(31, 15, 16, 3.2), 'hat')
put(ell(31, 13, 9.5, 8) & (yy <= 14), 'hat')
put((ell(31, 13, 9.5, 8) & (yy >= 11) & (yy <= 12)), 'band')
c[16:18][ell(31, 15, 16, 3.2)[16:18]] = IDX['hat_d']

# right arm raised, holding up a card
rect(45, 4, 57, 21, 'card')
rect(47, 6, 55, 12, 'card_art'); rect(47, 6, 55, 8, 'card_art2')
rect(47, 14, 55, 19, 'parch')
for y in (15, 17):
    rect(48, y, 53, y, 'face_d')
thick((41, 39), (48, 24), 2.2, 'fur')
put(ell(49, 22, 2.6, 2.4), 'face')

# shading: light from the top left
fur = np.isin(c, [IDX['fur']])
def shifted(m, dx, dy):
    return np.roll(np.roll(m, dy, 0), dx, 1)
c[fur & ~shifted(fur, 2, 2)] = IDX['fur_l']
c[fur & ~shifted(fur, -2, -2)] = IDX['fur_d']
face = c == IDX['face']
c[face & ~shifted(face, -1, -2) & (yy > 34)] = IDX['face_d']
# nose and smile
c[29, 30] = c[29, 32] = IDX['fur_d']
for x, y in ((27, 31), (28, 32), (29, 33), (30, 33), (31, 33), (32, 33), (33, 33), (34, 32), (35, 31)):
    c[y, x] = IDX['fur_d']
hat = c == IDX['hat']
c[hat & ~shifted(hat, -2, -1)] = IDX['hat_d']

# 1 px outline
solid = c > 0
edge = ~solid & (shifted(solid, 1, 0) | shifted(solid, -1, 0) | shifted(solid, 0, 1) | shifted(solid, 0, -1))
c[edge] = IDX['ink']


def rgba(idx):
    a = np.zeros(idx.shape + (4,), np.uint8)
    a[..., :3] = RGB[idx]; a[..., 3] = (idx > 0) * 255
    return Image.fromarray(a, 'RGBA')


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


def scene(sprite):
    """80x64 sunset behind the monkey, dithered in bands like an old card painting."""
    h, w = 64, 80
    sky = ['#211c3c', '#3a2a58', '#6a3458', '#a84a4a', '#d8743a', '#f0a456']
    sy, sx = np.mgrid[0:h, 0:w]
    t = sy / 46 * (len(sky) - 1)
    i0 = np.clip(t.astype(int), 0, len(sky) - 1)
    i1 = np.clip(i0 + 1, 0, len(sky) - 1)
    pick = np.where((t - i0) > BAYER[sy % 4, sx % 4], i1, i0)
    cols = np.array([[int(s[i:i + 2], 16) for i in (1, 3, 5)] for s in sky], np.uint8)
    img = cols[pick]
    sun = ((sx - 62) ** 2 + (sy - 40) ** 2) <= 64
    img[sun] = [248, 214, 140]
    hill = sy > 50 + 4 * np.sin(sx / 7.0) + 2 * np.sin(sx / 3.1 + 1)
    img[hill] = [32, 24, 26]
    out = Image.fromarray(img, 'RGB').convert('RGBA')
    out.alpha_composite(sprite, (8, 0))
    return out.convert('RGB')


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'out'
    os.makedirs(out, exist_ok=True)
    sp = rgba(c)
    sp.save(os.path.join(out, 'monkey-sprite.png'))
    art = scene(sp); art.save(os.path.join(out, 'monkey-art.png'))
    head = sp.crop((10, 2, 58, 40)); head.save(os.path.join(out, 'monkey-head.png'))
    icon = art.crop((14, 2, 66, 54)); icon.save(os.path.join(out, 'monkey-icon.png'))   # 52x52, sunset behind
    for name, im in (('monkey-sprite', sp), ('monkey-art', art), ('monkey-head', head), ('monkey-icon', icon)):
        im.resize((im.width * 12, im.height * 12), Image.NEAREST).save(os.path.join(out, name + '-x12.png'))
    print('monkey done')
