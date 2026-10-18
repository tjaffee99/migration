# Arrivals, immigrant population, US population and net migration, 2024–2026: notes

These files carry the page past FY2023 (arrivals) and ACS 2024 (immigrants living here). They were
built on 2026-10-18. Run `bash scripts/recent/run_all.sh` to rebuild them, or
`FETCH=1 bash scripts/recent/run_all.sh` to download the raw inputs first. The checks are in
`python3 -I scripts/recent/check_recent.py`, which ends with "all checks passed". Every figure quoted
below is printed by these scripts.

| file | rows | content |
|---|---|---|
| `flows_recent_by_birth.csv` | 362 | LPRs by country, FY2024 (full year) and FY2025 (Q1 only). Same columns as `flows_by_birth_1989_present.csv`. **By country of nationality, preliminary** (see below) |
| `flows_recent_totals.csv` | 11 | National LPR totals by quarter, split into adjustments of status and new arrivals: FY2023 Q1–Q4, FY2024 Q1–Q4, FY2025 Q1 |
| `stock_recent_by_country.csv` | 6,468 | Foreign-born population by country of birth from the CPS: 32 monthly blocks (Jan 2024 – Sep 2026) and 3 annual means. Columns `year,months,origin_label,level,parent_label,count,source_id,note`. No ACS 2025 rows yet |
| `us_population_annual.csv` | 138 | US population: census counts for 1790–1890 (census years only), July 1 estimates for 1900–2025, and a projection for 2026 |
| `net_migration_recent.csv` | 16 | Net international migration, 2020–2026: Census Vintage 2024 and Vintage 2025, the Census 2026 projection, CBO and Brookings/AEI |
| `sources_recent.csv` | 19 | `source_id,citation,url,accessed,notes` |

Scripts are in `scripts/recent/`:
- `fetch_recent.sh` downloads everything and lists every URL.
- `cps_fetch_aggregate.py` fetches and aggregates the CPS microdata.
- `build_flows_recent.py`, `build_stock_cps.py`, `build_us_population.py` and `build_net_migration.py` build the processed files.
- `write_sources_recent.py` writes `sources_recent.csv`.
- `check_recent.py` runs the checks.

Raw inputs are in `data/raw/` (git-ignored, about 13 MB): `archiveit_ohss_recent/` (with `.memento` files), `census_cps_basic/`, `census_popest/`, `census_wp56/`, `census_newsroom/`, `cbo_demographic_outlook_2026/` (with a `.memento` file), `brookings_immigration_2026/` and `pew_2025/`.

## 1. Legal arrivals (LPRs), FY2024–FY2026

**What exists.** `ohss.dhs.gov` and `www.cbo.gov` return 403 to this environment. Every DHS file
therefore comes from an **Archive-It** capture, found with
`https://wayback.archive-it.org/all/timemap/link/<url>` and the closest-capture redirect
(`/all/20261018000000/<url>`). The Archive-It CDX endpoint returns "forbidden by administrative
rules", and it does not support prefix queries. No reader or proxy service was used. For each
publication, the latest capture is:

| publication | latest capture | what it holds |
|---|---|---|
| Legal Immigration and Adjustment of Status (LIAS) report page | 2025-11-15 | Lists FY2024 (Quarterly, Q1–Q4, posted 2025-06-24) and FY2025 Q1 (posted 2025-07-25). Both workbooks are captured and used |
| `/topics/immigration/yearbook/2024` | 2025-11-14 (its only capture) | "Tables 1-12: Lawful Permanent Residents (LPRs) (coming soon)" |
| `/topics/immigration/yearbook/2024/table1` … `table4` | none (empty timemaps) | OHSS posted the FY2024 LPR data tables on 2026-06-08, according to the page metadata shown in web search results. **No archived copy** exists, so they could not be read |
| Yearbook landing page | 2026-07-10 | "2024 Yearbook Download coming soon" |
| LPR pages, Tables 8–11 expanded | 2026-05/07 | Go only to FY2023 |

