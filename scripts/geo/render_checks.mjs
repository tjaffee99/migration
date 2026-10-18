#!/usr/bin/env node
// Visual verification: render web/geo/us_historical.topo.json for selected years (July 1 snapshot,
// via us_historical_years.json) to PNG with d3-geo + headless Chromium.
// Usage: node render_checks.mjs OUT_DIR [year ...] [--proj=albersusa|conic]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { feature } from 'topojson-client';
import { geoAlbersUsa, geoConicEqualArea, geoPath } from 'd3-geo';
import { svgsToPngs, hashColor } from './lib_render.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GEO = path.resolve(HERE, '../../web/geo');
const args = process.argv.slice(2);
const outDir = args.find((a) => !a.startsWith('--') && !/^\d{4}$/.test(a));
const projName = (args.find((a) => a.startsWith('--proj=')) || '--proj=albersusa').slice(7);
const GAPS = args.includes('--gaps'); // fill-only on black: gaps/slivers between polygons show up as dark lines
const topoFile = (args.find((a) => a.startsWith('--topo=')) || '').slice(7) || null;
const ZOOMS = { ne: [[-81, 36.5], [-69.5, 45.5]], gulf: [[-95, 28.5], [-84, 33.5]], west: [[-125, 31], [-102, 49.5]] };
let years = args.filter((a) => /^\d{4}$/.test(a)).map(Number);
if (!years.length) years = [1610, 1650, 1700, 1750, 1776, 1783, 1790, 1803, 1810, 1820, 1840, 1850, 1860, 1870, 1880, 1900, 1912, 1959, 2024];
if (!outDir) { console.error('usage: node render_checks.mjs OUT_DIR [years...]'); process.exit(1); }
fs.mkdirSync(outDir, { recursive: true });

const topo = JSON.parse(fs.readFileSync(topoFile || path.join(GEO, 'us_historical.topo.json')));
const idx = JSON.parse(fs.readFileSync(path.join(GEO, 'us_historical_years.json')));
const all = feature(topo, topo.objects.jurisdictions || Object.values(topo.objects)[0]).features;
const byId = new Map(all.map((f) => [f.properties.id, f]));
const W = 1000, H = 680;
const POWER = { Spain: '#f2d98a', France: '#a9c4ea', 'Great Britain': '#efb3ae', 'Great Britain (disputed)': '#f3cfc9', Mexico: '#b9dfa6', Russia: '#cdb7e3', Hawaii: '#9fd9d2', '': '#e3e3e3' };
const TYPE_STROKE = { colony: '#5a3d1e', state: '#222', territory: '#1d4f91', district: '#7a1f6e', unorganized: '#777', other: '#555' };
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

function projection() {
  if (ZOOMS[projName]) { const [[x0, y0], [x1, y1]] = ZOOMS[projName]; return geoConicEqualArea().parallels([29.5, 45.5]).rotate([96, 0]).fitExtent([[10, 40], [W - 10, H - 70]], { type: 'MultiPoint', coordinates: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] }); }
  if (projName === 'conic') return geoConicEqualArea().parallels([29.5, 45.5]).rotate([96, 0]).fitExtent([[10, 40], [W - 10, H - 70]], { type: 'MultiPoint', coordinates: [[-125, 24], [-66, 24], [-66, 49.5], [-125, 49.5], [-96, 50]] });
  return geoAlbersUsa().fitExtent([[10, 40], [W - 10, H - 100]], { type: 'MultiPoint', coordinates: [[-125, 24.5], [-66.9, 24.5], [-66.9, 49.4], [-125, 49.4], [-160, 20], [-150, 65]] });
}
const items = [];
for (const y of years) {
  const ids = idx.years[y] || [];
  const feats = ids.map((id) => byId.get(id)).filter(Boolean);
  const proj = projection();
  const pathGen = geoPath(proj);
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><rect width="100%" height="100%" fill="${GAPS ? '#000' : '#fbfaf7'}"/>`;
  const ctx = feats.filter((f) => f.properties.context), jur = feats.filter((f) => !f.properties.context);
  for (const f of ctx) svg += `<path d="${pathGen(f) || ''}" fill="${POWER[f.properties.power] || '#ddd'}" ${GAPS ? 'stroke="none"' : 'stroke="#999" stroke-width="0.4" stroke-dasharray="2,2"'}/>`;
  for (const f of jur) svg += `<path d="${pathGen(f) || ''}" fill="${hashColor(f.properties.id.replace(/_v\d+$|_\d{8}$/, ''))}" ${GAPS ? 'stroke="none"' : `fill-opacity="0.9" stroke="${TYPE_STROKE[f.properties.type] || '#333'}" stroke-width="0.7"`}/>`;
  for (const f of jur) {
    const c = pathGen.centroid(f); if (!c || !isFinite(c[0])) continue;
    const a = pathGen.area(f); const t = a > 2500 ? f.properties.name.replace(/ Territory$/, ' Terr.') : a > 300 ? (f.properties.abbr || '') : '';
    if (t) svg += `<text x="${c[0].toFixed(1)}" y="${c[1].toFixed(1)}" font-family="sans-serif" font-size="${a > 2500 ? 9 : 7.5}" text-anchor="middle" fill="#111" stroke="#fff" stroke-width="2.2" paint-order="stroke">${esc(t)}</text>`;
  }
  // legend for context powers in this year
  const powers = [...new Map(ctx.map((f) => [f.properties.name, f.properties.power])).entries()];
  let ly = H - 8 - 15 * (Math.ceil(powers.length / 2) - 1);
  powers.forEach(([name, power], i) => {
    const x = 12 + (i % 2) * 490, yy = ly + Math.floor(i / 2) * 15;
    svg += `<rect x="${x}" y="${yy - 9}" width="12" height="10" fill="${POWER[power] || '#ddd'}" stroke="#999"/><text x="${x + 16}" y="${yy}" font-family="sans-serif" font-size="10" fill="#333">${esc(name)}</text>`;
  });
  svg += `<text x="12" y="24" font-family="sans-serif" font-size="18" font-weight="bold" fill="#111">${y} (July 1) - ${jur.length} jurisdictions, ${ctx.length} context polygons [${projName}]</text></svg>`;
  const tag = (GAPS ? '_gaps' : '') + (topoFile ? '_' + path.basename(topoFile).replace(/\.topo\.json$|\.json$/, '') : '');
  items.push({ svg, file: path.join(outDir, `us_${y}_${projName}${tag}.png`), width: W, height: H });
}
await svgsToPngs(items);
console.log(`rendered ${items.length} PNGs to ${outDir}`);
