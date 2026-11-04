"""Vintage card front, laid out from measurements of 1993-95 cards (Ihsan's Shade, Jester's Cap).

python3 card.py [blue|black|white|artifact] -> card-<v>.png (1876x2612, 2x of a 938x1306 measured scan)
Frame and box textures are the quilted tiles from the user's own scans (brand/textures/hires).
"""
import sys, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
FONTS = os.path.join(HERE, 'fonts')
V = sys.argv[1] if len(sys.argv) > 1 else 'blue'
S = 2
CW, CH = 938 * S, 1306 * S


def px(*v):
    return tuple(int(round(a * S)) for a in v)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), int(size * S))


TITLE = 'Metamorphous-Regular.ttf'
BODY, ITAL = 'CrimsonText-Regular.ttf', 'CrimsonText-Italic.ttf'

# per frame: title ink, title shadow, bevel light/dark, pip colour, text box style
STYLE = {
    'blue':     dict(ink='#f4f0e6', shadow='#0a0a10', hi=(1.12, .72), pip='#bfe0f2', box='box-blue', frame='frame-blue', torn=False),
    'black':    dict(ink='#f2eee6', shadow='#000000', hi=(1.0, 1.0), pip='#c8c8c4', box='box-black', frame='frame-black', torn=True),
    'white':    dict(ink='#111111', shadow=None, hi=(1.08, .78), pip='#f6f0d8', box='box-white', frame='frame-white', torn=False),
    'artifact': dict(ink='#f2eee6', shadow='#140c06', hi=(1.1, .7), pip='#d8d0c4', box='box-artifact', frame='frame-artifact', torn=False),
}[V]

TEXT = dict(
    title='Card Hunt', cost=('2', 'pip'), type='Summon Legend',
    rules='Whenever you seek a card, search every shop in the realm at once, then take the cheapest copy.',
    flavor='“No lock in the bazaar kept a card from him for long.”',
    attrib='—Tales of the Night Market',
    illus='Illus. Card Hunt', copy='© 2026 Card Hunt. Unofficial fan project.', pt='2/2')


# mean and spread measured from the user's reference cards (frame strip and text-box margin)
MATCH = {
    'frame-blue': ((61, 153, 175), (14, 19, 14)), 'box-blue': ((178, 208, 216), (12, 10, 10)),
    'frame-black': ((36, 42, 37), (12, 13, 12)), 'box-black': ((198, 158, 118), (14, 12, 11)),
    'frame-white': ((196, 186, 174), (16, 16, 16)), 'box-white': ((214, 207, 203), (9, 9, 9)),
    'frame-artifact': ((110, 94, 83), (19, 17, 16)), 'box-artifact': ((200, 197, 188), (12, 12, 12)),
}


def tile(name, size):
    t = Image.open(os.path.join(BRAND, 'textures', 'hires', name + '.jpg')).convert('RGB')
    t = t.resize((size, size), Image.LANCZOS)
    a = np.asarray(t).astype(np.float32); m, sd = MATCH[name]
    a = (a - a.mean((0, 1))) / (a.std((0, 1)) + 1e-6) * np.array(sd) + np.array(m)
    t = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    out = Image.new('RGB', (CW, CH))
    for y in range(0, CH, size):
        for x in range(0, CW, size):
            out.paste(t, (x, y))
    return out


def bevel(img, box, w, hi, lo, inset=True):
    """emboss a rectangle edge: inset = darker top/left, lighter bottom/right (like the printed art well)"""
    x0, y0, x1, y1 = box
    a = np.asarray(img).astype(np.float32)
    top, bot = (lo, hi) if inset else (hi, lo)
    a[y0:y0 + w, x0:x1] *= top; a[y0:y1, x0:x0 + w] *= top
    a[y1 - w:y1, x0:x1] *= bot; a[y0:y1, x1 - w:x1] *= bot
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def text_shadow(d, xy, s, f, ink, shadow, off=(1.4, 1.4), anchor='ls'):
    if shadow:
        d.text((xy[0] + off[0] * S, xy[1] + off[1] * S), s, font=f, fill=shadow, anchor=anchor)
    d.text(xy, s, font=f, fill=ink, anchor=anchor)


def wrap(d, s, f, width):
    words, lines, cur = s.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def magnifier(d, cx, cy, r, ink):
    """our own pip glyph: a lens and handle"""
    lw = max(2, int(r * .22))
    d.ellipse([cx - r * .55, cy - r * .62, cx + r * .35, cy + r * .28], outline=ink, width=lw)
    d.line([cx + r * .22, cy + r * .16, cx + r * .62, cy + r * .58], fill=ink, width=int(lw * 1.5))


