#!/usr/bin/env bash
# Fetch the raw inputs for the immigrant-flow files (scripts/flows/build_flows.py).
#
# The live DHS sites (ohss.dhs.gov, www.dhs.gov) block this environment, so every DHS/INS file
# comes from a public web ARCHIVE copy, never via a reader/fetch proxy:
#   * Archive-It (Internet Archive), exact captures:  https://wayback.archive-it.org/all/<ts>/<orig-url>
#   * Perma.cc capture deposited at archive.org:      https://archive.org/download/perma_cc_<ID>/<ID>.warc.gz
# plus the Census Bureau's own scan of Historical Statistics (1960).
#
# Usage (from anywhere):  bash scripts/flows/fetch_archives.sh
# Then:  python3 -I scripts/flows/ocr_hsus1960.py   (optional; needs tesseract; output is already in data/raw)
#        python3 -I scripts/flows/build_flows.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AIT="$ROOT/data/raw/archiveit_ohss"
PERMA="$ROOT/data/raw/perma_cc_dhs"
H60="$ROOT/data/raw/hsus1960_chC"
mkdir -p "$AIT" "$PERMA" "$H60"

ait_get () {  # $1 = Archive-It memento URL, $2 = local file name
  local out="$AIT/$2" try
  if [ -s "$out" ] && ! grep -q -s "Rate limit reached" "$out"; then echo "have $2"; return 0; fi
  for try in 1 2 3 4 5 6; do
    curl -sS -L -m 600 -o "$out" "$1" || true
    if grep -q -s "Rate limit reached" "$out"; then sleep $((20 * try)); continue; fi   # Archive-It throttles
    break
  done
  echo "$1" > "$out.memento"
  echo "$(stat -c %s "$out") $(file -b "$out" | cut -c1-40)  $2"
  sleep 8
}

# OHSS Yearbook of Immigration Statistics, Lawful Permanent Residents workbooks
ait_get "https://wayback.archive-it.org/all/20241115094237/https://ohss.dhs.gov/sites/default/files/2023-12/2023_0818_plcy_yearbook_lawful_permanent_residents_fy2022_0.xlsx" lpr_fy2022.xlsx
ait_get "https://wayback.archive-it.org/all/20241115000302/https://ohss.dhs.gov/sites/default/files/2024-09/2024_0906_ohss_yearbook_lawful_permanent_residents_fy2023_0.xlsx" lpr_fy2023.xlsx
# DHS 2009 Yearbook LPR tables (xls bundle)
ait_get "https://wayback.archive-it.org/all/20241116003221/https://ohss.dhs.gov/sites/default/files/2023-12/LPR2009_0.zip" lpr2009.zip
# INS Statistical Yearbooks 1996 and 1999 (xls bundles)
ait_get "https://wayback.archive-it.org/all/20241116003642/https://ohss.dhs.gov/sites/default/files/2023-12/statyearbk96_0.zip" ins_yb1996.zip
ait_get "https://wayback.archive-it.org/all/20241116003638/https://ohss.dhs.gov/sites/default/files/2023-12/ois_1999yb_4_0.zip" ins_yb1999.zip

# Perma.cc capture C24E-JGKR (2022-08-25) of
#   https://www.dhs.gov/sites/default/files/publications/immigration-statistics/yearbook/2019/yearbook_immigration_statistics_2019.pdf
# Only pages 12-22 (Tables 1-3) are kept, to keep the raw folder small.
if [ ! -s "$PERMA/yearbook2019_tables1-3_p12-22.pdf" ]; then
  TMPD="$(mktemp -d)"
  for t in 1 2 3; do
    curl -sS -L -m 900 -o "$TMPD/C24E-JGKR.warc.gz" "https://archive.org/download/perma_cc_C24E-JGKR/C24E-JGKR.warc.gz" || true
    [ "$(stat -c %s "$TMPD/C24E-JGKR.warc.gz")" -gt 100000 ] && break; sleep 10   # archive.org sometimes 500s
  done
  python3 -I "$ROOT/scripts/flows/warc_extract.py" "$TMPD/C24E-JGKR.warc.gz" "$TMPD/x" >/dev/null
  python3 -I "$ROOT/scripts/flows/pdf_pages.py" "$TMPD/x/yearbook_immigration_statistics_2019.pdf" 12 22 "$PERMA/yearbook2019_tables1-3_p12-22.pdf"
  rm -rf "$TMPD"
fi

# Census Bureau: Historical Statistics of the U.S., Colonial Times to 1957 (1960), chapter C
[ -s "$H60/hist_stats_colonial-1957-chC.pdf" ] || curl -sS -m 600 -o "$H60/hist_stats_colonial-1957-chC.pdf" \
  "https://www2.census.gov/library/publications/1960/compendia/hist_stats_colonial-1957/hist_stats_colonial-1957-chC.pdf"
ls -la "$AIT" "$PERMA" "$H60"
