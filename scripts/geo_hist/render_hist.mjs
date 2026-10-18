#!/usr/bin/env node
// Visual check of web/geo/world_hist.topo.json: one PNG per year (July 1 set from world_hist_years.json),
// drawn like the page (d3 geoEqualEarth().rotate([90, 0]), 1200 px wide), polities lightly coloured by
// sovereign (dependencies) or own name, thin borders, Natural Earth 50m land in grey underneath (gaps).
//   node render_hist.mjs OUT_DIR [year ...] [--zoom=lon0,lat0,lon1,lat1[:tag]] [--gaps] [--nolabels]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { feature, merge } from 'topojson-client';
import { geoPath, geoEqualEarth, geoGraticule10 } from 'd3-geo';
import { svgsToPngs, hashColor, esc, pageProjection } from './lib_render.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GEO = path.resolve(HERE, '../../web/geo');
const args = process.argv.slice(2);
const outDir = args.find((a) => !a.startsWith('--') && !/^\d{4}$/.test(a));
let years = args.filter((a) => /^\d{4}$/.test(a)).map(Number);
if (!years.length) years = [1610, 1700, 1776, 1815, 1850, 1880, 1890, 1914, 1925, 1950, 1990, 2026];
const zoomArg = (args.find((a) => a.startsWith('--zoom=')) || '').slice(7);
const GAPS = args.includes('--gaps');
const LABELS = !args.includes('--nolabels');
fs.mkdirSync(outDir, { recursive: true });

const topo = JSON.parse(fs.readFileSync(path.join(GEO, 'world_hist.topo.json')));
const idx = JSON.parse(fs.readFileSync(path.join(GEO, 'world_hist_years.json')));
const all = feature(topo, topo.objects.polities).features;
const byId = new Map(all.map((f) => [f.properties.id, f]));
const ne = JSON.parse(fs.readFileSync(path.join(GEO, 'world_50m.topo.json')));
const land = feature(ne, ne.objects.land);

const W = 1200;
let proj, H, tag = '';
if (zoomArg) {
  const [bb, t] = zoomArg.split(':');
  const [x0, y0, x1, y1] = bb.split(',').map(Number);
  tag = '_' + (t || 'zoom');
  H = 820;
  proj = geoEqualEarth().rotate([90, 0]).fitExtent([[5, 30], [W - 5, H - 5]],
    { type: 'MultiPoint', coordinates: [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [(x0 + x1) / 2, y0], [(x0 + x1) / 2, y1]] });
} else {
  proj = pageProjection(W);
  H = Math.ceil(geoPath(proj).bounds({ type: 'Sphere' })[1][1]) + 2;
}
const pathGen = geoPath(proj);
const items = [];
for (const y of years) {
  const ids = idx.years[String(y)] || [];
  const feats = ids.map((id) => byId.get(id)).filter(Boolean);
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><rect width="100%" height="100%" fill="#fff"/>`;
  svg += `<path d="${pathGen({ type: 'Sphere' })}" fill="${GAPS ? '#000' : '#dfe9f2'}"/>`;
  if (!GAPS) svg += `<path d="${pathGen(geoGraticule10())}" fill="none" stroke="#c9d6e2" stroke-width="0.3"/>`;
  svg += `<path d="${pathGen(land)}" fill="${GAPS ? '#ff00ff' : '#9a9a9a'}"/>`;
  for (const f of feats) {
    const d = pathGen(f); if (!d) continue;
    const p = f.properties;
    if (GAPS) { svg += `<path d="${d}" fill="#fff"/>`; continue; }
    const col = hashColor(p.sub || p.name);
    svg += `<path d="${d}" fill="${col}" fill-opacity="${p.sub ? 0.55 : 0.9}" stroke="#333" stroke-width="${zoomArg ? 0.6 : 0.35}"><title>${esc(p.name)}</title></path>`;
  }
  if (LABELS && !GAPS) {
    for (const f of feats) {
      const a = pathGen.area(f); if (a < (zoomArg ? 900 : 250)) continue;
      const c = pathGen.centroid(f); if (!c || !isFinite(c[0])) continue;
      const p = f.properties;
      const t = p.sub ? `${p.name} (${p.sub})` : p.name;
      svg += `<text x="${c[0].toFixed(1)}" y="${c[1].toFixed(1)}" font-family="sans-serif" font-size="${a > 6000 ? 8 : 6.5}" text-anchor="middle" fill="#111" stroke="#fff" stroke-width="1.6" paint-order="stroke">${esc(t)}</text>`;
    }
  }
  const srcs = {}; feats.forEach((f) => { srcs[f.properties.src] = (srcs[f.properties.src] || 0) + 1; });
  svg += `<text x="10" y="20" font-family="sans-serif" font-size="15" font-weight="bold" fill="#111" stroke="#fff" stroke-width="3" paint-order="stroke">${y} (July 1) - ${feats.length} polities ${esc(JSON.stringify(srcs))}${GAPS ? ' - GAP CHECK: magenta = land without polity' : ''}</text></svg>`;
  items.push({ svg, width: W, height: H, file: path.join(outDir, `world_${y}${tag}${GAPS ? '_gaps' : ''}.png`) });
}
await svgsToPngs(items);
console.log(`rendered ${items.length} PNGs to ${outDir}`);
