"""Fetch CPS basic monthly public-use microdata (fixed-width .dat.gz) and keep only small
aggregates of the foreign-born population by country of birth.

Source: U.S. Census Bureau / BLS, Current Population Survey, basic monthly public-use files,
  https://www2.census.gov/programs-surveys/cps/datasets/<year>/basic/<mon><yy>pub.dat.gz
Record layout (variable positions, implied decimals) is parsed from that year's
  <year>_Basic_CPS_Public_Use_Record_Layout_plus_IO_Code_list.txt (same folder), so a position
  change between years is picked up instead of silently misreading columns.

The microdata (~9-10 MB compressed, ~120 MB uncompressed per month) are downloaded to a temporary
directory, aggregated, and deleted. Only these files are written (git-ignored raw folder):
  data/raw/census_cps_basic/aggregates/<yyyy>_<mm>_by_penatvty.csv
      year,month,penatvty,prcitshp_group,hrmis,n_records,w_pwsswgt,n_civ16,w_pwsswgt_civ16,w_pwcmpwgt
      (hrmis = month-in-sample 1-8, kept so that rotation groups can serve as random groups for
       approximate standard errors)
      (prcitshp_group: native_us (1), native_island (2), native_abroad (3), fb_naturalized (4),
       fb_noncitizen (5))
  data/raw/census_cps_basic/aggregates/<yyyy>_<mm>_fb_by_entry.csv
      year,month,prinuyer,w_pwsswgt,n_records     (foreign born = PRCITSHP 4,5)
  data/raw/census_cps_basic/aggregates/manifest.csv   one row per month: url, bytes, sha256,
      records read, person records, sum of weights

Weights: PWSSWGT and PWCMPWGT carry 4 implied decimal places (layout text); divided by 10,000.
Usage:  python3 -I scripts/recent/cps_fetch_aggregate.py [YYYY-MM ...]   (default: all months
        listed in the 2024-2026 directory listings)
"""
import csv, gzip, hashlib, io, os, re, subprocess, sys, tempfile, zipfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'data', 'raw', 'census_cps_basic')
AGG = os.path.join(RAW, 'aggregates')
LAY = os.path.join(RAW, 'layouts')
BASE = 'https://www2.census.gov/programs-surveys/cps/datasets/{y}/basic/'
MON = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
VARS = ['HRMONTH', 'HRYEAR4', 'HRMIS', 'PRTAGE', 'PRPERTYP', 'PENATVTY', 'PRCITSHP', 'PRINUYER',
        'PWSSWGT', 'PWCMPWGT']
CIT = {1: 'native_us', 2: 'native_island', 3: 'native_abroad', 4: 'fb_naturalized',
       5: 'fb_noncitizen'}


def curl(url, out=None):
    cmd = ['curl', '-sS', '-f', '-L', '--retry', '4', '--retry-delay', '10', '-m', '900']
    if out:
        cmd += ['-o', out]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise RuntimeError(f'curl failed {url}: {r.stderr.decode()[:300]}')
    return r.stdout


def layout(year):
    """Parse NAME SIZE DESCRIPTION START-END lines of the year's record layout."""
    fn = os.path.join(LAY, f'{year}_Basic_CPS_Public_Use_Record_Layout_plus_IO_Code_list.txt')
    if not os.path.exists(fn):
        os.makedirs(LAY, exist_ok=True)
        curl(BASE.format(y=year) + os.path.basename(fn), fn)
    txt = open(fn, encoding='latin-1').read()
    pos = {}
    for v in VARS:
        m = re.search(r'^' + v + r'\s+(\d+)\s.*?(\d+)\s*\D{0,3}?\s*(\d+)\s*$', txt, re.M)
        if not m:
            raise SystemExit(f'{v} not found in {fn}')
        size, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if b - a + 1 != size:
            raise SystemExit(f'{v}: size {size} != {a}-{b} in {fn}')
        pos[v] = (a - 1, b)
    # implied decimals stated in the layout for both weights
    for v in ('PWSSWGT', 'PWCMPWGT'):
        i = re.search(r'^' + v + r'\s', txt, re.M).start()
        if '4 IMPLIED DECIMAL' not in ' '.join(txt[i:i + 400].upper().split()):
            raise SystemExit(f'{v}: "4 implied decimal" not found next to definition in {fn}')
    return pos


def months_listed(year):
    html = curl(BASE.format(y=year)).decode('utf-8', 'replace')
    got = sorted(set(re.findall(r'href="([a-z]{3})(\d\d)pub\.dat\.gz"', html)))
    return sorted((year, MON.index(m) + 1) for m, yy in got if int(yy) == year % 100)


