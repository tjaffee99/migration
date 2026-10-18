#!/usr/bin/env node
// GeoJSON (build_world_hist.py output) -> web/geo/world_hist.topo.json
//   node build_topo.mjs WORK_DIR OUT_TOPO [--interval=0.002] [--quantization=100000]
//
// One TopoJSON object `polities`. Topology is built separately for each source (src = hb, cshapes, ne and,
// only with build_world_hist.py --merge-across-sources, cshapes+hb): inside a source every polygon of every
// year goes into one mapshaper layer, so borders repeated across year-versions become shared arcs; no arc is
// shared between sources, so the GPL-3.0 (historical-basemaps) and CC BY-NC-SA 4.0 (CShapes) parts stay
// separable. Light Visvalingam (weighted) simplification in degrees (the data has longitudes > 180 east of
// the antimeridian, so mapshaper treats it as planar), then one common quantization for all arcs.
// Finally every polygon is checked with d3-geo for spherical winding; a ring set that d3 would read as
// "the whole globe minus this polygon" (area > 2π sr) is reversed.
import fs from 'node:fs';
import path from 'node:path';
import mapshaper from 'mapshaper';
import { feature } from 'topojson-client';
import { geoArea } from 'd3-geo';

const args = process.argv.slice(2);
const [work, outFile] = args.filter((a) => !a.startsWith('--'));
const opt = (k, d) => { const a = args.find((x) => x.startsWith(`--${k}=`)); return a ? a.slice(k.length + 3) : d; };
const interval = opt('interval', '0.002');
const Q = Number(opt('quantization', '100000'));
const raw = JSON.parse(fs.readFileSync(path.join(work, 'world_hist_raw.geojson'), 'utf8'));
const ORDER = ['id', 'name', 'sub', 'src', 'from', 'to', 'precision'];

// ---- per-source topology + simplification (unquantized)
const groups = {};
for (const f of raw.features) (groups[f.properties.src] ||= []).push(f);
const parts = [];
for (const [src, feats] of Object.entries(groups)) {
  const inFile = path.join(work, `_src_${src.replace('+', '_')}.geojson`);
  const outTmp = path.join(work, `_src_${src.replace('+', '_')}.topo.json`);
  fs.writeFileSync(inFile, JSON.stringify({ type: 'FeatureCollection', features: feats }));
  await mapshaper.runCommands(`-i "${inFile}" name=polities -simplify weighted interval=${interval} keep-shapes ` +
    `-o "${outTmp}" format=topojson id-field=id no-quantization precision=0.0000001`);
  const t = JSON.parse(fs.readFileSync(outTmp, 'utf8'));
  if (t.transform) {                          // decode delta-encoded quantized arcs to absolute coordinates
    const { scale: [sx, sy], translate: [tx, ty] } = t.transform;
    t.arcs = t.arcs.map((a) => { let x = 0, y = 0; return a.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty]; }); });
    delete t.transform;
  }
  parts.push({ src, topo: t });
  fs.unlinkSync(inFile); fs.unlinkSync(outTmp);
  console.error(`  ${src}: ${feats.length} polygons`);
}

// ---- merge arc tables with a common quantization
let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
for (const { topo } of parts) for (const arc of topo.arcs) for (const [x, y] of arc) {
  if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
}
const kx = (x1 - x0) / (Q - 1) || 1, ky = (y1 - y0) / (Q - 1) || 1;
const arcs = [];
const geometries = [];
for (const { topo } of parts) {
  const off = arcs.length;
  for (const arc of topo.arcs) {
    const q = [];
    let px = null, py = null;
    for (const [x, y] of arc) {
      const ix = Math.round((x - x0) / kx), iy = Math.round((y - y0) / ky);
      if (ix === px && iy === py) continue;
      q.push([ix, iy]); px = ix; py = iy;
    }
    if (q.length === 1) q.push(q[0].slice());
    const d = [q[0]];
    for (let i = 1; i < q.length; i++) d.push([q[i][0] - q[i - 1][0], q[i][1] - q[i - 1][1]]);
    arcs.push(d);
  }
  const shift = (i) => (i >= 0 ? i + off : ~(~i + off));
  for (const g of topo.objects.polities.geometries) {
    if (g.type === 'Polygon') g.arcs = g.arcs.map((r) => r.map(shift));
    else if (g.type === 'MultiPolygon') g.arcs = g.arcs.map((p) => p.map((r) => r.map(shift)));
    geometries.push(g);
  }
}
const topo = { type: 'Topology', transform: { scale: [kx, ky], translate: [x0, y0] }, arcs,
  objects: { polities: { type: 'GeometryCollection', geometries } } };

// ---- properties in a fixed order; spherical winding check
let flipped = 0, empty = 0;
for (const g of geometries) {
  const p = g.properties || {};
  g.properties = Object.fromEntries(ORDER.map((k) => [k, k === 'precision' ? Number(p[k]) : (p[k] ?? '')]));
  delete g.id;
  if (!g.type || !g.arcs) { empty++; continue; }
  const polys = g.type === 'Polygon' ? [g.arcs] : g.arcs;
  polys.forEach((rings, i) => {
    const f = feature(topo, { type: 'Polygon', arcs: rings });
    if (geoArea(f) > 2 * Math.PI) {
      const rev = rings.map((r) => r.slice().reverse().map((a) => ~a));
      if (g.type === 'Polygon') g.arcs = rev; else g.arcs[i] = rev;
      flipped++;
      console.error(`  reversed ring set of ${g.properties.id} part ${i} (d3 area ${geoArea(f).toFixed(4)} sr)`);
    }
  });
}
if (empty) throw new Error(`${empty} geometries lost their shape in simplification`);
geometries.sort((a, b) => (a.properties.from < b.properties.from ? -1 : a.properties.from > b.properties.from ? 1 : 0));
fs.writeFileSync(outFile, JSON.stringify(topo));
const npts = arcs.reduce((s, a) => s + a.length, 0);
console.error(`wrote ${outFile}: ${geometries.length} polities, ${arcs.length} arcs, ${npts} points, ` +
  `${(fs.statSync(outFile).size / 1e6).toFixed(2)} MB; rings reversed for d3: ${flipped}`);
