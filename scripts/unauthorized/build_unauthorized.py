#!/usr/bin/env python3
"""Build the illegal-immigration tables for the Atlas of Arrivals.

Outputs (data/processed/):
  unauthorized_population.csv   year,origin_label,level,parent_label,count,low,high,source_id,note
  unauthorized_inflows.csv       period_start,period_end,origin_label,level,parent_label,count,low,high,basis,source_id,note
  unauthorized_indicators.csv    year,series,count,source_id,note
  sources_unauthorized.csv       source_id,citation,url,accessed,notes

Inputs: data/raw/<source_slug>/ (fetch with scripts/unauthorized/fetch_raw.sh). Tables that exist as text or
spreadsheets are parsed; numbers that appear only in report prose are entered below together with an
"evidence" snippet that must occur in the saved raw file, and every such check is reported at the end.
Hand transcriptions of scanned tables / images live next to their source in data/raw (transcribed_*.csv).

Terminology: the user-facing wording is "illegal immigrants / illegal immigration". The file names keep the
word "unauthorized" (as wired into the site build). Every series that also counts people with a temporary
legal permission (parolees, pending asylum applicants, TPS, DACA...) says so in its note.

Run: python3 -I scripts/unauthorized/build_unauthorized.py
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
ACCESSED = "2026-10-18"

STOCK, FLOW, IND = [], [], []
CHECKS = {"ok": 0, "missing_file": [], "not_found": []}
_TEXT_CACHE = {}


def _norm(s):
    s = s.replace("​", "").replace("­", "").replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def text(rel):
    p = RAW / rel
    if rel not in _TEXT_CACHE:
        _TEXT_CACHE[rel] = _norm(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else None
    return _TEXT_CACHE[rel]


def evidence(rel, *snippets):
    """Assert each snippet occurs (whitespace-normalised) in the raw file; record the outcome."""
    t = text(rel)
    if t is None:
        CHECKS["missing_file"].append(rel)
        return
    for s in snippets:
        if _norm(s) in t:
            CHECKS["ok"] += 1
        else:
            CHECKS["not_found"].append((rel, s))


def num(s):
    s = str(s).strip().replace(",", "")
    if s in ("", "-", "***", "NA", "(x)", "None") or s.startswith("<"):
        return None
    if s.startswith("(") and s.endswith(")"):
        return -int(s[1:-1])
    return int(float(s))


def stock(year, label, level, parent, count, src, note, low=None, high=None):
    STOCK.append(dict(year=year, origin_label=label, level=level, parent_label=parent, count=count,
                      low=low, high=high, source_id=src, note=note))


def flow(p0, p1, label, level, parent, count, basis, src, note, low=None, high=None):
    FLOW.append(dict(period_start=p0, period_end=p1, origin_label=label, level=level, parent_label=parent,
                     count=count, low=low, high=high, basis=basis, source_id=src, note=note))


def ind(year, series, count, src, note):
    IND.append(dict(year=year, series=series, count=count, source_id=src, note=note))


ALL = "All countries"
TEMP_INCL = ("includes people with temporary protection from deportation (parolees, pending asylum applicants, "
             "TPS, DACA, people released at the border with a notice to appear)")

# =====================================================================================================
# 1. Pew Research Center 2025 (Passel & Krogstad): 1990-2023, regions + 18 countries, 90% margins of error
#    RECOMMENDED PRIMARY CONTINUOUS STOCK SERIES
# =====================================================================================================
PEW_REGION = {"Brazil": "South America", "Canada": "Europe & Canada", "China": "Asia", "Colombia": "South America",
              "Cuba": "Caribbean", "Dominican Republic": "Caribbean", "Ecuador": "South America",
              "El Salvador": "Central America", "Guatemala": "Central America", "Haiti": "Caribbean",
              "Honduras": "Central America", "India": "Asia", "Nicaragua": "Central America", "Peru": "South America",
              "Philippines": "Asia", "Ukraine": "Europe & Canada", "Venezuela": "South America"}


def build_pew2025():
    import openpyxl
    f = RAW / "pew_2025_unauthorized" / "detailed_tables_country-trends.xlsx"
    ws = openpyxl.load_workbook(f, data_only=True).active
    rows = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
    h = next(i for i, r in enumerate(rows) if r[1] == "Region/country of birth")
    hdr, rows = rows[h], rows[h - 2:]
    years = [2000 + int(h[1:]) if int(h[1:]) < 50 else 1900 + int(h[1:]) for h in hdr[2:25]]
    moe_years = [2000 + int(h[1:]) if int(h[1:]) < 50 else 1900 + int(h[1:]) for h in hdr[26:48]]
    data, section = {}, None
    for r in rows[3:]:
        if r[0] in ("Regions", "Countries"):
            section = r[0]
            continue
        name = r[0] if r[0] == "All countries" else r[1]
        if not name or str(name).startswith(("Note", "Source", "Publication")) or r[2] is None:
            continue
        est = dict(zip(years, r[2:25]))
        moe = dict(zip(moe_years, r[26:48]))
        data[name] = (section, est, moe)
    src = "pew2025_passel_krogstad"
    regions = [n for n, v in data.items() if v[0] == "Regions" and n != "Other than Mexico"]
    countries = [n for n, v in data.items() if v[0] == "Countries"]
    for y in years:
        ref = "Apr 1 (1990 census, via Warren & Warren 2013)" if y == 1990 else ("Mar 1 (CPS)" if y < 2005 else "Jul 1 (ACS)")
        base = f"ref={ref}; primary series; {TEMP_INCL}"

        def add(name, level, parent, extra=""):
            c = num(data[name][1][y])
            m = num(data[name][2].get(y)) if data[name][2].get(y) not in (None, "(x)") else None
            lo, hi = (max(c - m, 0), c + m) if (c is not None and m is not None) else (None, None)
            stock(y, name, level, parent, c, src, base + ("; 90% CI" if m else "; no margin of error published") + extra, lo, hi)
            return c

        tot = add("All countries", "total", "")
        mex = add("Mexico", "country", ALL)
        reg_sum = 0
        for rg in regions:
            if rg == "Mexico":
                continue
            rc = add(rg, "region", ALL, "; region as defined by Pew (Middle East = Middle East-North Africa; Asia = South, Central and East Asia)")
            reg_sum += rc
            cs = 0
            for c in countries:
                if PEW_REGION[c] != rg:
                    continue
                v = data[c][1][y]
                if num(v) is None:
                    continue  # '(x)' = no estimate (Cuba before 2021), '<10,000' (Ukraine 1998): left in the residual
                add(c, "country", rg)
                cs += num(v)
            stock(y, f"Other {rg} (derived)", "residual", rg, rc - cs, src,
                  base + "; derived = region minus listed countries (rounded inputs; may be slightly off or negative)")
        stock(y, "Oceania and unknown (derived)", "residual", ALL, tot - mex - reg_sum, src,
              base + "; derived = total minus Mexico minus regions (Pew: 'total includes a residual (not shown) from other countries')")
    evidence("pew_2025_unauthorized/report.txt", "Reached a Record 14 Million in 2023")
    evidence("pew_2025_unauthorized/report.txt", "The 1995-2003 estimates are", "the number of unauthorized immigrants as of March 1")

    # illegal-only part: people without any protection from deportation
    s2 = "pew2025_no_protection"
    stock(2023, ALL, "total", "", 8_000_000, s2, "ref=Jul 1; illegal immigrants with NO protection from deportation "
          "(Pew figure: 'No deportation protection 57% (8.0 million)'); the other 6.0 million had temporary protection")
    stock(2021, ALL, "total", "", 7_800_000, s2, "derived = 10.5 million total minus 2.7 million with some protection (both from Pew 2025 text)")
    stock(2007, ALL, "total", "", 11_700_000, s2, "derived = 12.2 million total minus about 500,000 with some protection (both from Pew 2025 text)")
    evidence("pew_2025_unauthorized/report.txt", "(8.0 million)", "(6.0 million)", "up from 2.7 million in 2021",
             "(12.2 million), about", "500,000 had some protection from deportation")


# =====================================================================================================
# 2. DHS OIS/OHSS (Baker & Warren 2024, Appendix Table A2-1): Jan 1 2000, 2005-2020, 2022; top-10 countries
# =====================================================================================================
def build_ohss():
    rel = "archiveit_ohss_unauth/ohss_2018_2022.txt"
    lines = (RAW / rel).read_text(errors="replace").splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().startswith("Country") and "2000" in l and "2022" in l)
    cols = lines[i].split()[1:]
    assert len(cols) == 21, cols
    names = ["Total", "Mexico", "Guatemala", "El Salvador", "Honduras", "Philippines", "Venezuela", "Colombia",
             "Brazil", "India", "China", "All others"]
    tab = {}
    for l in lines[i + 1:]:
        s = l.strip()
        if s.startswith("State"):
            break
        for n in names:
            if s.startswith(n + " ") and n not in tab:
                vals = s[len(n):].split()
                assert len(vals) == 21, (n, vals)
                tab[n] = [num(v) for v in vals]
    assert set(tab) == set(names), set(names) - set(tab)
    basis = {"2000": "2000 census", "2005": "ACS tied to 2000 census", "2010": "ACS tied to 2000 census",
             "2010*": "ACS tied to 2010 census", "2015": "2010-15 method", "2015**": "2015-18 updated method",
             "2018": "2015-18 updated method", "2018**": "2018-20 updated method", "2022": "ACS tied to 2020 census"}
    primary_cols = {"2000", "2005", "2006", "2007", "2008", "2009", "2010*", "2011", "2012", "2013", "2014", "2015**",
                    "2016", "2017", "2018**", "2019", "2020", "2022"}
    for j, col in enumerate(cols):
        y = int(col.strip("*"))
        prim = col in primary_cols
        src = "ohss2024_baker_warren" if prim else "ohss2024_baker_warren_prev_basis"
        b = basis.get(col) or ("ACS tied to 2000 census" if y < 2010 else "ACS tied to 2010 census" if y < 2015
                               else "2015-18 updated method" if y < 2018 else "2018-20 updated method")
        note = (f"ref=Jan 1; basis={b}; {'latest-vintage value for this year' if prim else 'superseded value on the earlier basis (series break year)'}; "
                f"{TEMP_INCL}; persons who entered before 1980 assumed legal")
        stock(y, ALL, "total", "", tab["Total"][j] * 1000, src, note)
        tot_c = 0
        for n in names[1:-1]:
            v = tab[n][j]
            if v is None:
                continue
            lab = "China" + (" (incl. Hong Kong and Macau)" if col in ("2018**", "2019", "2020", "2022") else "")
            extra = ""
            if (n == "Colombia" and y <= 2013) or (n == "Brazil" and 2010 <= y <= 2015) or (n == "Venezuela" and 2007 <= y <= 2015):
                extra = "; approximation per OHSS note"
            stock(y, lab if n == "China" else n, "country", ALL, v * 1000, src, note + extra)
            tot_c += v
        oth = tab["All others"][j]
        stock(y, "All other countries", "residual", ALL, oth * 1000, src,
              note + "; includes countries not shown (incl. Venezuela where n/a)")
    evidence(rel, "Estimates of the Unauthorized population (in thousands) by Country of Birth and State of Residence",
             "Persons who are beneficiaries of Temporary Protected Status (TPS), Deferred Action for Childhood Arrivals (DACA)",
             "Individuals who were paroled into the United States are considered to be unauthorized immigrants")


# =====================================================================================================
# 3. INS 2003 (Warren): annual Jan 1 1990-2000 (Table C) and 75 countries 1990/2000 (Table 2)
# =====================================================================================================
def build_ins2003():
    rel = "archiveit_ohss_unauth/ins_1990_2000.txt"
    lines = (RAW / rel).read_text(errors="replace").splitlines()
    src = "ins2003_warren"
    note0 = ("ref=Jan 1; definition excludes refugees, asylees and parolees with work authorization and people allowed "
             "to remain under legislative provisions/court rulings (closest to an illegal-only concept), but Honduras 2000 "
             "includes 105,000 granted TPS in Dec 1998")
    # Table C
    k = next(i for i, l in enumerate(lines) if l.startswith("Table C."))
    tabc = {}
    for l in lines[k:k + 40]:
        m = re.match(r"^(19\d\d|2000)\s+([\d,]+)(.*)$", l.strip())
        if m:
            rest = m.group(3).split()
            tabc[int(m.group(1))] = [num(m.group(2))] + [num(x) for x in rest]
    assert len(tabc) == 11, sorted(tabc)
    # Table 2 (countries, thousands)
    s = next(i for i, l in enumerate(lines) if l.startswith("Table 2. Estimated Unauthorized Resident Population, by Country"))
    e = next(i for i in range(s, len(lines)) if lines[i].startswith("Source: INS Office of Policy and Planning"))
    regions = {"Europe", "Asia", "Africa", "Oceania", "North America", "South America"}
    pat = re.compile(r"^([A-Z][A-Za-z.,&' ]*?)\s+(-|\d[\d,]*)\s+(-|\d[\d,]*)\s+(-?\d[\d,]*|-)\s+(\d[\d,]*)\s*$")
    t2, cur = [], None
    for l in lines[s:e]:
        m = pat.match(l.strip())
        if not m:
            continue
        name = m.group(1).strip()
        if name == "Hondurasa":
            name = "Honduras"
        v2000, v1990 = num(m.group(2)) or 0, num(m.group(3)) or 0
        if name == "All countries":
            lvl, par = "total", ""
        elif name in regions:
            lvl, par, cur = "region", ALL, name
        elif name.startswith("Other "):
            lvl, par = "residual", cur
        else:
            lvl, par = "country", cur
        t2.append((name, lvl, par, v2000, v1990))
    assert sum(1 for r in t2 if r[1] == "country") >= 60, len(t2)
    for y in range(1990, 2001):
        if y in (1990, 2000):
            for name, lvl, par, v2000, v1990 in t2:
                v = v2000 if y == 2000 else v1990
                lab = {"Other North America": "Other North America (Caribbean & Central America n.e.c.)",
                       "Micronesia, Federated States": "Micronesia (Federated States)"}.get(name, name)
                stock(y, lab, lvl, par, v * 1000, src, note0 + "; Table 2 (thousands; '-' = rounds to zero)")
        else:
            stock(y, ALL, "total", "", tabc[y][0] * 1000, src, note0 + "; Table C")
    evidence(rel, "Table C. Annual Estimates of Population and Net Change", "asylees, and parolees who have work authorization")
    return tabc


# =====================================================================================================
# 4. Warren & Warren 2013 (IMR): annual Jan 1 1990-2010 and components of change
# =====================================================================================================
def build_ww2013():
    rel = "pmc_warren_warren_2013/PMC3744247.txt"
    t = " ".join((RAW / rel).read_text(errors="replace").split())
    i = t.index("Table 3. Estimates of the Total Unauthorized Immigrant Population of the United States and Annual Components")
    j = t.index("Open in a new tab", i)
    toks = [x.strip() for x in " ".join(t[i:j].split()).split("|")]
    rows = {}
    for k, tok in enumerate(toks):
        if re.fullmatch(r"(19\d\d|20(0\d|10))", tok) and k + 1 < len(toks) and re.fullmatch(r"\d{1,2},\d{3}", toks[k + 1]):
            vals = []
            for x in toks[k + 2:k + 9]:
                if re.fullmatch(r"(19\d\d|20\d\d)", x):
                    break
                if x:
                    vals.append(num(x))
            rows[int(tok)] = [num(toks[k + 1])] + vals
    assert set(rows) == set(range(1990, 2011)), sorted(rows)
    src = "warren_warren2013_imr"
    for y, r in sorted(rows.items()):
        stock(y, ALL, "total", "", r[0] * 1000, src,
              "ref=Jan 1; residual method (2000 census, ACS 2005-2010); legally resident count omits asylees/parolees with "
              "work authorization, pending I-485 and TPS (577,000 in 2000), so modestly overstates illegal immigrants")
    evidence(rel, "Precise counts of the legally resident population should", "Temporary Protected Status")
    return rows


# =====================================================================================================
# 5. Other stock estimates (prose, scanned tables, secondary reproductions)
# =====================================================================================================
def build_other_stocks():
    # INS 1997 (1996 Yearbook, Table P): October 1996, top 20 countries
    for fname, src, year, extra in [
            ("archiveorg_ins_yearbooks/transcribed_ins_yb1996_tableP_oct1996.csv", "ins_yb1996_tableP", 1996,
             "ref=Oct 1996; INS 1997 estimate (later revised to about 5.8 million by INS 2003); includes people permitted to remain pending "
             "status decisions (e.g., Salvadorans with DED) per yearbook text; Oct 1996 range 4.6-5.4 million"),
            ("archiveorg_ins_yearbooks/transcribed_ins_yb1994_tableN_oct1992.csv", "ins_yb1994_tableN", 1992,
             "ref=Oct 1992; original INS 1994 estimate (revised to 3.9 million in the 1996 Yearbook); excludes short-term "
             "seasonal workers and visitors overstaying briefly")]:
        with open(RAW / fname) as fh:
            for r in csv.DictReader(fh):
                n, c = r["country_of_origin"], int(r["population"])
                if n == "All countries":
                    lo, hi = (4_600_000, 5_400_000) if year == 1996 else (None, None)
                    stock(year, ALL, "total", "", c, src, extra + "; hand transcription of scanned table", lo, hi)
                elif n == "Other":
                    stock(year, "All other countries", "residual", ALL, c, src, extra)
                else:
                    stock(year, "Bahamas" if n == "Bahamas, The" else n, "country", ALL, c, src, extra)
    evidence("archiveorg_ins_yearbooks/doj-reports_j-212-10996_djvu.txt", "with a range of about 4.6 to 5.4 million",
             "revised estimate of 3.9 million for October 1992", "permitted to remain in the United States pending")
    evidence("archiveorg_ins_yearbooks/doj-reports_j-212-10994_djvu.txt", "All countries 3,379,000", "1,321,000",
             "grew from 2.2 million in 1988", "peak of nearly 5 million at the beginning of the")
    stock(1992, ALL, "total", "", 3_900_000, "ins_yb1996_text", "ref=Oct 1992; revised INS estimate published in the 1996 Yearbook text (Table N value was 3,379,000)")
    stock(1988, ALL, "total", "", 2_200_000, "ins_yb1994_text", "ref=fall 1988 (just after IRCA legalization); INS 1994 Yearbook text: 'grew from 2.2 million in 1988'")
    stock(1987, ALL, "total", "", 5_000_000, "ins_yb1994_text",
          "approximate: INS 1994 Yearbook says the population 'reached a peak of nearly 5 million at the beginning of the IRCA legalization program' (May 1987)",
          None, 5_000_000)

    # CMS / Warren 2019 essay: 2010 and 2017, top 15 countries (thousands, image tables)
    src = "cms2019_warren"
    with open(RAW / "perma_cc_unauth/transcribed_cms2019_tables2_3.csv") as fh:
        rows = [r for r in csv.DictReader(fh) if r["table"] == "T2"]
    for r in rows:
        y, n, v = int(r["period"]), r["country"], int(r["thousands"]) * 1000
        note = "ref=mid-year ACS-based (CMS); hand transcription of image Table 2; includes people with TPS/DACA and pending cases"
        if n == "All countries":
            stock(y, ALL, "total", "", v, src, note)
        elif n == "All other":
            stock(y, "All other countries", "residual", ALL, v, src, note)
        else:
            stock(y, n, "country", ALL, v, src, note)
    evidence("perma_cc_unauth/cms_warren2019_essay.txt", "the total undocumented population declined by about one million from 2010 to 2017",
             "Of the estimated 515,000 arrivals in 2016, a total of 320,000")

    # CMS / Warren 2025 (JMHS) via States Newsroom: 2023 = 12.2 million; +2 million since 2020; Venezuela
    src = "cms2025_warren_via_statesnewsroom"
    rel = "cms_warren2025_secondary/royalexaminer_states_newsroom_2025-05-29.txt"
    evidence(rel, "increased to 12.2 million in 2023", "grew by 2 million from 2020 to 2023",
             "increased from 55,000 in 2013 to 220,000 in 2020", "doubled in 2023 to 445,000",
             "includes not only people in the U.S. without legal authorization, but immigrants in programs that provide temporary legal status")
    n2 = "CMS estimate reported by States Newsroom (2025-05-29); " + TEMP_INCL
    stock(2023, ALL, "total", "", 12_200_000, src, n2)
    stock(2023, "Venezuela", "country", ALL, 445_000, src, n2)
    stock(2023, "All other countries (derived)", "residual", ALL, 12_200_000 - 445_000, src, n2 + "; derived")
    stock(2020, ALL, "total", "", 10_200_000, src, n2 + "; derived = 12.2 million minus 'grew by 2 million from 2020 to 2023'")
    stock(2020, "Venezuela", "country", ALL, 220_000, src, n2)
    stock(2020, "All other countries (derived)", "residual", ALL, 10_200_000 - 220_000, src, n2 + "; derived")

    # MPI 2019 (pooled 2015-19 ACS weighted to 2019; Perma.cc capture Sept 2022)
    src = "mpi_profile2019"
    rel = "perma_cc_unauth/mpi_profile_US_2022capture.txt"
    evidence(rel, "Unauthorized Population | 11,047,000", "Mexico | 5,313,000", "El Salvador | 741,000", "Guatemala | 724,000",
             "India | 553,000", "Honduras | 490,000", "Mexico and Central America | 7,381,000", "Caribbean | 327,000",
             "South America | 907,000", "Europe/Canada/Oceania | 440,000", "Asia | 1,697,000", "Africa | 295,000",
             "pooled 2015-19 American Community Survey")
    n3 = "ref=2019 (pooled 2015-19 ACS + SIPP weighted to 2019 totals by J. Van Hook); MPI's 'unauthorized' count also includes people with TPS, DACA or pending asylum"
    stock(2019, ALL, "total", "", 11_047_000, src, n3)
    reg = {"Mexico and Central America": (7_381_000, {"Mexico": 5_313_000, "El Salvador": 741_000, "Guatemala": 724_000, "Honduras": 490_000}),
           "Caribbean": (327_000, {}), "South America": (907_000, {}), "Europe/Canada/Oceania": (440_000, {}),
           "Asia": (1_697_000, {"India": 553_000}), "Africa": (295_000, {})}
    for rg, (rv, cs) in reg.items():
        stock(2019, rg, "region", ALL, rv, src, n3)
        for c, v in cs.items():
            stock(2019, c, "country", rg, v, src, n3)
        stock(2019, f"Other {rg} (derived)" if cs else f"{rg} (no country detail in source)", "residual", rg,
              rv - sum(cs.values()), src, n3 + ("; derived" if cs else ""))

    # MPI 2023 fact sheet (Oct 2025; file revised Aug 2026)
    src = "mpi2025_factsheet"
    rel = "mpi_factsheet_2026/mpi-unauthorized-immigrants-fact-sheet-2025-final.txt"
    top = {"Mexico": 5_530_000, "Guatemala": 1_402_000, "Honduras": 1_098_000, "El Salvador": 1_078_000, "Venezuela": 486_000,
           "Colombia": 351_000, "Philippines": 294_000, "Brazil": 286_000, "Ecuador": 225_000, "Dominican Republic": 212_000}
    evidence(rel, "Total 13,738,000", "All Other Countries 2,777,000", "Mexico and Central", "America, 68%", "South America, 12%",
             "Caribbean, 4%", "Europe, Canada, Oceania, 7%", "Asia, 6%", "Africa, 3%",
             "as many as 4 million people", *[f"{k} {v:,}" for k, v in top.items()])
    n4 = "ref=mid-2023 (pooled 2019-23 ACS + SIPP weighted to 2023 totals by J. Van Hook); " + TEMP_INCL + " (MPI: up to 4 million in mid-2023)"
    T = 13_738_000
    stock(2023, ALL, "total", "", T, src, n4)
    reg_of = {"Mexico": "Mexico and Central America", "Guatemala": "Mexico and Central America", "Honduras": "Mexico and Central America",
              "El Salvador": "Mexico and Central America", "Venezuela": "South America", "Colombia": "South America",
              "Brazil": "South America", "Ecuador": "South America", "Philippines": "Asia", "Dominican Republic": "Caribbean"}
    shares = {"Mexico and Central America": 68, "South America": 12, "Caribbean": 4, "Europe/Canada/Oceania": 7, "Asia": 6, "Africa": 3}
    for rg, pct in shares.items():
        rv = round(T * pct / 100)
        stock(2023, rg, "region", ALL, rv, src, n4 + f"; derived = {pct}% (rounded share, Figure 4) x total; range = +/-0.5 pp",
              round(T * (pct - 0.5) / 100), round(T * (pct + 0.5) / 100))
        cs = {c: v for c, v in top.items() if reg_of[c] == rg}
        for c, v in cs.items():
            stock(2023, c, "country", rg, v, src, n4)
        stock(2023, f"Other {rg} (derived)" if cs else f"{rg} (no country detail in source)", "residual", rg,
              rv - sum(cs.values()), src, n4 + "; derived from rounded regional share")
    stock(2023, ALL, "total", "", T - 4_000_000, "mpi2025_without_liminal",
          "derived lower bound for illegal immigrants without any temporary status: 13,738,000 minus MPI's 'as many as 4 million' "
          "with TPS, DACA, pending asylum or parole in mid-2023", T - 4_000_000, None)

    # Census Bureau, 1980 census (Warren & Passel 1987; Passel & Woodrow 1984 via Chiswick 1988; Passel 1986 MLR)
    src = "passel_woodrow1984_via_chiswick1988"
    rel = "eric_pre1980/ED296133_excerpt_ch2_p19-21.txt"
    evidence(rel, "Number 135 100.0 2,057 100.0", "Mexico 101 74.8 1,131 55.0", "Other W. Hem. 12 8.9 477 23.2",
             "Europe 9 6.7 150 7.3", "Asia 10 7.4 213 10.4", "Other 3 2.0 86 4.2")
    evidence("bls_mlr_1986_passel/mlr_1986_09_rpt2full.txt", "1980 census count of aliens shows that 2,057,000 undocu",
             "1,131,000, or 55 percent, were born in Mexico")
    n5 = ("ref=Apr 1 1980; undocumented aliens COUNTED in the 1980 census only (those missed by the census are excluded; "
          "DHS cites a total of 2-4 million for 1980)")
    stock(1980, ALL, "total", "", 2_057_000, src, n5)
    stock(1980, "Mexico", "country", ALL, 1_131_000, src, n5)
    for lab, v in [("Other Western Hemisphere", 477_000), ("Europe", 150_000), ("Asia", 213_000), ("Other", 86_000)]:
        stock(1980, f"{lab} (no country detail in source)", "residual", ALL, v, src, n5)
    evidence("archiveit_ohss_unauth/ois_jan2011.txt", "lion in 1980 (Warren and Passel, 1987) to 8.5 million by 2000")
    stock(1980, ALL, "total", "", None, "ois2012_hoefer_rytina_baker",
          "ref=1980; total population range 'from 2-4 million in 1980 (Warren and Passel, 1987)' as cited by DHS OIS (Jan 2011 report)",
          2_000_000, 4_000_000)

    # Woodrow & Passel 1990 (June 1986 / June 1988 CPS) via CRS RL33874
    src = "woodrow_passel1990_via_crs"
    rel = "crs_everycrsreport/RL33874.txt"
    evidence(rel, "estimate of 3.2 million unauthorized resident aliens in 1986", "the estimate for 1988 dropped to 1.9 million",
             "from 2.1 million in 1986", "from 0.2 million in 1986")
    n6 = "Census Bureau demographers (Woodrow & Passel), CPS-based, as summarized by CRS RL33874 (2014)"
    stock(1986, ALL, "total", "", 3_200_000, src, n6 + "; ref=June 1986")
    stock(1986, "Mexico", "country", ALL, 2_100_000, src, n6 + "; 69% of total")
    stock(1986, "Asia (no country detail in source)", "residual", ALL, 200_000, src, n6 + "; 6% of total")
    stock(1986, "All other countries (derived)", "residual", ALL, 900_000, src, n6 + "; derived")
    stock(1988, ALL, "total", "", 1_900_000, src, n6 + "; ref=June 1988, after IRCA legalization applications")

    # INS testimony 1981 and Census Bureau review 1980 (Siegel, Passel & Robinson)
    evidence("eric_pre1980/ED210367.txt", "illegal alien population estimate as 6 million")
    stock(1981, ALL, "total", "", None, "ins1981_meissner_testimony",
          "range only: 'between 3 and 6 million illegal aliens in this Country' (INS Acting Commissioner, Oct 1981; scan reads '3 and t million', "
          "upper limit stated as 6 million on p. 7)", 3_000_000, 6_000_000)
    evidence(rel_spr := "eric_pre1980/ED296133_excerpt_ch2_p19-21.txt", "almost certainly below 6.0 million",
             "possibly only 3.5 to 5.0 million", "almost certainly less than 3.0 million", "possibly only 1.5 to 2.5")
    stock(1978, ALL, "total", "", None, "siegel_passel_robinson1981_via_chiswick1988",
          "range only: 'almost certainly below 6.0 million, and may be substantially less, possibly only 3.5 to 5.0 million' for 'some recent year, say 1978'",
          3_500_000, 6_000_000)
    stock(1978, "Mexico", "country", ALL, None, "siegel_passel_robinson1981_via_chiswick1988",
          "range only: Mexican component 'almost certainly less than 3.0 million ... possibly only 1.5 to 2.5 million'", 1_500_000, 3_000_000)

    # Census Bureau 2001 residual for 2000 (via INS 2003)
    evidence("archiveit_ohss_unauth/ins_1990_2000.txt", "the Census Bureau estimated that 8.7 million foreign-born persons were in the")
    stock(2000, ALL, "total", "", 8_700_000, "census2001_residual_via_ins2003",
          "ref=2000; Census Bureau 'residual foreign-born population (including both unauthorized and quasi-legal migrants)', as quoted by INS 2003")

    # Yale (Fazel-Zarandi, Feinstein & Kaplan 2018), demographic flow model
    rel = "perma_cc_unauth/yale_plosone_2018.txt"
    evidence(rel, "The mean of our simulations", "is 22.1 million", "ninety-five percent probability interval is [16.2,29.5]",
             "Our conservative estimate for 2016 is 16.7 million")
    stock(2016, ALL, "total", "", 22_100_000, "yale2018_fazelzarandi",
          "ref=2016; flow-model simulation mean with 95% probability interval; conservative variant 16.7 million; outlier vs. residual-method estimates (~11 million)",
          16_200_000, 29_500_000)


# =====================================================================================================
# 6. Inflows / net change / period of entry
# =====================================================================================================
def build_flows(tabc, ww):
    # INS 2003 Table C (calendar years 1990-1999, thousands)
    src = "ins2003_warren"
    comp = ["population_jan1", "net_change", "entered", "left_total", "emigrated", "died", "removed_by_INS",
            "adjusted_to_legal_status_in_US", "left_briefly_returned_as_LPR"]
    for y in range(1990, 2000):
        r = tabc[y]
        d = dict(zip(comp, r))
        flow(y, y, ALL, "total", "", d["entered"] * 1000, "gross_inflow", src,
             "component=entered; people who moved to the US in the year and still lived here illegally at year end; excludes parolees/asylees with work authorization")
        flow(y, y, ALL, "total", "", d["net_change"] * 1000, "net_change", src, "component=net_change (Jan 1 to Jan 1)")
        for c in comp[3:]:
            flow(y, y, ALL, "total", "", d[c] * 1000, "other", src, f"component={c} (outflow from the illegal-immigrant population)")
    # Chart 3 labels: entries by Mexico / Central America / all other (thousands); rows sum to Table C col 3
    ch3 = {1990: (454, 35, 260), 1991: (390, 32, 195), 1992: (380, 28, 149), 1993: (403, 32, 129), 1994: (473, 48, 165),
           1995: (513, 59, 200), 1996: (450, 55, 172), 1997: (437, 57, 160), 1998: (537, 73, 208), 1999: (629, 82, 257)}
    for y, (mx, ca, ot) in ch3.items():
        assert abs(mx + ca + ot - tabc[y][2]) <= 2, (y, mx + ca + ot, tabc[y][2])
        n = "component=entered; data labels of Chart 3 (log-scale chart), consistent with Table C totals within rounding"
        flow(y, y, "Mexico", "country", ALL, mx * 1000, "gross_inflow", src, n)
        flow(y, y, "Central America", "region", ALL, ca * 1000, "gross_inflow", src, n)
        flow(y, y, "Central America (no country detail in source)", "residual", "Central America", ca * 1000, "gross_inflow", src, n)
        flow(y, y, "All other countries", "residual", ALL, ot * 1000, "gross_inflow", src, n)
    evidence("archiveit_ohss_unauth/ins_1990_2000.txt", "Chart 3. Annual Estimates of Unauthorized Immigration from Mexico, Central",
             "454", "629", "257", "82")

    # Warren & Warren 2013 Table 3 (calendar years 1990-2009, thousands)
    src = "warren_warren2013_imr"
    names = ["population_jan1", "net_change", "entered", "left_total", "emigrated", "adjusted_to_legal_status", "removed_by_DHS", "died"]
    for y in range(1990, 2010):
        d = dict(zip(names, ww[y]))
        flow(y, y, ALL, "total", "", d["entered"] * 1000, "gross_inflow", src,
             "component=entered; new arrivals in the year who joined the illegal-immigrant population (estimated from year-of-entry cohorts surviving to 2000/2010 plus departures)")
        flow(y, y, ALL, "total", "", d["net_change"] * 1000, "net_change", src, "component=net_change")
        for c in names[3:]:
            flow(y, y, ALL, "total", "", d[c] * 1000, "other", src, f"component={c} (outflow)")

    # Pew 2008 / 2010 averages and period-of-arrival profiles
    evidence("pew_older/pew_126.txt", "an average of about 850,000 new unauthorized immigrants entered each",
             "about 550,000", "per year from March 2005 to March 2007", "300,000 per year for March 2007 to March 2009",
             "of 150,000 unauthorized immigrants from Mexico arrived annually during the",
             "March 2007 to March 2009 period", "annual average of 500,000",
             "1.7 million, or 15% of unauthorized immigrants, arrived", "3.5 million, or 32% of the",
             "million—arrived during the 1990s", "1.4 million unauthorized immigrants, or 13% of the total, arrived during the")
    src = "pew2010_passel_cohn"
    pa = "unit=annual_average; periods run March to March; gross arrivals (border crossers and visa violators) before departures"
    flow(2000, 2005, ALL, "total", "", 850_000, "gross_inflow", src, pa)
    flow(2005, 2007, ALL, "total", "", 550_000, "gross_inflow", src, pa)
    flow(2007, 2009, ALL, "total", "", 300_000, "gross_inflow", src, pa)
    flow(2000, 2005, "Mexico", "country", ALL, 500_000, "gross_inflow", src, pa + "; Mexico only ('first half of the decade')")
    flow(2007, 2009, "Mexico", "country", ALL, 150_000, "gross_inflow", src, pa + "; Mexico only")
    ep = "unit=period_total; people in the March {s} illegal-immigrant population who arrived in the period (survivors only)"
    for p0, p1, v, s, sid in [(2005, 2009, 1_700_000, 2009, "pew2010_passel_cohn"), (2000, 2004, 3_500_000, 2009, "pew2010_passel_cohn"),
                              (1990, 1999, 4_500_000, 2009, "pew2010_passel_cohn"), (1980, 1989, 1_400_000, 2009, "pew2010_passel_cohn"),
                              (2005, 2008, 1_600_000, 2008, "pew2008_passel_cohn"), (2000, 2004, 3_700_000, 2008, "pew2008_passel_cohn"),
                              (1995, 1999, 3_100_000, 2008, "pew2008_passel_cohn"), (1990, 1999, 5_100_000, 2008, "pew2008_passel_cohn"),
                              (1980, 1989, 1_600_000, 2008, "pew2008_passel_cohn"),
                              (2000, 2005, 4_400_000, 2005, "pew2006_passel"), (1995, 1999, 2_900_000, 2005, "pew2006_passel"),
                              (1990, 1994, 2_000_000, 2005, "pew2006_passel"), (1980, 1989, 1_800_000, 2005, "pew2006_passel"),
                              (2000, 2004, 3_100_000, 2004, "pew2005_passel"), (1995, 1999, 3_600_000, 2004, "pew2005_passel"),
                              (1990, 1994, 2_200_000, 2004, "pew2005_passel"), (1980, 1989, 1_300_000, 2004, "pew2005_passel")]:
        flow(p0, p1, ALL, "total", "", v, "entered_period", sid, ep.format(s=s) + f"; stock_year={s}")
    evidence("pew_older/pew_94.txt", "inflows of unauthorized immigrants", "averaged 800,000 a year from 2000 to 2004, but fell to 500,000 a year from 2005",
             "annual net average of about 525,000", "annual growth has averaged only 275,000",
             "about 1.6 million new undocumented immigrants", "Of those, 1.6 million, or 13% of all", "The other 3.7 million",
             "Of the 5.1 million who arrived during that decade, 3.1 million came", "estimated 1.6 million undocumented immigrants, 13% of the total")
    src = "pew2008_passel_cohn"
    flow(2000, 2004, ALL, "total", "", 800_000, "gross_inflow", src, "unit=annual_average; new undocumented entrants per year (border crossers and visa violators)")
    flow(2005, 2008, ALL, "total", "", 500_000, "gross_inflow", src, "unit=annual_average; about 1.6 million in total 2005-2008; 'substantially smaller number arriving since 2007'")
    flow(2000, 2005, ALL, "total", "", 525_000, "net_change", src, "unit=annual_average; 8.4 million (2000) to 11.1 million (early 2005)")
    flow(2005, 2008, ALL, "total", "", 275_000, "net_change", src, "unit=annual_average; 11.1 million (2005) to 11.9 million (March 2008)")
    evidence("pew_older/pew_61.txt", "4.4 million – 40%", "(850,000 per year)", "2.9 million -- 26%", "2.0 million -- 18%", "1.8 million --16%")
    evidence("pew_older/pew_44.txt", "3.1 million – 30%", "3.6 million -- 35%", "2.2 million -- 21%", "1.3 million -- 14%")
    # Pew 2025
    src = "pew2025_passel_krogstad"
    rel = "pew_2025_unauthorized/report.txt"
    evidence(rel, "In 2023, more than 4.2", "years, up from 1.8 million in", "Total 2,525,000 2,125,000 390,000",
             "releases at southwest border 1,225,000 1,150,000 60,000", "paroles at southwest border 820,000 555,000 265,000",
             "(CHNV) paroles 370,000 335,000 35,000", "Uniting for Ukraine (U4U) paroles 110,000 75,000 30,000",
             "possibly by as much as 1 million")
    flow(2019, 2023, ALL, "total", "", 4_200_000, "entered_period", src,
         "unit=period_total; ADULTS only: 'more than 4.2 million' adults (Pew 'unauthorized' definition) in the US less than five years in 2023; stock_year=2023 (Jul 1); " + TEMP_INCL)
    flow(2017, 2021, ALL, "total", "", 1_800_000, "entered_period", src, "unit=period_total; ADULTS only, in the US less than five years in 2021; stock_year=2021")
    pr = ("people released or paroled at entry (temporary legal permission, counted in Pew's 'unauthorized' total); NOT illegal entries; "
          "from OHSS monthly tables via Pew; rounded to nearest 5,000")
    for p0, p1, months, vals in [(2023, 2024, "Jul 2023-Dec 2024", (2_525_000, 1_225_000, 820_000, 370_000, 110_000)),
                                 (2023, 2024, "Jul 2023-Jun 2024", (2_125_000, 1_150_000, 555_000, 335_000, 75_000)),
                                 (2024, 2024, "Jul-Dec 2024", (390_000, 60_000, 265_000, 35_000, 30_000))]:
        for comp_, v in zip(["releases_and_paroles_total", "USBP_releases_SW_border", "OFO_paroles_SW_border", "CHNV_paroles", "U4U_paroles_Pew_estimate"], vals):
            flow(p0, p1, ALL, "total", "", v, "gross_inflow", src, f"component={comp_}; months={months}; {pr}")
    flow(2025, 2025, ALL, "total", "", None, "net_change", src,
         "months=Jan-Jun 2025; 'the unauthorized immigrant population likely declined, possibly by as much as 1 million' (preliminary, CPS-based)", -1_000_000, 0)

    # DHS OIS / OHSS: stock by period of entry (survivors)
    evidence("archiveit_ohss_unauth/ois_jan2011.txt", "11,510,000", "1,580,000", "3,330,000", "3,030,000", "1,650,000", "1,070,000", "850,000")
    evidence("archiveit_ohss_unauth/ois_jan2012.txt", "11,430,000", "1,540,000", "3,250,000", "2,920,000", "1,720,000", "1,110,000", "890,000")
    evidence("archiveit_ohss_unauth/ois_jan2014.txt", "12,120,000", "630,000", "2,040,000", "6,090,000", "3,360,000",
             "11,780,000", "2,460,000", "4,070,000", "3,950,000", "1,300,000")
    for sid, sy, bins in [
            ("ois2012_hoefer_rytina_baker", 2011, [(2005, 2010, 1_580_000), (2000, 2004, 3_330_000), (1995, 1999, 3_030_000), (1990, 1994, 1_650_000), (1985, 1989, 1_070_000), (1980, 1984, 850_000)]),
            ("ois2013_baker_rytina", 2012, [(2005, 2011, 1_540_000), (2000, 2004, 3_250_000), (1995, 1999, 2_920_000), (1990, 1994, 1_720_000), (1985, 1989, 1_110_000), (1980, 1984, 890_000)]),
            ("ois2017_baker", 2014, [(2009, 2013, 630_000), (2004, 2008, 2_040_000), (1994, 2003, 6_090_000), (1980, 1993, 3_360_000)]),
            ("ois2017_baker", 2007, [(2002, 2006, 2_460_000), (1997, 2001, 4_070_000), (1987, 1996, 3_950_000), (1980, 1986, 1_300_000)])]:
        for p0, p1, v in bins:
            flow(p0, p1, ALL, "total", "", v, "entered_period", sid,
                 f"unit=period_total; stock_year={sy} (Jan 1); people in that stock who entered in the period (survivors); "
                 + ("years-in-US bins converted to entry years; " if sid == "ois2017_baker" else "") + TEMP_INCL)
    rel = "archiveit_ohss_unauth/ohss_2018_2022.txt"
    lines = (RAW / rel).read_text(errors="replace").splitlines()
    k = next(i for i, l in enumerate(lines) if "Period of Entry" in l and "2018*" in l)
    per = {"1980–1990": (1980, 1989), "1990–1999": (1990, 1999), "2000–2009": (2000, 2009), "2010 or later": (2010, 2021)}
    for l in lines[k + 1:k + 8]:
        s = l.strip()
        for lab, (p0, p1) in per.items():
            if s.startswith(lab):
                vals = [num(x) for x in s[len(lab):].split()]
                for sy, v in zip([2018, 2019, 2020, 2022], vals):
                    flow(p0, p1, ALL, "total", "", v, "entered_period", "ohss2024_baker_warren",
                         f"unit=period_total; stock_year={sy} (Jan 1); table label '{lab}' (figure: 1980-1989); 2018 = revised; " + TEMP_INCL)

    # MPI: years of US residence of the 2019 and mid-2023 populations (survivors by approximate entry period)
    evidence("perma_cc_unauth/mpi_profile_US_2022capture.txt", "Less than 5 | 2,370,000", "5 to 9 | 1,744,000", "10 to 14 | 2,132,000",
             "15 to 19 | 2,368,000", "20 or more | 2,433,000")
    for p0, p1, v in [(2015, 2019, 2_370_000), (2010, 2014, 1_744_000), (2005, 2009, 2_132_000), (2000, 2004, 2_368_000), (None, 1999, 2_433_000)]:
        flow(p0, p1, ALL, "total", "", v, "entered_period", "mpi_profile2019",
             "unit=period_total; stock_year=2019; years-of-residence bins (<5, 5-9, 10-14, 15-19, 20+) converted to approximate entry years; data pooled 2015-19"
             + ("; '20 or more' years (no start year)" if p0 is None else "") + "; " + TEMP_INCL)
    evidence("mpi_factsheet_2026/mpi-unauthorized-immigrants-fact-sheet-2025-final.txt", "The largest share-45 percent-had lived in the",
             "with another 14", "percent having 15 to 19 years of residence, and 21", "percent at least five years of residence. Just 20 per-",
             "cent had lived in the country for less than five years")
    for p0, p1, pct, lab in [(2019, 2023, 20, "<5 years"), (2009, 2018, 21, "5-14 years"), (2004, 2008, 14, "15-19 years"), (None, 2003, 45, "20+ years")]:
        flow(p0, p1, ALL, "total", "", round(13_738_000 * pct / 100), "entered_period", "mpi2025_factsheet",
             f"unit=period_total; stock_year=2023 (mid-year); derived = {pct}% ({lab} of US residence) x 13,738,000; range = +/-0.5 pp; approximate entry years; " + TEMP_INCL,
             round(13_738_000 * (pct - 0.5) / 100), round(13_738_000 * (pct + 0.5) / 100))

    # INS 1994 / 1996 yearbooks
    evidence("archiveorg_ins_yearbooks/doj-reports_j-212-10996_djvu.txt", "281,000 and 275,000", "approximately 230,000 undocumented Mexican",
             "increased by just over 150,000")
    flow(1988, 1992, ALL, "total", "", 281_000, "net_change", "ins_yb1996_text", "unit=annual_average; Oct 1988-Oct 1992 (revised INS estimates)")
    flow(1992, 1996, ALL, "total", "", 275_000, "net_change", "ins_yb1996_text", "unit=annual_average; Oct 1992-Oct 1996")
    flow(1988, 1996, "Mexico", "country", ALL, 150_000, "net_change", "ins_yb1996_text", "unit=annual_average; 'just over 150,000' per year, Mexico only")
    flow(1990, 1996, "Mexico", "country", ALL, 230_000, "entered_period", "ins_yb1996_text",
         "unit=annual_average; 'approximately 230,000 undocumented Mexican immigrants established residence annually between 1990 and 1996' (net addition of arrivals of the period, before later departures)")
    evidence("archiveorg_ins_yearbooks/doj-reports_j-212-10994_djvu.txt", "an average annual growth of", "about 300,000")
    flow(1988, 1992, ALL, "total", "", 300_000, "net_change", "ins_yb1994_text", "unit=annual_average; original 1994 estimate (2.2 million in 1988 to 3.4 million Oct 1992)")

    # Census Bureau 1980s
    rel = "bls_mlr_1986_passel/mlr_1986_09_rpt2full.txt"
    evidence(rel, "grew by between 100,000 and 300,000 per year between", "undocumented immigration of 200,000 for every year since",
             "An estimated 1,517,000, or 75 percent", "946,000 (or 46 per-")
    flow(1980, 1983, ALL, "total", "", None, "net_change", "census_passel1986_mlr", "unit=annual_average; April 1980 census vs April 1983 CPS; range only", 100_000, 300_000)
    flow(1980, 1985, ALL, "total", "", 200_000, "net_change", "census_passel1986_mlr",
         "unit=annual_average; ASSUMPTION adopted in Census Bureau postcensal estimates from Jan 1986 ('net annual undocumented immigration of 200,000 for every year since 1980')")
    flow(1970, 1979, ALL, "total", "", 1_517_000, "entered_period", "census_passel1986_mlr", "unit=period_total; undocumented aliens counted in the 1980 census who entered in the 1970s; stock_year=1980")
    flow(1975, 1980, ALL, "total", "", 946_000, "entered_period", "census_passel1986_mlr", "unit=period_total; entered in the 5 years before the 1980 census; stock_year=1980")
    src = "passel_woodrow1984_via_chiswick1988"
    for p0, p1, v, extra in [(1975, 1980, 941_000, ""), (1970, 1974, 576_000, ""), (None, 1969, 540_000, "; 'before 1970' (no start year)")]:
        flow(p0, p1, ALL, "total", "", v, "entered_period", src, "unit=period_total; counted in the 1980 census; stock_year=1980" + extra)
    evidence("eric_pre1980/ED296133_excerpt_ch2_p19-21.txt", "Period of entry: 1975-80 61 45.2 941 45.7", "1970-74 43 31.9 576 28.0", "Before 1970 32 23.7 540 26.3")
    evidence("eric_pre1980/ED210367.txt", "one-half million each year")
    flow(1981, 1981, ALL, "total", "", None, "net_change", "ins1981_meissner_testimony",
         "unit=annual_average; 'continuing to grow from one-quarter to one-half million each year' (INS testimony, Oct 1981); range only", 250_000, 500_000)

    # CMS: arrivals in 2016 by mode (image table, thousands)
    src = "cms2019_warren"
    with open(RAW / "perma_cc_unauth/transcribed_cms2019_tables2_3.csv") as fh:
        rows = [r for r in csv.DictReader(fh) if r["table"] == "T3"]
    for r in rows:
        comp_ = {"total_arrivals": "all_arrivals", "overstays": "visa_overstays", "ewi": "entries_without_inspection"}[r["series"]]
        n, v = r["country"], int(r["thousands"]) * 1000
        lab = {"All other": "All other countries", "Dom Rep.": "Dominican Republic"}.get(n, n)
        lvl = "total" if n == "All countries" else "residual" if n == "All other" else "country"
        flow(2016, 2016, lab, lvl, "" if lvl == "total" else ALL, v, "gross_inflow", src,
             f"component={comp_}; people who joined the illegal-immigrant population in 2016 (CMS year-of-entry estimates); hand transcription of image Table 3 (thousands)")

    # CBO (net immigration of 'other foreign nationals' = illegal entrants + overstays + parolees/people awaiting court)
    rel26 = "archiveit_cbo/cbo_2026_61879_demographic_outlook.txt"
    evidence(rel26, "averaged −130,000 people from", "2010 to 2019 and then totaled 830,000 people in 2021",
             "2.0 million people in 2022, 2.4 million people in 2023", "and 1.3 million people in 2024", "−360,000 people in that year",
             "equals −330,000 peo-", "−130,000 people in 2030 and 140,000 people in 2036",
             "January and September 2025: 1.1 million people and", "−290,000 people, respectively",
             "A total of 380,000 people joined the OFN category last", "(20,000), people who entered at ports of entry and were",
             "released into the country by CBP officials (60,000)", "(50,000), and people who entered legally in a temporary",
             "status but overstayed their term of residency (260,000)", "540,000 people estimated to have",
             "In 2024, CBO estimates, 960,000 people were released", "roughly 800,000",
             "and 300,000 people estimated to have entered the United", "numbered 270,000 in fiscal year 2024",
             "a total of about 750,000 people", "400,000 people in the other-foreign-national category left",
             "estimates that 120,000 people from the other-foreign-",
             "estimates that 225,000 other foreign nationals obtained", "482,954 people may have overstayed", "670,674 people were observed")
    OFN = ("CBO 'other foreign nationals' = people who entered illegally + visa overstayers + people paroled in or released "
           "and awaiting immigration court (the last group has temporary legal permission); illegal-only part not published")
    src = "cbo2026_demographic_outlook"
    flow(2010, 2019, ALL, "total", "", -130_000, "net_change", src, "unit=annual_average; calendar years; " + OFN)
    for y, v, proj in [(2021, 830_000, False), (2022, 2_000_000, False), (2023, 2_400_000, False), (2024, 1_300_000, False),
                       (2025, -360_000, False), (2026, -330_000, True), (2027, -330_000, True), (2030, -130_000, True), (2036, 140_000, True)]:
        flow(y, y, ALL, "total", "", v, "net_change", src, ("PROJECTION; " if proj else "estimate; ") + "calendar year; " + OFN)
    flow(2025, 2025, ALL, "total", "", 1_100_000, "net_change", "cbo2025_jan_demographic_outlook", "PROJECTION made Jan 2025 (value quoted in CBO Jan 2026, App. B); " + OFN)
    flow(2025, 2025, ALL, "total", "", -290_000, "net_change", "cbo2025_sep_demographic_update", "PROJECTION made Sep 2025 (value quoted in CBO Jan 2026, App. B); " + OFN)
    g = "calendar year; people joining the OFN category; "
    for comp_, v, ill in [("joined_total", 380_000, False), ("released_between_ports_USBP", 20_000, False), ("released_at_ports_OFO", 60_000, False),
                          ("entered_without_encountering_CBP", 50_000, True), ("visa_overstays", 260_000, True),
                          ("illegal_only_sum_EWI_not_encountered_plus_overstays", 310_000, True)]:
        flow(2025, 2025, ALL, "total", "", v, "gross_inflow", src,
             f"component={comp_}; " + g + ("ILLEGAL entry or overstay" if ill else "includes people released/paroled with temporary permission")
             + ("; derived sum 50,000 + 260,000" if comp_.startswith("illegal_only") else ""))
    for comp_, v, ill, ex in [("released_between_ports_USBP", 540_000, False, ""), ("released_at_ports_OFO", 960_000, False, ""),
                              ("entered_without_encountering_CBP", 300_000, True, "; 'roughly' (FY2024: 270,000)"),
                              ("visa_overstays", 260_000, True, "; overstayers present in 2024")]:
        flow(2024, 2024, ALL, "total", "", v, "gross_inflow", src, f"component={comp_}; " + g + ("ILLEGAL entry or overstay" if ill else "temporary permission") + ex)
    flow(2023, 2023, ALL, "total", "", 800_000, "gross_inflow", src, "component=entered_without_encountering_CBP; calendar year; 'roughly 800,000'; ILLEGAL entry")
    for comp_, v in [("left_total", 750_000), ("emigrated_voluntarily", 400_000), ("removed_from_interior", 120_000), ("obtained_permanent_legal_status", 225_000)]:
        flow(2025, 2025, ALL, "total", "", v, "other", src, f"component={comp_} (outflow from OFN category); calendar year 2025; 'about'")
    rel24 = "archiveit_cbo/cbo_2024_59697_demographic_outlook.txt"
    evidence(rel24, "other-foreign-national category was 600,000 in 2021 and 1.9 million in 2022",
             "foreign-national category was 2.4 million in 2023", "such immigration was 2.5 million in 2023",
             "ber was 2.2 million", "In 2024, as in", "2023, CBO projects that 2.4 million people",
             "rary status—3.3 million in fiscal year 2023", "a total of 660,000", "(1.1 million), people who entered the country at official",
             "CBP officials (900,000), people who entered without", "encountering a CBP official (860,000)", "term of residency (430,000)",
             "was 2.6 million in fiscal year 2023")
    src = "cbo2024_demographic_outlook"
    flow(2021, 2021, ALL, "total", "", 600_000, "net_change", src, "earlier vintage (Jan 2024); calendar year; " + OFN)
    flow(2022, 2022, ALL, "total", "", 1_900_000, "net_change", src, "earlier vintage (Jan 2024); calendar year; " + OFN)
    flow(2023, 2023, ALL, "total", "", 2_400_000, "net_change", src, "earlier vintage (Jan 2024); calendar year; DHS-data method 2.5 million, Census-data method 2.2 million; " + OFN, 2_200_000, 2_500_000)
    flow(2024, 2024, ALL, "total", "", 2_400_000, "net_change", src, "PROJECTION (Jan 2024); " + OFN)
    for comp_, v, ill in [("joined_total", 3_300_000, False), ("released_between_ports_USBP", 1_100_000, False), ("released_at_ports_OFO", 900_000, False),
                          ("entered_without_encountering_CBP", 860_000, True), ("visa_overstays", 430_000, True),
                          ("illegal_only_sum_EWI_not_encountered_plus_overstays", 1_290_000, True)]:
        flow(2023, 2023, ALL, "total", "", v, "gross_inflow", src,
             f"component={comp_}; FISCAL year 2023 (Oct 2022-Sep 2023); " + ("ILLEGAL entry or overstay" if ill else "includes people released/paroled with temporary permission")
             + ("; derived sum 860,000 + 430,000" if comp_.startswith("illegal_only") else "")
             + ("; 750,000 observed got-aways + 15% for undetected" if comp_ == "entered_without_encountering_CBP" else ""))
    flow(2023, 2023, ALL, "total", "", 660_000, "other", src, "component=left_total (emigrated or obtained legal status); FISCAL year 2023")
    flow(2023, 2023, ALL, "total", "", 2_600_000, "net_change", src, "FISCAL year 2023, DHS-data method; " + OFN)

    # Census Bureau net international migration (ALL migrants, all legal statuses) - context only
    for f, sid in [("census_popest_nim/NST-EST2025-ALLDATA.csv", "census_v2025_popest"), ("census_popest_nim/NST-EST2024-ALLDATA.csv", "census_v2024_popest")]:
        with open(RAW / f, encoding="latin-1") as fh:
            us = next(r for r in csv.DictReader(fh) if r["NAME"] == "United States")
        for k, v in us.items():
            m = re.match(r"INTERNATIONALMIG(\d{4})$", k)
            if m and int(m.group(1)) >= 2021:
                y = int(m.group(1))
                flow(y - 1, y, ALL, "total", "", int(v), "other", sid,
                     f"component=net_international_migration_ALL_statuses; Jul 1 {y-1}-Jun 30 {y}; NOT an illegal-immigration estimate (legal status not estimated)")
    evidence("census_popest_nim/v2025_press_release.txt", "net international migration is projected to be approximately 321,000 by July 2026")
    flow(2025, 2026, ALL, "total", "", 321_000, "other", "census_v2025_popest",
         "component=net_international_migration_ALL_statuses; PROJECTION for Jul 2025-Jun 2026 (Vintage 2025 press release); NOT illegal-specific")

    # Brookings (Edelberg, Veuger & Watson), Jan 2026
    rel = "brookings_2026_net_migration/page.txt"
    evidence(rel, "net immigration likely ranged between –295,000 and –10,000 for 2025",
             "range between –925,000 and +185,000", "parole/NTA inflows at around 67,000 to 70,000",
             "entries without inspection to be between 22,000 and 39,000", "We estimate 310,000 to 315,000 removals for 2025",
             "For 2024, we rely on the recently released Congressional Budget Office (CBO) estimate of 270,000")
    src = "brookings2026_edelberg_veuger_watson"
    flow(2025, 2025, ALL, "total", "", None, "other", src, "component=net_migration_ALL_statuses; calendar 2025; range only; NOT illegal-specific", -295_000, -10_000)
    flow(2026, 2026, ALL, "total", "", None, "other", src, "component=net_migration_ALL_statuses; PROJECTION 2026; range only", -925_000, 185_000)
    flow(2025, 2025, ALL, "total", "", None, "gross_inflow", src, "component=entries_without_inspection; ILLEGAL entries not encountered by any official; range only", 22_000, 39_000)
    flow(2025, 2025, ALL, "total", "", None, "gross_inflow", src, "component=parole_and_NTA_releases; temporary permission (not illegal entry); range only", 67_000, 70_000)
    flow(2025, 2025, ALL, "total", "", None, "other", src, "component=removals (ICE border + interior removals, all statuses); range only", 310_000, 315_000)

    # DHS public statement, Dec 2025 (via syndicated news report)
    rel = "sinclair_dhs_departures_2025/page.txt"
    evidence(rel, "more than 2.5 million illegal aliens leaving the U.S. DHS has deported more than 605,000 illegal aliens and another 1.9 million have self-deported",
             "the number of illegal immigrants who have self-deported is just an estimation")
    src = "dhs2025_press_statement_via_tnnd"
    note = ("Jan 20-Dec 10, 2025; DHS press statement (Assistant Secretary McLaughlin) quoted by The National News Desk, 2025-12-11; "
            "self-deportation figure is an undocumented DHS estimate (Brookings: likely CPS-based and covering legal immigrants too)")
    flow(2025, 2025, ALL, "total", "", 2_500_000, "other", src, "component=claimed_departures_total ('more than 2.5 million'); " + note)
    flow(2025, 2025, ALL, "total", "", 605_000, "other", src, "component=claimed_removals ('more than 605,000'); " + note)
    flow(2025, 2025, ALL, "total", "", 1_900_000, "other", src, "component=claimed_self_deportations (estimate); " + note)

    # DHS 2017: estimated successful illegal entries between ports of entry, southwest border (IDA model)
    rel = "archiveit_dhs_border_security/dhs2017_estimates_of_border_security.txt"
    evidence(rel, "IDA estimates that 1.8 million aliens successfully crossed the border in 2000, versus", "170,000 in 2016")
    for y, v in [(2000, 1_800_000), (2016, 170_000)]:
        flow(y, y, ALL, "total", "", v, "gross_inflow", "dhs2017_border_security",
             "component=successful_illegal_entries_SW_border_between_ports; fiscal year; IDA model for DHS; entries (events), ILLEGAL entry only; excludes overstays and ports of entry")


# =====================================================================================================
# 7. Indicators (NOT migrant counts)
# =====================================================================================================
def build_indicators():
    rel = "perma_cc_dhs_yb2019_enforcement/yearbook2019_tables33_39.txt"
    lines = (RAW / rel).read_text(errors="replace").splitlines()
    k39 = next(i for i, l in enumerate(lines) if "Table 39." in l)
    t33, t39 = {}, {}
    for l in lines[:k39]:
        for m in re.finditer(r"(\d{4})(\d)?(?:\s*\.)+\s+([\d,]+)", l):
            t33[int(m.group(1))] = (num(m.group(3)), m.group(2))
    for l in lines[k39:]:
        for m in re.finditer(r"(\d{4})(\d)?(?:\s*\.)+\s+([\d,]+)\s+(NA|[\d,]+)", l):
            t39[int(m.group(1))] = (num(m.group(3)), num(m.group(4)), m.group(2))
    assert set(t33) == set(range(1925, 2020)), len(t33)
    assert set(t39) == set(range(1892, 2020)), len(t39)
    for y, (v, fn) in sorted(t33.items()):
        n = "fiscal year; EVENTS not people (repeat crossers counted each time); Border Patrol apprehensions (+ ICE administrative arrests from 1952; all ICE ERO arrests from 2008)"
        if fn:
            n += "; footnote: " + {"1": "FY1976 includes 15 months (Jul 1975-Sep 1976)", "2": "from 2008 includes all ICE ERO administrative arrests",
                                   "3": "from 2009 includes 287(g) arrests", "4": "ICE ERO counting method revised in 2016"}[fn]
        ind(y, "apprehensions_nationwide", v, "dhs_yb2019_tables33_39", n)
    for y, (rem, ret, fn) in sorted(t39.items()):
        n = "fiscal year; events; all removable aliens (not only people who entered illegally)" + ("; FY1976 includes 15 months" if fn == "3" else "") + ("; ICE counting revised 2016" if fn == "4" else "")
        ind(y, "removals", rem, "dhs_yb2019_tables33_39", n + "; removal = compulsory departure under an order of removal")
        if ret is not None:
            ind(y, "returns", ret, "dhs_yb2019_tables33_39", n + "; return = confirmed departure without an order of removal")
    with open(RAW / "pew_2026_border/usbp_sw_border_encounters_fy1960_2025.csv") as fh:
        for r in csv.DictReader(fh):
            y = int(r["fiscal_year"])
            ind(y, "usbp_southwest_border_apprehensions_encounters", int(r["encounters"]), "pew2026_gramlich_border",
                "fiscal year; EVENTS not people; apprehensions before Mar 2020, apprehensions + Title 42 expulsions ('encounters') after; between ports of entry only")
    evidence("pew_2026_border/page.txt", "The Border Patrol recorded 237,538 encounters")
    import openpyxl
    ws = openpyxl.load_workbook(RAW / "census_popest_nim/blog_fig2_data.xlsx", data_only=True).active
    for r in ws.iter_rows(values_only=True):
        if isinstance(r[0], int) and r[5] is not None:
            ind(r[0], "humanitarian_migrant_arrivals_benchmark", int(r[5]) * 1000, "census_v2025_blog_fig2",
                f"Jul {r[0]-1}-Jun {r[0]} (earlier years may be fiscal years); Census Bureau benchmark from OHSS enforcement/legal-process tables + refugee admissions: "
                "refugees (legal) + parolees + people released at the border; thousands x 1000")
    rel = "archiveit_dhs_border_security/dhs2017_estimates_of_border_security.txt"
    evidence(rel, "falling back to 106,000 in 2016", "from 615,000 to 106,000", "increased to about 170,000 in 2013")
    for y, v, q in [(2006, 615_000, ""), (2013, 170_000, "; 'about'"), (2016, 106_000, "")]:
        ind(y, "usbp_known_gotaways_sw_border", v, "dhs2017_border_security", "fiscal year; illegal entries observed but not apprehended (known got-aways); excludes unobserved entries" + q)
    ind(2023, "usbp_observed_gotaways_reported", 670_674, "cbo2026_demographic_outlook",
        "fiscal year 2023; observed entrants not caught or pursued, per Border Patrol officials in media reports, as cited by CBO (Jan 2026, App. B)")
    ind(2024, "suspected_in_country_overstays", 482_954, "cbo2026_demographic_outlook",
        "fiscal year 2024; CBP Entry/Exit Overstay Report FY2024 Table 1 as cited by CBO; many leave or adjust soon after")
    rel = "wikipedia_unauth/Chinese_Confession_Program.wikitext"
    evidence(rel, "13,895 confessions", "22,083 people were exposed and 11,294 paper son slots were closed")
    cn = "Chinese Confession Program 1956-1965 (people who had entered with false identities, mostly 'paper sons', during/after Chinese exclusion 1882-1943); cumulative; Wikipedia citing M. Ngai and the Museum of Chinese in America"
    ind(1965, "chinese_confession_program_confessions_1956_1965", 13_895, "wikipedia_chinese_confession_program", cn)
    ind(1965, "chinese_confession_program_persons_exposed_1956_1965", 22_083, "wikipedia_chinese_confession_program", cn)
    ind(1965, "chinese_confession_program_paper_slots_closed_1956_1965", 11_294, "wikipedia_chinese_confession_program", cn)
    evidence("archiveorg_cgi_annual_reports/annualreportofco1926unit_djvu.txt", "We can not more than estimate the number who are here unlawfully")


# =====================================================================================================
# 8. Sources
# =====================================================================================================
AIT = "https://wayback.archive-it.org/all/"
SOURCES = [
    ("pew2025_passel_krogstad", "Jeffrey S. Passel and Jens Manuel Krogstad, 'U.S. Unauthorized Immigrant Population Reached a Record 14 Million in 2023', Pew Research Center, Aug 21 2025; report PDF and detailed table 'Unauthorized immigrant population by region and selected country of birth, 1990-2023' (xlsx)",
     "https://www.pewresearch.org/race-and-ethnicity/2025/08/21/u-s-unauthorized-immigrant-population-reached-a-record-14-million-in-2023/",
     "RECOMMENDED PRIMARY STOCK SERIES. Residual method, ACS 2005-2023 (Jul 1), CPS 1995-2003 (Mar 1), 1990 census (Apr 1, from Warren & Warren 2013). Supersedes all earlier Pew estimates. Counts parolees, asylum applicants, TPS, DACA, U/T visa applicants and border releasees as unauthorized (about 6 million of 14 million in 2023). No 1991-94, 1996-97, 1999, 2001-02, 2004, 2020 estimates. raw: data/raw/pew_2025_unauthorized/"),
    ("pew2025_no_protection", "Same Pew 2025 report: unauthorized immigrants with no protection from deportation (2023 figure) and derived values for 2021 and 2007 from the report text",
     "https://www.pewresearch.org/race-and-ethnicity/2025/08/21/u-s-unauthorized-immigrant-population-reached-a-record-14-million-in-2023/",
     "Closest published 'illegal-only' total for 2023 (8.0 million). 2021 and 2007 values derived by subtraction."),
    ("pew2010_passel_cohn", "Jeffrey S. Passel and D'Vera Cohn, 'U.S. Unauthorized Immigration Flows Are Down Sharply Since Mid-Decade', Pew Hispanic Center, Sep 1 2010 (reports/126.pdf)",
     "https://www.pewresearch.org/wp-content/uploads/sites/5/reports/126.pdf", "Annual-average inflows by March-to-March period; period of arrival of the 2009 population. raw: data/raw/pew_older/"),
    ("pew2008_passel_cohn", "Jeffrey S. Passel and D'Vera Cohn, 'Trends in Unauthorized Immigration: Undocumented Inflow Now Trails Legal Inflow', Pew Hispanic Center, Oct 2 2008 (reports/94.pdf)",
     "https://www.pewresearch.org/wp-content/uploads/sites/5/reports/94.pdf", "Average inflows 2000-04 and 2005-08, net growth, period of arrival of the 2008 population."),
    ("pew2006_passel", "Jeffrey S. Passel, 'The Size and Characteristics of the Unauthorized Migrant Population in the U.S.', Pew Hispanic Center, Mar 7 2006 (reports/61.pdf), Figure 1",
     "https://www.pewresearch.org/wp-content/uploads/sites/5/reports/61.pdf", "Period of arrival of the March 2005 population (with annualized rates)."),
    ("pew2005_passel", "Jeffrey S. Passel, 'Estimates of the Size and Characteristics of the Undocumented Population', Pew Hispanic Center, Mar 21 2005 (reports/44.pdf), Figure 3",
     "https://www.pewresearch.org/wp-content/uploads/sites/5/reports/44.pdf", "Period of arrival of the March 2004 population."),
    ("pew2026_gramlich_border", "John Gramlich, 'Migrant encounters at the U.S.-Mexico border are at their lowest level in more than 50 years', Pew Research Center, Feb 2 2026 (table of U.S. Border Patrol southwest border encounters by fiscal year, from CBP)",
     "https://www.pewresearch.org/short-reads/2026/02/02/migrant-encounters-at-the-us-mexico-border-are-at-their-lowest-level-in-more-than-50-years/",
     "Indicator only (events). Extracted table: data/raw/pew_2026_border/usbp_sw_border_encounters_fy1960_2025.csv"),
    ("ohss2024_baker_warren", "Bryan Baker and Robert Warren, 'Estimates of the Unauthorized Immigrant Population Residing in the United States: January 2018-January 2022', DHS Office of Homeland Security Statistics, April 2024; Table 1 (period of entry) and Appendix Table A2-1 (updated historical estimates 2000-2022 by country)",
     AIT + "20260130052120/https://ohss.dhs.gov/sites/default/files/2024-06/2024_0418_ohss_estimates-of-the-unauthorized-immigrant-population-residing-in-the-united-states-january-2018%25E2%2580%2593january-2022.pdf",
     "Archive-It capture 2026-01-30 (ohss.dhs.gov blocks this environment). Jan 1 reference dates. Includes TPS, DACA, parolees and people awaiting removal proceedings. Series breaks in 2010, 2015, 2018 (both values given; the later-basis value is used here, earlier one under ohss2024_baker_warren_prev_basis). No 2001-2004 or 2021."),
    ("ohss2024_baker_warren_prev_basis", "Same as ohss2024_baker_warren: Table A2-1 columns 2010 (2000-census basis), 2015 (pre-update method) and 2018 (2015-18 method) that were revised in the next segment",
     AIT + "20260130052120/https://ohss.dhs.gov/sites/default/files/2024-06/2024_0418_ohss_estimates-of-the-unauthorized-immigrant-population-residing-in-the-united-states-january-2018%25E2%2580%2593january-2022.pdf",
     "Use only to splice segments."),
    ("ois2012_hoefer_rytina_baker", "Michael Hoefer, Nancy Rytina and Bryan Baker, 'Estimates of the Unauthorized Immigrant Population Residing in the United States: January 2011', DHS Office of Immigration Statistics (2012), Table 1 (period of entry)",
     AIT + "20251116095248/https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%2520January%25202011_0.pdf",
     "Archive-It capture. Also cites 2-4 million for 1980 (Warren and Passel 1987)."),
    ("ois2013_baker_rytina", "Bryan Baker and Nancy Rytina, 'Estimates of the Unauthorized Immigrant Population Residing in the United States: January 2012', DHS OIS (2013), Table 1",
     AIT + "20251116095247/https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%2520January%25202012_0.pdf", "Archive-It capture."),
    ("ois2017_baker", "Bryan Baker, 'Estimates of the Unauthorized Immigrant Population Residing in the United States: January 2014', DHS OIS, July 2017, Table 1 (years in the US, January 2014 and January 2007)",
     AIT + "20251116095246/https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%2520January%25202014_1.pdf",
     "Archive-It capture. Report total 12.1 million for 2014 was later revised to 11.46 million (A2-1)."),
    ("ins2003_warren", "U.S. Immigration and Naturalization Service, Office of Policy and Planning, 'Estimates of the Unauthorized Immigrant Population Residing in the United States: 1990 to 2000' (Jan 31 2003; R. Warren), Tables 2, 3, C and Chart 3",
     AIT + "20251116095312/https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%25201990%2520to%25202000.pdf",
     "Archive-It capture. Jan 1 stocks 1990-2000; annual entries/departures by component 1990-1999; 75 countries for 1990 and 2000. Excludes asylees/parolees with work authorization and people allowed to stay under legislation/court rulings (but Honduras 2000 includes 105,000 TPS)."),
    ("census2001_residual_via_ins2003", "U.S. Census Bureau (2001) residual foreign-born estimate for 2000, as quoted in INS (2003) 'Estimates of the Unauthorized Immigrant Population ... 1990 to 2000', p. 14",
     AIT + "20251116095312/https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%25201990%2520to%25202000.pdf",
     "Secondary. Includes 'quasi-legal' migrants."),
    ("ins_yb1996_tableP", "U.S. INS, 1996 Statistical Yearbook of the Immigration and Naturalization Service (1997), 'Illegal Immigrants' section, Table P (October 1996, top 20 countries), p. 198",
     "https://archive.org/details/doj-reports_j-212-10996",
     "Scanned yearbook at archive.org (DOJ reports collection). Table P transcribed by eye from the page image: data/raw/archiveorg_ins_yearbooks/transcribed_ins_yb1996_tableP_oct1996.csv (rows add to the printed total)."),
    ("ins_yb1996_text", "U.S. INS, 1996 Statistical Yearbook, 'Illegal Immigrants' section text, pp. 197-199", "https://archive.org/details/doj-reports_j-212-10996",
     "Revised Oct 1992 total, average annual growth 1988-92 and 1992-96, Mexican additions. OCR text: doj-reports_j-212-10996_djvu.txt"),
    ("ins_yb1994_tableN", "U.S. INS, 1994 Statistical Yearbook of the Immigration and Naturalization Service, 'Illegal Immigrants' section, Table N (October 1992, top 20 countries), p. 179",
     "https://archive.org/details/doj-reports_j-212-10994",
     "Original Warren (1994) estimate (3.4 million), later revised to 3.9 million. Transcription: data/raw/archiveorg_ins_yearbooks/transcribed_ins_yb1994_tableN_oct1992.csv"),
    ("ins_yb1994_text", "U.S. INS, 1994 Statistical Yearbook, 'Illegal Immigrants' section text, pp. 178-180", "https://archive.org/details/doj-reports_j-212-10994",
     "1988 level (2.2 million), pre-IRCA peak (nearly 5 million), growth 300,000 a year 1988-92."),
    ("warren_warren2013_imr", "Robert Warren and John Robert Warren, 'Unauthorized Immigration to the United States: Annual Estimates and Components of Change, by State, 1990 to 2010', International Migration Review 47(2): 296-329 (2013), Table 3 (author manuscript PMC3744247)",
     "https://pmc.ncbi.nlm.nih.gov/articles/PMC3744247/",
     "Annual Jan 1 stocks and entries/departures 1990-2010 (national; state detail in the paper). Includes quasi-legal groups (asylees/parolees with work permits, pending I-485, TPS; 577,000 in 2000). Basis of CMS estimates and of Pew's 1990 value."),
    ("cms2019_warren", "Robert Warren, 'US Undocumented Population Continued to Fall from 2016 to 2017, and Visa Overstays Significantly Exceeded Illegal Crossings for the Seventh Consecutive Year', Center for Migration Studies of New York (essay; also JMHS 7(1), 2019), Tables 2 and 3",
     "https://cmsny.org/publications/essay-2017-undocumented-and-overstays/ (Perma.cc PA8R-EWTQ, archive.org item perma_cc_PA8R-EWTQ)",
     "Tables are images; transcribed by eye: data/raw/perma_cc_unauth/transcribed_cms2019_tables2_3.csv. cmsny.org blocks this environment."),
    ("cms2025_warren_via_statesnewsroom", "Robert Warren, 'The Undocumented Population in the United States Increased to 12.2 Million in 2023', Center for Migration Studies (May 2025; also published in the Journal on Migration and Human Security), as reported by States Newsroom (Virginia Mercury), May 29 2025, republished by Royal Examiner",
     "https://royalexaminer.com/immigrants-in-u-s-without-permanent-legal-status-grew-to-12-2-million-study-finds",
     "SECONDARY reproduction (journal and CMS sites blocked here). Includes DACA, TPS, pending asylum and parolees. Extract: data/raw/cms_warren2025_secondary/royalexaminer_states_newsroom_2025-05-29.txt"),
    ("mpi_profile2019", "Migration Policy Institute, 'Profile of the Unauthorized Population: United States' (2019 estimates from pooled 2015-19 ACS and 2008 SIPP, weighted to totals by J. Van Hook)",
     "https://www.migrationpolicy.org/data/unauthorized-immigrant-population/state/US (Perma.cc WRF9-SDPW, 2022-09-20)",
     "Extract: data/raw/perma_cc_unauth/mpi_profile_US_2022capture.txt. migrationpolicy.org blocks curl here."),
    ("mpi2025_factsheet", "Julia Gelatt, Ariel G. Ruiz Soto and James D. Bachmeier, 'Changing Origins, Rising Numbers: Unauthorized Immigrants in the United States', MPI fact sheet, Oct 2025 (file revised Aug 2026)",
     "https://www.migrationpolicy.org/system/files/2026-08/mpi-unauthorized-immigrants-fact-sheet-2025-final.pdf",
     "Fetched with the WebFetch tool (curl gets 403); PDF and text kept in data/raw/mpi_factsheet_2026/. Mid-2023 = 13.7 million; up to 4 million with TPS, DACA, pending asylum or parole; regional values derived from rounded shares."),
    ("mpi2025_without_liminal", "Derived from mpi2025_factsheet: 13,738,000 minus 'as many as 4 million' with liminal status", "https://www.migrationpolicy.org/system/files/2026-08/mpi-unauthorized-immigrants-fact-sheet-2025-final.pdf",
     "Lower bound for illegal immigrants without temporary status, mid-2023."),
    ("passel_woodrow1984_via_chiswick1988", "Jeffrey S. Passel and Karen A. Woodrow, 'Geographic Distribution of Undocumented Immigrants: Estimates of Undocumented Aliens Counted in the 1980 Census by State', International Migration Review 18(3): 642-671 (1984), as reproduced in Barry R. Chiswick, Illegal Aliens: Their Employment and Employers (W.E. Upjohn Institute, 1988), Table 2-3 (ERIC ED296133)",
     "https://files.eric.ed.gov/fulltext/ED296133.pdf",
     "Secondary reproduction of the Census Bureau estimate; excerpt kept: data/raw/eric_pre1980/ED296133_excerpt_ch2_p19-21.txt. Counted in the census only."),
    ("census_passel1986_mlr", "Jeffrey S. Passel (U.S. Census Bureau), 'Estimating the number of undocumented aliens', Monthly Labor Review, September 1986 (report drawn from Employment and Earnings, Feb 1986), summarizing Warren & Passel, 'A Count of the Uncountable' (then forthcoming in Demography) and Passel & Woodrow (1984)",
     "https://www.bls.gov/opub/mlr/1986/09/rpt2full.pdf",
     "Fetched with WebFetch (curl 403); kept: data/raw/bls_mlr_1986_passel/. 1980 census count 2,057,000 (Mexico 1,131,000), period of entry, growth 1980-83, Census Bureau assumption of 200,000 net per year."),
    ("woodrow_passel1990_via_crs", "Karen Woodrow and Jeffrey S. Passel, 'Post-IRCA Undocumented Immigration to the United States: An Analysis Based on the June 1988 CPS', in Frank D. Bean, Barry Edmonston and Jeffrey Passel (eds.), Undocumented Migration to the United States (RAND Corporation, 1990), as summarized in CRS Report RL33874 'Unauthorized Aliens Residing in the United States: Estimates Since 1986' (Jan 23 2014)",
     "https://www.everycrsreport.com/reports/RL33874.html", "SECONDARY (rand.org blocked). 1986: 3.2 million (Mexico 2.1 million, Asia 0.2 million); 1988: 1.9 million."),
    ("ins1981_meissner_testimony", "Doris Meissner (Acting Commissioner, INS), 'A Legalization Program for Illegal Aliens Living in the United States', statement before the House Judiciary Subcommittee on Immigration, Refugees and International Law, Oct 15 1981 (ERIC ED210367)",
     "https://files.eric.ed.gov/fulltext/ED210367.pdf", "Official range 3-6 million and growth of 250,000-500,000 a year; scanned, OCR text kept."),
    ("siegel_passel_robinson1981_via_chiswick1988", "Siegel, Passel and Robinson (1981), U.S. Census Bureau review of existing studies of the number of illegal residents, as quoted in Barry R. Chiswick, Illegal Aliens: Their Employment and Employers (Upjohn Institute, 1988), p. 19 (ERIC ED296133); elsewhere in the book Chiswick summarizes it as 3.5-6.0 million in 1980, about half Mexican",
     "https://files.eric.ed.gov/fulltext/ED296133.pdf", "SECONDARY quotation. Ranges for 'some recent year, say 1978'."),
    ("yale2018_fazelzarandi", "Mohammad M. Fazel-Zarandi, Jonathan S. Feinstein and Edward H. Kaplan, 'The number of undocumented immigrants in the United States: Estimates based on demographic modeling with data from 1990 to 2016', PLoS ONE 13(9): e0201193 (2018)",
     "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0201193 (Perma.cc B68X-FYK7)", "Alternative flow-model estimate far above all residual-method series; included for completeness, not recommended for the site."),
    ("cbo2026_demographic_outlook", "Congressional Budget Office, 'The Demographic Outlook: 2026 to 2056' (Jan 2026), Appendix B 'Net Immigration of People in the Other-Foreign-National Category'",
     AIT + "20260716071048/https://www.cbo.gov/system/files/2026-01/61879-Demographic-Outlook.pdf",
     "Archive-It capture (cbo.gov blocks this environment). 'Other foreign nationals' = illegal entrants + overstayers + parolees/people released to await court; calendar years."),
    ("cbo2025_jan_demographic_outlook", "Congressional Budget Office, 'The Demographic Outlook: 2025 to 2055' (Jan 2025), publication 60875 - value quoted in CBO (Jan 2026), Appendix B", "https://www.cbo.gov/publication/60875", "Not fetched directly; projection superseded."),
    ("cbo2025_sep_demographic_update", "Congressional Budget Office, 'An Update to the Demographic Outlook, 2025 to 2055' (Sep 2025), publication 61390 - value quoted in CBO (Jan 2026), Appendix B", "https://www.cbo.gov/publication/61390", "Not fetched directly; projection superseded."),
    ("cbo2024_demographic_outlook", "Congressional Budget Office, 'The Demographic Outlook: 2024 to 2054' (Jan 2024), Appendix B",
     AIT + "20250101190003/https://www.cbo.gov/system/files/2024-01/59697-Demographic-Outlook.pdf", "Archive-It capture. Earlier vintage for 2021-2023 and FY2023 inflow components."),
    ("census_v2025_popest", "U.S. Census Bureau, Vintage 2025 national/state population estimates, components of change (NST-EST2025-ALLDATA) and press release CB26-20 (Jan 27 2026)",
     "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv",
     "Net international migration of ALL migrants (legal status not estimated); context for 2021-2026. From Vintage 2024 an adjustment for humanitarian migrants (2022-24)."),
    ("census_v2024_popest", "U.S. Census Bureau, Vintage 2024 national/state population estimates, components of change (NST-EST2024-ALLDATA)",
     "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/totals/NST-EST2024-ALLDATA.csv", "Earlier vintage of NIM, all migrants."),
    ("census_v2025_blog_fig2", "U.S. Census Bureau, Random Samplings blog 'New Population Estimates Show Historic Decline in Net International Migration' (Jan 2026), Figure 2 data: benchmark data by category 2015-2025",
     "https://www.census.gov/content/dam/Census/newsroom/blogs/2026/historic-decline-in-net-international-migration/historic-decline-in-net-international-migration-figure-2-data.xlsx",
     "Humanitarian migrants = refugees + parolees + border releases (OHSS/State Dept data); indicator only."),
    ("brookings2026_edelberg_veuger_watson", "Wendy Edelberg, Stan Veuger and Tara Watson, 'Macroeconomic implications of immigration flows in 2025 and 2026: January 2026 update', Brookings Institution, Jan 13 2026",
     "https://www.brookings.edu/articles/macroeconomic-implications-of-immigration-flows-in-2025-and-2026-january-2026-update/",
     "Net migration of all migrants 2025-26 and components (EWI, parole/NTA, removals). Extract: data/raw/brookings_2026_net_migration/page.txt"),
    ("dhs2025_press_statement_via_tnnd", "U.S. Department of Homeland Security press statement (Assistant Secretary Tricia McLaughlin, Dec 10 2025), as quoted in 'Trump's second term sees 2.5 million illegal aliens leave, shattering historic records', The National News Desk (Sinclair), Dec 11 2025",
     "https://okcfox.com/news/nation-world/trumps-second-term-sees-25-million-illegal-aliens-leave-shattering-historic-records-dhs-tricia-mclaughlin",
     "SECONDARY; dhs.gov blocked. Administration claim with undisclosed method for self-deportations. Extract: data/raw/sinclair_dhs_departures_2025/page.txt"),
    ("dhs2017_border_security", "U.S. Department of Homeland Security, Office of Immigration Statistics, 'Efforts by DHS to Estimate Southwest Border Security between Ports of Entry' (Sep 2017)",
     AIT + "20181225094429/https://www.dhs.gov/sites/default/files/publications/17_0914_estimates-of-border-security.pdf",
     "Archive-It capture. IDA model of successful illegal entries (2000, 2016 in text; annual values only in a chart) and USBP known got-aways."),
    ("dhs_yb2019_tables33_39", "U.S. DHS, Office of Immigration Statistics, 2019 Yearbook of Immigration Statistics, Table 33 'Aliens Apprehended: Fiscal Years 1925 to 2019' and Table 39 'Aliens Removed or Returned: Fiscal Years 1892 to 2019'",
     "https://perma.cc/C24E-JGKR (archive.org item perma_cc_C24E-JGKR) of https://www.dhs.gov/sites/default/files/publications/immigration-statistics/yearbook/2019/yearbook_immigration_statistics_2019.pdf",
     "Indicators only. Pages kept: data/raw/perma_cc_dhs_yb2019_enforcement/yearbook2019_tables33_39.pdf"),
    ("wikipedia_chinese_confession_program", "Wikipedia, 'Chinese Confession Program' (wikitext), citing Mae Ngai (interview) and the Museum of Chinese in America",
     "https://en.wikipedia.org/w/index.php?title=Chinese_Confession_Program&action=raw", "SECONDARY; indicator of exclusion-era illegal entry, not a migrant count."),
]


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def validate():
    errs = []
    used = {r["source_id"] for r in STOCK + FLOW + IND}
    known = {s[0] for s in SOURCES}
    errs += [f"source_id without citation: {u}" for u in sorted(used - known)]
    # summing rule: for each (year, source) with a total and children: countries + residuals = total
    from collections import defaultdict
    groups = defaultdict(list)
    for r in STOCK:
        groups[(r["year"], r["source_id"])].append(r)
    worst = []
    for k, rs in groups.items():
        tot = [r for r in rs if r["level"] == "total"]
        kids = [r for r in rs if r["level"] in ("country", "residual") and r["count"] is not None]
        if len(tot) > 1:
            errs.append(f"two totals for {k}")
        if tot and kids and tot[0]["count"] is not None:
            d = sum(r["count"] for r in kids) - tot[0]["count"]
            worst.append((abs(d) / tot[0]["count"], k, d))
            if abs(d) > max(0.005 * tot[0]["count"], 10_000):
                errs.append(f"sum mismatch {k}: children - total = {d:,}")
        labels = {r["origin_label"] for r in rs}
        for r in rs:
            if r["parent_label"] and r["parent_label"] not in labels:
                errs.append(f"missing parent {r['parent_label']} for {r['origin_label']} {k}")
        seen = set()
        for r in rs:
            key = (r["origin_label"], r["level"])
            if key in seen:
                errs.append(f"duplicate row {k} {key}")
            seen.add(key)
    worst.sort(reverse=True)
    return errs, worst[:5]


def main():
    build_pew2025()
    build_ohss()
    tabc = build_ins2003()
    ww = build_ww2013()
    build_other_stocks()
    build_flows(tabc, ww)
    build_indicators()
    STOCK.sort(key=lambda r: (r["source_id"], r["year"], {"total": 0, "region": 1, "country": 2, "residual": 3}[r["level"]], r["parent_label"], r["origin_label"]))
    FLOW.sort(key=lambda r: (r["source_id"], r["period_start"] if r["period_start"] is not None else 0, r["period_end"], r["basis"]))
    IND.sort(key=lambda r: (r["series"], r["year"]))
    write_csv(OUT / "unauthorized_population.csv", ["year", "origin_label", "level", "parent_label", "count", "low", "high", "source_id", "note"], STOCK)
    write_csv(OUT / "unauthorized_inflows.csv", ["period_start", "period_end", "origin_label", "level", "parent_label", "count", "low", "high", "basis", "source_id", "note"], FLOW)
    write_csv(OUT / "unauthorized_indicators.csv", ["year", "series", "count", "source_id", "note"], IND)
    used = {r["source_id"] for r in STOCK + FLOW + IND}
    write_csv(OUT / "sources_unauthorized.csv", ["source_id", "citation", "url", "accessed", "notes"],
              [dict(source_id=s[0], citation=s[1], url=s[2], accessed=ACCESSED, notes=s[3]) for s in SOURCES if s[0] in used])
    errs, worst = validate()
    print(f"population rows {len(STOCK)}, inflow rows {len(FLOW)}, indicator rows {len(IND)}, sources {len(used)}")
    print(f"evidence checks passed: {CHECKS['ok']}; missing raw files: {sorted(set(CHECKS['missing_file']))}")
    for rel, s in CHECKS["not_found"]:
        print(f"  EVIDENCE NOT FOUND in {rel}: {s!r}")
    print("largest relative child-sum gaps (rounding):", [(f"{w:.3%}", k, d) for w, k, d in worst])
    for e in errs:
        print("  ERROR", e)
    if errs or CHECKS["not_found"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
