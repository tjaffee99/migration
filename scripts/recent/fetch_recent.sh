#!/usr/bin/env bash
# Fetch the raw inputs for the 2024-2026 extension ("recent" slice). Raw folders are git-ignored;
# every URL is listed here and in data/processed/sources_recent.csv.
#
# DHS/OHSS (ohss.dhs.gov) and CBO (www.cbo.gov) return 403 to this environment, so those files come
# from Archive-It (Internet Archive) captures, never via a reader/fetch proxy. Archive-It throttles
# ("Rate limit reached" page with HTTP 200): ait_get backs off and retries.
#
# Usage:  bash scripts/recent/fetch_recent.sh          (then: bash scripts/recent/run_all.sh)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
R="$ROOT/data/raw"

get () {  # URL OUTFILE  (plain HTTPS download, skip if present)
  local u="$1" out="$2"
  mkdir -p "$(dirname "$out")"
  if [ -s "$out" ]; then echo "have $(basename "$out")"; return 0; fi
  curl -sS -f -L --retry 3 -m 600 -o "$out" "$u" && echo "got  $(basename "$out")" || { echo "FAILED $u" >&2; rm -f "$out"; }
}
ait_get () {  # ARCHIVE-IT-MEMENTO-URL OUTFILE
  local u="$1" out="$2" t
  mkdir -p "$(dirname "$out")"
  if [ -s "$out" ] && ! grep -q -s "Rate limit reached" "$out"; then echo "have $(basename "$out")"; return 0; fi
  for t in 1 2 3 4 5 6 7 8; do
    curl -sS -L -m 600 -o "$out" "$u" || true
    if grep -q -s "Rate limit reached" "$out"; then sleep $((30 * t)); continue; fi
    break
  done
  echo "$u" > "$out.memento"
  echo "got  $(basename "$out") ($(stat -c %s "$out") bytes, $(file -b "$out" | cut -c1-30))"
  sleep 10
}
AIT=https://wayback.archive-it.org/all

# 1. OHSS Legal Immigration and Adjustment of Status (LIAS) quarterly workbooks (Archive-It, Nov 2025).
#    The LIAS page's latest capture (2025-11-15) lists FY2024 Q1-Q4 and FY2025 Q1 only; the FY2024
#    Yearbook LPR tables (posted 2026-06-08) and later LIAS quarters have no Archive-It capture.
D="$R/archiveit_ohss_recent"
ait_get "$AIT/20251115113218/https://ohss.dhs.gov/sites/default/files/2025-06/2025_0624_ohss_legal-immigration-adjustment-of-status-fy-2024q4_0.xlsx" "$D/lias_fy2024q4.xlsx"
ait_get "$AIT/20251115113217/https://ohss.dhs.gov/system/files/2025-07/2025_0725_ohss_legal-immigration-adjustment-of-status-fy-2025q1.xlsx" "$D/lias_fy2025q1.xlsx"
ait_get "$AIT/20251115113223/https://ohss.dhs.gov/sites/default/files/2024-06/2024_0507_ohss_legal-immigration-adjustment-of-status-fy-2023q4.xlsx" "$D/lias_fy2023q4.xlsx"

# 2. CPS basic monthly microdata -> aggregates only (the script downloads each month to a temp dir,
#    aggregates, deletes it). Layouts and the country-code list (Attachment 14 of the Jan 2026
#    supplement technical documentation) are kept.
D="$R/census_cps_basic/layouts"; C=https://www2.census.gov/programs-surveys/cps
for y in 2024 2025 2026; do
  get "$C/datasets/$y/basic/${y}_Basic_CPS_Public_Use_Record_Layout_plus_IO_Code_list.txt" "$D/${y}_Basic_CPS_Public_Use_Record_Layout_plus_IO_Code_list.txt"
done
get "$C/datasets/2026/basic/cps_dd_record_layout.csv" "$D/cps_dd_record_layout.csv"
get "$C/datasets/2026/basic/cps_dd_record_layout.txt" "$D/cps_dd_record_layout.txt"
get "$C/techdocs/cpsjan26.pdf" "$D/cpsjan26.pdf"
python3 -I "$ROOT/scripts/recent/cps_fetch_aggregate.py"

