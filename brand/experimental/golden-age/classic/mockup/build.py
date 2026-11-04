"""Build the vintage UI mockup page: python3 build.py -> mockup.html (textures and cards inlined)."""
import base64, io, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSIC = os.path.dirname(HERE)
BRAND = os.path.abspath(os.path.join(CLASSIC, '..', '..', '..'))


def uri(path, size, q=80):
    im = Image.open(path).convert('RGB'); im.thumbnail((size, size), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'JPEG', quality=q)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


def card(v):
    im = Image.open(os.path.join(CLASSIC, f'card-{v}.png'))
    bg = Image.new('RGB', im.size, (10, 10, 10)); bg.paste(im, (0, 0), im)
    bg.thumbnail((340, 480), Image.LANCZOS)
    b = io.BytesIO(); bg.save(b, 'JPEG', quality=82)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


I = {
    'search': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="10" cy="10" r="6.5"/><path d="M15 15l5.5 5.5" stroke-linecap="round"/></svg>',
    'lens': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="10" cy="10" r="5.5"/><path d="M14.2 14.2l5 5" stroke-linecap="round" stroke-width="3"/></svg>',
    'sun': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 7v10" /><path d="M12 7a5 5 0 0 1 0 10z" fill="currentColor"/></svg>',
    'home': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3l9 8h-3v9h-4v-6h-4v6H6v-9H3z"/></svg>',
    'heart': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
    'grid': '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/></svg>',
    'cart': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 4h3l2.4 10.5h9.8L20 7H7.2" stroke-linejoin="round"/><circle cx="10" cy="19" r="1.6" fill="currentColor"/><circle cx="17" cy="19" r="1.6" fill="currentColor"/></svg>',
    'deck': '<svg viewBox="0 0 24 24" fill="currentColor" width="30" height="30"><rect x="3" y="5" width="11" height="15" rx="1.5" transform="rotate(-8 8 12)" opacity=".6"/><rect x="9" y="4" width="11" height="15" rx="1.5"/></svg>',
}
STORES = [('E', 'EA Collectibles', '#9cc8d8'), ('L', 'La Mood', '#e8c8c0'), ('M', 'Mana Lounge', '#c8d8a8'), ('G', 'Gamers Emporium', '#e8d098'), ('P', 'Players C&C', '#d8d0c4')]


def nav(on=0):
    icons = ['home', 'heart', 'grid']
    items = ''.join(f'<span class="{"on" if i == on else ""}">{I[n]}</span>' for i, n in enumerate(icons))
    return f'<div class="nav"><div class="bar">{items}</div><div class="cart">{I["cart"]}<b>2</b></div></div>'


def home():
    chips = ''.join(f'<span class="chip">{c}</span>' for c in ('Sol Ring', 'Lightning Bolt', 'Rhystic Study'))
    stores = ''.join(f'<div class="store"><i style="background:{c}">{l}</i>{n}</div>' for l, n, c in STORES[:4])
    return f'''<div class="scr">
  <div class="hd"><div class="grow"><div class="brand">Card Hunt</div><div class="tag">Five shops, one search</div></div>
    <span class="pip">{I["lens"]}</span><span class="pip">{I["sun"]}</span></div>
  <div class="search well">{I["search"]}Search cards or products</div>
  <div class="chips">{chips}</div>
  <div class="panel"><span>{I["deck"]}</span><div class="grow"><div class="t">Price a whole decklist</div><div class="s">Paste your list and see every card at all five shops.</div></div><span class="chev">›</span></div>
  <div class="sec"><h2>Your shops</h2><span>5 of 5 searched</span></div>
  <div class="stores">{stores}</div>
  <div class="panel"><div class="grow"><div class="t">Hunt on every device</div><div class="s">Turn on sync to keep favourites, lists and your cart everywhere.</div></div><span class="chev">›</span></div>
  {nav(0)}
</div>'''


def results(cards):
    items = [('EA Collectibles', '$4.25 – $6.00', 'NM · LP'), ('Mana Lounge', '$3.99', 'Near Mint'),
             ('La Mood Comics', '$5.50', 'Lightly Played'), ('Gamers Emporium', '$4.75 – $7.25', 'NM · LP · MP')]
    cells = ''.join(f'<div class="res"><img src="{cards[i % 4]}" alt=""><div class="st">{s}</div><div class="pr">{p}</div><div class="cond">{c}</div></div>'
                    for i, (s, p, c) in enumerate(items))
    return f'''<div class="scr">
  <div class="hd"><div class="grow"><div class="brand" style="font-size:24px">Card Hunt</div></div><span class="pip">{I["lens"]}</span></div>
  <div class="search well q">{I["search"]}<span style="font-style:normal">Card Hunt</span></div>
  <div class="filt"><span class="chip">In stock</span><span class="chip">Lowest price</span><span class="chip">All shops</span></div>
  <div class="grid">{cells}</div>
  {nav(0)}
</div>'''


cards = [card(v) for v in ('black', 'blue', 'white', 'artifact')]
phones = ''
for theme, cap in (('dark', 'Dark · black frame'), ('light', 'Light · white frame')):
    phones += f'<figure><div class="ph {theme}">{home()}</div><figcaption>{cap} · home</figcaption></figure>\n'
for theme, cap in (('dark', 'Dark · results'), ('light', 'Light · results')):
    phones += f'<figure><div class="ph {theme}">{results(cards)}</div><figcaption>{cap}</figcaption></figure>\n'

html = open(os.path.join(HERE, 'mockup.src.html')).read()
rep = {'__PHONES__': phones,
       '__FRAME_BLACK__': uri(os.path.join(BRAND, 'textures', 'frame-black.jpg'), 600),
       '__FRAME_WHITE__': uri(os.path.join(BRAND, 'textures', 'frame-white.jpg'), 600),
       '__BOX_BLACK__': uri(os.path.join(BRAND, 'textures', 'box-black.jpg'), 500),
       '__BOX_WHITE__': uri(os.path.join(BRAND, 'textures', 'box-white.jpg'), 500)}
for k, v in rep.items():
    html = html.replace(k, v)
open(os.path.join(HERE, 'mockup.html'), 'w').write(html)
print('mockup.html', len(html) // 1024, 'KB')
