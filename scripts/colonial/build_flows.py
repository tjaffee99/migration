"""Build data/processed/flows_colonial_by_origin.csv (European & other non-African arrivals,
1607-1819, plus Fogleman's African/status aggregates for reference).

Every hand-entered number carries an `evidence` string that must occur verbatim (after
whitespace normalisation) in the saved raw file it came from; the script asserts this.
Tables from Tomlins (2001) are parsed directly from the pdftotext output.

The `note` column starts with a series tag:
  series=primary  -> non-overlapping best-estimate series (sum these for totals)
  series=subset   -> regional/sub-group detail already contained in a primary row
  series=alt      -> alternative estimate for a period/group already covered (do not add)
Run: python3 -I scripts/colonial/build_flows.py
"""
import csv
import re
from pathlib import Path

ROOT = Path("/home/user/migration")
RAW = ROOT / "data/raw"
OUT = ROOT / "data/processed/flows_colonial_by_origin.csv"
FIELDS = ["period_start", "period_end", "origin_label", "count", "low", "high", "destination",
          "status", "source_id", "note"]

_cache = {}


def text(rel):
    if rel not in _cache:
        t = (RAW / rel).read_text(encoding="utf-8", errors="replace")
        _cache[rel] = norm(t)
    return _cache[rel]


def norm(t):
    # compare on ASCII letters/digits only, so pdftotext ligature/dash mojibake does not matter
    return re.sub(r"[^A-Za-z0-9]", "", t).lower()


def check(rel, evidence):
    ev = norm(evidence)
    assert ev in text(rel), f"evidence not found in {rel}: {evidence!r}"


rows = []


def add(ps, pe, origin, count, low="", high="", dest="", status="mixed", src="", note="",
        raw=None, evidence=None):
    if raw and evidence:
        for ev in ([evidence] if isinstance(evidence, str) else evidence):
            check(raw, ev)
    rows.append({"period_start": ps, "period_end": pe, "origin_label": origin, "count": count,
                 "low": low, "high": high, "destination": dest, "status": status,
                 "source_id": src, "note": note})


TOM = "tomlins_2001_laborhistory/tomlins.txt"
tom_lines = (RAW / TOM).read_text(encoding="utf-8", errors="replace").splitlines()

# ---------------------------------------------------------------------------------------
# 1. Fogleman (1992) decade x European group, 1700-1775, as reproduced in Tomlins (2001)
#    Appendix III Table A1 (in thousands). PRIMARY for 1700-1775.
# ---------------------------------------------------------------------------------------
i0 = next(i for i, l in enumerate(tom_lines) if l.startswith("Decade ending       German"))
hdr = ["German", "N. Irish", "S. Irish", "Scots", "English", "Welsh", "Other"]
LABEL = {"German": "Germans", "N. Irish": "Northern Irish (Ulster)", "S. Irish": "Southern Irish",
         "Scots": "Scots", "English": "English", "Welsh": "Welsh",
         "Other": "Other Europeans"}
colsum = {h: 0.0 for h in hdr}
grand = 0.0
for l in tom_lines[i0 + 1:i0 + 12]:
    parts = l.split()
    if not parts:
        continue
    if parts[0] == "Total":
        tot = [float(x) for x in parts[1:]]
        for h, v in zip(hdr, tot[:-1]):
            assert abs(colsum[h] - v) < 0.051, (h, colsum[h], v)
        assert abs(grand - tot[-1]) < 0.051, (grand, tot[-1])
        assert abs(tot[-1] - 307.4) < 1e-9
        break
    end = int(parts[0])
    vals = [float(x) for x in parts[1:]]
    assert abs(sum(vals[:-1]) - vals[-1]) < 0.051, (end, vals)
    grand += vals[-1]
    start = end - 9
    pend = 1775 if end == 1779 else end
    for h, v in zip(hdr, vals[:-1]):
        colsum[h] += v
        add(start, pend, LABEL[h], int(round(v * 1000)), dest="Thirteen colonies",
            status="mixed", src="fogleman1992_jih_via_tomlins2001",
            note=("series=primary; Fogleman JIH 22:4 (1992) estimate reproduced in Tomlins (2001) "
                  "Table A1 (thousands, 1 decimal => rounded to 100); voluntary + convict migrants"
                  + ("; Tomlins labels this 'decade ending 1779' but Fogleman's series ends 1775"
                     if end == 1779 else "")))

