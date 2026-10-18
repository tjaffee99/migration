#!/usr/bin/env node
// Structural checks of web/geo/world_hist.topo.json + world_hist_years.json:
//   - every year 1607-2026 present; every listed id exists and is valid on July 1 (from <= YYYY-07-01 <= to);
//   - every id valid on July 1 is listed; no id listed twice in a year;
//   - properties {id,name,sub,src,from,to,precision} present with the expected types/values;
//   - every polygon has non-empty geometry and d3-geo spherical winding (area < 2π sr, i.e. not inverted);
//   - prints polity counts and source mix for selected years.
// Exit code 1 on any error.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { feature } from 'topojson-client';
import { geoArea, geoBounds } from 'd3-geo';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GEO = path.resolve(HERE, '../../web/geo');
const topo = JSON.parse(fs.readFileSync(path.join(GEO, 'world_hist.topo.json')));
const idx = JSON.parse(fs.readFileSync(path.join(GEO, 'world_hist_years.json')));
const errs = [];
const err = (m) => { if (errs.length < 50) console.error('ERROR', m); errs.push(m); };

const objs = Object.keys(topo.objects);
if (objs.length !== 1 || objs[0] !== 'polities') err(`objects: ${objs}`);
const feats = feature(topo, topo.objects.polities).features;
const byId = new Map();
const SRC = new Set(['hb', 'cshapes', 'cshapes+hb', 'ne']);
const DATE = /^\d{4}-\d{2}-\d{2}$/;
let maxArea = 0;
for (const f of feats) {
  const p = f.properties;
  const keys = Object.keys(p).join(',');
  if (keys !== 'id,name,sub,src,from,to,precision') err(`${p.id}: property keys ${keys}`);
  if (byId.has(p.id)) err(`duplicate id ${p.id}`);
  byId.set(p.id, f);
  if (!p.name) err(`${p.id}: empty name`);
  if (typeof p.sub !== 'string') err(`${p.id}: sub not a string`);
  if (!SRC.has(p.src)) err(`${p.id}: src ${p.src}`);
  if (!DATE.test(p.from) || !DATE.test(p.to) || p.from > p.to) err(`${p.id}: dates ${p.from} ${p.to}`);
  if (![1, 2, 3].includes(p.precision)) err(`${p.id}: precision ${p.precision}`);
  const g = f.geometry;
  if (!g || !g.coordinates.length) { err(`${p.id}: empty geometry`); continue; }
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  for (const rings of polys) {
    const a = geoArea({ type: 'Polygon', coordinates: rings });
    if (a > 2 * Math.PI) err(`${p.id}: inverted polygon (area ${a.toFixed(3)} sr)`);
    maxArea = Math.max(maxArea, a);
  }
  const [[x0], [x1]] = geoBounds(f);
  if (!isFinite(x0) || !isFinite(x1)) err(`${p.id}: bad bounds`);
}
const years = idx.years;
for (let y = 1607; y <= 2026; y++) {
  const list = years[String(y)];
  if (!list) { err(`year ${y} missing`); continue; }
  const d = `${y}-07-01`;
  const seen = new Set();
  for (const id of list) {
    const f = byId.get(id);
    if (!f) { err(`${y}: unknown id ${id}`); continue; }
    if (seen.has(id)) err(`${y}: ${id} listed twice`);
    seen.add(id);
    if (!(f.properties.from <= d && d <= f.properties.to)) err(`${y}: ${id} not valid on ${d}`);
  }
  for (const f of feats) {
    const p = f.properties;
    if (p.from <= d && d <= p.to && !seen.has(p.id)) err(`${y}: valid id ${p.id} not listed`);
  }
}
const unused = feats.filter((f) => !Object.values(years).some((l) => l.includes(f.properties.id)));
if (unused.length) console.log(`note: ${unused.length} short-lived CShapes periods are valid on no July 1 (kept for exact dates), e.g. ${unused.slice(0, 3).map((f) => f.properties.id).join(', ')}`);
for (const y of [1607, 1700, 1776, 1815, 1816, 1850, 1880, 1885, 1886, 1914, 1925, 1950, 1990, 2019, 2026]) {
  const mix = {};
  for (const id of years[String(y)]) { const s = byId.get(id).properties.src; mix[s] = (mix[s] || 0) + 1; }
  console.log(`${y}: ${years[String(y)].length} polities ${JSON.stringify(mix)}`);
}
const size = fs.statSync(path.join(GEO, 'world_hist.topo.json')).size;
console.log(`${feats.length} polities, ${topo.arcs.length} arcs, ${(size / 1e6).toFixed(2)} MB; largest polygon ${(maxArea / (4 * Math.PI) * 100).toFixed(1)}% of the sphere`);
if (errs.length) { console.error(`${errs.length} errors`); process.exit(1); }
console.log('verify_hist: OK');
