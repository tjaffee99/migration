"""Build the FY2024+ LPR ("legal arrivals") files from the archived OHSS quarterly reports.

  data/processed/flows_recent_by_birth.csv   same columns as flows_by_birth_1989_present.csv
  data/processed/flows_recent_totals.csv     national totals by fiscal year and quarter

Source: OHSS "Legal Immigration and Adjustment of Status Report" (LIAS) quarterly workbooks,
Table 1A "Persons obtaining lawful permanent resident status by type of admission and region and
country of NATIONALITY" (Total / Adjustments of status / New arrivals, each by quarter). The
live site blocks this environment; the files are Archive-It captures (see the .memento files in
data/raw/archiveit_ohss_recent/ and scripts/recent/fetch_recent.sh).

IMPORTANT: the LIAS tables are by country of NATIONALITY, preliminary (data one month after the
quarter), and rounded to the nearest 10. The final FY2024 Yearbook tables by country of BIRTH
(posted by OHSS in June 2026) have no archived copy. Rows are flagged in `basis`:
  preliminary_annual_nationality    FY2024: all four quarters (Oct 2023 - Sep 2024)
  preliminary_partial_q1_nationality FY2025: first quarter only (Oct - Dec 2024)
Region parents: the same lookup as the existing birth file (country -> region of the FY2023 rows
of flows_by_birth_1989_present.csv), plus Kiribati -> Oceania.
Run: python3 -I scripts/recent/build_flows_recent.py
"""
import csv, os
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'data', 'raw', 'archiveit_ohss_recent')
PROC = os.path.join(ROOT, 'data', 'processed')
FILES = [  # fiscal year, workbook, source_id, quarters published
    (2023, 'lias_fy2023q4.xlsx', 'ohss_lias_fy2023q4', 4),
    (2024, 'lias_fy2024q4.xlsx', 'ohss_lias_fy2024q4', 4),
    (2025, 'lias_fy2025q1.xlsx', 'ohss_lias_fy2025q1', 1),
]
EXTRA_PARENT = {'Kiribati': 'Oceania'}


def read_table1a(fn):
    ws = openpyxl.load_workbook(fn, read_only=True, data_only=True)['Table 1A']
    rows = list(ws.iter_rows(values_only=True))
    hdr = next(i for i, r in enumerate(rows) if r[0] and str(r[0]).startswith('Region and country'))
    top, sub = rows[hdr], rows[hdr + 1]
    blocks = {}
    cur = None
    for j, v in enumerate(top):
        if v:
            cur = v.strip()
        if cur and j > 0:
            blocks.setdefault(cur, {})[sub[j]] = j
    assert set(blocks) == {'Total', 'Adjustments of status', 'New arrivals'}, blocks.keys()
    out, sec = {'REGION': [], 'COUNTRY': []}, None
    source_note = ''
    for r in rows[hdr + 2:]:
        a = r[0]
        if a in ('REGION', 'COUNTRY'):
            sec = a
            continue
        if isinstance(a, str) and a.startswith('Source'):
            source_note = a
        if not sec or not isinstance(a, str) or r[1] is None or a.startswith(('1 ', 'Note', 'Source')):
            continue
        rec = {b: {q: r[j] for q, j in cols.items()} for b, cols in blocks.items()}
        out[sec].append((a.strip(), rec))
    return out, source_note


def label(a):
    return 'All other countries' if a.startswith('All other countries') else a


