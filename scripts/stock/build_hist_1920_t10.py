#!/usr/bin/env python3
"""1900, 1910, 1920 foreign-born population by principal country of birth, by state.

Source: Fourteenth Census of the United States (1920), Vol. II Population, Chapter VI (Country of
birth of the foreign-born population), Table 10 "Distribution of foreign-born population by
principal countries of birth, with rank in 1920, by divisions and states: 1920, 1910, and 1900",
pp. 710-726 (data/raw/census1920_v2/41084484v2ch08.pdf, PDF pages 26-42), manually transcribed into
data/raw/census1920_v2/t10_manual/p*.txt (one block per state; columns 1920 'both sexes', 1910,
1900; NA = not shown).

Each state lists its principal countries (12-25, varying by state) and 'All other countries'.
validate() checks, for every state and year, that the listed countries + 'All other countries'
equal 'Total foreign born' ('French' = French Canadians, a sub-line of Canada, excluded), and that
every total equals WP81 Table 14.  Notes printed in the source: 1910 figures for Austria, Germany,
Russia and Poland were adjusted in 1920 (persons of Polish mother tongue moved to Poland);
Newfoundland is included with Canada in 1900; 'Syria, etc.'/'Armenia, etc.' = countries
constituting Turkey in Asia in 1910 (Armenia, Palestine, Syria, Turkey in Asia); West Indies
excludes U.S. possessions.
Usage: python3 -I scripts/stock/build_hist_1920_t10.py   (prints the validation report)
"""
import csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stocklib import STATE_FIPS  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'data', 'raw', 'census1920_v2', 't10_manual')
YEARS = (1920, 1910, 1900)
SUB = {'French': ('Canada-French', 'Canada')}
RESIDUAL = {'All other countries', 'Atlantic Islands', 'West Indies', 'Central and South America'}
RELABEL = {'Syria etc.': 'Turkey in Asia (Syria, Armenia, Palestine, Turkey in Asia; source: "Syria, etc.")',
           'Armenia etc.': 'Turkey in Asia (Syria, Armenia, Palestine, Turkey in Asia; source: "Armenia, etc.")',
           'Atlantic Islands': 'Atlantic Islands (incl. Azores)',
           'West Indies': 'West Indies (except U.S. possessions)'}


def load():
    states, order = {}, []
    for fn in sorted(glob.glob(os.path.join(SRC, 'p*.txt'))):
        cur = None
        for line in open(fn):
            line = line.strip()
            if not line or line.startswith('# '):
                continue
            if line.startswith('#STATE'):
                cur = line[7:].strip()
                assert cur not in states, cur
                states[cur] = []
                order.append(cur)
                continue
            parts = [p.strip() for p in line.split(',')]
            lab, vals = ','.join(parts[:-3]), parts[-3:]
            states[cur].append((lab, [None if v == 'NA' else int(v) for v in vals]))
    return states, order


def validate(states):
    probs = []
    for st, rows in states.items():
        tot = [r for r in rows if r[0] == 'Total foreign born']
        assert len(tot) == 1, st
        for k, y in enumerate(YEARS):
            s = sum((r[1][k] or 0) for r in rows if r[0] not in SUB and r[0] != 'Total foreign born')
            if s != tot[0][1][k]:
                probs.append('sum %s %d: total %d vs parts %d' % (st, y, tot[0][1][k], s))
    wp = {}
    fn = os.path.join(ROOT, 'data', 'processed', 'stock_state_totals.csv')
    if os.path.exists(fn):
        for r in csv.DictReader(open(fn)):
            if r['year'] in ('1900', '1910', '1920') and r['state_fips']:
                wp[(r['state_fips'], int(r['year']))] = int(r['foreign_born'])
        for st, rows in states.items():
            tot = [r for r in rows if r[0] == 'Total foreign born'][0][1]
            for k, y in enumerate(YEARS):
                w = wp.get((STATE_FIPS[st], y))
                if w is None or w != tot[k]:
                    probs.append('WP81 T14 %s %d: %s vs %s' % (st, y, tot[k], w))
    return probs


def rows():
    states, order = load()
    probs = validate(states)
    assert not probs, probs
    S = 'census1920_v2_t10'
    out = []
    for st in order:
        fips = STATE_FIPS[st]
        for k, y in enumerate(YEARS):
            for lab, vals in states[st]:
                v = vals[k]
                if v is None:
                    continue
                if lab == 'Total foreign born':
                    level, parent, label = 'total', '', 'Total'
                elif lab in SUB:
                    label, parent = SUB[lab]
                    level = 'subcountry'
                else:
                    label = RELABEL.get(lab, lab)
                    level = 'residual' if lab in RESIDUAL else 'country'
                    parent = 'Total'
                out.append(dict(year=y, state_fips=fips, origin_label=label, level=level,
                                parent_label=parent, count=v, moe='', source_id=S))
                if lab == 'French':
                    canada = [vv[k] for ll, vv in states[st] if ll == 'Canada'][0]
                    out.append(dict(year=y, state_fips=fips, origin_label='Canada-Other (derived)',
                                    level='subcountry', parent_label='Canada', count=canada - v, moe='',
                                    source_id=S + '_derived'))
    return out


if __name__ == '__main__':
    states, order = load()
    probs = validate(states)
    n = sum(len(r) for r in states.values())
    print(len(order), 'states/DC;', n, 'label rows x 3 years; problems:', len(probs))
    for p in probs:
        print(' ', p)
