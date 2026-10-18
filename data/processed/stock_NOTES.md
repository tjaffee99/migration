# Foreign-born population (stock) by country of birth, U.S. and states, 1850–2024

Regenerate everything with `bash scripts/stock/run_all.sh` (add `FETCH=1` to re-download missing
raw inputs). Raw downloads are under `data/raw/<source>/`; sources are described in
`sources_stock.csv`. Checks: `python3 -I scripts/stock/check_outputs.py`.

## Files

| file | rows | content |
|---|---|---|
| `stock_national_by_country.csv` | 4,636 | `year,origin_label,level,parent_label,count,source_id` — one series per year, 36 years |
| `stock_state_totals.csv` | 1,804 | `year,state,state_fips,total_pop,foreign_born,source_id` — 36 years |
| `stock_state_by_country.csv` | 168,377 | `year,state_fips,origin_label,level,parent_label,count,moe,source_id` — 26 years |
| `sources_stock.csv` | 62 | `source_id,citation,url,accessed,notes` |

### Hierarchy and levels (read this before summing)

Every block (national: one `year`; states: one `year` + `state_fips`) is a tree:

* `total` – the block's foreign-born total (`parent_label` blank).
* `region` – top-level groups (Europe, Asia, Africa, Oceania, Latin America, Northern America; ACS and
  2000 SF3 use **Americas**, which contains the subregions Latin America and Northern America).
* `subregion` – any deeper group (Northern Europe, British Isles, Caribbean, "Other Central America"
  when it has countries under it, "Former Soviet Union, in Europe", "Yugoslavia (former)" in 2000, ...).
* `country` – the first country-like unit on a branch.
* `subcountry` – **an extra level, not in the original spec, needed to avoid double counting**: a unit
  inside a country row — England/Scotland/Wales inside Great Britain / United Kingdom, Northern Ireland
  inside United Kingdom, Azores inside "Portugal (total)", Hong Kong and Taiwan inside the ACS/SF3 row
  "China", Canada-French/Canada-Other/Newfoundland inside Canada, Serbia inside ACS 2009–2011 "Yugoslavia".
  Never add subcountry rows to country rows.
* `residual` – "Other …", "… n.e.c.", "Not reported", "Born at sea", "All other countries", and
  remainders computed by the pipeline (labels ending in `(derived)`, `source_id` ending in `_derived`).

Invariant (verified for all 36 national blocks and all 1,278 state blocks):
**sum(level = country) + sum(level = residual) = total.** In addition every `parent_label` exists
in its block, labels are unique within a block, no count is negative, and every node with children
equals the sum of its children (zero exceptions).

Rules used to build the trees: the hierarchy comes from the indentation of the WP81 tables and from the
`!!` label paths of the ACS/SF3 variables (never from line numbers, which change between years).
A node whose value is not available in a year is dropped and its children attach to the nearest
available ancestor. Where an aggregate's children do not add up to it (e.g. Asia in 1960 lists only a
few countries), a residual `<aggregate>, country not specified (derived)` (or `<country>, remainder
(derived)` inside a country) carries the difference; an aggregate with no detail at all
(e.g. South America 1850–1930) gets one such child equal to itself. Children of residual rows are
not emitted (e.g. "Other Caribbean" → West Indies n.e.c./Other).

## Coverage matrix

| year(s) | national by country | state totals | state × country |
|---|---|---|---|
| 1850–1890 | WP81 T4 (1930-era detail, ~25–35 countries) | WP81 T14 | **gap** |
| 1900, 1910, 1920 | WP81 T4 | WP81 T14 | 1920 Census Vol II ch VI Table 10: principal countries (12–25 per state) + "All other countries", all 48 states + DC; manual transcription |
| 1930 | WP81 T4 | WP81 T14 | **gap** |
| 1940 | foreign-born **white** by 26 countries (1950 Census Table 49) + non-white residual | WP81 T14 | **gap** |
| 1950 | foreign-born **white** by 26 countries (1950 Census Table 49) + residual | WP81 T14 | foreign-born **white**, 33 categories, 48 states + DC (1950 Census Table 71; manual transcription) |
| 1960, 1970 | WP81 T3 (partial detail; many derived "not specified") | WP81 T14 | **gap** |
| 1980 | WP81 T3 (~120 countries) | WP81 T14 | **gap** |
| 1990 | WP81 T3 (~125 countries) | WP81 T14 | 6 world regions only (1990 STF4C PA23 extract) + derived "not reported" |
| 2000 | WP81 T3 (~130 countries) | WP81 T14 | 2000 SF3 PCT019 (≈100 countries/groups), 50 states + DC + PR |
| 2005–2008 | ACS 1-yr B05006 (summary file; 123 lines) | ACS 1-yr B05002 (SF) | ACS 1-yr B05006: 33 (2005), 36 (2006), 47 (2007, 2008) states; 3-year fills in 2007/2008 |
| 2009 | ACS 1-yr B05006 (SF; 161 lines) | ACS 1-yr B05002 (SF) | all 50 + DC (5-year 2005–2009 SF fill for 25 filtered states) |
| 2010–2019, 2021–2024 | ACS 1-yr B05006 (data.census.gov API; 161–178 lines) | ACS 1-yr B05002 | all 50 + DC (1-year where published; 5-year ending same year for the ~20–25 filtered states, `source_id` acs5_<y-4>_<y>_b05006) |
| 2020 | ACS **5-year 2016–2020** B05006 (no standard 1-year release) | ACS 2020 1-yr **experimental** XK200503 | ACS 5-year 2016–2020, all 50 + DC |

