"""Build data/processed/population_1610_1840.csv.

Sources
- HSUS 1975 (Bicentennial ed.), Series Z 1-19 "Estimated Population of American
  Colonies: 1610 to 1780" (p. 1168; raw scan in data/raw/hsus_1975_chZ/chZ.pdf).
  * Totals ("White and Negro") are machine-read from Wikipedia's reproduction
    (data/raw/wikipedia/List_of_colonial_and_pre-Federal_US_historical_population.wiki)
    and verified against the HSUS Total row (read off the scan) by column sums.
  * The "Negro" panel is not reproduced on Wikipedia; it was transcribed by hand from
    the fetched HSUS scan (page image) and is verified here by column sums against the
    HSUS Negro Total row.
- Census Working Paper 56 (Gibson & Jung 2002), Appendix A tables A-21..A-26
  (1840..1790): total, Black, free Black, slave, by state (current boundaries).
Run: python3 -I scripts/colonial/build_population.py
"""
import csv
import re
from pathlib import Path

import openpyxl

ROOT = Path("/home/user/migration")
WIKI = ROOT / "data/raw/wikipedia/List_of_colonial_and_pre-Federal_US_historical_population.wiki"
WP56 = ROOT / "data/raw/census_twps0056/appendixA.xlsx"
OUT = ROOT / "data/processed/population_1610_1840.csv"

YEARS_A = [1610, 1620, 1630, 1640, 1650, 1660, 1670, 1680, 1690]
YEARS_B = [1700, 1710, 1720, 1730, 1740, 1750, 1760, 1770, 1780]

# ---- HSUS Z 1-19 Total row and Negro panel, transcribed from the scan (p. 1168) ----
HSUS_TOTAL_ROW = {1780: 2780369, 1770: 2148076, 1760: 1593625, 1750: 1170760, 1740: 905563,
                  1730: 629445, 1720: 466185, 1710: 331711, 1700: 250888, 1690: 210372,
                  1680: 151507, 1670: 111935, 1660: 75058, 1650: 50368, 1640: 26634,
                  1630: 4646}
# 1620 and 1610 appear only in an inset: Plymouth 102 + Virginia 2,200 (1620); Virginia 350 (1610)
HSUS_INSET = {1620: {"Plymouth": 102, "Virginia": 2200}, 1610: {"Virginia": 350}}

NEG_YEARS = [1780, 1770, 1760, 1750, 1740, 1730, 1720, 1710, 1700, 1690, 1680, 1670, 1660,
             1650, 1640, 1630]
N = None
NEGRO = {  # columns follow NEG_YEARS
    "Total":          [575420, 459822, 325806, 236420, 150024, 91021, 68839, 44866, 27817, 16729, 6971, 4535, 2920, 1600, 597, 60],
    "Maine":          [458, 475, 300, N, N, N, N, N, N, N, N, N, N, N, N, N],
    "New Hampshire":  [541, 654, 600, 550, 500, 200, 170, 150, 130, 100, 75, 65, 50, 40, 30, N],
    "Vermont":        [50, 25, N, N, N, N, N, N, N, N, N, N, N, N, N, N],
    "Massachusetts":  [4822, 4754, 4566, 4075, 3035, 2780, 2150, 1310, 800, 400, 170, 160, 422, 295, 150, N],
    "Rhode Island":   [2671, 3761, 3468, 3347, 2408, 1648, 543, 375, 300, 250, 175, 115, 65, 25, N, N],
    "Connecticut":    [5885, 5698, 3783, 3010, 2598, 1490, 1093, 750, 450, 200, 50, 35, 25, 20, 15, N],
    "New York":       [21054, 19112, 16340, 11014, 8996, 6956, 5740, 2811, 2256, 1670, 1200, 690, 600, 500, 232, 10],
    "New Jersey":     [10460, 8220, 6567, 5354, 4366, 3008, 2385, 1332, 840, 450, 200, 60, N, N, N, N],
    "Pennsylvania":   [7855, 5761, 4409, 2872, 2055, 1241, 2000, 1575, 430, 270, 25, N, N, N, N, N],
    "Delaware":       [2996, 1836, 1733, 1496, 1035, 478, 700, 500, 135, 82, 55, 40, 30, 15, N, N],
    "Maryland":       [80515, 63818, 49004, 43450, 24031, 17220, 12499, 7945, 3227, 2162, 1611, 1190, 758, 300, 20, N],
    "Virginia":       [220582, 187605, 140570, 101452, 60000, 30000, 26559, 23118, 16390, 9345, 3000, 2000, 950, 405, 150, 50],
    "North Carolina": [91000, 69600, 33554, 19800, 11000, 6000, 3000, 900, 415, 300, 210, 150, 20, N, N, N],
    "South Carolina": [97000, 75178, 57334, 39000, 30000, 20000, 12000, 4100, 2444, 1500, 200, 30, N, N, N, N],
    "Georgia":        [20831, 10625, 3578, 1000, N, N, N, N, N, N, N, N, N, N, N, N],
    "Kentucky":       [7200, 2500, N, N, N, N, N, N, N, N, N, N, N, N, N, N],
    "Tennessee":      [1500, 200, N, N, N, N, N, N, N, N, N, N, N, N, N, N],
}
# Notes from HSUS footnotes: RI and CT 1780 Negro figures include some Indians (fn 7);
# Virginia 1620 total includes 20 Negroes (fn 8). Plymouth has no Negro row.
NEGRO_1620 = {"Virginia": 20}
HSUS_CORRECTIONS = {("New Hampshire", 1700): 4958}


