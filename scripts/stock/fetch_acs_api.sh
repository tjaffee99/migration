#!/usr/bin/env bash
# Fetch ACS 1-year detailed tables B05006 (place of birth for the foreign-born) and
# B05002 (place of birth by nativity/citizenship; gives total pop + foreign-born)
# for the nation and all states (+DC, PR) from the keyless data.census.gov table API,
# plus variable metadata (labels) from api.census.gov/data/<yr>/acs/acs1/groups/<tbl>.json
# (metadata endpoints are keyless). Also fetches Decennial 2000 SF3 PCT019 / P021.
# Years: 2010-2024 (data.census.gov has no ACSDT1Y2005-2009; see fetch_acs_sf_2005_2009.sh).
# 2020 1-year standard estimates were not released (ACSDT1Y2020 does not exist).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/data/raw/acs1_api"
mkdir -p "$OUT"
API="https://data.census.gov/api/access/data/table"
get() { # id geo outfile
  local id="$1" g="$2" f="$3"
  if [[ -s "$f" ]]; then return 0; fi
  for attempt in 1 2 3 4; do
    if curl -sS -f -m 300 -G "$API" --data-urlencode "id=$id" --data-urlencode "g=$g" -o "$f.tmp"; then
      mv "$f.tmp" "$f"; return 0; fi
    sleep $((attempt*5))
  done
  echo "FAILED $id $g" >&2; rm -f "$f.tmp"
}
meta() { # url outfile
  local u="$1" f="$2"
  if [[ -s "$f" ]]; then return 0; fi
  curl -sS -f -m 300 "$u" -o "$f" || echo "FAILED meta $u" >&2
}
for y in 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2021 2022 2023 2024; do
  for t in B05006 B05002; do
    get "ACSDT1Y$y.$t" '010XX00US' "$OUT/ACSDT1Y${y}_${t}_us.json"
    get "ACSDT1Y$y.$t" '010XX00US$0400000' "$OUT/ACSDT1Y${y}_${t}_states.json"
    meta "https://api.census.gov/data/$y/acs/acs1/groups/$t.json" "$OUT/groups_acs1_${y}_${t}.json"
  done
done
# Decennial 2000 SF3
D="$ROOT/data/raw/dec2000_sf3"; mkdir -p "$D"
OUT="$D"
for t in PCT019 P021; do
  get "DECENNIALSF32000.$t" '010XX00US' "$D/DECENNIALSF32000_${t}_us.json"
  get "DECENNIALSF32000.$t" '010XX00US$0400000' "$D/DECENNIALSF32000_${t}_states.json"
  meta "https://api.census.gov/data/2000/dec/sf3/groups/$t.json" "$D/groups_dec2000sf3_${t}.json"
done
# ACS 5-year 2016-2020 B05006 (stand-in for 2020, when no standard 1-year was released)
D="$ROOT/data/raw/acs5_2020"; mkdir -p "$D"
get "ACSDT5Y2020.B05006" '010XX00US' "$D/ACSDT5Y2020_B05006_us.json"
get "ACSDT5Y2020.B05006" '010XX00US$0400000' "$D/ACSDT5Y2020_B05006_states.json"
meta "https://api.census.gov/data/2020/acs/acs5/groups/B05006.json" "$D/groups_acs5_2020_B05006.json"
# 2020 ACS 1-year *experimental* estimates: place of birth (total / native / foreign born)
D="$ROOT/data/raw/acs1_2020_experimental"; mkdir -p "$D"
for t in XK200501 XK200503; do
  [[ -s "$D/$t.xlsx" ]] || curl -sS -f -m 300 -o "$D/$t.xlsx" "https://www2.census.gov/programs-surveys/acs/experimental/2020/data/$t.xlsx"
done
# ACS 2005-2009 variable metadata (labels) used with the summary files
D="$ROOT/data/raw/acs_sf_2005_2009"; mkdir -p "$D"
for y in 2005 2006 2007 2008 2009; do for t in B05006 B05002; do
  meta "https://api.census.gov/data/$y/acs/acs1/groups/$t.json" "$D/groups_acs1_${y}_${t}.json"
done; done
echo done