Decennial 2010 and 2020 censuses did not ask place of birth; the 2010 and 2020 points come from the ACS.
Alaska and Hawaii are not in WP81 before 1960 (not part of U.S. totals then). Puerto Rico (fips 72)
appears in ACS state totals and in 2000 SF3, but its ACS B05006 is filtered/absent (PR uses B05006PR).

## Sanity checks (from check_outputs.py)

* 1850: 2,244,602 (9.7%) ✓  1910: 13,515,886 (14.7%) ✓  1970: 9,619,302 ✓  2000: 31,107,889 ✓
  ACS 2023: 47,831,053 (B05006) / 47,831,411 (B05002) ✓
* State sums = national foreign born exactly for 1850–2000 (except 1960: WP81 Table 14 states sum to
  9,738,143, while WP81 Tables 1/3 give 9,738,091 — two 1960 sample tabulations). ACS: state B05002 sums equal the U.S. B05002 figure;
  B05006 totals are a few hundred lower than B05002 because B05006 excludes persons born at sea.
* State × country totals equal state totals for 1900–1920 (all 49 units) and 1990–2024.
* Cross-checks: WP29 Table 4 vs WP81 Table 4 (846 cells) and WP29 Table 3 vs WP81 Table 3 (550 cells)
  identical; WP29 Table 13 vs WP81 Table 14 (719 state values) identical.
* Manual transcriptions are fully constrained: 1950 Table 71 — all 539 printed row/column sum
  constraints hold; 1920 Table 10 — every state × year block adds to its total and every total
  equals WP81 T14; 1950 Table 49 — parts add exactly to the printed totals.

## Label changes / comparability (important for the map)

**1850–1930 (WP81 T4, census-era geography):** "Great Britain" (England, Scotland, Wales, GB n.e.c.) and
"Ireland" (whole island) to 1920; from 1930 "United Kingdom" = Great Britain + Northern Ireland and
"Ireland" = Irish Free State. "Soviet Union (former)" = Russia (Russian Empire) before 1920.
Austria, Hungary, Germany, Russia are the boundaries of each census (1910 adjusted for Poland).
"Czechoslovakia", "Yugoslavia", "Lithuania", "Latvia" etc. only from 1920/1930. "Turkey in Europe",
"Turkey in Asia", "Armenia", "Palestine", "Syria" as printed. "Portugal (total)" = Azores + Portugal
(WP81 prints both rows as "Portugal"; renamed). Canada includes Newfoundland (Canada-French /
Canada-Other / Newfoundland as subcountries, 1890–1930). "Sandwich Islands (Hawaii)" before 1900.
"Africa excl. Atlantic Islands" and "Atlantic Islands" are residuals (no country detail).

**1940, 1950:** only the foreign-born white population was tabulated by country. National rows give
the 26 printed categories ("England and Wales", "Scotland", "Northern Ireland" under a derived
"United Kingdom"; "Ireland (Eire)"; "U.S.S.R."; "Asia" (incl. Turkey in Europe) has no detail;
"Canada-French"/"Canada-Other" (incl. Newfoundland) under derived "Canada"; "Other America"), plus a
residual for the rest of the foreign born: 1940 = WP81 Table 9 races other than white (175,758,
exact: white + non-white = total); 1950 = WP81 total (10,347,395, sample) − Table 49 white total
(10,161,168), derived 186,227 — the two 1950 tabulations differ (WP81 T9 gives 251,980 non-white),
so treat 1950 residuals as approximate. Mexicans were classified as white in 1940/1950; Asian
countries are therefore heavily undercounted in these two years. The 1950 state × country block
total is the foreign-born white count (state all-race totals are in `stock_state_totals.csv`; they
are 20%-sample estimates and are smaller than the white count in 20 states, so no non-white
remainder was formed at state level).

