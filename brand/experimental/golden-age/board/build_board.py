"""Inline images and icon SVGs into the direction board: python3 build_board.py -> board.html"""
import base64, io, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GA = os.path.dirname(HERE)
BRAND = os.path.abspath(os.path.join(GA, '..', '..'))


def uri(path, size=None, fmt=None):
    im = Image.open(path)
    if size:
        im = im.convert('RGB'); im.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    fmt = fmt or ('PNG' if path.endswith('.png') else 'JPEG')
    im.save(buf, fmt, quality=82) if fmt == 'JPEG' else im.save(buf, fmt, optimize=True)
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(buf.getvalue()).decode()


EYE = ('<circle cx="32" cy="32" r="22" fill="#2a1d12"/>'
       '<circle cx="32" cy="32" r="16" fill="#c8923e"/><circle cx="32" cy="32" r="16" fill="url(#iris)"/>'
       '<ellipse cx="32" cy="32" rx="5" ry="9" fill="#0e0b08"/><circle cx="27" cy="26" r="3" fill="#fff4d0"/>'
       '<circle cx="32" cy="32" r="22" fill="none" stroke="#b08a3a" stroke-width="5"/>'
       '<circle cx="32" cy="32" r="24.5" fill="none" stroke="#5a4018" stroke-width="1.5"/>'
       '<path d="M6 20 C 20 8, 44 8, 58 20 L 56 22 C 44 14, 20 14, 8 22 Z" fill="#0e0b08"/>'
       '<defs><radialGradient id="iris" cx="40%" cy="40%" r="60%"><stop offset="0" stop-color="#f0c060"/>'
       '<stop offset=".7" stop-color="#b8701e"/><stop offset="1" stop-color="#5a3010"/></radialGradient></defs>')
EYEICON = '<rect width="64" height="64" rx="12" fill="#0e0b08"/><g transform="translate(4 6) scale(.875)">' + EYE.replace('id="iris"', 'id="iris2"').replace('url(#iris)', 'url(#iris2)') + '</g>'


def gear_path(cx, cy, r1, r2, n):
    import math
    pts = []
    for i in range(n * 2):
        a0, a1 = i / (n * 2) * 2 * math.pi, (i + 1) / (n * 2) * 2 * math.pi
        r = r1 if i % 2 else r2
        pts += [(cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(a1), cy + r * math.sin(a1))]
    return 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + 'Z'


GEARICON = ('<rect width="64" height="64" rx="12" fill="#1a1e1d"/>'
            f'<path d="{gear_path(32, 32, 22, 27, 14)}" fill="#9a7a3a"/>'
            '<circle cx="32" cy="32" r="17" fill="#23282a"/><circle cx="32" cy="32" r="13" fill="#c8d86a" opacity=".28"/>'
            '<rect x="25" y="21" width="14" height="20" rx="1.5" fill="#0c0e0d" stroke="#e8f0a0" stroke-width="1.6"/>'
            '<rect x="27.5" y="24" width="9" height="7" fill="#c8d86a"/>'
            '<path d="M24 20 C 26 14, 38 14, 40 20 L 44 21 L 20 21 Z" fill="#0c0e0d"/>')

html = open(os.path.join(HERE, 'board.src.html')).read()
rep = {
    '__EYE__': EYE, '__EYEICON__': EYEICON, '__GEARICON__': GEARICON,
    '__FRAME_BLACK__': uri(os.path.join(BRAND, 'textures', 'frame-black.jpg'), 400, 'JPEG'),
    '__BOX_BLACK__': uri(os.path.join(BRAND, 'textures', 'box-black.jpg'), 400, 'JPEG'),
    '__FRAME_ART__': uri(os.path.join(BRAND, 'textures', 'frame-artifact.jpg'), 400, 'JPEG'),
    '__BOX_ART__': uri(os.path.join(BRAND, 'textures', 'box-artifact.jpg'), 400, 'JPEG'),
    '__B_SPRITE__': uri(os.path.join(GA, 'art', 'B-sprite-native.png')),
    '__B_LOGO__': uri(os.path.join(GA, 'B', 'logo-native.png')),
    '__B_ICON__': uri(os.path.join(GA, 'B', 'icon-native.png')),
    '__B_FRONT__': uri(os.path.join(GA, 'B', 'card-front-native.png')),
    '__B_BACK__': uri(os.path.join(GA, 'B', 'card-back-native.png')),
    '__B_ART__': uri(os.path.join(GA, 'art', 'B-art-native.png')),
}
for k, v in rep.items():
    html = html.replace(k, v)
open(os.path.join(HERE, 'board.html'), 'w').write(html)
print('board.html', len(html) // 1024, 'KB')
