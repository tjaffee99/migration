#!/usr/bin/env python3
"""Build data/processed/stock_state_by_country.csv
   (year,state_fips,origin_label,level,parent_label,count,moe,source_id)

  1990       1990 STF4C matrix PA23 extract (region of birth, excl. not reported) for states,
             with the state foreign-born total from WP81 Table 14 and a derived
             "Region or country not reported" residual                 [census1990_stf4c_pa23]
  2000       Decennial 2000 SF3 PCT019 (data.census.gov)               [dec2000_sf3_pct019]
  2005-2009  ACS 1-year summary file B05006                            [acs1_sf_b05006]
  2010-2019, 2021-2024  ACS 1-year B05006 (data.census.gov)            [acs1_api_b05006]
  2020       ACS 5-year 2016-2020 B05006                               [acs5_2016_2020_b05006]
  Where the 1-year B05006 is filtered (suppressed) for a state, the 5-year estimate ending
  in that year is used instead (2010-2024 only)                       [acs5_<y-4>_<y>_b05006]
  1950       foreign-born WHITE by country, 1950 Census Vol. II Pt 1 Table 71 (manual
             transcription, validated by all row/column sums; build_hist_1950_t71.py)
                                                                       [census1950_v2p1_t71]

Every (year, state_fips, source) block satisfies sum(country)+sum(residual) == total.
Usage: python3 -I scripts/stock/build_state_by_country.py
"""
import csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stocklib import Node, build_tree_from_paths, finalize_tree, check_partition, STATE_FIPS, tree_rows  # noqa
import acs_read  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw')
PROC = os.path.join(ROOT, 'data', 'processed')
WARN = []


def acs_year(year):
    out = []
    if year == 2020:
        labels = acs_read.load_groups(os.path.join(RAW, 'acs5_2020', 'groups_acs5_2020_B05006.json'), 'B05006')
        d = acs_read.load_api_table(os.path.join(RAW, 'acs5_2020', 'ACSDT5Y2020_B05006_states.json'), 'B05006')
        for geo, rec in d.items():
            rr = tree_rows(labels, rec['E'], rec['M'], 'acs5_2016_2020_b05006', warn=WARN)
            for r in rr:
                r.update(year=year, state_fips=geo[-2:])
            out += rr
        return out
    if year <= 2009:
        labels = acs_read.load_groups(os.path.join(RAW, 'acs_sf_2005_2009', 'groups_acs1_%d_B05006.json' % year),
                                      'B05006')
        recs = acs_read.load_sf_table(year, 'B05006')
        geo_recs = {}
        for d, rec in recs.items():
            if rec['stusab'] == 'US':
                continue
            from build_state_totals import STUSAB
            geo_recs[STATE_FIPS[STUSAB[rec['stusab']]]] = rec
        sid = 'acs1_sf_b05006'
    else:
        labels = acs_read.load_groups(os.path.join(RAW, 'acs1_api', 'groups_acs1_%d_B05006.json' % year), 'B05006')
        d = acs_read.load_api_table(os.path.join(RAW, 'acs1_api', 'ACSDT1Y%d_B05006_states.json' % year), 'B05006')
        geo_recs = {g[-2:]: r for g, r in d.items()}
        sid = 'acs1_api_b05006'
    five = None
    for fips, rec in sorted(geo_recs.items()):
        if rec['E'].get(1) is None:
            # filtered 1-year table -> 5-year fallback
            if year >= 2010:
                if five is None:
                    l5 = acs_read.load_groups(os.path.join(RAW, 'acs5_api', 'groups_acs5_%d_B05006.json' % year),
                                              'B05006')
                    d5 = acs_read.load_api_table(os.path.join(RAW, 'acs5_api', 'ACSDT5Y%d_B05006_states.json' % year),
                                                 'B05006')
                    five = (l5, {g[-2:]: r for g, r in d5.items()})
                r5 = five[1].get(fips)
                if r5 and r5['E'].get(1) is not None:
                    rr = tree_rows(five[0], r5['E'], r5['M'], 'acs5_%d_%d_b05006' % (year - 4, year), warn=WARN)
                    for r in rr:
                        r.update(year=year, state_fips=fips)
                    out += rr
                    continue
            job = {2007: '2007_3yr', 2008: '2008_3yr', 2009: '2009_5yr'}.get(year)
            if job:
                if five is None:
                    five = acs_read.load_sf_multi(job)
                from build_state_totals import STUSAB
                ab = [k for k, v in STUSAB.items() if STATE_FIPS[v] == fips][0]
                rm = five[0].get(ab)
                if rm and rm['E'].get(1) is not None:
                    assert rm['geo']['sumlevel'] == '040', rm['geo']
                    rr = tree_rows(five[1], rm['E'], rm['M'], five[2], warn=WARN)
                    for r in rr:
                        r.update(year=year, state_fips=fips)
                    out += rr
                    continue
            WARN.append('NOTE %d state %s: 1-year B05006 filtered, no fallback' % (year, fips))
            continue
        rr = tree_rows(labels, rec['E'], rec['M'], sid, warn=WARN)
        for r in rr:
            r.update(year=year, state_fips=fips)
        out += rr
    return out


