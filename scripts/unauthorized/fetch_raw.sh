#!/usr/bin/env bash
# Fetch the raw inputs for the illegal-immigration files (scripts/unauthorized/build_unauthorized.py).
#
# Everything lands in data/raw/<source_slug>/ (git-ignored). Hand transcriptions and small page extracts
# that cannot be re-created by this script are listed in data/processed/unauthorized_NOTES.md
# ("Files to keep in git") and must be whitelisted in .gitignore.
#
# Access notes (this environment, 2026-10): cbo.gov, dhs.gov, ohss.dhs.gov, cmsny.org, migrationpolicy.org,
# journals.sagepub.com, onlinelibrary.wiley.com and rand.org refuse direct requests. DHS/OHSS and CBO files
# therefore come from Archive-It captures (wayback.archive-it.org/all/<ts>/<url>, see ait_get.sh); CMS, MPI
# (2019) and the Yale PLOS ONE paper come from Perma.cc WARCs deposited at archive.org; the MPI 2025 fact
# sheet and the BLS 1986 note were obtained with the WebFetch tool (curl gets 403) and are kept as files.
#
# Usage: bash scripts/unauthorized/fetch_raw.sh        (re-runnable; skips files already present)
# Needs: curl, pdftotext (poppler); brotli for Python (pip install --target <dir> brotli) to decode the
#        Perma.cc WARCs: set PYLIB=<dir>.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$ROOT/data/raw"
HERE="$ROOT/scripts/unauthorized"
AIT="$HERE/ait_get.sh"
WARC="$HERE/warc_pages.py"
PYLIB="${PYLIB:-}"

get () {  # $1 url, $2 output path
  mkdir -p "$(dirname "$2")"
  if [ -s "$2" ]; then echo "have ${2#$RAW/}"; return 0; fi
  curl -sS -L -m 600 -o "$2" "$1" -w "%{http_code} %{size_download} ${2#$RAW/}\n" || echo "FAILED $1"
}
txt () { [ -s "${1%.pdf}.txt" ] || pdftotext -layout "$1" "${1%.pdf}.txt"; }
h2t () {  # $1 page.html, $2 output .txt (plain-text extract of an HTML page; <article> only if present)
  [ -s "$2" ] || [ ! -s "$1" ] || python3 -I - "$1" "$2" <<'PY'
import re, sys, html
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
i, j = t.find("<article"), t.find("</article>")
if i > 0 and j > i:
    t = t[i:j]
t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S)
t = re.sub(r"<(br|p|tr|div|h\d|li|figcaption)\b[^>]*>", "\n", t); t = re.sub(r"</t[dh]>", " | ", t)
t = re.sub(r"<[^>]+>", "", t); t = html.unescape(t); t = re.sub(r"[ \t]+", " ", t); t = re.sub(r"\n\s*\n+", "\n", t)
open(sys.argv[2], "w").write(t)
PY
}

# ---- Pew Research Center (pewresearch.org works directly) -------------------------------------------
P=$RAW/pew_2025_unauthorized
get "https://www.pewresearch.org/wp-content/uploads/sites/20/2025/08/RE_2025.08.21_Unauthorized-Immigrants_REPORT.pdf" $P/report.pdf
get "https://www.pewresearch.org/wp-content/uploads/sites/20/2025/08/RE_2025.08.21_Unauthorized-immigrants_detailed-tables_country-trends.xlsx" $P/detailed_tables_country-trends.xlsx
get "https://www.pewresearch.org/wp-content/uploads/sites/20/2025/08/RE_2025.08.21_Unauthorized-immigrants_detailed-tables_state-trends.xlsx" $P/detailed_tables_state-trends.xlsx
txt $P/report.pdf
P=$RAW/pew_older
for r in 44 61 94 126; do get "https://www.pewresearch.org/wp-content/uploads/sites/5/reports/$r.pdf" $P/pew_$r.pdf; txt $P/pew_$r.pdf; done
P=$RAW/pew_2026_border
get "https://www.pewresearch.org/short-reads/2026/02/02/migrant-encounters-at-the-us-mexico-border-are-at-their-lowest-level-in-more-than-50-years/" $P/page.html
h2t $P/page.html $P/page.txt
[ -s $P/usbp_sw_border_encounters_fy1960_2025.csv ] || python3 -I - "$P/page.html" "$P/usbp_sw_border_encounters_fy1960_2025.csv" <<'PY'
import re, sys, html
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for m in re.finditer(r"<table.*?</table>", t, re.S):
    cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(0), re.S)]
    if cells[:2] == ["Fiscal year", "Total encounters"]:
        with open(sys.argv[2], "w") as fo:
            fo.write("fiscal_year,encounters\n")
            for y, n in zip(cells[2::2], cells[3::2]):
                fo.write(f"{y},{n.replace(',', '')}\n")
        break
PY

