# Illegal immigration: estimates, arrivals and indicators (1882–2026)

Files built by `scripts/unauthorized/build_unauthorized.py` from inputs fetched by
`scripts/unauthorized/fetch_raw.sh` (raw files in `data/raw/<source_slug>/`). The build re-reads every
saved raw file and checks 230 "evidence" snippets (each number typed from report prose or a scan is
matched against the saved text); it stops if any check fails or if a child-sum test fails.

**Wording.** These notes and the series descriptions say *illegal immigrants / illegal immigration*.
The file names keep "unauthorized", and the sources use "unauthorized", "undocumented" or "other
foreign nationals". Every published series is wider than "people who crossed illegally or overstayed".
Most of them also count people who hold a temporary, revocable legal permission: parolees, people
released at the border to await court, pending asylum applicants, TPS holders and DACA recipients.
Each row's `note` says when that applies, and §3 gives the part that is illegal-only wherever a source
publishes it.

| File | Content |
|---|---|
| `unauthorized_population.csv` | Estimated number of illegal immigrants living in the US (stock), total and by region/country of birth where published |
| `unauthorized_inflows.csv` | New arrivals (gross inflow), net change, survivors by period of entry, and outflow components |
| `unauthorized_indicators.csv` | Enforcement and administrative counts. **These are not migrant counts** (events, repeat crossers, legal migrants mixed in) |
| `sources_unauthorized.csv` | One row per `source_id`: citation, URL (Archive-It/Perma.cc address where the live site blocks this environment), notes |

## 1. Conventions

- **`level`**: `total` / `region` / `country` / `residual`, as in the other `data/processed` files. Within
  one `year` (or period) and one `source_id`, the `country` and `residual` rows add up to the `total`.
  The build checks this, with tolerances for the sources' independent rounding: the largest gap is 0.17%.
  A region with no country detail gets a residual child, "X (no country detail in source)". A region with
  partial detail gets "Other X (derived)", which equals the region minus the listed countries. Mexico is
  a `country` directly under "All countries" in Pew, OHSS, CMS and the INS yearbooks. INS 2003 places it
  under "North America", and MPI under "Mexico and Central America".
- **`low`/`high`**: these hold the published range (Pew: 90% confidence interval; INS 1996: 4.6–5.4
  million; Yale: 95% interval). They also hold rounding bounds for values derived from rounded shares.
  **When only a range was published, `count` is blank** (SPR 1978, INS 1981, DHS's "2–4 million in 1980",
  Brookings 2025).
- **Derived values** say "derived" in the note: residuals, the MPI regions computed from rounded shares,
  the Pew 2021 and 2007 "no protection" figures, the CMS 2020 figure, and the CBO sums of illegal-only
  components. Nothing is interpolated.
- **Tokens in `note`**:
  - `ref=` is the reference date of a stock.
  - `component=` names the flow component (`entered`, `left_total`, `emigrated`, `removed_by_DHS`,
    `visa_overstays`, `entries_without_inspection`, `released_at_ports_OFO`, …).
  - `unit=annual_average` or `unit=period_total` says how to read `count` for a multi-year period. Single
    years carry no `unit` and give the yearly number.
  - `stock_year=` is the year of the stock that an `entered_period` row was measured in.
  - `months=` marks periods that are not calendar years.
  - `PROJECTION` marks values that are not estimates.
- **Inflow `basis`**:
  - `gross_inflow`: people joining the population in the year or period, before any departures.
  - `net_change`: the change in the stock.
  - `entered_period`: people in a later stock who had entered in the period. These are survivors only, so
    they understate arrivals.
  - `other`: outflow components, net migration of all migrants (Census, Brookings) and administrative
    claims.
  - `period_start` is blank for open-ended bins ("before 1970", "20+ years in the US").

## 2. Recommended primary series

**Stock: `pew2025_passel_krogstad`** (Pew Research Center, Passel & Krogstad, Aug 2025), 1990–2023.

- It is the only series that is continuous over 34 years, re-estimated in one pass with one method, and
  internally consistent: Pew says it supersedes all earlier Pew estimates.
- It gives 8 regions plus 18 countries for every year, and 90% margins of error.
- Its 2022–2023 values already include the Census Bureau's Vintage-2024 upward revision of
  2021–2023 immigration (the humanitarian surge). DHS's latest estimate (Jan 2022, from the 2021 ACS)
  predates that revision.
