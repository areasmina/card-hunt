"""Cards, card backs, logos and icons for the three golden-age directions.

python3 compose.py [A|B|C ...]   reads art/<D>-art.png, art/<D>-mascot.png -> <D>/...
  A classic  painted art, ornamental bronze frame, IM Fell + Cinzel Decorative type
  B pixel    everything built at 1/5 size, snapped to the palette, pixel type, x5
  C hybrid   painted art and frame, ornaments and gold drawn as stepped pixels
Ornaments, symbols and type layout are our own (no real card frames or set symbols copied).
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.abspath(os.path.join(HERE, '..', '..'))
ART = os.path.join(HERE, 'art')
FONTS = os.path.join(HERE, 'fonts')
TILE = lambda n: os.path.join(BRAND, 'textures', 'hires', n + '.jpg')
sys.path.insert(0, HERE)
import paint  # palette + dither helpers

GOLD, GOLD_D, GOLD_L = (184, 144, 62), (92, 66, 26), (236, 204, 128)
INK, PARCH_INK, NIGHT = (24, 16, 10), (34, 22, 12), (13, 11, 10)
TITLE, BODY, ITAL, DECO = 'IMFeENsc28P.ttf', 'IMFeENrm28P.ttf', 'IMFeENit28P.ttf', 'CinzelDecorative-Bold.ttf'
PIXF, PIXF_B = 'Silkscreen-Regular.ttf', 'Silkscreen-Bold.ttf'

CARD = dict(
    title='Card Hunt',
    type='Legendary Creature — Monkey Hunter',
    rules='Whenever you go looking for a card, search every shop at once. Take the cheapest copy.',
    flavor='“In the bazaar of a thousand stalls, only the monkey knew where every treasure slept.”',
    pt='2/2',
)
HEAD_BOX = None   # filled from the art size below (square around the head, hat and card)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), max(6, int(size)))


def tiled(path, w, h, tile_px, tint=(1, 1, 1), dark=1.0):
    t = Image.open(path).convert('RGB').resize((tile_px, tile_px), Image.LANCZOS)
    out = Image.new('RGB', (w, h))
    for y in range(0, h, tile_px):
        for x in range(0, w, tile_px):
            out.paste(t, (x, y))
    a = np.asarray(out).astype(np.float32) * np.array(tint) * dark
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def burn(im, strength=0.55):
    """Burnt, age-darkened edges, like an old parchment box."""
    w, h = im.size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    e = np.maximum(np.abs(x / w - 0.5), np.abs(y / h - 0.5)) * 2
    k = 1 - strength * np.clip((e - 0.7) / 0.3, 0, 1) ** 2
    a = np.asarray(im).astype(np.float32) * k[..., None] * np.array([1, 0.92, 0.8])
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def star_lattice(w, h, cell, width, color, ss=3):
    """Our own arabesque: interlaced 8-point stars on a square lattice (tileable)."""
    W, H, c = w * ss, h * ss, cell * ss
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    r1, r2 = c * 0.42, c * 0.42
    for cy in range(-c, H + c, c):
        for cx in range(-c, W + c, c):
            for rot in (0, 45):
                pts = []
                for k in range(4):
                    a = math.radians(rot + 45 + 90 * k)
                    pts.append((cx + r1 * math.cos(a), cy + r1 * math.sin(a)))
                d.line(pts + [pts[0]], fill=255, width=int(width * ss))
            d.ellipse((cx - c * 0.09, cy - c * 0.09, cx + c * 0.09, cy + c * 0.09), outline=255, width=int(width * ss))
            hx, hy = cx + c / 2, cy + c / 2
            d.line([(hx - c * 0.12, hy), (hx, hy - c * 0.12), (hx + c * 0.12, hy), (hx, hy + c * 0.12), (hx - c * 0.12, hy)],
                   fill=255, width=int(width * ss))
    m = im.resize((w, h), Image.LANCZOS)
    layer = Image.new('RGBA', (w, h), color + (0,)); layer.putalpha(m)
    return layer


def emboss(base, layer, alpha=0.6, shadow=2):
    """Lay gold ornament on the frame with a dark under-shadow, so it reads as raised."""
    a = layer.split()[3]
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0)); sh.putalpha(a.point(lambda v: int(v * 0.7)))
    out = base.convert('RGBA')
    out.alpha_composite(sh, (shadow, shadow))
    lay = layer.copy(); lay.putalpha(a.point(lambda v: int(v * alpha)))
    out.alpha_composite(lay)
    return out


def rr(d, box, r, **kw):
    d.rounded_rectangle(box, r, **kw)


def gold_frame(d, box, f, double=True):
    x0, y0, x1, y1 = box
    d.rectangle(box, outline=GOLD_D, width=max(1, int(8 * f)))
    d.rectangle((x0 + 2 * f, y0 + 2 * f, x1 - 2 * f, y1 - 2 * f), outline=GOLD, width=max(1, int(4 * f)))
    if double:
        d.rectangle((x0 + 9 * f, y0 + 9 * f, x1 - 9 * f, y1 - 9 * f), outline=GOLD_D, width=max(1, int(2 * f)))


def star(d, cx, cy, r, f, fill=GOLD, outline=GOLD_D):
    pts = []
    for k in range(16):
        a = math.radians(22.5 * k - 90)
        rad = r if k % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    d.polygon(pts, fill=fill, outline=outline)


def magnifier_symbol(d, cx, cy, r, f):
    """Our expansion symbol: a little magnifier."""
    w = max(1, int(5 * f))
    d.line((cx + r * 0.45, cy + r * 0.45, cx + r * 1.05, cy + r * 1.05), fill=GOLD_D, width=w * 3)
    d.line((cx + r * 0.45, cy + r * 0.45, cx + r * 1.05, cy + r * 1.05), fill=GOLD, width=w * 2)
    d.ellipse((cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7), fill=(30, 26, 22), outline=GOLD, width=w * 2)
    d.ellipse((cx - r * 0.42, cy - r * 0.5, cx - r * 0.1, cy - r * 0.2), fill=(220, 220, 200))


def cost_disc(d, cx, cy, r, f):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(214, 190, 134), outline=GOLD_D, width=max(1, int(3 * f)))
    star(d, cx, cy, r * 0.62, f, fill=(60, 40, 20), outline=(60, 40, 20))


def wrap(d, text, fnt, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=fnt) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur]


def medallion(art, size, ring=0.07):
    """Round gold medallion with the monkey's head inside (transparent outside)."""
    s = size
    out = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(out)
    d.ellipse((0, 0, s - 1, s - 1), fill=GOLD_D)
    d.ellipse((s * 0.015, s * 0.015, s * 0.985, s * 0.985), fill=GOLD)
    inner = int(s * (1 - 2 * ring))
    face = art.resize((inner, inner), Image.LANCZOS)
    m = Image.new('L', (inner, inner), 0); ImageDraw.Draw(m).ellipse((0, 0, inner - 1, inner - 1), fill=255)
    out.paste(face, ((s - inner) // 2, (s - inner) // 2), m)
    d.ellipse(((s - inner) / 2, (s - inner) / 2, (s + inner) / 2, (s + inner) / 2), outline=GOLD_D, width=max(1, s // 120))
    n = 40
    for k in range(n):                                  # bead ring
        a = 2 * math.pi * k / n; rr_ = s * (0.5 - ring / 2)
        x, y = s / 2 + rr_ * math.cos(a), s / 2 + rr_ * math.sin(a); b = s * 0.012
        d.ellipse((x - b, y - b, x + b, y + b), fill=GOLD_L, outline=GOLD_D)
    return out


# ---------------------------------------------------------------- per-direction rendering helpers
def pixel_snap(im, k):
    """Snap an RGB(A) image to the palette at 1/k size with dither, then scale back up (B, C bits)."""
    a = np.asarray(im.convert('RGBA')).astype(np.float32) / 255
    h, w = a.shape[0] // k, a.shape[1] // k
    small = paint.down(a[..., :3], w, h)
    idx = paint.clean(paint.dither(small, 0.1))
    rgb = paint.up(paint.PAL[idx], k)
    al = paint.up(paint.down(a[..., 3:].repeat(3, -1), w, h)[..., :1] > 0.5, k).astype(np.float32)
    out = np.dstack([rgb, al])
    H, W = a.shape[:2]
    canvas = np.zeros((H, W, 4), np.float32); canvas[:out.shape[0], :out.shape[1]] = out
    return Image.fromarray((canvas * 255).astype(np.uint8), 'RGBA')


def stepped(layer, k):
    """Make an overlay (ornaments, gold rules) into chunky stepped pixels."""
    w, h = layer.size
    return layer.resize((w // k, h // k), Image.BOX).resize((w // k * k, h // k * k), Image.NEAREST)


def frame_base(D, w, h, f):
    if D == 'B':
        base = tiled(TILE('frame-artifact'), w, h, max(8, int(500 * f)), (0.85, 0.75, 0.62), 0.75)
    else:
        base = tiled(TILE('frame-artifact'), w, h, int(500 * f), (0.9, 0.78, 0.62), 0.72)
    lat = star_lattice(w, h, max(8, int(120 * f)), max(1, 3 * f), GOLD)
    if D == 'C':
        lat = stepped(lat, 4)
    return emboss(base, lat, 0.42, max(1, int(3 * f)))


def parchment(w, h, f, burnt=0.55):
    return burn(tiled(TILE('box-black'), w, h, max(8, int(520 * f))), burnt)


def text_font(D, kind, size):
    if D == 'B':
        return font(PIXF_B if kind in ('title', 'type') else PIXF, size)
    return font({'title': TITLE, 'type': TITLE, 'body': BODY, 'ital': ITAL, 'deco': DECO}[kind], size)


# ---------------------------------------------------------------- the card front
def card_front(D, art):
    S = 5 if D == 'B' else 1                     # B is built small and scaled up
    W, H = 1500 // S, 2100 // S; f = 1 / S
    card = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    rr(d, (0, 0, W - 1, H - 1), int(70 * f), fill=NIGHT)
    fr = frame_base(D, W - int(120 * f), H - int(120 * f), f)
    m = Image.new('L', fr.size, 0); rr(ImageDraw.Draw(m), (0, 0, fr.size[0] - 1, fr.size[1] - 1), int(30 * f), fill=255)
    card.paste(fr, (int(60 * f), int(60 * f)), m)

    g = Image.new('RGBA', card.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)   # gold work, stepped for C
    # title plate
    tp = (int(110 * f), int(105 * f), int(1390 * f), int(230 * f))
    card.paste(parchment(tp[2] - tp[0], tp[3] - tp[1], f, 0.4), tp[:2])
    gold_frame(gd, tp, f, False)
    # art window
    aw = (int(130 * f), int(262 * f), int(1370 * f), int(1254 * f))
    card.paste(art.convert('RGB').resize((aw[2] - aw[0], aw[3] - aw[1]), Image.NEAREST if D == 'B' else Image.LANCZOS), aw[:2])
    gold_frame(gd, (aw[0] - 14 * f, aw[1] - 14 * f, aw[2] + 14 * f, aw[3] + 14 * f), f)
    for cx, cy in ((aw[0] - 14 * f, aw[1] - 14 * f), (aw[2] + 14 * f, aw[1] - 14 * f),
                   (aw[0] - 14 * f, aw[3] + 14 * f), (aw[2] + 14 * f, aw[3] + 14 * f)):
        star(gd, cx, cy, 30 * f, f)
    # type plate
    ty = (int(110 * f), int(1290 * f), int(1390 * f), int(1398 * f))
    card.paste(parchment(ty[2] - ty[0], ty[3] - ty[1], f, 0.4), ty[:2])
    gold_frame(gd, ty, f, False)
    # text box
    tb = (int(130 * f), int(1432 * f), int(1370 * f), int(1902 * f))
    card.paste(parchment(tb[2] - tb[0], tb[3] - tb[1], f), tb[:2])
    gold_frame(gd, tb, f)
    # symbols
    for i, cx in enumerate((1330, 1245)):
        cost_disc(gd, cx * f, 167 * f, 36 * f, f)
    magnifier_symbol(gd, 1320 * f, 1340 * f, 30 * f, f)
    if D == 'C':
        g = stepped(g, 4)
    card.alpha_composite(g)

    d = ImageDraw.Draw(card)
    d.fontmode = '1' if D == 'B' else 'L'
    fs = {'title': 88, 'type': 54, 'body': 54, 'ital': 47, 'small': 34, 'pt': 66}
    if D == 'B':
        fs = {'title': 70, 'type': 38, 'body': 40, 'ital': 36, 'small': 30, 'pt': 60}
    d.text((150 * f, 168 * f), CARD['title'], font=text_font(D, 'title', fs['title'] * f), fill=PARCH_INK, anchor='lm')
    d.text((150 * f, 1344 * f), CARD['type'], font=text_font(D, 'type', fs['type'] * f), fill=PARCH_INK, anchor='lm')
    body = text_font(D, 'body', fs['body'] * f); ital = text_font(D, 'ital', fs['ital'] * f)
    y = 1475 * f
    for line in wrap(d, CARD['rules'], body, 1150 * f):
        d.text((175 * f, y), line, font=body, fill=PARCH_INK); y += fs['body'] * 1.18 * f
    y += 26 * f
    for line in wrap(d, CARD['flavor'], ital, 1150 * f):
        d.text((175 * f, y), line, font=ital, fill=PARCH_INK); y += fs['ital'] * 1.18 * f
    d.text((130 * f, 1972 * f), 'Illus. Card Hunt', font=text_font(D, 'body', fs['small'] * f), fill=(214, 190, 134), anchor='lm')
    d.text((1370 * f, 1970 * f), CARD['pt'], font=text_font(D, 'title', fs['pt'] * f), fill=(236, 214, 160), anchor='rm')
    if D == 'B':
        card = card.resize((W * S, H * S), Image.NEAREST)
    return card


# ---------------------------------------------------------------- the card back
def card_back(D, head):
    S = 5 if D == 'B' else 1
    W, H = 1500 // S, 2100 // S; f = 1 / S
    card = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    rr(d, (0, 0, W - 1, H - 1), int(70 * f), fill=NIGHT)
    fr = frame_base(D, W - int(120 * f), H - int(120 * f), f)
    m = Image.new('L', fr.size, 0); rr(ImageDraw.Draw(m), (0, 0, fr.size[0] - 1, fr.size[1] - 1), int(30 * f), fill=255)
    card.paste(fr, (int(60 * f), int(60 * f)), m)
    g = Image.new('RGBA', card.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
    gold_frame(gd, (int(100 * f), int(100 * f), int(1400 * f), int(2000 * f)), f)
    for cx, cy in ((100, 100), (1400, 100), (100, 2000), (1400, 2000)):
        star(gd, cx * f, cy * f, 46 * f, f)
    rib = (int(250 * f), int(1500 * f), int(1250 * f), int(1680 * f))
    if D == 'C':
        g = stepped(g, 4)
    card.alpha_composite(g)
    med = medallion(head, int(900 * f))
    card.alpha_composite(med, (int(300 * f), int(380 * f)))
    card.paste(parchment(rib[2] - rib[0], rib[3] - rib[1], f, 0.5), rib[:2])
    g2 = Image.new('RGBA', card.size, (0, 0, 0, 0)); gold_frame(ImageDraw.Draw(g2), rib, f, False)
    if D == 'C':
        g2 = stepped(g2, 4)
    card.alpha_composite(g2)
    d = ImageDraw.Draw(card); d.fontmode = '1' if D == 'B' else 'L'
    d.text((750 * f, 1592 * f), 'Card Hunt', font=text_font(D, 'deco' if D != 'B' else 'title', (110 if D != 'B' else 84) * f),
           fill=PARCH_INK, anchor='mm')
    d.text((750 * f, 1800 * f), 'Every store, one search', font=text_font(D, 'ital', 54 * f), fill=(214, 190, 134), anchor='mm')
    if D == 'B':
        card = card.resize((W * S, H * S), Image.NEAREST)
    return card


# ---------------------------------------------------------------- logo + icons
def gold_text(D, size_box, text, fnt, xy, anchor, k=1):
    """Gold lettering with dark edge and a soft engraved shadow."""
    w, h = size_box
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).text(xy, text, font=fnt, anchor=anchor, fill=255)
    if D == 'B':
        m = m.point(lambda v: 255 if v > 110 else 0)
    edge = m.filter(ImageFilter.MaxFilter(5 if D != 'B' else 3))
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sh = Image.new('RGBA', (w, h), (0, 0, 0, 160)); sh.putalpha(edge.point(lambda v: int(v * 0.6)))
    out.alpha_composite(sh, (max(1, w // 400), max(1, w // 400)))
    e = Image.new('RGBA', (w, h), GOLD_D + (255,)); e.putalpha(edge); out.alpha_composite(e)
    yy = np.linspace(0, 1, h)[:, None].repeat(w, 1)
    grad = np.dstack([np.interp(yy, [0, 0.45, 0.55, 1], [c1, c2, c3, c4]) for c1, c2, c3, c4 in
                      zip(GOLD_L, GOLD_L, GOLD, GOLD_D)]).astype(np.uint8)
    gi = Image.fromarray(grad, 'RGB').convert('RGBA'); gi.putalpha(m); out.alpha_composite(gi)
    return out


def logo(D, head):
    S = 6 if D == 'B' else 1
    W, H = 2400 // S, 900 // S; f = 1 / S
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(out)
    rr(d, (0, 0, W - 1, H - 1), int(90 * f), fill=NIGHT)
    fr = frame_base(D, W - int(60 * f), H - int(60 * f), f)
    m = Image.new('L', fr.size, 0); rr(ImageDraw.Draw(m), (0, 0, fr.size[0] - 1, fr.size[1] - 1), int(70 * f), fill=255)
    out.paste(fr, (int(30 * f), int(30 * f)), m)
    g = Image.new('RGBA', out.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
    gold_frame(gd, (int(60 * f), int(60 * f), int(2340 * f), int(840 * f)), f)
    if D == 'C':
        g = stepped(g, 4)
    out.alpha_composite(g)
    out.alpha_composite(medallion(head, int(700 * f)), (int(100 * f), int(100 * f)))
    if D == 'B':
        fnt = font(PIXF_B, 205 * f); tag = font(PIXF, 62 * f)
    elif D == 'C':
        fnt = font(TITLE, 270 * f); tag = font(ITAL, 84 * f)
    else:
        fnt = font(DECO, 225 * f); tag = font(ITAL, 84 * f)
    gt = gold_text(D, (W, H), 'Card Hunt', fnt, (int(1500 * f), int(400 * f)), 'mm')
    if D == 'C':
        gt = stepped(gt, 4)
    out.alpha_composite(gt)
    d = ImageDraw.Draw(out); d.fontmode = '1' if D == 'B' else 'L'
    d.text((int(1500 * f), int(640 * f)), 'Every store, one search', font=tag, fill=(214, 190, 134), anchor='mm')
    if D == 'B':
        out = out.resize((W * S, H * S), Image.NEAREST)
    return out


def icon(D, head, size=1024, scale=0.86, bleed=True):
    S = 8 if D == 'B' else 1
    W = size // S if D == 'B' else size; f = W / 1024
    out = frame_base(D, W, W, f * 1.6) if bleed else Image.new('RGBA', (W, W), (0, 0, 0, 0))
    out = out.convert('RGBA')
    med = medallion(head, int(W * scale))
    out.alpha_composite(med, ((W - med.size[0]) // 2, (W - med.size[1]) // 2))
    if D == 'B':
        out = out.resize((W * S, W * S), Image.NEAREST)
    return out


def head_crop(img, box):
    return img.crop(box)


def main(dirs):
    for D in dirs:
        od = os.path.join(HERE, D); os.makedirs(od, exist_ok=True)
        art = Image.open(os.path.join(ART, f'{D}-art.png')).convert('RGB')
        w, h = art.size
        hb = HEAD_FRAC
        head = art.crop((int(hb[0] * w), int(hb[1] * h), int(hb[2] * w), int(hb[3] * h)))
        if D == 'B':
            head = pixel_snap(head.resize((head.width // 8 * 8, head.height // 8 * 8)), 8).convert('RGB')
        front = card_front(D, art); front.save(os.path.join(od, 'card-front.png'))
        back = card_back(D, head); back.save(os.path.join(od, 'card-back.png'))
        logo(D, head).save(os.path.join(od, 'logo.png'))
        icon(D, head).save(os.path.join(od, 'icon-1024.png'))
        for name, size, sc in (('icon-512.png', 512, 0.86), ('icon-192.png', 192, 0.86),
                               ('icon-maskable-512.png', 512, 0.66), ('apple-touch-icon.png', 180, 0.8)):
            im = icon(D, head, 1024, sc).resize((size, size), Image.NEAREST if D == 'B' else Image.LANCZOS)
            im.save(os.path.join(od, name))
        mascot = os.path.join(ART, f'{D}-mascot.png')
        if os.path.exists(mascot):
            Image.open(mascot).save(os.path.join(od, 'mascot.png'))
        art.save(os.path.join(od, 'illustration.png'))
        print('composed', D)


HEAD_FRAC = (0.30, 0.10, 0.72, 0.62)   # head + hat + held card, as fractions of the art (set after render)

if __name__ == '__main__':
    main(sys.argv[1:] or ['A', 'B', 'C'])
