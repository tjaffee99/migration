#!/usr/bin/env python3
"""Geometric checks of the final web/geo/world_hist.topo.json (decoded, after simplification/quantization):
for sample years, (1) total area where two polities of the same year overlap, listing the worst pairs, and
(2) share of Natural Earth 1:50m land (excluding Antarctica) covered by the year's polities.

    python3 -I verify_overlaps.py [year ...]
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shapely  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402
from geo_util import topo_decode, clean, km2, unwrap, stitch_antimeridian, polys  # noqa: E402

GEO = os.path.join(HERE, '../../web/geo')
years = [int(a) for a in sys.argv[1:]] or [1610, 1700, 1776, 1815, 1816, 1822, 1850, 1866, 1871, 1880, 1885,
                                           1886, 1890, 1914, 1925, 1939, 1950, 1960, 1990, 2026]
topo = json.load(open(os.path.join(GEO, 'world_hist.topo.json')))
idx = json.load(open(os.path.join(GEO, 'world_hist_years.json')))['years']
feats = {p['id']: (p, clean(g)) for p, g in topo_decode(topo, 'polities')}
ne = json.load(open(os.path.join(GEO, 'world_50m.topo.json')))
land = [q for _, g in topo_decode(ne, 'land') for q in polys(unwrap(clean(g))) if q.bounds[3] > -60]
land = stitch_antimeridian(clean(shapely.union_all(land)))
land_km2 = km2(land)
print(f'NE 50m land excl. Antarctica: {land_km2 / 1e6:.1f} M km²')
for y in years:
    ids = idx[str(y)]
    gs = [feats[i][1] for i in ids]
    tree = STRtree(gs)
    worst = []
    total = 0.0
    for i, g in enumerate(gs):
        for j in tree.query(g):
            if j <= i:
                continue
            inter = g.intersection(gs[j])
            if inter.is_empty:
                continue
            a = km2(clean(inter)) if clean(inter) is not None else 0
            if a > 0:
                total += a
                worst.append((a, feats[ids[i]][0]['name'], feats[ids[j]][0]['name']))
    worst.sort(reverse=True)
    u = shapely.union_all(gs)
    cov = km2(clean(land.intersection(u))) / land_km2
    print(f'{y}: {len(ids)} polities; overlap {total:,.0f} km²; land covered {cov * 100:.1f}%' +
          (f"; worst: {', '.join(f'{n1}/{n2} {a:,.0f}' for a, n1, n2 in worst[:3])}" if worst else ''))