- Reference dates: July 1 (2005–2023, ACS), March 1 (1995–2003, CPS), April 1 1990 (taken from Warren &
  Warren 2013).
- Missing years: 1991–94, 1996–97, 1999, 2001–02, 2004 and 2020 (no 2020 estimate because of COVID survey
  problems).
- Definition: it includes about 6.0 million people with temporary protection in 2023, against 2.7 million
  in 2021 and 0.5 million in 2007. The illegal-only companion series is `pew2025_no_protection`
  (8.0 million in 2023).

For a **yearly** line, fill the Pew gaps from the shape of the annual series rather than from their
levels. Use Warren & Warren 2013 (`warren_warren2013_imr`, Jan 1 1990–2010) or INS 2003 (1990–2000)
for 1991–2004, and DHS/OHSS for 2020. The levels differ by up to about 1 million: Pew 2000 = 8.6 million,
W&W Jan 2000 = 8.6 million, INS Jan 2000 = 7.0 million because INS excludes quasi-legal groups, and
OHSS 2000 = 8.46 million. **After 2023** nobody has published a complete estimate. Pew's 2025 report
says the population "likely continued to increase rapidly through at least mid-2024", grew little in
the second half of 2024, and fell in Jan–Jun 2025 "possibly by as much as 1 million". As of July 2025
it was still above 14 million. CBO's net change of "other foreign nationals" (+1.3 million in 2024,
−0.36 million in 2025, −0.33 million projected for 2026) is the only published yearly quantity for
2024–2026.

**Arrivals: `warren_warren2013_imr` 1990–2009** (yearly gross "entered" and outflow components),
plus the CBO gross components for 2023–2025. See §6 for building a series by origin.

## 3. Coverage and definitions by source

### Stock (`unauthorized_population.csv`)

| source_id | Years (reference date) | Origin detail | Parolees / pending asylum / TPS / DACA | Notes |
|---|---|---|---|---|
| `pew2025_passel_krogstad` | 1990, 1995, 1998, 2000, 2003, 2005–2019, 2021–2023 | 8 regions (Mexico, Central America, South America, Caribbean, Europe & Canada, Asia, Middle East–N. Africa, sub-Saharan Africa) + 18 countries | **Included** (≈6.0 million of 14.0 million in 2023) | Residual method; 90% CI |
| `pew2025_no_protection` | 2023 (+2021, 2007 derived) | total | **Excluded**: no protection from deportation | 2023: 8.0 million; Pew also says ">12 million entered illegally or overstayed; 2 million entered legally and were paroled or released" |
| `ohss2024_baker_warren` (+`_prev_basis`) | Jan 1 2000, 2005–2020, 2022 | 10 countries + rest | **Included** (TPS, DACA, other deferred action, people awaiting removal proceedings, parolees) | Breaks in 2010, 2015 and 2018 (both values kept); no 2001–04 or 2021; China includes HK/Macau from 2018 |
| `ins2003_warren` | Jan 1 1990–2000 (countries 1990 and 2000) | 6 continents, 75 countries | **Excluded**: refugees, asylees, parolees with work permits, people allowed to stay under legislation or court rulings | The closest to an illegal-only definition, but Honduras 2000 includes 105,000 TPS |
| `warren_warren2013_imr` | Jan 1 1990–2010 | total (states in the paper) | Partly included (asylees/parolees with work permits, pending I-485, TPS: about 577,000 in 2000) | Base of the CMS series |
| `ins_yb1996_tableP` / `ins_yb1996_text` | Oct 1996 (range 4.6–5.4 million); Oct 1992 revised 3.9 million | 20 countries | Included where status was pending (e.g., Salvadorans with DED) | Superseded by INS 2003 (Oct 1996 ≈ 5.8 million) |
| `ins_yb1994_tableN` / `ins_yb1994_text` | Oct 1992 (3,379,000); 1988 2.2 million; 1987 "nearly 5 million" | 20 countries | — | Original Warren (1994) estimate |
| `woodrow_passel1990_via_crs` | June 1986 3.2 million (Mexico 2.1 million, Asia 0.2 million); June 1988 1.9 million | Mexico, Asia | — | Secondary (CRS RL33874) |
| `passel_woodrow1984_via_chiswick1988` | Apr 1 1980: 2,057,000 **counted in the census** | Mexico + 4 groups | — | Excludes people missed by the census |
| `ois2012_hoefer_rytina_baker` | 1980: 2–4 million (range) | — | — | DHS citing Warren & Passel 1987 |
| `ins1981_meissner_testimony` | 1981: 3–6 million (range) | — | — | Official INS position before IRCA |
| `siegel_passel_robinson1981_via_chiswick1988` | "say 1978": 3.5–6.0 million (Mexico 1.5–3.0 million) | Mexico | — | Census Bureau review of earlier studies (quoted by Chiswick 1988) |
| `census2001_residual_via_ins2003` | 2000: 8.7 million | — | **Included** ("quasi-legal") | Secondary |
| `cms2019_warren` | 2010, 2017 | 15 countries | Included | Transcribed from images |
| `cms2025_warren_via_statesnewsroom` | 2023: 12.2 million; 2020: 10.2 million (derived) | Venezuela | **Included** (DACA, TPS, pending asylum, parolees) | Secondary news report |
| `mpi_profile2019` | 2019 (pooled 2015–19) | 6 regions, 5 countries | Included | 11.05 million |
| `mpi2025_factsheet` / `mpi2025_without_liminal` | mid-2023: 13.74 million; ≥9.74 million without liminal status | 6 regions (from rounded shares), 10 countries | Included ("as many as 4 million" with TPS, DACA, pending asylum or parole) | Fetched via WebFetch |
| `yale2018_fazelzarandi` | 2016: 22.1 million (95% interval 16.2–29.5 million) | — | n/a (flow model) | Outlier; not recommended |

