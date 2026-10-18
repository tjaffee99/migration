#!/usr/bin/env python3
"""Consistency checks for the stock outputs (prints a report; exit code 1 on hard failures).

  * every (year[, state], source block) of the by-country files: sum(country)+sum(residual)==total
  * every parent_label exists in the same block; labels unique within a block
  * children of each node sum to the node (where the node has children) -- reported, not fatal
  * no negative counts
  * sanity values (1850 2.24M, 1910 13.5M / 14.7%, 1970 9.6M, 2000 31.1M, ACS 2023 47.8M)
  * state sums vs national totals; every source_id documented in sources_stock.csv
Usage: python3 -I scripts/stock/check_outputs.py
"""
import collections, csv, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROC = os.path.join(ROOT, 'data', 'processed')
hard = []


def blocks(rows, key):
    b = collections.defaultdict(list)
    for r in rows:
        b[key(r)].append(r)
    return b


def check_block(name, sub):
    tot = [r for r in sub if r['level'] == 'total']
    if len(tot) != 1:
        hard.append('%s: %d total rows' % (name, len(tot)))
        return 0
    t = int(tot[0]['count'])
    p = sum(int(r['count']) for r in sub if r['level'] in ('country', 'residual'))
    if t != p:
        hard.append('%s: total %d != country+residual %d' % (name, t, p))
    labels = collections.Counter(r['origin_label'] for r in sub)
    d = [l for l, c in labels.items() if c > 1]
    if d:
        hard.append('%s: duplicate labels %s' % (name, d[:5]))
    lab = set(labels)
    miss = [r['origin_label'] for r in sub if r['parent_label'] and r['parent_label'] not in lab]
    if miss:
        hard.append('%s: parent missing for %s' % (name, miss[:5]))
    neg = [r['origin_label'] for r in sub if int(r['count']) < 0]
    if neg:
        hard.append('%s: negative %s' % (name, neg[:5]))
    kids = collections.defaultdict(int)
    has = set()
    for r in sub:
        if r['parent_label']:
            kids[r['parent_label']] += int(r['count'])
            has.add(r['parent_label'])
    soft = 0
    for r in sub:
        if r['origin_label'] in has and kids[r['origin_label']] != int(r['count']):
            soft += 1
    return soft


def main():
    src = {r['source_id'] for r in csv.DictReader(open(os.path.join(PROC, 'sources_stock.csv')))}
    nat = list(csv.DictReader(open(os.path.join(PROC, 'stock_national_by_country.csv'))))
    st = list(csv.DictReader(open(os.path.join(PROC, 'stock_state_by_country.csv'))))
    tot = list(csv.DictReader(open(os.path.join(PROC, 'stock_state_totals.csv'))))
    print('rows: national %d, state x country %d, state totals %d' % (len(nat), len(st), len(tot)))
    soft = 0
    for y, sub in blocks(nat, lambda r: r['year']).items():
        soft += check_block('national %s' % y, sub)
    nb = 0
    for k, sub in blocks(st, lambda r: (r['year'], r['state_fips'])).items():
        nb += 1
        soft += check_block('state %s/%s' % k, sub)
    print('state x country blocks checked:', nb, '; nodes whose children do not sum to them:', soft)
    for f, rows in (('national', nat), ('state_by_country', st), ('state_totals', tot)):
        und = sorted({r['source_id'] for r in rows} - src)
        if und:
            hard.append('%s: undocumented source_id %s' % (f, und))
    # sanity values
    ntot = {int(r['year']): int(r['count']) for r in nat if r['level'] == 'total'}
    us_pop = collections.defaultdict(int)
    us_fb = collections.defaultdict(int)
    for r in tot:
        if r['state_fips'] != '72':
            us_pop[int(r['year'])] += int(r['total_pop'])
            us_fb[int(r['year'])] += int(r['foreign_born'])
    print('\nSanity checks (national by-country total; state-sum foreign born; % of population):')
    for y, exp in ((1850, '2.24M'), (1910, '13.5M (14.7%)'), (1970, '9.6M'), (2000, '31.1M'), (2023, '47.8M')):
        print('  %d: national %s ; state sum %s ; %.1f%%  (expected ~%s)' %
              (y, format(ntot.get(y), ','), format(us_fb[y], ','), 100.0 * us_fb[y] / us_pop[y], exp))
    print('\nYears in each file:')
    print('  national:', sorted(ntot))
    print('  state totals:', sorted(us_fb))
    print('  state x country:', sorted({int(r['year']) for r in st}))
    print('\nState-sum vs national foreign-born total (state totals file, excl. PR):')
    for y in sorted(us_fb):
        n = ntot.get(y)
        if n:
            print('  %d  states %s  national %s  diff %s' % (y, format(us_fb[y], ','), format(n, ','),
                                                         format(us_fb[y] - n, ',')))
    if hard:
        print('\nHARD FAILURES:')
        for h in hard[:50]:
            print(' ', h)
        sys.exit(1)
    print('\nall hard checks passed')


if __name__ == '__main__':
    main()
