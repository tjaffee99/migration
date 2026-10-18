"""Validate and assemble HSUS 1960 series C 88-114 ("Immigrants, by country: 1820 to 1957",
Historical Statistics of the United States, Colonial Times to 1957, ch. C, pp. 56-59).

Inputs: data/raw/hsus1960_chC/C88_114_tesseract_ocr.csv (Tesseract, column by column, made by
scripts/flows/ocr_hsus1960.py), the PDF's own text layer (a second, independent OCR), and the
DHS Table 1 annual totals (C 88 is the same series).

Every cell gets candidate values: the Tesseract reading, the aligned text-layer reading, and
3<->8 variants of the Tesseract reading (Tesseract systematically reads this typeface's 3 as 8),
each with a plausibility cost.  Per year, the cheapest unambiguous assignment satisfying the
table's accounting identities is chosen:
    E1 Europe      = sum of the 11 European columns (C 90-100)
    E2 Asia        = Turkey in Asia + China + Japan + Other Asia (C 102-105)
    E3 America     = Canada & Newfoundland + Mexico + Other America (C 107-109)
    E4 Australasia = Australia & New Zealand + Other Pacific Islands (C 112-113)
    E5 All         = Europe + Asia + America + Africa + Australasia + All other (= DHS Table 1)
Text-layer tokens are aligned to columns monotonically (no swapping of values between columns).
If all five identities hold the year is 'full'.  Otherwise only regional groups whose own
identity has a unique best solution are kept and the rest of the total goes into one derived
residual row ('derived_unvalidated_remainder').  Cells whose kept value differs from the
Tesseract reading get basis 'reported_annual_ocr_reconciled'.
"""
import csv
import itertools
import re
from collections import defaultdict

EU_COLS = ["All countries", "Europe", "Great Britain", "Ireland", "Scandinavia", "Other Northwestern Europe",
           "Germany", "Poland", "Other Central Europe", "U.S.S.R. and Baltic States", "Other Eastern Europe",
           "Italy", "Other Southern Europe"]
AS_COLS = ["Asia", "Turkey in Asia", "China", "Japan", "Other Asia", "America", "Canada and Newfoundland",
           "Mexico", "Other America", "Africa", "Australasia", "Australia and New Zealand",
           "Other Pacific Islands", "All other countries"]
EQS = [
    ("Europe", EU_COLS[2:]),
    ("Asia", ["Turkey in Asia", "China", "Japan", "Other Asia"]),
    ("America", ["Canada and Newfoundland", "Mexico", "Other America"]),
    ("Australasia", ["Australia and New Zealand", "Other Pacific Islands"]),
    ("All countries", ["Europe", "Asia", "America", "Africa", "Australasia", "All other countries"]),
]
LEVEL = {"All countries": ("total", ""),
         "Europe": ("region", "All countries"), "Asia": ("region", "All countries"),
         "America": ("region", "All countries"), "Africa": ("region", "All countries"),
         "Australasia": ("region", "All countries"), "All other countries": ("residual", "All countries"),
         "Great Britain": ("country", "Europe"), "Ireland": ("country", "Europe"),
         "Scandinavia": ("subregion", "Europe"), "Other Northwestern Europe": ("residual", "Europe"),
         "Germany": ("country", "Europe"), "Poland": ("country", "Europe"),
         "Other Central Europe": ("residual", "Europe"), "U.S.S.R. and Baltic States": ("subregion", "Europe"),
         "Other Eastern Europe": ("residual", "Europe"), "Italy": ("country", "Europe"),
         "Other Southern Europe": ("residual", "Europe"),
         "Turkey in Asia": ("country", "Asia"), "China": ("country", "Asia"), "Japan": ("country", "Asia"),
         "Other Asia": ("residual", "Asia"), "Canada and Newfoundland": ("country", "America"),
         "Mexico": ("country", "America"), "Other America": ("residual", "America"),
         "Australia and New Zealand": ("subregion", "Australasia"),
         "Other Pacific Islands": ("residual", "Australasia")}
SID = "hsus1960_C88_114"
TOTALS_SID = "ohss_yb2022_lpr_xlsx"


def to_int(tok):
    tok = (tok or "").strip()
    if not tok:
        return None
    if " " in tok:                       # two words fell in one cell -> unreliable
        tok = tok.replace(" ", "")
    if not re.fullmatch(r"\d{1,3}([.,]\d{3})*|\d+", tok):
        digits = re.sub(r"[^\d]", "", tok)
        return int(digits) if digits else None
    return int(re.sub(r"[^\d]", "", tok))


