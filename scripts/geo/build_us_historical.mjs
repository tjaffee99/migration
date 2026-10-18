#!/usr/bin/env node
// Build web/geo/us_historical.topo.json + web/geo/us_historical_years.json
//
// Inputs (see download_raw.sh):
//   data/raw/newberry_ahcb/extracted/US_AtlasHCB_StateTerr_Gen01/...  (states & territories 1783-09-03 .. 2000-12-31)
//   data/raw/newberry_ahcb/extracted/US_AtlasHCB_Counties_Gen01/...   (historical counties, used for 1629 .. 1783-09-02)
//
// Pipeline
//   1. Colonial / Revolutionary era (before 1783-09-03): dissolve AHCB historical counties
//      (incl. AHCB "non-county areas") by colony at every date on which a colony's county set
//      changes, keep only versions whose outline actually changes. A few documented
//      back-fill rules extend colonies to their founding dates, and add New Netherland,
//      New Sweden and New Haven, which AHCB does not map.
//   2. 1783-09-03 onward: AHCB US_HistStateTerr polygons (end date 2000-12-31 -> 2024-12-31).
//   3. Everything is clipped to the present-day US outline (dissolved AHCB 2000 polygons).
//   4. "Context" polygons = (modern outline) minus (all jurisdictions active at each change date),
//      split by fixed acquisition regions (Louisiana Purchase, Florida, Texas, Mexican Cession,
//      ...) and labelled with the colonial power by date. The year index uses July-1 snapshots.
//   5. One mapshaper layer -> simplify (shared arcs) -> TopoJSON.
// Optional: GEO_DEBUG_DIR=<dir> dumps regions.json + unsimplified.json; GEO_SIMPLIFY / GEO_QUANT override settings.
import mapshaper from 'mapshaper';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { geoArea } from 'd3-geo';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const RAW = path.join(ROOT, 'data/raw/newberry_ahcb/extracted');
const ST_SHP = path.join(RAW, 'US_AtlasHCB_StateTerr_Gen01/US_HistStateTerr_Gen01_Shapefile/US_HistStateTerr_Gen01.shp');
const CO_SHP = path.join(RAW, 'US_AtlasHCB_Counties_Gen01/US_HistCounties_Gen01_Shapefile/US_HistCounties_Gen01.shp');
const OUT_DIR = path.join(ROOT, 'web/geo');
const SIMPLIFY = process.env.GEO_SIMPLIFY || '30%';           // mapshaper -simplify: % of removable vertices kept (Visvalingam, weighted)
const QUANT = process.env.GEO_QUANT || '100000';
const FIRST_YEAR = 1607, LAST_YEAR = 2024;
const AHCB_LAST = 20001231, OPEN_END = 20241231;
const STATE_TERR_START = 17830903;

const log = (...a) => console.log('[us_historical]', ...a);

