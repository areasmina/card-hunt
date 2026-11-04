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
const OTHER_GAMES = /final fantasy tcg|fabula ultima|gundam card|pok[eé]mon|yu-?gi-?oh|lorcana|one piece|flesh and blood|digimon|dragon ball|star wars unlimited/i;
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

// Stores people add themselves are passed as ?extra=host1,host2 and get the id "x:<host>".
const HOST_RE = /^(?=.{4,100}$)([a-z0-9-]+\.)+[a-z]{2,}$/;
const storeFor = id => STORES[id] || (id.startsWith('x:') && HOST_RE.test(id.slice(2)) ? { name: id.slice(2), host: id.slice(2) } : null);

async function searchStore(id, q) {
  const s = storeFor(id);
  // The exact phrase first ("Ultima" in quotes, so "Ultimate ..." products don't fill the 10 slots), then the usual search if that finds nothing.
  const fetchSug = async quoted => {
    const u = `https://${s.host}/search/suggest.json?q=${encodeURIComponent(quoted ? `"${q.replace(/"/g, '')}"` : q)}&resources[type]=product&resources[limit]=10&resources[options][unavailable_products]=last`;
    const get = () => fetch(u, { headers: { 'User-Agent': UA, Accept: 'application/json' }, cf: { cacheTtl: 300, cacheEverything: true } });
    let r; try { r = await get(); } catch { r = { ok: false, status: 0 }; }
    // A busy store (429) or a hiccup: wait a moment and ask once more before giving up on it.
    if (!r.ok && (r.status === 429 || r.status === 0 || r.status >= 500)) { await new Promise(res => setTimeout(res, 900)); r = await get(); }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const sug = await r.json();
    return (sug.resources?.results?.products || []).filter(p => !OTHER_GAMES.test(`${p.type || ''} ${p.vendor || ''} ${p.title}`));
  };
  const nq0 = norm(q), named = p => { const t = ` ${norm(baseName(p.title))} `; return nq0.split(' ').every(w => t.includes(` ${w} `)); };
  let prods = await fetchSug(true);
  if (!prods.some(named)) prods = await fetchSug(false);
  const nq = norm(q), words = nq.split(' ');
  const exact = prods.filter(p => norm(baseName(p.title)) === nq);
  // No exact name here: keep products whose own name has every word you typed as a whole word, so "Ultima"
  // finds "Ultima, Origin of Oblivion" but not "Ultimate Guard" sleeves or cards from the set "Ultimate Masters".
  prods = exact.length ? exact : prods.filter(p => { const t = ` ${norm(baseName(p.title))} `; return words.every(w => t.includes(` ${w} `)); });

  return prods.map(p => {
    const handle = (p.url || '').split('?')[0];
    const min = num(p.price_min) ?? num(p.price), max = num(p.price_max) ?? min;
    return {
      store: id, storeName: s.name,
      title: p.title, name: baseName(p.title), set: setLabel(p.title, p.body),
      url: `https://${s.host}${handle}`,
      image: img(p.featured_image?.url || p.image),
      foil: /\betched\b/i.test(p.title) || /\bfoil\b/i.test(p.title.replace(/\bnon[\s-]?foil\b/ig, '')),
      priceMin: min, priceMax: max,
      available: !!p.available, exact: exact.length > 0,
    };
  });
}

// Shopify CDN images resize on request: drop old "_32x32" size suffixes and ask for 180px.
function shopifySized(u) {
  try {
    const x = new URL(u); if (x.protocol === 'http:') x.protocol = 'https:';
    if (!/\/cdn\/shop\/|cdn\.shopify\.com/.test(x.href)) return x.href;
    x.pathname = x.pathname.replace(/_(\d+x\d*|x\d+|small|medium|large|grande|compact|icon|thumb)(@\dx)?(\.\w+)$/i, '$3');
    for (const k of ['width', 'height', 'crop']) x.searchParams.delete(k);
    x.searchParams.set('width', '180'); x.searchParams.set('height', '180'); x.searchParams.set('crop', 'center');
    return x.href;
  } catch { return u; }
}
// "store.401games.ca" -> "401games" when the store's real name can't be read.
function prettyHost(h) { const b = h.replace(/^(www|store|shop|en)\./, '').split('.')[0]; return b.charAt(0).toUpperCase() + b.slice(1); }

