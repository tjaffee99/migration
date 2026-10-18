#!/usr/bin/env python3
"""Write data/processed/sources_stock.csv (source_id,citation,url,accessed,notes).
A '<id>_derived' source_id marks rows computed by the pipeline from <id> (sums of printed parts,
or the remainder of an aggregate whose printed children do not add up to it)."""
import csv, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ACC = '2026-10-18'
W2 = 'https://www2.census.gov'
DC = 'https://data.census.gov/api/access/data/table'
S = [
    ('census_wp81_t1', 'Gibson, Campbell and Kay Jung (2006). Historical Census Statistics on the Foreign-Born Population of the United States: 1850 to 2000. U.S. Census Bureau Population Division Working Paper No. 81, Table 1 (Nativity of the population).',
     W2 + '/library/working-papers/2006/demo/pop-twps0081/tab01.xls', 'Total foreign born 1940 (11,594,896; complete count) and 1950 (10,347,395; 20% sample) used as national totals for 1940/1950. raw: data/raw/census_wp81/'),
    ('census_wp81_t3', 'Gibson & Jung (2006), Working Paper No. 81, Table 3: World region and country or area of birth of the foreign-born population: 1960 to 2000.',
     W2 + '/library/working-papers/2006/demo/pop-twps0081/tab03.xls', 'National 1960-2000. 1960-1990 sample data identical to WP29 Table 3 (cross-checked, 550 cells). Corrections: 1970 not-reported printed 315,721 but Total-Reported=315,732 (=WP81 T4, WP29 T3) -> 315,732 used; 1990 Gambia/Guinea/Ivory Coast (added in WP81) are not in the Western Africa 1990 subtotal -> dropped for 1990 (contained in Africa n.e.c.); 2000 "Soviet Union (former)" 838,809 is a memo total incl. Asian republics -> replaced by its parts.'),
    ('census_wp81_t4', 'Gibson & Jung (2006), Working Paper No. 81, Table 4: World region and country or area of birth of the foreign-born population, with geographic detail shown in decennial census publications of 1930 or earlier: 1850-1930 and 1960-2000.',
     W2 + '/library/working-papers/2006/demo/pop-twps0081/tab04.xls', 'National 1850-1930 (complete count). Identical to WP29 Table 4 for 1850-1930/1960-1990 (846 cells compared, 0 differences).'),
    ('census_wp81_t9', 'Gibson & Jung (2006), Working Paper No. 81, Table 9: Race and Hispanic origin of the foreign-born population: 1850 to 1990.',
     W2 + '/library/working-papers/2006/demo/pop-twps0081/tab09.xls', '1940 foreign born of races other than white (175,758) = residual for which country of birth was not tabulated.'),
    ('census_wp81_t14', 'Gibson & Jung (2006), Working Paper No. 81, Table 14: Nativity of the population, for regions, divisions, and states: 1850 to 2000.',
     W2 + '/library/working-papers/2006/demo/pop-twps0081/tab14.xls', 'State total population and foreign born 1850-2000 (1960+ sample). Equal to WP29 Table 13 for 1850-1990 (719 values compared, 0 differences). Territories are shown under the modern state name; see notes.'),
    ('census_wp29', 'Gibson, Campbell J. and Emily Lennon (1999). Historical Census Statistics on the Foreign-born Population of the United States: 1850-1990. U.S. Census Bureau Population Division Working Paper No. 29.',
     'https://www.census.gov/library/working-papers/1999/demo/POP-twps0029.html', 'Tables 3, 4, 13 (data/raw/census_wp29/) used only to cross-check WP81; not cited in output rows.'),
    ('census1950_v2p1_t49', 'U.S. Bureau of the Census (1953). U.S. Census of Population: 1950. Vol. II, Characteristics of the Population, Part 1, United States Summary, Table 49: Country of birth of the foreign-born population, for the United States, urban and rural, 1950, and for the United States, 1870 to 1940 (p. 1-98).',
     W2 + '/library/publications/decennial/1950/population-volume-2/21983999v2p1ch3.pdf', 'Foreign-born WHITE by country, 1950 (20% sample) and 1940; the only country-of-birth detail tabulated in 1940/1950. Manually transcribed from the scan (data/raw/census1950_v2p1/table49_transcribed_fbwhite_1950_1940.csv); parts sum exactly to the printed totals 10,161,168 (1950) and 11,419,138 (1940 = WP81 T9 white foreign born).'),
    ('census1950_v2p1_t71', 'U.S. Bureau of the Census (1953). U.S. Census of Population: 1950. Vol. II, Part 1, United States Summary, Table 71: Country of birth of the foreign-born white population, by regions, divisions, and states: 1950 (pp. 1-122, 1-123).',
     W2 + '/library/publications/decennial/1950/population-volume-2/21983999v2p1ch3.pdf', 'State x country 1950, foreign-born WHITE only (33 categories). Manually transcribed (data/raw/census1950_v2p1/t71_manual/); all 539 row/column sum constraints of the printed table hold. Block total = foreign-born white (state all-race FB totals are in stock_state_totals.csv).'),
    ('census1920_v2_t10', 'U.S. Bureau of the Census (1922). Fourteenth Census of the United States Taken in the Year 1920. Vol. II, Population, Chapter VI, Table 10: Distribution of foreign-born population by principal countries of birth, with rank in 1920, by divisions and states: 1920, 1910, and 1900 (pp. 710-726).',
     W2 + '/library/publications/decennial/1920/volume-2/41084484v2ch08.pdf', 'State x country 1900/1910/1920 for the principal countries of each state (12-25) plus "All other countries". Manually transcribed (data/raw/census1920_v2/t10_manual/); every state/year adds up and equals WP81 T14. 1910 figures for Austria/Germany/Russia/Poland as adjusted in 1920 (Polish mother tongue -> Poland); 1900 Canada incl. Newfoundland.'),
    ('census1990_stf4c_pa23', 'U.S. Bureau of the Census. Selected 1990 characteristics to supplement Census 2000 sample demographic profile - Region of birth of the foreign born. Source: 1990 STF4C, Matrix PA23 (file 90fb-birth.txt).',
     W2 + '/census_1990/other/90fb-birth.txt', 'State x world region (6 regions), foreign born excluding not reported, 1990 (sample). Residual "Region or country not reported (derived)" = WP81 T14 state foreign born minus reported.'),
    ('dec2000_sf3_pct019', 'U.S. Census Bureau. Census 2000 Summary File 3, Table PCT019: Place of birth for the foreign-born population (via data.census.gov table API; labels from api.census.gov/data/2000/dec/sf3/groups/PCT019.json).',
     DC + '?id=DECENNIALSF32000.PCT019&g=010XX00US$0400000', 'State x country 2000 (sample), 126 lines. Includes "Born at sea" line.'),
    ('acs1_sf_b05006', 'U.S. Census Bureau. American Community Survey 1-year estimates, Summary File (sequence-based), Table B05006 Place of birth for the foreign-born population, 2005-2009.',
     W2 + '/programs-surveys/acs/summary_file/<year>/data/', 'National and state, 2005-2009 (data.census.gov has no ACSDT1Y2005-2009). Sequences: 2005 #12, 2006 #22, 2007-2009 #25; record LOGRECNO 0000001 (sumlevel 010/040 verified in geo headers). Labels from api.census.gov/data/<y>/acs/acs1/groups/B05006.json, cross-checked with the lookup files. 2005: household population only (no group quarters). Filtered (suppressed) for ~16-26 small states each year.'),
    ('acs1_sf_b05002', 'U.S. Census Bureau. ACS 1-year Summary File, Table B05002 Place of birth by nativity and citizenship status, 2005-2009.',
     W2 + '/programs-surveys/acs/summary_file/<year>/data/', 'State total population (line 1) and foreign born (line 13), 2005-2009. Sequences 2005 #11, 2006 #20, 2007-2009 #23.'),
    ('acs1_api_b05006', 'U.S. Census Bureau. American Community Survey 1-year estimates, Table B05006 Place of birth for the foreign-born population in the United States, 2010-2019 and 2021-2024 (data.census.gov table API, keyless).',
     DC + '?id=ACSDT1Y<year>.B05006&g=010XX00US$0400000', 'National (g=010XX00US) and all states+DC+PR (g=010XX00US$0400000). Labels from api.census.gov/data/<year>/acs/acs1/groups/B05006.json; hierarchy taken from the label path, not line numbers. Estimates with MOE. Table is filtered for ~20-25 small states each year (filled from 5-year, see acs5_*).'),
    ('acs1_api_b05002', 'U.S. Census Bureau. ACS 1-year, Table B05002 Place of birth by nativity and citizenship status, 2010-2019, 2021-2024 (data.census.gov table API).',
     DC + '?id=ACSDT1Y<year>.B05002&g=010XX00US$0400000', 'State total population and foreign born (label "Foreign born" / "Foreign-born" 2024).'),
    ('acs1_2020_experimental_xk200503', 'U.S. Census Bureau. 2020 American Community Survey 1-Year Experimental Estimates, Table XK200503 Place of birth in the United States.',
     W2 + '/programs-surveys/acs/experimental/2020/data/XK200503.xlsx', 'State total population and foreign born for 2020 (no standard 2020 1-year release). Experimental weighting; the Census Bureau cautions against comparison with other ACS years.'),
    ('acs5_2016_2020_b05006', 'U.S. Census Bureau. ACS 5-year estimates 2016-2020, Table B05006 (data.census.gov table API).',
     DC + '?id=ACSDT5Y2020.B05006&g=010XX00US$0400000', 'Stand-in for year 2020 (national and all states) because the standard 2020 1-year estimates were not released; a 5-year period estimate centred on 2018, not a 2020 point estimate.'),
    ('acs5_api_b05006_fill', 'U.S. Census Bureau. ACS 5-year estimates, Table B05006, periods ending 2010-2024 (data.census.gov table API).',
     DC + '?id=ACSDT5Y<year>.B05006&g=010XX00US$0400000', 'Rows tagged acs5_<y-4>_<y>_b05006 are 5-year estimates used ONLY for states whose 1-year B05006 for year <y> is filtered; the year column is the 5-year end year. raw: data/raw/acs5_api/'),
    ('acs_sf_multiyear_fill', 'U.S. Census Bureau. ACS 3-year (2005-2007, 2006-2008) and 5-year (2005-2009) Summary Files, Table B05006.',
     W2 + '/programs-surveys/acs/summary_file/<year>/data/', 'Rows tagged acs3_2005_2007_sf_b05006, acs3_2006_2008_sf_b05006, acs5_2005_2009_sf_b05006: used ONLY for states whose 1-year B05006 for 2007/2008/2009 is filtered. MT, ND, SD, WY have no 3-year B05006 (2007/2008 gap).'),
]


