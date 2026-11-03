// Builds stores-ca.json: Canada's game, comic and hobby shops from OpenStreetMap, for the "Find nearby" map.
// Run with `node scripts/build-stores.mjs`. A GitHub Action runs it every week so the list stays fresh.
// Public Overpass servers are slow and sometimes down, so each province is fetched on its own, with retries.
import { writeFileSync, readFileSync, existsSync } from 'node:fs';

const PROVINCES = ['ON', 'QC', 'BC', 'AB', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE', 'YT', 'NT', 'NU'];
const SERVERS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter'];
const CHAINS = /^(eb games|gamestop|toys ?r ?us|indigo|chapters|coles|build-a-bear|hallmark|spencer|walmart|best buy|mastermind|dollarama|goodwill|value village|mrs\.? ?tiggy|winners|homesense|showcase|lego|disney|claire)/i;
const TCG = /card|game|comic|hobby|tcg|magic|pok[eé]mon|collect|dragon|dice|geek|nerd|mana|deck|lounge|guild|quest|tabletop|board|figure|anime|manga/i;
const CORE = /^(games|hobby|comic|collector|anime)$/;
const SHOPS = ['games', 'hobby', 'comic', 'collector', 'anime', 'toys', 'books', 'video_games', 'trade', 'gift', 'second_hand'];
const OUT = new URL('../stores-ca.json', import.meta.url);

async function province(pv) {
  const q = `[out:json][timeout:240];area["ISO3166-2"="CA-${pv}"]->.p;nwr["shop"~"^(${SHOPS.join('|')})$"](area.p);out center tags;`;
  for (let attempt = 0; attempt < 3; attempt++) {
    for (const ep of SERVERS) {
      try {
        const r = await fetch(ep, { method: 'POST', body: 'data=' + encodeURIComponent(q), headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'CardHunt/1.0 (areasmina.github.io/card-hunt)' }, signal: AbortSignal.timeout(300000) });
        if (!r.ok) { console.log(pv, ep, r.status); continue; }
        const j = await r.json();
        if (j.remark) { console.log(pv, ep, 'incomplete:', j.remark); continue; }   // a timed-out answer is partial
        console.log(pv, ep, j.elements.length); return j.elements;
      } catch (e) { console.log(pv, ep, e.name); }
    }
    await new Promise(res => setTimeout(res, 10000));
  }
  return null;
}

const old = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : null;
const elements = []; let failed = 0;
for (const pv of PROVINCES) { const e = await province(pv); if (e) elements.push(...e); else failed++; }
if (failed > 2 || (old && elements.length < 0.7 * (old.raw || 0))) { console.log('Too many provinces failed; keeping the current list.'); process.exit(0); }

const stores = [], seen = new Set();
for (const e of elements) {
  const t = e.tags || {}, name = (t.name || '').trim(); if (!name || CHAINS.test(name)) continue;
  const shop = (t.shop || '').split(';')[0];
  let web = t.website || t['contact:website'] || t.url || '';
  if (!CORE.test(shop) && !TCG.test(name + ' ' + web)) continue;
  if (t['brand:wikidata'] && !/^(games|comic)$/.test(shop)) continue;          // big chains
  const lat = e.lat ?? e.center?.lat, lon = e.lon ?? e.center?.lon; if (lat == null) continue;
  if (web && !/^https?:\/\//i.test(web)) web = 'https://' + web;
  const k = name.toLowerCase() + '|' + lat.toFixed(3); if (seen.has(k)) continue; seen.add(k);
  const addr = [[t['addr:housenumber'], t['addr:street']].filter(Boolean).join(' '), t['addr:city']].filter(Boolean).join(', ');
  stores.push([name, +lat.toFixed(5), +lon.toFixed(5), web, SHOPS.indexOf(shop) + 1, addr]);
}
stores.sort((a, b) => a[1] - b[1] || a[2] - b[2]);
if (old && JSON.stringify(old.stores) === JSON.stringify(stores)) { console.log('No changes'); process.exit(0); }
writeFileSync(OUT, JSON.stringify({ at: new Date().toISOString().slice(0, 10), source: 'OpenStreetMap contributors (ODbL)', raw: elements.length,
  fields: ['name', 'lat', 'lon', 'website', 'shop', 'address'], shops: SHOPS, stores }));
console.log('kept', stores.length, 'of', elements.length, 'with a website', stores.filter(s => s[3]).length);
