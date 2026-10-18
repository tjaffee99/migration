#!/usr/bin/env node
// Build web/geo/us_states_modern.topo.json from us-atlas@3.0.1 states-10m.json
// (US Census Bureau cartographic boundary files 2017, 1:10m, via the us-atlas npm package).
// Objects: "states" (id = 2-digit state FIPS; properties fips, name, abbr, type) and "nation".
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const SRC = path.join(ROOT, 'data/raw/us_atlas/states-10m.json');
const OUT = path.join(ROOT, 'web/geo/us_states_modern.topo.json');

const ABBR = {
  '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID',
  '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO',
  '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA',
  '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI', '56': 'WY',
  '60': 'AS', '66': 'GU', '69': 'MP', '72': 'PR', '78': 'VI',
};
const topo = JSON.parse(fs.readFileSync(SRC, 'utf8'));
for (const g of topo.objects.states.geometries) {
  const fips = String(g.id).padStart(2, '0');
  g.id = fips;
  const type = fips === '11' ? 'district' : +fips >= 60 ? 'territory' : 'state';
  g.properties = { fips, name: g.properties.name, abbr: ABBR[fips] || '', type };
}
topo.objects.states.geometries.sort((a, b) => (a.id < b.id ? -1 : 1));
for (const g of topo.objects.nation.geometries) g.properties = { name: 'United States' };
fs.writeFileSync(OUT, JSON.stringify(topo));
const n = topo.objects.states.geometries;
console.log(`[us_states_modern] wrote ${OUT} (${(fs.statSync(OUT).size / 1024).toFixed(0)} KB): ${n.filter((g) => g.properties.type === 'state').length} states, ` +
  `${n.filter((g) => g.properties.type === 'district').length} district, ${n.filter((g) => g.properties.type === 'territory').length} territories`);