def main():
    rows = [list(s[:3]) + [ACC, s[3]] for s in S]
    ids = [s[0] for s in S]
    # expand pattern families and derived ids actually used
    used = set()
    for fn in ('stock_national_by_country.csv', 'stock_state_by_country.csv', 'stock_state_totals.csv'):
        p = os.path.join(ROOT, 'data', 'processed', fn)
        if os.path.exists(p):
            used |= {r['source_id'] for r in csv.DictReader(open(p))}
    for u in sorted(used):
        if u in ids:
            continue
        base = u[:-len('_derived')] if u.endswith('_derived') else u
        if u.endswith('_derived'):
            note = 'Derived by the pipeline from %s: sums of printed parts, or the remainder of an aggregate whose printed children do not add up to it (labels end in "(derived)").' % base
            rows.append([u, 'Derived from ' + base, '', ACC, note])
        elif u.startswith('acs5_') and u.endswith('_b05006') and '_sf_' not in u:
            y = u.split('_')[2]
            rows.append([u, 'U.S. Census Bureau. ACS 5-year estimates %s-%s, Table B05006.' % (u.split('_')[1], y),
                         DC + '?id=ACSDT5Y%s.B05006&g=010XX00US$0400000' % y, ACC,
                         'Used only for states whose 1-year B05006 for %s is filtered (see acs5_api_b05006_fill).' % y])
        elif '_sf_b05006' in u:
            rows.append([u, 'U.S. Census Bureau. ACS multi-year Summary File, Table B05006 (%s).' % u, W2 + '/programs-surveys/acs/summary_file/', ACC,
                         'See acs_sf_multiyear_fill.'])
        ids.append(u)
    out = os.path.join(ROOT, 'data', 'processed', 'sources_stock.csv')
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['source_id', 'citation', 'url', 'accessed', 'notes'])
        seen = set()
        for r in rows:
            if r[0] in seen:
                continue
            seen.add(r[0])
            w.writerow(r)
    print('wrote', out, len(seen))


if __name__ == '__main__':
    main()