# 3. ACS 2025 1-year B05006 (national) - scheduled for release 2026-10-29 (Census CB26-164).
#    Downloads only once the table exists; build_stock_cps.py then adds the rows.
D="$R/acs1_api_2025"; mkdir -p "$D"
if curl -sS -f -m 120 -o "$D/groups_acs1_2025_B05006.json.tmp" "https://api.census.gov/data/2025/acs/acs1/groups/B05006.json" 2>/dev/null; then
  mv "$D/groups_acs1_2025_B05006.json.tmp" "$D/groups_acs1_2025_B05006.json"
  curl -sS -f -m 300 -G "https://data.census.gov/api/access/data/table" --data-urlencode "id=ACSDT1Y2025.B05006" \
       --data-urlencode "g=010XX00US" -o "$D/ACSDT1Y2025_B05006_us.json" || { echo "ACS 2025 table not available yet"; rm -f "$D/ACSDT1Y2025_B05006_us.json"; }
  curl -sS -f -m 300 -G "https://data.census.gov/api/access/data/table" --data-urlencode "id=ACSDT1Y2025.B05002" \
       --data-urlencode "g=010XX00US" -o "$D/ACSDT1Y2025_B05002_us.json" || rm -f "$D/ACSDT1Y2025_B05002_us.json"
else
  rm -f "$D/groups_acs1_2025_B05006.json.tmp"; echo "ACS 2025 1-year not released yet (api.census.gov/data/2025/acs/acs1 404)"
fi

# 4. Census Bureau population estimates (national totals) and WP56 census counts
D="$R/census_popest"; P=https://www2.census.gov/programs-surveys/popest
get "$P/tables/1900-1980/national/totals/popclockest.txt" "$D/popclockest.txt"
get "$P/tables/1990-2000/intercensal/national/us-est90int-07.csv" "$D/us-est90int-07.csv"
get "$P/datasets/2000-2010/intercensal/national/us-est00int-tot.csv" "$D/us-est00int-tot.csv"
get "$P/tables/2000-2010/intercensal/national/us-est00int-01.csv" "$D/us-est00int-01.csv"
get "$P/tables/2010-2020/intercensal/national/nst-est2020int-pop.xlsx" "$D/nst-est2020int-pop.xlsx"
get "$P/datasets/2020-2024/state/totals/NST-EST2024-ALLDATA.csv" "$D/NST-EST2024-ALLDATA.csv"
get "$P/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv" "$D/NST-EST2025-ALLDATA.csv"
get "$P/tables/2020-2025/national/totals/NA-EST2025-POP.xlsx" "$D/NA-EST2025-POP.xlsx"
get "https://www2.census.gov/library/working-papers/2002/demo/pop-twps0056/appendixA.xlsx" "$R/census_wp56/appendixA.xlsx"

# 5. Net international migration: Census newsroom text, CBO (Archive-It), Brookings; Pew (validation)
D="$R/census_newsroom"
get "https://www.census.gov/newsroom/press-releases/2026/population-growth-slows.html" "$D/population-growth-slows.html"
get "https://www.census.gov/newsroom/blogs/random-samplings/2026/01/historic-decline-in-net-international-migration.html" "$D/rs_historic-decline-in-net-international-migration.html"
get "https://www.census.gov/newsroom/press-releases/2026/dates-announced-for-2025-acs-1-year-estimates.html" "$D/dates-announced-for-2025-acs-1-year-estimates.html"
ait_get "$AIT/20260716071048/https://www.cbo.gov/system/files/2026-01/61879-Demographic-Outlook.pdf" "$R/cbo_demographic_outlook_2026/61879-Demographic-Outlook.pdf"
get "https://www.brookings.edu/articles/macroeconomic-implications-of-immigration-flows-in-2025-and-2026-january-2026-update/" \
    "$R/brookings_immigration_2026/macroeconomic-implications-of-immigration-flows-in-2025-and-2026-january-2026-update.html"
get "https://www.pewresearch.org/short-reads/2025/08/21/key-findings-about-us-immigrants/" "$R/pew_2025/pew_2025-08-21_key-findings-about-us-immigrants.html"