def parse_wiki():
    """Return {colony: {year: value or None}} from the two wikitables."""
    txt = WIKI.read_text()
    secA = txt[txt.index("==1610–1690=="):txt.index("==1700–1780==")]
    secB = txt[txt.index("==1700–1780=="):txt.index("==See also==")]
    out = {}
    for sec, years, skip in [(secA, YEARS_A, 1), (secB, YEARS_B, 0)]:
        rows = sec.split("\n|-")
        for r in rows:
            lines = [l for l in r.strip().split("\n") if l.startswith("|") and not l.startswith("|}")]
            if not lines:
                continue
            m = re.search(r"'''(?:\[\[[^|\]]*\|)?([^\]']+?)(?:\]\])?'''", lines[0])
            if not m:
                continue
            name = m.group(1).strip()
            cells = lines[1 + skip:]
            vals = []
            for c in cells:
                v = c.split("|")[-1].strip()
                v = re.sub(r"\{\{[^}]*\}\}", "", v).strip()
                v = v.replace(",", "")
                vals.append(int(v) if v.isdigit() else None)
            if len(vals) != len(years):
                raise SystemExit(f"cell count mismatch for {name}: {len(vals)}")
            out.setdefault(name, {}).update(dict(zip(years, vals)))
    return out


def colonial_rows():
    wiki = parse_wiki()
    total = wiki.pop("Total")
    # Cells where the Wikipedia reproduction differs from the HSUS scan (scan wins;
    # verified by the column sum equalling the printed HSUS Total row).
    for (colony, y), v in HSUS_CORRECTIONS.items():
        print(f"NOTE: correcting Wikipedia {colony} {y}: {wiki[colony][y]} -> HSUS {v}")
        wiki[colony][y] = v
    # check wiki colony sums against wiki total row and the HSUS total row from the scan
    for y in YEARS_A + YEARS_B:
        s = sum(v.get(y) or 0 for v in wiki.values())
        hs = HSUS_TOTAL_ROW.get(y, sum(HSUS_INSET.get(y, {}).values()))
        assert s == hs, (y, s, hs)
        if total[y] != hs:
            print(f"NOTE: Wikipedia Total row {y} = {total[y]} differs from HSUS {hs} (colony sum {s})")
    # inset check
    for y, d in HSUS_INSET.items():
        for k, v in d.items():
            assert wiki[k][y] == v, (k, y, wiki[k][y], v)
    # Negro panel column sums
    for i, y in enumerate(NEG_YEARS):
        s = sum((vals[i] or 0) for k, vals in NEGRO.items() if k != "Total")
        assert s == NEGRO["Total"][i], ("negro", y, s, NEGRO["Total"][i])
    rows = []
    for colony, byyear in sorted(wiki.items()):
        for y in YEARS_A + YEARS_B:
            tot = byyear.get(y)
            if tot is None:
                continue
            blk = None
            if colony in NEGRO and y in NEG_YEARS:
                blk = NEGRO[colony][NEG_YEARS.index(y)]
            elif y == 1620 and colony in NEGRO_1620:
                blk = NEGRO_1620[colony]
            if y == 1780:
                utype = "state" if colony not in ("Maine", "Vermont", "Kentucky", "Tennessee") else "territory"
            else:
                utype = "colony"
            if colony in ("Maine", "Kentucky", "Tennessee", "Vermont") and y < 1780:
                utype = "territory"
            rows.append({"year": y, "unit": colony, "unit_type": utype, "total": tot,
                         "black": "" if blk is None else blk, "enslaved": "",
                         "source_id": "hsus1975_Z1_19"})
    return rows