# Group totals 1700-1775 with ranges from Tomlins' review of the literature (ALT rows)
alt_ranges = [
    ("Germans", 84500, 84500, 120000,
     "low = Fogleman; other scholars suggest 90,000-120,000 (Wokeck, Grubb, Roeber, Moltmann, Bailyn); "
     "Wokeck (1999) 111,000 to all North America",
     ["suggests a range of 90,000± 120,000", "German migration to all of North America of 111,000"]),
    ("Irish (Northern + Southern)", 108600, 65000, 108600,
     "Tomlins: range for Irish immigration 65,000-108,000 (Cullen/Wokeck low; Fogleman 108,600 "
     "treated as a well-documented upper bound); Purvis 114,000 Ulster; Bailyn/Purvis imply 150-250,000",
     ["Fogleman’ s aggregate of 108,600", "range for Irish immigration at 65,000± 108,000"]),
    ("Scots", 35300, 35300, 65300,
     "Purvis 62,500 (concurred by Smout, Landsman & Devine); Bailyn 40,000 for 1760-75 alone; "
     "Tomlins suggests Scots ~30,000 above Fogleman (high = 35,300 + 30,000)",
     ["Fogleman’ s ® gure for Scottish migration, 35,300", "that of 62,500 suggested by Purvis",
      "Scottish total (somewhat more con® dently, given the greater scholarly consensus here) about 30,000 larger"]),
    ("English and Welsh", 73100, 73100, 88100,
     "Fogleman English 44,100 + Welsh 29,000; Tomlins suggests ~15,000 more; Canny: 50,000 English "
     "incl. convicts 1700-1775; Purvis-ratio would imply Welsh ~45,000",
     ["English/Welsh total could be about 15,000 larger", "a ® gure of 50,000, including convicts",
      "one in the order of 45,000"]),
    ("All Europeans", 307400, 307000, 350000,
     "Tomlins: appropriate range for European migration 1700-1780 is 307,000-350,000 "
     "(Fogleman lower bound; Potter/Gemery/Galenson global estimates 340,000-370,000)",
     ["range for European migration, 1700± 1780, is in the order of 307,000± 350,000",
      "global estimates in the range of 340,000± 370,000"]),
]
for origin, c, lo, hi, nt, ev in alt_ranges:
    add(1700, 1775, origin, c, lo, hi, "Thirteen colonies", "mixed", "tomlins2001_laborhistory",
        "series=alt; " + nt, TOM, ev)

