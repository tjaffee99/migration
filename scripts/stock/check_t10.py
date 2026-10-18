#!/usr/bin/env python3
"""Validate the manual transcription of 1920 Census Vol. II ch. VI Table 10 (1920/1910/1900 by state):
every state block must add up (countries excl. the 'French' sub-line + 'All other countries' = total,
for each year, NA cells treated as 0 where the source prints a footnote), and the totals must
match WP81 Table 14."""
import csv, glob, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'data', 'raw', 'census1920_v2', 't10_manual')
SUB = {'French'}   # sub-lines (part of the preceding country)


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
            states[cur].append((lab, [None if v == 'NA' else int(v.rstrip('?')) for v in vals], fn))
    return states, order


def check(states):
    probs = []
    for st, rows in states.items():
        tot = [r for r in rows if r[0] == 'Total foreign born']
        assert len(tot) == 1, st
        for k, y in enumerate((1920, 1910, 1900)):
            s = sum((r[1][k] or 0) for r in rows if r[0] not in SUB and r[0] != 'Total foreign born')
            if s != tot[0][1][k]:
                probs.append((st, y, tot[0][1][k], s, tot[0][1][k] - s))
    return probs


if __name__ == '__main__':
    states, order = load()
    probs = check(states)
    wp = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'processed', 'stock_state_totals.csv'))):
        if r['year'] in ('1900', '1910', '1920'):
            wp[(r['state'].split(' (')[0], int(r['year']))] = int(r['foreign_born'])
    for st in order:
        tot = [r for r in states[st] if r[0] == 'Total foreign born'][0][1]
        for k, y in enumerate((1920, 1910, 1900)):
            w = wp.get((st, y))
            if w is not None and w != tot[k]:
                probs.append(('WP81 total', st, y, tot[k], w))
    print(len(order), 'states;', len(probs), 'problems')
    for p in probs:
        print(p)