// ---------------------------------------------------------------- date helpers (ints YYYYMMDD)
const toDate = (n) => new Date(Date.UTC(Math.floor(n / 10000), Math.floor(n / 100) % 100 - 1, n % 100));
const fromDate = (d) => d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
const addDays = (n, k) => { const d = toDate(n); d.setUTCDate(d.getUTCDate() + k); return fromDate(d); };
const iso = (n) => { const s = String(n); return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`; };
const july1 = (y) => y * 10000 + 701;

// ---------------------------------------------------------------- mapshaper helpers
async function msRun(cmd, inputs = {}) {
  return mapshaper.applyCommands(cmd, inputs);
}
async function msGeo(cmd, inputs = {}) {
  const out = await msRun(`${cmd} -o out.json format=geojson geojson-type=FeatureCollection`, inputs);
  return JSON.parse(out['out.json']);
}
const FC = (features) => ({ type: 'FeatureCollection', features });

// Robust overlays. mapshaper's -dissolve/-clip/-erase silently return wrong (empty) results when a
// layer contains overlapping copies of polygons, and two-dataset -clip/-erase failed on these inputs
// (many coincident boundaries). So: (a) every union is its own mapshaper run using -dissolve2
// (which handles overlaps), and (b) overlays use a single-layer planar mosaic (-mosaic) whose
// non-overlapping tiles are then re-assembled one output feature at a time.
async function dissolveOne(geoms) { // union of geometries -> geometry|null
  if (!geoms.length) return null;
  const res = await msGeo('-i in.json -dissolve2', { 'in.json': FC(geoms.map((g) => ({ type: 'Feature', properties: { k: 1 }, geometry: g }))) });
  return res.features.find((f) => f.geometry)?.geometry || null;
}
async function mosaicTiles(items) { // items: [{fid:int, geometry}] -> [{ids:int[], geometry}]
  const res = await msGeo('-i in.json -mosaic calc="ids=collect(fid)"',
    { 'in.json': FC(items.map((it) => ({ type: 'Feature', properties: { fid: it.fid }, geometry: it.geometry }))) });
  return res.features.filter((t) => t.geometry && Array.isArray(t.properties.ids)).map((t) => ({ ids: t.properties.ids, geometry: t.geometry }));
}
// For each geometry i: keep(tileIds) decides which of its tiles survive. Geometries that lose no tile
// are returned unchanged (exact original vertices); others are re-assembled from their kept tiles.
async function overlayEach(geoms, extra, keep) {
  const tiles = await mosaicTiles([...extra, ...geoms.map((g, i) => ({ fid: i, geometry: g }))]);
  const kept = new Map(), lost = new Set();
  for (const t of tiles) {
    const ok = keep(t.ids);
    for (const id of t.ids) if (id >= 0) { if (ok) { if (!kept.has(id)) kept.set(id, []); kept.get(id).push(t.geometry); } else lost.add(id); }
  }
  const out = [];
  for (let i = 0; i < geoms.length; i++) out.push(!lost.has(i) ? geoms[i] : await dissolveOne(kept.get(i) || []));
  return out;
}
const OUTLINE_FID = -1;
const clipToOutline = (geoms, outlineGeom) => overlayEach(geoms, [{ fid: OUTLINE_FID, geometry: outlineGeom }], (ids) => ids.includes(OUTLINE_FID));

// mapshaper's GeoJSON output uses RFC 7946 (counter-clockwise) exterior rings; d3-geo expects the
// opposite. d3safe() returns a re-wound copy for d3 measurements (never fed back to mapshaper).
function d3safe(f) {
  const fix = (rings) => (geoArea({ type: 'Polygon', coordinates: rings }) > 2 * Math.PI ? rings.map((r) => r.slice().reverse()) : rings);
  const g = f.geometry || f;
  const ng = g.type === 'Polygon' ? { type: 'Polygon', coordinates: fix(g.coordinates) } : { type: 'MultiPolygon', coordinates: g.coordinates.map(fix) };
  return { type: 'Feature', properties: f.properties || {}, geometry: ng };
}
const EARTH_R = 6371.0088;
const areaKm2 = (f) => geoArea(d3safe(f)) * EARTH_R * EARTH_R;

// drop polygon parts smaller than minKm2 (numerical slivers); returns null if nothing is left
const SLIVER_KM2 = 2;
function dropSlivers(g, minKm2) {
  if (!g) return null;
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
  const keep = polys.filter((rings) => {
    let a = geoArea({ type: 'Polygon', coordinates: rings });
    if (a > 2 * Math.PI) a = 4 * Math.PI - a;
    return a * EARTH_R * EARTH_R >= minKm2;
  });
  if (!keep.length) return null;
  return keep.length === 1 ? { type: 'Polygon', coordinates: keep[0] } : { type: 'MultiPolygon', coordinates: keep };
}

// canonical geometry key (ring start/rotation/order independent) to detect identical outlines
function geomKey(g) {
  if (!g) return '';
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
  const rings = [];
  for (const p of polys) for (const r of p) {
    const pts = r.slice(0, -1).map((c) => `${c[0].toFixed(7)},${c[1].toFixed(7)}`);
    if (!pts.length) continue;
    let k = 0; for (let i = 1; i < pts.length; i++) if (pts[i] < pts[k]) k = i;
    rings.push(pts.slice(k).concat(pts.slice(0, k)).join(';'));
  }
  return rings.sort().join('|');
}

// ---------------------------------------------------------------- colonial jurisdiction rules
const COLONY = {
  'Virginia Colony': { key: 'va_colony', name: 'Virginia', abbr: 'VA', fips: '51' },
  'Massachusetts Colony': { key: 'ma_colony', name: 'Massachusetts Bay', abbr: 'MA', fips: '25' },
  'Maryland Colony': { key: 'md_colony', name: 'Maryland', abbr: 'MD', fips: '24' },
  'Rhode Island Colony': { key: 'ri_colony', name: 'Rhode Island', abbr: 'RI', fips: '44' },
  'Connecticut Colony': { key: 'ct_colony', name: 'Connecticut', abbr: 'CT', fips: '09' },
  'North Carolina Colony': { key: 'nc_colony', name: 'North Carolina', abbr: 'NC', fips: '37' },
  'New York Colony': { key: 'ny_colony', name: 'New York', abbr: 'NY', fips: '36' },
  'Delaware Colony': { key: 'de_colony', name: 'Delaware', abbr: 'DE', fips: '10' },
  'New Jersey Colony': { key: 'nj_colony', name: 'New Jersey', abbr: 'NJ', fips: '34' },
  'New Hampshire Colony': { key: 'nh_colony', name: 'New Hampshire', abbr: 'NH', fips: '33' },
  'Pennsylvania Colony': { key: 'pa_colony', name: 'Pennsylvania', abbr: 'PA', fips: '42' },
  'South Carolina Colony': { key: 'sc_colony', name: 'South Carolina', abbr: 'SC', fips: '45' },
  'Georgia Colony': { key: 'ga_colony', name: 'Georgia', abbr: 'GA', fips: '13' },
};
const REV = { // AHCB county STATE_TERR values 1776-07-04 .. 1783-09-02
  Virginia: ['va', '51'], Massachusetts: ['ma', '25'], Maryland: ['md', '24'], 'Rhode Island': ['ri', '44'],
  Connecticut: ['ct', '09'], 'North Carolina': ['nc', '37'], 'New York': ['ny', '36'], Delaware: ['de', '10'],
  'New Jersey': ['nj', '34'], 'New Hampshire': ['nh', '33'], Pennsylvania: ['pa', '42'], 'South Carolina': ['sc', '45'],
  Georgia: ['ga', '13'],
};
const META = {};
for (const v of Object.values(COLONY)) META[v.key] = { ...v, type: 'colony' };
for (const [nm, [ab, fips]] of Object.entries(REV)) META[`${ab}_state1776`] = { key: `${ab}_state1776`, name: nm, abbr: ab.toUpperCase(), fips, type: 'state' };
Object.assign(META, {
  vt_republic1777: { key: 'vt_republic1777', name: 'Vermont Republic', abbr: 'VT Rep', fips: '50', type: 'other' },
  er_triangle1782: { key: 'er_triangle1782', name: 'Erie Triangle (unorganized federal territory)', abbr: 'Erie Tri', fips: '42', type: 'unorganized' },
  plymouth_colony: { key: 'plymouth_colony', name: 'Plymouth', abbr: 'PLY', fips: '25', type: 'colony' },
  me_province: { key: 'me_province', name: 'Province of Maine', abbr: 'ME', fips: '23', type: 'colony' },
  east_jersey: { key: 'east_jersey', name: 'East Jersey', abbr: 'EJ', fips: '34', type: 'colony' },
  west_jersey: { key: 'west_jersey', name: 'West Jersey', abbr: 'WJ', fips: '34', type: 'colony' },
  new_netherland: { key: 'new_netherland', name: 'New Netherland (Dutch)', abbr: 'NN', fips: '36', type: 'colony' },
  new_sweden: { key: 'new_sweden', name: 'New Sweden (Swedish)', abbr: 'NSw', fips: '10', type: 'colony' },
  new_haven_colony: { key: 'new_haven_colony', name: 'New Haven', abbr: 'NHav', fips: '09', type: 'colony' },
});
const EAST_JERSEY_IDS = new Set(['njs_ncaeast', 'njs_bergen', 'njs_essex', 'njs_middlesex', 'njs_monmouth', 'njs_somerset']);
const PLYMOUTH_COUNTY_IDS = new Set(['mas_plymouth', 'mas_barnstable', 'mas_bristol']);
const DUTCH_RECONQUEST = [16730809, 16741109]; // New Netherland briefly restored
const CAROLINA_SPLIT = 17120124;              // separate governor for North Carolina

function jurOf(p, D) {
  const st = p.STATE_TERR, id = p.ID;
  let key = null;
  if (COLONY[st]) key = COLONY[st].key;
  else if (REV[st]) key = `${REV[st][0]}_state1776`;
  else if (st === 'Vermont Republic') key = 'vt_republic1777';
  else if (st === 'Erie Triangle Unorganized Federal Territory') key = 'er_triangle1782';
  else return null;
  if (key === 'ma_colony') {
    if (id === 'mac_newplymouth') key = 'plymouth_colony';
    else if (PLYMOUTH_COUNTY_IDS.has(id) && D < 16911007) key = 'plymouth_colony';
    else if (id === 'mes_nca' && p.NAME === 'Maine') key = 'me_province';
  }
  if (key === 'nj_colony' && D < 17020415) key = EAST_JERSEY_IDS.has(id) ? 'east_jersey' : 'west_jersey';
  return key;
}
function renameForDate(key, D) {
  if (D >= DUTCH_RECONQUEST[0] && D <= DUTCH_RECONQUEST[1] && ['ny_colony', 'nj_colony', 'east_jersey', 'west_jersey', 'de_colony'].includes(key)) return 'new_netherland';
  return key;
}
function nameFor(key, D) {
  if (key === 'nc_colony' && D < CAROLINA_SPLIT) return 'Carolina (North)';
  if (key === 'sc_colony' && D < CAROLINA_SPLIT) return 'Carolina (South)';
  return META[key].name;
}

// Back-fill / approximation rules (documented in GEO_NOTES.md).
// tpl: function(D) -> list of {key, date, ids?, exclude?} record selections whose union approximates the colony.
const NY_TPL = { key: 'ny_colony', date: 16831101, exclude: ['nys_cornwall', 'nys_dukes'] };
const BACKFILL = [
  { key: 'va_colony', from: 16070514, to: 16341230, tpl: () => [{ key: 'va_colony', date: 16341231 }], note: 'Jamestown founded 1607-05-14; AHCB maps Virginia from its 8 shires of 1634 - this 1634 extent is back-filled to 1607 (approximation).' },
  { key: 'plymouth_colony', from: 16201221, to: 16300112, tpl: () => [{ key: 'plymouth_colony', date: 16300113 }], note: 'Plymouth settled 1620-12; AHCB maps it from the 1630 patent - shape back-filled (approximation).' },
  { key: 'md_colony', from: 16340325, to: 16380123, tpl: () => [{ key: 'md_colony', date: 16380124 }], note: 'St. Mary\'s City founded 1634-03-25; AHCB 1638 extent back-filled (approximation).' },
  { key: 'ri_colony', from: 16360601, to: 16440313, tpl: () => [{ key: 'ri_colony', date: 16440314 }], note: 'Providence founded 1636; AHCB maps Rhode Island from the 1644 patent - shape back-filled (approximation).' },
  { key: 'ct_colony', from: 16360601, to: 16620422, tpl: () => [{ key: 'ct_colony', date: 16650408 }], note: 'Connecticut settled 1636; AHCB maps it from the 1662 charter - its 1665 extent (after the Narragansett decision) is back-filled, minus the approximate New Haven Colony (approximation).' },
  { key: 'new_haven_colony', from: 16380424, to: 16650104, tpl: () => [{ key: 'ct_colony', date: 16660510, ids: ['cts_newhaven'] }], note: 'Not mapped by AHCB; approximated by the first New Haven County (1666), created from the former New Haven Colony towns.' },
  { key: 'new_sweden', from: 16380329, to: 16550914, tpl: () => [{ key: 'de_colony', date: 16730912, ids: ['des_newcastle', 'des_upland'] }], note: 'Not mapped by AHCB; approximated by the Dutch-created counties New Amstel and Upland of 1673 (Delaware valley).' },
  { key: 'new_netherland', from: 16240501, to: 16640907, tpl: (D) => [NY_TPL].concat(D >= 16550915 ? [{ key: 'de_colony', date: 16730912 }] : []), note: 'Not mapped by AHCB; approximated by the extent of New York\'s first counties (1683), plus the Delaware valley after the 1655 conquest of New Sweden.' },
  { key: 'ny_colony', from: 16640908, to: 16831031, tpl: () => [NY_TPL], note: 'AHCB maps no New York counties (except Cornwall in Maine) before 1683-11-01; the 1683 extent is back-filled to the 1664 English conquest (approximation).' },
  { key: 'nj_colony', from: 16640908, to: 16760630, tpl: () => [{ key: 'east_jersey', date: 16760701 }, { key: 'west_jersey', date: 16760701 }], note: 'New Jersey granted 1664; AHCB maps it from the 1676 East/West division - shape back-filled (approximation).' },
  { key: 'de_colony', from: 16640908, to: 16730911, tpl: () => [{ key: 'de_colony', date: 16730912 }], note: 'Delaware (under the Duke of York) 1664-1673; AHCB maps it from 1673 - shape back-filled (approximation).' },
  { key: 'sc_colony', from: 16700401, to: 16820509, tpl: () => [{ key: 'sc_colony', date: 16820510 }], note: 'Charles Town founded 1670; AHCB maps South Carolina from 1682 - shape back-filled (approximation).' },
  { key: 'ga_colony', from: 17330212, to: 17580316, tpl: () => [{ key: 'ga_colony', date: 17580317 }], note: 'Savannah founded 1733-02-12; AHCB maps Georgia from its 1758 parishes - shape back-filled (approximation).' },
];
const NEW_HAVEN_PERIOD = [16380424, 16650104];

// ---------------------------------------------------------------- context regions & labels
const GENERIC = 'Outside US/colonial jurisdiction';
// label timelines: [fromDate (inclusive), name, power]
const REGION_LABELS = {
  east: [[0, `${GENERIC} (Indigenous lands; contested British/French claims)`, ''],
    [17630210, 'British territory (outside colonial counties)', 'Great Britain'],
    [17760704, 'Disputed: British claim / state charter claims', 'Great Britain (disputed)'],
    [STATE_TERR_START, GENERIC, '']],
  florida: [[0, 'Spanish Florida', 'Spain'], [17630210, 'British Florida (East & West Florida)', 'Great Britain'], [17830903, 'Spanish Florida', 'Spain'], [18210717, GENERIC, '']],
  wfl: [[0, GENERIC, ''], [16990501, 'French Louisiana (Gulf coast)', 'France'], [17630210, 'British West Florida', 'Great Britain'], [17830903, 'Spanish West Florida', 'Spain'], [18130415, GENERIC, '']],
  louisiana: [[0, GENERIC, ''], [16820409, 'French Louisiana', 'France'], [17630210, 'Spanish Louisiana', 'Spain'], [18001001, 'Louisiana (retroceded to France 1800; Spanish-administered)', 'France'], [18031220, GENERIC, '']],
  redriver: [[0, GENERIC, ''], [16700502, "Rupert's Land (British, Hudson's Bay Company)", 'Great Britain'], [18181020, GENERIC, '']],
  texas: [[0, 'New Spain (Spanish claim)', 'Spain'], [18210927, 'Mexico', 'Mexico'], [18360302, GENERIC, '']],
  cession: [[0, 'New Spain (Spanish claim)', 'Spain'], [18210927, 'Mexico', 'Mexico'], [18480704, GENERIC, '']],
  gadsden: [[0, 'New Spain (Spanish claim)', 'Spain'], [18210927, 'Mexico', 'Mexico'], [18531230, GENERIC, '']],
  oregon: [[0, `${GENERIC} (Pacific Northwest)`, ''], [17901028, 'Pacific Northwest (contested British/Spanish/US claims)', ''], [18460615, GENERIC, '']],
  alaska: [[0, `${GENERIC} (Alaska Native lands)`, ''], [17840814, 'Russian America', 'Russia'], [18671018, GENERIC, '']],
  hawaii: [[0, 'Hawaiian Islands (independent chiefdoms)', 'Hawaii'], [17950501, 'Kingdom of Hawaii', 'Hawaii'], [18930117, 'Provisional Government of Hawaii', 'Hawaii'], [18940704, 'Republic of Hawaii', 'Hawaii'], [18980707, GENERIC, '']],
  other: [[0, GENERIC, '']],
};
function regionLabel(region, D) {
  let cur = REGION_LABELS[region][0];
  for (const e of REGION_LABELS[region]) if (D >= e[0]) cur = e;
  return { name: cur[1], power: cur[2] };
}

// ---------------------------------------------------------------- main
async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  log('reading AHCB shapefiles');
  const ST = await msGeo(`-i "${ST_SHP}"`);
  const CO = await msGeo(`-i "${CO_SHP}" -filter "START_N < ${STATE_TERR_START}"`);
  log(`state/territory polygons: ${ST.features.length}; pre-1783-09-03 county polygons: ${CO.features.length}`);

  const outline = await msGeo('-i st.json -filter "END_N==20001231" -dissolve2', { 'st.json': ST });
  outline.features[0].properties = { id: 'outline' };
  const outlineGeom = outline.features[0].geometry;
  const outlineKm2 = (await msGeo('-i in.json -each "A=this.area/1e6"', { 'in.json': outline })).features[0].properties.A;

  // ---- 1. colonial / revolutionary era
  const recs = CO.features.map((f, i) => ({ i, p: f.properties, g: f.geometry }));
  const activeAt = (D) => recs.filter((r) => r.p.START_N <= D && r.p.END_N >= D);
  const selectRecs = (sel) => activeAt(sel.date).filter((r) => jurOf(r.p, sel.date) === sel.key &&
    (!sel.ids || sel.ids.includes(r.p.ID)) && (!sel.exclude || !sel.exclude.includes(r.p.ID)));

  const bp = new Set([16070514]);
  for (const r of recs) { bp.add(r.p.START_N); bp.add(addDays(r.p.END_N, 1)); }
  for (const b of BACKFILL) { bp.add(b.from); bp.add(addDays(b.to, 1)); }
  [DUTCH_RECONQUEST[0], addDays(DUTCH_RECONQUEST[1], 1), CAROLINA_SPLIT, 16911007, 17020415, 16550915, NEW_HAVEN_PERIOD[0], addDays(NEW_HAVEN_PERIOD[1], 1)].forEach((d) => bp.add(d));
  const breaks = [...bp].filter((d) => d >= 16070514 && d < STATE_TERR_START).sort((a, b) => a - b);
  log(`colonial breakpoints: ${breaks.length}`);

  // state per jurisdiction at each breakpoint: signature (record indices + flags)
  const perKey = {}; // key -> [{D, sig, recIdx[], flags}]
  for (const D of breaks) {
    const groups = {};
    const add = (key, r, approxNote) => {
      const k = renameForDate(key, D);
      (groups[k] ||= { set: new Set(), notes: new Set() }).set.add(r.i);
      if (approxNote) groups[k].notes.add(approxNote);
    };
    for (const r of activeAt(D)) { const k = jurOf(r.p, D); if (k) add(k, r, null); }
    for (const b of BACKFILL) {
      if (D < b.from || D > b.to) continue;
      for (const sel of b.tpl(D)) for (const r of selectRecs(sel)) add(b.key, r, b.note);
    }
    for (const [k, g] of Object.entries(groups)) {
      const minusNH = k === 'ct_colony' && D >= NEW_HAVEN_PERIOD[0] && D <= NEW_HAVEN_PERIOD[1];
      const name = nameFor(k, D);
      const idx = [...g.set].sort((a, b) => a - b);
      const sig = `${idx.join(',')}|${minusNH ? 'xNH' : ''}`;
      (perKey[k] ||= []).push({ D, sig, idx, minusNH, name, notes: [...g.notes] });
    }
  }
  // collapse to runs of identical (sig,name); a jurisdiction absent at a breakpoint ends its run
  const nhTemplate = selectRecs({ key: 'ct_colony', date: 16660510, ids: ['cts_newhaven'] });
  const candidates = [];
  for (const [key, states] of Object.entries(perKey)) {
    const byD = new Map(states.map((s) => [s.D, s]));
    let run = null;
    for (let bi = 0; bi <= breaks.length; bi++) {
      const D = breaks[bi];
      const s = bi < breaks.length ? byD.get(D) : null;
      if (run && (!s || s.sig !== run.sig || s.name !== run.name || s.notes.join() !== run.notes.join())) { run.end = addDays(D ?? STATE_TERR_START, -1); candidates.push(run); run = null; }
      if (s && !run) run = { key, start: D, sig: s.sig, idx: s.idx, minusNH: s.minusNH, name: s.name, notes: s.notes };
    }
  }
  log(`colonial candidate versions (distinct county sets): ${candidates.length}`);

  // dissolve each candidate's records (one mapshaper run per jurisdiction)
  const byKey = {};
  candidates.forEach((c, ci) => (byKey[c.key] ||= []).push(ci));
  for (const [key, cis] of Object.entries(byKey)) {
    const raw = [];
    for (const ci of cis) raw.push(await dissolveOne(candidates[ci].idx.map((ri) => recs[ri].g)));
    const clipped = await clipToOutline(raw, outlineGeom);
    cis.forEach((ci, k) => {
      const c = candidates[ci];
      c.geometry = clipped[k];
      const a0 = raw[k] ? areaKm2(raw[k]) : 0, a1 = clipped[k] ? areaKm2(clipped[k]) : 0;
      if (a1 < a0 * 0.995) log(`  note: clipping ${key} (${c.start}) to the modern outline removed ${(a0 - a1).toFixed(0)} of ${a0.toFixed(0)} km2`);
    });
  }
  // New Haven subtraction for Connecticut
  const nhGeom = await dissolveOne(nhTemplate.map((r) => r.g));
  for (const c of candidates) if (!c.geometry) log(`  WARNING: no geometry for ${c.key} ${c.start}-${c.end} (${c.idx.length} records)`);
  const ctx = candidates.filter((c) => c.minusNH && c.geometry);
  if (ctx.length) {
    const NH_FID = -2;
    const res = await overlayEach(ctx.map((c) => c.geometry), [{ fid: NH_FID, geometry: nhGeom }], (ids) => !ids.includes(NH_FID));
    ctx.forEach((c, k) => {
      const g = res[k];
      log(`  Connecticut ${c.start}: minus New Haven ${areaKm2(c.geometry).toFixed(0)} -> ${g ? areaKm2(g).toFixed(0) : 0} km2`);
      c.geometry = g;
    });
  }
  // merge consecutive candidates of the same key whose outline and name are identical
  const colonial = [];
  for (const key of Object.keys(byKey)) {
    const list = byKey[key].map((ci) => candidates[ci]).sort((a, b) => a.start - b.start);
    let cur = null;
    for (const c of list) {
      c.gkey = geomKey(c.geometry);
      if (cur && cur.gkey === c.gkey && cur.name === c.name && addDays(cur.end, 1) === c.start && cur.notes.join() === c.notes.join()) { cur.end = c.end; continue; }
      if (cur) colonial.push(cur);
      cur = { ...c };
    }
    if (cur) colonial.push(cur);
  }
  const colonialFeatures = colonial.filter((c) => c.geometry).map((c) => {
    const m = META[c.key];
    if (c.minusNH && !c.notes.length) c.notes = ['AHCB 1662 charter area minus the approximate New Haven Colony, which joined Connecticut on 1665-01-05 (approximation).'];
    const approx = c.notes.length > 0;
    return {
      type: 'Feature', geometry: c.geometry,
      properties: {
        id: `${c.key}_${c.start}`, name: c.name, type: m.type, start: iso(c.start), end: iso(c.end), fips: m.fips, abbr: m.abbr,
        src: approx ? 'approx' : 'ahcb_counties', note: approx ? c.notes.join(' ') : 'Extent of the colony\'s AHCB counties / non-county areas (organized area), not its full charter claim.',
      },
    };
  });
  log(`colonial/revolutionary versions after outline de-duplication: ${colonialFeatures.length}`);

  // ---- 2. AHCB states & territories 1783+
  const TYPE = { State: 'state', Territory: 'territory', 'Unorganized Territory': 'unorganized', Other: 'other', 'District of Columbia': 'district' };
  const FIPS = {
    al: '01', ak: '02', az: '04', ar: '05', ca: '06', co: '08', ct: '09', de: '10', dc: '11', fl: '12', ga: '13', hi: '15', id: '16', il: '17', in: '18', ia: '19',
    ks: '20', ky: '21', la: '22', me: '23', md: '24', ma: '25', mi: '26', mn: '27', ms: '28', mo: '29', mt: '30', ne: '31', nv: '32', nh: '33', nj: '34', nm: '35',
    ny: '36', nc: '37', nd: '38', oh: '39', ok: '40', or: '41', pa: '42', ri: '44', sc: '45', sd: '46', tn: '47', tx: '48', ut: '49', vt: '50', va: '51', wa: '53',
    wv: '54', wi: '55', wy: '56',
  };
  const FIPS_SPECIAL = { // ancestor -> main successor (blank = no single successor)
    ak_dept: '02', ak_district: '02', hi_annexation: '15', it_indianterr: '40', sw_terr: '47', ol_terr: '22', fl_uft: '12', tx_republic: '48', vt_republic: '50',
    ds_deseret: '49', er_triangleuft: '42', or_uft: '', or_country: '', dk_terr: '', la_purchase: '', la_district: '', la_terr: '', nw_terr: '', mx_cession: '',
    gd_purchase: '', uf_terr: '', ub_area: '', wi_terrdefacto: '',
  };
  const stClipped = { features: [] };
  { const byId = {}; for (const f of ST.features) (byId[f.properties.ID] ||= []).push(f);
    for (const fs_ of Object.values(byId)) {
      const clipped = await clipToOutline(fs_.map((f) => f.geometry), outlineGeom);
      fs_.forEach((f, k) => {
        const a0 = areaKm2(f), a1 = clipped[k] ? areaKm2(clipped[k]) : 0;
        if (a1 < a0 * 0.995) log(`  note: clipping ${f.properties.ID}_v${f.properties.VERSION} to the modern outline removed ${(a0 - a1).toFixed(0)} of ${a0.toFixed(0)} km2`);
        stClipped.features.push({ type: 'Feature', properties: f.properties, geometry: clipped[k] });
      });
    } }
  const stFeatures = stClipped.features.filter((f) => f.geometry).map((f) => {
    const p = f.properties;
    const id = p.ID;
    let fips = id in FIPS_SPECIAL ? FIPS_SPECIAL[id] : (FIPS[id.slice(0, 2)] ?? '');
    let type = TYPE[p.TERR_TYPE] || 'other';
    if (id === 'ak_district' || id === 'la_district') type = 'district';
    return {
      type: 'Feature', geometry: f.geometry,
      properties: {
        id: `${id}_v${p.VERSION}`, name: p.NAME === 'Mississippi Terr.' ? 'Mississippi Territory' : p.FULL_NAME || p.NAME, type,
        start: iso(p.START_N), end: iso(p.END_N === AHCB_LAST ? OPEN_END : p.END_N), fips, abbr: p.ABBR_NAME,
        src: 'ahcb_stateterr', note: p.CHANGE,
      },
    };
  });
  log(`state/territory versions kept: ${stFeatures.length}`);
  const jur = [...colonialFeatures, ...stFeatures];

  // ---- 3. context regions (static partition of the modern outline)
  // mapshaper -mosaic builds a planar partition of all inputs; each tile takes the region with the
  // lowest priority number covering it. (Sequential -erase calls proved unreliable on these inputs.)
  const stById = (id) => ST.features.filter((f) => f.properties.ID === id);
  const e1783 = ST.features.filter((f) => f.properties.START_N <= STATE_TERR_START && f.properties.END_N >= STATE_TERR_START);
  const regionDefs = [ // [region, source polygons]; order = priority
    ['hawaii', stById('hi_state')], ['alaska', stById('ak_state')], ['florida', stById('fl_uft')], ['texas', stById('tx_republic')],
    ['gadsden', stById('gd_purchase')], ['cession', stById('mx_cession')], ['redriver', stById('ub_area')], ['louisiana', stById('la_purchase')],
    ['oregon', stById('or_country')], ['east', e1783],
    ['wfl', stById('ol_terr')], // Orleans Territory 1804 incl. the US-claimed West Florida strip; only its leftover (the strip) survives
  ];
  const REGION_NAMES = regionDefs.map((r) => r[0]).concat(['other']);
  const OUTSIDE_PRIO = REGION_NAMES.length - 1;
  const mosaicIn = [{ type: 'Feature', properties: { prio: OUTSIDE_PRIO }, geometry: outline.features[0].geometry }];
  regionDefs.forEach(([, feats], prio) => feats.forEach((f) => mosaicIn.push({ type: 'Feature', properties: { prio }, geometry: f.geometry })));
  const regionsFC = await msGeo(`-i in.json -mosaic calc="prio=min(prio), cover=max(prio)" -filter "cover==${OUTSIDE_PRIO}" -dissolve prio`, { 'in.json': FC(mosaicIn) });
  for (const f of regionsFC.features) { f.properties = { region: REGION_NAMES[f.properties.prio], reg: f.properties.prio }; }
  for (const f of regionsFC.features) log(`  region ${f.properties.region.padEnd(10)} ${(geoArea(d3safe(f)) * 6371 * 6371 / 1e3).toFixed(0)}k km2`);
  if (process.env.GEO_DEBUG_DIR) fs.writeFileSync(path.join(process.env.GEO_DEBUG_DIR, 'regions.json'), JSON.stringify(regionsFC));

  // ---- 4. context polygons, computed at every date on which the set of active jurisdictions
  //         (or a region label) changes; consecutive intervals with identical pieces are merged.
  const isoN = (s) => +s.replace(/-/g, '');
  const changeSet = new Set([16070514]);
  for (const f of jur) { changeSet.add(isoN(f.properties.start)); changeSet.add(addDays(isoN(f.properties.end), 1)); }
  for (const tl of Object.values(REGION_LABELS)) for (const e of tl) if (e[0] > 0) changeSet.add(e[0]);
  const changeDates = [...changeSet].filter((d) => d >= 16070514 && d <= OPEN_END).sort((a, b) => a - b);
  const activeIds = (D) => jur.filter((f) => isoN(f.properties.start) <= D && isoN(f.properties.end) >= D).map((f) => f.properties.id);
  const jurById = new Map(jur.map((f) => [f.properties.id, f]));
  const piecesCache = new Map(); // active-set signature -> pieces
  const intervals = [];
  for (let k = 0; k < changeDates.length; k++) {
    const D = changeDates[k];
    const end = k + 1 < changeDates.length ? addDays(changeDates[k + 1], -1) : OPEN_END;
    const ids = activeIds(D);
    const sig = ids.slice().sort().join(',');
    if (!piecesCache.has(sig)) {
      // planar mosaic of region tiles + active jurisdictions; keep tiles not covered by any jurisdiction
      const mos = regionsFC.features.map((f) => ({ type: 'Feature', properties: { reg: f.properties.reg, act: 0 }, geometry: f.geometry }))
        .concat(ids.map((id) => ({ type: 'Feature', properties: { reg: -1, act: 1 }, geometry: jurById.get(id).geometry })));
      const tiles = await msGeo('-i in.json -mosaic calc="reg=max(reg), act=max(act)" -filter "reg>=0" -each "A=this.area/1e6"', { 'in.json': FC(mos) });
      const tot = tiles.features.reduce((a, t) => a + t.properties.A, 0);
      if (Math.abs(tot - outlineKm2) > outlineKm2 * 0.001) log(`  WARNING: mosaic at ${D} covers ${tot.toFixed(0)} km2, outline is ${outlineKm2.toFixed(0)}`);
      const free = tiles.features.filter((t) => t.properties.act === 0);
      const res = free.length ? await msGeo('-i in.json -dissolve reg', { 'in.json': FC(free) }) : FC([]);
      piecesCache.set(sig, res.features.map((f) => ({ region: REGION_NAMES[f.properties.reg], geometry: dropSlivers(f.geometry, SLIVER_KM2) }))
        .filter((f) => f.geometry).map((f) => ({ ...f, gkey: geomKey(f.geometry) })));
    }
    intervals.push({ start: D, end, ids, pieces: piecesCache.get(sig) });
  }
  log(`context: ${changeDates.length} change dates, ${piecesCache.size} distinct active sets`);
  const ctxRuns = []; // {region, gkey, geometry, name, power, start, end}
  const open = new Map(); // region|gkey|name -> latest run
  for (const iv of intervals) {
    iv.ctxRuns = [];
    for (const pc of iv.pieces) {
      const lab = regionLabel(pc.region, iv.start);
      const k = `${pc.region}|${pc.gkey}|${lab.name}`;
      let run = open.get(k);
      if (run && addDays(run.end, 1) === iv.start) run.end = iv.end;
      else { run = { region: pc.region, gkey: pc.gkey, geometry: pc.geometry, name: lab.name, power: lab.power, start: iv.start, end: iv.end }; ctxRuns.push(run); open.set(k, run); }
      iv.ctxRuns.push(run);
    }
  }
  const usedIds = new Set();
  for (const r of ctxRuns) {
    const base = `ctx_${r.region}_${r.start}`;
    let id = base; let n = 2; while (usedIds.has(id)) id = `${base}_${n++}`; usedIds.add(id); r.id = id;
  }
  const ctxFeatures = ctxRuns.map((r) => ({
    type: 'Feature', geometry: r.geometry,
    properties: { id: r.id, name: r.name, type: 'other', start: iso(r.start), end: iso(r.end), fips: '', abbr: '', src: 'context', power: r.power, context: true,
      note: 'Part of the present-day US not covered by any jurisdiction drawn for this period; label = colonial power by date for this acquisition region.' },
  }));
  log(`context features: ${ctxFeatures.length}`);
  // year index (July 1 snapshots): jurisdictions + context ids
  const yearIndex = {};
  for (let y = FIRST_YEAR; y <= LAST_YEAR; y++) {
    const D = july1(y);
    const iv = intervals.find((v) => v.start <= D && v.end >= D);
    yearIndex[y] = iv ? [...iv.ids, ...iv.ctxRuns.map((r) => r.id)] : [];
  }

  // ---- 5. assemble, simplify, export
  const all = [...jur, ...ctxFeatures];
  if (process.env.GEO_DEBUG_DIR) fs.writeFileSync(path.join(process.env.GEO_DEBUG_DIR, 'unsimplified.json'), JSON.stringify(FC(all)));
  const props = new Map(all.map((f) => [f.properties.id, f.properties]));
  const geoOnly = FC(all.map((f) => ({ type: 'Feature', properties: { id: f.properties.id }, geometry: f.geometry })));
  const out = await msRun(`-i all.json -rename-layers jurisdictions -simplify percentage=${SIMPLIFY} keep-shapes -o out.topo.json format=topojson quantization=${QUANT}`, { 'all.json': geoOnly });
  const topo = JSON.parse(out['out.topo.json']);
  for (const g of topo.objects.jurisdictions.geometries) {
    const p = props.get(g.properties.id);
    g.properties = { id: p.id, name: p.name, type: p.type, start: p.start, end: p.end, fips: p.fips, abbr: p.abbr, src: p.src, ...(p.power !== undefined ? { power: p.power, context: true } : {}), note: p.note };
  }
  topo.objects.jurisdictions.geometries.sort((a, b) => (a.properties.start < b.properties.start ? -1 : a.properties.start > b.properties.start ? 1 : a.properties.id < b.properties.id ? -1 : 1));
  const topoPath = path.join(OUT_DIR, 'us_historical.topo.json');
  fs.writeFileSync(topoPath, JSON.stringify(topo));
  const idx = {
    description: 'For each year, ids of us_historical.topo.json geometries (object "jurisdictions") active on July 1 of that year. Ids starting with "ctx_" are context polygons (areas not yet in a US/colonial jurisdiction).',
    snapshot: 'July 1', first_year: FIRST_YEAR, last_year: LAST_YEAR, years: yearIndex,
  };
  fs.writeFileSync(path.join(OUT_DIR, 'us_historical_years.json'), JSON.stringify(idx));
  log(`wrote ${topoPath} (${(fs.statSync(topoPath).size / 1024).toFixed(0)} KB), ${topo.objects.jurisdictions.geometries.length} geometries, ${topo.arcs.length} arcs`);
}

main().catch((e) => { console.error(e); process.exit(1); });