# ---------------------------------------------------------------------------------------
# 2. 17th century (PRIMARY): Tomlins (2001) regional synthesis.
#    Chesapeake decadal series = Tomlins Table 1 (from Menard 1988 / McCusker & Menard).
# ---------------------------------------------------------------------------------------
i1 = next(i for i, l in enumerate(tom_lines) if l.startswith("Table 1. European migration, servant"))
for l in tom_lines[i1:i1 + 25]:
    m = re.match(r"^(1\d{3})(\*?)\s+(.*)$", l)
    if not m:
        continue
    end, approx, rest = int(m.group(1)), m.group(2), m.group(3).split()
    start = 1607 if end == 1610 else end - 9
    nums = [float(x) for x in rest]
    tag = "approximation (*) in source; " if approx else ""
    if len(nums) == 6:   # MD all, MD serv, VA all, VA serv, Chesapeake serv, white pop
        md_all, md_s, va_all, va_s, ches_s, pop = nums
        assert abs(md_s + va_s - ches_s) < 0.011, (end, nums)
    elif len(nums) == 4:  # VA only (1610-1630)
        md_all = None
        va_all, va_s, ches_s, pop = nums
    elif len(nums) == 2:  # Chesapeake servants only (1690, 1700)
        md_all = va_all = None
        ches_s, pop = nums
    else:
        raise SystemExit(f"unexpected Table 1 row: {l}")
    base = ("Tomlins (2001) Table 1 'European migration ... Maryland and Virginia' (thousands), "
            "built on Menard (1988) 'British Migration to the Chesapeake Colonies'; Tomlins assumes 80% servants")
    if md_all is not None:
        add(start, end, "British (Chesapeake immigrants)", int(round(md_all * 1000)), dest="Maryland",
            src="tomlins2001_table1_menard", note=f"series=primary; {tag}{base}; servants {md_s}k")
    if va_all is not None:
        add(start, end, "British (Chesapeake immigrants)", int(round(va_all * 1000)), dest="Virginia",
            src="tomlins2001_table1_menard", note=f"series=primary; {tag}{base}; servants {va_s}k")
    if md_all is None and va_all is None:
        # only servant migrants given; all-migrant count derived at Tomlins' stated 80% servant share
        derived = int(round(ches_s * 1000 / 0.8, -2))
        add(start, end, "British (Chesapeake immigrants)", derived, 13000, 14000,
            dest="Chesapeake (Maryland and Virginia)", src="tomlins2001_table1_menard",
            note=(f"series=primary; DERIVED: source gives only servant migrants ({ches_s}k); count = "
                  f"servants / 0.8 (Tomlins' stated 80% assumption); low/high = Horn's 13,000-14,000 "
                  f"per decade for the 1680s-1690s (virtualjamestown_horn)"
                  + ("; decade ending 1700 overlaps Fogleman's 1700 start by one year" if end == 1700 else "")))
check("virtualjamestown_horn/horn_essay.txt", "falling back to 13,000-14,000 in the 1680s and 1690s")
check(TOM, "Lower South of 8000 of which 40% (3200) were servants")

# New England, Delaware Valley, Lower South, New Netherland (Tomlins Appendix I)
add(1630, 1642, "English (Great Migration)", 21000, dest="New England", status="mixed",
    src="tomlins2001_laborhistory",
    note="series=primary; Tomlins uses 'the common 21,000 estimate for the 1630-42 period'; 16.5% servants",
    raw=TOM, evidence="For New England I use the common 21,000 estimate for the 1630± 42 period")
add(1643, 1699, "English", 3000, dest="New England", status="mixed", src="tomlins2001_laborhistory",
    note=("series=primary; DERIVED as Tomlins' New England total 24,000 minus 21,000 for 1630-42 "
          "('a nominal 500 per decade for the remainder of the century')"),
    raw=TOM, evidence=["to New England of 24,000 of which 16.5% (4000) were servants",
                       "plus a nominal 500 per decade"])
add(1670, 1699, "European (mostly British)", 8000, dest="Lower South (Carolina)", status="mixed",
    src="tomlins2001_laborhistory",
    note="series=primary; Tomlins: 'no more than a guess ... clearly an upper bound'; 40% servants",
    raw=TOM, evidence=["Lower South of 8000 of which 40% (3200) were servants", "The ® gure is clearly an upper bound"])
add(1624, 1664, "New Netherland colonists (Dutch and other Europeans)", 6000, dest="New Netherland",
    status="mixed", src="tomlins2001_laborhistory",
    note="series=primary; Tomlins citing van den Boogaart, 'The Servant Migration to New Netherland, 1624-1664'; 55% servants",
    raw=TOM, evidence=["and to New Netherlands of 6000 of which 3300 (55%) were servants"])
add(1607, 1699, "Other Europeans (mostly Swedish and German)", 1500, dest="", status="mixed",
    src="tomlins2001_laborhistory",
    note=("series=primary; Fogleman's 17th-c. figure as reported by Tomlins; Tomlins notes it is unclear "
          "whether his regional sources include them, and adding them reconciles his 161,000 with Fogleman's 165,000"),
    raw=TOM, evidence="some 1500 miscellaneous (mostly Swedish and German) migrants")
