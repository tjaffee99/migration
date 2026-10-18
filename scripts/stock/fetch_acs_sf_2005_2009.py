#!/usr/bin/env python3
"""Fetch ACS 1-year Summary File (sequence-based) pieces for 2005-2009, which are not
available from the data.census.gov table API.

For each year, for the nation and each state (+DC, PR), downloads the zipped sequence
files holding B05002 and B05006, plus the first bytes of the geography file (to verify
that LOGRECNO 0000001 is the summary-level 040/010 record).  Sequence numbers come from
the Census sequence/table lookup files saved in data/raw/acs_sf_2005_2009/.

Usage: python3 -I scripts/stock/fetch_acs_sf_2005_2009.py
"""
import os, re, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'data', 'raw', 'acs_sf_2005_2009')
BASE = 'https://www2.census.gov/programs-surveys/acs/summary_file'
# (B05002 seq, B05006 seq) from the lookup files (Chapter_5_tables_summary_list.xls,
# merge_5_6_final.txt/.xls, merge_5_6.xls/.txt)
SEQ = {2005: (11, 12), 2006: (20, 22), 2007: (23, 25), 2008: (23, 25), 2009: (23, 25)}
DATADIR = {2005: 'data', 2006: 'data', 2007: 'data/1_year', 2008: 'data/1_year',
           2009: 'data/1_year_seq_by_state'}


def curl(args, retries=4):
    for a in range(retries):
        r = subprocess.run(['curl', '-sS', '-f', '-m', '600'] + args, capture_output=True)
        if r.returncode == 0:
            return r.stdout
        time.sleep(5 * (a + 1))
    raise RuntimeError('curl failed: %s %s' % (args, r.stderr.decode()[:300]))


def listing(url):
    html = curl([url]).decode('utf-8', 'replace')
    return re.findall(r'href="([^"?/][^"]*)"', html)


def main():
    for year, (s02, s06) in SEQ.items():
        ydir = os.path.join(OUT, str(year))
        os.makedirs(ydir, exist_ok=True)
        root = '%s/%d/%s/' % (BASE, year, DATADIR[year])
        dirs = [h for h in listing(root) if h.endswith('/') and not h.startswith('http')]
        for d in dirs:
            files = listing(root + d)
            want = []
            for seq in (s02, s06):
                if year == 2005:
                    pat = re.compile(r'^[a-z]{2}%07d\.2005-1yr\.zip$' % seq)
                else:
                    pat = re.compile(r'^%d1[a-z]{2}%04d000\.zip$' % (year, seq))
                m = [f for f in files if pat.match(f)]
                if len(m) != 1:
                    print('WARN', year, d, seq, m, file=sys.stderr)
                want += m
            geo = [f for f in files if re.match(r'^(g%d1[a-z]{2}\.txt|[a-z]{2}geo\.2005-1yr)$' % year, f)]
            sub = os.path.join(ydir, d.strip('/'))
            os.makedirs(sub, exist_ok=True)
            for f in want:
                dest = os.path.join(sub, f)
                if not os.path.exists(dest):
                    data = curl([root + d + f])
                    open(dest, 'wb').write(data)
            for f in geo:  # only the first 64 KB: enough for the first logical records
                dest = os.path.join(sub, f + '.head')
                if not os.path.exists(dest):
                    data = curl(['-r', '0-65535', root + d + f])
                    open(dest, 'wb').write(data)
            print(year, d, want, geo)


if __name__ == '__main__':
    main()
