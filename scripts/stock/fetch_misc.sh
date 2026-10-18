#!/usr/bin/env bash
# Fetch the non-API raw inputs of the stock pipeline (idempotent; skips existing files).
# Census WP29 tables (data/raw/census_wp29/) were provided in advance and are not re-fetched.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
R="$ROOT/data/raw"
g() { local u="$1" f="$2"; mkdir -p "$(dirname "$f")"; [[ -s "$f" ]] || curl -sS -f -m 600 -o "$f" "$u"; }
W2=https://www2.census.gov
# Working Paper 81 (Gibson & Jung 2006) tables 1-26
for i in $(seq -w 1 26); do g "$W2/library/working-papers/2006/demo/pop-twps0081/tab$i.xls" "$R/census_wp81/tab$i.xls"; done
# 1990 STF4C PA23 extract: region of birth of the foreign born, US/states/counties/places
g "$W2/census_1990/other/README.TXT" "$R/census1990_other/README.TXT"
g "$W2/census_1990/other/90fb-birth.txt" "$R/census1990_other/90fb-birth.txt"
# 1950 Census Vol. II Part 1 (U.S. Summary) chapter with Tables 49 and 71 (scanned; transcribed by hand)
g "$W2/library/publications/decennial/1950/population-volume-2/21983999v2p1ch3.pdf" "$R/census1950_v2p1/21983999v2p1ch3.pdf"
# 1920 Census Vol. II chapter VI (Table 10; scanned; transcribed by hand)
g "$W2/library/publications/decennial/1920/volume-2/41084484v2ch08.pdf" "$R/census1920_v2/41084484v2ch08.pdf"
# ACS 2005-2009 summary-file sequence/table lookups (1-year, plus 3-/5-year used for fills)
S=$R/acs_sf_2005_2009
g "$W2/programs-surveys/acs/summary_file/2005/documentation/Chapter_5_tables_summary_list.xls" "$S/2005_Chapter_5_tables_summary_list.xls"
g "$W2/programs-surveys/acs/summary_file/2006/documentation/merge_5_6_final.txt" "$S/2006_merge_5_6_final.txt"
g "$W2/programs-surveys/acs/summary_file/2007/documentation/1_year/merge_5_6_final.xls" "$S/2007_merge_5_6_final.xls"
g "$W2/programs-surveys/acs/summary_file/2008/documentation/1_year/user_tools/merge_5_6.xls" "$S/2008_merge_5_6.xls"
g "$W2/programs-surveys/acs/summary_file/2009/documentation/1_year/user_tools/merge_5_6.txt" "$S/2009_merge_5_6.txt"
g "$W2/programs-surveys/acs/summary_file/2007/documentation/3_year/merge_5_6_final.xls" "$S/2007_3yr_merge_5_6_final.xls"
g "$W2/programs-surveys/acs/summary_file/2008/documentation/3_year/merge_5_6.xls" "$S/2008_3yr_merge_5_6.xls"
g "$W2/programs-surveys/acs/summary_file/2009/documentation/5_year/user_tools/Sequence_Number_and_Table_Number_Lookup.txt" "$S/2009_5yr_Sequence_Number_and_Table_Number_Lookup.txt"
g https://api.census.gov/data/2007/acs/acs3/groups/B05006.json "$S/groups_acs3_2007_B05006.json"
g https://api.census.gov/data/2008/acs/acs3/groups/B05006.json "$S/groups_acs3_2008_B05006.json"
g https://api.census.gov/data/2009/acs/acs5/groups/B05006.json "$S/groups_acs5_2009_B05006.json"
echo done