add(1607, 1699, "Convicts and prisoners (mostly Scottish)", 2300, dest="", status="convict",
    src="tomlins2001_laborhistory",
    note="series=primary; Fogleman's 17th-c. involuntary European migrants as reported by Tomlins (see previous row)",
    raw=TOM, evidence="2300 involuntary European (mostly Scottish) migrants")

# Delaware Valley, Tomlins Table 6 (round numbers). 1670s-1690s British = PRIMARY (17th c.);
# 1700s-1770s = SUBSET of the Fogleman series.
i6 = next(i for i, l in enumerate(tom_lines) if "Table 6. Immigration to the Delaware Valley" in l)
t6 = []
for l in tom_lines[i6:i6 + 20]:
    m = re.match(r"^\s*(1\d{2}0)/9\s+(.*)$", l)
    if m:
        t6.append((int(m.group(1)), l))
assert len(t6) == 11, len(t6)
for start, l in t6:
    # fixed-width columns located from the header line
    cols = {"British": (15, 27), "German": (27, 42), "Southern Irish": (42, 58),
            "Northern Irish": (58, 75), "Total": (75, 90), "Philadelphia": (90, 200)}
    vals = {}
    for k, (a, b) in cols.items():
        s = l[a:b].strip()
        vals[k] = int(s) if s else None
    tot = sum(v for k, v in vals.items() if k not in ("Total", "Philadelphia") and v)
    t6_disc = ""
    if tot != vals["Total"]:
        t6_disc = f"; NB source row total {vals['Total']} != sum of columns {tot}"
        print(f"NOTE: Tomlins Table 6 {start}s: printed total {vals['Total']} vs column sum {tot}")
    end = start + 9
    for k, lab in [("British", "British"), ("German", "Germans"), ("Southern Irish", "Southern Irish"),
                   ("Northern Irish", "Northern Irish (Ulster)")]:
        v = vals[k]
        if not v:
            continue
        tagp = "series=primary" if start < 1700 else "series=subset"
        src_note = ("British column: Fischer (Albion's Seed) through 1720, Bailyn 1760-76; German & Irish "
                    "columns: Fogleman (1992) pp. 702, 705")
        add(start, end if end < 1776 else 1775, lab, v, dest="Delaware Valley (Philadelphia/New Castle)",
            status="mixed", src="tomlins2001_table6",
            note=f"{tagp}; Tomlins (2001) Table 6 'Immigration to the Delaware Valley' (round numbers); {src_note}"
                 + ("" if start < 1700 else "; contained in the thirteen-colonies Fogleman rows") + t6_disc)
    if vals["Philadelphia"]:
        add(start, end if end < 1776 else 1775, "All European arrivals", vals["Philadelphia"],
            dest="Philadelphia", status="mixed", src="tomlins2001_table6",
            note="series=subset; Tomlins Table 6 'Arrivals in Philadelphia' column, from Klepp (1989)")

# ---------------------------------------------------------------------------------------
# 3. ALT 17th-century estimates
# ---------------------------------------------------------------------------------------
HORN = "virtualjamestown_horn/horn_essay.txt"
for dest, c in [("Chesapeake (Virginia and Maryland)", 130000), ("Middle Colonies", 24000),
                ("New England", 21000)]:
    add(1607, 1699, "English", c, dest=dest, status="mixed", src="horn_virtualjamestown",
        note="series=alt; James Horn, 'Leaving England' essay (Virtual Jamestown): 17th-century English emigration",
        raw=HORN, evidence="approximately 210,000 went to the Caribbean, 130,000 to the Chesapeake (Virginia and Maryland), 24,000 to the Middle Colonies, and 21,000 to New England")
