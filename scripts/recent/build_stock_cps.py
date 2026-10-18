"""Build data/processed/stock_recent_by_country.csv from the CPS monthly aggregates.

Input: data/raw/census_cps_basic/aggregates/<yyyy>_<mm>_by_penatvty.csv (written by
cps_fetch_aggregate.py) and the PENATVTY code list (CPS Attachment 14, "Countries and areas of the
world", parsed from layouts/cpsjan26.pdf into layouts/cps_penatvty_codes_attachment14.csv).

Output columns: year,months,origin_label,level,parent_label,count,source_id,note
  * source_id cps_basic_monthly     one block per survey month   (months = "MM")
  * source_id cps_basic_annual_avg  mean of the available months (months = "MM-MM[,MM-MM]")
  ACS 2025 1-year rows would carry source_id acs1_api_b05006; there are none (not released).

Definitions
  * Foreign born = PRCITSHP 4 (naturalized) or 5 (not a citizen): not a U.S. citizen at birth.
    This is the Census/ACS definition (B05006 universe). People born abroad of American
    parent(s) (PRCITSHP 3) are natives and are excluded even though PENATVTY is a foreign code.
  * Weight = PWSSWGT (final person weight, "used for most tabulations", universe all persons
    PRPERTYP 1-3), 4 implied decimals. PWCMPWGT (composite weight) only covers civilians 16+
    (PRPERTYP 2) and is used here only for the civilian-16+ cross-check printed below.
  * Universe = CPS civilian noninstitutionalized population (PWSSWGT sums to the Census Bureau's
    monthly civilian noninstitutionalized population control). ACS includes group quarters.
Standard errors (approximate, shown as 90% MOE in `note`): the 8 month-in-sample rotation groups
of each month are used as random groups, Var(month) = sum_g (X_g - mean)^2 / (8*7) with
X_g = 8 x rotation-group total; pooled (averaged) over the months of a calendar year; the annual
mean's variance = pooled monthly variance x F, F = sum_c n_c^2 / (8 |S|^2) where n_c is the number
of months cohort c is in sample during the |S| months (4-8-4 rotation; assumes a household keeps
its country of birth -> conservative). F = 0.316 (12 months), 0.320 (11), 0.383 (9).
Run: python3 -I scripts/recent/build_stock_cps.py
"""
import csv, glob, math, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'data', 'raw', 'census_cps_basic')
OUT = os.path.join(ROOT, 'data', 'processed', 'stock_recent_by_country.csv')
SUMMARY = os.path.join(RAW, 'cps_foreign_born_monthly_summary.csv')
Z90 = 1.645

# hierarchy (ACS B05006-style regions/subregions so CPS rows line up with the ACS rows in
# stock_national_by_country.csv). node -> parent; leaves are PENATVTY codes.
TREE = {
    'Europe': 'Total', 'Northern Europe': 'Europe', 'Western Europe': 'Europe',
    'Southern Europe': 'Europe', 'Eastern Europe': 'Europe',
    'Asia': 'Total', 'Eastern Asia': 'Asia', 'South Central Asia': 'Asia',
    'South Eastern Asia': 'Asia', 'Western Asia': 'Asia',
    'Africa': 'Total', 'Eastern Africa': 'Africa', 'Middle Africa': 'Africa',
    'Northern Africa': 'Africa', 'Southern Africa': 'Africa', 'Western Africa': 'Africa',
    'Oceania': 'Total', 'Australia and New Zealand Subregion': 'Oceania',
    'Americas': 'Total', 'Latin America': 'Americas', 'Caribbean': 'Latin America',
    'Central America': 'Latin America', 'South America': 'Latin America',
    'Northern America': 'Americas',
}
# multi-code countries: country label -> [(code, subcountry label)]
COMBINED = {
    'United Kingdom': [('138', 'United Kingdom, not specified'), ('139', 'England'),
                       ('140', 'Scotland'), ('142', 'Northern Ireland')],
    'Portugal': [('129', 'Portugal, excluding Azores'), ('130', 'Azores')],
    'Czechoslovakia (incl. Czech Republic and Slovakia)': [
        ('105', 'Czechoslovakia, not specified'), ('148', 'Czech Republic'), ('149', 'Slovakia')],
    'China': [('207', 'China, excluding Hong Kong and Taiwan'), ('209', 'Hong Kong'),
              ('240', 'Taiwan')],
    'Korea': [('217', 'Korea, not specified'), ('220', 'South Korea')],
}
PARENT_OF = {}   # code or combined label -> parent node
for node, codes in {
    'Northern Europe': '106 108 118 119 127 136 UK',
    'Western Europe': '102 103 109 110 126 137',
    'Southern Europe': '116 120 134 PRT',
    'Eastern Europe': '100 104 117 128 132 147 150 151 152 154 168 155 156 157 160 162 163 164 165 '
                      'CSK',
    'Eastern Asia': '215 228 CHN KOR',
    'South Central Asia': '200 202 203 210 212 218 229 231 238 246',
    'South Eastern Asia': '205 206 211 223 226 233 236 242 247',
    'Western Asia': '158 159 161 213 214 216 222 224 235 239 243 245 248',
    'Northern America': '300 301',
    'Central America': '303 310 311 312 313 314 315 316',
    'Caribbean': '321 323 324 327 328 329 330 332 333 338 339 340 341',
    'South America': '360 361 362 363 364 365 368 369 370 372 373',
    'Eastern Africa': '416 417 427 448 453 457 460 461',
    'Middle Africa': '407 412 459',
    'Northern Africa': '400 414 430 436 451',
    'Southern Africa': '449',
    'Western Africa': '408 421 423 425 429 440 444 447 454',
    'Australia and New Zealand Subregion': '501 515',
    'Oceania': '508 511 512 523 527',
}.items():
    for c in codes.split():
        c = {'UK': 'United Kingdom', 'PRT': 'Portugal', 'CHN': 'China', 'KOR': 'Korea',
             'CSK': 'Czechoslovakia (incl. Czech Republic and Slovakia)'}.get(c, c)
        PARENT_OF[c] = node
