#!/usr/bin/env python3
"""Build the historical world-borders layer (1607-2026) as GeoJSON + the per-year id lists.

    python3 -I build_world_hist.py --hb-dir ../../../aourednik/historical-basemaps/geojson \
        --cshapes-dir ../../data/raw/cshapes --ne-topo ../../web/geo/world_50m.topo.json \
        --work ../../data/raw/cshapes/_build --years-out ../../web/geo/world_hist_years.json

Output: <work>/world_hist_raw.geojson (unsimplified; build_topo.mjs simplifies it into web/geo/world_hist.topo.json)
and the years file. Rules (see web/geo/WORLD_HIST_NOTES.md):
  1607-1815  historical-basemaps (HB): latest snapshot on or before the year.
  1816-1885  Europe: CShapes-Europe (yearly); rest of the world: HB latest snapshot on or before the year, except
             Latin America/Caribbean 1822-1877, which uses the HB 1878 snapshot (independence wave of 1810-1825).
  1886-2026  CShapes 2.0 (GW), polygons valid on July 1 (2020-2026 = 2019-12-31 state), plus Natural Earth fills
             for territories CShapes does not map.
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import shapely  # noqa: E402
from shapely.geometry import shape, box, Polygon, LineString  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

from geo_util import (clean, polys, km2, compactness, stitch_antimeridian, unwrap, topo_decode,  # noqa: E402
                      to_feature, dump_fc)
import names as N  # noqa: E402

SNAPS = [1600, 1650, 1700, 1715, 1783, 1800, 1815, 1878, 1880]
FIRST, LAST_HB, LAST = 1607, 1885, 2026
CS_LAST = '2019-12-31'
STILL = '2026-12-31'          # "still valid at the end of the covered period"
GRID = 1e-6                   # coordinate grid (degrees) applied to all inputs so shared edges match exactly
LATAM_FROM, LATAM_TO = 1822, 1877

log = lambda *a: print(*a, file=sys.stderr, flush=True)


def snap(g):
    return clean(shapely.set_precision(g, GRID)) if g is not None else None


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')[:40] or 'x'


def latest_snap(y):
    return max(s for s in SNAPS if s <= y)


# ------------------------------------------------------------------------------------------------ masks

def us_mexico_border(ne):
    """US-Mexico land border (Natural Earth 1:50m) as a list of (lon, lat) from the Pacific to the Gulf."""
    geo = {p['name']: g for p, g in ne}
    line = shapely.line_merge(geo['United States'].boundary.intersection(geo['Mexico'].boundary))
    if line.geom_type == 'MultiLineString':
        line = max(line.geoms, key=lambda l: l.length)
    cs = list(line.coords)
    return cs if cs[0][0] < cs[-1][0] else cs[::-1]


def latam_mask(border):
    """Polygon = Latin America + Caribbean + tropical Pacific east of 180° (south of the US-Mexico border,
    passing between Florida/Keys and Cuba/Bahamas). In-frame copy for stitched coordinates > 180 included."""
    w_end, e_end = border[0], border[-1]
    na = Polygon([(-181, 90), (-181, w_end[1]), (w_end[0] - 0.4, w_end[1])] + [tuple(p) for p in border] +
                 [(e_end[0] + 0.3, e_end[1] - 0.05), (-85.5, 24.8), (-83.2, 24.35), (-82.0, 24.25), (-80.2, 24.4),
                  (-79.75, 25.2), (-79.75, 27.5), (-25, 40), (-25, 90)])
    L = box(-181, -90, -25, 90).difference(na)
    extra = shapely.transform(L.intersection(box(-181, -90, -165, 90)), lambda c: c + [360.0, 0.0])
    return clean(L.union(extra))


FLORIDA_1815 = Polygon([(-87.45, 31.0), (-85.0, 31.0), (-84.86, 30.70), (-82.2, 30.57), (-81.45, 30.71),
                        (-79.0, 30.71), (-79.0, 24.0), (-87.45, 24.0)])


# ------------------------------------------------------------------------------------------------ HB

class Polity:
    __slots__ = ('S', 'name', 'sub', 'geom', 'prec')

    def __init__(self, S, name, sub, geom, prec):
        self.S, self.name, self.sub, self.geom, self.prec = S, name, sub, geom, prec

    @property
    def key(self):
        return (self.name, self.sub)


def load_hb(hb_dir, S):
    fc = json.load(open(os.path.join(hb_dir, f'world_{S}.geojson')))
    named = collections.defaultdict(list)
    prec = {}
    unnamed = []
    for f in fc['features']:
        p = f['properties'] or {}
        g = unwrap(clean(shape(f['geometry'])))
        bp = p.get('BORDERPRECISION') or 1
        bp = 1 if bp < 1 else int(bp)
        for part in polys(g):
            if part.bounds[3] < -55:                               # Antarctica
                continue
            rp = part.representative_point()
            name, sub = N.hb_props(S, p.get('NAME'), p.get('SUBJECTO'), rp.x, rp.y)
            if name == '':
                continue
            if name is None:
                unnamed.append(part)
                continue
            named[(name, sub)].append(part)
            prec[(name, sub)] = min(prec.get((name, sub), 3), bp)
    # unnamed parts: a few hand fixes, then small islands join the nearest named polity within 1.5°
    keys = list(named)
    allparts, owner = [], []
    for k in keys:
        for q in named[k]:
            allparts.append(q); owner.append(k)
    tree = STRtree(allparts)
    dropped = 0
    for q in unnamed:
        c = q.representative_point()
        if S >= 1815 and 143.5 < c.x < 149 and -44 < c.y < -39.5:
            k = ("Van Diemen's Land" if S == 1815 else 'Tasmania', N.brit(S))
            named[k].append(q); prec.setdefault(k, 3); continue
        if -8 < c.x < -6 and 61 < c.y < 62.6:                        # Faroe Islands
            k = ('Denmark-Norway' if S <= 1800 else 'Denmark', '')
            named[k].append(q); prec.setdefault(k, 3); continue
        if km2(q) > 40000:
            dropped += 1; continue
        i = tree.nearest(q)
        if q.distance(allparts[i]) <= 1.5:
            named[owner[i]].append(q)
        else:
            dropped += 1
    pol = []
    for k, parts in named.items():
        g = stitch_antimeridian(snap(shapely.union_all(parts)))
        if g is not None:
            pol.append(Polity(S, k[0], k[1], g, prec.get(k, 3)))
    # 1815: Spanish Florida is drawn as part of the United States in HB 1815 (Spanish until 1821)
    if S == 1815:
        us = next(p for p in pol if p.name == 'United States')
        fl = clean(us.geom.intersection(FLORIDA_1815))
        us.geom = clean(us.geom.difference(FLORIDA_1815))
        pol.append(Polity(S, 'Spanish Florida', 'Spain', snap(fl), us.prec))
    # overlaps: smaller polities win (HB draws vassals/enclaves on top of larger polygons)
    pol.sort(key=lambda p: p.geom.area)
    orig = [p.geom for p in pol]
    tree = STRtree(orig)
    for i, p in enumerate(pol):
        smaller = [j for j in tree.query(p.geom) if j < i and orig[j].intersects(p.geom)]
        if smaller:
            p.geom = clean(p.geom.difference(shapely.union_all([orig[j] for j in smaller])))
    pol = [p for p in pol if p.geom is not None and km2(p.geom) > 0.5]
    log(f'  HB {S}: {len(pol)} polities, {len(unnamed)} unnamed parts ({dropped} dropped)')
    return {p.key: p for p in pol}


# ------------------------------------------------------------------------------------------------ CShapes-Europe

class CSERow:
    __slots__ = ('uid', 'rid', 'raw', 'holder', 'y0', 'y1', 'geom', 'losers_to')


def load_cse(path):
    rows = []
    for f in json.load(open(path))['features']:
        p = f['properties']
        if p['From'] > LAST_HB or p['To'] < 1816:
            continue
        r = CSERow()
        r.rid, r.raw, r.holder = p['Id'], p['Name'], p['Holder']
        r.y0, r.y1 = max(p['From'], 1816), min(p['To'], LAST_HB)
        r.uid = f"{r.rid}_{p['From']}"
        r.geom = stitch_antimeridian(snap(shape(f['geometry'])))
        rows.append(r)
    # overlapping rows (data errors in CShapes-Europe): remember which row keeps the overlap
    tree = STRtree([r.geom for r in rows])
    for i, r in enumerate(rows):
        r_beats = []
        for j in tree.query(r.geom):
            o = rows[j]
            if o is r or o.y0 > r.y1 or o.y1 < r.y0 or not o.geom.intersects(r.geom):
                continue
            inter = clean(o.geom.intersection(r.geom))
            if inter is None or km2(inter) < 0.5:
                continue
            w = CSE_WINNER.get(frozenset((o.raw, r.raw)))
            o_wins = (w == o.raw) if w else (o.geom.area < r.geom.area)
            if o_wins:
                r_beats.append(o)
        r.losers_to = r_beats
    log(f'  CShapes-Europe: {len(rows)} rows used for 1816-1885; '
        f'{sum(1 for r in rows if r.losers_to)} rows overlap a neighbour (overlap given to the winner)')
    return rows


# Which row keeps an overlap between two CShapes-Europe rows (otherwise the smaller polygon wins):
# southern Bessarabia was Russian until the Treaty of Paris (1856); rump Saxony stayed Saxon in 1815;
# Savoy and Nice were French from 1860; the British occupation of Balaklava (1855-56) was wartime only.
CSE_WINNER = {frozenset(('Russia', 'Ottoman Empire')): 'Russia', frozenset(('Saxony', 'Germany')): 'Saxony',
              frozenset(('France', 'Piedmont')): 'France', frozenset(('Russia', 'United Kingdom')): 'Russia'}


CSE_HB_ALIAS = {
    'Tunisia': ['Tunis'], 'Netherlands': ['Netherlands', 'United Kingdom of the Netherlands'],
    'United Kingdom of the Netherlands': ['United Kingdom of the Netherlands'],
    'North German Confederation': ['Prussia', 'German Empire'], 'German Empire': ['German Empire', 'Prussia'],
    'Austria-Hungary': ['Austria-Hungary', 'Austrian Empire'], 'Italy': ['Italy', 'Kingdom of Sardinia'],
}


# ------------------------------------------------------------------------------------------------ build

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hb-dir', required=True)
    ap.add_argument('--cshapes-dir', required=True)
    ap.add_argument('--ne-topo', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--years-out', required=True)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)

    ne = [(p, unwrap(clean(g))) for p, g in topo_decode(json.load(open(a.ne_topo)), 'countries')]
    border = us_mexico_border(ne)
    L = latam_mask(border)
    log(f'US-Mexico border: {len(border)} pts {border[0]} -> {border[-1]}')

    log('loading historical-basemaps')
    hb = {S: load_hb(a.hb_dir, S) for S in SNAPS}
    cse = load_cse(os.path.join(a.cshapes_dir, 'CShapes-Europe.geojson'))
    cp_ever_names = set()
    for r in cse:
        for y in range(r.y0, r.y1 + 1):
            n = N.cse_props(r.rid, r.raw, r.holder, y)[0]
            cp_ever_names.update(CSE_HB_ALIAS.get(n, [n]))

    comps = {}                      # key -> dict(name, sub, src, prec, geom)
    year_keys = {}                  # year -> [keys]

    alias, by_sig = {}, collections.defaultdict(list)

    def put(key, name, sub, src, prec, geom_fn):
        """Register a component; identical name/sub/geometry from another snapshot or year reuses the earlier
        key, so a polity that HB redraws unchanged from snapshot to snapshot becomes one feature."""
        if key in alias:
            return alias[key]
        if key not in comps:
            g = geom_fn()
            if g is None:
                comps[key] = None
                return None
            sig = (name, sub, src, prec)
            for k2 in by_sig[sig]:
                g2 = comps[k2]['geom']
                if abs(g2.area - g.area) < 1e-9 and g2.equals(g):
                    alias[key] = k2
                    return k2
            comps[key] = dict(name=name, sub=sub, src=src, prec=prec, geom=g)
            by_sig[sig].append(key)
        return key if comps[key] is not None else None

    # ---- caches for the Europe footprint and HB remainders
    fcache, fdistinct = {}, []

    def footprint(active):
        """Europe footprint for a set of CShapes-Europe rows; identical outlines share one id."""
        k = frozenset(r.uid for r in active)
        if k not in fcache:
            F = clean(shapely.union_all([r.geom for r in active]))
            for fid, G in fdistinct:
                if abs(G.area - F.area) < 1e-9 and G.equals(F):
                    fcache[k] = (fid, G); break
            else:
                shapely.prepare(F)
                fid = f'F{len(fdistinct)}'
                fdistinct.append((fid, F))
                fcache[k] = (fid, F)
        return fcache[k]

    rcache, fixcache = {}, {}

    def remainder(p, fkey, F, Lclip, cp_ever):
        """Parts of HB polity p outside the CShapes-Europe footprint (and outside L when Lclip), minus slivers.
        Returns (geom or None, effective footprint id or None when the footprint does not touch p)."""
        touch = fkey is not None and p.geom.intersects(F)
        efk = fkey if touch else None
        k = (p.S, p.key, efk, Lclip)
        if k in rcache:
            return rcache[k], efk
        g = p.geom
        if Lclip and g.intersects(L):
            g = clean(g.difference(L))
        if g is not None and touch:
            out = []
            for r in polys(clean(g.difference(F))):
                a_ = km2(r)
                if a_ < 1:
                    continue
                if r.distance(F) > 0.02:                      # remote part (e.g. Greenland, Siberia, Canaries)
                    out.append(r); continue
                ring = clean(r.buffer(0.01).difference(r))
                unc = clean(ring.difference(F)) if ring is not None else None
                enclosed = ring is not None and (unc is None or unc.area < 0.15 * ring.area)
                if enclosed:
                    if not cp_ever and a_ >= 20:                  # polity CShapes-Europe never maps (Hamburg...)
                        out.append(r)
                elif a_ >= 50000 or (a_ >= 2000 and compactness(r) >= 0.05):
                    out.append(r)
            g = snap(shapely.union_all(out)) if out else None
        rcache[k] = g
        return g, efk

    # ---- 1607-1885
    log('assembling 1607-1885')
    latam78 = {}
    for p in hb[1878].values():                                    # 1878 polities inside the Latin America mask
        g = clean(p.geom.intersection(L)) if p.geom.intersects(L) else None
        if g is not None:
            latam78[p.key] = g
    # US/Canada slivers that fall south of the NE border join HB 1878 Mexico
    mex = latam78.get(('Mexico', ''))
    for k in list(latam78):
        if k[0] in ('United States', 'Canada', 'Russian Empire', 'Alaska'):
            g = latam78.pop(k)
            if mex is not None:
                touch = [q for q in polys(g) if q.distance(mex) < 0.01]
                if touch:
                    mex = snap(shapely.union_all([mex] + touch))
    if mex is not None:
        latam78[('Mexico', '')] = mex

    for Y in range(FIRST, LAST_HB + 1):
        keys = []
        S = latest_snap(Y)
        europe = 1816 <= Y <= LAST_HB
        lat = LATAM_FROM <= Y <= LATAM_TO
        if not europe:                                             # 1607-1815: one snapshot for the world
            for p in hb[S].values():
                keys.append(put(('hb', S, p.key), p.name, p.sub, 'hb', p.prec, lambda p=p: p.geom))
            year_keys[Y] = [k for k in keys if k]
            continue
        active = [r for r in cse if r.y0 <= Y <= r.y1]
        fkey, F = footprint(active)
        rows_by_name = {}
        for r in active:
            n, sub = N.cse_props(r.rid, r.raw, r.holder, Y)
            rows_by_name[n] = (r, n, sub)
        hb_to_row = {}
        for n, (r, _, _) in rows_by_name.items():
            for hn in CSE_HB_ALIAS.get(n, [n]):
                hb_to_row.setdefault(hn, n)
        attach = collections.defaultdict(list)                     # cse name -> [(hb polity, remainder geom)]
        # renames/merges of 1815 North American polities after 1821
        merge_us = []
        for p in hb[S].values():
            name, sub, key_extra = p.name, p.sub, ()
            if S == 1815 and Y >= LATAM_FROM:
                if p.name == 'Spanish Florida' or (p.name == 'Viceroyalty of New Spain' and Y >= 1848):
                    merge_us.append(p); continue
                if p.name == 'Viceroyalty of New Spain':
                    continue                                       # part of Mexico ('hbmx') until 1847
                if p.name == 'Russian America' and Y >= 1868:
                    name, sub = 'Alaska', 'United States'
                if p.name == 'British North America' and Y >= 1868:
                    name, sub = 'Canada', ''
                if p.name == 'United States':
                    continue                                       # handled with merge_us below
            cpn = hb_to_row.get(p.name)
            g, efk = remainder(p, fkey, F, lat and S == 1815, p.name in cp_ever_names)
            if g is None:
                continue
            if cpn is not None:
                attach[cpn].append((p, g, efk))
                continue
            if g is p.geom and (name, sub) == p.key:
                ck = ('hb', S, p.key)
            else:
                ck = ('hbx', S, p.key, name, sub, efk, lat and S == 1815)
            keys.append(put(ck, name, sub, 'hb', p.prec, lambda g=g: g))
        if S == 1815 and Y >= LATAM_FROM:
            us = hb[1815][('United States', '')]
            parts = [remainder(q, fkey, F, lat, False)[0] for q in [us] + merge_us]
            tag = tuple(sorted(q.name for q in merge_us))
            keys.append(put(('hbus', tag, lat), 'United States', '', 'hb', us.prec,
                            lambda parts=parts: snap(shapely.union_all([q for q in parts if q is not None]))))
        if lat:
            for k, g in latam78.items():
                p = hb[1878][k]
                if k == ('Mexico', '') and Y < 1848:
                    # 1822-1847: Mexico = HB 1878 Mexico (south of today's border) + HB 1815 New Spain north of it
                    ns, _ = remainder(hb[1815][('Viceroyalty of New Spain', 'Spain')], fkey, F, True, False)
                    keys.append(put(('hbmx',), 'Mexico', '', 'hb', min(p.prec, 3),
                                    lambda g=g, ns=ns: snap(shapely.union_all([g, ns]))))
                    continue
                keys.append(put(('hb78L', k), p.name, p.sub, 'hb', p.prec, lambda g=g: g))
        actset = {r.uid for r in active}
        for n, (r, n_, sub) in rows_by_name.items():
            beats = tuple(sorted(o.uid for o in r.losers_to if o.uid in actset))
            rg = r.geom
            if beats:
                ck = ('csefix', r.uid, beats)
                if ck not in fixcache:
                    fixcache[ck] = snap(r.geom.difference(shapely.union_all([o.geom for o in r.losers_to if o.uid in beats])))
                rg = fixcache[ck]
            extra = attach.get(n, [])
            if extra:
                ek = tuple(sorted((p.S, p.key, efk) for p, _, efk in extra))
                ck = ('cse+hb', r.uid, n, sub, ek, beats)
                prec = min([3] + [p.prec for p, _, _ in extra])
                keys.append(put(ck, n, sub, 'cshapes+hb', prec,
                                lambda rg=rg, extra=extra: snap(shapely.union_all([rg] + [g for _, g, _ in extra]))))
            else:
                keys.append(put(('cse', r.uid, n, sub, beats), n, sub, 'cshapes', 3, lambda rg=rg: rg))
        year_keys[Y] = [k for k in keys if k]
        if Y % 10 == 0:
            log(f'  {Y}: {len(year_keys[Y])} polities, {len(comps)} components so far')

    # ---- runs of consecutive years -> features with from/to
    feats = []
    runs = collections.defaultdict(list)
    for Y in sorted(year_keys):
        for k in year_keys[Y]:
            rs = runs[k]
            if rs and rs[-1][1] == Y - 1:
                rs[-1][1] = Y
            else:
                rs.append([Y, Y])
    used_ids = collections.Counter()
    for k, rs in runs.items():
        c = comps[k]
        for y0, y1 in rs:
            if c['src'] == 'hb':
                S = k[1] if k[0] in ('hb', 'hbx') else (1878 if k[0] == 'hb78L' else 1815)
                base = f'hb{S}_{slug(c["name"])}'
                frm = f'{S}-01-01' if (y0 == max(FIRST, S) or (S < FIRST and y0 == FIRST)) else f'{y0}-01-01'
            else:
                base = f'cse_{slug(c["name"])}'
                frm = f'{y0}-01-01'
            to = f'{y1}-12-31'
            feats.append(dict(base=base, y0=y0, frm=frm, to=to, c=c))
            used_ids[base] += 1
    taken = set()
    for f in feats:
        i = f['base'] if used_ids[f['base']] == 1 else f"{f['base']}_{f['y0']}"
        if i in taken:
            i2 = f"{i}_{slug(f['c']['sub'])}" if f['c']['sub'] else i
            n = 2
            while i2 in taken:
                i2 = f'{i}_{n}'; n += 1
            i = i2
        taken.add(i)
        f['id'] = i
    log(f'1607-1885: {len(feats)} features')

    # ---- 1886-2026 CShapes 2.0
    log('CShapes 2.0')
    topo = json.load(open(os.path.join(a.cshapes_dir, 'rpkg/cshapes/inst/extdata/cshapes_2_gw.topojson')))
    cs = []
    for p, g in topo_decode(topo, 'cshapes_2_gw'):
        g = stitch_antimeridian(snap(g))
        owner = int(p['owner']) if str(p['owner']).lstrip('-').isdigit() else None
        for frm, to, name, sub in N.cs_periods(p['gwcode'], p['country_name'], p['start'], p['end'], p['status'], owner):
            to2 = STILL if to == CS_LAST else to
            cs.append(dict(id=f"cs_{p['gwcode']}_{frm.replace('-', '')}", name=name, sub=sub, src='cshapes',
                           frm=frm, to=to2, prec=3, geom=g, gw=p['gwcode']))
    # Hawaii before US annexation
    hawaii = next(c for c in cs if c['gw'] == 4)
    for frm, to, name, sub in N.HAWAII:
        cs.append(dict(id=f"cs_4_{frm.replace('-', '')}", name=name, sub=sub, src='cshapes', frm=frm, to=to,
                       prec=3, geom=hawaii['geom'], gw=4))
    # Natural Earth fills
    nebyname = collections.defaultdict(list)
    for p, g in ne:
        nebyname[p['name']].append(g)
    cs_tree_geoms = [c['geom'] for c in cs]
    tree = STRtree(cs_tree_geoms)
    nfill = 0
    ne_ids = set()
    for src, segs in N.FILLS:
        nm, bb = (src, None) if isinstance(src, str) else src
        g = clean(shapely.union_all(nebyname[nm])) if nebyname.get(nm) else None
        if g is None:
            log(f'  fill: no NE shape for {nm}'); continue
        g = stitch_antimeridian(g)
        if bb:
            g = clean(g.intersection(box(*bb)))
        g = snap(g)
        if g is None:
            continue
        hits = [cs[i] for i in tree.query(g) if cs_tree_geoms[i].intersects(g)]
        for frm, to, name, sub in segs:
            # split the segment wherever the set of overlapping CShapes polygons changes
            cuts = sorted({h['frm'] for h in hits if frm < h['frm'] <= to} |
                          {_next(h['to']) for h in hits if frm <= h['to'] < to})
            bounds = [frm] + cuts
            prev = None
            for i, b in enumerate(bounds):
                e = to if i == len(bounds) - 1 else _prev(bounds[i + 1])
                over = [h['geom'] for h in hits if h['frm'] <= e and h['to'] >= b]
                gg = clean(g.difference(shapely.union_all(over))) if over else g
                if gg is not None:
                    gg = clean(shapely.union_all([q for q in polys(gg) if km2(q) >= 2])) if any(km2(q) >= 2 for q in polys(gg)) else None
                if gg is None:
                    prev = None; continue
                if prev is not None and prev['geom'].equals(gg) and prev['to'] == _prev(b):
                    prev['to'] = e; continue
                nid = f'ne_{slug(name)}_{b.replace("-", "")}'
                while nid in ne_ids:
                    nid += '_b'
                ne_ids.add(nid)
                prev = dict(id=nid, name=name, sub=sub, src='ne', frm=b, to=e,
                            prec=3, geom=gg, gw=None)
                cs.append(prev); nfill += 1
    log(f'  CShapes features {len(cs) - nfill}, NE fills {nfill}')

    # ---- write
    out = []
    for f in feats:
        c = f['c']
        out.append(to_feature(c['geom'], dict(id=f['id'], name=c['name'], sub=c['sub'], src=c['src'],
                                              **{'from': f['frm'], 'to': f['to']}, precision=c['prec'])))
    for c in cs:
        out.append(to_feature(c['geom'], dict(id=c['id'], name=c['name'], sub=c['sub'], src=c['src'],
                                              **{'from': c['frm'], 'to': c['to']}, precision=c['prec'])))
    ids = collections.Counter(f['properties']['id'] for f in out)
    dup = [i for i, n in ids.items() if n > 1]
    assert not dup, dup[:10]
    dump_fc(os.path.join(a.work, 'world_hist_raw.geojson'), out)

    years = {}
    for Y in range(FIRST, LAST + 1):
        d = f'{Y}-07-01'
        years[str(Y)] = sorted(f['properties']['id'] for f in out if f['properties']['from'] <= d <= f['properties']['to'])
    # consistency with the per-year assembly
    for Y, ks in year_keys.items():
        assert len(years[str(Y)]) == len(ks), (Y, len(years[str(Y)]), len(ks))
    with open(a.years_out, 'w') as fh:
        json.dump({'description': 'Ids of world_hist.topo.json polities in force on July 1 of each year. '
                                  'See WORLD_HIST_NOTES.md for the selection rule.',
                   'snapshot': 'July 1', 'first_year': FIRST, 'last_year': LAST, 'years': years},
                  fh, separators=(',', ':'), ensure_ascii=False)
    log(f'wrote {len(out)} features; years file {a.years_out}')


def _prev(d):
    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()


def _next(d):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()


if __name__ == '__main__':
    main()
