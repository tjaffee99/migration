#!/usr/bin/env python3
"""1950 foreign-born WHITE population by country of birth, by state.

Source: U.S. Census of Population 1950, Vol. II Part 1 (U.S. Summary), Table 71
"Country of birth of the foreign-born white population, by regions, divisions, and states: 1950",
pp. 1-122/1-123 = PDF pages 38-39 of data/raw/census1950_v2p1/21983999v2p1ch3.pdf.

Pipeline: OCR tokens (ocr_census_table.py -> data/raw/census1950_v2p1/ocr/t71_p3{8,9}.json)
-> grid by row (y) and column (right edge x) -> manual corrections read off the page image
(data/raw/census1950_v2p1/t71_corrections.csv) -> validation: every state row must add up to
'All countries', every division to the sum of its states, every region to its divisions and
the U.S. to its regions, for every column.  Only a fully validated grid is written.

Output: data/raw/census1950_v2p1/t71_validated_grid.csv (wide) and rows appended to the
historical state x country file used by build_state_by_country.py.
Usage: python3 -I scripts/stock/build_hist_1950_t71.py [--report]
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocr_census_table import tokens, parse_int  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'data', 'raw', 'census1950_v2p1')
OCR_DPI = 400   # dpi used for ocr_census_table.py on pages 38-39

COLS_P1 = ['All countries', 'England and Wales', 'Scotland', 'Northern Ireland', 'Ireland (Eire)', 'Norway',
           'Sweden', 'Denmark', 'Netherlands', 'Belgium', 'Switzerland', 'France', 'Germany', 'Poland',
           'Czechoslovakia', 'Austria', 'Hungary']
COLS_P2 = ['Yugoslavia', 'U.S.S.R.', 'Lithuania', 'Finland', 'Rumania', 'Greece', 'Italy', 'Spain',
           'Portugal', 'Other Europe', 'Asia', 'Canada-French', 'Canada-Other', 'Mexico', 'Other America',
           'All other', 'Not reported']
REGIONS = {'Northeast': ['New England', 'Middle Atlantic'],
           'North Central': ['E. N. Central', 'W. N. Central'],
           'South': ['South Atlantic', 'E. S. Central', 'W. S. Central'],
           'West': ['Mountain', 'Pacific']}
DIVISIONS = {
    'New England': ['Maine', 'New Hampshire', 'Vermont', 'Massachusetts', 'Rhode Island', 'Connecticut'],
    'Middle Atlantic': ['New York', 'New Jersey', 'Pennsylvania'],
    'E. N. Central': ['Ohio', 'Indiana', 'Illinois', 'Michigan', 'Wisconsin'],
    'W. N. Central': ['Minnesota', 'Iowa', 'Missouri', 'North Dakota', 'South Dakota', 'Nebraska', 'Kansas'],
    'South Atlantic': ['Delaware', 'Maryland', 'District of Columbia', 'Virginia', 'West Virginia',
                       'North Carolina', 'South Carolina', 'Georgia', 'Florida'],
    'E. S. Central': ['Kentucky', 'Tennessee', 'Alabama', 'Mississippi'],
    'W. S. Central': ['Arkansas', 'Louisiana', 'Oklahoma', 'Texas'],
    'Mountain': ['Montana', 'Idaho', 'Wyoming', 'Colorado', 'New Mexico', 'Arizona', 'Utah', 'Nevada'],
    'Pacific': ['Washington', 'Oregon', 'California']}
ROWS = (['United States'] + list(REGIONS) + [d for r in REGIONS.values() for d in r] +
        [s for d in DIVISIONS.values() for s in d])


def grid_from_ocr(path, ncols, xmin=380, ymin=330, k=1.0):
    xmin, ymin = xmin * k, ymin * k
    toks = [t for t in tokens(path) if t['xl'] > xmin and t['y'] > ymin and any(c.isdigit() for c in t['text'])]
    # columns: cluster right edges
    xr = sorted(t['xr'] for t in toks)
    centers = []
    for x in xr:
        if centers and x - centers[-1][-1] < 40 * k:
            centers[-1].append(x)
        else:
            centers.append([x])
    centers = [sorted(c)[len(c) // 2] for c in centers if len(c) >= 10]
    for t in toks:
        t['col'] = min(range(len(centers)), key=lambda k: abs(centers[k] - t['xr']))
        t['dx'] = abs(centers[t['col']] - t['xr'])
    # row anchors: y of tokens in the first three columns, merged when within 10 px
    ys = sorted(t['y'] for t in toks if t['col'] <= 2 and t['dx'] <= 45 * k)
    anchors = []
    for y in ys:
        if anchors and y - anchors[-1][-1] < 10 * k:
            anchors[-1].append(y)
        else:
            anchors.append([y])
    anchors = [sum(a) / len(a) for a in anchors]
    grid = [dict(y=a, cells=[None] * len(centers), raw=[''] * len(centers)) for a in anchors]
    for t in sorted(toks, key=lambda t: t['xl']):
        if t['dx'] > 45 * k:
            continue
        i = min(range(len(anchors)), key=lambda k: abs(anchors[k] - t['y']))
        if abs(anchors[i] - t['y']) > 11 * k:
            continue
        g = grid[i]
        g['raw'][t['col']] = (g['raw'][t['col']] + ' ' + t['text']).strip()
        g['cells'][t['col']] = parse_int(g['raw'][t['col']])
    return grid, centers


def constraints(cols):
    """List of (target_cell, [part cells])."""
    cons = []
    for name in ROWS:
        cons.append(((name, 'All countries'), [(name, c) for c in cols[1:]]))
    groups = dict(DIVISIONS)
    groups.update(REGIONS)
    groups['United States'] = list(REGIONS)
    for parent, kids in groups.items():
        for c in cols:
            cons.append(((parent, c), [(k, c) for k in kids]))
    return cons


def solve(data, cols):
    """Fill cells left blank by OCR when a sum constraint has exactly one unknown.
    Returns {cell: 'inferred'}; such cells are re-checked against the other constraints."""
    inferred = {}
    cons = constraints(cols)
    changed = True
    while changed:
        changed = False
        for tgt, parts in cons:
            cells = [tgt] + parts
            unk = [c for c in cells if data[c] is None]
            if len(unk) != 1:
                continue
            u = unk[0]
            if u == tgt:
                val = sum(data[p] for p in parts)
            else:
                val = data[tgt] - sum(data[p] for p in parts if p != u)
            if val < 0:
                continue
            data[u] = val
            inferred[u] = 'inferred'
            changed = True
    return inferred


def load_corrections():
    fn = os.path.join(SRC, 't71_corrections.csv')
    out = {}
    if os.path.exists(fn):
        for r in csv.DictReader(l for l in open(fn) if not l.startswith('#')):
            out[(r['row'], r['col'])] = int(r['value'])
    return out


def build(report=False):
    g1, c1 = grid_from_ocr(os.path.join(SRC, 'ocr', 't71_p38.json'), 17, k=OCR_DPI / 300)
    g2, c2 = grid_from_ocr(os.path.join(SRC, 'ocr', 't71_p39.json'), 17, k=OCR_DPI / 300)
    assert len(c1) == 17 and len(c2) == 17, (len(c1), len(c2))
    assert len(g1) == len(ROWS) and len(g2) == len(ROWS), (len(g1), len(g2), len(ROWS))
    data, raw = {}, {}
    for i, name in enumerate(ROWS):
        for j, col in enumerate(COLS_P1):
            data[(name, col)] = g1[i]['cells'][j]
            raw[(name, col)] = g1[i]['raw'][j]
        for j, col in enumerate(COLS_P2):
            data[(name, col)] = g2[i]['cells'][j]
            raw[(name, col)] = g2[i]['raw'][j]
    corr = load_corrections()
    for k, v in corr.items():
        assert k in data, k
        data[k] = v
    cols = COLS_P1 + COLS_P2
    inferred = solve(data, cols)
    problems = []
    # row checks
    for name in ROWS:
        vals = [data[(name, c)] for c in cols[1:]]
        if None in vals or data[(name, 'All countries')] is None:
            problems.append(('row-missing', name, [c for c in cols if data[(name, c)] is None]))
        elif sum(vals) != data[(name, 'All countries')]:
            problems.append(('row', name, data[(name, 'All countries')] - sum(vals)))
    # column checks
    groups = dict(DIVISIONS)
    groups.update(REGIONS)
    groups['United States'] = list(REGIONS)
    for parent, kids in groups.items():
        for c in cols:
            vals = [data[(k, c)] for k in kids]
            if None in vals or data[(parent, c)] is None:
                continue
            if sum(vals) != data[(parent, c)]:
                problems.append(('col', parent, c, data[(parent, c)] - sum(vals)))
    if report:
        for p in problems:
            print(p)
        print(len(problems), 'problems')
    return data, raw, problems, cols, inferred, (g1, c1, g2, c2)


if __name__ == '__main__':
    data, raw, problems, cols, inferred, geo = build(report=True)
    print(len(inferred), 'cells inferred from sums')
    if '--cells' in sys.argv:
        for p in problems:
            if p[0] == 'row-missing':
                for c in p[2]:
                    print('MISSING', p[1], c, repr(raw[(p[1], c)]))
    if not problems:
        out = os.path.join(SRC, 't71_validated_grid.csv')
        with open(out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['area'] + cols)
            for name in ROWS:
                w.writerow([name] + [data[(name, c)] for c in cols])
        print('validated grid written', out)
