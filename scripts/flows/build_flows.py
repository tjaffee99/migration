#!/usr/bin/env python3
"""Build the immigrant-flow (arrivals / new LPRs) files, 1820-latest.

Inputs (all under data/raw/, fetched by scripts/flows/fetch_archives.sh):
  archiveit_ohss/lpr_fy2022.xlsx     OHSS Yearbook FY2022 LPR workbook (Tables 1, 2, 3d)  [Archive-It capture]
  archiveit_ohss/lpr_fy2023.xlsx     OHSS Yearbook FY2023 LPR workbook (Tables 1, 2, 3; rounded to 10)
  archiveit_ohss/lpr2009.zip         DHS Yearbook 2009 LPR tables (table01/02/03d.xls)
  archiveit_ohss/ins_yb1996.zip      INS Statistical Yearbook 1996 tables (table2.xls)
  archiveit_ohss/ins_yb1999.zip      INS Statistical Yearbook 1999 tables (Table_2.xls, Table_3.xls)
  perma_cc_dhs/yearbook2019_tables1-3_p12-22.pdf   DHS Yearbook 2019, pp. 12-22 (Tables 1-3) [perma.cc capture]
  hsus1960_chC/hist_stats_colonial-1957-chC.pdf    HSUS Colonial Times to 1957, ch. C (series C 88-114)

Outputs (data/processed/):
  flows_totals_1820_present.csv, flows_by_origin_1820_present.csv,
  flows_by_birth_1989_present.csv, sources_flows.csv
Validation messages are printed to stdout (and summarised in flows_NOTES.md by hand).

Run:  python3 -I scripts/flows/build_flows.py
"""
import csv
import io
import os
import re
import subprocess
import sys
import zipfile
from collections import OrderedDict, defaultdict

import openpyxl
import xlrd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "processed")
AIT = os.path.join(RAW, "archiveit_ohss")
PERMA = os.path.join(RAW, "perma_cc_dhs")
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)  # our own helper module (scripts dir only; no data dirs)
import hsus1960  # noqa: E402

MSGS = []


def log(msg):
    MSGS.append(msg)
    print(msg)


# ----------------------------------------------------------------------------
# value / label helpers
# ----------------------------------------------------------------------------
def to_count(v):
    """Return int, 0 for '-', None for withheld ('D'/'NA'), 'SKIP' for not applicable."""
    if v is None:
        return "SKIP"
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip().replace(",", "")
    if s == "":
        return "SKIP"
    if s in ("-", "–", "—"):
        return 0
    if s in ("D", "NA"):
        return None
    if s.upper() == "X" or re.fullmatch(r"\(\d+\)", s):
        return "SKIP"
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return int(round(float(s)))
    raise ValueError(f"unparseable cell {v!r}")


