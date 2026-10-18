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
interpolated in the page between those benchmark years.

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

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"
Y0, Y1 = 1607, 2024
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
landing = defaultdict(lambda: [0.0] * NY)
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
    if land:
        landing[land][y - Y0] += c
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
        basis[y - Y0] = "B" if y in birth_years else "A"

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
    if y in totals and basis[i] in ("A", "B", "D", "H"):
        forced = sum(flow[k][i] for k in flow if R.units[k].get("forced"))
        check(f"{y} total = official + enslaved", abs(s - forced - totals[y]) < max(20, 0.001 * totals[y]),
              f"{s - forced:,.0f} vs {totals[y]:,.0f}")

# ---------------------------------------------------------------- stock (foreign-born residents)
nat = defaultdict(list)
for r in rows("stock_national_by_country.csv"):
    nat[int(r["year"])].append(r)
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
nat_pop = []
for y in SY:
    p = sum(v[y][0] for v in st_tot.values() if y in v and v[y][0])
    nat_pop.append(p or None)

stc = defaultdict(lambda: defaultdict(list))
for r in rows("stock_state_by_country.csv"):
    stc[r["state_fips"]][int(r["year"])].append(r)

# Censuses before 2000 list only each state's main birthplaces (plus "All other countries"),
# so an origin missing from those tables is unknown, not zero.
PARTIAL_YEARS = {1900, 1910, 1920, 1950}
state_years_with_countries = set()
st_out = {}
for key in sorted(set(st_tot) | set(stc)):
    pop = [st_tot[key].get(y, (None, None))[0] for y in SY]
    fb = [st_tot[key].get(y, (None, None))[1] for y in SY]
    o = defaultdict(lambda: [None] * len(SY))
    for k, y in enumerate(SY):
        t = stc.get(key, {}).get(y)
        if not t:
            continue
        vec = table_by_origin(t, y)
        detailed = sum(1 for r in leaves(t) if r["level"] in ("country", "subcountry"))
        if detailed < 5:
            continue  # region-only tables (1990) can't name a birthplace
        state_years_with_countries.add(y)
        for uid, v in vec.items():
            o[uid][k] = round(v)
        if y not in PARTIAL_YEARS:
            # full country lists: an origin absent this year is zero, not unknown
            for uid in list(o):
                if o[uid][k] is None:
                    o[uid][k] = 0
    entry = {"pop": [round(x) if x else None for x in pop], "fb": [round(x) if x is not None else None for x in fb]}
    if o:
        covered = [k for k, y in enumerate(SY) if y in state_years_with_countries and stc.get(key, {}).get(y)
                   and any(arr[k] is not None for arr in o.values())]
        # an origin first seen later is zero in earlier full-list years
        for uid, arr in o.items():
            for k in covered:
                if arr[k] is None and SY[k] not in PARTIAL_YEARS:
                    arr[k] = 0
        entry["o"] = {uid: arr for uid, arr in o.items() if any(v for v in arr if v)}
        entry["oy"] = covered
    st_out[key] = entry
# ---------------------------------------------------------------- population before 1850
STATE_FIPS = {}
modern = json.load(open(ROOT / "web" / "geo" / "us_states_modern.topo.json", encoding="utf-8"))
for g in modern["objects"]["states"]["geometries"]:
    STATE_FIPS[g["properties"]["name"]] = g["properties"]["fips"]
STATE_FIPS.update({"Plymouth": "plymouth", "Louisiana (Orleans Territory)": "22"})
colpop = defaultdict(dict)
for r in rows("population_1610_1840.csv"):
    key = STATE_FIPS.get(r["unit"])
    if not key:
        raise SystemExit(f"unmapped population unit {r['unit']}")
    colpop[key][int(r["year"])] = colpop[key].get(int(r["year"]), 0) + (num(r["total"]) or 0)
# fold areas into the jurisdiction that governed them at the time
for child, parent, until in (("21", "51", 1792), ("54", "51", 1863), ("23", "25", 1820), ("47", "37", 1790)):
    for y, v in list(colpop.get(child, {}).items()):
        if y < until:
            colpop[parent][y] = colpop[parent].get(y, 0) + v
            del colpop[child][y]
pop_out = {}
for key, d in colpop.items():
    ys = sorted(d)
    if ys:
        pop_out[key] = {"y": ys, "v": [round(d[y]) for y in ys]}
check("1790 population", abs(sum(colpop[k].get(1790, 0) for k in colpop) - 3929214) < 5,
      f"{sum(colpop[k].get(1790, 0) for k in colpop):,.0f}")

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
used = set(flow_o) | set(nat_o) | {u for e in st_out.values() for u in e.get("o", {})}
origins = []
for uid in sorted(used, key=lambda u: R.units[u]["name"]):
    u = dict(R.units[uid])
    origins.append(u)