### Arrivals and net change (`unauthorized_inflows.csv`)

| source_id | Coverage | What it measures |
|---|---|---|
| `warren_warren2013_imr` | yearly 1990–2009 | entered, left (emigrated, adjusted, removed, died), net change |
| `ins2003_warren` | yearly 1990–1999; **Mexico / Central America / other** for entries | entered = arrived in the year and still illegal at year end; 5 outflow components |
| `pew2010_passel_cohn`, `pew2008_passel_cohn` | 2000–05, 2005–07, 2007–09 (Mar–Mar), 2000–04, 2005–08 | yearly-average gross arrivals (Mexico shown separately), net growth, survivors by period of arrival |
| `pew2006_passel`, `pew2005_passel` | 2005 and 2004 stocks | survivors by arrival period (1980s, 1990–94, 1995–99, 2000–04/05) |
| `ois2012…`, `ois2013…`, `ois2017_baker`, `ohss2024_baker_warren` | 2007, 2011, 2012, 2014, 2018–2022 stocks | survivors by period of entry from 1980 |
| `mpi_profile2019`, `mpi2025_factsheet` | 2019 and 2023 stocks | years of US residence → approximate entry periods |
| `census_passel1986_mlr`, `passel_woodrow1984_via_chiswick1988` | 1980 census | entered 1975–80 (941,000–946,000), 1970–74, before 1970; net growth 1980–83 100,000–300,000 a year; Census assumption 200,000 a year |
| `ins1981_meissner_testimony` | 1981 | net growth 250,000–500,000 a year |
| `ins_yb1994_text`, `ins_yb1996_text` | 1988–92, 1992–96 | net growth 300,000 / 281,000 / 275,000 a year; Mexico about 150,000 a year net and about 230,000 a year arriving |
| `cms2019_warren` | 2016 | 515,000 arrivals: 320,000 overstays, 190,000 entries without inspection; top-5 countries for each |
| `dhs2017_border_security` | FY2000, FY2016 | modelled successful illegal crossings between ports of entry on the southwest border: 1.8 million → 170,000 |
| `cbo2024_demographic_outlook` | 2021–2023 (+2024 projection); FY2023 components | net "other foreign nationals"; FY2023 gross 3.3 million = 1.1 million Border Patrol releases + 0.9 million port-of-entry releases + 0.86 million not encountered + 0.43 million overstays |
| `cbo2026_demographic_outlook` | 2010–19 average; 2021–2025; projections 2026–2036; gross components 2023–2025; 2025 outflows | net OFN: 0.83, 2.0, 2.4, 1.3, −0.36 million; 2025 inflow 380,000 (310,000 illegal-only); 2025 outflow about 750,000 (400,000 voluntary, 120,000 interior removals, 225,000 legalized) |
| `cbo2025_jan_…`, `cbo2025_sep_…` | 2025 | superseded projections (+1.1 million, −0.29 million) |
| `pew2025_passel_krogstad` | Jul 2023–Dec 2024; 2019–23 entrants; Jan–Jun 2025 | releases and paroles (2.5 million; temporary permission, not illegal entries); adults under 5 years in the US (4.2 million in 2023); 2025 decline up to 1 million |
| `census_v2025_popest`, `census_v2024_popest` | Jul–Jun 2021–2025 (+2026 projection) | **all** net international migration (legal status not estimated): context only |
| `brookings2026_edelberg_veuger_watson` | 2025, 2026 | all-status net migration −295,000 to −10,000 (2026: −925,000 to +185,000); entries without inspection 22,000–39,000; parole/notice-to-appear releases 67,000–70,000; removals 310,000–315,000 |
| `dhs2025_press_statement_via_tnnd` | Jan 20–Dec 10 2025 | administration claim: more than 2.5 million left (605,000 deported, 1.9 million "self-deported", an estimate with an undisclosed method) |