RESIDUAL = {'166': 'Europe', '249': 'Asia', '343': 'Caribbean', '374': 'South America',
            '399': 'Americas', '462': 'Africa', '555': 'Total'}
MONTHS_MISSING_NOTE = {2025: 'October 2025 CPS was not collected (federal government shutdown); '
                             'no oct25pub file exists'}


def load_codes():
    fn = os.path.join(RAW, 'layouts', 'cps_penatvty_codes_attachment14.csv')
    return {r['penatvty']: r['name'] for r in csv.DictReader(open(fn))}


def load_months():
    """(year, month) -> {code: [w_total, n_records, [w_by_mis 1..8]]} for the foreign born,
    plus month totals."""
    data, totals = {}, {}
    for fn in sorted(glob.glob(os.path.join(RAW, 'aggregates', '*_by_penatvty.csv'))):
        y, m = map(int, re.match(r'(\d{4})_(\d\d)_', os.path.basename(fn)).groups())
        d = defaultdict(lambda: [0.0, 0, [0.0] * 8])
        tot = defaultdict(float)
        for r in csv.DictReader(open(fn)):
            w = float(r['w_pwsswgt'])
            tot['all'] += w
            tot[r['prcitshp_group']] += w
            tot['penatvty_foreign_any_citizenship'] += w if int(r['penatvty']) >= 100 else 0
            if r['prcitshp_group'] in ('fb_naturalized', 'fb_noncitizen'):
                e = d[r['penatvty']]
                e[0] += w
                e[1] += int(r['n_records'])
                e[2][int(r['hrmis']) - 1] += w
                tot['fb_civ16_pwcmpwgt'] += float(r['w_pwcmpwgt'])
                tot['fb_civ16_pwsswgt'] += float(r['w_pwsswgt_civ16'])
        data[(y, m)] = d
        totals[(y, m)] = tot
    return data, totals


def rotation_factor(months):
    s = set(months)
    n = []
    for t in range(-20, 14):
        k = sum(1 for mm in (t, t + 1, t + 2, t + 3, t + 12, t + 13, t + 14, t + 15) if mm in s)
        if k:
            n.append(k)
    return sum(k * k for k in n) / (8 * len(s) ** 2)


def rg_var(mis):
    x = [8 * v for v in mis]
    mu = sum(x) / 8
    return sum((v - mu) ** 2 for v in x) / 56


