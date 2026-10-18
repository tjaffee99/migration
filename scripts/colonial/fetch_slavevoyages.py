"""Fetch SlaveVoyages aggregates needed for the colonial slice.

Saves raw API responses (JSON) under data/raw/slavevoyages/api/.
- Trans-Atlantic *Estimates* (the "assessment" endpoint): annual x embarkation
  region, one request per specific disembarkation region in Mainland North America.
- Intra-American voyages database (dataset=1): annual x region of purchase,
  one request per principal region of disembarkation in Mainland North America.
- Trans-Atlantic voyages database (dataset=0): totals by principal disembarkation
  region (cross-check only).

The public site's front-end token is read from the downloaded runtime-config.js.
Run: python3 -I scripts/colonial/fetch_slavevoyages.py
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path("/home/user/migration")
RAW = ROOT / "data/raw/slavevoyages"
OUT = RAW / "api"
OUT.mkdir(parents=True, exist_ok=True)

cfg = (RAW / "runtime-config.js").read_text()
m = re.search(r'apiAuthToken:\s*"(Token [0-9a-f]+)"', cfg)
if not m:
    sys.exit("token not found in runtime-config.js")
HEAD = {"Authorization": m.group(1), "Content-Type": "application/json"}
BASE = "https://www.slavevoyages.org/api"

EST_REGIONS = ["Carolinas / Georgia", "Chesapeake", "Gulf states", "Northern U.S.",
               "U.S.A. unspecified"]
IA_REGIONS = ["Connecticut", "Florida", "Georgia", "Gulf coast", "Maine", "Maryland",
              "Massachusetts", "New Hampshire", "New Jersey", "New York", "North Carolina",
              "Other North America", "Pennsylvania", "Rhode Island", "South Carolina",
              "Texas", "Virginia", "Canada"]


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def post(path, payload, fname):
    dest = OUT / fname
    if dest.exists():
        return json.loads(dest.read_text())
    r = requests.post(BASE + path, headers=HEAD, data=json.dumps(payload), timeout=120)
    r.raise_for_status()
    obj = {"request_path": path, "request_payload": payload, "response": r.json(),
           "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    dest.write_text(json.dumps(obj, indent=1))
    time.sleep(1)
    return obj


# A. Estimates: year x embarkation region, per specific disembarkation region
for reg in EST_REGIONS:
    payload = {"cols": ["embarkation_region__name"], "rows": ["year"], "binsize": 1,
               "agg_fn": "sum", "vals": ["disembarked_slaves"], "mode": "csv",
               "filter": [{"varName": "disembarkation_region__name", "searchTerm": [reg],
                           "op": "in"}]}
    post("/assessment/crosstabs/", payload, f"est_year_x_embark__{slug(reg)}.json")

# A2. Estimates cross-check: year x specific disembarkation region (mainland NA)
payload = {"cols": ["disembarkation_region__import_area__name", "disembarkation_region__name"],
           "rows": ["year"], "binsize": 1, "agg_fn": "sum", "vals": ["disembarked_slaves"],
           "mode": "csv",
           "filter": [{"varName": "disembarkation_region__import_area__name",
                       "searchTerm": ["Mainland North America"], "op": "in"}]}
post("/assessment/crosstabs/", payload, "est_year_x_disembark_mainlandNA.json")

# A3. Estimates: all broad areas, by decade (context / sanity check)
payload = {"cols": ["disembarkation_region__import_area__name"], "rows": ["year"],
           "binsize": 10, "agg_fn": "sum", "vals": ["embarked_slaves", "disembarked_slaves"],
           "mode": "csv", "filter": []}
post("/assessment/crosstabs/", payload, "est_decade_x_broad_area_all.json")

# B. Intra-American voyages (dataset 1): year x (broad, principal) purchase region
YEAR = "voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year"
DIS = "voyage_slaves_numbers__imp_total_num_slaves_disembarked"
for reg in IA_REGIONS:
    payload = {"columns": ["voyage_itinerary__imp_broad_region_of_slave_purchase__name",
                           "voyage_itinerary__imp_principal_region_of_slave_purchase__name"],
               "rows": YEAR, "rows_label": "Year range", "agg_fn": "sum", "binsize": 1,
               "value_field": DIS, "offset": 0, "limit": 1000,
               "filter": [{"varName": "dataset", "searchTerm": [1], "op": "in"},
                          {"varName": "voyage_itinerary__imp_principal_region_slave_dis__name",
                           "searchTerm": [reg], "op": "in"}]}
    post("/voyage/crosstabs/", payload, f"ia_year_x_purchase__{slug(reg)}.json")

# C. Trans-Atlantic voyages (dataset 0): cross-check totals by principal disembark region
for ds, nm in [(0, "ta"), (1, "ia")]:
    payload = {"columns": ["voyage_itinerary__imp_principal_region_slave_dis__name"],
               "rows": YEAR, "rows_label": "Year range", "agg_fn": "sum", "binsize": 10,
               "value_field": DIS, "offset": 0, "limit": 1000,
               "filter": [{"varName": "dataset", "searchTerm": [ds], "op": "in"},
                          {"varName": "voyage_itinerary__imp_broad_region_slave_dis__name",
                           "searchTerm": ["Mainland North America"], "op": "in"}]}
    post("/voyage/crosstabs/", payload, f"{nm}_voyages_decade_x_disembark_mainlandNA.json")

print("done", sorted(p.name for p in OUT.iterdir()))
