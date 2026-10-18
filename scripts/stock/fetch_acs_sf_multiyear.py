#!/usr/bin/env python3
"""Fetch ACS multi-year summary-file B05006 sequences used ONLY to fill states whose 1-year
B05006 was filtered (suppressed) in 2007-2009:
  2007 -> 2005-2007 3-year (seq 25, start 7);  2008 -> 2006-2008 3-year (seq 25, start 7);
  2009 -> 2005-2009 5-year (seq 18, start 66).
Lookups: data/raw/acs_sf_2005_2009/2007_3yr_merge_5_6_final.xls, 2008_3yr_merge_5_6.xls,
2009_5yr_Sequence_Number_and_Table_Number_Lookup.txt.
Usage: python3 -I scripts/stock/fetch_acs_sf_multiyear.py
"""
import os, re, subprocess, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'data', 'raw', 'acs_sf_2005_2009')
BASE = 'https://www2.census.gov/programs-surveys/acs/summary_file'
# union of states with filtered 1-year B05006 in 2007-2009 (see build_state_by_country.py)
STATES = {'AK': 'Alaska', 'AL': 'Alabama', 'AR': 'Arkansas', 'DC': 'DistrictofColumbia', 'DE': 'Delaware',
          'HI': 'Hawaii', 'IA': 'Iowa', 'ID': 'Idaho', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
          'ME': 'Maine', 'MS': 'Mississippi', 'MT': 'Montana', 'ND': 'NorthDakota', 'NE': 'Nebraska',
          'NH': 'NewHampshire', 'NM': 'NewMexico', 'OK': 'Oklahoma', 'RI': 'RhodeIsland', 'SD': 'SouthDakota',
          'UT': 'Utah', 'VT': 'Vermont', 'WV': 'WestVirginia', 'WY': 'Wyoming'}
JOBS = {
    '2007_3yr': ('2007/data/3_year/{name}/', '20073{ab}0025000.zip', 'g20073{ab}.txt'),
    '2008_3yr': ('2008/data/3_year/{name}/', '20083{ab}0025000.zip', 'g20083{ab}.txt'),
    '2009_5yr': ('2009/data/5_year_seq_by_state/{name}/All_Geographies_Not_Tracts_Block_Groups/',
                 '20095{ab}0018000.zip', 'g20095{ab}.txt'),
}


def curl(args):
    for a in range(4):
        r = subprocess.run(['curl', '-sS', '-f', '-m', '600'] + args, capture_output=True)
        if r.returncode == 0:
            return r.stdout
        time.sleep(5 * (a + 1))
    raise RuntimeError('curl failed %s' % args)


for job, (d, zf, gf) in JOBS.items():
    for ab, name in STATES.items():
        sub = os.path.join(OUT, job, name)
        os.makedirs(sub, exist_ok=True)
        url = BASE + '/' + d.format(name=name)
        z = zf.format(ab=ab.lower())
        g = gf.format(ab=ab.lower())
        if not os.path.exists(os.path.join(sub, z)):
            open(os.path.join(sub, z), 'wb').write(curl([url + z]))
        if not os.path.exists(os.path.join(sub, g + '.head')):
            open(os.path.join(sub, g + '.head'), 'wb').write(curl(['-r', '0-65535', url + g]))
        print(job, name, flush=True)