for (ps, pe, lo, hi) in [(1630, 1649, 8000, 9000), (1650, 1679, 16000, 20000), (1680, 1699, 13000, 14000)]:
    nd = (pe - ps + 1) // 10
    add(ps, pe, "White immigrants (mostly English)", (lo + hi) // 2 * nd, lo * nd, hi * nd,
        "Chesapeake (Virginia and Maryland)", "mixed", "horn_virtualjamestown",
        f"series=alt; Horn gives {lo:,}-{hi:,} per decade; count = midpoint x {nd} decades (DERIVED)",
        HORN, ["In the 1630s and 1640s, white immigration averaged about 8,000-9,000 per decade",
               "surged to 16,000-20,000 per decade from 1650 to 1680"])
add(1630, 1700, "British", 155000, dest="Mainland colonies", status="mixed", src="gemery_via_tomlins2001",
    note="series=alt; Henry Gemery's estimate of British emigration 1630-1700 (39,000 to northern colonies, 116,000 to the South), as reported by Tomlins (2001)",
    raw=TOM, evidence="Gemery suggests a total British migration during 1630± 1700 of 155,000, of which 116,000 is to the Chesapeake and Lower South")
add(1630, 1700, "British", 39000, dest="Northern colonies (New England & Middle)", status="mixed",
    src="gemery_via_tomlins2001", note="series=alt; Gemery via Tomlins (subset of the 155,000 row)",
    raw=TOM, evidence="of whom 39,000 went to Northern colonies and 116,000 to the South")
add(1630, 1700, "British", 116000, dest="Southern colonies (Chesapeake & Lower South)", status="mixed",
    src="gemery_via_tomlins2001", note="series=alt; Gemery via Tomlins (subset of the 155,000 row)",
    raw=TOM, evidence="of whom 39,000 went to Northern colonies and 116,000 to the South")
add(1607, 1700, "British", 123000, 99000, 146000, "Chesapeake", "mixed", "menard_via_tomlins2001",
    "series=alt; Menard's 'best guess' c.123,000 for the 17th-century Chesapeake (range 99,000-146,000); Horn ~120,000",
    TOM, ["Menard’ s own ª best guessº of c. 123,000 for the entire 17th century", "[99,000± 146,000]"])
add(1607, 1699, "European (all)", 161000, 161000, 165200, "Mainland colonies", "mixed",
    "tomlins2001_laborhistory",
    "series=alt; Tomlins' 17th-c. regional total (102,000 servants, <64%); Fogleman's equivalent is 165,000 (60% servants)",
    TOM, ["Servants thus comprise somewhat less than 64% of all 17th century migrants (102,000 of 161,000)",
          "total European migration of 165,000 (compared with my 161,000)"])
add(1607, 1780, "European (all)", "", 470000, 515000, "Mainland colonies", "mixed", "tomlins2001_laborhistory",
    "series=alt; Tomlins: total European migration to the mainland through 1780 of 470,000-515,000, of which ~54,500 involuntary (convicts/prisoners)",
    TOM, "current estimates suggest a total European migration of between 470,000 and 515,000")
add(1655, 1665, "Swedes and Finns (New Sweden)", 600, dest="New Sweden (Delaware Valley)", status="unknown",
    src="wikipedia_new_sweden",
    note="series=subset; 'roughly 600 Swedes and Finns' settled the area after 1638 (period approximate: 1638-1655 colony); part of Fogleman's 1,500 misc.",
    raw="wikipedia/New_Sweden.wiki", evidence="the area was settled by roughly 600 Swedes and [[Finns]]")
rows[-1]["period_start"], rows[-1]["period_end"] = 1638, 1655
add(1654, 1654, "Jews (Sephardic, from Brazil via the Netherlands)", 23, dest="New Amsterdam (New Netherland)",
    status="free", src="wikipedia_jews_colonial",
    note="series=subset; first group of Jewish refugees to New Amsterdam (single event); part of the New Netherland row",
    raw="wikipedia/History_of_the_Jews_in_Colonial_America.wiki",
    evidence="in connection with the group of 23 Jews who arrived as refugees from [[Brazil]]")