def similar(a, b):
    sa, sb = str(a), str(b)
    return len(sa) == len(sb) and sum(1 for x, y in zip(sa, sb) if x != y) <= 2


def eq_ok(vals, parent, kids):
    return (vals.get(parent) or 0) == sum(vals.get(k) or 0 for k in kids)


def parse(ocr_csv, pdf, dhs_totals):
    """Return (rows, messages).  rows follow the flows_by_origin schema."""
    msgs = []
    pages = defaultdict(list)
    with open(ocr_csv) as f:
        for r in csv.DictReader(f):
            pages[int(r["page"])].append(r)
    tl = {p: textlayer_rows(pdf, p, n) for p, n in ((18, 13), (19, 13), (20, 14), (21, 12))}
    # the p.21 text layer lacks the Turkey (C 102) and All-other (C 114) columns: shift indices
    tl[21] = [[((j if j == 0 else j + 1), v) for j, v in r] for r in tl[21]]
    eu, asx = pages[18] + pages[19], pages[20] + pages[21]
    teu, tas = tl[18] + tl[19], tl[20] + tl[21]
    years = list(range(1957, 1819, -1))
    if not (len(eu) == len(asx) == len(teu) == len(tas) == len(years)):
        msgs.append(f"HSUS 1960: row counts do not match years (tess {len(eu)}/{len(asx)}, "
                    f"text layer {len(teu)}/{len(tas)}, years {len(years)}) -- HSUS rows skipped")
        return [], msgs
    rows, full, partial, c88_mismatch, n_alt = [], [], [], [], 0
    for y, re_, ra, te, ta in zip(years, eu, asx, teu, tas):
        cands, tess = {}, {}
        for cols_, row_, toks in ((EU_COLS, re_, te), (AS_COLS, ra, ta)):
            tv = [to_int(row_[f"c{i+1}"]) for i in range(len(cols_))]
            al = align_textlayer(tv, toks)
            for i, lab in enumerate(cols_):
                tess[lab] = tv[i]
                cands[lab] = cell_candidates(tv[i], [al[i]] if i in al else [])
        txt88 = next((v for j, v in te if j == 0), None)
        if dhs_totals[y] not in (tess["All countries"], txt88):
            c88_mismatch.append(y)
        cands["All countries"] = {dhs_totals[y]: 0}
        vals, validated, status = solve_year_joint(cands)
        (full if status == "full" else partial).append(y)
        leaf_sum = 0
        for lab in EU_COLS + AS_COLS:
            if lab not in validated:
                continue
            v = vals[lab]
            lev, par = LEVEL[lab]
            alt = v != tess[lab] and not (tess[lab] is None and v == 0)
            n_alt += alt
            rows.append(dict(period_start=y, period_end=y, origin_label=lab, level=lev, parent_label=par,
                             count=v, basis="reported_annual_ocr_reconciled" if alt else "reported_annual",
                             source_id=SID))
            if lev in ("country", "residual"):
                leaf_sum += v
            elif lev == "subregion":   # Scandinavia, U.S.S.R. & Baltic, Australia & NZ: leaf aggregates
                rows.append(dict(period_start=y, period_end=y, origin_label=f"{lab} (no country detail in source)",
                                 level="residual", parent_label=lab, count=v,
                                 basis="derived_region_without_detail", source_id=SID))
                leaf_sum += v
            elif lab == "Africa":
                rows.append(dict(period_start=y, period_end=y, origin_label="Africa (no country detail in source)",
                                 level="residual", parent_label="Africa", count=v,
                                 basis="derived_region_without_detail", source_id=SID))
                leaf_sum += v
        if status == "partial":
            rows.append(dict(period_start=y, period_end=y,
                             origin_label="Remainder not validated from OCR (total minus validated groups)",
                             level="residual", parent_label="All countries", count=dhs_totals[y] - leaf_sum,
                             basis="derived_unvalidated_remainder", source_id=SID))
    msgs.append(f"HSUS 1960 C 88-114: {len(full)} of {len(years)} years fully reconciled (all 5 identities); "
                f"{len(partial)} partially (only regional groups whose identity holds are kept, rest in a derived "
                f"remainder row): {sorted(partial)}")
    msgs.append(f"  cells where the reconciled value differs from the Tesseract reading: {n_alt}; "
                f"years where neither OCR source matched the DHS total exactly: {len(c88_mismatch)}")
    return rows, msgs