// Read a store's home page once: name, favicon logo, a banner picture, short description, theme colour,
// contact email and social links. Shopify sometimes rate-limits us, so retry once after a pause.
async function readHome(host) {
  const out = { name: '', logo: null, banner: null, description: '', color: null, email: null, phone: null, addresses: [], pages: [], socials: {} };
  try {
    const get = () => fetch(`https://${host}/`, { headers: { 'User-Agent': UA, Accept: 'text/html' }, redirect: 'follow' });
    let hp = await get();
    if (hp.status === 429) { await new Promise(r => setTimeout(r, 900)); hp = await get(); }
    if (!hp.ok) { out.status = hp.status; return out; }
    const t = (await hp.text()).slice(0, 600000);
    const dec = v => v.replace(/&amp;/g, '&').replace(/&#39;|&#039;/g, "'").replace(/&quot;/g, '"').replace(/&ndash;|&mdash;/g, '-').replace(/\s+/g, ' ').trim();
    const abs = u => { try { const x = new URL(dec(u).replace(/^\/\//, 'https://'), `https://${host}/`); if (x.protocol === 'http:') x.protocol = 'https:'; return x.href; } catch { return null; } };
    const meta = (attr, key) => { const m = t.match(new RegExp(`<meta[^>]+${attr}=["']${key}["'][^>]*content=["']([^"']*)["']`, 'i')) || t.match(new RegExp(`<meta[^>]+content=["']([^"']*)["'][^>]*${attr}=["']${key}["']`, 'i')); return m ? dec(m[1]) : ''; };
    out.name = meta('property', 'og:site_name');
    out.description = (meta('name', 'description') || meta('property', 'og:description')).slice(0, 400);
    out.color = (meta('name', 'theme-color').match(/^#[0-9a-f]{3,8}$/i) || [null])[0];
    const icon = t.match(/<link[^>]+rel=["'](?:apple-touch-icon|shortcut icon|icon)["'][^>]*>/i);
    const href = icon && icon[0].match(/href=["']([^"']+)["']/i);
    if (href) out.logo = shopifySized(abs(href[1]));
    // Banner: the first big picture in a slideshow or image-banner section, else the social share image.
    const sec = t.match(/(?:slideshow|image-banner|hero|banner)[\s\S]{0,4000}?<img[^>]+src=["']([^"']+\.(?:jpe?g|png|webp)[^"']*)["']/i);
    const og = meta('property', 'og:image');
    const pick = sec ? abs(sec[1]) : (og ? abs(og) : null);
    if (pick) { const x = new URL(pick); if (/\/cdn\/shop\/|cdn\.shopify\.com/.test(x.href)) { x.searchParams.delete('height'); x.searchParams.delete('crop'); x.searchParams.set('width', '1200'); } out.banner = x.href; }
    const mail = t.match(/mailto:([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})/i); if (mail) out.email = mail[1];
    // Shops often write their email and phone as plain text in the footer, so look in the visible text too.
    const text = t.replace(/<(script|style|svg)[\s\S]*?<\/\1>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/&nbsp;|&#160;/g, ' ');
    if (!out.email) { const m = text.match(/\b[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|ca|net|org|co|io|shop|store)\b/i); if (m && !/example|domain|sentry|shopify/i.test(m[0])) out.email = m[0]; }
    const tel = t.match(/href=["']tel:([+\d][\d\s().-]{6,20})["']/i) || text.match(/(?:\+?1[\s.-]?)?\(?\b[2-9]\d{2}\)?[\s.-]\d{3}[\s.-]\d{4}\b/);
    out.phone = tel ? (tel[1] || tel[0]).trim() : null;
    out.addresses = findAddresses(t, text);
    out.pages = [...new Set([...t.matchAll(/href=["'](\/pages\/[a-z0-9-]*(?:contact|location|our-store|stores|visit|about|hours|find-us)[a-z0-9-]*)["']/gi)].map(m => m[1].toLowerCase()))].slice(0, 4);
    const SOC = { instagram: /instagram\.com/, facebook: /facebook\.com/, tiktok: /tiktok\.com/, youtube: /youtube\.com|youtu\.be/, x: /(?:twitter|x)\.com/, discord: /discord\.(?:gg|com)/ };
    for (const m of t.matchAll(/href=["'](https?:\/\/[^"']+)["']/gi)) {
      const u = dec(m[1]); for (const [k, re] of Object.entries(SOC)) if (!out.socials[k] && re.test(u) && !/sharer|share\?|intent\/|\/plugins\//i.test(u)) out.socials[k] = u;
    }
  } catch (e) { out.error = String(e); }
  return out;
}

// A shop's street addresses (some have several locations), from its own site: structured data, the text around a
// Canadian postal code, or a "123 Something Street, City" line when there's no postal code.
const STREET = /\b(st|street|rd|road|ave|avenue|lane|ln|blvd|boulevard|dr|drive|way|cres|crescent|hwy|highway|pkwy|court|ct|place|pl|square|sq|trail|line|unit|suite|rue|chemin|boul)\b/i;
const PROV = '(?:ON|Ontario|QC|Qu[eé]bec|BC|British Columbia|AB|Alberta|MB|Manitoba|SK|Saskatchewan|NS|Nova Scotia|NB|New Brunswick|NL|PE|PEI)';
function findAddresses(html, text) {
  const out = [], add = a => { a = a.replace(/\s+,/g, ',').replace(/\s*,\s*/g, ', ').replace(/\s+/g, ' ').replace(/[\s,.-]+$/, '').trim();
    const k = (a.match(/^\d+\s+\S+/) || [a])[0].toLowerCase(); if (a.length > 8 && !out.some(x => (x.match(/^\d+\s+\S+/) || [x])[0].toLowerCase() === k)) out.push(a); };
  for (const m of html.matchAll(/"streetAddress"\s*:\s*"([^"]{3,120})"[^}]{0,300}?"addressLocality"\s*:\s*"([^"]{1,60})"/g)) add(`${m[1]}, ${m[2]}`);
  const flat = text.replace(/\s+/g, ' ').replace(/​/g, '');
  for (const m of flat.matchAll(/\b[A-CEGHJ-NPR-TVXY]\d[A-CEGHJ-NPR-TV-Z][ -]?\d[A-CEGHJ-NPR-TV-Z]\d\b/gi)) {
    const before = flat.slice(Math.max(0, m.index - 110), m.index);
    const starts = [...before.matchAll(/\b\d{1,6}[A-Za-z]?\s+(?=[A-Za-z])/g)].map(x => x.index);
    for (let i = starts.length - 1; i >= 0; i--) { const seg = before.slice(starts[i]); if (STREET.test(seg)) { add(seg + m[0]); break; } }
  }
  const noPc = new RegExp(String.raw`\b\d{1,6}\s+(?:[A-Z][\w.'-]*\s+){1,4}(?:St|Street|Rd|Road|Ave|Avenue|Dr|Drive|Blvd|Boulevard|Way|Lane|Cres|Crescent|Line|Hwy|Highway|Pkwy|Court|Ct|Place|Pl|Trail)\b\.?(?:\s*(?:E|W|N|S|East|West|North|South)\b)?(?:,?\s*(?:Unit|Suite|#)\s*[\w-]+)?\s*,?\s*(?:[A-Z][a-z]+\s*){1,2},?\s*${PROV}\b`, 'g');
  for (const m of flat.matchAll(noPc)) add(m[0]);
  return out.slice(0, 6);
}
function findAddress(html, text) { return findAddresses(html, text)[0] || null; }
// Free geocoding through OpenStreetMap's Nominatim (one lookup per address, cached for a month).
async function geocode(addr, ctx) {
  if (!addr) return null;
  const key = new Request('https://cardhunt.cache/v2/geo/' + encodeURIComponent(addr.toLowerCase()));
  const hit = await caches.default.match(key); if (hit) return hit.json();
  const tryQ = async q => { try { const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=ca&q=${encodeURIComponent(q)}`, { headers: { 'User-Agent': 'CardHunt/1.0 (https://areasmina.github.io/card-hunt/)' }, signal: AbortSignal.timeout(8000) }); const j = await r.json(); return j[0] ? { lat: +(+j[0].lat).toFixed(5), lon: +(+j[0].lon).toFixed(5) } : null; } catch { return null; } };
  const pc = (addr.match(/[A-Z]\d[A-Z][ -]?\d[A-Z]\d/i) || [])[0];
  // Photon (also free, built on OpenStreetMap) forgives spelling, like "Meadowbrooke" for Meadowbrook Drive.
  const photon = async q => { try { const r = await fetch(`https://photon.komoot.io/api/?limit=1&bbox=-141,41.6,-52.6,83.2&q=${encodeURIComponent(q)}`, { headers: { 'User-Agent': 'CardHunt/1.0 (https://areasmina.github.io/card-hunt/)' }, signal: AbortSignal.timeout(8000) }); const j = await r.json(); const c = j.features && j.features[0] && j.features[0].geometry.coordinates; return c ? { lat: +c[1].toFixed(5), lon: +c[0].toFixed(5) } : null; } catch { return null; } };
  const clean = addr.replace(/\b(unit|suite)\s*[\w-]+,?/i, '').replace(/,?\s*canada\b/i, '');
  const geo = await tryQ(clean) || await photon(clean) || (pc && await tryQ(pc.replace(/[ -]/, ' ')));
  if (geo) ctx.waitUntil(caches.default.put(key, Response.json(geo, { headers: { 'Cache-Control': 'public, max-age=2592000' } })));
  return geo;
}

// GET /recs?names=A|B|C -> cards that Commander decks with those cards often play (EDHREC's public card pages),
// ranked by how many of your cards they go with and how high EDHREC lists them. Each card page is cached for a week.
const REC_LISTS = /^(highliftcards|highsynergycards|topcards|creatures|instants|sorceries|utilityartifacts|enchantments|planeswalkers|manaartifacts)$/;
const edhSlug = n => n.split(' // ')[0].toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/['’,.!?:]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
async function edhCard(name, ctx) {
  const slug = edhSlug(name); if (!slug) return null;
  const key = new Request(`https://cardhunt.cache/v1/edh/${slug}`);
  const hit = await caches.default.match(key); if (hit) return hit.json();
  let lists = null;
  try {
    const r = await fetch(`https://json.edhrec.com/pages/cards/${slug}.json`, { headers: { 'User-Agent': UA, Accept: 'application/json' }, signal: AbortSignal.timeout(9000) });
    if (r.ok) { const j = await r.json(); lists = (j.container?.json_dict?.cardlists || []).filter(l => REC_LISTS.test(l.tag || ''))
      .map(l => ({ tag: l.tag, cards: (l.cardviews || []).slice(0, 12).map(c => ({ name: c.name, syn: typeof c.synergy === 'number' ? c.synergy : null })) })); }
    else if (r.status === 404) lists = [];
  } catch {}
  if (lists) ctx.waitUntil(caches.default.put(key, Response.json(lists, { headers: { 'Cache-Control': 'public, max-age=604800' } })));
  return lists;
}
async function recs(url, ctx) {
  const names = [...new Set(String(url.searchParams.get('names') || '').split('|').map(x => x.trim()).filter(x => x.length > 1 && x.length < 120))].slice(0, 6);
  if (!names.length) return Response.json({ ok: false, error: 'names required' }, { status: 400, headers: CORS });
  const mine = new Set(names.map(n => n.toLowerCase())), score = new Map();
  // EDHREC's "High Lift" list is the real synergy signal; its "top cards" are staples every deck plays, so those
  // (and anything on the Sol Ring page, a stand-in for "every deck") count for little.
  const [pages, base] = await Promise.all([Promise.all(names.map(n => edhCard(n, ctx))), edhCard('Sol Ring', ctx)]);
  const staple = new Set((base || []).flatMap(l => l.cards.map(c => c.name.toLowerCase())));
  pages.forEach((lists, i) => { if (!lists) return;
    for (const l of lists) { if (l.tag === 'topcards' || l.tag === 'manaartifacts') continue;
      l.cards.forEach((c, k) => {
        const low = c.name.toLowerCase(); if (mine.has(low)) return;
        let w = (l.tag === 'highliftcards' || l.tag === 'highsynergycards' ? 3 : 1) * (1 + (12 - k) / 12);
        if (staple.has(low)) w *= 0.2;
        const e = score.get(low) || { name: c.name, score: 0, with: [] }; e.score += w; if (!e.with.includes(names[i])) e.with.push(names[i]); score.set(low, e);
      }); } });
  const out = [...score.values()].sort((a, b) => b.score - a.score).slice(0, 18).map(e => ({ name: e.name, with: e.with.slice(0, 2) }));
  return Response.json({ ok: true, seeds: names, cards: out, found: pages.filter(Boolean).length },
    { headers: { ...CORS, 'Cache-Control': 'public, max-age=3600' } });
}

// GET /profile?host=<store host> -> what a store page shows. Cached for a day so repeat visits are instant.
async function profile(url, ctx) {
  const host = String(url.searchParams.get('host') || '').toLowerCase();
  if (!HOST_RE.test(host)) return Response.json({ ok: false, error: 'bad host' }, { status: 400, headers: CORS });
  const key = new Request(`https://cardhunt.cache/v5/profile/${host}`);
  const hit = url.searchParams.has('fresh') ? null : await caches.default.match(key);
  if (hit) return hit;
  const p = await readHome(host);
  // No address on the home page: look on the store's own contact or locations pages, then the usual ones.
  if (!p.status && !p.addresses.length) {
    const paths = [...new Set([...p.pages, '/pages/contact', '/pages/contact-us', '/pages/about-us'])].slice(0, 5);
    for (const path of paths) {
      try { let r = await fetch(`https://${host}${path}`, { headers: { 'User-Agent': UA, Accept: 'text/html' }, redirect: 'follow' });
        if (r.status === 429) { await new Promise(res => setTimeout(res, 1200)); r = await fetch(`https://${host}${path}`, { headers: { 'User-Agent': UA, Accept: 'text/html' }, redirect: 'follow' }); }
        if (!r.ok) continue;
        const t = (await r.text()).slice(0, 400000); const a = findAddresses(t, t.replace(/<(script|style|svg)[\s\S]*?<\/\1>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/&nbsp;|&#160;/g, ' '));
        if (a.length) { p.addresses = a; break; } } catch {}
    }
  }
  p.locations = [];
  for (const a of p.addresses.slice(0, 4)) { const g = await geocode(a, ctx); if (g) p.locations.push({ address: a, ...g }); }
  p.address = p.addresses[0] || null; p.geo = p.locations[0] ? { lat: p.locations[0].lat, lon: p.locations[0].lon } : null;
  delete p.pages;
  const policies = [['Refund policy', 'refund-policy'], ['Shipping policy', 'shipping-policy'], ['Privacy policy', 'privacy-policy'], ['Terms of service', 'terms-of-service']]
    .map(([title, slug]) => ({ title, url: `https://${host}/policies/${slug}` }));
  const ok = !p.status && !p.error;
  const res = Response.json({ ok, host, ...p, policies }, { headers: { ...CORS, 'Cache-Control': ok ? 'public, max-age=86400' : 'no-store' } });
  if (ok) ctx.waitUntil(caches.default.put(key, res.clone()));
  return res;
}

// GET /nearby?lat=&lon=&r=<metres>  ->  game, comic and hobby shops around a point, from OpenStreetMap.
// Public Overpass servers are often busy, so this tries a few in turn and caches answers for a day.
const OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'];
const CHAINS = /^(eb games|gamestop|toys ?r ?us|indigo|chapters|coles|build-a-bear|hallmark|spencer|walmart|best buy|mastermind|dollarama|goodwill|value village)/i;
const TCG_NAME = /card|game|comic|hobby|tcg|magic|pok[eé]mon|collect|dragon|dice|geek|nerd|mana|deck|lounge/i;
async function nearby(url, ctx) {
  const lat = +url.searchParams.get('lat'), lon = +url.searchParams.get('lon');
  const r = Math.round(Math.min(50000, Math.max(500, +url.searchParams.get('r') || 10000)) / 100) * 100;
  if (!isFinite(lat) || !isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return Response.json({ ok: false, error: 'bad location' }, { status: 400, headers: CORS });
  const key = new Request(`https://cardhunt.cache/v1/nearby/${lat.toFixed(3)},${lon.toFixed(3)},${r}`);
  const hit = await caches.default.match(key); if (hit) return hit;
  const dLat = r / 111320, dLon = r / (111320 * Math.max(0.2, Math.cos(lat * Math.PI / 180)));
  const a = `(${(lat - dLat).toFixed(4)},${(lon - dLon).toFixed(4)},${(lat + dLat).toFixed(4)},${(lon + dLon).toFixed(4)})`;  // a box is much faster than around: for Overpass
  const q = `[out:json][timeout:30];nwr["shop"~"^(games|hobby|comic|collector|anime|toys|trade|books|video_games|gift|second_hand)$"]${a};out center tags 300;`;
  let data = null, last = '';
  for (const ep of OVERPASS) {
    try {
      const res = await fetch(ep, { method: 'POST', body: 'data=' + encodeURIComponent(q), headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json', 'User-Agent': UA }, signal: AbortSignal.timeout(ep.includes('overpass-api.de') ? 40000 : 20000) });
      if (res.ok) { data = await res.json(); if (data && Array.isArray(data.elements)) break; }
      last += `${new URL(ep).host} ${res.status}; `; data = null; continue;
    } catch (e) { last += `${new URL(ep).host} ${e.name}; `; }
  }
  if (!data) return Response.json({ ok: false, error: "The map service is busy right now. Try again in a minute.", detail: last }, { headers: { ...CORS, 'Cache-Control': 'no-store' } });
  const seen = new Set(), stores = [];
  for (const e of data.elements) {
    const t = e.tags || {}, name = (t.name || '').trim(); if (!name || CHAINS.test(name) || /^(Q|P)\d/.test(t['brand:wikidata'] || '') && !/^(games|comic)$/.test(t.shop || '')) continue;
    const core = /^(games|hobby|comic|collector|anime)$/.test(t.shop || '');
    let web0 = t.website || t['contact:website'] || t.url || '';
    if (!core && !TCG_NAME.test(name + ' ' + web0)) continue;
    const plat = e.lat ?? e.center?.lat, plon = e.lon ?? e.center?.lon; if (plat == null) continue;
    if (Math.hypot((plat - lat) * 111320, (plon - lon) * 111320 * Math.cos(lat * Math.PI / 180)) > r * 1.02) continue;
    let web = web0;
    if (web && !/^https?:\/\//i.test(web)) web = 'https://' + web;
    const id = name.toLowerCase() + '|' + plat.toFixed(3); if (seen.has(id)) continue; seen.add(id);
    const addr = [[t['addr:housenumber'], t['addr:street']].filter(Boolean).join(' '), t['addr:city']].filter(Boolean).join(', ');
    stores.push({ name, lat: plat, lon: plon, website: web || null, shop: t.shop || null, addr: addr || null, tcg: core && TCG_NAME.test(name) || t.shop === 'games' });
  }
  stores.sort((x, y) => (!!y.website - !!x.website) || (y.tcg - x.tcg) || x.name.localeCompare(y.name));
  const out = Response.json({ ok: true, stores }, { headers: { ...CORS, 'Cache-Control': 'public, max-age=86400' } });
  ctx.waitUntil(caches.default.put(key, out.clone()));
  return out;
}

// Check a store someone wants to add: is it a Shopify store whose product search works from here,
// what is it called, and does it have a BinderPOS deck-list page that can fill its cart?
const DECK_PATHS = ['/pages/deck-list', '/pages/multi-card-search', '/pages/decklist', '/pages/deck-builder', '/pages/deckbuilder', '/pages/buylist-deck', '/pages/card-list', '/pages/multi-search'];
async function checkStore(raw) {
  let host = String(raw).trim().toLowerCase().replace(/^[a-z]+:\/\//, '').split(/[/?#]/)[0];
  if (!HOST_RE.test(host)) return Response.json({ ok: false, error: "That doesn't look like a website address." }, { headers: CORS });
  const get = (h, path, accept = 'application/json') => fetch(`https://${h}${path}`, { headers: { 'User-Agent': UA, Accept: accept }, redirect: 'follow' });
  let r;
  try { r = await get(host, '/search/suggest.json?q=sol%20ring&resources[type]=product&resources[limit]=1'); } catch { r = null; }
  if (r && r.url) { try { const h = new URL(r.url).host; if (HOST_RE.test(h)) host = h; } catch {} } // follow e.g. shop.com -> www.shop.com
  let ok = false; try { ok = !!(r && r.ok && (await r.json()).resources); } catch {}
  if (!ok && r && r.status === 429) return Response.json({ ok: false, host, busy: true, error: 'This store is busy right now. Try adding it again in a minute.' }, { headers: CORS });
  if (!ok) return Response.json({ ok: false, host, status: r && r.status, error: "Card Hunt can only search stores built on Shopify, and this one didn't answer like a Shopify store." }, { headers: CORS });
  const prof = await readHome(host);
  let name = prof.name || '', logo = prof.logo || null;
  if (!name) { try { const m = await get(host, '/meta.json'); if (m.ok) { const j = await m.json(); if (j.name) name = j.name; } } catch {} }
  if (!name) name = prettyHost(host);
  // Only BinderPOS deck-list pages accept a prefilled ?cards= list, so require its script on the page.
  let deck = null; const tried = [];
  for (const path of DECK_PATHS) {
    try {
      let d = await get(host, path, 'text/html');
      if (d.status === 429) { await new Promise(r => setTimeout(r, 800)); d = await get(host, path, 'text/html'); }
      tried.push(`${path}:${d.status}`);
      if (d.ok && new URL(d.url).pathname === path && /binderpos/i.test(await d.text())) { deck = `https://${new URL(d.url).host}${path}`; break; }
    } catch (e) { tried.push(`${path}:err`); }
  }
  // Shopify often rate-limits these page loads from Cloudflare, so say when the answer is a guess.
  return Response.json({ ok: true, host, name, logo, deck, deckUnsure: !deck && tried.some(t => t.endsWith(':429')), tried }, { headers: { ...CORS, 'Cache-Control': 'no-store' } });
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
    if (url.pathname === '/store') return checkStore(url.searchParams.get('url') || '');
    if (url.pathname === '/profile') return profile(url, ctx);
    if (url.pathname === '/nearby') return nearby(url, ctx);
    if (url.pathname === '/recs') return recs(url, ctx);
    if (url.pathname === '/geo') { const q = String(url.searchParams.get('q') || '').slice(0, 200).trim(); const g = q.length > 5 ? await geocode(q, ctx) : null;
      return Response.json(g ? { ok: true, ...g } : { ok: false, error: "Couldn't find that address. Try adding the city." }, { headers: CORS }); }
    if (url.pathname.startsWith('/sync/')) return sync(req, env, url.pathname.slice(6));
    if (url.pathname !== '/search') return new Response('Not found', { status: 404, headers: CORS });

    const q = (url.searchParams.get('q') || '').trim().slice(0, 120);
    if (q.length < 2) return Response.json({ error: 'q is required' }, { status: 400, headers: CORS });
    const extra = (url.searchParams.get('extra') || '').toLowerCase().split(',').map(h => h.trim()).filter(h => HOST_RE.test(h)).slice(0, 12).map(h => 'x:' + h);
    const ids = [...new Set([...(url.searchParams.get('stores') || Object.keys(STORES).join(',')).split(',').filter(id => STORES[id]), ...extra])];

    const cache = caches.default;
    const key = new Request(`https://cardhunt.cache/v6/search?q=${encodeURIComponent(norm(q))}&s=${ids.sort().join(',')}`);
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