def clean_label(lab):
    """Strip footnote reference markers and dot leaders, keep the source wording."""
    s = str(lab).replace(" ", " ").strip()
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"[\s.]+$", "", s)                 # dot leaders
        s = re.sub(r"(?<=[A-Za-z)\]])\s*/?\d+(\s*,\s*\d+)*\s*/?$", "", s)  # 2,3  /5  17/  12
        s = re.sub(r"\s+/\d*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


# ----------------------------------------------------------------------------
# hierarchy for the "selected country of last residence" tables (DHS Table 2 and INS Table 2)
# ----------------------------------------------------------------------------
REGIONS_SEL = {"europe", "asia", "america", "africa", "oceania"}
SUBREGIONS_AMERICA = {"caribbean", "centralamerica", "southamerica"}
AMERICA_COUNTRIES = {"canadaandnewfoundland", "canadanewfoundland", "mexico"}
SUBCOUNTRY_PARENT = {"austria": "Austria-Hungary", "hungary": "Austria-Hungary",
                     "norway": "Norway-Sweden", "sweden": "Norway-Sweden"}
TOTAL_LABELS = {"total", "allcountries"}
NOTSPEC = {"notspecified"}


def classify_selected(labels):
    """labels: list of cleaned labels in source order -> list of (level, parent)."""
    out = []
    region = sub = None
    total_label = None
    parent_labels = {}
    for lab in labels:
        n = norm(lab)
        if n in TOTAL_LABELS:
            total_label = lab
            out.append(("total", ""))
            continue
        if n in NOTSPEC:
            out.append(("residual", total_label))
            region = sub = None
            continue
        if n in REGIONS_SEL:
            region, sub = lab, None
            out.append(("region", total_label))
            continue
        if region and norm(region) == "america":
            if n in SUBREGIONS_AMERICA:
                sub = lab
                out.append(("subregion", region))
                continue
            if n in AMERICA_COUNTRIES:
                sub = None
                out.append(("country", region))
                continue
            if n == "otheramerica":
                sub = None
                out.append(("residual", region))
                continue
        if n in SUBCOUNTRY_PARENT and norm(SUBCOUNTRY_PARENT[n]) in parent_labels:
            out.append(("subcountry", parent_labels[norm(SUBCOUNTRY_PARENT[n])]))
            continue
        if n.startswith("other"):
            out.append(("residual", sub or region))
            continue
        out.append(("country", sub or region))
        parent_labels[n] = lab
    return out


def rows_from_table(labels, values_by_period, source_id, basis, hierarchy):
    """labels: list; values_by_period: {(ps,pe): [values aligned with labels]}"""
    rows = []
    for (ps, pe), vals in values_by_period.items():
        for lab, (lev, par), v in zip(labels, hierarchy, vals):
            c = to_count(v)
            if c == "SKIP":
                continue
            rows.append(dict(period_start=ps, period_end=pe, origin_label=lab, level=lev,
                             parent_label=par or "", count=c, basis=basis, source_id=source_id))
    return add_detail_residuals(rows)


def add_detail_residuals(rows):
    """A region/subregion with no child rows in the source (e.g. Africa, Oceania in INS Table 2)
    gets a derived residual child carrying the same count, so that country+residual rows still
    sum to the total.  Marked basis=derived_region_without_detail."""
    out = list(rows)
    by = defaultdict(list)
    for r in rows:
        by[(r["period_start"], r["period_end"], r["source_id"])].append(r)
    for key, rs in by.items():
        parents = {r["parent_label"] for r in rs}
        for r in rs:
            if r["level"] in ("region", "subregion") and r["origin_label"] not in parents:
                d = dict(r)
                d.update(origin_label=f"{r['origin_label']} (no country detail in source)", level="residual",
                         parent_label=r["origin_label"], basis="derived_region_without_detail")
                out.append(d)
    return out


# ----------------------------------------------------------------------------
# validation: totals = sum(country + residual), parent = sum(children)
# ----------------------------------------------------------------------------
def validate(rows, name, tol_per_row=0.0):
    by_period = defaultdict(list)
    for r in rows:
        by_period[(r["period_start"], r["period_end"], r["source_id"])].append(r)
    worst = 0
    n_bad = 0
    for key, rs in sorted(by_period.items()):
        tot = [r for r in rs if r["level"] == "total"]
        if not tot:
            continue
        total = tot[0]["count"]
        leaf = [r for r in rs if r["level"] in ("country", "residual")]
        s = sum(r["count"] or 0 for r in leaf)
        nwith = sum(1 for r in leaf if r["count"] is None)
        tol = tol_per_row * len(leaf) / 2 + 0.5
        diff = s - total
        worst = max(worst, abs(diff))
        if abs(diff) > tol:
            n_bad += 1
            log(f"  [{name}] {key}: countries+residuals={s:,} vs total={total:,} (diff {diff:+,}; withheld cells={nwith})")
        # parent/children
        kids = defaultdict(int)
        for r in rs:
            if r["level"] != "total" and r["parent_label"]:
                kids[r["parent_label"]] += r["count"] or 0
        for r in rs:
            if r["level"] in ("region", "subregion", "country") and r["origin_label"] in kids:
                d = kids[r["origin_label"]] - (r["count"] or 0)
                ktol = tol_per_row * 40 + 0.5
                if abs(d) > ktol:
                    log(f"  [{name}] {key}: children of '{r['origin_label']}' sum to "
                        f"{kids[r['origin_label']]:,} vs row {r['count']:,} (diff {d:+,})")
    log(f"[{name}] checked {len(by_period)} periods; periods failing leaf-sum check: {n_bad}; max |diff| {worst:,}")


# ----------------------------------------------------------------------------
# readers
# ----------------------------------------------------------------------------
def xlsx_rows(path, sheet):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def xls_rows(zpath, member):
    with zipfile.ZipFile(zpath) as z:
        sh = xlrd.open_workbook(file_contents=z.read(member)).sheet_by_index(0)
    return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]


def read_table1(rows):
    out = {}
    for r in rows:
        for i in range(0, len(r) - 1, 2):
            y, n = r[i], r[i + 1]
            if y is None or n is None:
                continue
            m = re.match(r"^(\d{4})(\.0)?\b", str(y).strip())
            if m and isinstance(n, (int, float)):
                out[int(m.group(1))] = int(round(n))
    return out


