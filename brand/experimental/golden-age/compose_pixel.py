"""B, The Rooftop Thief: card, card back, logo and icons drawn at native pixel size.

The card is 192x268 native pixels with the 160x128 illustration placed 1:1, then scaled x8. Frames,
lattice, medallions and gold are drawn pixel by pixel from the same ramps as pixel.py. Type uses
Silkscreen (OFL) at its native 8 px. Nothing is resampled except by whole-number nearest scaling.

python3 compose_pixel.py   (after pixel.py)  -> B/
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pixel as P

HERE = os.path.dirname(os.path.abspath(__file__))
OD = os.path.join(HERE, 'B'); os.makedirs(OD, exist_ok=True)
FONT = lambda b=False, s=8: ImageFont.truetype(os.path.join(HERE, 'fonts', 'Silkscreen-Bold.ttf' if b else 'Silkscreen-Regular.ttf'), s)
C = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in P.HEX.items()}
B4 = P.B4


def bay(w, h):
    return np.tile(B4, (h // 4 + 1, w // 4 + 1))[:h, :w]


def frame_tex(w, h):
    """Dark bronze field: two-tone ordered dither + an 8-point star lattice with lit and shadow pixels."""
    a = np.zeros((h, w, 3), np.uint8)
    b = bay(w, h)
    y, x = np.mgrid[0:h, 0:w]
    noise = (np.sin(x * 0.37 + y * 0.11) + np.sin(y * 0.29 - x * 0.07)) * 0.25 + 0.5
    a[:] = C['f0']; a[(b < noise * 0.5)] = C['d0']
    cell = 22
    u, v = (x % cell) - cell / 2 + 0.5, (y % cell) - cell / 2 + 0.5
    sq1 = np.maximum(np.abs(u), np.abs(v))
    sq2 = (np.abs(u) + np.abs(v)) / math.sqrt(2)
    line = (np.abs(sq1 - 6) < 0.5) | (np.abs(sq2 - 6) < 0.5)
    a[line] = C['d1']
    a[line & ((u + v) < -4)] = C['d2']                 # lit edge, light from the upper left of each star
    a[np.roll(line, 1, 0) & ~line] = C['out']          # shadow pixel under the gold
    dot = (np.abs(u) < 1) & (np.abs(v) < 1)
    a[dot] = C['d3']
    return a


def parch(w, h):
    a = np.zeros((h, w, 3), np.uint8); a[:] = C['w0']
    b = bay(w, h)
    y, x = np.mgrid[0:h, 0:w]
    e = np.maximum(np.abs(x / max(w - 1, 1) - 0.5), np.abs(y / max(h - 1, 1) - 0.5)) * 2
    a[(e > 0.78) & (b < (e - 0.78) * 4)] = C['h2']
    a[(e > 0.9) & (b < (e - 0.9) * 8)] = C['s1']
    a[(b < 0.06)] = C['h3']
    return a


def gold_rect(d, box, double=False):
    x0, y0, x1, y1 = box
    d.rectangle((x0, y0, x1, y1), outline=C['d1'])
    d.rectangle((x0 + 1, y0 + 1, x1 - 1, y1 - 1), outline=C['d3'])
    d.line((x0 + 1, y0 + 1, x1 - 1, y0 + 1), fill=C['d4'])
    if double:
        d.rectangle((x0 + 3, y0 + 3, x1 - 3, y1 - 3), outline=C['d1'])


def star(d, cx, cy):
    for dx, dy, c in ((0, -2, 'd4'), (0, 2, 'd2'), (-2, 0, 'd3'), (2, 0, 'd2'), (0, 0, 'd4'),
                      (-1, -1, 'd3'), (1, 1, 'd1'), (1, -1, 'd3'), (-1, 1, 'd1')):
        d.point((cx + dx, cy + dy), fill=C[c])


def disc(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=C['h3'], outline=C['d1'])
    d.point((cx - r // 2, cy - r // 2), fill=C['m2'])
    star(d, cx, cy)


def magnifier(d, cx, cy):
    d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), outline=C['d3'], fill=C['n2'])
    d.point((cx - 1, cy - 1), fill=C['m2'])
    d.line((cx + 3, cy + 3, cx + 5, cy + 5), fill=C['d2'])


def medallion(img_rgb, box_src, r_out):
    """Native-size round medallion: gold ring pixels around a 1:1 crop of the illustration."""
    s = 2 * r_out + 1
    out = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    y, x = np.mgrid[0:s, 0:s] - r_out
    d = np.hypot(x, y)
    a = np.zeros((s, s, 4), np.uint8)
    crop = np.asarray(img_rgb.crop(box_src).convert('RGB'))
    ri = r_out - 4
    cy0 = (crop.shape[0] - s) // 2; cx0 = (crop.shape[1] - s) // 2
    inner = d <= ri
    sub = np.zeros((s, s, 3), np.uint8)
    hh, ww = crop.shape[:2]
    ys, xs = np.clip(np.arange(s) + cy0, 0, hh - 1), np.clip(np.arange(s) + cx0, 0, ww - 1)
    sub[:] = crop[ys][:, xs]
    a[inner, :3] = sub[inner]; a[inner, 3] = 255
    ring = (d > ri) & (d <= r_out)
    ang = np.arctan2(y, x)
    lit = np.cos(ang + 2.4)
    ringc = np.where(lit[..., None] > 0.4, C['d4'], np.where(lit[..., None] > -0.2, C['d3'], C['d2']))
    a[ring, :3] = ringc[ring]; a[ring, 3] = 255
    a[(d > ri) & (d <= ri + 1), :3] = C['d1']
    a[(d > r_out - 1) & (d <= r_out), :3] = C['f0']
    beads = ring & (np.abs(d - (ri + 2.5)) < 0.7) & (((np.degrees(ang) + 360) % 30) < 8)
    a[beads, :3] = C['m2']
    return Image.fromarray(a, 'RGBA')


def text(d, xy, s, bold=False, fill=None, anchor='la', size=8):
    d.text(xy, s, font=FONT(bold, size), fill=fill or C['f0'], anchor=anchor)


def card_front(art):
    W, H = 192, 268
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.rounded_rectangle((0, 0, W - 1, H - 1), 9, fill=C['out'])
    fr = Image.fromarray(frame_tex(W - 12, H - 12)); im.paste(fr, (6, 6))
    d.rectangle((6, 6, W - 7, H - 7), outline=C['f0'])
    # title plate
    im.paste(Image.fromarray(parch(176, 14)), (8, 10)); gold_rect(d, (7, 9, 184, 24))
    text(d, (12, 13), 'CARD HUNT', True)
    disc(d, 176, 16, 4); disc(d, 166, 16, 4)
    # art 1:1
    im.paste(art, (16, 30)); gold_rect(d, (13, 27, 178, 160), True)
    for cx, cy in ((13, 27), (178, 27), (13, 160), (178, 160)):
        star(d, cx, cy)
    # type plate
    im.paste(Image.fromarray(parch(176, 13)), (8, 165)); gold_rect(d, (7, 164, 184, 178))
    text(d, (11, 168), 'Legendary Monkey Thief', True)
    magnifier(d, 176, 170)
    # text box
    im.paste(Image.fromarray(parch(166, 66)), (13, 183)); gold_rect(d, (12, 182, 179, 249), True)
    lines = ['Search every shop at once.', 'Take the cheapest copy.', '',
             '"No lock in the bazaar', 'kept a card from him', 'for long."']
    for i, l in enumerate(lines):
        text(d, (19, 189 + i * 9), l, fill=C['f0'] if i < 2 else C['f1'])
    text(d, (10, 255), 'Illus. Card Hunt', fill=C['h3'])
    text(d, (182, 255), '3/1', True, C['m2'], 'ra')
    return im


def card_back(art):
    W, H = 192, 268
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.rounded_rectangle((0, 0, W - 1, H - 1), 9, fill=C['out'])
    im.paste(Image.fromarray(frame_tex(W - 12, H - 12)), (6, 6))
    gold_rect(d, (11, 11, W - 12, H - 12), True)
    for cx, cy in ((11, 11), (W - 12, 11), (11, H - 12), (W - 12, H - 12)):
        star(d, cx, cy)
    med = medallion(art, (60, 6, 140, 86), 38)
    im.alpha_composite(med, (W // 2 - 38, 54))
    im.paste(Image.fromarray(parch(140, 18)), (26, 178)); gold_rect(d, (25, 177, 166, 196))
    text(d, (96, 183), 'CARD HUNT', True, C['f0'], 'ma', 16 if False else 8)
    text(d, (96, 206), 'Every store,', fill=C['d4'], anchor='ma')
    text(d, (96, 216), 'one search', fill=C['d4'], anchor='ma')
    return im


def logo(art):
    W, H = 300, 112
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.rounded_rectangle((0, 0, W - 1, H - 1), 10, fill=C['out'])
    im.paste(Image.fromarray(frame_tex(W - 8, H - 8)), (4, 4))
    gold_rect(d, (7, 7, W - 8, H - 8), True)
    im.alpha_composite(medallion(art, (52, 8, 132, 88), 46), (10, 9))
    d.rectangle((104, 26, 290, 82), fill=C['out']); gold_rect(d, (104, 26, 290, 82))
    # gold pixel lettering with a dark drop and a lit top row
    m = Image.new('L', (W, H), 0); md = ImageDraw.Draw(m); md.fontmode = '1'
    md.text((198, 46), 'CARD HUNT', font=FONT(True, 16), anchor='mm', fill=255)
    a = np.asarray(m) > 0
    out = np.asarray(im).copy()
    sh = np.roll(np.roll(a, 1, 0), 1, 1) & ~a
    out[sh, :3] = C['f0']; out[sh, 3] = 255
    yy = np.mgrid[0:H, 0:W][0]
    top = a & ~np.roll(a, 1, 0)
    out[a, :3] = np.array(C['d3']); out[a & (yy > 49), :3] = np.array(C['d2'])
    out[top, :3] = np.array(C['d4']); out[a, 3] = 255
    im = Image.fromarray(out, 'RGBA'); d = ImageDraw.Draw(im); d.fontmode = '1'
    text(d, (198, 66), 'every store, one search', fill=C['h3'], anchor='mm')
    for x in (130, 266):
        star(d, x, 66)
    return im


def icon(art, n=128, r=None):
    im = Image.fromarray(frame_tex(n, n)).convert('RGBA')
    r = r or n // 2 - 6
    c = (P.T((93, 54)))
    cy = max(c[1], r + 1)
    box = (int(c[0] - r - 6), int(cy - r), int(c[0] + r - 5), int(cy + r + 1))
    im.alpha_composite(medallion(art, box, r), (n // 2 - r, n // 2 - r))
    return im


def main():
    art = Image.open(os.path.join(HERE, 'art', 'B-art-native.png')).convert('RGB')
    save = lambda im, name, k: im.resize((im.width * k, im.height * k), Image.NEAREST).save(os.path.join(OD, name))
    f = card_front(art); f.save(os.path.join(OD, 'card-front-native.png')); save(f, 'card-front.png', 8)
    b = card_back(art); b.save(os.path.join(OD, 'card-back-native.png')); save(b, 'card-back.png', 8)
    l = logo(art); l.save(os.path.join(OD, 'logo-native.png')); save(l, 'logo.png', 8)
    ic = icon(art); ic.save(os.path.join(OD, 'icon-native.png'))
    save(ic, 'icon-1024.png', 8); save(ic, 'icon-512.png', 4)
    save(icon(art, 96, 40), 'icon-192.png', 2)
    save(icon(art, 128, 40), 'icon-maskable-512.png', 4)
    save(icon(art, 90, 38), 'apple-touch-icon.png', 2)
    Image.open(os.path.join(HERE, 'art', 'B-mascot.png')).save(os.path.join(OD, 'mascot.png'))
    Image.open(os.path.join(HERE, 'art', 'B-art.png')).save(os.path.join(OD, 'illustration.png'))
    print('B composed')


if __name__ == '__main__':
    main()