add(1700, 1700, "French Huguenots", 390, dest="Virginia (Manakintown)", status="free", src="wikipedia_huguenots",
    note="series=subset; original settlers of the 1700 Huguenot settlement at Manakin Town (contained in Fogleman 'Other')",
    raw="wikipedia/Huguenots.wiki", evidence="Of the original 390 settlers in the isolated settlement")

# ---------------------------------------------------------------------------------------
# 4. Fogleman (1998) Table 1 status aggregates (UMBC handout reproduction) - ALT/reference
# ---------------------------------------------------------------------------------------
UMBC = "umbc_historylab/handout.txt"
check(UMBC, "1607-1699 33,200 2,300 96,600 66,300")
check(UMBC, "1700-1775 278,400 52,200 103,600 151,600")
for ps, pe, vals in [(1607, 1699, (33200, 2300, 96600, 66300)), (1700, 1775, (278400, 52200, 103600, 151600))]:
    for (lab, st), v in zip([("Africans (slaves)", "enslaved"), ("Convicts and prisoners", "convict"),
                             ("Indentured servants (all European origins)", "indentured"),
                             ("Free immigrants (all European origins)", "free")], vals):
        add(ps, pe, lab, v, dest="Thirteen colonies", status=st, src="fogleman1998_jah_table1_via_umbc",
            note=("series=alt; Fogleman (1998) JAH Table 1 'Estimated Immigration into the Thirteen Colonies "
                  "and the United States ... 1607-1819', as reproduced on a UMBC teaching handout"
                  + ("; Africans: primary series is slave_trade_arrivals.csv" if st == "enslaved" else "")))
check("germanna_note0406/note0406.html", "African 278,400")
NOW = "nowrasteh_1776/page.txt"
add(1776, 1809, "All immigrants incl. slaves", 387800, dest="United States", status="mixed",
    src="fogleman1998_via_nowrasteh2026",
    note=("series=alt; DERIVED: Fogleman's 973,600 total (slave and free) for 1700-1809 as quoted by "
          "Nowrasteh (2026) minus Fogleman's 585,800 for 1700-1775 (UMBC handout); includes enslaved Africans"),
    raw=NOW, evidence="a total of 973,600 people —slave and free—entered the colonies or states in over a century from 1700 to 1809")

# Convicts by origin (Vaver / earlyamericancrime.com, citing Ekirch)
EAC = "earlyamericancrime_convicts/overview.txt"
add(1718, 1775, "Irish convicts and vagabonds", 16000, 16000, "", "Thirteen colonies", "convict",
    "earlyamericancrime_vaver", "series=subset; 'more than 16,000 people were transported from Ireland between 1718 and 1775' (contained in Fogleman Irish rows)",
    EAC, "more than 16,000 people were transported from Ireland between 1718 and 1775")
add(1718, 1775, "English convicts", 34000, dest="Thirteen colonies", status="convict", src="earlyamericancrime_vaver",
    note="series=subset; 'native Englishmen, who totaled about 34,000' (contained in Fogleman English rows)",
    raw=EAC, evidence="The majority of convicts sentenced to transportation were native Englishmen, who totaled about 34,000")
add(1718, 1775, "British convicts (mostly English/Welsh)", 36000, dest="Thirteen colonies", status="convict",
    src="ekirch_via_tomlins2001", note="series=alt; Ekirch (Bound for America) via Tomlins: 'perhaps 36,000 convicts' 1718-1775",
    raw=TOM, evidence="between 1718 and 1775 perhaps 36,000 convicts")

