#!/usr/bin/env python3
"""Build data/processed/stock_state_totals.csv  (year,state,state_fips,total_pop,foreign_born,source_id)

  1850-2000  WP81 Table 14 (census_wp81/tab14.xls)                     [census_wp81_t14]
             (cross-checked against WP29 Table 13 for 1850-1990)
  2005-2009  ACS 1-year summary file B05002 (total; foreign born)     [acs1_sf_b05002]
  2010-2019, 2021-2024  ACS 1-year B05002 via data.census.gov          [acs1_api_b05002]
  2020       ACS 1-year experimental table XK200503                   [acs1_2020_experimental_xk200503]

State names follow the source.  WP81/WP29 show territories under the modern state name;
where the source footnotes say the area differs, the name is annotated and state_fips is
left blank when the unit is not a single modern state (Dakota Territory 1860-1880;
Virginia incl. West Virginia 1850-1860).  Puerto Rico (fips 72) is included for ACS years
(not part of the U.S. totals).
Usage: python3 -I scripts/stock/build_state_totals.py
"""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlrd, openpyxl  # noqa: E402
from stocklib import parse_num, clean_label, STATE_FIPS  # noqa: E402
import acs_read  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw')
PROC = os.path.join(ROOT, 'data', 'processed')


def wp81_t14():
    sh = xlrd.open_workbook(os.path.join(RAW, 'census_wp81', 'tab14.xls')).sheet_by_index(0)
    out, us = [], {}
    years = None
    in_states = False
    for r in range(sh.nrows):
        c0 = str(sh.cell_value(r, 0))
        if c0.startswith('Region, division, and state'):
            ys = []
            for c in (1, 5):
                v = str(sh.cell_value(r, c)).replace('*', '').strip()
                ys.append(int(float(v)) if v else None)
            years = ys
            in_states = False
            continue
        if years is None:
            continue
        if c0.strip() == 'STATE':
            in_states = True
            continue
        lab = clean_label(c0)
        if lab == 'United States':
            for k, y in enumerate(years):
                if y:
                    us[y] = (parse_num(sh.cell_value(r, 1 + 4 * k)), parse_num(sh.cell_value(r, 3 + 4 * k)))
            continue
        if not in_states or lab.startswith('Footnotes'):
            continue
        m = re.match(r'^(.*?)\s*(\d)?$', lab)
        name, fn = m.group(1).strip(), m.group(2)
        if name not in STATE_FIPS:
            continue   # division headings
        for k, y in enumerate(years):
            if not y:
                continue
            tot = parse_num(sh.cell_value(r, 1 + 4 * k))
            fb = parse_num(sh.cell_value(r, 3 + 4 * k))
            raw_tot = str(sh.cell_value(r, 1 + 4 * k)).strip()
            if tot is None or raw_tot in ('2', '3', '1') or (isinstance(sh.cell_value(r, 1 + 4 * k), float) and tot < 10 and fb is not None and fb < 10):
                continue   # (NA), (X) or a footnote reference
            state, fips = name, STATE_FIPS[name]
            if name == 'South Dakota' and y in (1860, 1870, 1880):
                state, fips = 'Dakota Territory (shown as South Dakota in source; incl. present North Dakota)', ''
            elif name == 'Virginia' and y in (1850, 1860):
                state, fips = 'Virginia (incl. present West Virginia)', ''
            elif name == 'Oklahoma' and y == 1900:
                state = 'Oklahoma (Oklahoma Territory and Indian Territory combined)'
            out.append(dict(year=y, state=state, state_fips=fips, total_pop=tot, foreign_born=fb,
                            source_id='census_wp81_t14'))
    return out, us


def wp29_t13_check(rows81):
    """Compare WP29 Table 13 (1850-1990) with WP81 Table 14."""
    wb = openpyxl.load_workbook(os.path.join(RAW, 'census_wp29', 'table13.xlsx'), read_only=True)
    idx = {(r['year'], r['state_fips'] or r['state']): r for r in rows81}
    eq = diff = 0
    msgs = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        hdr = [str(x).replace('*', '') if x is not None else '' for x in rows[6]]
        years = [int(hdr[1]) if hdr[1].strip().isdigit() else None,
                 int(hdr[5]) if len(hdr) > 5 and hdr[5].strip().isdigit() else None]
        instate = False
        for row in rows[7:]:
            lab = clean_label(row[0] or '')
            if lab == 'STATES':
                instate = True
            if not instate:
                continue
            nm = re.sub(r'\s*/\d$', '', lab).strip()
            if nm not in STATE_FIPS:
                continue
            for k, y in enumerate(years):
                if not y:
                    continue
                fb = parse_num(row[3 + 4 * k])
                key = (y, STATE_FIPS[nm])
                if key not in idx:
                    alt = [r for r in rows81 if r['year'] == y and nm in r['state']]
                    if not alt:
                        continue
                    r81 = alt[0]
                else:
                    r81 = idx[key]
                if fb == r81['foreign_born']:
                    eq += 1
                else:
                    diff += 1
                    msgs.append('WP29 T13 vs WP81 T14 %s %s FB: %s vs %s' % (nm, y, fb, r81['foreign_born']))
    return ['WP29 T13 vs WP81 T14 foreign-born: %d equal, %d differ' % (eq, diff)] + msgs


