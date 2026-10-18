"""Combine the processed source tables into the single yearly dataset the map reads.

Reads  data/processed/*.csv (built by scripts/flows, scripts/colonial, scripts/stock) and
       data/curated/events.json
Writes web/data/data.json and prints validation checks.

Annual arrivals by origin, 1607-2024
  1607-1775  historians' period estimates (Menard, Tomlins, Fogleman), spread evenly over
             the years of each period; enslaved Africans from the SlaveVoyages estimates.
  1776-1782  war years: no estimate for European arrivals.
  1783-1819  9,900 Europeans a year (Grabbe via Cohn), split by the origin mix of the
             1820s official counts (an assumption, flagged in the page).
  1820-1987  official annual totals (DHS Yearbook Table 1) split by origin with iterative
             proportional fitting, so each year matches its official total and each origin
             matches its official decade total (Table 2). For 1820-1957 the fit starts from the
             yearly counts by country group in Historical Statistics of the US (1960), so the
             within-decade timing follows real yearly data.
  1988       official annual counts by country of last residence.
  1989-2023  official annual counts by country of birth (yearbook Table 3).
Immigrants living in the US (foreign-born) by origin: census years 1850-2000, ACS 2005-2024,
interpolated in the page between those benchmark years. (State-level tables stay in
data/processed for other uses; the page draws national figures only.)

Usage: python3 -I scripts/build/build_data.py
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins import GROUPS, Registry  # noqa: E402
import illegal  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"
Y0, Y1 = 1607, 2026
NY = Y1 - Y0 + 1
R = Registry()
checks = []


def rows(name):
    path = P / name
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def check(label, ok, detail=""):
    checks.append((ok, label, detail))


# ---------------------------------------------------------------- hierarchy helpers
def leaves(table):
    """Rows of one source table that have no child rows, so summing them never double counts.

    Where a parent's children don't add up to it (e.g. Austria-Hungary in the 1900s, with only
    part of it split into Austria and Hungary), the remainder is kept as a leaf under the
    parent's own label.
    """
    kids = defaultdict(list)
    for r in table:
        if r["level"] != "total":
            kids[r["parent_label"]].append(r)
    out = []
    for r in table:
        if r["level"] == "total":
            continue
        ch = [c for c in kids.get(r["origin_label"], []) if c is not r]
        if not ch:
            out.append(r)
            continue
        rem = (num(r["count"]) or 0) - sum(num(c["count"]) or 0 for c in ch)
        if rem > 0.5:
            out.append(dict(r, count=str(rem), level="residual" if r["level"] in ("region", "subregion") else r["level"]))
    tot = next((r for r in table if r["level"] == "total"), None)
    if tot:
        top = kids.get(tot["origin_label"], [])
        rem = (num(tot["count"]) or 0) - sum(num(c["count"]) or 0 for c in top)
        if rem > 0.5:
            out.append({"origin_label": "Not specified", "level": "residual", "parent_label": "", "count": str(rem)})
    return out


def resolve_row(r, year):
    lvl = r["level"]
    if lvl in ("region", "subregion"):
        lvl = "residual"
    return R.resolve(r["origin_label"], lvl, r["parent_label"], year)


def table_by_origin(table, year):
    out = defaultdict(float)
    for r in leaves(table):
        c = num(r["count"])
        if not c:
            continue
        uid = resolve_row(r, year)
        if uid is None:
            uid = R.unit("XNS")["id"]
        out[uid] += c
    return dict(out)


def table_total(table):
    for r in table:
        if r["level"] == "total":
            return num(r["count"])
    return None


# ---------------------------------------------------------------- flows: colonial era
flow = defaultdict(lambda: [0.0] * NY)  # origin id -> per-year values
basis = [""] * NY


def add_spread(uid, start, end, count):
    start, end = max(start, Y0), min(end, Y1)
    n = end - start + 1
    if n <= 0:
        return
    for y in range(start, end + 1):
        flow[uid][y - Y0] += count / n


colonial = rows("flows_colonial_by_origin.csv")
grabbe = None
for r in colonial:
    if not r["note"].startswith("series=primary"):
        continue
    a, b, c = int(r["period_start"]), int(r["period_end"]), num(r["count"])
    if r["origin_label"] == "All European origins":
        grabbe = r
        continue
    uid = R.resolve(r["origin_label"])
    if uid is None:
        raise SystemExit(f"unmapped colonial label: {r['origin_label']}")
    add_spread(uid, a, b, c)

# enslaved Africans: SlaveVoyages estimates (direct from Africa) + intra-American (via the Caribbean)
EMBARK = {
    "Senegambia and off-shore Atlantic": "AF_SEN", "Sierra Leone": "AF_SLE", "Windward Coast": "AF_WIN",
    "Gold Coast": "AF_GOL", "Bight of Benin": "AF_BEN", "Bight of Biafra": "AF_BIA",
    "West Central Africa and St. Helena": "AF_WCA", "South-east Africa and Indian ocean islands": "AF_SEA",
}
LANDING = {  # landing region -> (name, lon, lat)
    "chesapeake": ("Chesapeake (Virginia & Maryland)", -76.35, 37.25),
    "carolinas": ("Carolinas & Georgia (Charleston, Savannah)", -79.93, 32.78),
    "gulf": ("Gulf Coast (New Orleans)", -90.07, 29.95),
    "north": ("Northern colonies (New York, Rhode Island)", -73.9, 40.9),
    "florida": ("Florida (St. Augustine)", -81.31, 29.9),
    "texas": ("Texas (Galveston)", -94.8, 29.3),
}
TAST_LAND = {"Chesapeake": "chesapeake", "Carolinas / Georgia": "carolinas", "Gulf states": "gulf", "Northern U.S.": "north"}
INTRA_LAND = {
    "Virginia": "chesapeake", "Maryland": "chesapeake", "North Carolina": "carolinas", "South Carolina": "carolinas",
    "Georgia": "carolinas", "Gulf coast": "gulf", "Florida": "florida", "Texas": "texas",
    "New York": "north", "New Jersey": "north", "Pennsylvania": "north", "Connecticut": "north", "Rhode Island": "north",
    "Massachusetts": "north", "New Hampshire": "north", "Maine": "north",
}
forced_pairs = defaultdict(lambda: [0.0] * NY)  # (origin id, landing key) -> per-year values
forced_total = 0.0
for r in rows("slave_trade_arrivals.csv"):
    y, c = int(r["year"]), num(r["count"]) or 0
    if not (Y0 <= y <= Y1) or not c:
        continue
    if r["basis"] == "tast_estimates":
        uid = R.unit(EMBARK[r["embark_region"]])["id"]
        land = TAST_LAND.get(r["disembark_region"])
    elif r["basis"] == "intra_american":
        src = r["embark_region"]
        # coastwise trade within North America is internal migration, and "Other"/"Undefined" can't be placed
        if not src.startswith(("Caribbean:", "Brazil:", "Spanish Mainland Americas:")):
            continue
        uid = R.unit("AF_CAR")["id"]
        land = INTRA_LAND.get(r["disembark_region"])
    else:
        continue
    flow[uid][y - Y0] += c
    forced_total += c
    forced_pairs[(uid, land or "east")][y - Y0] += c
check("Enslaved Africans landed (estimates + documented intra-American)", 380000 < forced_total < 460000, f"{forced_total:,.0f}")

# ---------------------------------------------------------------- flows: official 1820-2023
totals = {int(r["year"]): num(r["total"]) for r in rows("flows_totals_1820_present.csv")}
fl = rows("flows_by_origin_1820_present.csv")
tables = defaultdict(list)
for r in fl:
    tables[(int(r["period_start"]), int(r["period_end"]), r["source_id"])].append(r)
HSUS = "hsus1960_C88_114"  # 1820-1957 yearly counts by country group (OCR'd, validated cells only)
annual_tables = {k[0]: v for k, v in tables.items() if k[0] == k[1] and k[2] != HSUS}
hsus_tables = {k[0]: v for k, v in tables.items() if k[0] == k[1] and k[2] == HSUS}
# From 1989 the yearbooks list every country of birth (Table 3); the last-residence table (Table 2)
# lumps many countries into "Other" and leaves up to 11% "Unknown". Prefer birth where available.
birth_years = set()
btables = defaultdict(list)
for r in rows("flows_by_birth_1989_present.csv"):
    if r["period_start"] == r["period_end"]:
        btables[int(r["period_start"])].append(r)
for y, t in btables.items():
    annual_tables[y] = t
    birth_years.add(y)
# FY2024 and FY2025: OHSS quarterly reports, by nationality and preliminary. FY2025 has only its
# first quarter (Oct-Dec 2024) published, so the year is projected as four times that quarter.
RECENT = {}
rt = defaultdict(list)
for r in rows("flows_recent_by_birth.csv"):
    rt[int(r["period_start"])].append(r)
for y, t in rt.items():
    if y in annual_tables:
        continue
    annual_tables[y] = t
    RECENT[y] = 4.0 if "partial_q1" in t[0]["basis"] else 1.0
decade_tables = {k[0]: (k, v) for k, v in tables.items() if k[1] - k[0] == 9}

annual_known = {}
for y, t in sorted(annual_tables.items()):
    vec = table_by_origin(t, y)
    tt = table_total(t)
    s = sum(vec.values())
    check(f"{y} annual origins sum to total", tt is None or abs(s - tt) <= max(15, 0.002 * tt), f"{s:,.0f} vs {tt}")
    # yearbooks revise totals slightly; scale origins to the official Table 1 total for the year
    if y in totals and s:
        f = totals[y] / s
        check(f"{y} by-origin table within 1% of Table 1 total", abs(f - 1) < 0.01, f"ratio {f:.4f}")
        vec = {k: v * f for k, v in vec.items()}
    if y in RECENT:
        vec = {k: v * RECENT[y] for k, v in vec.items()}
        totals[y] = (tt or s) * RECENT[y]
    annual_known[y] = vec

decade_vecs = {}
for d, (key, t) in sorted(decade_tables.items()):
    decade_vecs[d] = table_by_origin(t, d)
    tt = table_total(t)
    s = sum(decade_vecs[d].values())
    check(f"{d}s decade origins sum to total", tt is None or abs(s - tt) <= max(15, 0.002 * tt), f"{s:,.0f} vs {tt}")

# 1783-1819: Grabbe-based total, split by the 1820s European mix
EURO_GROUPS = {"bri", "nwe", "see"}
mix = {k: v for k, v in decade_vecs[1820].items() if R.units[k]["group"] in EURO_GROUPS}
msum = sum(mix.values())
per_year = 9900.0
for y in range(1783, 1820):
    for k, v in mix.items():
        flow[k][y - Y0] += per_year * v / msum
check("Grabbe row present", grabbe is not None and "9,900" in grabbe["note"], "9,900 a year, 1783-1819")


def ipf(years, tot, col, seed, iters=200):
    """Scale seed[y][o] so rows sum to tot[y] and columns to col[o]."""
    m = {y: dict(seed[y]) for y in years}
    for _ in range(iters):
        for y in years:
            s = sum(m[y].values())
            if s > 0:
                f = tot[y] / s
                for o in m[y]:
                    m[y][o] *= f
        err = 0.0
        for o, target in col.items():
            s = sum(m[y].get(o, 0) for y in years)
            if s > 0:
                f = target / s
                err = max(err, abs(f - 1))
                for y in years:
                    if o in m[y]:
                        m[y][o] *= f
        if err < 1e-6:
            break
    return m


decades = sorted(decade_vecs)
shares = {}
for d in decades:
    v = decade_vecs[d]
    s = sum(v.values())
    shares[d] = {k: x / s for k, x in v.items()}


def share_at(o, y):
    """Origin share in year y, linearly interpolated between decade midpoints."""
    pts = [(d + 4.5, shares[d].get(o, 0.0)) for d in decades]
    if y <= pts[0][0]:
        return pts[0][1]
    if y >= pts[-1][0]:
        return pts[-1][1]
    for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
        if x0 <= y <= x1:
            return s0 + (s1 - s0) * (y - x0) / (x1 - x0)
    return 0.0


def hsus_category(uid):
    """Which Historical Statistics (1960) series C 89-114 group an origin belongs to."""
    u = R.units[uid]
    g = u["group"]
    if g == "bri":
        return "Ireland" if uid == "IRL" else "Great Britain"
    if uid in ("NOR", "SWE", "DNK", "ISL", "NOS"):
        return "Scandinavia"
    if uid in ("FIN", "SUN", "RUS", "LVA", "EST", "LTU", "UKR", "BLR"):
        return "U.S.S.R. and Baltic States"
    if uid == "DEU":
        return "Germany"
    if g == "nwe":
        return "Other Northwestern Europe"
    if uid == "POL":
        return "Poland"
    if uid == "ITA":
        return "Italy"
    if uid in ("ROU", "BGR", "OTE", "ALB"):
        return "Other Eastern Europe"
    if uid in ("ESP", "PRT", "GRC", "MLT", "XEU", "XSE"):
        return "Other Southern Europe"
    if g == "see":
        return "Other Central Europe"
    if uid in ("CHN", "JPN"):
        return {"CHN": "China", "JPN": "Japan"}[uid]
    if uid in ("OTA", "TUR"):
        return "Turkey in Asia"
    if g == "asi":
        return "Other Asia"
    if g == "can":
        return "Canada and Newfoundland"
    if g == "mex":
        return "Mexico"
    if g == "lat":
        return "Other America"
    if g == "afr":
        return "Africa"
    if uid in ("AUS", "NZL"):
        return "Australia and New Zealand"
    if uid == "XOC" or g == "oth" and uid not in ("XNS", "XNT"):
        return "Other Pacific Islands"
    return "All other countries"


HSUS_CATS = {"Great Britain", "Ireland", "Scandinavia", "Other Northwestern Europe", "Germany", "Poland",
             "Other Central Europe", "U.S.S.R. and Baltic States", "Other Eastern Europe", "Italy",
             "Other Southern Europe", "Turkey in Asia", "China", "Japan", "Other Asia", "Canada and Newfoundland",
             "Mexico", "Other America", "Africa", "Australia and New Zealand", "Other Pacific Islands",
             "All other countries"}


def hsus_year(y):
    """Validated group counts for year y, and the count left unvalidated (None if no table)."""
    t = hsus_tables.get(y)
    if not t:
        return None, None
    have = {}
    by_label = {r["origin_label"]: r for r in t}
    for cat in HSUS_CATS:
        r = by_label.get(cat)
        if r and num(r["count"]) is not None:
            have[cat] = num(r["count"])
    # regions with no further detail carry their count on the region row
    for reg, cat in (("Africa", "Africa"),):
        r = by_label.get(reg)
        if r and cat not in have and num(r["count"]) is not None:
            have[cat] = num(r["count"])
    rem = sum(num(r["count"]) or 0 for r in t if r["basis"] == "derived_unvalidated_remainder")
    return have, rem


hsus_used = set()
for d in decades:
    if d >= 1990:
        continue  # annual counts exist from 1988
    years = [y for y in range(d, d + 10) if y not in annual_known]
    if not years:
        continue
    col = dict(decade_vecs[d])
    for y in range(d, d + 10):
        if y in annual_known:
            for k, v in annual_known[y].items():
                col[k] = col.get(k, 0) - v
    col = {k: max(0.0, v) for k, v in col.items() if v > 0.5}
    tot = {y: totals[y] for y in years}
    # bring the decade vector to the sum of the annual totals (they agree to within rounding)
    f = sum(tot.values()) / sum(col.values())
    # 1980s: 1988-89 come from a different yearbook with coarser African/Oceanian detail, so the
    # remainder left for 1980-87 is rescaled by a few percent
    check(f"{d}s annual totals agree with decade-by-origin total", abs(f - 1) < (0.03 if len(years) < 10 else 0.01), f"ratio {f:.4f}")
    col = {k: v * f for k, v in col.items()}
    seed = {}
    for y in years:
        w = {o: max(share_at(o, y), 1e-9) for o in col}
        have, rem = hsus_year(y)
        if have:
            # shape the year with the validated group counts; groups that failed validation share
            # the unvalidated remainder in proportion to their interpolated decade shares
            cats = defaultdict(list)
            for o in col:
                cats[hsus_category(o)].append(o)
            open_w = sum(w[o] for c, os_ in cats.items() if c not in have for o in os_)
            seed[y] = {}
            for c, os_ in cats.items():
                cw = sum(w[o] for o in os_)
                if c in have:
                    amount = have[c]
                else:
                    amount = (rem or 0) * cw / open_w if open_w else 0
                for o in os_:
                    seed[y][o] = max(amount * w[o] / cw, 1e-6) if cw else 1e-6
            hsus_used.add(y)
        else:
            s = sum(w.values())
            seed[y] = {o: tot[y] * w[o] / s for o in col}
    m = ipf(years, tot, col, seed)
    for y in years:
        for o, v in m[y].items():
            flow[o][y - Y0] += v
        basis[y - Y0] = "H" if y in hsus_used else "D"
for y, vec in annual_known.items():
    if Y0 <= y <= Y1:
        for o, v in vec.items():
            flow[o][y - Y0] += v
        basis[y - Y0] = ("P" if RECENT[y] != 1 else "R") if y in RECENT else "B" if y in birth_years else "A"

for y in range(Y0, Y1 + 1):
    i = y - Y0
    if basis[i]:
        continue
    if y < 1776:
        basis[i] = "C"
    elif y < 1783:
        basis[i] = "W"
    elif y < 1820:
        basis[i] = "G"
    else:
        basis[i] = "N"  # not yet published

total = []
for y in range(Y0, Y1 + 1):
    i = y - Y0
    s = sum(v[i] for v in flow.values())
    total.append(round(s) if s > 0 or basis[i] != "N" else None)
    if y in totals and basis[i] in ("A", "B", "D", "H", "R", "P"):
        forced = sum(flow[k][i] for k in flow if R.units[k].get("forced"))
        check(f"{y} total = official + enslaved", abs(s - forced - totals[y]) < max(20, 0.001 * totals[y]),
              f"{s - forced:,.0f} vs {totals[y]:,.0f}")

# ---------------------------------------------------------------- stock (foreign-born residents)
nat = defaultdict(list)
for r in rows("stock_national_by_country.csv"):
    nat[int(r["year"])].append(r)
# 2025 and 2026: Current Population Survey yearly averages (2026 = January-September). CPS counts run
# about 2% above the ACS (2024: 51.2M vs 50.2M), so they are scaled by the 2024 ratio to join the ACS.
cps = defaultdict(list)
for r in rows("stock_recent_by_country.csv"):
    if r["source_id"] == "cps_basic_annual_avg":
        cps[int(r["year"])].append(r)
cps_ratio = table_total(nat[2024]) / table_total(cps[2024])
check("CPS 2024 vs ACS 2024 within 3%", abs(cps_ratio - 1) < 0.03, f"ACS/CPS = {cps_ratio:.4f}")
for y in (2025, 2026):
    if y in cps and y not in nat:
        nat[y] = [dict(r, count=str((num(r["count"]) or 0) * cps_ratio)) if r["count"] else r for r in cps[y]]
SY = sorted(nat)
stock_nat = {}
nat_total = []
for y in SY:
    stock_nat[y] = table_by_origin(nat[y], y)
    tt = table_total(nat[y])
    nat_total.append(tt)
    s = sum(stock_nat[y].values())
    check(f"{y} national foreign-born origins sum to total", tt is None or abs(s - tt) <= max(50, 0.003 * tt), f"{s:,.0f} vs {tt}")

st_tot = defaultdict(dict)
for r in rows("stock_state_totals.csv"):
    y = int(r["year"])
    key = r["state_fips"]
    if not key:
        n = r["state"]
        if n.startswith("Virginia"):
            key = "51"
        elif n.startswith("Dakota"):
            key = "dakota"
        else:
            continue
    st_tot[key][y] = (num(r["total_pop"]), num(r["foreign_born"]))
usp = {int(r["year"]): num(r["population"]) for r in rows("us_population_annual.csv")}
nat_pop = []
for y in SY:
    p = usp.get(y) or sum(v[y][0] for v in st_tot.values() if y in v and v[y][0])
    nat_pop.append(p or None)

# ---------------------------------------------------------------- population and the foreign-born before 1850
# Total population: colonial estimates (HSUS series Z 1-19, decadal 1610-1780), censuses 1790-1840,
# then the census/ACS state sums; geometric interpolation between benchmark years.
bench = defaultdict(float)
for r in rows("population_1610_1840.csv"):
    bench[int(r["year"])] += num(r["total"]) or 0
for y, v in zip(SY, nat_pop):
    if v:
        bench[y] = v
# Census Bureau counts and July 1 estimates (1790-2025) and its 2026 projection
for y, v in usp.items():
    if v and y >= 1790:
        bench[y] = v
bys = sorted(bench)
pop = [None] * NY
for y in range(Y0, Y1 + 1):
    if y < bys[0] or y > bys[-1]:
        continue
    k = max(i for i, b in enumerate(bys) if b <= y)
    a, va = bys[k], bench[bys[k]]
    if a == y:
        pop[y - Y0] = va
        continue
    b, vb = bys[k + 1], bench[bys[k + 1]]
    pop[y - Y0] = va * (vb / va) ** ((y - a) / (b - a))

# The census first asked birthplace in 1850. Before that, model each origin's foreign-born residents as
# last year's survivors plus this year's arrivals, with one yearly loss rate (deaths and departures)
# chosen so the modelled total for 1850 matches the 1850 census count of the foreign-born, capped at
# 90% of the estimated population.
FB1850 = nat_total[SY.index(1850)]
FIRST_CENSUS = 1850


def model_fb(m):
    stock = defaultdict(float)
    series = defaultdict(lambda: [0.0] * NY)
    for y in range(Y0, FIRST_CENSUS + 1):
        i = y - Y0
        for uid in list(stock):
            stock[uid] *= (1 - m)
        for uid, arr in flow.items():
            if arr[i]:
                stock[uid] += arr[i]
        # early Chesapeake mortality ran far above any average rate: never let the modelled
        # immigrants exceed 90% of the estimated population
        tot = sum(stock.values())
        if pop[i] and tot > 0.9 * pop[i]:
            f = 0.9 * pop[i] / tot
            for uid in stock:
                stock[uid] *= f
        if y < FIRST_CENSUS:
            for uid, v in stock.items():
                series[uid][i] = v
    return sum(stock.values()), series


lo_m, hi_m = 0.0, 0.2
for _ in range(60):
    mid = (lo_m + hi_m) / 2
    tot, _s = model_fb(mid)
    lo_m, hi_m = (mid, hi_m) if tot > FB1850 else (lo_m, mid)
fb_rate = (lo_m + hi_m) / 2
fb_total_1850, fb_model = model_fb(fb_rate)
check("modelled 1850 foreign-born matches census", abs(fb_total_1850 - FB1850) < 1000, f"{fb_total_1850:,.0f} vs {FB1850:,.0f}, loss rate {fb_rate:.4f}/yr")
# before the first colonial estimate (1610) the population was the arrivals themselves
for y in range(Y0, bys[0]):
    pop[y - Y0] = sum(arr[y - Y0] for arr in fb_model.values())
for y in range(Y0, FIRST_CENSUS):
    i = y - Y0
    tot = sum(arr[i] for arr in fb_model.values())
    check(f"{y} modelled foreign-born not above population", pop[i] is None or tot <= pop[i] * 1.0001, f"{tot:,.0f} vs {pop[i]}")

# ---------------------------------------------------------------- package
def sparse(arr, digits=0):
    nz = [i for i, v in enumerate(arr) if v > 0.5]
    if not nz:
        return None
    a, b = nz[0], nz[-1]
    return [a, [round(v) for v in arr[a:b + 1]]]


flow_o = {}
for uid, arr in flow.items():
    sp = sparse(arr)
    if sp:
        flow_o[uid] = sp

group_ids = [g["id"] for g in GROUPS]
nat_o = defaultdict(lambda: [None] * len(SY))
nat_g = {g: [0] * len(SY) for g in group_ids}
for k, y in enumerate(SY):
    for uid, v in stock_nat[y].items():
        nat_o[uid][k] = round(v)
        nat_g[R.units[uid]["group"]][k] += round(v)
# ---------------------------------------------------------------- net migration, for years without arrival counts
nm = {r["series"] + "|" + r["period"][:4]: r for r in rows("net_migration_recent.csv")}


def _nm(key):
    r = nm.get(key)
    return num(r["value"]) if r else None


def _signed(v):
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):,.0f}"


NET_NOTES = {}
if _nm("census_v2025_nim_projection|2025") is not None:
    lo, hi = num(nm["brookings_aei_jan2026_net_migration|2026"]["low"]), num(nm["brookings_aei_jan2026_net_migration|2026"]["high"])
    NET_NOTES[2026] = (f"Net migration in 2026 is projected at {_signed(_nm('census_v2025_nim_projection|2025'))} (Census Bureau, July 2025–June 2026), "
                       f"{_signed(_nm('cbo_jan2026_net_immigration|2026'))} (CBO) and {_signed(lo)} to {_signed(hi)} (Brookings/AEI).")

# ---------------------------------------------------------------- illegal immigration
un_flow, un_basis, un_info, un_pop, un_checks = illegal.build(R, Y0, Y1)
check("illegal arrivals 1990-2009 match Warren & Warren", 15e6 < un_checks["total 1990-2009 (W&W)"] < 18e6, f"{un_checks['total 1990-2009 (W&W)']:,.0f}")
flow_u = {}
for uid, arr in un_flow.items():
    sp = sparse(arr)
    if sp:
        flow_u[uid] = sp

used = set(flow_o) | set(nat_o) | set(flow_u)
origins = []
for uid in sorted(used, key=lambda u: R.units[u]["name"]):
    u = dict(R.units[uid])
    at = R.anchor(uid)
    if at:
        u["at"] = at
        u["to"] = R.coast(uid)
    origins.append(u)

forced_out = defaultdict(dict)
for (uid, land), arr in forced_pairs.items():
    sp = sparse(arr)
    if sp:
        forced_out[uid][land] = sp
landings = {k: {"name": n, "at": [lon, lat]} for k, (n, lon, lat) in LANDING.items()}

events = json.load(open(ROOT / "data" / "curated" / "events.json", encoding="utf-8"))

sources = []
seen = set()
for name in ("sources_colonial.csv", "sources_flows.csv", "sources_stock.csv", "sources_unauthorized.csv", "sources_recent.csv"):
    path = P / name
    if not path.exists():
        continue
    for r in rows(name):
        if r["source_id"] in seen or r["source_id"].endswith("_derived"):
            continue
        seen.add(r["source_id"])
        sources.append({"id": r["source_id"], "cite": r["citation"], "url": r.get("url", "")})
sources.append({"id": "ahcb", "cite": "Newberry Library, Atlas of Historical County Boundaries (state and territory boundaries, CC0).",
                "url": "https://publications.newberry.org/ahcb/"})
sources.append({"id": "historical_basemaps", "cite": "World borders 1607–1885: adapted from A. Ourednik, historical-basemaps "
                "(GPL-3.0). Simplified, renamed and re-dated for this map.",
                "url": "https://github.com/aourednik/historical-basemaps"})
sources.append({"id": "cshapes", "cite": "World borders: Europe 1816–1885 from CShapes-Europe (Cederman, Girardin, Müller-Crepon "
                "& Pengl 2025); 1886–2026 from CShapes 2.0 (Schvitz, Rüegger, Girardin, Cederman, Weidmann & Gleditsch "
                "2022), ETH Zürich, CC BY-NC-SA 4.0; 2019 borders are carried forward to 2026.",
                "url": "https://icr.ethz.ch/data/cshapes/"})
sources.append({"id": "natural_earth", "cite": "Natural Earth country boundaries via world-atlas and us-atlas (public domain / ISC); also small territories missing from the historical border sets.",
                "url": "https://www.naturalearthdata.com/"})

stock_kind = ["census" if y <= 2000 else "cps" if y in (2025, 2026) else "acs" for y in SY]


ABOUT = {
    "intro": [
        "This atlas follows migration into the territory of the present-day United States for every year from "
        f"{Y0} to {Y1}. Two measures run through it. Arrivals count the people who came in a given year, by where "
        "they came from. Immigrants living in the US count residents born abroad, by birthplace, as censuses and "
        "surveys recorded them.",
        "No single record covers four centuries, so each era uses the best source available, and the page marks "
        "which kind of number you are looking at. Official counts show as plain figures. Estimates show with a "
        "≈ sign and an outlined marker. Values between census years are interpolated.",
    ],
    "caveats": [
        "Before 1820 nobody counted arrivals. Colonial figures are historians' reconstructions with wide ranges "
        "(for example, 84,500–120,000 Germans arriving 1700–1775). They are spread evenly over each period, so "
        "year-to-year changes before 1820 are not real.",
        "Enslaved Africans were brought by force. They are counted from the SlaveVoyages estimates of captives "
        "landed directly from Africa, plus documented voyages from the Caribbean. Smuggling after the 1808 ban is "
        "undercounted, and the domestic slave trade is internal migration, so it is left out.",
        "From 1820 to 1987 the yearly totals are official, but origins by country were published by decade. Each "
        "decade's country totals are spread across its years using yearly counts for broad country groups "
        "(through 1957) or in proportion to the yearly totals (1958–1987). Per-country values in those years are "
        "shown with a ≈ sign.",
        "Illegal immigration is shown hatched, from published estimates only: 1980 census survivors for "
        "1970–1980 (a lower bound), a model between published figures for 1981–1989 and 2010–2020, Warren & "
        "Warren (2013) for 1990–2009, the Center for Migration Studies for 2016, and CBO for 2021–2025. It counts "
        "people who crossed the border illegally (including those caught and released into immigration court) and "
        "visa overstays; lawful paroles at ports of entry are left out, and the 2021–2022 CBO figures are net "
        "increases that include some parolees. Origins are split using estimates of the illegal immigrant "
        "population by country (Passel & Woodrow, INS, Pew Research Center, CMS). No credible estimate exists "
        "before 1970. People who later became permanent residents (for example the 2.7 million legalized under "
        "the 1986 amnesty, counted in 1989–1991) appear twice: once arriving illegally and once as legal "
        "residents.",
        "2024 legal arrivals are preliminary counts by nationality; 2025 is projected from its first quarter; no "
        "2026 arrival counts exist yet. Immigrants living in the US in 2025 and 2026 come from the Census Bureau's "
        "monthly Current Population Survey (2026 = January–September), scaled to the 2024 American Community "
        "Survey; the survey's margin of error is about ±0.8 million.",
        "Official arrivals record country of last residence through 1988 and country of birth from 1989; the "
        "two can differ. From 1892 they count immigrants admitted; since the 1980s they count people granted "
        "permanent residence that year, including people already living in the US. The 1989–1991 spike is the "
        "1986 amnesty (IRCA). Temporary workers, students and refugees not yet adjusted are not counted as "
        "arrivals; illegal immigration is shown separately, as above.",
        "Country names follow each source. Empires and unions that later split (Austria-Hungary, the Soviet Union, "
        "Yugoslavia, Czechoslovakia) appear under their historical names, so a country's line can start or stop "
        "when borders changed.",
        "Census birthplace data begin in 1850 and are interpolated between census years. The 1940 and 1950 "
        "censuses tabulated country of birth for white residents only; other foreign-born residents appear as "
        "not tabulated.",
        "Arrows are schematic. Each starts at an origin, joins the other arrows from its world region, and the "
        "merged arrow runs to the circle for the United States. Arrow width is proportional to the number of "
        "people, on one scale for all years unless the map is set to fit the year.",
        "The circle for the United States is sized by its population (colonial estimates before 1790) and split "
        "into people born in the US and immigrants by birthplace. Before 1850 the immigrant share is modelled "
        "from arrivals, with yearly deaths and departures set so the total matches the 1850 census.",
        "The shaded United States shows the colonies, states and territories as they stood on July 1 of the "
        "year. Colonies are drawn from their organized counties rather than their sea-to-sea charter claims.",
        "World borders show the states, empires and peoples as they stood on July 1. CShapes gives exact dates "
        "from 1886 (1816 in Europe). Before then the borders come from snapshots for selected years, each used "
        "until the next, so changes between snapshots can show late, and many borders, especially in the "
        "interior of Africa, the Americas and Asia, are approximate. Borders after 2019 are carried forward.",
    ],
}
ERAS = [
    {"years": "1607–1775", "flow": "Historians' estimates by period (Menard; Tomlins; Fogleman) and SlaveVoyages estimates for enslaved Africans.",
     "stock": "Not recorded."},
    {"years": "1776–1819", "flow": "War years without an estimate, then about 9,900 Europeans a year (Grabbe via Cohn) with an assumed origin mix; slave trade from SlaveVoyages.",
     "stock": "Not recorded."},
    {"years": "1820–1987", "flow": "Official yearly totals; origins from official decade totals (DHS Yearbook Tables 1 and 2), timed within each decade by yearly counts for 22 country groups through 1957 (Historical Statistics of the US, 1960).",
     "stock": "Census birthplace counts every ten years from 1850 (Census Working Papers 29 and 81)."},
    {"years": "1970–2023", "flow": "Illegal immigration added from published estimates (Passel & Woodrow; Warren & Warren; CMS; CBO), split by origin with illegal-population estimates (INS, Pew Research Center).",
     "stock": "Includes illegal immigrants, whom censuses and surveys count among the foreign-born."},
    {"years": "1988–2023", "flow": "Official yearly counts: by country of last residence in 1988, by country of birth from 1989 (INS and DHS yearbooks).",
     "stock": "Census 1990 and 2000; American Community Survey each year from 2005."},
    {"years": "2024–2026", "flow": "Preliminary 2024 counts by nationality and 2025 projected from its first quarter (OHSS quarterly reports); illegal immigration from CBO; no 2026 counts yet.",
     "stock": "Current Population Survey yearly averages for 2025 and 2026 (scaled to the 2024 ACS); Census Bureau population estimates and its 2026 projection."},
]

data = {
    "start": Y0, "end": Y1, "defaultYear": 1910,
    "groups": GROUPS,
    "origins": origins,
    "flow": {"total": total, "basis": "".join(basis), "o": flow_o, "u": flow_u, "uBasis": un_basis},
    "uBasisInfo": un_info,
    "netNotes": NET_NOTES,
    "illegalPop": {"years": list(un_pop), "v": list(un_pop.values())},
    "basisInfo": {
        "C": {"label": "Historians' estimate", "cls": "estimate", "band": "Historians' estimates",
              "long": "Period totals from historians (Menard, Tomlins, Fogleman), spread evenly across the years of each period. Enslaved Africans: SlaveVoyages estimates."},
        "W": {"label": "War years · Europeans not estimated", "cls": "estimate", "band": "War",
              "long": "No estimate exists for European arrivals during the Revolutionary War; the slave trade is shown where recorded."},
        "G": {"label": "Estimated total · origin mix assumed", "cls": "estimate", "band": "Estimated total",
              "long": "About 9,900 Europeans a year (Grabbe, via Cohn). Their origins are assumed to match the 1820s official counts."},
        "H": {"label": "Official total · origins partly estimated", "cls": "interp", "band": "Official totals; origins from yearly group counts and decade totals",
              "long": "The yearly total is the official count. Each country's official decade total is spread across the decade following the yearly counts for its country group (Historical Statistics of the US, 1960, series C 88–114)."},
        "D": {"label": "Official total · origins split from decade counts", "cls": "interp", "band": "Official totals; origins from decade counts",
              "long": "The yearly total is the official count. Origins are official decade totals divided among the decade's years in proportion to the yearly totals."},
        "A": {"label": "Official count", "cls": "official", "band": "Official yearly counts",
              "long": "Persons obtaining lawful permanent resident status, by country of last residence (INS Statistical Yearbook)."},
        "B": {"label": "Official count by birthplace", "cls": "official", "band": "Official yearly counts by country of birth",
              "long": "Persons obtaining lawful permanent resident status, by country of birth (INS and DHS yearbooks)."},
        "R": {"label": "Preliminary official count", "cls": "official", "band": "Preliminary",
              "long": "Fiscal 2024 permanent residents by country of nationality, from the OHSS quarterly report (preliminary)."},
        "P": {"label": "Projected from first quarter", "cls": "estimate", "band": "Projected",
              "long": "Only October-December 2024 (the first quarter of fiscal 2025) has been published; the year is shown as four times that quarter."},
        "N": {"label": "Not yet published", "cls": "estimate", "band": "",
              "long": "The arrivals count for this year has not been published yet."},
    },
    "stock": {
        "years": SY, "kind": stock_kind,
        "nat": {"total": nat_total, "pop": nat_pop, "g": nat_g, "o": {k: v for k, v in nat_o.items()}},
    },
    "forced": {"pairs": forced_out, "landings": landings},
    "pop": [round(v) if v else None for v in pop],
    "fbModel": {"rate": round(fb_rate, 5), "until": FIRST_CENSUS - 1,
                "o": {k: sp for k, sp in ((k, sparse(v)) for k, v in fb_model.items()) if sp}},
    "events": events,
    "sources": sources,
    "about": ABOUT,
    "eras": ERAS,
}
out = ROOT / "web" / "data" / "data.json"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

bad = [c for c in checks if not c[0]]
print(f"{len(checks) - len(bad)}/{len(checks)} checks passed")
for ok, label, detail in bad:
    print("  FAIL", label, detail)
if R.unmatched:
    print("unmatched labels:", R.unmatched)
print(f"origins: {len(origins)} ({sum(1 for o in origins if 'at' in o)} drawn as arrows); "
      f"stock years: {SY[0]}-{SY[-1]} ({len(SY)}); forced-migration routes: {sum(len(v) for v in forced_out.values())}")
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.2f} MB)")