**1900–1920 state tables (1920 Vol II Table 10):** countries are listed directly under Total (no
regions); England, Scotland, Wales are `country` rows (no UK/GB row), Ireland is the whole island.
"Russia and Lithuania"; "Jugo-Slavia"; Turkey in Asia appears as "Syria, etc." or "Armenia, etc."
(same group: Armenia, Palestine, Syria, Turkey in Asia) → label "Turkey in Asia (…; source: …)";
"Atlantic Islands (incl. Azores)", "West Indies (except U.S. possessions)" and "Central and South
America" are residuals; Canada has a "Canada-French" sub-line in some states (Canada-Other derived).
The countries shown vary by state (each state's principal countries); the rest is "All other countries".

**1960–2000 (WP81 T3):** 1960/1970 Taiwan included with China; 1960/1970 "Cape Verde" is Other Atlantic Islands (relabelled "Other Atlantic Islands (shown as Cape Verde in source)", level residual); "Korea (total)"; "Czechoslovakia (former)"; 2000: "Soviet Union (former)" is
replaced by "Former Soviet Union, in Europe" (Belarus, Moldova, Russia, Ukraine, USSR n.e.c.) and
"Former Soviet Union (part), South Central Asia" / "… Western Asia" (Kazakhstan …, Armenia,
Azerbaijan, Georgia); "Yugoslavia (former)" is a subregion with Yugoslavia, Bosnia and Herzegovina,
Croatia, Macedonia, Slovenia, Serbia, Kosovo; Palestine (1990) is in Asia n.e.c. in 2000;
"Portugal (total)" includes Madeira in 2000. "Micronesia (region)" vs "Micronesia (incl. Federated
States of Micronesia)" disambiguated. 2000 imputes country of birth (not reported = 316, born at sea).

**ACS B05006 (2005–2024) and SF3 PCT019 (2000):** "United Kingdom" (2005–2008) → "United Kingdom
(inc. Crown Dependencies)" (2009+), with subcountries "United Kingdom, excluding England and
Scotland" (= Wales, N. Ireland, Crown dependencies, UK n.e.c.), England, Scotland. "China" is a
country row that **includes** Hong Kong and Taiwan (subcountries "China, excluding Hong Kong and
Taiwan", "Hong Kong", "Taiwan"); in WP81 these are three separate countries. Line set expanded in
2009 (≈40 countries added), 2019 (Congo, DR Congo, Micronesia, Senegal, Uganda, Zimbabwe; "North
Macedonia (Macedonia)") and 2022 (Algeria, Azerbaijan, Bhutan, Georgia, Ivory Coast, Marshall Islands,
St. Lucia, Tanzania, Togo, UAE; "Burma (Myanmar)"); Yugoslavia dropped 2012 (Serbia was its child
2009–2011); "Azores Islands" under Portugal from 2013; "Cape Verde" → "Cabo Verde" 2014; Somalia 2015;
"Asia,n.e.c." → "Asia, n.e.c." 2020. ACS universe excludes persons born at sea; 2005 covers the
household population only. MOE (90%) given for ACS rows; blank for censuses and derived rows. In years
where some states use 5-year fills, state × country sums are not exactly the 1-year national figure.

## States and territories

`state` keeps the WP81 name (modern state names are used by the source for territories, e.g.
Washington 1860 = Washington Territory, Utah 1850 = Utah Territory incl. later Nevada, New Mexico
1850–1860 incl. later Arizona). Where the source footnotes a different area: "Dakota Territory
(shown as South Dakota in source; incl. present North Dakota)" 1860–1880 and "Virginia (incl. present
West Virginia)" 1850–1860 have blank `state_fips`; Oklahoma 1900 = Oklahoma Territory + Indian
Territory (fips 40). Territorial boundaries before statehood differ from the modern state.
State × country files use `state_fips` only (all blocks are single modern states).

## Gaps and what was tried (historical state × country)

* **NHGIS/IPUMS** (would cover 1850–1990 fully) need an API key — not used.
* Replication packages searched: Burchardi–Chaney–Hassan (Zenodo 8021467: README read; 2010 ancestry
  instruments + county crosswalks, 7.9 GB zip, no published historical FB-by-country counts in the
  README — not downloaded); Sequeira–Nunn–Qian (RES 2020) and Fulford–Petkov–Schiantarelli (JEG 2020):
  no accessible data deposit found (Zenodo/Dataverse/web search); UVA Historical Census Browser is
  closed; ICPSR 2896 requires login.
* Scanned census volumes on www2.census.gov contain the missing tables but have no usable text layer
  (OCR was tried and rejected as too error-prone; the 1900–1920 and 1950 tables were transcribed by
  hand and validated by their printed totals). Candidates for future transcription: 1850–1890 census
  "nativity" state tables; 1900 Vol. I Table 33 (full country list); 1930 Vol. II ch. 7 and Vol. III
  state tables; 1940 "Nativity and Parentage of the White Population — Country of Origin of the
  Foreign Stock" (www2.census.gov/library/publications/decennial/1940/population-nativity/);
  1960/1970 PC(1)-C state reports. HSUS Bicentennial C 228–295 (national only) OCR is garbled.
* 1990 state × country: only the 6-region STF4C extract is keyless; STF3/STF4 country detail is not.
* 2005–2008 state × country: ~4–18 small states have no B05006 (1-year filtered; no 3-year before 2007,
  and MT, ND, SD, WY have no 3-year B05006 either).