STATEHOOD = {  # year of statehood (for unit_type); others were original states
    "Vermont": 1791, "Kentucky": 1792, "Tennessee": 1796, "Ohio": 1803, "Louisiana": 1812,
    "Indiana": 1816, "Mississippi": 1817, "Illinois": 1818, "Alabama": 1819, "Maine": 1820,
    "Missouri": 1821, "Arkansas": 1836, "Michigan": 1837, "Florida": 1845, "Iowa": 1846,
    "Wisconsin": 1848, "West Virginia": 1863, "District of Columbia": None,
}
ORIGINAL = {"New Hampshire", "Massachusetts", "Rhode Island", "Connecticut", "New York",
            "New Jersey", "Pennsylvania", "Delaware", "Maryland", "Virginia", "North Carolina",
            "South Carolina", "Georgia"}


def census_rows():
    wb = openpyxl.load_workbook(WP56, read_only=True)
    sheets = {1840: "1840 Table A-21", 1830: "1830 Table A-22", 1820: "1820 Table A-23",
              1810: "1810 Table A-24", 1800: "1800 Table A-25", 1790: "1790 Table A-26"}
    us_totals = {}
    rows = []
    for year, sh in sheets.items():
        ws = wb[sh]
        in_states = False
        stsum = 0
        for r in ws.iter_rows(values_only=True):
            a = r[0]
            if not isinstance(a, str):
                continue
            name = a.strip().lstrip(".").strip().rstrip(".").strip()
            name = re.sub(r"\.{3,}.*$", "", name).strip()
            if a.strip().startswith("United States"):
                us_totals[year] = r[1]
            if a.startswith("DIVISION AND STATE"):
                in_states = True
                continue
            if a.startswith("AS PUBLISHED"):
                in_states = False
                continue
            if not in_states or not a.strip().startswith("."):
                continue

            def num(x):
                return 0 if x in ("-", None, " ") else int(x)
            tot, blk, free, slave = num(r[1]), num(r[5]), num(r[7]), num(r[9])
            assert free + slave == blk, (year, name, free, slave, blk)
            stsum += tot
            if name in ORIGINAL:
                utype = "state"
            elif name == "District of Columbia":
                utype = "territory"
            else:
                sy = STATEHOOD.get(name)
                utype = "state" if (sy is not None and year >= sy) else "territory"
            rows.append({"year": year, "unit": name, "unit_type": utype, "total": tot,
                         "black": blk, "enslaved": slave, "source_id": "census_twps0056_appA"})
        if stsum != us_totals[year]:
            print(f"NOTE: {year} sum of state rows {stsum} != WP56 US total {us_totals[year]} "
                  f"(diff {stsum - us_totals[year]})")
    return rows, us_totals


def main():
    rows = colonial_rows()
    crow, us = census_rows()
    rows += crow
    rows.sort(key=lambda r: (r["year"], r["unit"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "unit", "unit_type", "total", "black",
                                          "enslaved", "source_id"])
        w.writeheader()
        w.writerows(rows)
    print("rows", len(rows), "US census totals", us)


if __name__ == "__main__":
    main()
