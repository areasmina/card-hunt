// Card Hunt search helper: searches several Shopify MTG stores at once.
// GET /search?q=<card name>[&stores=ea,mana]  ->  JSON list of matching products with price range and stock.
// Note: Shopify rate-limits Cloudflare Worker traffic on product pages (HTTP 429), so this only uses each
// store's predictive search endpoint, which gives product-level price (min/max) and availability.

const STORES = {
  ea:      { name: 'EA Collectibles', host: 'www.eacollectibles.com' },
  lamood:  { name: 'La Mood',         host: 'lamoodcomics.ca' },
  mana:    { name: 'Mana Lounge',     host: 'www.manalounge.ca' },
  ge:      { name: 'Gamers Emporium', host: 'gamersemporium.ca' },
  players: { name: 'Players',         host: 'playerscandc.com' },
};
const OTHER_GAMES = /pok[eé]mon|yu-?gi-?oh|lorcana|one piece|flesh and blood|digimon|dragon ball|star wars unlimited/i;
const UA = 'Mozilla/5.0 (compatible; CardHunt/1.0; +https://areasmina.github.io/card-hunt/)';
const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' };

const norm = s => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();

// "Lightning Bolt [Revised]", "Lightning Bolt (226) (4ED)", "Lightning Bolt (M11-149) - Magic 2011"
function baseName(title) { return title.split(/\s[\[(]|\s-\s/)[0].trim(); }
function setLabel(title, body) {
  const fromBody = (body || '').match(/<td>\s*Set:\s*<\/td>\s*<td>([^<]+)<\/td>/i);
  if (fromBody) return fromBody[1].trim();
  const sq = title.match(/\[([^\]]+)\]\s*$/); if (sq) return sq[1];
  const dash = title.match(/\s-\s(.+)$/); if (dash) return dash[1].replace(/:\s*\(.*\)$/, '');
  const paren = title.match(/\(([A-Z0-9]{2,6})\)\s*$/); if (paren) return paren[1];
  return '';
}
const num = v => (v == null || v === '') ? null : Number(v);
const img = u => !u ? null : (u.startsWith('//') ? 'https:' + u : u);

async function searchStore(id, q) {
  const s = STORES[id];
  const u = `https://${s.host}/search/suggest.json?q=${encodeURIComponent(q)}&resources[type]=product&resources[limit]=10&resources[options][unavailable_products]=last`;
  const r = await fetch(u, { headers: { 'User-Agent': UA, Accept: 'application/json' }, cf: { cacheTtl: 300, cacheEverything: true } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const sug = await r.json();
  let prods = (sug.resources?.results?.products || []).filter(p => !OTHER_GAMES.test(`${p.type || ''} ${p.vendor || ''} ${p.title}`));
  const nq = norm(q), words = nq.split(' ');
  const exact = prods.filter(p => norm(baseName(p.title)) === nq);
  prods = exact.length ? exact : prods.filter(p => { const t = norm(p.title); return words.every(w => t.includes(w)); });

  return prods.map(p => {
    const handle = (p.url || '').split('?')[0];
    const min = num(p.price_min) ?? num(p.price), max = num(p.price_max) ?? min;
    return {
      store: id, storeName: s.name,
      title: p.title, name: baseName(p.title), set: setLabel(p.title, p.body),
      url: `https://${s.host}${handle}`,
      image: img(p.featured_image?.url || p.image),
      foil: /\bfoil\b/i.test(p.title),
      priceMin: min, priceMax: max,
      available: !!p.available,
    };
  });
}

// Sync: a device keeps a random secret code; the saved data is stored in KV under a hash of it.
// GET /sync/<code> -> {at, data} or 404. PUT /sync/<code> with {at, data} stores it.
async function sync(req, env, code) {
  if (!/^[a-z0-9]{16,64}$/.test(code)) return Response.json({ error: 'bad code' }, { status: 400, headers: CORS });
  if (!env.SYNC) return Response.json({ error: 'sync storage not set up' }, { status: 503, headers: CORS });
  const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('cardhunt:' + code));
  const key = 'u:' + [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join('');
  const nc = { ...CORS, 'Cache-Control': 'no-store' };
  if (req.method === 'GET') {
    const v = await env.SYNC.get(key);
    return v ? new Response(v, { headers: { ...nc, 'Content-Type': 'application/json' } }) : Response.json({ error: 'not found' }, { status: 404, headers: nc });
  }
  if (req.method === 'PUT') {
    const body = await req.text();
    if (body.length > 1_000_000) return Response.json({ error: 'too big' }, { status: 413, headers: nc });
    let j; try { j = JSON.parse(body); } catch { return Response.json({ error: 'bad json' }, { status: 400, headers: nc }); }
    if (typeof j.at !== 'number' || typeof j.data !== 'object') return Response.json({ error: 'bad shape' }, { status: 400, headers: nc });
    await env.SYNC.put(key, body);
    return Response.json({ ok: true, at: j.at }, { headers: nc });
  }
  return new Response('Method not allowed', { status: 405, headers: nc });
}

export default {
  async fetch(req, env, ctx) {
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
    const url = new URL(req.url);
    if (url.pathname === '/') return new Response('Card Hunt helper is running. Try /search?q=Lightning+Bolt', { headers: CORS });
    if (url.pathname.startsWith('/sync/')) return sync(req, env, url.pathname.slice(6));
    if (url.pathname !== '/search') return new Response('Not found', { status: 404, headers: CORS });

    const q = (url.searchParams.get('q') || '').trim().slice(0, 120);
    if (q.length < 2) return Response.json({ error: 'q is required' }, { status: 400, headers: CORS });
    const ids = (url.searchParams.get('stores') || Object.keys(STORES).join(',')).split(',').filter(id => STORES[id]);

    const cache = caches.default;
    const key = new Request(`https://cardhunt.cache/v2/search?q=${encodeURIComponent(norm(q))}&s=${ids.sort().join(',')}`);
    const hit = url.searchParams.has('fresh') ? null : await cache.match(key);
    if (hit) return hit;

    const settled = await Promise.allSettled(ids.map(id => searchStore(id, q)));
    const results = [], errors = [];
    settled.forEach((r, i) => r.status === 'fulfilled' ? results.push(...r.value) : errors.push({ store: ids[i], error: String(r.reason?.message || r.reason) }));

    const res = Response.json({ query: q, at: new Date().toISOString(), results, errors },
      { headers: { ...CORS, 'Cache-Control': 'public, max-age=600' } });
    if (!errors.length) ctx.waitUntil(cache.put(key, res.clone()));
    return res;
  },
};
