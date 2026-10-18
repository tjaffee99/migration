#!/usr/bin/env python3
"""1950 foreign-born WHITE population by country of birth, by state (state x country, 1950).

Source: U.S. Census of Population 1950, Vol. II Part 1 (U.S. Summary), Table 71
"Country of birth of the foreign-born white population, by regions, divisions, and states: 1950",
pp. 1-122/1-123 (data/raw/census1950_v2p1/21983999v2p1ch3.pdf, PDF pages 38-39), manually
transcribed into data/raw/census1950_v2p1/t71_manual/*.csv (see README.txt there).

validate() checks every constraint of the printed table: each state/division/region row adds
up to 'All countries'; states add up to their division, divisions to regions, regions to the
U.S., in every column.  rows() returns long-format rows for stock_state_by_country.csv with the
same hierarchy as the 1950 national rows (Europe / Americas / United Kingdom / Canada are sums
of printed parts, source_id ..._derived).  The block total is the foreign-born WHITE population.
Usage: python3 -I scripts/stock/build_hist_1950_t71.py   (prints the validation report)
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stocklib import STATE_FIPS  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'data', 'raw', 'census1950_v2p1', 't71_manual')

COLS_P1 = ['All countries', 'England and Wales', 'Scotland', 'Northern Ireland', 'Ireland (Eire)', 'Norway',
           'Sweden', 'Denmark', 'Netherlands', 'Belgium', 'Switzerland', 'France', 'Germany', 'Poland',
           'Czechoslovakia', 'Austria', 'Hungary']
COLS_P2 = ['Yugoslavia', 'U.S.S.R.', 'Lithuania', 'Finland', 'Rumania', 'Greece', 'Italy', 'Spain',
           'Portugal', 'Other Europe', 'Asia', 'Canada-French', 'Canada-Other', 'Mexico', 'Other America',
           'All other', 'Not reported']
COLS = COLS_P1 + COLS_P2
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
EUROPE = COLS[1:27]   # England and Wales .. Other Europe


def load():
    data, uncertain = {}, set()
    for pg, cl in (('38', COLS_P1), ('39', COLS_P2)):
        for half, cc in (('L', cl[:9]), ('R', cl[9:])):
            for blk in 'ABCDEF':
                for row in csv.reader(open(os.path.join(SRC, 'p%s_%s_%s.csv' % (pg, half, blk)))):
                    name, vals = row[0], row[1:]
                    assert len(vals) == len(cc), (pg, half, blk, name)
                    for c, v in zip(cc, vals):
                        if v.endswith('?'):
                            uncertain.add((name, c))
                            v = v[:-1]
                        data[(name, c)] = int(v)
    missing = [(n, c) for n in ROWS for c in COLS if (n, c) not in data]
    assert not missing, missing[:5]
    return data, uncertain


def validate(data):
    problems = []
    for n in ROWS:
        s = sum(data[(n, c)] for c in COLS[1:])
        if s != data[(n, 'All countries')]:
            problems.append('row %s: %d vs %d' % (n, data[(n, 'All countries')], s))
    groups = dict(DIVISIONS)
    groups.update(REGIONS)
    groups['United States'] = list(REGIONS)
    ncon = 0
    for p, kids in groups.items():
        for c in COLS:
            ncon += 1
            s = sum(data[(k, c)] for k in kids)
            if s != data[(p, c)]:
                problems.append('col %s/%s: %d vs %d' % (p, c, data[(p, c)], s))
    return problems, len(ROWS) + ncon


def rows():
    """Universe: foreign-born WHITE (complete count).  The all-races state foreign-born totals
    available (WP81 Table 14, 1950) are 20-percent-sample estimates and are smaller than the
    complete-count foreign-born white figure in 20 states, so no non-white remainder is formed."""
    data, _ = load()
    problems, _ = validate(data)
    assert not problems, problems
    S, D = 'census1950_v2p1_t71', 'census1950_v2p1_t71_derived'
    out = []
    for name in [s for d in DIVISIONS.values() for s in d]:
        fips = STATE_FIPS[name]
        v = {c: data[(name, c)] for c in COLS}

        def add(label, level, parent, count, sid):
            out.append(dict(year=1950, state_fips=fips, origin_label=label, level=level,
                            parent_label=parent, count=count, moe='', source_id=sid))
        T = 'Total (foreign-born white only)'
        add(T, 'total', '', v['All countries'], S)
        add('Europe', 'region', T, sum(v[c] for c in EUROPE), D)
        add('United Kingdom', 'country', 'Europe', v['England and Wales'] + v['Scotland'] + v['Northern Ireland'], D)
        for c in ('England and Wales', 'Scotland', 'Northern Ireland'):
            add(c, 'subcountry', 'United Kingdom', v[c], S)
        for c in EUROPE[3:]:
            add(c, 'residual' if c == 'Other Europe' else 'country', 'Europe', v[c], S)
        add('Asia', 'region', T, v['Asia'], S)
        add('Asia, country not specified (derived; incl. Turkey in Europe)', 'residual', 'Asia', v['Asia'], D)
        add('Americas', 'region', T, v['Canada-French'] + v['Canada-Other'] + v['Mexico'] + v['Other America'], D)
        add('Canada', 'country', 'Americas', v['Canada-French'] + v['Canada-Other'], D)
        add('Canada-French', 'subcountry', 'Canada', v['Canada-French'], S)
        add('Canada-Other', 'subcountry', 'Canada', v['Canada-Other'], S)
        add('Mexico', 'country', 'Americas', v['Mexico'], S)
        add('Other America', 'residual', 'Americas', v['Other America'], S)
        add('All other', 'residual', T, v['All other'], S)
        add('Not reported', 'residual', T, v['Not reported'], S)
    return out


if __name__ == '__main__':
    data, unc = load()
    problems, n = validate(data)
    print('cells', len(data), '; poorly printed cells resolved by sums:', len(unc))
    print('constraints checked', n, '; violations', len(problems))
    for p in problems:
        print(' ', p)
