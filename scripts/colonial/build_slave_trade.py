"""Build data/processed/slave_trade_arrivals.csv from saved SlaveVoyages API responses.

basis = tast_estimates : Trans-Atlantic Slave Trade *Estimates* (SlaveVoyages "assessment"
                          endpoint), disembarked captives, by year x African embarkation region x
                          specific disembarkation region within "Mainland North America".
basis = intra_american : Intra-American Slave Trade database (voyage-level, dataset=1),
                          imputed captives disembarked, by year of arrival x (broad region:
                          principal region) of purchase x principal region of disembarkation.
                          Documented voyages only (not an estimate of the full trade).
                          Rows whose purchase region is itself in Mainland North America are the
                          coastwise/domestic trade (internal, not immigration).
Run: python3 -I scripts/colonial/build_slave_trade.py
"""
import csv
import io
import json
from pathlib import Path

ROOT = Path("/home/user/migration")
API = ROOT / "data/raw/slavevoyages/api"
OUT = ROOT / "data/processed/slave_trade_arrivals.csv"

EST = {"Carolinas_Georgia": "Carolinas / Georgia", "Chesapeake": "Chesapeake",
       "Gulf_states": "Gulf states", "Northern_U_S": "Northern U.S.",
       "U_S_A_unspecified": "U.S.A. unspecified"}
IA = ["Connecticut", "Florida", "Georgia", "Gulf_coast", "Maine", "Maryland", "Massachusetts",
      "New_Hampshire", "New_Jersey", "New_York", "North_Carolina", "Other_North_America",
      "Pennsylvania", "Rhode_Island", "South_Carolina", "Texas", "Virginia"]  # Canada excluded


def load(name):
    return json.loads((API / name).read_text())["response"]


def est_rows():
    rows = []
    grand = 0
    for slug, region in EST.items():
        data = load(f"est_year_x_embark__{slug}.json")["data"]
        tab = list(csv.reader(io.StringIO(data)))
        header = tab[0]
        assert header[-1] == "Totals"
        tot_check = 0
        for r in tab[1:]:
            if r[0] == "Totals":
                assert int(float(r[-1])) == tot_check, (region, r[-1], tot_check)
                continue
            year = int(r[0])
            rowsum = 0
            for emb, v in zip(header[1:-1], r[1:-1]):
                if v == "":
                    continue
                c = int(round(float(v)))
                rowsum += c
                if c == 0:
                    continue
                rows.append({"year": year, "embark_region": emb, "disembark_region": region,
                             "count": c, "basis": "tast_estimates",
                             "source_id": "slavevoyages_tast_estimates"})
            assert rowsum == int(float(r[-1])), (region, year)
            tot_check += rowsum
        grand += tot_check
        print(f"estimates {region}: {tot_check}")
    # cross-check against the independent year x region query
    data = load("est_year_x_disembark_mainlandNA.json")["data"]
    tab = list(csv.reader(io.StringIO(data)))
    assert int(float(tab[-1][-1])) == grand, (tab[-1][-1], grand)
    print("estimates mainland North America total:", grand)
    return rows, grand


def ia_rows():
    rows = []
    grand = 0
    foreign = 0
    for slug in IA:
        resp = load(f"ia_year_x_purchase__{slug}.json")
        region = slug.replace("_", " ")
        data = resp["data"]
        years = [d for d in data if d["Year range"] != "All"]
        assert resp["metadata"]["total_results_count"] <= len(data), slug
        allrow = [d for d in data if d["Year range"] == "All"]
        sub = 0
        for d in years:
            if d["Year range"] in ("nan", ""):
                print(f"NOTE: {region}: {d['All']} captives on voyages with unknown arrival year skipped")
                sub += d["All"]
                continue
            year = int(d["Year range"])
            rs = 0
            for k, v in d.items():
                if k in ("Year range", "All") or not v:
                    continue
                broad, _, princ = k.partition("__")
                rs += v
                emb = f"{broad}: {princ}" if princ else broad
                rows.append({"year": year, "embark_region": emb, "disembark_region": region,
                             "count": v, "basis": "intra_american",
                             "source_id": "slavevoyages_iastd"})
                if broad != "Mainland North America":
                    foreign += v
            assert rs == d["All"], (slug, year, rs, d["All"])
            sub += rs
        if allrow:
            assert allrow[0]["All"] == sub, (slug, allrow[0]["All"], sub)
        grand += sub
    print("intra-American to US mainland regions (excl. Canada):", grand,
          "of which from outside mainland North America:", foreign)
    return rows, grand, foreign


def main():
    e, etot = est_rows()
    i, itot, ifor = ia_rows()
    rows = sorted(e + i, key=lambda r: (r["basis"] != "tast_estimates", r["year"],
                                        r["disembark_region"], r["embark_region"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "embark_region", "disembark_region", "count",
                                          "basis", "source_id"])
        w.writeheader()
        w.writerows(rows)
    print("rows:", len(rows), "(estimates", len(e), ", intra-American", len(i), ")")
    # decade summary for the notes
    dec = {}
    for r in e:
        dec.setdefault(r["year"] // 10 * 10, 0)
        dec[r["year"] // 10 * 10] += r["count"]
    print("estimates by decade:", dict(sorted(dec.items())))
    s1700 = sum(r["count"] for r in e if 1700 <= r["year"] <= 1775)
    s1619 = sum(r["count"] for r in e if r["year"] <= 1699)
    s1776 = sum(r["count"] for r in e if 1776 <= r["year"] <= 1807)
    s1808 = sum(r["count"] for r in e if r["year"] >= 1808)
    print("estimates <=1699:", s1619, " 1700-1775:", s1700, " 1776-1807:", s1776, " 1808+:", s1808)
    ia_pre1808 = sum(r["count"] for r in i if r["year"] <= 1807
                     and not r["embark_region"].startswith("Mainland North America"))
    print("intra-American from outside mainland NA, arrivals <=1807:", ia_pre1808)


if __name__ == "__main__":
    main()