def period_of(h):
    s = str(h).strip()
    m = re.fullmatch(r"(\d{4})(\.0)?(\s*/?\d+)?", s)
    if m:
        y = int(m.group(1))
        return (y, y)
    m = re.fullmatch(r"(\d{4})\s*to\s*(\d{4})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def read_selected(rows, header_row_idx, want, label_col=0):
    """Return labels, {period: values} for the wanted periods (set of (ps,pe) or callable)."""
    hdr = rows[header_row_idx]
    cols = {}
    for j, h in enumerate(hdr):
        if j == label_col or h is None:
            continue
        p = period_of(h)
        if p and (want(p) if callable(want) else p in want):
            cols.setdefault(p, j)
    labels, data = [], OrderedDict((p, []) for p in sorted(cols))
    started = False
    for r in rows[header_row_idx + 1:]:
        lab = r[label_col]
        if lab is None or str(lab).strip() == "":
            continue
        cl = clean_label(lab)
        if norm(cl) in TOTAL_LABELS:
            started = True
        if not started:
            continue
        # footnote / note lines end the table
        if re.match(r"^(\d+\s|-\s|D\s|NA\s|Note|Source|See )", str(lab).strip()) or len(cl) > 60:
            break
        vals = [r[cols[p]] if cols[p] < len(r) else None for p in data]
        if all(v is None or str(v).strip() == "" for v in vals):
            continue
        labels.append(cl)
        for p, v in zip(data, vals):
            data[p].append(v)
    return labels, data


# ----------------------------------------------------------------------------
# full-country tables (REGION block + COUNTRY block): DHS 2009 table03d, FY2022 3d, FY2023 2/3
# ----------------------------------------------------------------------------
def read_blocked(rows, header_row_idx):
    hdr = rows[header_row_idx]
    cols = {}
    for j, h in enumerate(hdr):
        if j == 0 or h is None:
            continue
        p = period_of(h)
        if p:
            cols[p] = j
    block = None
    regions, countries = [], []
    for r in rows[header_row_idx + 1:]:
        lab = r[0]
        if lab is None or str(lab).strip() == "":
            continue
        s = str(lab).strip()
        if s == "REGION":
            block = "R"
            continue
        if s == "COUNTRY":
            block = "C"
            continue
        if re.match(r"^(\d+\s|-\s|D\s|NA\s|Note|Source)", s) or len(s) > 60:
            break
        vals = {p: r[j] if j < len(r) else None for p, j in cols.items()}
        (regions if block == "R" else countries).append((clean_label(s), vals))
    return regions, countries


def read_ins_t3(rows):
    """INS 1999 Table 3 (birth), grouped by region in source order."""
    hdr_idx = next(i for i, r in enumerate(rows) if str(r[0]).startswith("Region and country"))
    hdr = rows[hdr_idx]
    cols = {}
    for j, h in enumerate(hdr):
        if j and h not in (None, ""):
            p = period_of(re.sub(r"\s+\d+$", "", str(h).strip()))
            if p:
                cols[p] = j
    out = []
    for r in rows[hdr_idx + 1:]:
        lab = r[0]
        if lab is None or str(lab).strip() == "":
            continue
        s = str(lab).strip()
        if re.match(r"^(\d+\s|-\s)", s):
            break
        out.append((clean_label(s), {p: r[j] for p, j in cols.items()}))
    return out


INS_T3_REGIONS = {"europe", "asia", "africa", "oceania", "northamerica", "southamerica"}
INS_T3_SUB = {"caribbean", "centralamerica"}


def ins_t3_rows(items, source_id, years):
    rows = []
    region = sub = None
    for lab, vals in items:
        n = norm(lab)
        if n == "allcountries":
            lev, par = "total", ""
            region = sub = None
        elif n in INS_T3_REGIONS:
            lev, par, region, sub = "region", "All countries", lab, None
        elif n in INS_T3_SUB and region and norm(region) == "northamerica":
            lev, par, sub = "subregion", region, lab
        elif n.startswith("bornon") or n.startswith("unknown"):
            lev, par = "residual", "All countries"
            region = sub = None
        else:
            lev, par = "country", sub or region
        for p, v in vals.items():
            if p[0] not in years:
                continue
            c = to_count(v)
            if c == "SKIP":
                continue
            rows.append(dict(period_start=p[0], period_end=p[1], origin_label=lab, level=lev,
                             parent_label=par, count=c, basis="reported_annual", source_id=source_id))
    return rows


# --- region assignment for DHS alphabetical country lists -------------------
ALIASES = {  # later DHS spelling -> INS 1999 spelling (used only to look up the region)
    "antiguaandbarbuda": "antiguabarbuda", "bahamas": "bahamasthe", "bosniaandherzegovina": "bosniaherzegovina",
    "caboverde": "capeverde", "czechia": "czechrepublic", "czechoslovakiaformer": "czechoslovakia",
    "eswatini": "swaziland", "gambia": "gambiathe", "guineabissau": "guineabissau",
    "koreanorth": "korea", "koreasouth": "korea", "northmacedonia": "macedonia", "macedonia": "macedonia",
    "saintkittsandnevis": "stkittsnevis", "saintkittsnevis": "stkittsnevis", "saintlucia": "stlucia",
    "saintvincentandthegrenadines": "stvincentandthegrenadines", "slovakia": "slovakrepublic",
    "sovietunionformer": "sovietunion", "virginislandsbritish": "britishvirginislands",
    "virginislandsus": "usvirginislands", "usvirginislands": "usvirginislands",
    "chinapeoplesrepublic": "chinapeoplesrepublic", "micronesiafederatedstatesof": "micronesiafederatedstates",
    "turksandcaicosislands": "turksandcaicosislands", "yugoslaviaformer": "yugoslavia",
    "saotomeandprincipe": "saotomeandprincipe", "stpierreandmiquelon": "stpierreandmiquelon",
    "saintpierreandmiquelon": "stpierreandmiquelon", "burma": "burma", "myanmar": "burma",
    "cotedivoire": "cotedivoire", "germany": "germany", "timorleste": "indonesia",
    "pitcairnislands": "pitcairnisland", "wallisandfutunaislands": "wallisandfutunaislands",
}
EXTRA_REGION = {  # countries absent from the INS 1999 list -> DHS region (checked by sums below)
    "serbia": "Europe", "montenegro": "Europe", "kosovo": "Europe", "serbiaandmontenegroformer": "Europe",
    "serbiaandmontenegro": "Europe", "southsudan": "Africa", "curacao": "North America",
    "sintmaarten": "North America", "bonaire": "North America", "bonairesinteustatiusandsaba": "North America",
    "netherlandsantillesformer": "North America", "palestine": "Asia", "westbank": "Asia", "gaza": "Asia",
    "taiwan": "Asia", "macau": "Asia", "hongkong": "Asia", "guam": "Oceania", "puertorico": "North America",
    "unitedstates": "North America", "andorra": "Europe", "comoros": "Africa", "eritrea": "Africa",
    "saintbarthelemy": "North America", "saintmartin": "North America", "southkorea": "Asia",
    "northkorea": "Asia", "greenland": "North America", "frenchguiana": "South America",
    "guadeloupe": "North America", "martinique": "North America", "reunion": "Africa",
    "mayotte": "Africa", "stmaarten": "North America", "netherlandsantilles": "North America",
    "saintmartinfrench": "North America", "eswatiniformerlyswaziland": "Africa",
    "northmacedoniaformerlymacedonia": "Europe",
    # INS 1999 Table 3 put these former-Soviet republics under Europe; DHS (2000+) counts them in Asia.
    # Verified: moving exactly these 8 closes the DHS Asia/Europe region-sum gaps in every year.
    "armenia": "Asia", "azerbaijan": "Asia", "georgia": "Asia", "kazakhstan": "Asia", "kyrgyzstan": "Asia",
    "tajikistan": "Asia", "turkmenistan": "Asia", "uzbekistan": "Asia",
}


def build_region_lookup(ins_items):
    look = {}
    region = None
    for lab, _ in ins_items:
        n = norm(lab)
        if n in INS_T3_REGIONS:
            region = lab.strip()
            continue
        if n in INS_T3_SUB:
            continue
        if n == "allcountries" or n.startswith("born") or n.startswith("unknown"):
            continue
        if region:
            look[n] = region
    return look


def region_for(label, look):
    n = norm(label)
    for key in (n, ALIASES.get(n, n)):
        if key in EXTRA_REGION:
            return EXTRA_REGION[key]
        if key in look:
            return look[key]
    return None


def blocked_rows(regions, countries, source_id, years, look, name):
    rows = []
    unmapped = set()
    total_label = "Total"
    for lab, vals in regions:
        lev = "total" if norm(lab) == "total" else "region"
        for p, v in vals.items():
            if p[0] in years:
                c = to_count(v)
                if c != "SKIP":
                    rows.append(dict(period_start=p[0], period_end=p[1], origin_label=lab, level=lev,
                                     parent_label="" if lev == "total" else total_label, count=c,
                                     basis="reported_annual", source_id=source_id))
    for lab, vals in countries:
        n = norm(lab)
        if n == "total":
            continue
        if n.startswith("allothercountries"):
            lev, par = "residual", total_label
        elif n == "unknown":
            lev, par = "residual", "Unknown"
        else:
            lev, par = "country", region_for(lab, look)
            if par is None:
                unmapped.add(lab)
                par = ""
        for p, v in vals.items():
            if p[0] in years:
                c = to_count(v)
                if c != "SKIP":
                    rows.append(dict(period_start=p[0], period_end=p[1], origin_label=lab, level=lev,
                                     parent_label=par, count=c, basis="reported_annual", source_id=source_id))
    if unmapped:
        log(f"  [{name}] countries without region mapping: {sorted(unmapped)}")
    return rows


# ----------------------------------------------------------------------------
# DHS 2019 yearbook PDF (perma.cc capture), Table 2 annual pages / Table 3 / Table 1
# ----------------------------------------------------------------------------
VAL = r"(?:\d{1,3}(?:,\d{3})*|-|D|X)"


def pdf_text(path, first, last):
    return subprocess.run(["pdftotext", "-layout", "-f", str(first), "-l", str(last), path, "-"],
                          check=True, capture_output=True, text=True).stdout


def parse_pdf_rows(text, ncols):
    out = []
    pat = re.compile(r"^(?P<lab>\s*\S.*?)\s+(?P<vals>(?:" + VAL + r"\s+){" + str(ncols - 1) + "}" + VAL + r")\s*$")
    prev = ""
    for line in text.splitlines():
        m = pat.match(line)
        if not m:
            prev = line.strip()
            continue
        lab = clean_label(m.group("lab"))
        if lab.startswith("(") and prev and re.fullmatch(r"[A-Za-z ,.'-]+", prev):
            lab = prev + " " + lab   # label wrapped onto two lines, e.g. "North Macedonia / (formerly Macedonia)"
        prev = ""
        if not re.search(r"[A-Za-z]", lab) or lab.lower().startswith(("region", "of last", "fiscal")):
            continue
        out.append((lab, m.group("vals").split()))
    return out


# ----------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    fy22 = os.path.join(AIT, "lpr_fy2022.xlsx")
    fy23 = os.path.join(AIT, "lpr_fy2023.xlsx")
    z09 = os.path.join(AIT, "lpr2009.zip")
    z96 = os.path.join(AIT, "ins_yb1996.zip")
    z99 = os.path.join(AIT, "ins_yb1999.zip")
    yb19 = os.path.join(PERMA, "yearbook2019_tables1-3_p12-22.pdf")

    # ======================= Table 1: annual totals ==========================
    t1_22 = read_table1(xlsx_rows(fy22, "Table 1"))
    t1_23 = read_table1(xlsx_rows(fy23, "Table 1"))
    t1_09 = read_table1(xls_rows(z09, "table01.xls"))
    t1_19 = {}
    for line in pdf_text(yb19, 1, 1).splitlines():
        for y, n in re.findall(r"\b(1[89]\d\d|20[01]\d)\s*1?\s*[. ]*\s+(\d{1,3}(?:,\d{3})+|\d{1,3})(?=\s|$)", line):
            t1_19[int(y)] = int(n.replace(",", ""))
    log(f"Table 1: FY2022 workbook years {min(t1_22)}-{max(t1_22)} ({len(t1_22)}); FY2023 {min(t1_23)}-{max(t1_23)};"
        f" 2009 xls {min(t1_09)}-{max(t1_09)}; 2019 PDF {len(t1_19)} years")
    diffs19 = {y: (t1_19[y], t1_22[y]) for y in t1_19 if y in t1_22 and t1_19[y] != t1_22[y]}
    diffs09 = {y: (t1_09[y], t1_22[y]) for y in t1_09 if y in t1_22 and t1_09[y] != t1_22[y]}
    log(f"  cross-check 2019 PDF vs FY2022 workbook: {len(t1_19)} years compared, {len(diffs19)} differ {dict(list(diffs19.items())[:8])}")
    log(f"  cross-check 2009 xls vs FY2022 workbook: {len(t1_09)} years compared, {len(diffs09)} differ {dict(list(diffs09.items())[:8])}")
    rdiff = [abs(t1_23[y] - t1_22[y]) for y in t1_22 if y in t1_23]
    log(f"  FY2023 (rounded) vs FY2022 (unrounded): max |diff| {max(rdiff)} over {len(rdiff)} years")

    def fy_note(y):
        parts = []
        if y <= 1831 or 1844 <= y <= 1849:
            parts.append("year ending Sep 30")
        if 1833 <= y <= 1842 or 1851 <= y <= 1867:
            parts.append("year ending Dec 31")
        if y == 1832:
            parts.append("15 months ending Dec 31 1832")
        if y == 1843:
            parts.append("9 months ending Sep 30 1843")
        if y == 1850:
            parts.append("15 months ending Dec 31 1850")
        if y == 1868:
            parts.append("6 months ending Jun 30 1868")
        if 1869 <= y <= 1975:
            parts.append("year ending Jun 30")
        if y == 1976:
            parts.append("15 months Jul 1 1975-Sep 30 1976 (FY end changed)")
        if y >= 1977:
            parts.append("year ending Sep 30")
        if y <= 1867:
            parts.append("alien passenger arrivals at seaports")
        elif y <= 1891 or 1895 <= y <= 1897:
            parts.append("immigrant alien arrivals")
        else:
            parts.append("immigrants admitted / persons obtaining LPR status")
        if 1892 <= y <= 1903:
            parts.append("cabin-class arrivals not counted")
        if y < 1908:
            parts.append("land arrivals not completely enumerated")
        if 1989 <= y <= 1994:
            parts.append("includes IRCA legalization adjustments (peak 1989-1991)")
        if y in (2020, 2021):
            parts.append("COVID-19 processing slowdown")
        if y >= 2023:
            parts.append("OHSS rounded to nearest 10")
        return "; ".join(parts)

    with open(os.path.join(OUT, "flows_totals_1820_present.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "total", "source_id", "note"])
        for y in range(1820, max(t1_23) + 1):
            if y in t1_22:
                w.writerow([y, t1_22[y], "ohss_yb2022_lpr_xlsx", fy_note(y)])
            else:
                w.writerow([y, t1_23[y], "ohss_yb2023_lpr_xlsx", fy_note(y)])
    for y, ref in ((1907, 1285349), (1991, 1826595), (1914, 1218480), (1854, 427833)):
        log(f"  well-known check {y}: total={t1_22[y]:,} (expected about {ref:,})")

    # ======================= Table 2: last residence =========================
    rows_all = []

    # (a) decades 1820-2019 + annual 2020-2022 from the FY2022 workbook
    r22 = xlsx_rows(fy22, "Table 2")
    h22 = next(i for i, r in enumerate(r22) if r[0] and str(r[0]).startswith("Region and country"))
    labs, data = read_selected(r22, h22, lambda p: True)
    hier = classify_selected(labs)
    dec = OrderedDict((p, v) for p, v in data.items() if p[1] - p[0] == 9)
    log(f"FY2022 Table 2: {len(labs)} rows; decades {list(dec)[0]}..{list(dec)[-1]}; annual {[p for p in data if p[0]==p[1]]}")
    rows_dec = rows_from_table(labs, dec, "ohss_yb2022_lpr_xlsx", "reported_decade", hier)
    validate(rows_dec, "decades FY2022")
    rows_all += rows_dec
    ann2022 = OrderedDict((p, v) for p, v in data.items() if p[0] == p[1])
    sel_2020_22 = rows_from_table(labs, ann2022, "ohss_yb2022_lpr_xlsx", "reported_annual", hier)
    validate(sel_2020_22, "annual 2020-2022 selected (FY2022) [not written; cross-check only]")
    # decade sums vs Table 1
    for (ps, pe), vals in dec.items():
        tot = to_count(vals[0])
        t1s = sum(t1_22[y] for y in range(ps, pe + 1))
        if tot != t1s:
            log(f"  decade {ps}-{pe}: Table 2 total {tot:,} vs sum of Table 1 years {t1s:,} (diff {tot-t1s:+,})")

    # cross-check decades vs 2019 PDF (pages 2-5 of the extract = Table 2 decade pages)
    pdf_dec = parse_pdf_rows(pdf_text(yb19, 2, 3), 10) + parse_pdf_rows(pdf_text(yb19, 4, 5), 9)
    pdfd = defaultdict(list)
    for lab, vals in pdf_dec:
        pdfd[norm(lab)].append(vals)
    nchk = nbad = 0
    for i, lab in enumerate(labs):
        got = pdfd.get(norm(lab))
        if not got or len(got) < 2:
            continue
        pv = got[0] + got[1]  # 1820s..1910s + 1920s..2000s
        xv = [dec[p][i] for p in list(dec)[:19]]
        for a, b in zip(pv, xv):
            nchk += 1
            if to_count(a) != to_count(b):
                nbad += 1
    log(f"  cross-check decades 1820s-2000s, 2019 PDF vs FY2022 workbook: {nchk} cells compared, {nbad} differ")

    # (b) annual 1988-1993 from INS 1996 yearbook, 1994-1999 from INS 1999 yearbook (Table 2)
    r96 = xls_rows(z96, "table2.xls")
    h96 = next(i for i, r in enumerate(r96) if any(str(x).strip() == "1988" for x in r))
    labs96, data96 = read_selected(r96, h96, lambda p: p[0] == p[1] and 1988 <= p[0] <= 1993)
    hier96 = classify_selected(labs96)
    rows96 = rows_from_table(labs96, data96, "ins_syb1996_xls", "reported_annual", hier96)
    validate(rows96, "INS 1996 Table 2 (1988-1993)")
    r99 = xls_rows(z99, "1999/Table_2.xls")
    h99 = next(i for i, r in enumerate(r99) if str(r[0]).strip().startswith("last residence"))
    labs99, data99 = read_selected(r99, h99, lambda p: p[0] == p[1] and 1994 <= p[0] <= 1999)
    hier99 = classify_selected(labs99)
    rows99 = rows_from_table(labs99, data99, "ins_syb1999_xls", "reported_annual", hier99)
    validate(rows99, "INS 1999 Table 2 (1994-1999)")
    rows_all += rows96 + rows99
    for y in (1990, 1991, 1999):
        ins = next(r["count"] for r in rows96 + rows99 if r["period_start"] == y and r["level"] == "total")
        log(f"  INS-era total {y}: {ins:,} vs DHS Table 1 {t1_22[y]:,} (diff {ins - t1_22[y]:+,})")

    # (c) annual 2000-2009 from the DHS 2009 yearbook (table02.xls)
    r09 = xls_rows(z09, "table02.xls")
    h09 = next(i for i, r in enumerate(r09) if str(r[0]).startswith("Region and country"))
    labs09, data09 = read_selected(r09, h09, lambda p: p[0] == p[1] and 2000 <= p[0] <= 2009)
    hier09 = classify_selected(labs09)
    rows09 = rows_from_table(labs09, data09, "dhs_yb2009_xls", "reported_annual", hier09)
    validate(rows09, "DHS 2009 Table 2 (2000-2009)")
    rows_all += rows09

    # (d) annual 2010-2013 from the DHS 2019 yearbook PDF (Table 2 annual pages = extract pp. 6-7)
    pdf_ann = parse_pdf_rows(pdf_text(yb19, 6, 7), 10)
    labs19 = [l for l, _ in pdf_ann]
    years19 = list(range(2010, 2020))
    data19 = OrderedDict(((y, y), [v[i] for _, v in pdf_ann]) for i, y in enumerate(years19))
    hier19 = classify_selected(labs19)
    rows19 = rows_from_table(labs19, data19, "dhs_yb2019_pdf_perma", "reported_annual", hier19)
    validate(rows19, "DHS 2019 PDF Table 2 (2010-2019)")
    log(f"  2019 PDF Table 2 annual: {len(labs19)} rows parsed (FY2022 workbook has {len(labs)})")
    rows_all += [r for r in rows19 if r["period_start"] <= 2013]
    for y in years19:
        t = next(r["count"] for r in rows19 if r["period_start"] == y and r["level"] == "total")
        if t != t1_22[y]:
            log(f"  2019 PDF Table 2 total {y} {t:,} != Table 1 {t1_22[y]:,}")

    # (e) annual 2014-2023, all countries (rounded to 10) from the FY2023 workbook
    ins_t3 = read_ins_t3(xls_rows(z99, "1999/Table_3.xls"))
    look = build_region_lookup(ins_t3)
    r23 = xlsx_rows(fy23, "Table 2")
    h23 = next(i for i, r in enumerate(r23) if r[0] and str(r[0]).startswith("Region and country"))
    reg23, cty23 = read_blocked(r23, h23)
    rows23 = blocked_rows(reg23, cty23, "ohss_yb2023_lpr_xlsx", set(range(2014, 2024)), look, "FY2023 Table 2")
    validate(rows23, "FY2023 Table 2 full-country (2014-2023, rounded)", tol_per_row=10)
    rows_all += rows23
    # rounded full table vs unrounded selected table, overlap years
    for y in (2014, 2019, 2022):
        sel = {r["origin_label"]: r["count"] for r in (rows19 if y < 2020 else sel_2020_22)
               if r["period_start"] == y and r["level"] == "country"}
        full = {r["origin_label"]: r["count"] for r in rows23 if r["period_start"] == y}
        common = [k for k in sel if k in full]
        md = max(abs(sel[k] - full[k]) for k in common)
        log(f"  {y}: selected-table vs full-table, {len(common)} common countries, max |diff| {md}")

    # (f) annual 1820-1957 from HSUS 1960 (series C 88-114), OCR text validated by row sums
    hs_rows, hs_msgs = hsus1960.parse(os.path.join(RAW, "hsus1960_chC", "C88_114_tesseract_ocr.csv"),
                                      os.path.join(RAW, "hsus1960_chC", "hist_stats_colonial-1957-chC.pdf"), t1_22)
    for m in hs_msgs:
        log(m)
    rows_all += hs_rows
    validate(hs_rows, "HSUS 1960 C 88-114 (annual 1820-1957)")
    hs_tot = {r["period_start"]: r["count"] for r in hs_rows if r["level"] == "total"}
    dd = {y: (hs_tot[y], t1_22[y]) for y in hs_tot if hs_tot[y] != t1_22.get(y)}
    log(f"  HSUS 1960 totals vs DHS Table 1: {len(hs_tot)} years, {len(dd)} differ: {dict(list(dd.items())[:10])}")

    rows_all.sort(key=lambda r: (r["period_start"], r["period_end"], r["source_id"]))
    cols = ["period_start", "period_end", "origin_label", "level", "parent_label", "count", "basis", "source_id"]
    with open(os.path.join(OUT, "flows_by_origin_1820_present.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows_all:
            r = dict(r)
            r["count"] = "" if r["count"] is None else r["count"]
            w.writerow(r)
    log(f"flows_by_origin rows written: {len(rows_all)}")
    # duplicate guard: one source per (period, label)
    seen = defaultdict(set)
    for r in rows_all:
        seen[(r["period_start"], r["period_end"])].add(r["source_id"])
    multi = {k: v for k, v in seen.items() if len(v) > 1}
    log(f"  periods with more than one source: {multi if multi else 'none'}")

    # ======================= Table 3: country of birth =======================
    birth = []
    birth += ins_t3_rows(ins_t3, "ins_syb1999_xls", set(range(1989, 2000)))
    validate(birth, "INS 1999 Table 3 birth (1989-1999)")
    r09b = xls_rows(z09, "table03d.xls")
    h09b = next(i for i, r in enumerate(r09b) if str(r[0]).startswith("Region and country"))
    reg, cty = read_blocked(r09b, h09b)
    b09 = blocked_rows(reg, cty, "dhs_yb2009_xls", set(range(2000, 2010)), look, "2009 Table 3")
    validate(b09, "DHS 2009 Table 3 birth (2000-2009)", tol_per_row=1)
    birth += b09
    # 2010-2012 from 2019 PDF Table 3 (extract pp. 8-11): REGION block then COUNTRY block
    t3 = parse_pdf_rows(pdf_text(yb19, 8, 11), 10)
    regs, ctys, seen_tot = [], [], 0
    for lab, vals in t3:
        if norm(lab) == "total":
            seen_tot += 1
            (regs if seen_tot == 1 else ctys).append((lab, vals))
            continue
        (regs if seen_tot == 1 else ctys).append((lab, vals))
    to_vals = lambda v: {(y, y): v[i] for i, y in enumerate(range(2010, 2020))}
    b19 = blocked_rows([(l, to_vals(v)) for l, v in regs], [(l, to_vals(v)) for l, v in ctys],
                       "dhs_yb2019_pdf_perma", {2010, 2011, 2012}, look, "2019 PDF Table 3")
    validate(b19, "DHS 2019 PDF Table 3 birth (2010-2012)", tol_per_row=1)
    birth += b19
    r22b = xlsx_rows(fy22, "Table 3d")
    h22b = next(i for i, r in enumerate(r22b) if r[0] and str(r[0]).startswith("Region and country"))
    reg, cty = read_blocked(r22b, h22b)
    b22 = blocked_rows(reg, cty, "ohss_yb2022_lpr_xlsx", set(range(2013, 2023)), look, "FY2022 Table 3d")
    validate(b22, "FY2022 Table 3d birth (2013-2022)", tol_per_row=1)
    birth += b22
    r23b = xlsx_rows(fy23, "Table 3")
    h23b = next(i for i, r in enumerate(r23b) if r[0] and str(r[0]).startswith("Region and country"))
    reg, cty = read_blocked(r23b, h23b)
    b23 = blocked_rows(reg, cty, "ohss_yb2023_lpr_xlsx", {2023}, look, "FY2023 Table 3")
    validate(b23, "FY2023 Table 3 birth (2023, rounded)", tol_per_row=10)
    birth += b23
    birth.sort(key=lambda r: (r["period_start"], r["source_id"]))
    with open(os.path.join(OUT, "flows_by_birth_1989_present.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in birth:
            r = dict(r)
            r["count"] = "" if r["count"] is None else r["count"]
            w.writerow(r)
    log(f"flows_by_birth rows written: {len(birth)}")


SOURCES = [
    ("ohss_yb2022_lpr_xlsx",
     "U.S. Dept. of Homeland Security, Office of Homeland Security Statistics (OHSS), 2022 Yearbook of Immigration "
     "Statistics, Lawful Permanent Residents tables (Table 1; Table 2 by region and selected country of last "
     "residence, FY1820-2022; Table 3d by country of birth FY2013-2022). File "
     "2023_0818_plcy_yearbook_lawful_permanent_residents_fy2022_0.xlsx",
     "https://wayback.archive-it.org/all/20241115094237/https://ohss.dhs.gov/sites/default/files/2023-12/2023_0818_plcy_yearbook_lawful_permanent_residents_fy2022_0.xlsx",
     "Archive-It (Internet Archive) capture 2024-11-15 of the OHSS file; ohss.dhs.gov itself blocks this environment. "
     "Unrounded. Used for annual totals 1820-2022 and decade-by-country 1820s-2010s; raw file data/raw/archiveit_ohss/lpr_fy2022.xlsx"),
    ("ohss_yb2023_lpr_xlsx",
     "OHSS, 2023 Yearbook of Immigration Statistics, Lawful Permanent Residents tables (Table 1 FY1820-2023; Table 2 "
     "by region and country of last residence FY2014-2023, all countries; Table 3 by country of birth FY2014-2023). "
     "File 2024_0906_ohss_yearbook_lawful_permanent_residents_fy2023_0.xlsx",
     "https://wayback.archive-it.org/all/20241115000302/https://ohss.dhs.gov/sites/default/files/2024-09/2024_0906_ohss_yearbook_lawful_permanent_residents_fy2023_0.xlsx",
     "Archive-It capture 2024-11-15. All cells rounded by OHSS to the nearest 10 (privacy). Used for total 2023, "
     "annual last-residence by country 2014-2023 and birth 2023; raw file data/raw/archiveit_ohss/lpr_fy2023.xlsx"),
    ("dhs_yb2009_xls",
     "DHS Office of Immigration Statistics, 2009 Yearbook of Immigration Statistics, LPR tables (table02.xls: by "
     "region and selected country of last residence, decades 1820-1999 and FY2000-2009; table03d.xls: by country of "
     "birth FY2000-2009; table01.xls). Bundle LPR2009_0.zip",
     "https://wayback.archive-it.org/all/20241116003221/https://ohss.dhs.gov/sites/default/files/2023-12/LPR2009_0.zip",
     "Archive-It capture 2024-11-16. Used for annual last residence 2000-2009 and birth 2000-2009; raw data/raw/archiveit_ohss/lpr2009.zip"),
    ("dhs_yb2019_pdf_perma",
     "DHS Office of Immigration Statistics, 2019 Yearbook of Immigration Statistics (PDF), pp. 5-15 = Tables 1-3",
     "https://perma.cc/C24E-JGKR (archive.org item perma_cc_C24E-JGKR) of https://www.dhs.gov/sites/default/files/publications/immigration-statistics/yearbook/2019/yearbook_immigration_statistics_2019.pdf",
     "Perma.cc capture 2022-08-25 (WARC from archive.org). Only PDF pages 12-22 kept (data/raw/perma_cc_dhs/). Text "
     "layer is born-digital and clean. Used for annual last residence 2010-2013 and birth 2010-2012, and as a cross-check "
     "of Table 1 and the decade table"),
    ("ins_syb1996_xls",
     "U.S. Immigration and Naturalization Service, 1996 Statistical Yearbook of the INS, table2.xls (Immigration by "
     "region and selected country of last residence, FY1820-1996). Bundle statyearbk96_0.zip",
     "https://wayback.archive-it.org/all/20241116003642/https://ohss.dhs.gov/sites/default/files/2023-12/statyearbk96_0.zip",
     "Archive-It capture 2024-11-16. Used for annual last residence 1988-1993 (INS-era, unrevised figures)"),
    ("ins_syb1999_xls",
     "U.S. INS, 1999 Statistical Yearbook of the INS, Table_2.xls (last residence, FY1820-1999) and Table_3.xls "
     "(immigrants admitted by region and country of birth, FY1989-99). Bundle ois_1999yb_4_0.zip",
     "https://wayback.archive-it.org/all/20241116003638/https://ohss.dhs.gov/sites/default/files/2023-12/ois_1999yb_4_0.zip",
     "Archive-It capture 2024-11-16. Used for annual last residence 1994-1999 and birth 1989-1999 (INS-era figures; "
     "FY1998 revised in this edition). Table 3's grouping also supplies the base country->region lookup"),
    ("hsus1960_C88_114",
     "U.S. Bureau of the Census, Historical Statistics of the United States, Colonial Times to 1957 (Washington, 1960), "
     "Chapter C, Series C 88-114 'Immigrants, by country: 1820 to 1957', pp. 56-59",
     "https://www2.census.gov/library/publications/1960/compendia/hist_stats_colonial-1957/hist_stats_colonial-1957-chC.pdf",
     "Scanned PDF. Digits read twice (Tesseract column-by-column OCR -> data/raw/hsus1960_chC/C88_114_tesseract_ocr.csv, "
     "and the PDF's own text layer) and reconciled against the table's five accounting identities and DHS Table 1; "
     "only identity-consistent values are kept (see flows_NOTES.md)"),
]


def write_sources():
    with open(os.path.join(OUT, "sources_flows.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "citation", "url", "accessed", "notes"])
        for sid, cit, url, notes in SOURCES:
            w.writerow([sid, cit, url, "2026-10-18", notes])


if __name__ == "__main__":
    main()
    write_sources()