def dec2000():
    g = json.load(open(os.path.join(RAW, 'dec2000_sf3', 'groups_dec2000sf3_PCT019.json')))['variables']
    labels = {}
    for k, v in g.items():
        m = re.match(r'^PCT019(\d{3})$', k)
        if m:
            labels[int(m.group(1))] = acs_read.label_path(v['label'])
    d = json.load(open(os.path.join(RAW, 'dec2000_sf3', 'DECENNIALSF32000_PCT019_states.json')))['response']['data']
    hdr = d[0]
    out = []
    for row in d[1:]:
        r = dict(zip(hdr, row))
        est = {int(k[6:]): acs_read.to_int(v) for k, v in r.items() if re.match(r'^PCT019\d{3}$', k)}
        rr = tree_rows(labels, est, {}, 'dec2000_sf3_pct019', warn=WARN)
        for x in rr:
            x.update(year=2000, state_fips=r['GEO_ID'][-2:])
        out += rr
    return out


def census1990():
    """STF4C PA23 extract: region of birth of the foreign born excl. not reported."""
    fb = {}
    for r in csv.DictReader(open(os.path.join(PROC, 'stock_state_totals.csv'))):
        if r['year'] == '1990':
            fb[r['state_fips']] = int(r['foreign_born'])
    out = []
    regions = ['Europe', 'Asia', 'Africa', 'Oceania', 'Latin America', 'Northern America']
    for line in open(os.path.join(RAW, 'census1990_other', '90fb-birth.txt'), encoding='latin-1'):
        parts = line.split()
        if len(parts) < 12 or parts[0] != '1' or parts[1] != '04000':
            continue
        fips = parts[2]
        vals = [int(x) for x in parts[3:10]]
        reported, regs = vals[0], vals[1:]
        if sum(regs) != reported:
            WARN.append('1990 %s regions sum %d != reported %d' % (fips, sum(regs), reported))
        total = fb[fips]
        out.append(dict(year=1990, state_fips=fips, origin_label='Total', level='total', parent_label='',
                        count=total, moe='', source_id='census_wp81_t14'))
        for lab, v in zip(regions, regs):
            out.append(dict(year=1990, state_fips=fips, origin_label=lab, level='region',
                            parent_label='Total', count=v, moe='', source_id='census1990_stf4c_pa23'))
            out.append(dict(year=1990, state_fips=fips, origin_label=lab + ', country not specified (derived)',
                            level='residual', parent_label=lab, count=v, moe='',
                            source_id='census1990_stf4c_pa23_derived'))
        out.append(dict(year=1990, state_fips=fips, origin_label='Region or country not reported (derived)',
                        level='residual', parent_label='Total', count=total - reported, moe='',
                        source_id='census1990_stf4c_pa23_derived'))
    return out


def main():
    rows = []
    rows += census1990()
    rows += dec2000()
    for y in range(2005, 2025):
        rows += acs_year(y)
    import build_hist_1950_t71
    rows += build_hist_1950_t71.rows()   # 1950, foreign-born white, manual transcription
    # checks
    blocks = {}
    for r in rows:
        k = (r['year'], r['state_fips'], r['source_id'].replace('_derived', '').replace('census_wp81_t14', 'census1990_stf4c_pa23'))
        blocks.setdefault(k, []).append(r)
    bad = 0
    for k, sub in blocks.items():
        t, p = check_partition(sub)
        if t is not None and t != p:
            bad += 1
            WARN.append('partition mismatch %s: %s vs %s' % (k, t, p))
    fn = os.path.join(PROC, 'stock_state_by_country.csv')
    rows.sort(key=lambda r: (r['year'], r['state_fips']))
    with open(fn, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year', 'state_fips', 'origin_label', 'level', 'parent_label', 'count', 'moe', 'source_id'])
        for r in rows:
            w.writerow([r['year'], r['state_fips'], r['origin_label'], r['level'], r['parent_label'],
                        r['count'], r['moe'], r['source_id']])
    print('wrote', fn, len(rows), 'rows;', len(blocks), 'year-state blocks;', bad, 'partition mismatches')
    # coverage & state-sum vs national check
    nat = {}
    for r in csv.DictReader(open(os.path.join(PROC, 'stock_national_by_country.csv'))):
        if r['level'] == 'total':
            nat[int(r['year'])] = int(r['count'])
    print('year n_states sources sum_state_totals(excl PR) national_total')
    for y in sorted(set(r['year'] for r in rows)):
        sub = [r for r in rows if r['year'] == y and r['level'] == 'total' and r['state_fips'] != '72']
        srcs = sorted(set(r['source_id'] for r in sub))
        print(y, len(sub), ','.join(srcs), sum(r['count'] for r in sub), nat.get(y))
    for w_ in WARN[:60]:
        print('WARN', w_)


if __name__ == '__main__':
    main()