def main():
    parent = {r['origin_label']: r['parent_label']
              for r in csv.DictReader(open(os.path.join(PROC, 'flows_by_birth_1989_present.csv')))
              if r['period_start'] == '2023' and r['level'] == 'country'}
    parent.update(EXTRA_PARENT)
    yb23 = {r['origin_label']: int(r['count']) for r in csv.DictReader(
        open(os.path.join(PROC, 'flows_by_birth_1989_present.csv')))
        if r['period_start'] == '2023' and r['count']}
    rows, totals, parsed = [], [], {}
    for fy, fn, sid, nq in FILES:
        t, src = read_table1a(os.path.join(RAW, fn))
        parsed[fy] = t
        print(f'FY{fy} {fn}: {len(t["COUNTRY"])} country rows; {src}')
        reg_total = dict((a, rec) for a, rec in t['REGION'])
        tot = reg_total['Total']
        for q in ('Quarter 1', 'Quarter 2', 'Quarter 3', 'Quarter 4', 'Total'):
            if tot['Total'][q] is None or (q == 'Total' and nq == 1):
                continue
            totals.append([fy, q.replace('Quarter ', 'Q') if q != 'Total' else
                           ('Q1-Q4' if nq == 4 else f'Q1-Q{nq}'),
                           tot['Total'][q], tot['Adjustments of status'][q],
                           tot['New arrivals'][q],
                           'preliminary_nationality_rounded10', sid])
        if fy == 2023:
            continue   # FY2023 is already in flows_by_birth (final, by birth); used for checks only
        basis = ('preliminary_annual_nationality' if nq == 4 else
                 f'preliminary_partial_q1_q{nq}_nationality' if nq > 1 else
                 'preliminary_partial_q1_nationality')
        col = 'Total'   # year-to-date total of the quarters published
        rows.append([fy, fy, 'Total', 'total', '', tot['Total'][col], basis, sid])
        for a, rec in t['REGION']:
            if a != 'Total':
                rows.append([fy, fy, a, 'region', 'Total', rec['Total'][col], basis, sid])
        for a, rec in t['COUNTRY']:
            if a == 'Total':
                assert rec['Total'][col] == tot['Total'][col]
                continue
            lab = label(a)
            if lab == 'All other countries':
                rows.append([fy, fy, lab, 'residual', 'Total', rec['Total'][col], basis, sid])
            elif lab == 'Unknown':
                rows.append([fy, fy, lab, 'residual', 'Unknown', rec['Total'][col], basis, sid])
            else:
                rows.append([fy, fy, lab, 'country', parent[lab], rec['Total'][col], basis, sid])
    # checks: leaf sums vs total (rounded cells), region sums
    for fy in (2024, 2025):
        blk = [r for r in rows if r[0] == fy]
        tot = next(r[5] for r in blk if r[3] == 'total')
        leaf = sum(r[5] for r in blk if r[3] in ('country', 'residual'))
        regs = {r[2]: r[5] for r in blk if r[3] == 'region'}
        print(f'FY{fy}: total {tot:,}; countries+residuals {leaf:,} ({leaf - tot:+,}); '
              f'regions {sum(regs.values()):,}')
        for reg, v in regs.items():
            s = sum(r[5] for r in blk if r[3] in ('country', 'residual') and r[4] == reg)
            print(f'    {reg:15s} {v:9,} children {s:9,} ({s - v:+,})')
    with open(os.path.join(PROC, 'flows_recent_by_birth.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['period_start', 'period_end', 'origin_label', 'level', 'parent_label', 'count',
                    'basis', 'source_id'])
        w.writerows(rows)
    with open(os.path.join(PROC, 'flows_recent_totals.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['fiscal_year', 'quarters', 'lpr_total', 'adjustments_of_status',
                    'new_arrivals', 'basis', 'source_id'])
        w.writerows(totals)
    print(f'wrote flows_recent_by_birth.csv ({len(rows)} rows), flows_recent_totals.csv '
          f'({len(totals)} rows)')
    # FY2023 calibration: preliminary LIAS by nationality vs final Yearbook by birth
    t23 = dict((a, rec['Total']['Total']) for a, rec in parsed[2023]['COUNTRY'])
    print(f'FY2023 LIAS total (nationality, preliminary) {t23["Total"]:,} vs Yearbook total '
          f'(birth, final) {yb23["Total"]:,} ({t23["Total"] - yb23["Total"]:+,})')
    diffs = sorted(((t23[a] - yb23[a], a) for a in t23 if a in yb23 and a != 'Total'),
                   key=lambda x: -abs(x[0]))
    print('  largest nationality-minus-birth gaps FY2023:',
          '; '.join(f'{a} {d:+,} (birth {yb23[a]:,})' for d, a in diffs[:12]))
    top = sorted(((yb23[a], a) for a in t23 if a in yb23 and a not in ('Total', 'Unknown')),
                 reverse=True)[:20]
    print('  top-20 birth countries, |nationality/birth - 1| max: '
          f'{max(abs(t23[a] / v - 1) for v, a in top):.3f}; median '
          f'{sorted(abs(t23[a] / v - 1) for v, a in top)[10]:.3f}')


if __name__ == '__main__':
    main()