# ---------------------------------------------------------------------------------------
# 5. Whole-colonial-period origin totals (Meyerink & Szucs 1997, via Wikipedia) - ALT
# ---------------------------------------------------------------------------------------
WD = "wikipedia/Demographic_history_of_the_United_States.wiki"
for lab, v, ev in [("England", 230000, "[[England]]* || 230,000"),
                   ("Ulster Scots-Irish", 135000, "[[Ulster Scots people|Scots Irish]]* || 135,000"),
                   ("Germany", 103000, "|| 103,000 || 270,000"),
                   ("Scotland", 48500, "[[Scotland]]* || 48,500"),
                   ("Ireland", 8000, "[[Ireland]]* || 8,000"),
                   ("Netherlands", 6000, "[[Netherlands]] || 6,000"),
                   ("Wales", 4000, "[[Wales]]* || 4,000"),
                   ("France", 3000, "[[France]] || 3,000"),
                   ("Jews", 1000, "|| 1,000 || 2,000"),
                   ("Sweden", 500, "[[Sweden]] || 500"),
                   ("Other", 50000, "||50,000 ||200,000"),
                   ("Africa", 360000, "|| 360,000 ||757,000")]:
    add(1607, 1789, lab, v, dest="Territory of the US (1790)", status="enslaved" if lab == "Africa" else "unknown",
        src="meyerink_szucs1997_via_wikipedia",
        note=("series=alt; 'Immigrants before 1790' table on Wikipedia 'Demographic history of the United States', "
              "citing Meyerink & Szucs, The Source (1997); unverified against the book; useful for small groups "
              "(Dutch, French, Jews, Swedes)"),
        raw=WD, evidence=ev)

# ---------------------------------------------------------------------------------------
# 6. Aggregate average-annual estimates (Cohn; EH.net & Engerman-Margo/NBER) - ALT, and
#    1780/83-1819 totals (PRIMARY for the early national period)
# ---------------------------------------------------------------------------------------
EH = "ehnet_cohn_immigration/page.txt"
NB = "nber_c11745/c.txt"
check(EH, "Sources : Years before 1820: Grabbe (1989).")
for ps, pe, avg, ny, tag in [(1630, 1700, 2200, 70, "alt"), (1700, 1779, 4325, 80, "alt"),
                             (1780, 1819, 9900, 40, "primary")]:
    check(EH, f"{avg:,}")
    check(NB, f"{avg:,}")
    note = (f"series={tag}; DERIVED: Cohn's average yearly total {avg:,} (all countries, excl. slaves) x {ny} years; "
            "EH.net 'Immigration to the United States' Table 1 (sources: years before 1820 Grabbe 1989) and "
            "Engerman & Margo (NBER 2010) Table 9.5 citing Cohn (2009); source period label "
            f"'{ps}-{pe if pe != 1779 else 1780}'")
    if tag == "primary":
        note += "; low = Treasury/Bromwell 250,000 (1783-1819); no origin breakdown available for this period"
        add(ps, pe, "All European origins", avg * ny, 250000, "", "United States", "mixed", "cohn_ehnet_grabbe", note)
    else:
        add(ps, pe, "All European origins", avg * ny, "", "", "Mainland colonies", "mixed", "cohn_ehnet_grabbe", note)
add(1783, 1819, "All origins (foreign arrivals)", 250000, dest="United States", status="unknown",
    src="hsus1949_chB_note",
    note=("series=alt; HSUS 1789-1945 (1949) note to series B 304-352: immigrants 'from the close of the "
          "Revolutionary War up to 1820 has been estimated at 250,000' (Treasury Bureau of Statistics 1903; "
          "Bromwell 1856 per immigrantentrepreneurship.org)"),
    raw="hsus_1949_chB/chB.txt", evidence=["from tbe close of the Revolutionary War up to 1820 has been", "estimated at 250,000 (Bureau of Statistics, Treasury Department"])
check("immigrantentrepreneurship_vol2/page.txt", "William J. Bromwell’s 1856 estimate of 250,000 foreign-born arrivals")

# German-speaking arrivals in the early national period (Boyd, citing Grabbe 2001 and Grubb 2011)
BOY = "immigrantentrepreneurship_merchants/page.txt"
add(1800, 1808, "German-speaking", 8031, 8000, "", "Pennsylvania", "mixed", "boyd_immigrantentrepreneurship",
    "series=subset; Grubb (2011) enumerated 8,031 for Pennsylvania alone; Grabbe (2001) 'slightly more than 8,000' German-speaking arrivals 1800-1808 (called conservative)",
    BOY, ["Farley Grubb has enumerated 8,031 for Pennsylvania alone",
          "Estimates of slightly more than 8,000 German-speaking arrivals between for the period 1800-1808"])
