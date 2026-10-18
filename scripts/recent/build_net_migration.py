"""Build data/processed/net_migration_recent.csv  (period,series,value,low,high,source_id,note)

* Census Bureau Vintage 2024 and Vintage 2025 national components of change
  (NST-EST2024-ALLDATA.csv / NST-EST2025-ALLDATA.csv, US row, INTERNATIONALMIG<year>).
  Estimate year <y> = July 1 of y-1 to June 30 of y; 2020 = April 1 - June 30, 2020.
* Census Bureau V2025 projection for July 1, 2025 - June 30, 2026 ("approximately 321,000"),
  stated in press release CB26-20 and the Random Samplings blog of Jan 27, 2026 (saved HTML in
  data/raw/census_newsroom/; the number is read from the saved text, not typed in).
* CBO, The Demographic Outlook: 2026 to 2056 (Jan 2026), net immigration, calendar years
  2025 and 2026 (Social Security area population concept), read from the PDF text.
* Brookings/AEI (Edelberg, Veuger, Watson, Jan 13 2026): likely range for calendar 2025 and 2026.
Run: python3 -I scripts/recent/build_net_migration.py
"""
import csv, html, os, re, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'data', 'processed', 'net_migration_recent.csv')


def text_of_html(fn):
    s = open(fn, encoding='utf-8', errors='replace').read()
    s = re.sub(r'<(script|style).*?</\1>', '', s, flags=re.S)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)))


def num(s):
    s = s.replace('–', '-').replace('−', '-').replace('–', '-').replace(',', '').strip()
    return int(s)


def period(y):
    return '2020-04-01/2020-06-30' if y == 2020 else f'{y - 1}-07-01/{y}-06-30'


def main():
    rows = []
    for vint, fn in ((2024, 'NST-EST2024-ALLDATA.csv'), (2025, 'NST-EST2025-ALLDATA.csv')):
        us = next(r for r in csv.DictReader(open(os.path.join(RAW, 'census_popest', fn),
                                                 encoding='latin-1')) if r['NAME'] == 'United States')
        for y in range(2020, vint + 1):
            note = ('April 1 - June 30, 2020 only (estimates base to first July 1)' if y == 2020
                    else 'estimate year July 1 - June 30')
            note += f'; natural change {int(us[f"NATURALCHG{y}"]):,}; total change {int(us[f"NPOPCHG_{y}"]):,}'
            rows.append([period(y), f'census_v{vint}_nim', int(us[f'INTERNATIONALMIG{y}']), '', '',
                         f'census_popest_v{vint}', note])
    # Census V2025 projection for 2026
    t = text_of_html(os.path.join(RAW, 'census_newsroom', 'population-growth-slows.html'))
    m = re.search(r'net international migration is projected to be approximately ([\d,]+) by July 2026', t)
    assert m, 'projection sentence not found in press release'
    t2 = text_of_html(os.path.join(RAW, 'census_newsroom',
                                   'rs_historic-decline-in-net-international-migration.html'))
    m2 = re.search(r'projected to further decline to approximately ([\d,]+) in 2026', t2)
    assert m2 and num(m2.group(1)) == num(m.group(1))
    rows.append([period(2026), 'census_v2025_nim_projection', num(m.group(1)), '', '',
                 'census_v2025_press_release',
                 'short-term projection "if current trends continue" (July 1, 2025 - June 30, 2026); '
                 'emigration assumed to double from 2025; feeds the CPS 2026 population controls'])
    # CBO January 2026
    pdf = os.path.join(RAW, 'cbo_demographic_outlook_2026', '61879-Demographic-Outlook.pdf')
    cbo = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    cbo = re.sub(r'\s+', ' ', cbo)
    m = re.search(r'CBO now projects net immigration of ([\d,]+) people \(instead of [\d.]+ mil- ?lion\) '
                  r'in 2025, ([\d,]+) \(instead of [\d.]+ million\) in 2026', cbo)
    assert m, 'CBO sentence not found'
    for y, v in ((2025, m.group(1)), (2026, m.group(2))):
        rows.append([f'{y}-01-01/{y}-12-31', 'cbo_jan2026_net_immigration', num(v), '', '',
                     'cbo_demographic_outlook_2026',
                     'calendar year; Social Security area population concept (includes U.S. citizens '
                     'abroad); 2025 is a CBO estimate, 2026 a projection'])
    # Brookings / AEI January 2026
    b = text_of_html(os.path.join(RAW, 'brookings_immigration_2026',
                                  'macroeconomic-implications-of-immigration-flows-in-2025-and-2026-'
                                  'january-2026-update.html'))
    m25 = re.search(r'net immigration likely ranged between ([–\-−]?[\d,]+) and ([–\-−]?[\d,]+) for 2025', b)
    m26 = re.search(r'For 2026, we project that net immigration will likely range between '
                    r'([–\-−]?[\d,]+) and \+?([–\-−]?[\d,]+)', b)
    assert m25 and m26, 'Brookings sentences not found'
    for y, mm, kind in ((2025, m25, 'estimate'), (2026, m26, 'projection')):
        lo, hi = sorted((num(mm.group(1)), num(mm.group(2))))
        rows.append([f'{y}-01-01/{y}-12-31', 'brookings_aei_jan2026_net_migration', '', lo, hi,
                     'brookings_aei_2026', f'calendar year; likely range ({kind}); low- and '
                     'high-immigration scenarios; no central value published'])
    with open(OUT, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['period', 'series', 'value', 'low', 'high', 'source_id', 'note'])
        w.writerows(rows)
    print(f'wrote {OUT}: {len(rows)} rows')
    for r in rows:
        print('  ', r[0], r[1], r[2], r[3], r[4])


if __name__ == '__main__':
    main()
