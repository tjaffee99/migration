#!/usr/bin/env bash
# Fetch archived copies of DHS/OHSS Yearbook of Immigration Statistics files.
#
# The live DHS sites (ohss.dhs.gov, www.dhs.gov) block this environment, so
# every file here comes from a public web ARCHIVE:
#   * Archive-It (Internet Archive)  https://wayback.archive-it.org/all/<ts>/<orig-url>
#   * Perma.cc captures deposited at archive.org  https://archive.org/download/perma_cc_<ID>/<ID>.warc.gz
# No third-party reader/fetch proxies are used.
#
# Usage: bash scripts/flows/fetch_archives.sh   (run from repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AIT="$ROOT/data/raw/archiveit_ohss"
PERMA="$ROOT/data/raw/perma_cc_dhs"
mkdir -p "$AIT" "$PERMA"

ait_get () {  # $1 = original URL, $2 = local file name
  local out="$AIT/$2" try
  if [ -s "$out" ] && ! grep -q -s "Rate limit reached" "$out"; then echo "have $2"; return 0; fi
  for try in 1 2 3 4 5 6; do
    curl -sS -L -m 600 -o "$out" -D "$out.hdr" "https://wayback.archive-it.org/all/20250101000000/$1" || true
    if grep -q -s "Rate limit reached" "$out"; then sleep $((20 * try)); continue; fi
    break
  done
  # keep the resolved capture URL (memento) for provenance
  grep -i '^location:' "$out.hdr" | tail -1 | sed 's/^[Ll]ocation: *//' | tr -d '\r' > "$out.memento" || true
  rm -f "$out.hdr"
  echo "$(stat -c %s "$out") $(file -b "$out" | cut -c1-40)  $2  <- $(cat "$out.memento")"
  sleep 8
}

# --- OHSS yearbook workbooks (xlsx) -------------------------------------
ait_get "https://ohss.dhs.gov/sites/default/files/2023-12/2023_0818_plcy_yearbook_lawful_permanent_residents_fy2022_0.xlsx" lpr_fy2022.xlsx
ait_get "https://ohss.dhs.gov/sites/default/files/2024-09/2024_0906_ohss_yearbook_lawful_permanent_residents_fy2023_0.xlsx" lpr_fy2023.xlsx
ait_get "https://ohss.dhs.gov/system/files/2026-06/2026_0604_ohss_yearbook_lawful_permanent_residents_fy2024.xlsx" lpr_fy2024.xlsx
ait_get "https://ohss.dhs.gov/sites/default/files/2024-10/2022_0405_plcy_lawful_permanent_residents_fy2021_excel_1.zip" lpr_fy2021_excel.zip
ait_get "https://ohss.dhs.gov/sites/default/files/2023-12/LPR2009_0.zip" lpr2009.zip
ait_get "https://ohss.dhs.gov/sites/default/files/2023-12/LPR2008_0.zip" lpr2008.zip
# INS yearbooks 1996-1999 table bundles
ait_get "https://ohss.dhs.gov/sites/default/files/2023-12/statyearbk96_0.zip" ins_yb1996.zip
ait_get "https://ohss.dhs.gov/sites/default/files/2023-12/ois_1998yb_0.zip" ins_yb1998.zip
ait_get "https://ohss.dhs.gov/sites/default/files/2023-12/ois_1999yb_4_0.zip" ins_yb1999.zip

# --- Perma.cc capture (deposited at archive.org) of the 2019 Yearbook PDF ----
# perma.cc/C24E-JGKR = https://www.dhs.gov/sites/default/files/publications/immigration-statistics/yearbook/2019/yearbook_immigration_statistics_2019.pdf
# Only pages 12-22 (Tables 1-3) are kept, to keep the raw folder small.
if [ ! -s "$PERMA/yearbook2019_tables1-3_p12-22.pdf" ]; then
  TMPD="$(mktemp -d)"
  for t in 1 2 3; do
    curl -sS -L -m 900 -o "$TMPD/C24E-JGKR.warc.gz" "https://archive.org/download/perma_cc_C24E-JGKR/C24E-JGKR.warc.gz" || true
    [ "$(stat -c %s "$TMPD/C24E-JGKR.warc.gz")" -gt 100000 ] && break; sleep 10
  done
  python3 -I "$ROOT/scripts/flows/warc_extract.py" "$TMPD/C24E-JGKR.warc.gz" "$TMPD/x" >/dev/null
  python3 -I "$ROOT/scripts/flows/pdf_pages.py" "$TMPD/x/yearbook_immigration_statistics_2019.pdf" 12 22 "$PERMA/yearbook2019_tables1-3_p12-22.pdf"
  rm -rf "$TMPD"
fi
ls -la "$PERMA"

# --- Census Bureau: Historical Statistics of the U.S., Colonial Times to 1957 (1960), chapter C
H60="$ROOT/data/raw/hsus1960_chC"; mkdir -p "$H60"
[ -s "$H60/hist_stats_colonial-1957-chC.pdf" ] || curl -sS -m 600 -o "$H60/hist_stats_colonial-1957-chC.pdf" \
  "https://www2.census.gov/library/publications/1960/compendia/hist_stats_colonial-1957/hist_stats_colonial-1957-chC.pdf"