def torn_mask(box, seed=3):
    """ragged parchment edge, like the black-frame text boxes"""
    x0, y0, x1, y1 = box
    m = Image.new('L', (CW, CH), 0); d = ImageDraw.Draw(m)
    r = np.random.default_rng(seed)
    def jag(n, amp):
        v = np.cumsum(r.normal(0, 1, n)); v = (v - np.linspace(v[0], v[-1], n)); v = v / (np.abs(v).max() + 1e-6)
        return v * amp + r.normal(0, amp * .18, n)
    a = 7 * S; n = 140
    top = [(x, y0 + jag_v) for x, jag_v in zip(np.linspace(x0, x1, n), jag(n, a))]
    right = [(x1 + j, y) for y, j in zip(np.linspace(y0, y1, n // 2), jag(n // 2, a))]
    bot = [(x, y1 + j) for x, j in zip(np.linspace(x1, x0, n), jag(n, a))]
    left = [(x0 + j, y) for y, j in zip(np.linspace(y1, y0, n // 2), jag(n // 2, a))]
    d.polygon(top + right + bot + left, fill=255)
    return m


def build():
    card = Image.new('RGB', (CW, CH), (8, 8, 8))
    frame = tile(STYLE['frame'], int(1460 * S / 2))
    fm = Image.new('L', (CW, CH), 0); ImageDraw.Draw(fm).rectangle(px(38, 38, 900, 1268), fill=255)
    card.paste(frame, (0, 0), fm)
    # the frame's own inner shading near the black border
    card = bevel(card, px(38, 38, 900, 1268), 3 * S, .8, .8)

    # art well
    art_outer, art_inner = px(86, 108, 852, 722), px(100, 120, 838, 710)
    hi, lo = STYLE['hi']
    if V == 'black':
        d = ImageDraw.Draw(card); d.rectangle(art_inner, fill=(10, 10, 10))
        card = bevel(card, (art_inner[0] - 3 * S, art_inner[1] - 3 * S, art_inner[2] + 3 * S, art_inner[3] + 3 * S), 3 * S, .55, .35)
    else:
        card = bevel(card, art_outer, int(5 * S), hi, lo, inset=True)
        d = ImageDraw.Draw(card); d.rectangle(art_inner, fill=(10, 10, 10))
    art = Image.open(os.path.join(HERE, f'art-{V}.png')).convert('RGB')
    z = 1.16; aw, ah = art.width / z, art.height / z; ax, ay = art.width * .47 - aw / 2, art.height * .44 - ah / 2
    art = art.crop((int(ax), int(ay), int(ax + aw), int(ay + ah))).resize((art_inner[2] - art_inner[0], art_inner[3] - art_inner[1]), Image.LANCZOS)
    card.paste(art, art_inner[:2])

    # text box
    tb = px(106, 784, 832, 1170)
    box = tile(STYLE['box'], int(1100 * S / 2))
    if STYLE['torn']:
        m = torn_mask(tb)
        burn = m.filter(ImageFilter.GaussianBlur(5 * S))
        shadow = Image.new('RGB', (CW, CH), (0, 0, 0))
        card.paste(shadow, (int(2 * S), int(3 * S)), m.filter(ImageFilter.GaussianBlur(3 * S)))
        card.paste(box, (0, 0), m)
        edge = ImageChops.subtract(m, burn)
        card.paste(Image.new('RGB', (CW, CH), (90, 50, 20)), (0, 0), edge.point(lambda v: int(v * .8)))
    else:
        card = bevel(card, (tb[0] - 6 * S, tb[1] - 6 * S, tb[2] + 6 * S, tb[3] + 6 * S), int(6 * S), hi, lo, inset=True)
        card.paste(box.crop(tb), tb[:2])

    d = ImageDraw.Draw(card)
    ink, sh = STYLE['ink'], STYLE['shadow']
    # title and cost
    text_shadow(d, px(78, 92), TEXT['title'], font(TITLE, 42), ink, sh)
    cx, cy, r = 842 * S, 74 * S, 21 * S
    for i, kind in enumerate(reversed(TEXT['cost'])):
        x = cx - i * 45 * S
        d.ellipse([x - r + 2 * S, cy - r + 3 * S, x + r + 2 * S, cy + r + 3 * S], fill=(0, 0, 0))
        if kind == 'pip':
            d.ellipse([x - r, cy - r, x + r, cy + r], fill=STYLE['pip'])
            magnifier(d, x, cy, r * .95, (20, 20, 20))
        else:
            d.ellipse([x - r, cy - r, x + r, cy + r], fill='#e8e0d0')
            d.text((x, cy + 1 * S), kind, font=font(BODY, 38), fill=(20, 20, 20), anchor='mm')
    # type line and set symbol
    text_shadow(d, px(78, 766), TEXT['type'], font(TITLE, 36), ink, sh)
    sx, sy = 832 * S, 752 * S
    d.ellipse([sx - 13 * S, sy - 13 * S, sx + 13 * S, sy + 13 * S], outline=ink, width=int(2 * S))
    magnifier(d, sx, sy, 11 * S, ink)
    # rules and flavour
    x, y, wdt = 132 * S, 842 * S, 680 * S
    fr, fi = font(BODY, 44), font(ITAL, 44)
    for ln in wrap(d, TEXT['rules'], fr, wdt):
        d.text((x, y), ln, font=fr, fill=(18, 14, 10), anchor='ls'); y += 43 * S
    y += 4 * S
    for ln in wrap(d, TEXT['flavor'], fi, wdt):
        d.text((x, y), ln, font=fi, fill=(18, 14, 10), anchor='ls'); y += 43 * S
    d.text((x, y), TEXT['attrib'], font=fi, fill=(18, 14, 10), anchor='ls')
    # illus, copyright, P/T
    text_shadow(d, px(78, 1207), TEXT['illus'], font(BODY, 34), ink, sh, off=(1.1, 1.1))
    text_shadow(d, px(78, 1233), TEXT['copy'], font(BODY, 16), ink, sh, off=(.8, .8))
    text_shadow(d, px(868, 1212), TEXT['pt'], font(BODY, 50), ink, sh, anchor='rs')

    # rounded corners
    mask = Image.new('L', (CW, CH), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CW - 1, CH - 1], radius=34 * S, fill=255)
    out = Image.new('RGBA', (CW, CH), (0, 0, 0, 0)); out.paste(card, (0, 0), mask)
    p = os.path.join(HERE, f'card-{V}.png'); out.save(p); print('wrote', p)


build()
