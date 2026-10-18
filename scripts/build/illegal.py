"""Yearly illegal immigration (new arrivals) by origin, 1970-2025, from published estimates.

No source publishes yearly illegal arrivals by country for the whole period, so this stitches the
published series together (see data/processed/unauthorized_NOTES.md, section 6). "Illegal" here means
people who crossed the border without inspection (whether or not they were caught and released into
immigration proceedings) plus people who overstayed a visa. Lawful paroles at ports of entry and
programme paroles (CHNV, Uniting for Ukraine) are not counted.

Yearly totals, by period:
  1970-1980  people counted in the 1980 census who had entered illegally in 1970-74 and 1975-80
             (Passel & Woodrow); survivors, so a lower bound.                         basis "L"
  1981-1989  a model: about 200,000 a year (the Census Bureau's working assumption for net growth
             in 1980-85) to 1985, then 250,000 (INS put growth at 250-500k).           basis "M"
  1990-2009  Warren & Warren (2013), new arrivals who joined the illegal population.   basis "W"
  2010-2015  a model: straight line from Warren & Warren's 2009 to CMS's 2016 value.   basis "M"
  2016       Center for Migration Studies (Warren 2019): 515,000 arrivals.             basis "C"
  2017-2020  a model: held at the 2016 level; no yearly estimate is published.         basis "M"
  2021-2022  CBO: net increase of "other foreign nationals" (also counts some
             parolees).                                                                basis "K"
  2023-2025  CBO components: crossings not encountered + people released after crossing
             between ports + visa overstays (paroles at ports left out).               basis "K"
Origin mix: 1980 and 1986 illegal-population composition (1970-89), INS 2003 entries by
Mexico / Central America / other with the INS 2000 population mix inside the last two (1990-99),
Pew's Mexican share of arrivals and Pew population mix (2000-09), CMS 2016 arrivals by country
(2010-20), and the 2021-2023 change in Pew's population by country, leaving out Ukraine, whose
arrivals came through lawful parole (2021-25).
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"

BASIS = {
    "L": {"label": "1980 census survivors (lower bound)", "long": "People counted in the 1980 census who had entered illegally in 1970-74 or 1975-80 (Passel & Woodrow). Those who died, left or were legalized before 1980 are missing."},
    "M": {"label": "modelled", "long": "No yearly estimate is published for this year; the value is a model between published estimates (see About the data)."},
    "W": {"label": "Warren & Warren estimate", "long": "Warren & Warren (2013), International Migration Review: yearly arrivals who joined the illegal immigrant population."},
    "C": {"label": "Center for Migration Studies estimate", "long": "Warren (2019), Center for Migration Studies: people who joined the illegal immigrant population in 2016, by country."},
    "K": {"label": "CBO estimate", "long": "Congressional Budget Office demographic outlooks: illegal border crossings (including people released into proceedings) and visa overstays; 2021-22 are net increases of people without permanent status."},
}


def _rows(name):
    with open(P / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build(R, Y0, Y1):
    """Return ({origin id: [per-year values]}, basis string, notes) for years Y0..Y1."""
    NY = Y1 - Y0 + 1
    inflow = _rows("unauthorized_inflows.csv")
    stock = _rows("unauthorized_population.csv")

    def pick(src, start, end=None, label="All countries", basis="gross_inflow", note_has=None):
        end = start if end is None else end
        for r in inflow:
            if (r["source_id"] == src and r["period_start"] == str(start) and r["period_end"] == str(end)
                    and r["origin_label"] == label and r["basis"] == basis
                    and (note_has is None or note_has in r["note"])):
                return _num(r["count"])
        raise KeyError((src, start, end, label, basis, note_has))

    def resolve(label, level, parent=""):
        low = label.lower()
        if "europe & canada" in low:
            return R.unit("XEU")["id"]
        if "oceania and unknown" in low:
            return R.unit("XNS")["id"]
        if "middle east" in low:
            return R.unit("XAS")["id"]
        if "sub-saharan" in low:
            return R.unit("XAF")["id"]
        if "western hemisphere" in low:
            return R.unit("XLA")["id"]
        if low.startswith("other (no country") or low.startswith("all other"):
            return R.unit("XNS")["id"]
        lvl = "residual" if level in ("region", "subregion", "residual") else level
        uid = R.resolve(label, lvl, parent)
        return uid or R.unit("XNS")["id"]

    def stock_mix(src, year, exclude=()):
        """Leaf composition of an illegal-population estimate, as shares."""
        t = [r for r in stock if r["source_id"] == src and r["year"] == str(year)]
        parents = {r["parent_label"] for r in t}
        mix = defaultdict(float)
        for r in t:
            if r["level"] == "total" or r["origin_label"] in parents:
                continue
            c = _num(r["count"])
            if not c:
                continue
            uid = resolve(r["origin_label"], r["level"], r["parent_label"])
            if uid in exclude:
                continue
            mix[uid] += c
        s = sum(mix.values())
        return {k: v / s for k, v in mix.items()}

    def blend(a, b, t):
        keys = set(a) | set(b)
        return {k: a.get(k, 0) * (1 - t) + b.get(k, 0) * t for k in keys}

    MEX = R.unit("MEX")["id"]
    CA = {R.unit(c)["id"] for c in ("SLV", "GTM", "HND", "NIC", "BLZ", "CRI", "PAN")}
    out = defaultdict(lambda: [0.0] * NY)
    basis = [""] * NY

    def put(y, total, mix, code):
        if not (Y0 <= y <= Y1):
            return
        s = sum(mix.values())
        for k, v in mix.items():
            out[k][y - Y0] += total * v / s
        basis[y - Y0] = code

    # ---- 1970-1989
    mix80 = stock_mix("passel_woodrow1984_via_chiswick1988", 1980)
    m86 = {MEX: 2100 / 3200, R.unit("XAS")["id"]: 200 / 3200}
    rest86 = 1 - sum(m86.values())
    other80 = {k: v for k, v in mix80.items() if k not in (MEX, R.unit("XAS")["id"])}
    so = sum(other80.values())
    for k, v in other80.items():
        m86[k] = m86.get(k, 0) + rest86 * v / so
    entered_70s = pick("census_passel1986_mlr", 1970, 1979, basis="entered_period")
    entered_75_80 = pick("census_passel1986_mlr", 1975, 1980, basis="entered_period")
    per_70_74 = (entered_70s - entered_75_80 * 5 / 5.25) / 5  # the 1975-80 count runs to April 1980
    per_75_80 = entered_75_80 / 5.25
    for y in range(1970, 1975):
        put(y, per_70_74, mix80, "L")
    for y in range(1975, 1981):
        put(y, per_75_80, mix80, "L")
    net_80_85 = pick("census_passel1986_mlr", 1980, 1985, basis="net_change")
    for y in range(1981, 1990):
        t = min(1, max(0, (y - 1983) / 3))
        put(y, net_80_85 if y <= 1985 else 250000, blend(mix80, m86, t), "M")

    # ---- 1990-1999: Warren & Warren totals, INS 2003 split
    ins00 = stock_mix("ins2003_warren", 2000)
    ca_mix = {k: v for k, v in ins00.items() if k in CA} or {R.unit("SLV")["id"]: 1}
    oth_mix = {k: v for k, v in ins00.items() if k not in CA and k != MEX}
    for y in range(1990, 2000):
        tot = pick("warren_warren2013_imr", y, note_has="component=entered")
        mx = pick("ins2003_warren", y, label="Mexico")
        ca = pick("ins2003_warren", y, label="Central America")
        ot = pick("ins2003_warren", y, label="All other countries")
        s = mx + ca + ot
        mix = {MEX: mx / s}
        cs, os_ = sum(ca_mix.values()), sum(oth_mix.values())
        for k, v in ca_mix.items():
            mix[k] = mix.get(k, 0) + ca / s * v / cs
        for k, v in oth_mix.items():
            mix[k] = mix.get(k, 0) + ot / s * v / os_
        put(y, tot, mix, "W")

    # ---- 2000-2009: Warren & Warren totals, Pew Mexican share and population mix
    sh_00_05 = 500000 / pick("pew2010_passel_cohn", 2000, 2005)
    sh_07_09 = 150000 / pick("pew2010_passel_cohn", 2007, 2009)
    for y in range(2000, 2010):
        tot = pick("warren_warren2013_imr", y, note_has="component=entered")
        msh = sh_00_05 if y < 2005 else sh_07_09 if y >= 2007 else (sh_00_05 + sh_07_09) / 2
        py = 2000 if y < 2003 else 2003 if y < 2005 else y
        mix = {k: v * (1 - msh) for k, v in stock_mix("pew2025_passel_krogstad", py, exclude={MEX}).items()}
        mix[MEX] = msh
        put(y, tot, mix, "W")

    # ---- 2010-2020: CMS 2016 arrivals by country, rest by Pew 2016 population mix
    cms = {}
    rest = 0
    for r in inflow:
        if r["source_id"] == "cms2019_warren" and "component=all_arrivals" in r["note"] and r["level"] != "total":
            if r["origin_label"] == "All other countries":
                rest = _num(r["count"])
            else:
                cms[resolve(r["origin_label"], "country")] = _num(r["count"])
    cms_total = pick("cms2019_warren", 2016, note_has="component=all_arrivals")
    pmix = stock_mix("pew2025_passel_krogstad", 2016, exclude=set(cms))
    mix16 = dict(cms)
    for k, v in pmix.items():
        mix16[k] = mix16.get(k, 0) + rest * v
    w09 = pick("warren_warren2013_imr", 2009, note_has="component=entered")
    for y in range(2010, 2021):
        tot = w09 + (cms_total - w09) * (y - 2009) / 7 if y < 2016 else cms_total
        put(y, tot, mix16, "C" if y == 2016 else "M")

    # ---- 2021-2025: CBO, by the 2021-2023 change in Pew's population by country
    a, b = stock_mix("pew2025_passel_krogstad", 2021), stock_mix("pew2025_passel_krogstad", 2023)
    t21 = {r["origin_label"]: _num(r["count"]) for r in stock if r["source_id"] == "pew2025_passel_krogstad" and r["year"] == "2021"}
    tot21 = t21["All countries"]
    tot23 = next(_num(r["count"]) for r in stock if r["source_id"] == "pew2025_passel_krogstad" and r["year"] == "2023" and r["origin_label"] == "All countries")
    growth = {k: max(0.0, b.get(k, 0) * tot23 - a.get(k, 0) * tot21) for k in set(a) | set(b)}
    # Ukrainians arrived almost entirely through the lawful Uniting for Ukraine parole programme
    growth[R.unit("UKR")["id"]] = 0.0
    cbo_net = {y: pick("cbo2026_demographic_outlook", y, basis="net_change", note_has="estimate;") for y in (2021, 2022)}
    for y in (2021, 2022):
        put(y, cbo_net[y], growth, "K")
    comp = lambda src, y, c: pick(src, y, note_has="component=" + c)
    t23 = sum(comp("cbo2024_demographic_outlook", 2023, c) for c in ("entered_without_encountering_CBP", "released_between_ports_USBP", "visa_overstays"))
    t24 = sum(comp("cbo2026_demographic_outlook", 2024, c) for c in ("entered_without_encountering_CBP", "released_between_ports_USBP", "visa_overstays"))
    t25 = sum(comp("cbo2026_demographic_outlook", 2025, c) for c in ("entered_without_encountering_CBP", "released_between_ports_USBP", "visa_overstays"))
    put(2023, t23, growth, "K")
    put(2024, t24, growth, "K")
    put(2025, t25, growth, "K")

    # illegal immigrant population (Pew; INS and Passel & Woodrow earlier), for context
    pop = {}
    for r in stock:
        if r["origin_label"] == "All countries" and r["level"] == "total" and _num(r["count"]):
            if r["source_id"] == "pew2025_passel_krogstad" or (r["source_id"] in ("passel_woodrow1984_via_chiswick1988", "woodrow_passel1990_via_crs") and r["year"] in ("1980", "1986")):
                pop[int(r["year"])] = _num(r["count"])
    checks = {"total 1990-2009 (W&W)": sum(sum(v[1990 - Y0:2010 - Y0]) for v in out.values()),
              "2023": sum(v[2023 - Y0] for v in out.values()), "2025": sum(v[2025 - Y0] for v in out.values())}
    return dict(out), "".join(c or " " for c in basis), BASIS, dict(sorted(pop.items())), checks
