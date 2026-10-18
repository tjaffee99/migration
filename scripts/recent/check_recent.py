"""Checks and validation figures for the 2024-2026 files (quoted in data/processed/recent_NOTES.md).
Run: python3 -I scripts/recent/check_recent.py   (exit code 1 on any failed invariant)"""
import csv, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(ROOT, 'data', 'processed')
RAW = os.path.join(ROOT, 'data', 'raw')
FAIL = []


def rd(name):
    return list(csv.DictReader(open(os.path.join(P, name))))


def tree_check(blocks, name, tol):
    for key, rows in blocks.items():
        labs = [(r['origin_label'], r['level']) for r in rows]   # 'Unknown' is both a region and
        if len(labs) != len(set(labs)):                           # its own residual (DHS convention)
            FAIL.append(f'{name} {key}: duplicate labels')
        val = {r['origin_label']: int(r['count']) for r in rows if r['count'] != ''}
        tot = [int(r['count']) for r in rows if r['level'] == 'total']
        leaf = sum(int(r['count']) for r in rows if r['level'] in ('country', 'residual'))
        if len(tot) != 1 or abs(leaf - tot[0]) > tol:
            FAIL.append(f'{name} {key}: countries+residuals {leaf} vs total {tot}')
        if any(int(r['count']) < 0 for r in rows):
            FAIL.append(f'{name} {key}: negative count')
        for r in rows:
            if r['parent_label'] and r['parent_label'] not in val:
                FAIL.append(f'{name} {key}: parent {r["parent_label"]} missing')
        kids = defaultdict(int)
        for r in rows:
            if r['parent_label'] and not (r['level'] == 'residual' and r['origin_label'] == r['parent_label']):
                kids[(r['parent_label'], r['level'] == 'subcountry')] += int(r['count'])
        worst = 0
        for (p, sub), s in kids.items():
            worst = max(worst, abs(val[p] - s))
        if worst > tol:
            FAIL.append(f'{name} {key}: parent/children gap {worst}')
    return len(blocks)


def main():
    src = {r['source_id'] for r in rd('sources_recent.csv')}
    # ---- flows
    fl = rd('flows_recent_by_birth.csv')
    blocks = defaultdict(list)
    for r in fl:
        blocks[(r['period_start'], r['basis'])].append(r)
    n = tree_check(blocks, 'flows', tol=200)   # cells rounded to 10 by OHSS
    print(f'flows_recent_by_birth: {len(fl)} rows, {n} periods; source ids ok: '
          f'{all(r["source_id"] in src for r in fl)}')
    for (y, b), rows in sorted(blocks.items()):
        t = next(int(r['count']) for r in rows if r['level'] == 'total')
        top = sorted(((int(r['count']), r['origin_label']) for r in rows if r['level'] == 'country'),
                     reverse=True)[:8]
        print(f'  FY{y} {b}: total {t:,}; top: ' + ', '.join(f'{l} {c:,}' for c, l in top))
    yb = {(r['period_start'], r['origin_label']): int(r['count']) for r in rd('flows_by_birth_1989_present.csv')
          if r['period_start'] == '2023' and r['count']}
    t24 = next(int(r['count']) for r in fl if r['period_start'] == '2024' and r['level'] == 'total')
    print(f'  FY2024 preliminary {t24:,} vs FY2023 final {yb[("2023", "Total")]:,} '
          f'({100 * (t24 / yb[("2023", "Total")] - 1):+.1f}%)')
    tot = rd('flows_recent_totals.csv')
    q = {(r['fiscal_year'], r['quarters']): int(r['lpr_total']) for r in tot}
    print(f'  FY2025 Q1 {q[("2025", "Q1")]:,} vs FY2024 Q1 {q[("2024", "Q1")]:,} '
          f'({100 * (q[("2025", "Q1")] / q[("2024", "Q1")] - 1):+.1f}%)')
    # ---- stock
    st = rd('stock_recent_by_country.csv')
    blocks = defaultdict(list)
    for r in st:
        blocks[(r['year'], r['months'], r['source_id'])].append(r)
    n = tree_check(blocks, 'stock', tol=60)
    print(f'stock_recent_by_country: {len(st)} rows, {n} blocks; source ids ok: '
          f'{all(r["source_id"] in src for r in st)}')
    acs = {r['origin_label']: int(r['count']) for r in rd('stock_national_by_country.csv')
           if r['year'] == '2024'}
    ann = {(r['year'], r['origin_label']): int(r['count']) for r in st
           if r['source_id'] == 'cps_basic_annual_avg'}
    mon = {(int(r['year']), int(r['months'])): int(r['count']) for r in st
           if r['source_id'] == 'cps_basic_monthly' and r['level'] == 'total'}
    for y in ('2024', '2025', '2026'):
        print(f'  CPS {y} annual average foreign born: {ann[(y, "Total")]:,}')
    print(f'  CPS 2024 / ACS 2024 ({acs["Total"]:,}) = {ann[("2024", "Total")] / acs["Total"]:.4f}')
    print(f'  CPS Jan 2025 {mon[(2025, 1)]:,} and Jun 2025 {mon[(2025, 6)]:,} '
          f'(Pew Aug 2025 / Census blog: 53.3M and 51.9M)')
    peak = max(mon.items(), key=lambda kv: kv[1])
    print(f'  CPS peak month {peak[0][1]:02d}/{peak[0][0]} {peak[1]:,}; latest 09/2026 {mon[(2026, 9)]:,}')
    print(f'  Dec 2024 -> Jan 2025 {mon[(2025, 1)] - mon[(2024, 12)]:+,}; '
          f'Dec 2025 -> Jan 2026 {mon[(2026, 1)] - mon[(2025, 12)]:+,} (population-control breaks)')
    print(f'  Jan-Sep 2026 vs Jan-Sep 2025 mean: '
          f'{sum(mon[(2026, m)] for m in range(1, 10)) / 9 - sum(mon[(2025, m)] for m in range(1, 10)) / 9:+,.0f}')
    # ---- population
    pop = rd('us_population_annual.csv')
    yrs = [int(r['year']) for r in pop]
    ok = yrs == list(range(1790, 1900, 10)) + list(range(1900, 2027))
    if not ok:
        FAIL.append('us_population years')
    if not all(r['source_id'] in src for r in pop):
        FAIL.append('us_population source ids')
    v = {int(r['year']): int(r['population']) for r in pop}
    dec = [y for y in range(1901, 2027) if v[y] < v[y - 1]]
    print(f'us_population_annual: {len(pop)} rows {yrs[0]}-{yrs[-1]}; years ok {ok}; '
          f'year-on-year declines: {dec}')
    print(f'  2024 {v[2024]:,}  2025 {v[2025]:,}  2026 {v[2026]:,}')
    # ---- net migration
    nm = rd('net_migration_recent.csv')
    if not all(r['source_id'] in src for r in nm):
        FAIL.append('net_migration source ids')
    print(f'net_migration_recent: {len(nm)} rows; series: {sorted({r["series"] for r in nm})}')
    if FAIL:
        print('FAILED:\n  ' + '\n  '.join(FAIL))
        sys.exit(1)
    print('all checks passed')


if __name__ == '__main__':
    main()
