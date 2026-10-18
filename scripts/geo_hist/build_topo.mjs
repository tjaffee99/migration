#!/usr/bin/env node
// GeoJSON (build_world_hist.py output) -> web/geo/world_hist.topo.json
//   node build_topo.mjs WORK_DIR OUT_TOPO [--interval=0.002] [--quantization=100000]
// One TopoJSON object `polities`; every polygon of every source and year goes into one mapshaper layer, so
// borders shared between year-versions (and between sources) become shared arcs. Light Visvalingam (weighted)
// simplification in degrees (the data has longitudes > 180 east of the antimeridian, so mapshaper treats it as
// planar), then quantization. Finally each feature is checked with d3-geo for spherical winding: an exterior
// ring that d3 would read as "everything except this polygon" (area > 2π sr) is reversed in the topology.
import fs from 'node:fs';
import path from 'node:path';
import mapshaper from 'mapshaper';
import { feature } from 'topojson-client';
import { geoArea } from 'd3-geo';

const args = process.argv.slice(2);
const [work, outFile] = args.filter((a) => !a.startsWith('--'));
const opt = (k, d) => { const a = args.find((x) => x.startsWith(`--${k}=`)); return a ? a.slice(k.length + 3) : d; };
const interval = opt('interval', '0.002');
const quant = opt('quantization', '100000');
const raw = path.join(work, 'world_hist_raw.geojson');
const tmp = path.join(work, 'world_hist_ms.topo.json');

const cmd = `-i "${raw}" name=polities -simplify weighted interval=${interval} keep-shapes ` +
  `-o "${tmp}" format=topojson quantization=${quant} id-field=id`;
console.error('mapshaper', cmd);
await mapshaper.runCommands(cmd);

const topo = JSON.parse(fs.readFileSync(tmp, 'utf8'));
const obj = topo.objects.polities;
const ORDER = ['id', 'name', 'sub', 'src', 'from', 'to', 'precision'];
let flipped = 0, empty = 0;
for (const g of obj.geometries) {
  const p = g.properties || {};
  g.properties = Object.fromEntries(ORDER.map((k) => [k, k === 'precision' ? Number(p[k]) : (p[k] ?? '')]));
  delete g.id;
  if (!g.type || !g.arcs) { empty++; continue; }
  // spherical winding check, per polygon
  const polys = g.type === 'Polygon' ? [g.arcs] : g.arcs;
  polys.forEach((rings, i) => {
    const f = feature(topo, { type: 'Polygon', arcs: rings });
    if (geoArea(f) > 2 * Math.PI) {
      const rev = rings.map((r) => r.slice().reverse().map((a) => ~a));
      if (g.type === 'Polygon') g.arcs = rev; else g.arcs[i] = rev;
      flipped++;
    }
  });
}
if (empty) throw new Error(`${empty} geometries lost their shape in simplification`);
fs.writeFileSync(outFile, JSON.stringify(topo));
fs.unlinkSync(tmp);
const npts = topo.arcs.reduce((s, a) => s + a.length, 0);
console.error(`wrote ${outFile}: ${obj.geometries.length} polities, ${topo.arcs.length} arcs, ${npts} points, ` +
  `${(fs.statSync(outFile).size / 1e6).toFixed(2)} MB; rings reversed for d3: ${flipped}`);