def aggregate(year, month, pos, tmpdir, manifest):
    name = f'{MON[month - 1]}{year % 100:02d}pub.dat.gz'
    url = BASE.format(y=year) + name
    out1 = os.path.join(AGG, f'{year}_{month:02d}_by_penatvty.csv')
    out2 = os.path.join(AGG, f'{year}_{month:02d}_fb_by_entry.csv')
    if os.path.exists(out1) and os.path.exists(out2) and any(r['file'] == name for r in manifest):
        print('have', name)
        return
    fn = os.path.join(tmpdir, name)
    curl(url, fn)
    sha = hashlib.sha256(open(fn, 'rb').read()).hexdigest()
    nbytes = os.path.getsize(fn)
    g = lambda line, v: line[pos[v][0]:pos[v][1]]
    by = defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0])
    entry = defaultdict(lambda: [0.0, 0])
    nrec = nper = 0
    wsum = 0.0
    bad_month = 0
    with open(fn, 'rb') as fh:
        magic = fh.read(2)
    if magic == b'PK':   # e.g. jan24pub.dat.gz is actually a zip archive holding one .dat file
        zf = zipfile.ZipFile(fn)
        members = [i for i in zf.infolist() if not i.is_dir()]
        if len(members) != 1:
            raise SystemExit(f'{name}: zip with {len(members)} members')
        print(f'note: {name} is a zip archive ({members[0].filename})', flush=True)
        src = io.TextIOWrapper(zf.open(members[0]), encoding='latin-1')
    else:
        src = gzip.open(fn, 'rt', encoding='latin-1')
    with src as f:
        for line in f:
            nrec += 1
            try:
                pt = int(g(line, 'PRPERTYP'))
            except ValueError:
                continue
            if pt not in (1, 2, 3):
                continue
            if int(g(line, 'HRMONTH')) != month or int(g(line, 'HRYEAR4')) != year:
                bad_month += 1
            w = int(g(line, 'PWSSWGT')) / 10000.0
            if w <= 0:
                continue
            nper += 1
            wsum += w
            nat = int(g(line, 'PENATVTY'))
            cit = int(g(line, 'PRCITSHP'))
            age = int(g(line, 'PRTAGE'))
            wc = int(g(line, 'PWCMPWGT')) / 10000.0
            k = (nat, CIT.get(cit, f'code_{cit}'), int(g(line, 'HRMIS')))
            r = by[k]
            r[0] += 1
            r[1] += w
            if pt == 2 and age >= 16:
                r[2] += 1
                r[3] += w
                r[4] += max(wc, 0.0)
            if cit in (4, 5):
                e = entry[int(g(line, 'PRINUYER'))]
                e[0] += w
                e[1] += 1
    os.remove(fn)
    if bad_month:
        raise SystemExit(f'{name}: {bad_month} records with HRMONTH/HRYEAR4 != {month}/{year}')
    with open(out1, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['year', 'month', 'penatvty', 'prcitshp_group', 'hrmis', 'n_records',
                     'w_pwsswgt', 'n_civ16', 'w_pwsswgt_civ16', 'w_pwcmpwgt'])
        for (nat, cg, mis), r in sorted(by.items()):
            wr.writerow([year, month, f'{nat:03d}', cg, mis, r[0], f'{r[1]:.4f}', r[2],
                         f'{r[3]:.4f}', f'{r[4]:.4f}'])
    with open(out2, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['year', 'month', 'prinuyer', 'w_pwsswgt', 'n_records'])
        for k, (w, n) in sorted(entry.items()):
            wr.writerow([year, month, k, f'{w:.4f}', n])
    manifest.append({'year': year, 'month': month, 'file': name, 'url': url, 'bytes': nbytes,
                     'sha256': sha, 'records': nrec, 'person_records_w_gt0': nper,
                     'sum_pwsswgt': f'{wsum:.0f}'})
    print(f'{name}: {nrec} records, {nper} persons, sum PWSSWGT {wsum:,.0f}', flush=True)


def main():
    os.makedirs(AGG, exist_ok=True)
    mpath = os.path.join(AGG, 'manifest.csv')
    manifest = list(csv.DictReader(open(mpath))) if os.path.exists(mpath) else []
    if len(sys.argv) > 1:
        todo = [(int(a[:4]), int(a[5:7])) for a in sys.argv[1:]]
    else:
        todo = [ym for y in (2024, 2025, 2026) for ym in months_listed(y)]
    print('months:', ' '.join(f'{y}-{m:02d}' for y, m in todo), flush=True)
    lay = {}
    with tempfile.TemporaryDirectory(prefix='cps_') as tmp:
        for y, m in todo:
            if y not in lay:
                lay[y] = layout(y)
                if y != 2024 and lay[y] != lay.get(2024, lay[y]):
                    print(f'note: layout positions for {y} differ from 2024: {lay[y]}')
            aggregate(y, m, lay[y], tmp, manifest)
            manifest.sort(key=lambda r: (int(r['year']), int(r['month'])))
            with open(mpath, 'w', newline='') as f:
                wr = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
                wr.writeheader()
                wr.writerows(manifest)


if __name__ == '__main__':
    main()
