"""Shared geometry helpers for the historical world layer build (shapely 2.x, numpy)."""
import json
import math

import numpy as np
import shapely
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely import make_valid

R_KM = 6371.0088


def topo_decode(topo, objname):
    """Decode a (non-quantized or quantized) TopoJSON object into a list of (properties, shapely geom)."""
    arcs = topo['arcs']
    tr = topo.get('transform')
    dec = []
    for a in arcs:
        if tr:
            x = y = 0
            pts = []
            for dx, dy in a:
                x += dx; y += dy
                pts.append((x * tr['scale'][0] + tr['translate'][0], y * tr['scale'][1] + tr['translate'][1]))
            dec.append(pts)
        else:
            dec.append([tuple(p[:2]) for p in a])

    def ring(idxs):
        pts = []
        for i in idxs:
            seg = dec[i] if i >= 0 else dec[~i][::-1]
            pts.extend(seg if not pts else seg[1:])
        return pts

    out = []
    for g in topo['objects'][objname]['geometries']:
        t = g.get('type')
        if t == 'Polygon':
            geom = Polygon(ring(g['arcs'][0]), [ring(r) for r in g['arcs'][1:]])
        elif t == 'MultiPolygon':
            geom = MultiPolygon([Polygon(ring(p[0]), [ring(r) for r in p[1:]]) for p in g['arcs']])
        else:
            geom = None
        out.append((g.get('properties', {}), geom))
    return out


def polys(g):
    """List of Polygon parts of any geometry (drops points/lines)."""
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, (MultiPolygon, GeometryCollection)):
        out = []
        for p in g.geoms:
            out.extend(polys(p))
        return out
    return []


def clean(g):
    """Valid (Multi)Polygon or None."""
    if g is None or g.is_empty:
        return None
    if not g.is_valid:
        g = make_valid(g)
    ps = [p for p in polys(g) if p.area > 0]
    if not ps:
        return None
    return ps[0] if len(ps) == 1 else MultiPolygon(ps)


def km2(g):
    """Approximate area in km² (sinusoidal projection about the geometry's own centre: equal-area)."""
    if g is None or g.is_empty:
        return 0.0
    cx = g.centroid.x
    def f(c):
        x = (c[:, 0] - cx) * np.cos(np.radians(c[:, 1])) * (math.pi / 180) * R_KM
        y = c[:, 1] * (math.pi / 180) * R_KM
        return np.column_stack([x, y])
    return shapely.transform(g, f).area


def perim_km(g):
    cx = g.centroid.x
    def f(c):
        x = (c[:, 0] - cx) * np.cos(np.radians(c[:, 1])) * (math.pi / 180) * R_KM
        y = c[:, 1] * (math.pi / 180) * R_KM
        return np.column_stack([x, y])
    return shapely.transform(g, f).length


def compactness(p):
    """Polsby-Popper 4πA/P² (1 = circle, ~0 = sliver)."""
    a = km2(p); per = perim_km(p)
    return 0.0 if per == 0 else 4 * math.pi * a / (per * per)


def stitch_antimeridian(g):
    """Shift parts that touch lon=-180 by +360 and union, so features split at the antimeridian become one
    piece (coordinates may then exceed 180, which d3-geo handles on the sphere)."""
    if g is None:
        return None
    ps = polys(g)
    if not any(p.bounds[0] <= -179.999 for p in ps) or not any(p.bounds[2] >= 179.999 for p in ps):
        return g
    moved = []
    for p in ps:
        if p.bounds[0] <= -179.999 and p.bounds[2] < 0:
            moved.append(shapely.transform(p, lambda c: c + np.array([360.0, 0.0])))
        else:
            moved.append(p)
    # snap the seam so the two halves share the 180° edge exactly
    u = shapely.union_all([shapely.set_precision(p, 1e-7) for p in moved])
    return clean(u)


def to_feature(geom, props):
    return {'type': 'Feature', 'properties': props, 'geometry': mapping(geom)}


def dump_fc(path, feats):
    with open(path, 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': feats}, fh)


def _unwrap_coords(coords):
    out = [list(coords[0])]
    off = 0.0
    for i in range(1, len(coords)):
        dx = coords[i][0] - coords[i - 1][0]
        if dx > 180:
            off -= 360
        elif dx < -180:
            off += 360
        out.append([coords[i][0] + off, coords[i][1]])
    return out


def unwrap(g):
    """Make rings that jump across the antimeridian (lon step > 180°) continuous, so a planar library sees the
    right shape; parts are then shifted so they start at lon >= -180 (crossing parts extend beyond +180)."""
    if g is None:
        return None
    out = []
    for p in polys(g):
        rings = [list(p.exterior.coords)] + [list(r.coords) for r in p.interiors]
        if not any(abs(r[i + 1][0] - r[i][0]) > 180 for r in rings for i in range(len(r) - 1)):
            out.append(p); continue
        ext = _unwrap_coords(rings[0])
        if abs(ext[-1][0] - ext[0][0]) > 1e-6:      # ring encircles a pole (e.g. Antarctica): leave as is
            out.append(p); continue
        holes = [_unwrap_coords(r) for r in rings[1:]]
        q = Polygon(ext, holes)
        if q.bounds[0] < -180:
            q = shapely.transform(q, lambda c: c + np.array([360.0, 0.0]))
        out.append(q)
    return clean(MultiPolygon(out) if len(out) > 1 else out[0]) if out else None