def build_tree(leaf):
    """leaf: {key: (w, n, mis[8])} keyed by code. Returns ordered rows
    (label, level, parent, w, n, mis) satisfying the summing invariants."""
    codes = load_codes.cache
    node = defaultdict(lambda: [0.0, 0, [0.0] * 8])
    def add(k, w, n, mis):
        e = node[k]
        e[0] += w; e[1] += n
        for i in range(8):
            e[2][i] += mis[i]
    combined_of = {c: lab for lab, lst in COMBINED.items() for c, _ in lst}
    sublabel = {c: s for lab, lst in COMBINED.items() for c, s in lst}
    rows_country, rows_sub, rows_res = [], [], []
    for c, (w, n, mis) in leaf.items():
        if c in RESIDUAL:
            chain = [RESIDUAL[c]]
            rows_res.append((codes[c], 'residual', RESIDUAL[c], c))
        elif c in combined_of:
            lab = combined_of[c]
            rows_sub.append((sublabel[c], 'subcountry', lab, c))
            add(lab, w, n, mis)
            chain = [PARENT_OF[lab]]
        else:
            rows_country.append((codes[c], 'country', PARENT_OF[c], c))
            chain = [PARENT_OF[c]]
        while chain[-1] != 'Total':
            chain.append(TREE[chain[-1]])
        for k in chain:
            add(k, w, n, mis)
        node[('leaf', c)] = [w, n, mis]
    out = [('Total', 'total', '', node['Total'])]
    def kids_of(p):
        return [k for k, v in TREE.items() if v == p]
    def emit(p):
        for k in kids_of(p):
            if node[k][1] == 0 and node[k][0] == 0:
                continue
            out.append((k, 'region' if p == 'Total' else 'subregion', p, node[k]))
            emit(k)
        for lab, lev, par, c in sorted(rows_country):
            if par == p:
                out.append((lab, lev, par, node[('leaf', c)]))
        for lab in sorted(COMBINED):
            if PARENT_OF[lab] == p and node[lab][1] > 0:
                out.append((lab, 'country', p, node[lab]))
                for slab, lev, par, c in sorted(rows_sub, key=lambda r: r[3]):
                    if par == lab:
                        out.append((slab, lev, par, node[('leaf', c)]))
        for lab, lev, par, c in sorted(rows_res):
            if par == p:
                out.append((lab, lev, par, node[('leaf', c)]))
    emit('Total')
    return out


def check_block(rows, tol=0.5):
    tot = [r for r in rows if r[1] == 'total'][0][3]
    s = sum(r[3] for r in rows if r[1] in ('country', 'residual'))
    assert abs(s - tot) <= tol, (s, tot)
    by_parent = defaultdict(float)
    for lab, lev, par, cnt, *_ in rows:
        if par and not (lev == 'subcountry'):
            by_parent[par] += cnt
    sub_parent = defaultdict(float)
    for lab, lev, par, cnt, *_ in rows:
        if lev == 'subcountry':
            sub_parent[par] += cnt
    vals = {r[0]: r[3] for r in rows}
    for p, v in list(by_parent.items()) + list(sub_parent.items()):
        assert abs(vals[p] - v) <= tol, (p, vals[p], v)
    labels = [r[0] for r in rows]
    assert len(labels) == len(set(labels)), 'duplicate labels'


def fmt_moe(se):
    m = Z90 * se
    return f'{m / 1e6:.2f}M' if m >= 1e6 else f'{m / 1e3:.0f}k' if m >= 1e4 else f'{m:,.0f}'


def acs_rows(year, raw_dir):
    """ACS 1-year B05006 national rows in this file's schema, built with the stock pipeline's own
    readers (scripts/stock/acs_read.py, stocklib.tree_rows) so the tree matches
    stock_national_by_country.csv. Returns [] while the year is not released/downloaded."""
    tab = os.path.join(raw_dir, f'ACSDT1Y{year}_B05006_us.json')
    grp = os.path.join(raw_dir, f'groups_acs1_{year}_B05006.json')
    if not (os.path.exists(tab) and os.path.exists(grp)):
        return []
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'stock'))
    import acs_read, stocklib  # noqa: E402  (read-only reuse)
    labels = acs_read.load_groups(grp, 'B05006')
    d = acs_read.load_api_table(tab, 'B05006')['0100000US']
    out = []
    for r in stocklib.tree_rows(labels, d['E'], d['M'], 'acs1_api_b05006'):
        moe = f'ACS 1-year; 90% MOE +/-{r["moe"]:,}' if r['moe'] != '' else 'ACS 1-year; derived'
        out.append([year, '01-12', r['origin_label'], r['level'], r['parent_label'], r['count'],
                    r['source_id'], moe])
    return out