# ---- DHS / OHSS / INS via Archive-It ---------------------------------------------------------------
D=$RAW/archiveit_ohss_unauth
bash $AIT "https://ohss.dhs.gov/sites/default/files/2024-06/2024_0418_ohss_estimates-of-the-unauthorized-immigrant-population-residing-in-the-united-states-january-2018%E2%80%93january-2022.pdf" $D/ohss_2018_2022.pdf 2025
for y in 2011_0 2012_0 2014_1; do
  bash $AIT "https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%2520January%2520${y}.pdf" $D/ois_jan${y%_*}.pdf 2025
done
bash $AIT "https://ohss.dhs.gov/sites/default/files/2023-12/Unauthorized%2520Immigrant%2520Population%2520Estimates%2520in%2520the%2520US%25201990%2520to%25202000.pdf" $D/ins_1990_2000.pdf 2025
for f in $D/*.pdf; do txt "$f"; done
B=$RAW/archiveit_dhs_border_security
bash $AIT "https://www.dhs.gov/sites/default/files/publications/17_0914_estimates-of-border-security.pdf" $B/dhs2017_estimates_of_border_security.pdf 2018
txt $B/dhs2017_estimates_of_border_security.pdf
C=$RAW/archiveit_cbo
bash $AIT "https://www.cbo.gov/system/files/2026-01/61879-Demographic-Outlook.pdf" $C/cbo_2026_61879_demographic_outlook.pdf 2026
bash $AIT "https://www.cbo.gov/system/files/2024-01/59697-Demographic-Outlook.pdf" $C/cbo_2024_59697_demographic_outlook.pdf 2024
for f in $C/*.pdf; do txt "$f"; done

# DHS 2019 Yearbook (Perma.cc C24E-JGKR at archive.org): keep only Tables 33 (apprehensions 1925-2019)
# and 39 (removals/returns 1892-2019).
E=$RAW/perma_cc_dhs_yb2019_enforcement
if [ ! -s $E/yearbook2019_tables33_39.pdf ]; then
  mkdir -p $E; T="$(mktemp -d)"
  curl -sS -L -m 900 -o "$T/w.warc.gz" "https://archive.org/download/perma_cc_C24E-JGKR/C24E-JGKR.warc.gz"
  python3 -I $WARC "$T/w.warc.gz" "yearbook_immigration_statistics_2019.pdf" "$T/yb2019.pdf"
  python3 -I - "$T/yb2019.pdf" "$E/yearbook2019_tables33_39.pdf" <<'PY'
import sys
from pypdf import PdfReader, PdfWriter
r, w = PdfReader(sys.argv[1]), PdfWriter()
for p in r.pages:
    t = p.extract_text() or ""
    if "ALIENS APPREHENDED: FISCAL YEARS 1925 TO 2019" in t or "ALIENS REMOVED OR RETURNED: FISCAL YEARS 1892 TO 2019" in t:
        w.add_page(p)
w.write(sys.argv[2])
PY
  rm -rf "$T"
fi
txt $E/yearbook2019_tables33_39.pdf

# ---- INS Statistical Yearbooks 1994/1995/1996 (archive.org, DOJ scans; OCR text + page images) ------
Y=$RAW/archiveorg_ins_yearbooks
for id in doj-reports_j-212-10994 doj-reports_j-212-10995 doj-reports_j-212-10996; do
  get "https://archive.org/download/$id/${id}_djvu.txt" $Y/${id}_djvu.txt
done
get "https://archive.org/download/doj-reports_j-212-10994/page/n179_w2000.jpg" $Y/pages/yb1994_p179.jpg   # Table N
get "https://archive.org/download/doj-reports_j-212-10996/page/n198_w2000.jpg" $Y/pages/yb1996_p198.jpg   # Table P
# Commissioner General of Immigration, Annual Report 1926 (no numeric estimate of illegal residents)
get "https://archive.org/download/annualreportofco1926unit/annualreportofco1926unit_djvu.txt" $RAW/archiveorg_cgi_annual_reports/annualreportofco1926unit_djvu.txt

# ---- Perma.cc WARCs at archive.org: CMS (Warren) 2019 essay, MPI 2019 profile, Yale PLOS ONE 2018 --------
W=$RAW/perma_cc_unauth
for id in PA8R-EWTQ B5S2-GL6H WRF9-SDPW B68X-FYK7; do get "https://archive.org/download/perma_cc_$id/$id.warc.gz" $W/$id.warc.gz; done
PL=(); [ -n "$PYLIB" ] && PL=(--pylib "$PYLIB")
[ -s $W/cms_warren2019_essay.txt ] || python3 -I $WARC $W/PA8R-EWTQ.warc.gz "publications/essay-2017-undocumented-and-overstays" $W/cms_warren2019_essay.txt --text "${PL[@]}"
for t in Table2 Table3; do
  [ -s $W/cms2019_$t.jpg ] || python3 -I $WARC $W/PA8R-EWTQ.warc.gz "uploads/2019/01/2017-Undoc-$t.jpg" $W/cms2019_$t.jpg "${PL[@]}"
done
[ -s $W/cms_warren_kerwin2017.txt ] || python3 -I $WARC $W/B5S2-GL6H.warc.gz "publications/jmhs-visa-overstays-border-wall/" $W/cms_warren_kerwin2017.txt --text "${PL[@]}"
[ -s $W/mpi_profile_US_2022capture.txt ] || python3 -I $WARC $W/WRF9-SDPW.warc.gz "data/unauthorized-immigrant-population/state/US" $W/mpi_profile_US_2022capture.txt --text "${PL[@]}"
[ -s $W/yale_plosone_2018.txt ] || python3 -I $WARC $W/B68X-FYK7.warc.gz "plosone/article?id=10.1371/journal.pone.0201193" $W/yale_plosone_2018.txt --text "${PL[@]}"

# ---- Other open sources ---------------------------------------------------------------------------
get "https://pmc.ncbi.nlm.nih.gov/articles/PMC3744247/" $RAW/pmc_warren_warren_2013/PMC3744247.html
[ -s $RAW/pmc_warren_warren_2013/PMC3744247.txt ] || python3 -I - $RAW/pmc_warren_warren_2013/PMC3744247.html <<'PY'
import re, sys, html
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S)
t = re.sub(r"<(br|p|tr|div|h\d|li|table|caption)\b[^>]*>", "\n", t); t = re.sub(r"</t[dh]>", " | ", t)
t = re.sub(r"<[^>]+>", "", t); t = html.unescape(t); t = re.sub(r"[ \t]+", " ", t); t = re.sub(r"\n\s*\n+", "\n", t)
open(sys.argv[1][:-5] + ".txt", "w").write(t)
PY
N=$RAW/census_popest_nim
get "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv" $N/NST-EST2025-ALLDATA.csv
get "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/totals/NST-EST2024-ALLDATA.csv" $N/NST-EST2024-ALLDATA.csv
get "https://www.census.gov/newsroom/press-releases/2026/population-growth-slows.html" $N/v2025_press_release.html
h2t $N/v2025_press_release.html $N/v2025_press_release.txt
get "https://www.census.gov/newsroom/blogs/random-samplings/2026/01/historic-decline-in-net-international-migration.html" $N/blog_historic-decline-in-net-international-migration.html
h2t $N/blog_historic-decline-in-net-international-migration.html $N/blog_historic-decline-in-net-international-migration.txt
get "https://www.census.gov/content/dam/Census/newsroom/blogs/2026/historic-decline-in-net-international-migration/historic-decline-in-net-international-migration-figure-2-data.xlsx" $N/blog_fig2_data.xlsx
get "https://www.everycrsreport.com/reports/RL33874.html" $RAW/crs_everycrsreport/RL33874.html
h2t $RAW/crs_everycrsreport/RL33874.html $RAW/crs_everycrsreport/RL33874.txt
get "https://files.eric.ed.gov/fulltext/ED210367.pdf" $RAW/eric_pre1980/ED210367.pdf; txt $RAW/eric_pre1980/ED210367.pdf
get "https://files.eric.ed.gov/fulltext/ED296133.pdf" $RAW/eric_pre1980/ED296133.pdf
# (the kept excerpt ED296133_excerpt_ch2_p19-21.txt = lines 1-12, 383-396 and 1030-1172 of `pdftotext -layout ED296133.pdf`)
get "https://www.brookings.edu/articles/macroeconomic-implications-of-immigration-flows-in-2025-and-2026-january-2026-update/" $RAW/brookings_2026_net_migration/page.html
h2t $RAW/brookings_2026_net_migration/page.html $RAW/brookings_2026_net_migration/page.txt
get "https://okcfox.com/news/nation-world/trumps-second-term-sees-25-million-illegal-aliens-leave-shattering-historic-records-dhs-tricia-mclaughlin" $RAW/sinclair_dhs_departures_2025/page.html
h2t $RAW/sinclair_dhs_departures_2025/page.html $RAW/sinclair_dhs_departures_2025/page.txt
get "https://royalexaminer.com/immigrants-in-u-s-without-permanent-legal-status-grew-to-12-2-million-study-finds" $RAW/cms_warren2025_secondary/royalexaminer.html
h2t $RAW/cms_warren2025_secondary/royalexaminer.html $RAW/cms_warren2025_secondary/royalexaminer_states_newsroom_2025-05-29.txt
get "https://en.wikipedia.org/w/index.php?title=Chinese_Confession_Program&action=raw" $RAW/wikipedia_unauth/Chinese_Confession_Program.wikitext

# WebFetch-only (curl gets 403 here): kept in git as files, see unauthorized_NOTES.md
#   data/raw/mpi_factsheet_2026/mpi-unauthorized-immigrants-fact-sheet-2025-final.pdf  <- https://www.migrationpolicy.org/system/files/2026-08/mpi-unauthorized-immigrants-fact-sheet-2025-final.pdf
#   data/raw/bls_mlr_1986_passel/mlr_1986_09_rpt2full.pdf                              <- https://www.bls.gov/opub/mlr/1986/09/rpt2full.pdf
for f in $RAW/mpi_factsheet_2026/*.pdf $RAW/bls_mlr_1986_passel/*.pdf; do [ -s "$f" ] && txt "$f"; done
echo "fetch done"