def find_var(labels, want):
    hits = [n for n, p in labels.items() if p == want]
    assert len(hits) == 1, (want, hits)
    return hits[0]


def acs_totals():
    out, us = [], {}
    for year in range(2005, 2025):
        if year == 2020:
            continue
        if year <= 2009:
            labels = acs_read.load_groups(os.path.join(RAW, 'acs_sf_2005_2009',
                                                       'groups_acs1_%d_B05002.json' % year), 'B05002')
            vt, vf = find_var(labels, ()), find_var(labels, ('Foreign born',))
            recs = acs_read.load_sf_table(year, 'B05002')
            for d, rec in recs.items():
                st = rec['stusab']
                name = 'United States' if st == 'US' else None
                fips = None
                for nm, f in STATE_FIPS.items():
                    pass
                if st == 'US':
                    us[year] = (rec['E'][vt], rec['E'][vf])
                    continue
                name = STUSAB2NAME[st]
                out.append(dict(year=year, state=name, state_fips=STATE_FIPS[name],
                                total_pop=rec['E'][vt], foreign_born=rec['E'][vf],
                                source_id='acs1_sf_b05002'))
        else:
            labels = acs_read.load_groups(os.path.join(RAW, 'acs1_api', 'groups_acs1_%d_B05002.json' % year),
                                          'B05002')
            vt, vf = find_var(labels, ()), find_var(labels, ('Foreign born',))
            d = acs_read.load_api_table(os.path.join(RAW, 'acs1_api', 'ACSDT1Y%d_B05002_states.json' % year),
                                        'B05002')
            n = acs_read.load_api_table(os.path.join(RAW, 'acs1_api', 'ACSDT1Y%d_B05002_us.json' % year),
                                        'B05002')
            us[year] = (n['0100000US']['E'][vt], n['0100000US']['E'][vf])
            for geo, rec in d.items():
                fips = geo[-2:]
                out.append(dict(year=year, state=rec['name'], state_fips=fips,
                                total_pop=rec['E'][vt], foreign_born=rec['E'][vf],
                                source_id='acs1_api_b05002'))
    # 2020 experimental
    wb = openpyxl.load_workbook(os.path.join(RAW, 'acs1_2020_experimental', 'XK200503.xlsx'), read_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    hdr = rows[6]
    tot_row = [r for r in rows if r[0] and str(r[0]).strip() == 'Total:'][0]
    fb_row = [r for r in rows if r[0] and str(r[0]).strip() == 'Foreign born'][0]
    for c in range(1, len(hdr), 2):
        name = hdr[c]
        if not name:
            continue
        tot = int(str(tot_row[c]).replace(',', '').strip())
        fb = int(str(fb_row[c]).replace(',', '').strip())
        if name == 'United States':
            us[2020] = (tot, fb)
            continue
        out.append(dict(year=2020, state=name, state_fips=STATE_FIPS[name], total_pop=tot,
                        foreign_born=fb, source_id='acs1_2020_experimental_xk200503'))
    return out, us


STUSAB = {'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
          'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia',
          'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
          'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
          'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
          'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
          'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
          'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
          'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
          'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia',
          'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
          'PR': 'Puerto Rico'}
STUSAB2NAME = STUSAB


def main():
    wp, us_wp = wp81_t14()
    acs, us_acs = acs_totals()
    rows = wp + acs
    rows.sort(key=lambda r: (r['year'], r['state_fips'] or 'zz', r['state']))
    os.makedirs(PROC, exist_ok=True)
    fn = os.path.join(PROC, 'stock_state_totals.csv')
    with open(fn, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['year', 'state', 'state_fips', 'total_pop', 'foreign_born',
                                          'source_id'])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('wrote', fn, len(rows))
    us = dict(us_wp)
    us.update(us_acs)
    print('year n_states sum_states_total us_total sum_states_fb us_fb diff_fb')
    for y in sorted(set(r['year'] for r in rows)):
        sub = [r for r in rows if r['year'] == y and r['state_fips'] != '72']
        st = sum(r['total_pop'] or 0 for r in sub)
        sf = sum(r['foreign_born'] or 0 for r in sub)
        ut, uf = us.get(y, (None, None))
        print(y, len(sub), st, ut, sf, uf, (sf - uf) if uf is not None else '')
    for m in wp29_t13_check(wp)[:30]:
        print(m)


if __name__ == '__main__':
    main()