### Indicators (`unauthorized_indicators.csv`). None of these is a count of illegal immigrants.

- `apprehensions_nationwide`, FY1925–2019 (DHS Yearbook Table 33). From 1952 it includes ICE
  administrative arrests, and from 2008 all ICE ERO arrests. Counts are events, so one person
  apprehended several times counts several times.
- `usbp_southwest_border_apprehensions_encounters`, FY1960–2025 (Pew/CBP). From March 2020 it includes
  Title 42 expulsions.
- `removals` FY1892–2019 and `returns` FY1927–2019 (Table 39). These cover all deportable people,
  including some who entered legally.
- `usbp_known_gotaways_sw_border` (2006, 2013, 2016) and `usbp_observed_gotaways_reported` (FY2023).
- `suspected_in_country_overstays` (FY2024).
- `humanitarian_migrant_arrivals_benchmark` 2015–2025 (Census Bureau benchmark: refugees, who are
  legal, plus parolees and border releases).
- Chinese Confession Program 1956–65: 13,895 confessions, 22,083 people exposed, 11,294 "paper son"
  slots closed. These measure illegal entry during the Chinese-exclusion era only indirectly.

## 4. How each series treats temporary statuses

| Group | Pew | DHS/OHSS | INS 2003 | W&W 2013 / CMS | MPI | CBO "OFN" |
|---|---|---|---|---|---|---|
| Entered without inspection / overstayed | in | in | in | in | in | in |
| Parolees (CHNV, U4U, CBP One, port-of-entry paroles) | in | in ("until admitted or otherwise acquire status") | out (if work-authorized) | in | in | in |
| Released at the border with a notice to appear | in | in (awaiting proceedings) | — | in | in | in |
| Pending asylum applicants | in | in (not legal residents until granted) | in (not listed among the exclusions) | in | in | in |
| TPS | in | in | out (but Honduras 2000 in) | in | in | in (implied by CBO's TPS-termination emigration) |
| DACA | in | in | n/a | in | in | in (implied) |
| Granted asylum / refugees | out | out | out | out | out | out (LPR+) |

CBO and Pew are the only sources that also show how large the temporary-status part is in recent
years:

- Pew 2023: 6.0 million of 14.0 million had some protection.
- CBO FY2023 arrivals: 2.0 million of 3.3 million were releases or paroles.
- CBO 2025 arrivals: 80,000 of 380,000 were releases or paroles.

MPI says "as many as 4 million" of 13.7 million held a liminal status in mid-2023.

## 5. Overlaps and double counting with the site's legal-immigration data

1. **Stocks.** The foreign-born totals (`stock_*` files: census and ACS) already include the illegal
   immigrants that the census or ACS enumerated. Illegal-immigrant stocks are a subset, plus an allowance for
   people the surveys missed (for example, INS 2003 assumed a 10% census undercount). Never add them to foreign-born totals; show them as a share.
2. **IRCA (1986).** About 2.7 million people legalized. They were counted as LPR "immigrants" mainly in
   FY1989–1991 (the spike in `flows_totals_1820_present.csv`), yet they had arrived years earlier: the general
   program required residence since before January 1, 1982, and the Special Agricultural Worker program
   covered earlier farm work. An arrivals series
   that adds illegal arrivals to LPR admissions counts these people twice. Either drop the IRCA
   legalizations from the LPR counts or attribute them only to their earlier illegal arrival. Pew counts IRCA
   beneficiaries as legal from the date their application was approved. The stock falls from 3.2 million (1986)
   to 1.9 million (1988).
3. **Adjustment of status.** Many LPRs adjust status inside the US rather than arriving from abroad. Some of them were
   earlier counted as illegal arrivals: overstayers marrying citizens, 245(i) cases, Cuban parolees
   under the Cuban Adjustment Act, asylees, and people with TPS who later adjust. Warren & Warren and INS
   2003 report these exits each year (`component=adjusted_to_legal_status…`), and CBO estimates 225,000
   in 2025. To count each person once, combine illegal *arrivals* with LPR *new arrivals from abroad*,
   not with all LPR admissions, or subtract the adjustment outflow.
4. **Parolees and asylum seekers 2021–2024.** These people enter the illegal-immigrant estimates
   (Pew, DHS, CMS, MPI, CBO), but they are lawfully present while their status lasts. Some will later
   appear in LPR counts. The Census NIM, the Census humanitarian benchmark and CBO all count them. Do not
   add CBO "other foreign nationals" to Census NIM: NIM already includes them.
5. **Overlapping estimates.** Do not sum different sources for the same year. W&W/CMS, INS 2003 and
   DHS/OHSS share an author (R. Warren) and inputs, and Pew's 1990 value comes from Warren & Warren 2013.

## 6. Building a yearly series of illegal arrivals by origin, 1980s–2026

No source publishes yearly *gross* illegal arrivals by country for the whole period. The most
defensible construction from these files:

1. **1980–1989: survivors and bounds only.**
   - The Census Bureau counted 941,000–946,000 people in the 1980 census who had entered in 1975–80, and
     576,000 who entered in 1970–74.
   - Net growth was 100,000–300,000 a year in 1980–83, and the Census Bureau assumed 200,000 a year.
   - INS put growth at 250,000–500,000 a year in 1981.
   - In the Jan 2011 stock, 850,000 people had entered in 1980–84 and 1.07 million in 1985–89. These are
     survivors, so they are lower bounds.

   Origin split: Mexico was 55% of the 1980 count and 69% in 1986, and Asia 6% in 1986. Any yearly
   figure for the 1980s is a model, so flag it as one.
2. **1990–2009: Warren & Warren 2013 `entered`** (816,000 in 1990, peaking at 1.39 million in 2000,
   384,000 in 2009).
   - Split 1990–1999 with the INS 2003 Chart 3 shares (Mexico 61–72%, Central America 5–9%,
     all other 23–35% of entries). Use the INS totals (550,000–970,000) as a lower variant.
   - For 2000–2009, use Pew's Mexican share: 500,000 of 850,000 a year in 2000–05 and 150,000 of 300,000
     in 2007–09. Distribute the non-Mexican part by each country's change in the Pew stock, which is
     available for 2000, 2003 and 2005–09 by country.
   - Pew's own yearly averages (850,000 / 550,000 / 300,000) are a cross-check.
3. **2010–2019: no yearly gross series is accessible here.** Warren's yearly JMHS estimates exist, but
   journals.sagepub.com and cmsny.org block this environment. Use:
   - CMS 2016 (515,000 arrivals; 62% overstays);
   - CBO's average net of −130,000 a year;
   - OHSS survivors who entered 2010+ (1.68–2.31 million in 2018–2022 stocks);
   - MPI survivors (1.74 million entered 2010–14, 2.37 million 2015–19, in the 2019 stock);
   - the yearly changes in the Pew and DHS stocks by country (these are net, not gross).

   Any yearly gross figure for 2010–2019 built from these is a model, not a published estimate, and
   should be flagged as one.
4. **2020–2025: CBO.**
   - Gross components: FY2023 3.3 million; CY2024 about 2.06 million from the four components; CY2025
     380,000.
   - Net: 2021 0.83 million, 2022 2.0 million, 2023 2.4 million, 2024 1.3 million, 2025 −0.36 million.
   - Show the illegal-only part (not encountered at the border + overstays: FY2023 1.29 million, CY2025
     310,000) separately from releases and paroles.
   - Origin: the change in the Pew stock from 2021 to 2023 by country (Venezuela +460,000, Cuba +375,000,
     Colombia +285,000, Honduras +250,000, Ukraine +175,000 …) is the best available split for the surge
     years. DHS encounter data by citizenship were not fetched.
5. **2026:** CBO projects OFN net migration of −330,000. Census projects all-status net international
   migration of 321,000 for Jul 2025–Jun 2026. Brookings gives −925,000 to +185,000 (all statuses).

## 7. What does not exist, or could not be fetched

- **Before 1970** there is no credible numeric estimate of the illegal population or of illegal arrivals.
  The Commissioner General of Immigration wrote in 1926: "We can not more than estimate the number who
  are here unlawfully", and gave no number. For the 1920s–60s, apprehensions (from FY1925) and removals
  (from FY1892) are the only yearly series. Mexican "wetback"-era flows (1940s–50s) are known only
  through apprehensions, which peaked at 1.09 million in FY1954. Historians' estimates of illegal
  Chinese entry under exclusion (1882–1943, "paper sons") were not found in fetchable form. Only the
  1956–65 Confession Program counts are included, as indicators.
- **1970s:** only the Census Bureau's 1978 range and the 1980 census count are included. The range
  summarizes earlier 1970s studies, which were not fetched directly and are not included. Massey & Singer (1995, *Demography*) yearly Mexican undocumented flows 1965–1990 are
  paywalled and not included.
- **2024–2026 stock by origin:** not published by anyone. Pew gives only qualitative or preliminary
  statements, and DHS/OHSS has published nothing after January 2022.
- **DHS yearly illegal-entry model (2000–2016)** and USBP got-aways: published only as charts, apart from
  the values quoted in the text.
- **Excluded:** the Center for Immigration Studies' CPS-based estimates (cis.org blocks this
  environment; advocacy organization), and the CMS/Warren yearly JMHS tables for 2010–2022 (blocked).
  MPI's yearly 2010–2022 series appears only as a chart in the 2025 fact sheet.