land_out = {}
lmax = 0
for k, arr in landing.items():
    sp = sparse(arr)
    if sp:
        name, lon, lat = LANDING[k]
        land_out[k] = {"name": name, "lon": lon, "lat": lat, "v": sp}
        lmax = max(lmax, max(arr))

events = json.load(open(ROOT / "data" / "curated" / "events.json", encoding="utf-8"))

sources = []
seen = set()
for name in ("sources_colonial.csv", "sources_flows.csv", "sources_stock.csv"):
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
sources.append({"id": "natural_earth", "cite": "Natural Earth country boundaries via world-atlas and us-atlas (public domain / ISC).",
                "url": "https://www.naturalearthdata.com/"})

stock_kind = ["census" if y <= 2000 else "acs" for y in SY]

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
        "Official arrivals record country of last residence through 1988 and country of birth from 1989; the "
        "two can differ. From 1892 they count immigrants admitted; since the 1980s they count people granted "
        "permanent residence that year, including people already living in the US. The 1989–1991 spike is the "
        "1986 amnesty (IRCA). Unauthorized migration, temporary workers and refugees not yet adjusted are not "
        "counted as arrivals.",
        "Country names follow each source. Empires and unions that later split (Austria-Hungary, the Soviet Union, "
        "Yugoslavia, Czechoslovakia) appear under their historical names, so a country's line can start or stop "
        "when borders changed.",
        "Census birthplace data begin in 1850. The 1940 and 1950 censuses tabulated country of birth for white "
        "residents only; other foreign-born residents appear as not tabulated. State counts by country of "
        "birth exist for 1900, 1910 and 1920 (each state's main birthplaces, from the 1920 census), 1950 "
        "(white residents only), 2000, and every year from 2005 (American Community Survey; small states "
        "filled from multi-year estimates). Between two of those years up to 30 years apart, a state's "
        "birthplace mix is interpolated and scaled to its foreign-born total; 1951–1999 has no state breakdown.",
        "Boundaries show each jurisdiction as it stood on July 1 of the year. Colonies are drawn from their "
        "organized counties rather than their sea-to-sea charter claims.",
    ],
}
ERAS = [
    {"years": "1607–1775", "flow": "Historians' estimates by period (Menard; Tomlins; Fogleman) and SlaveVoyages estimates for enslaved Africans.",
     "stock": "Not recorded. The map shows colonial population (Historical Statistics of the US, series Z 1–19)."},
    {"years": "1776–1819", "flow": "War years without an estimate, then about 9,900 Europeans a year (Grabbe via Cohn) with an assumed origin mix; slave trade from SlaveVoyages.",
     "stock": "Not recorded. Census population by state from 1790."},
    {"years": "1820–1987", "flow": "Official yearly totals; origins from official decade totals (DHS Yearbook Tables 1 and 2), timed within each decade by yearly counts for 22 country groups through 1957 (Historical Statistics of the US, 1960).",
     "stock": "Census birthplace counts every ten years from 1850: foreign-born totals for every state, and each state's birthplace mix for 1900, 1910, 1920 and 1950."},
    {"years": "1988–2023", "flow": "Official yearly counts: by country of last residence in 1988, by country of birth from 1989 (INS and DHS yearbooks).",
     "stock": "Census 1990 and 2000; American Community Survey each year from 2005, national and by state and country."},
]

data = {
    "start": Y0, "end": Y1, "defaultYear": 1910,
    "groups": GROUPS,
    "origins": origins,
    "flow": {"total": total, "basis": "".join(basis), "o": flow_o},
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
        "N": {"label": "Not yet published", "cls": "estimate", "band": "",
              "long": "The arrivals count for this year has not been published yet."},
    },
    "stock": {
        "years": SY, "kind": stock_kind, "partialYears": sorted(PARTIAL_YEARS), "maxGap": 30,
        "nat": {"total": nat_total, "pop": nat_pop, "g": nat_g, "o": {k: v for k, v in nat_o.items()}},
        "st": st_out,
    },
    "colonial": {
        "pop": pop_out,
        "landings": land_out,
        "landingMax": round(lmax),
        "landingNote": "SlaveVoyages estimates of captives landed directly from Africa, plus documented voyages from the Caribbean. Smuggling after 1808 is undercounted.",
    },
    "events": events,
    "sources": sources,
    "about": ABOUT,
    "eras": ERAS,
    "worldNote": "Shading follows the origin units each source reported: historical empires and unions (Austria-Hungary, the Soviet Union, Yugoslavia) and slave-trade regions are shaded as one unit across their present-day countries.",
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
print(f"origins: {len(origins)}; state keys: {len(st_out)}; stock years: {SY[0]}-{SY[-1]} ({len(SY)}); "
      f"state-by-country years: {sorted(state_years_with_countries)}")
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.2f} MB)")