# ----------------------------------------------------------------------------
# second, independent OCR: the text layer that ships with the Census PDF (pdftotext -layout)
# ----------------------------------------------------------------------------
import subprocess

NUMTOK = re.compile(r"\d{1,3}(?:\s?[.,]\s?\d{3})+|\d+")


def _kmeans1d(xs, k, iters=60):
    xs = sorted(xs)
    cents = [xs[int((i + 0.5) * len(xs) / k)] for i in range(k)]
    for _ in range(iters):
        g = defaultdict(list)
        for x in xs:
            g[min(range(k), key=lambda i: abs(x - cents[i]))].append(x)
        new = [sum(g[i]) / len(g[i]) if g[i] else cents[i] for i in range(k)]
        if new == cents:
            break
        cents = new
    return sorted(cents)


def textlayer_rows(pdf, page, ncols):
    txt = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
                         check=True, capture_output=True, text=True).stdout
    rows, started = [], False
    for line in txt.splitlines():
        s = line.rstrip()
        if re.fullmatch(r"\s*(8[89]|9\d|1[01]\d)(\s+(8[89]|9\d|1[01]\d))+\s*", s):
            started = True
            continue
        if not started:
            continue
        m = re.match(r"^\s*(1[89]\d\d)\s*[.\-·, ]{2,}", s)
        body = (" " * m.end() + s[m.end():]) if m else s
        if re.match(r"^\s*\S{0,2}\s*\d?\s*(For|No record|Prior|Comprises|Includes|Philippine|Between|From|agree|nclusive)", s):
            if rows:
                break
            continue
        toks = [(mm.end(), int(re.sub(r"[^\d]", "", mm.group()))) for mm in NUMTOK.finditer(body)]
        if len(toks) < 3:
            continue
        rows.append(toks)
    ends = [e for r in rows for e, _ in r]
    cents = _kmeans1d(ends, ncols)
    out = []
    for r in rows:
        out.append([(min(range(ncols), key=lambda i: abs(e - cents[i])), v) for e, v in r])
    return out


# ----------------------------------------------------------------------------
# joint solver over candidate values from the two OCR sources
# ----------------------------------------------------------------------------
def solve_eq(parent_cands, kid_cands, max_states=600000, max_cost=8.0):
    """parent_cands: {value: cost}; kid_cands: list of {value: cost}.
    Returns {parent_value: (cost, [kid values], ambiguous)} for every reachable parent value.
    'ambiguous' = another assignment with the same (minimal) cost gives the same sum."""
    states = {0: (0, (), False)}
    pmax = max(parent_cands)
    for cands in kid_cands:
        new = {}
        for sm, (c, ch, amb) in states.items():
            for v, vc in cands.items():
                key, cc, nch = sm + v, c + vc, ch + (v,)
                if key > pmax or cc > max_cost:
                    continue
                cur = new.get(key)
                if cur is None or cc < cur[0]:
                    new[key] = (cc, nch, amb)
                elif cc == cur[0] and cur[1] != nch:
                    new[key] = (cc, cur[1], True)
        states = new
        if len(states) > max_states:
            return {}
    out = {}
    for pv, pc in parent_cands.items():
        if pv in states:
            c, ch, amb = states[pv]
            out[pv] = (pc + c, list(ch), amb)
    return out


def _variants(v, max_subs=3):
    """Tesseract systematically reads this typeface's '3' as '8' (and occasionally the reverse):
    enumerate readings with up to max_subs 8<->3 substitutions."""
    s = str(v)
    pos = [i for i, ch in enumerate(s) if ch in "38"]
    out = {}
    for k in range(1, min(max_subs, len(pos)) + 1):
        for comb in itertools.combinations(pos, k):
            t = list(s)
            for i in comb:
                t[i] = "3" if t[i] == "8" else "8"
            out[int("".join(t))] = k
    return out