The previous agent used perma.cc items deposited at archive.org. These were checked with the
archive.org advanced search, and the newest DHS ones date from 2022, so they do not help here. The
OHSS monthly enforcement and legal-processes tables were not obtained. As OHSS describes them, they
cover enforcement and humanitarian processes, not LPRs.

**What the rows are.** All rows come from LIAS Table 1A, "Persons obtaining LPR status by type of
admission and region and **country of nationality**", using the Total column.

| FY | `basis` | period | total |
|---|---|---|---|
| 2024 | `preliminary_annual_nationality` | Oct 2023 – Sep 2024, all 4 quarters | **1,356,760** (Q1 281,810; Q2 329,740; Q3 369,480; Q4 375,730). This is 782,770 adjustments of status plus 573,990 new arrivals |
| 2025 | `preliminary_partial_q1_nationality` | Oct – Dec 2024 only | **350,120** (190,350 adjustments, 159,770 new arrivals). That is +24.2% on FY2024 Q1 |
| 2026 | — | — | **nothing published that can be reached** |

The FY2024 total is +15.7% on FY2023 (final, 1,172,910). The leading countries in FY2024 are
Mexico 200,720, Cuba 178,130, China (People's Republic) 70,090, Dominican Republic 67,460,
India 64,660 and Afghanistan 50,460.

**Caveats. Do not join these rows to the 1989–2023 birth series without a flag.**
- **Nationality is not country of birth.** FY2023 is published both ways, so it can be used to
  calibrate:
  - Preliminary-by-nationality total 1,173,640, against the final-by-birth total 1,172,910 (+730).
  - The nationality table has about 28,000 "Unknown" cases, against 730 by birth. That pushes most
    countries 0.5–5% below their birth count. For the top 20 countries the median gap is 2.0%;
    Cuba is the worst at −9.3% (74,040 against 81,600).
  - Hong Kong, Macau and the former-state rows exist only by birth.
- **Preliminary.** The FY2024 data are "as of October 2024". OHSS revises them in the Yearbook.
- **Rounding.** OHSS rounds every cell to the nearest 10, so leaf sums differ from the totals by up
  to 140.
- **Region parents.** These use the same country-to-region lookup as the FY2023 rows of
  `flows_by_birth_1989_present.csv`, plus Kiribati → Oceania. "Unknown" is both a region and its own
  residual, as in the FY2023 rows. "All other countries" is a residual under Total.

## 2. Foreign-born population by country of birth

### ACS 2025 1-year: not released

- The data.census.gov table API says "There is no table with the ID: ACSDT1Y2025.B05006".
- `api.census.gov/data/2025/acs/acs1/groups/B05006.json` returns 404.
- `www2.census.gov/programs-surveys/acs/summary_file/2025/` contains only an empty
  `table-based-SF/documentation/` folder, dated 2026-10-14.
- Census press release CB26-164 (13 Oct 2026) schedules the 2025 ACS 1-year estimates for
  **29 Oct 2026**. The release was delayed by a Commerce disclosure-avoidance order.

`fetch_recent.sh` downloads the table once it exists. `build_stock_cps.py` then adds the 2025 rows
with `source_id=acs1_api_b05006`, building the tree with the stock pipeline's own readers
(`scripts/stock/acs_read.py`, `stocklib.tree_rows`). This route was tested on the 2024 files: it
gives 179 rows, the same as `stock_national_by_country.csv`.

### CPS basic monthly, Jan 2024 – Sep 2026

**Months.** There are 32 months: all 12 of 2024; 11 of 2025, because the October 2025 CPS was not
collected during the government shutdown and no `oct25pub` file exists; and January–September 2026.
The microdata files (`<mon><yy>pub.dat.gz`, fixed width) are downloaded to a temporary directory,
aggregated and deleted. Only the aggregates are kept, in
`data/raw/census_cps_basic/aggregates/<yyyy>_<mm>_by_penatvty.csv`, one row per country ×
citizenship × month-in-sample. `manifest.csv` records each file's URL, size and sha256. Variable
positions are parsed from each year's record layout, and they are the same in 2024–2026.
`jan24pub.dat.gz` is actually a zip archive, which the script handles.

**Definitions and weights.**
- **Foreign born** means `PRCITSHP` = 4 (naturalized) or 5 (not a citizen): not a US citizen at
  birth. This is the Census/ACS definition, the universe of B05006. Counting every foreign
  `PENATVTY` code instead (100–555) would add about 3.3 million natives born abroad to American
  parents (`PRCITSHP` 3). For example, September 2026 would be 54.6 million instead of 51.2 million.
  No foreign-born record carries a US or island `PENATVTY` code.
- **Weight.** `PWSSWGT` is the final weight. The layout says it is "used for most tabulations"; its
  universe is every person, with 4 implied decimals, so it is divided by 10,000.
  - `PWCMPWGT`, the composited weight, covers only civilians aged 16+ and exists for BLS labor-force
    statistics. It therefore cannot give the whole foreign-born population.
  - For civilians 16+, the two weights agree within 0.11% in every month. For example, September 2026
    gives 48,876,861 with `PWCMPWGT` and 48,872,192 with `PWSSWGT`. Every month is in
    `data/raw/census_cps_basic/cps_foreign_born_monthly_summary.csv`.
- **Universe.** The CPS covers the civilian noninstitutionalized population. `PWSSWGT` sums **exactly**
  to the Census Bureau's Vintage 2025 civilian noninstitutionalized population (NA-EST2025-POP) in
  every 2026 month; September 2026 is 338,091,951 in both. The ACS also counts group quarters.
- **Country names.** These come from the code list in CPS Attachment 14, "Countries and areas of the
  world (starting May 2012)", in the January 2026 supplement technical documentation (`cpsjan26.pdf`).
  - The list has 162 codes. All 156 foreign codes that occur in the data are mapped.
  - Spellings are kept as printed, e.g. "Columbia".
  - Countries the CPS codes separately are combined into one `country` row with `subcountry` children,
    to match the ACS rows:
    - United Kingdom = 138 n.s. + England + Scotland + Northern Ireland
    - China = 207 + Hong Kong 209 + Taiwan 240, as ACS "China" does
    - Korea = 217 n.s. + South Korea 220
    - Portugal = 129 + Azores 130
    - Czechoslovakia = 105 + Czech Republic + Slovakia
  - Regions and subregions follow ACS B05006 (Europe/Asia/Africa/Oceania/Americas → Latin America
    and Northern America → …).
  - The "not specified" codes are residuals: 166, 249, 343, 374, 399, 462 and 555 "Elsewhere".
- **Annual mean.** This is the plain mean of the available monthly estimates. In `months`, `01-12`
  marks a full year, `01-09,11-12` marks 2025 without October, and `01-09` marks 2026 to date.
  Monthly rows have `months` = `MM`.

**Results.**

| year | months | foreign born (mean) | approx. 90% MOE |
|---|---|---|---|
| 2024 | 12 | 51,226,993 | ±0.69M |
| 2025 | 11 (no Oct) | 52,008,806 | ±0.92M |
| 2026 | Jan–Sep | 51,630,201 | ±0.78M |

The monthly series peaks at 53,312,015 in January 2025. It falls to 51,851,271 in June 2025 and to
51,036,358 in September 2025. It then moves between 50.5 and 52.6 million: the low is 50,453,975 in
July 2026, and September 2026 stands at 51,216,458. The mean for
January–September 2026 is 0.52 million below the mean for January–September 2025.

**Population-control breaks: read before comparing years.** CPS weights are re-controlled every
January to a new vintage of population estimates. History is not revised.

| CPS months | weights controlled to | gap to the Vintage 2025 civilian noninstitutionalized population |
|---|---|---|
| 2024 | Vintage 2023-based projections | **2.5–3.3 million lower** (the Vintage 2023 series missed most of the 2022–24 humanitarian surge) |
| 2025 | Vintage 2024-based projections | 0.2–0.7 million higher |
| 2026 | Vintage 2025 | exact |

The foreign-born count jumps at both seams: +1,556,194 from December 2024 to January 2025, and
+874,708 from December 2025 to January 2026. Part of the 2024→2025 "increase" in annual means is
therefore a weighting artifact. Within-year changes are cleaner than changes between years.

**Validation.**
- **Against ACS 2024 (50,234,841).** The CPS 2024 annual mean is **51,226,993**, a ratio of
  **1.0198**. That is slightly above the 47–50 million expected beforehand, even though the CPS
  excludes group quarters.
  - By region, CPS/ACS is: Europe 0.887, Asia 0.966, Africa 1.049, Oceania 0.946, Latin America
    1.076 (Central America incl. Mexico 1.103, Caribbean 1.043, South America 1.025), Northern
    America 0.759.
  - Large countries: Mexico 12.38M against ACS 11.14M (1.11), India 1.15, China incl. Hong Kong
    and Taiwan 0.88, Philippines 0.86, Cuba 1.02, El Salvador 0.93, Vietnam 0.91, Guatemala 1.16,
    Dominican Republic 1.03, Colombia 1.01, Korea 0.84, Honduras 1.31, Venezuela 1.15, Canada 0.76,
    Germany 0.70.
  - So the CPS shows more Latin American-born and fewer European-, Canadian- and East Asian-born
    residents than the ACS. Small countries differ more.
- **Against the published 2025 decline.** Pew Research (21 Aug 2025, CPS via IPUMS) reports
  53.3 million immigrants in January 2025 (15.8%) and 51.9 million in June 2025 (15.4%). The Census
  Bureau's Vintage 2025 blog reports the same CPS figures. This tabulation gives **53,312,015**
  (15.85% of CPS weights) and **51,851,271** (15.38%), so it reproduces both. After September 2025 the
  series moves sideways, between 50.5 and 52.6 million. It is higher in January–April 2026
  (52.0–52.6 million), just after the January 2026 control change, and lower in June–August 2026
  (50.5–51.0 million).
  - Pew and the Census Bureau both warn that part of the 2025 fall may be survey nonresponse among
    immigrants, coverage error or the population controls, rather than emigration.

**Sampling error.** The CPS samples roughly 11,000–13,000 foreign-born person records a month, so
treat any country under about 100 records a month with care. The `note` of every row gives `n` and an
**approximate 90% MOE**, and adds "CV>30%: unreliable" where that applies. The MOEs are computed by
the pipeline, not published by BLS: the BLS generalized-variance parameter files return 403 here.
- **Method.** The 8 month-in-sample rotation groups of a month serve as random groups:
  Var = Σ(X_g − X̄)²/56, where X_g is 8 × the rotation group's weighted total. This variance is
  averaged over the months of the calendar year.
- **Annual means.** The pooled monthly variance is multiplied by F = Σ_c n_c² / (8·|S|²). Here n_c is
  the number of the |S| months that rotation cohort c is in sample under the 4-8-4 design.
  F is 0.316 for 12 months, 0.320 for 11 and 0.383 for 9. This assumes a household keeps its
  birthplace from month to month, which makes it conservative.
- **Size.** The monthly SE of the total is about 0.8 million on average, so the 90% MOE is about
  ±1.3 million. Month-in-sample bias and calibration effects are ignored, which also makes the MOEs
  conservative. Treat month-to-month moves of less than about 1 million in the total as noise.

## 3. US population, `us_population_annual.csv`

| years | basis | source |
|---|---|---|
| 1790–1890, census years only | `census_count` (census day, not July 1) | Census WP56 Appendix A, US rows. 1870 is the original count, not adjusted for the Southern undercount. 1890 = total population incl. Indian Territory and reservations (62,947,714; Table A-15) |
| 1900–1929 | `estimate_jul1_resident_excl_ak_hi_rounded_1000` | `popclockest.txt` (Census, 2000) |
| 1930–1939 | `estimate_jul1_resident_excl_ak_hi` | same |
| 1940–1949 | `estimate_jul1_resident_plus_af_overseas_excl_ak_hi` | same. Includes Armed Forces overseas (large in 1942–46) |
| 1950–1979 | `estimate_jul1_resident_plus_af_overseas` | same |
| 1980–1989 | `estimate_jul1_resident` | same |
| 1990–2019 | `intercensal_jul1_resident` | 1990–2000, 2000–2010 and 2010–2020 (Nov 2024) intercensal series |
| 2020–2025 | `postcensal_v2025_jul1_resident` | Vintage 2025 (Jan 2026); matches the July values of NA-EST2025-POP |
| 2026 | `projection_v2025_jul1_resident` | **342,620,143**: the Vintage 2025 short-term projection for July 1, 2026 in NA-EST2025-POP ("estimates beginning with August 1, 2025 are short-term projections"). This is the series behind the population clock and the 2026 CPS controls |

**Seams.**
- **1999→2000:** +3.12 million (279,040,168 → 282,162,411). This is the normal step between two
  intercensal series.
- **2010:** the two intercensal series differ by 28,538 for July 1, 2010; the 2010–2020 series is
  used.
- **1990s:** the old postcensal 1999 figure in `popclockest` was 6.35 million below the intercensal
  one, so it is not used.
- **1918:** the only year-on-year decline in the series (WWI and influenza).
- **2024–2026:** 340,003,797 → 341,784,857 → 342,620,143, i.e. +0.52% and then +0.24%.

## 4. Net international migration, `net_migration_recent.csv`

| series | periods | notes |
|---|---|---|
| `census_v2024_nim` | 2020 (Apr–Jun) and estimate years 2021–2024 (Jul–Jun) | 2024 = 2,786,119 |
| `census_v2025_nim` | the same, plus 2025 | 2024 revised to 2,734,468; **2025 = 1,262,202** (Jul 2024–Jun 2025) |
| `census_v2025_nim_projection` | Jul 2025–Jun 2026 | **≈321,000**, from the press release and blog "if current trends continue". Immigration was projected from monthly benchmark data, and emigration was assumed to double from 2025. This feeds the 2026 CPS controls |
| `cbo_jan2026_net_immigration` | calendar 2025 and 2026 | 410,000 (estimate) and 570,000 (projection). Uses the Social Security-area population concept |
| `brookings_aei_jan2026_net_migration` | calendar 2025 and 2026 | Ranges only: 2025 −295,000 to −10,000; **2026 −925,000 to +185,000** (`low`/`high`; no central value) |

The Census periods (July–June) and the CBO and Brookings periods (calendar years) are different
windows, so do not difference across series. No estimate made after January 2026 was found.

## Gaps and what was tried

- **FY2024 LPRs by country of birth (final Yearbook, June 2026):** no archived copy. Archive-It
  timemaps for the 2024 yearbook table pages are empty, and no perma.cc copy exists.
  `flows_recent_by_birth.csv` therefore holds **preliminary nationality** counts. When the Yearbook
  workbook becomes reachable, replace FY2024 with Table 3 (birth).
- **FY2025 Q2–Q4 and all of FY2026 LPRs:** not captured; the LIAS page was last captured on
  2025-11-15. FY2025 is Q1 only.
- **ACS 2025 1-year:** due 29 Oct 2026; the pipeline hook is in place.
- **BLS CPS standard-error parameters** (`bls.gov/cps/methods/...`): 403. The MOEs are the
  pipeline's random-group approximation.
- **Re-weighting CPS 2024 and 2025 to the Vintage 2025 controls:** not done. It cannot be done
  properly from the public files, because the controls are by age, sex, race, Hispanic origin and
  state, and nativity is not one of them.