- No source gives yearly illegal arrivals by **country** before 1990 or after 2016.

## 8. Files to keep in git (whitelist in `.gitignore`)

These are hand transcriptions or page extracts that `fetch_raw.sh` cannot recreate, because the content
came from scanned or image tables, the WebFetch tool, or news pages that change. All are small (under
about 1.5 MB):

```
data/raw/archiveorg_ins_yearbooks/transcribed_ins_yb1994_tableN_oct1992.csv
data/raw/archiveorg_ins_yearbooks/transcribed_ins_yb1996_tableP_oct1996.csv
data/raw/perma_cc_unauth/transcribed_cms2019_tables2_3.csv
data/raw/mpi_factsheet_2026/mpi-unauthorized-immigrants-fact-sheet-2025-final.pdf   (WebFetch only; 1.4 MB)
data/raw/mpi_factsheet_2026/mpi-unauthorized-immigrants-fact-sheet-2025-final.txt
data/raw/bls_mlr_1986_passel/mlr_1986_09_rpt2full.pdf                               (WebFetch only; 116 KB)
data/raw/bls_mlr_1986_passel/mlr_1986_09_rpt2full.txt
data/raw/eric_pre1980/ED296133_excerpt_ch2_p19-21.txt
data/raw/cms_warren2025_secondary/royalexaminer_states_newsroom_2025-05-29.txt
data/raw/sinclair_dhs_departures_2025/page.txt
data/raw/brookings_2026_net_migration/page.txt
data/raw/pew_2026_border/usbp_sw_border_encounters_fy1960_2025.csv
data/raw/perma_cc_unauth/cms_warren2019_essay.txt
data/raw/perma_cc_unauth/mpi_profile_US_2022capture.txt
data/raw/perma_cc_unauth/yale_plosone_2018.txt
```

Everything else in `data/raw/{pew_2025_unauthorized, pew_older, archiveit_ohss_unauth, archiveit_cbo,
archiveit_dhs_border_security, perma_cc_dhs_yb2019_enforcement, archiveorg_ins_yearbooks,
archiveorg_cgi_annual_reports, perma_cc_unauth, pmc_warren_warren_2013, census_popest_nim,
crs_everycrsreport, eric_pre1980, wikipedia_unauth}` can be re-downloaded with `fetch_raw.sh`.

## 9. Rebuild

```bash
PYLIB=<dir with `pip install --target <dir> brotli`> bash scripts/unauthorized/fetch_raw.sh
python3 -I scripts/unauthorized/build_unauthorized.py   # prints row counts, 230 evidence checks, sum checks
```
