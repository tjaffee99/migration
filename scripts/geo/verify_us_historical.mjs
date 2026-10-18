#!/usr/bin/env node
// Consistency checks for web/geo/us_historical.topo.json + us_historical_years.json:
//  * every id in the year index exists and is valid on July 1 of that year;
//  * no polygon is wound "inside out" for d3-geo (spherical area > hemisphere);
//  * for each distinct July-1 set: coverage of the modern outline (jurisdictions + context) and
//    overlapping jurisdictions (pairs overlapping by > 100 km2), via a planar mosaic.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import mapshaper from 'mapshaper';
import { feature } from 'topojson-client';
import { geoArea } from 'd3-geo';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GEO = path.resolve(HERE, '../../web/geo');
const topo = JSON.parse(fs.readFileSync(path.join(GEO, 'us_historical.topo.json')));
const idx = JSON.parse(fs.readFileSync(path.join(GEO, 'us_historical_years.json')));
const feats = feature(topo, topo.objects.jurisdictions).features;
const byId = new Map(feats.map((f) => [f.properties.id, f]));
const R = 6371.0088;
let errors = 0;
const err = (m) => { errors++; console.log('ERROR', m); };

if (byId.size !== feats.length) err('duplicate ids');
for (const f of feats) {
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  for (const p of polys) if (geoArea({ type: 'Polygon', coordinates: p }) > 2 * Math.PI) { err(`${f.properties.id}: inverted ring`); break; }
  for (const k of ['id', 'name', 'type', 'start', 'end', 'fips', 'abbr']) if (!(k in f.properties)) err(`${f.properties.id}: missing ${k}`);
  if (!['colony', 'state', 'territory', 'district', 'unorganized', 'other'].includes(f.properties.type)) err(`${f.properties.id}: bad type`);
  if (!(f.properties.start <= f.properties.end)) err(`${f.properties.id}: start > end`);
}
const referenced = new Set();
for (let y = idx.first_year; y <= idx.last_year; y++) {
  const ids = idx.years[y]; const d = `${y}-07-01`;
  if (!ids || !ids.length) { err(`year ${y}: empty`); continue; }
  for (const id of ids) {
    referenced.add(id);
    const f = byId.get(id); if (!f) { err(`year ${y}: unknown id ${id}`); continue; }
    if (!(f.properties.start <= d && d <= f.properties.end)) err(`year ${y}: ${id} not valid on ${d}`);
  }
  // completeness: every jurisdiction valid on July 1 must be listed
  for (const f of feats) if (f.properties.start <= d && d <= f.properties.end && !ids.includes(f.properties.id)) err(`year ${y}: ${f.properties.id} valid but not listed`);
}
console.log(`geometries: ${feats.length} (${feats.filter((f) => f.properties.context).length} context); referenced by the July-1 index: ${referenced.size}`);

// coverage & overlaps per distinct July-1 set
const outlineIds = idx.years[idx.last_year];
const sets = new Map();
for (let y = idx.first_year; y <= idx.last_year; y++) { const k = idx.years[y].slice().sort().join(','); if (!sets.has(k)) sets.set(k, []); sets.get(k).push(y); }
const run = async (fcIn) => JSON.parse((await mapshaper.applyCommands('-i in.json -mosaic calc="ids=collect(fid)" -each "A=this.area/1e6" -o o.json format=geojson', { 'in.json': fcIn }))['o.json']);
let outlineKm2 = null;
const overlapReport = new Map();
const coverage = [];
for (const [k, years] of sets) {
  const ids = k.split(',');
  const fc = { type: 'FeatureCollection', features: ids.map((id, i) => ({ type: 'Feature', properties: { fid: i }, geometry: byId.get(id).geometry })) };
  const tiles = (await run(fc)).features;
  const cov = tiles.reduce((a, t) => a + t.properties.A, 0);
  if (outlineKm2 === null || years.includes(idx.last_year)) outlineKm2 = outlineKm2 ?? cov;
  coverage.push([years[0], cov]);
  for (const t of tiles) {
    const jur = (t.properties.ids || []).filter((i) => !byId.get(ids[i]).properties.context);
    const ctx = (t.properties.ids || []).filter((i) => byId.get(ids[i]).properties.context);
    if (ctx.length && jur.length && t.properties.A > 1) err(`years ${years[0]}..: context overlaps jurisdiction (${t.properties.A.toFixed(0)} km2)`);
    if (jur.length > 1) {
      const key = jur.map((i) => ids[i]).sort().join(' + ');
      const e = overlapReport.get(key) || { A: 0, years: new Set() };
      e.A = Math.max(e.A, t.properties.A + (e.cur === years[0] ? e.A : 0)); e.cur = years[0];
      years.forEach((y) => e.years.add(y)); overlapReport.set(key, e);
    }
  }
}
const ref = coverage.find(([y]) => y >= 1959)?.[1];
const bad = coverage.filter(([, c]) => Math.abs(c - ref) > ref * 0.002);
console.log(`coverage of the modern outline (${ref.toFixed(0)} km2) checked for ${coverage.length} distinct July-1 sets; deviations > 0.2%: ${bad.length ? bad.map(([y, c]) => `${y}:${c.toFixed(0)}`).join(' ') : 'none'}`);
const rows = [...overlapReport.entries()].map(([k, e]) => [k, e.years]).filter(([k]) => true);
const fmtYears = (s) => { const a = [...s].sort((x, y) => x - y); const out = []; let st = a[0], pv = a[0]; for (const y of a.slice(1).concat([null])) { if (y === pv + 1) { pv = y; continue; } out.push(st === pv ? `${st}` : `${st}-${pv}`); st = pv = y; } return out.join(','); };
console.log(`overlapping jurisdiction pairs on July-1 snapshots (${rows.length}):`);
const agg = new Map();
for (const [k, ys] of rows) { const base = k.replace(/_v\d+|_\d{8}/g, ''); const e = agg.get(base) || new Set(); ys.forEach((y) => e.add(y)); agg.set(base, e); }
for (const [k, ys] of [...agg.entries()].sort((a, b) => Math.min(...a[1]) - Math.min(...b[1]))) console.log(`  ${k}: ${fmtYears(ys)}`);
console.log(errors ? `${errors} errors` : 'OK: no errors');
process.exit(errors ? 1 : 0);
