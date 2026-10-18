#!/usr/bin/env python3
"""Build data/processed/stock_national_by_country.csv

Sources (raw files under data/raw/):
  census_wp81/tab04.xls  WP81 Table 4 (1930-era detail) -> 1850-1930      [census_wp81_t4]
  census_wp81/tab03.xls  WP81 Table 3 (detailed)         -> 1960-2000      [census_wp81_t3]
  census1950_v4p3 / census1940 transcriptions            -> 1940, 1950     [see build_1940_1950.py]
  acs_sf_2005_2009/      ACS 1-year summary file B05006  -> 2005-2009      [acs1_sf_b05006]
  acs1_api/              ACS 1-year B05006 (data.census.gov) -> 2010-2019, 2021-2024 [acs1_api_b05006]
Cross-checks against WP29 tables 3/4 are printed (census_wp29/table03.xlsx, table04.xlsx).

Usage: python3 -I scripts/stock/build_national.py
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlrd, openpyxl  # noqa: E402
from stocklib import (Node, reparent, build_tree_from_depths, build_tree_from_paths, finalize_tree,  # noqa
                      check_partition, parse_num, clean_label, indent_depth)
import acs_read  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw')
PROC = os.path.join(ROOT, 'data', 'processed')
WARN = []


def read_wp81(tabno):
    sh = xlrd.open_workbook(os.path.join(RAW, 'census_wp81', 'tab%02d.xls' % tabno)).sheet_by_index(0)
    # header row: find the row whose cells contain year headings
    hdr_row = None
    for r in range(10):
        vals = [str(sh.cell_value(r, c)) for c in range(sh.ncols)]
        if any(v.startswith('2000') for v in vals):
            hdr_row = r
            break
    years = {}
    for c in range(sh.ncols):
        v = str(sh.cell_value(hdr_row, c)).replace('*', '').strip()
        try:
            y = int(float(v))
            if 1800 < y <= 2000:
                years[c] = y
        except ValueError:
            pass
    label_col = 0 if tabno == 3 else 2
    rows = []
    for r in range(hdr_row + 1, sh.nrows):
        raw = sh.cell_value(r, label_col)
        if not str(raw).strip():
            continue
        if str(raw).startswith('Footnotes') or str(raw).startswith(' *'):
            break
        lab = clean_label(raw)
        vals = {y: parse_num(sh.cell_value(r, c)) for c, y in years.items()}
        rows.append([lab, indent_depth(raw), vals, str(raw)])
    return rows, sorted(years.values())


def wp_tree(rows, tabno):
    # first data row is Total; 'Reported by region and/or country' is dropped (= Total minus
    # not reported) and its children are attached to Total.
    assert rows[0][0] == 'Total', rows[0]
    fixed = []
    for lab, depth, vals, raw in rows:
        if lab.startswith('Reported by region'):
            continue
        fixed.append([lab, depth, vals, raw])
    # depth normalisation: regions are rows with one leading dot ('.   Europe'); everything
    # else is parsed with its leading-run length.  Total is the root.
    root = build_tree_from_depths([(r[0], r[1], r[2]) for r in fixed])
    # 'Region or country not reported' has depth 0 like 'Reported...' -> child of root. ok.
    return root


def relabel(root, tabno):
    for n in root.walk():
        p = n.parent.label if n.parent else ''
        if n.label == 'Great Britain (total)':
            n.label = 'Great Britain'
        if n.label == 'Micronesia' and n.children:
            n.label = 'Micronesia (region)'
        elif n.label == 'Micronesia':
            n.label = 'Micronesia (incl. Federated States of Micronesia)'
        if n.label == 'Soviet Union (former, part)':
            n.label = 'Former Soviet Union (part), ' + p
        if n.label == 'In Europe' and p.startswith('Soviet Union'):
            n.label = 'Former Soviet Union, in Europe'
        if tabno == 4 and n.label == 'Portugal' and n.children:
            n.label = 'Portugal (total)'
        if n.label == 'Other' and p == 'Other Caribbean':
            n.label = 'Other Caribbean, other'


def unique_labels_check(rows, key):
    seen = {}
    for r in rows:
        k = r['origin_label']
        if k in seen:
            WARN.append('duplicate label %r in %s' % (k, key))
        seen[k] = 1


def national_wp():
    out = []
    # ---- Table 4: 1850-1930
    rows4, years4 = read_wp81(4)
    root4 = wp_tree(rows4, 4)
    relabel(root4, 4)
    for y in [y for y in years4 if y <= 1930]:
        rr = finalize_tree(root4, y, 'census_wp81_t4', warn=WARN)
        for r in rr:
            r['year'] = y
        unique_labels_check(rr, y)
        out += rr
    # ---- Table 3: 1960-2000
    rows3, years3 = read_wp81(3)
    root3 = wp_tree(rows3, 3)
    relabel(root3, 3)
    # Indentation of 'Northern Ireland' in WP81 T3 is deeper than 'Great Britain (total)',
    # but it is a part of the United Kingdom (UK = Great Britain + Northern Ireland).
    reparent(root3, 'Northern Ireland', 'United Kingdom')
    for n in root3.walk():
        if n.label in ('Gambia', 'Guinea', 'Ivory Coast (Cote d\'Ivoire)') and n.parent.label == 'Western Africa':
            # WP81 added 1990 values for these three countries without changing the 1990
            # Western Africa subtotal (111,566 = WP29 value = sum of the six countries shown in
            # WP29) -- in 1990 they are contained in 'Africa n.e.c.'.  Drop the 1990 values so
            # nothing is double counted.
            WARN.append('NOTE dropped WP81 T3 1990 %s=%s (contained in Africa n.e.c.)' %
                        (n.label, n.values.get(1990)))
            n.values[1990] = None
        if n.label == 'Soviet Union (former)':
            # In 2000 this row (838,809) is a memo total that also includes the Asian
            # republics shown under South Central / Western Asia; Eastern Europe sums with the
            # 'In Europe' part only.  Drop the memo value for 2000 so the parts take its place.
            n.values[2000] = None
        if n.label == 'Region or country not reported' and n.values.get(1970) == 315721:
            # WP81 Table 3 prints 315,721; Total - Reported = 315,732, which is also the value
            # in WP81 Table 4 and WP29 Table 3.  Use the internally consistent value.
            n.values[1970] = 315732
            WARN.append('NOTE corrected WP81 T3 1970 not-reported 315721 -> 315732')
    for y in years3:
        rr = finalize_tree(root3, y, 'census_wp81_t3', warn=WARN)
        for r in rr:
            r['year'] = y
            if y in (1960, 1970) and r['origin_label'] == 'Cape Verde':
                # WP81 T3 footnote 6: in 1960 and 1970 the figure is for Other Atlantic Islands
                r['origin_label'] = 'Cape Verde (1960-1970: Other Atlantic Islands)'
        unique_labels_check(rr, y)
        out += rr
    return out, root3, root4


def acs_tree_from_labels(labels, est, moe):
    items = []
    for n, path in sorted(labels.items()):
        if n == 1:
            continue
        items.append((path, 'v', est.get(n)))
    root, index = build_tree_from_paths(items)
    root.values['v'] = est.get(1)
    moes = {}
    for n, path in labels.items():
        moes[path[-1] if path else 'Total'] = moe.get(n)
    return root, index, moes


def acs_rows(labels, est, moe, source_id, year):
    root, index, _ = acs_tree_from_labels(labels, est, moe)
    # moe by node
    moe_by_node = {}
    for n, path in labels.items():
        node = root if not path else index[tuple(path)]
        moe_by_node[id(node)] = moe.get(n)
    rr = finalize_tree(root, 'v', source_id, warn=WARN)
    # attach moe by matching label + parent (labels unique within the ACS tree)
    lab2moe = {}
    for node in root.walk():
        lab2moe[node.label] = moe_by_node.get(id(node))
    for r in rr:
        r['moe'] = '' if r['source_id'].endswith('_derived') else lab2moe.get(r['origin_label'], '')
        if r['moe'] is None:
            r['moe'] = ''
        r['year'] = year
    unique_labels_check(rr, year)
    return rr


def acs_labels(year, table='B05006'):
    if year <= 2009:
        p = os.path.join(RAW, 'acs_sf_2005_2009', 'groups_acs1_%d_%s.json' % (year, table))
    else:
        p = os.path.join(RAW, 'acs1_api', 'groups_acs1_%d_%s.json' % (year, table))
    labs = acs_read.load_groups(p, table)
    return labs


def check_sf_labels(year, labels):
    titles = acs_read.load_sf_lookup_titles(year, 'B05006')
    bad = 0
    for ln, t in titles.items():
        lab = labels.get(ln)
        last = lab[-1] if lab else 'Total'
        if t.replace(' ', '').lower() != last.replace(' ', '').lower():
            bad += 1
            if bad < 5:
                WARN.append('SF %d line %d title %r vs API label %r' % (year, ln, t, last))
    return bad


def national_acs():
    out = []
    for year in range(2005, 2025):
        if year == 2020:
            # no standard 2020 1-year release; use the 2016-2020 5-year estimates as a stand-in
            labels = acs_read.load_groups(os.path.join(RAW, 'acs5_2020', 'groups_acs5_2020_B05006.json'),
                                          'B05006')
            d = acs_read.load_api_table(os.path.join(RAW, 'acs5_2020', 'ACSDT5Y2020_B05006_us.json'),
                                        'B05006')
            out += acs_rows(labels, d['0100000US']['E'], d['0100000US']['M'], 'acs5_2016_2020_b05006',
                            year)
            continue
        labels = acs_labels(year)
        if year <= 2009:
            check_sf_labels(year, labels)
            recs = acs_read.load_sf_table(year, 'B05006')
            us = [r for d, r in recs.items() if r['stusab'] == 'US']
            assert len(us) == 1
            est, moe = us[0]['E'], us[0]['M']
            sid = 'acs1_sf_b05006'
        else:
            d = acs_read.load_api_table(os.path.join(RAW, 'acs1_api', 'ACSDT1Y%d_B05006_us.json' % year),
                                        'B05006')
            est, moe = d['0100000US']['E'], d['0100000US']['M']
            sid = 'acs1_api_b05006'
        out += acs_rows(labels, est, moe, sid, year)
    return out


def crosscheck_wp29(root3, root4):
    """Compare WP81 values with WP29 tables 3/4 (1850-1990) by label."""
    msgs = []
    wb = openpyxl.load_workbook(os.path.join(RAW, 'census_wp29', 'table04.xlsx'), read_only=True)
    ws = wb.worksheets[0]
    yrs = [1990, 1980, 1970, 1960, 1930, 1920, 1910, 1900, 1890, 1880, 1870, 1860, 1850]
    wp81 = {}
    for n in root4.walk():
        wp81.setdefault(n.label, n.values)
    nmatch = nmis = 0
    for row in ws.iter_rows(values_only=True):
        if not row or not isinstance(row[0], (int, float)) or row[2] is None:
            continue
        lab = clean_label(row[2])
        if lab == 'Portugal':
            continue   # label used twice in Table 4 (total and part); not comparable by label
        v81 = wp81.get(lab) or wp81.get(lab.replace('Portugal', 'Portugal (total)'))
        if v81 is None:
            continue
        for i, y in enumerate(yrs):
            a = parse_num(row[3 + i])
            b = v81.get(y)
            if a is None and b is None:
                continue
            if a == b:
                nmatch += 1
            else:
                nmis += 1
                msgs.append('WP29 T4 vs WP81 T4 %s %s: %s vs %s' % (lab, y, a, b))
    msgs.insert(0, 'WP29 T4 vs WP81 T4: %d cells equal, %d differ' % (nmatch, nmis))
    # ---- Table 3, 1960-1990
    wb = openpyxl.load_workbook(os.path.join(RAW, 'census_wp29', 'table03.xlsx'), read_only=True)
    ws = wb.worksheets[0]
    yrs3 = [1990, 1980, 1970, 1960]
    wp81_3 = {}
    for n in root3.walk():
        wp81_3.setdefault(n.label, n.values)
    nm = nd = 0
    m3 = []
    for row in ws.iter_rows(values_only=True):
        if not row or row[0] is None or len(row) < 5:
            continue
        lab = clean_label(row[0]).replace(' (total)', '') if 'Great Britain' in str(row[0]) else clean_label(row[0])
        v81 = wp81_3.get(lab)
        if v81 is None:
            continue
        for i, y in enumerate(yrs3):
            a, b = parse_num(row[1 + i]), v81.get(y)
            if a is None and b is None:
                continue
            if a == b:
                nm += 1
            else:
                nd += 1
                m3.append('WP29 T3 vs WP81 T3 %s %s: %s vs %s' % (lab, y, a, b))
    msgs.append('WP29 T3 vs WP81 T3: %d cells equal, %d differ' % (nm, nd))
    return msgs + m3


def main():
    wp, root3, root4 = national_wp()
    acs = national_acs()
    rows = wp + acs
    for r in rows:
        r.setdefault('moe', '')
    # partition check
    keys = sorted(set((r['year'], r['source_id'].replace('_derived', '')) for r in rows))
    print('year source total country+residual')
    for y, s in keys:
        sub = [r for r in rows if r['year'] == y and r['source_id'].replace('_derived', '') == s]
        t, p = check_partition(sub)
        flag = '' if t == p else '  <-- MISMATCH'
        print(y, s, t, p, flag)
    os.makedirs(PROC, exist_ok=True)
    fn = os.path.join(PROC, 'stock_national_by_country.csv')
    with open(fn, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year', 'origin_label', 'level', 'parent_label', 'count', 'source_id'])
        for r in sorted(rows, key=lambda r: r['year']):
            w.writerow([r['year'], r['origin_label'], r['level'], r['parent_label'], r['count'],
                        r['source_id']])
    print('wrote', fn, len(rows), 'rows')
    for m in crosscheck_wp29(root3, root4)[:40]:
        print(m)
    for w_ in WARN:
        print('WARN', w_)


if __name__ == '__main__':
    main()
