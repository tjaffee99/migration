#!/usr/bin/env node
// Debug renderer: node render_geojson.mjs IN.geojson OUT.png [--title=..] [--zoom=lon0,lat0,lon1,lat1]
//   [--label] [--fix-winding] [--filter=prop:value]
// Draws every feature with the page projection (Equal Earth, rotate [90,0], 1200 px) or a zoomed Equal Earth.
import fs from 'node:fs';
import { geoArea, geoEqualEarth } from 'd3-geo';
import { worldSvg, svgsToPngs } from './lib_render.mjs';

const args = process.argv.slice(2);
const [inp, out] = args.filter((a) => !a.startsWith('--'));
const opt = (k) => (args.find((a) => a.startsWith(`--${k}=`)) || '').slice(k.length + 3) || null;
const gj = JSON.parse(fs.readFileSync(inp, 'utf8'));
let feats = gj.type === 'FeatureCollection' ? gj.features : [gj];
if (opt('filter')) { const [k, v] = opt('filter').split(':'); feats = feats.filter((f) => String(f.properties?.[k]) === v); }
if (args.includes('--fix-winding')) {
  for (const f of feats) {
    const g = f.geometry; if (!g) continue;
    const fixP = (rings) => (geoArea({ type: 'Polygon', coordinates: rings }) > 2 * Math.PI ? rings.map((r) => r.slice().reverse()) : rings);
    if (g.type === 'Polygon') g.coordinates = fixP(g.coordinates);
    if (g.type === 'MultiPolygon') g.coordinates = g.coordinates.map(fixP);
  }
}
let projection;
const W = 1200;
if (opt('zoom')) {
  const [x0, y0, x1, y1] = opt('zoom').split(',').map(Number);
  projection = geoEqualEarth().rotate([-(x0 + x1) / 2, 0]).fitExtent([[5, 30], [W - 5, 840]],
    { type: 'MultiPoint', coordinates: [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [(x0 + x1) / 2, y1], [(x0 + x1) / 2, y0]] });
}
const label = args.includes('--label') ? (f, path) => (path.area(f) > 60 ? (f.properties?.name || f.properties?.NAME || '') : '') : null;
let r = worldSvg(feats, { width: W, projection, title: opt('title') || inp, label, strokeWidth: 0.5 });
if (projection) r = { ...r, height: 860 };
await svgsToPngs([{ ...r, file: out }]);
console.log('wrote', out, feats.length, 'features');