def main():
    load_codes.cache = load_codes()
    data, totals = load_months()
    out_rows, summary = [], []
    years = sorted({y for y, _ in data})
    for y in years:
        months = sorted(m for (yy, m) in data if yy == y)
        F = rotation_factor(months)
        # monthly trees
        trees = {}
        for m in months:
            leaf = {c: (v[0], v[1], v[2]) for c, v in data[(y, m)].items()}
            trees[m] = build_tree(leaf)
        # pooled monthly variance per label within the year
        pooled = defaultdict(list)
        for m in months:
            for lab, lev, par, (w, n, mis) in trees[m]:
                pooled[lab].append(rg_var(mis))
        vmon = {lab: sum(v) / len(months) for lab, v in pooled.items()}
        for m in months:
            blk = []
            for lab, lev, par, (w, n, mis) in trees[m]:
                se = math.sqrt(vmon[lab])
                note = f'n={n} person records; approx. 90% MOE +/-{fmt_moe(se)}'
                if w > 0 and se / w > 0.30:
                    note += ' (CV>30%: unreliable)'
                if lev == 'total':
                    t = totals[(y, m)]
                    note += (f'; {100 * w / t["all"]:.2f}% of CPS civilian noninstitutional pop '
                             f'({t["all"]:,.0f})')
                blk.append((lab, lev, par, round(w), n, se))
                out_rows.append([y, f'{m:02d}', lab, lev, par, round(w), 'cps_basic_monthly', note])
            check_block([(b[0], b[1], b[2], b[3]) for b in blk], tol=60)
        # annual average
        labels = {}
        for m in months:
            for lab, lev, par, (w, n, mis) in trees[m]:
                e = labels.setdefault(lab, [lev, par, 0.0, 0])
                e[2] += w
                e[3] += n
        span = []
        for m in months:
            if span and span[-1][1] == m - 1:
                span[-1][1] = m
            else:
                span.append([m, m])
        mstr = ','.join(f'{a:02d}-{b:02d}' if a != b else f'{a:02d}' for a, b in span)
        order = [r[0] for r in trees[months[-1]]] + [l for l in labels if l not in
                                                     {r[0] for r in trees[months[-1]]}]
        blk = []
        for lab in order:
            lev, par, wsum, nsum = labels[lab]
            w = wsum / len(months)
            se = math.sqrt(vmon[lab] * F)
            note = (f'mean of {len(months)} monthly estimates; n={nsum} person-month records; '
                    f'approx. 90% MOE +/-{fmt_moe(se)}')
            if w > 0 and se / w > 0.30:
                note += ' (CV>30%: unreliable)'
            if lev == 'total' and y in MONTHS_MISSING_NOTE:
                note += '; ' + MONTHS_MISSING_NOTE[y]
            if lev == 'total' and len(months) < 12 and y not in MONTHS_MISSING_NOTE:
                note += f'; year to date (latest month {months[-1]:02d}/{y})'
            blk.append((lab, lev, par, round(w)))
            out_rows.append([y, mstr, lab, lev, par, round(w), 'cps_basic_annual_avg', note])
        check_block(blk, tol=60)
        for m in months:
            t = totals[(y, m)]
            tot_fb = [r for r in trees[m] if r[1] == 'total'][0][3]
            summary.append([y, m, round(t['all']), round(tot_fb[0]), tot_fb[1],
                            round(math.sqrt(rg_var(tot_fb[2]))), round(t['fb_naturalized']),
                            round(t['fb_noncitizen']), round(t['native_abroad']),
                            round(t['penatvty_foreign_any_citizenship']),
                            round(t['fb_civ16_pwsswgt']), round(t['fb_civ16_pwcmpwgt'])])
    # ACS 2025 1-year: not released as of 2026-10-18 (scheduled 2026-10-29); rows are added
    # automatically once scripts/recent/fetch_recent.sh has downloaded them.
    acs = acs_rows(2025, os.path.join(ROOT, 'data', 'raw', 'acs1_api_2025'))
    print(f'ACS 2025 1-year rows: {len(acs)}' + ('' if acs else ' (not released / not downloaded)'))
    out_rows = acs + out_rows
    with open(OUT, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year', 'months', 'origin_label', 'level', 'parent_label', 'count', 'source_id',
                    'note'])
        w.writerows(out_rows)
    with open(SUMMARY, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year', 'month', 'cps_weight_total', 'foreign_born', 'fb_n_records',
                    'fb_se_month_random_group', 'fb_naturalized', 'fb_noncitizen',
                    'native_born_abroad_us_parents', 'penatvty_foreign_any_citizenship',
                    'fb_civ16_pwsswgt', 'fb_civ16_pwcmpwgt'])
        w.writerows(summary)
    print(f'wrote {OUT}: {len(out_rows)} rows; summary {SUMMARY}')
    print('year months  fb_annual_avg   90%MOE')
    for r in out_rows:
        if r[6] == 'cps_basic_annual_avg' and r[3] == 'total':
            print(r[0], r[1], f'{r[5]:,}', r[7])


if __name__ == '__main__':
    main()
