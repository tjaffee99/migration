#!/usr/bin/env node
// Build the "origins" world map:
//   web/geo/world.topo.json      <- world-atlas@2.0.2 countries-110m.json (Natural Earth 1:110m admin-0)
//   web/geo/world_50m.topo.json  <- world-atlas@2.0.2 countries-50m.json  (Natural Earth 1:50m admin-0)
//   web/geo/world_countries.csv  <- iso3,iso_numeric,name,lon,lat,continent,subregion
// Crosswalk: world-atlas feature ids are ISO 3166-1 numeric codes; ISO alpha-3, names and regions come
// from the world-countries@5.1.0 npm package (ODbL). lon/lat = spherical centroid of the country's
// largest polygon in the 1:50m geometry (falls back to world-countries `latlng` when the country has
// no polygon in Natural Earth 1:50m, e.g. tiny islands).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { feature } from 'topojson-client';
import { geoArea, geoCentroid } from 'd3-geo';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const RAW = path.join(ROOT, 'data/raw');
const OUT = path.join(ROOT, 'web/geo');
const countries = JSON.parse(fs.readFileSync(path.join(RAW, 'world_countries/countries.json'), 'utf8'));

// Natural Earth units without an ISO 3166-1 numeric code in world-atlas
const NO_ID = { Kosovo: { iso3: 'XKX', iso_numeric: '', name: 'Kosovo' } }; // XKX: user-assigned code used by the World Bank / EU
const CONTINENT = (c) => {
  if (c.region === 'Americas') return c.subregion === 'South America' ? 'South America' : 'North America';
  if (c.region === 'Antarctic') return 'Antarctica';
  return c.region;
};
const byNum = new Map();
for (const c of countries) if (c.ccn3) byNum.set(c.ccn3.padStart(3, '0'), c);

function annotate(topo, label) {
  const unmatched = [];
  for (const g of topo.objects.countries.geometries) {
    const neName = g.properties?.name ?? '';
    const num = g.id != null ? String(g.id).padStart(3, '0') : '';
    const c = num ? byNum.get(num) : null;
    if (c) g.properties = { iso3: c.cca3, iso_numeric: num, name: c.name.common, ne_name: neName };
    else if (NO_ID[neName]) g.properties = { ...NO_ID[neName], ne_name: neName };
    else { g.properties = { iso3: '', iso_numeric: num, name: neName, ne_name: neName }; unmatched.push(`${num || '(no id)'} ${neName}`); }
  }
  console.log(`[world] ${label}: ${topo.objects.countries.geometries.length} countries; without ISO alpha-3: ${unmatched.join('; ') || 'none'}`);
  return topo;
}

const t110 = annotate(JSON.parse(fs.readFileSync(path.join(RAW, 'world_atlas/countries-110m.json'), 'utf8')), '110m');
const t50 = annotate(JSON.parse(fs.readFileSync(path.join(RAW, 'world_atlas/countries-50m.json'), 'utf8')), '50m');
fs.writeFileSync(path.join(OUT, 'world.topo.json'), JSON.stringify(t110));
fs.writeFileSync(path.join(OUT, 'world_50m.topo.json'), JSON.stringify(t50));

// centroids from 50m geometry: largest polygon part
function mainCentroid(f) {
  const g = f.geometry; if (!g) return null;
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
  let best = null, bestA = -1;
  for (const p of polys) { const a = geoArea({ type: 'Polygon', coordinates: p }); if (a > bestA) { bestA = a; best = p; } }
  return best ? geoCentroid({ type: 'Polygon', coordinates: best }) : null;
}
const geomByIso3 = new Map();
for (const f of feature(t50, t50.objects.countries).features) if (f.properties.iso3) geomByIso3.set(f.properties.iso3, f);

const rows = [];
const seen = new Set();
const csvq = (s) => (/[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g, '""')}"` : String(s));
let fromGeom = 0, fromLatLng = 0;
const pushRow = (iso3, num, name, continent, subregion) => {
  const f = geomByIso3.get(iso3);
  let ll = f ? mainCentroid(f) : null;
  const c = countries.find((x) => x.cca3 === iso3);
  if (ll) fromGeom++; else if (c?.latlng?.length === 2) { ll = [c.latlng[1], c.latlng[0]]; fromLatLng++; }
  rows.push([iso3, num, name, ll ? ll[0].toFixed(4) : '', ll ? ll[1].toFixed(4) : '', continent, subregion].map(csvq).join(','));
  seen.add(iso3);
};
for (const c of [...countries].sort((a, b) => (a.cca3 < b.cca3 ? -1 : 1))) {
  const iso3 = c.cca3 === 'UNK' ? 'XKX' : c.cca3; // world-countries uses the UN interim code UNK for Kosovo
  pushRow(iso3, c.ccn3 ? c.ccn3.padStart(3, '0') : '', c.name.common, CONTINENT(c), c.subregion || '');
}
if (!seen.has('XKX')) pushRow('XKX', '', 'Kosovo', 'Europe', 'Southeast Europe');
fs.writeFileSync(path.join(OUT, 'world_countries.csv'), ['iso3,iso_numeric,name,lon,lat,continent,subregion', ...rows].join('\n') + '\n');
for (const fn of ['world.topo.json', 'world_50m.topo.json', 'world_countries.csv']) console.log(`[world] wrote web/geo/${fn} (${(fs.statSync(path.join(OUT, fn)).size / 1024).toFixed(0)} KB)`);
console.log(`[world] ${rows.length} CSV rows; centroid from 1:50m geometry: ${fromGeom}, from world-countries latlng: ${fromLatLng}`);