def cell_candidates(tess_val, text_vals):
    """Candidate values for one cell with a plausibility cost (lower = better):
       0    Tesseract reading confirmed by the PDF text layer
       0.2  Tesseract reading alone
       0.3/sub  a 3<->8 variant of the Tesseract reading confirmed by the text layer
       1/sub    an unconfirmed 3<->8 variant
       1.5  a text-layer-only reading
    """
    tl = set(text_vals)
    c = {}
    if tess_val is not None:
        c[tess_val] = 0.0 if tess_val in tl else 0.2
        for v, k in _variants(tess_val).items():
            c.setdefault(v, (0.3 if v in tl else 1.0) * k)
    for v in tl:
        c.setdefault(v, 1.5)
    if tess_val is None:
        c.setdefault(0, 0.0 if not tl else 0.5)   # blank cell = none recorded
    return c


def solve_year_joint(cands):
    """cands: label -> {value: cost}; 'All countries' has a single (DHS) value.
    Returns (values, validated_labels, status).  status 'full' = all five identities hold;
    'partial' = only some regional identities could be validated (values holds only those)."""
    region_opts = {}
    for parent, kids in EQS[:-1]:
        sol = solve_eq(cands[parent], [cands[k] for k in kids])
        region_opts[parent] = sol or None
    total = next(iter(cands["All countries"]))
    top = []
    feasible = True
    for lab in EQS[-1][1]:
        if lab in region_opts:
            if region_opts[lab] is None:
                feasible = False
                break
            top.append({v: c for v, (c, _, _) in region_opts[lab].items()})
        else:
            top.append(cands[lab])
    chosen = {"All countries": total}
    if feasible:
        sol5 = solve_eq(cands["All countries"], top, max_cost=1e9)
        if sol5 and not sol5[total][2]:
            _, vals5, _ = sol5[total]
            ok = True
            for lab, v in zip(EQS[-1][1], vals5):
                chosen[lab] = v
                if lab in region_opts:
                    _, kv, amb = region_opts[lab][v]
                    if amb:
                        ok = False
                    for k, x in zip(dict(EQS)[lab], kv):
                        chosen[k] = x
            if ok:
                return chosen, set(chosen), "full"
    # partial: keep each regional group whose identity has a single best, unambiguous solution
    chosen = {"All countries": total}
    for parent, kids in EQS[:-1]:
        sol = region_opts[parent]
        if not sol:
            continue
        best = min(sol.items(), key=lambda kv: kv[1][0])
        ties = [v for v, (c, _, _) in sol.items() if c == best[1][0]]
        if len(ties) > 1 or best[1][2]:
            continue
        chosen[parent] = best[0]
        for k, x in zip(kids, best[1][1]):
            chosen[k] = x
    return chosen, set(chosen), "partial"


def _digit_sim(a, b):
    """similarity of two digit strings aligned from the right (0..1)"""
    sa, sb = str(a), str(b)
    n = max(len(sa), len(sb))
    same = sum(1 for x, y in zip(reversed(sa), reversed(sb)) if x == y or {x, y} == {"3", "8"})
    return same / n


def align_textlayer(tess_vals, toks):
    """Monotonic alignment of text-layer tokens [(est_col, value)] to the Tesseract columns.
    Returns {col_index: value}.  A token may only land on a column whose Tesseract cell is blank
    if its estimated column is within 1; otherwise it must look like the Tesseract reading."""
    n, m = len(tess_vals), len(toks)
    NEG = -1e9
    best = [[NEG] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = best[i][j]
            if cur == NEG:
                continue
            if i < n and cur > best[i + 1][j]:                 # column without a text token
                best[i + 1][j], back[i + 1][j] = cur, ("skipcol", i, j)
            if j < m and cur - 0.6 > best[i][j + 1]:           # drop a text token
                best[i][j + 1], back[i][j + 1] = cur - 0.6, ("skiptok", i, j)
            if i < n and j < m:
                est, v = toks[j]
                tv = tess_vals[i]
                if tv is None:
                    sc = 0.3 if abs(est - i) <= 1 else NEG
                else:
                    sc = _digit_sim(tv, v)
                    sc = sc if sc >= 0.5 else NEG
                if sc > NEG and cur + sc > best[i + 1][j + 1]:
                    best[i + 1][j + 1], back[i + 1][j + 1] = cur + sc, ("match", i, j)
    i, j = n, m
    out = {}
    while (i, j) != (0, 0) and back[i][j] is not None:
        kind, pi, pj = back[i][j]
        if kind == "match":
            out[pi] = toks[pj][1]
        i, j = pi, pj
    return out