add(1815, 1819, "Germans", 15000, 13500, "", "United States", "mixed", "boyd_immigrantentrepreneurship",
    "series=subset; 'German migration between 1815 and 1820, during which approximately 15,000 immigrated'; low = Grabbe's 13,500 German and Swiss passengers 1815-1820 (>=8,522 via Philadelphia); up to 48% redemptioners in 1817",
    BOY, ["The German migration between 1815 and 1820, during which approximately 15,000 immigrated to the U.S.",
          "Philadelphia absorbed at least 8,522 of an estimated 13,500 German and Swiss passengers"])

# ---------------------------------------------------------------------------------------
# 7. French / Spanish borderlands (not covered by the thirteen-colonies series) - PRIMARY
# ---------------------------------------------------------------------------------------
add(1778, 1783, "Canary Islanders (Isleños)", 2100, dest="Spanish Louisiana", status="free",
    src="wikipedia_islenos",
    note="series=primary; 'Between 1778 and 1783 another 2,100 Canarians arrived in Spanish Louisiana' (other Isleño groups given only as families: 16 families San Antonio 1731; 154 families Spanish Florida 1757-59)",
    raw="wikipedia/Isle__os.wiki", evidence="Between 1778 and 1783 another 2,100 Canarians arrived in [[Louisiana (New Spain)|Spanish Louisiana]]")
add(1764, 1790, "Acadians (French)", 4000, 3000, 4000, "Louisiana", "free", "wikipedia_louisiana_acadians",
    "series=primary; 'About 4,000 are thought to have settled in Louisiana' (citation needed on Wikipedia) vs. "
    "'3,000 Acadians who settled in Louisiana after the Expulsion' (Acadians article); arrivals after 1764; end year not stated (1790 is a placeholder)",
    "wikipedia/Louisiana__New_France_.wiki", "About 4,000 are thought to have settled in Louisiana")
check("wikipedia/Acadians.wiki", "it honors the 3,000 Acadians who settled in Louisiana after the Expulsion")
add(1785, 1785, "Acadians (from France)", 1633, dest="New Orleans (Spanish Louisiana)", status="free",
    src="wikipedia_louisiana_acadians", note="series=subset; 'In 1785, 1633 people of Acadian origin were brought from France to New Orleans'",
    raw="wikipedia/Louisiana__New_France_.wiki", evidence="In 1785, 1633 people of Acadian origin were brought from France to New Orleans")
add(1717, 1717, "French colonists (incl. 300 soldiers)", 550, dest="French Louisiana (Mississippi colony)",
    status="unknown", src="wikipedia_louisiana_acadians",
    note="series=alt; population STOCK in 1717 ('the colony of Mississippi counted 300 soldiers out of 550 people'), not a flow; recorded only as an order-of-magnitude marker for early French Louisiana",
    raw="wikipedia/Louisiana__New_France_.wiki", evidence="in 1717, the colony of Mississippi counted 300 soldiers out of 550 people")


def main():
    rows.sort(key=lambda r: (int(r["period_start"]), int(r["period_end"]), r["note"][:14], r["origin_label"], r["destination"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    prim = [r for r in rows if r["note"].startswith("series=primary")]
    tot = sum(int(r["count"]) for r in prim if r["count"] != "")
    p17 = sum(int(r["count"]) for r in prim if int(r["period_end"]) <= 1700)
    p18 = sum(int(r["count"]) for r in prim if r["source_id"] == "fogleman1992_jih_via_tomlins2001")
    print(f"rows={len(rows)} primary={len(prim)} primary_total={tot} 17th-c primary={p17} fogleman 1700-75={p18}")


if __name__ == "__main__":
    main()
