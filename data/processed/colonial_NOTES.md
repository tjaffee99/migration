# Colonial and early-national slice, 1607–1819: notes

Files:

| file | rows | content |
|---|---|---|
| `flows_colonial_by_origin.csv` | 163 | Arrivals of Europeans and other non-African migrants by origin group and period, 1607–1819, plus Fogleman's status and African aggregates for reference |
| `slave_trade_arrivals.csv` | 2,401 | Enslaved Africans landed in what is now the US. Annual, by embarkation region × disembarkation region. Has 605 `tast_estimates` rows and 1,796 `intra_american` rows |
| `population_1610_1840.csv` | 359 | Population by colony or state: 198 colonial rows (1610–1780, by decade) and 161 census rows (1790–1840) |
| `sources_colonial.csv` | 27 | Citations. Every `source_id` used in the three files is listed here (an assertion in `write_sources.py` checks this) |

Scripts are in `scripts/colonial/`. Run them in this order: `fetch_slavevoyages.py`, `build_slave_trade.py`, `build_population.py`, `build_flows.py`, `write_sources.py`. Raw downloads are in `data/raw/<slug>/`. Every number in the CSVs traces back to one of those files.

## 1. `flows_colonial_by_origin.csv`: how to use it

Each row's `note` starts with a series tag. **Use the tag before you sum anything.**

* `series=primary` (83 rows): a single best-estimate series with no overlaps. Summing these rows gives total European and other non-African arrivals, about 874,600 for 1607–1819.
* `series=subset` (37 rows): regional or sub-group detail that is already counted inside a primary row. Examples: Delaware Valley arrivals, Philadelphia arrivals, convicts by origin, Germans in 1815–19, Acadians in 1785. Use these rows for destination or origin detail, not for totals.
* `series=alt` (43 rows): competing estimates for a period or group that a primary row already covers. They exist to show uncertainty. They include Fogleman's African and status totals, and the primary series for Africans is `slave_trade_arrivals.csv`.

`status` is one of: `mixed` (free, indentured and convict together, which is what most sources give), `free`, `indentured`, `convict`, `enslaved`, `unknown`. Where a source gives a servant share, the note records it.

### Primary series by period

| period | origin detail | source | total |
|---|---|---|---|
| 1607–1700 | By destination. Chesapeake by colony and decade (Maryland and Virginia: Menard's series as tabulated in Tomlins 2001 Table 1). New England: 21,000 in 1630–42 plus 3,000 in 1643–99. Delaware Valley British, by decade 1670s–90s. Lower South 8,000. New Netherland 6,000. Plus Fogleman's 1,500 "mostly Swedish and German" and 2,300 convicts and prisoners | Tomlins (2001), Fogleman | **165,100** (Fogleman's 17th-century European total is 165,200) |
| 1700–1775 | By decade (1700–09 … 1770–75) for Germans, Northern Irish (Ulster), Southern Irish, Scots, English, Welsh and Other Europeans | Fogleman (1992 JIH) via Tomlins (2001) Table A1 | **307,400** |
| 1778–1790 | Spanish Louisiana: 2,100 Canary Islanders (1778–83) and about 4,000 Acadians (range 3,000–4,000) | Wikipedia | 6,100 |
| 1780–1819 | One aggregate row ("All European origins") | Cohn, citing Grabbe (1989): 9,900 a year × 40 years | **396,000** (low 250,000) |

Derived values are marked `DERIVED` in the note. There are four kinds:

* The Chesapeake decades 1681–90 and 1691–1700 (13,300 and 13,900). The source gives only servant migrants; I divided by Tomlins' stated 80% servant share. Horn's 13,000–14,000 per decade supplies low and high.
* New England 1643–99 = 24,000 − 21,000.
* Cohn's average annual figures multiplied by the number of years.
* Fogleman's 1776–1809 total, obtained by subtraction.

### Choices and reasons

* **1700–1775: Fogleman's decade × group table.** It is the standard disaggregated estimate, and Tomlins calls it "the best currently available". It reconciles exactly: 84.5k + 66.1k + 42.5k + 35.3k + 44.1k + 29.0k + 5.9k = 307.4k Europeans. Every row and column total in Tomlins' reproduction was checked by script. The final decade is 1770–1775, even though Tomlins labels it "decade ending 1779".
* **17th century: Tomlins' regional synthesis** (built from Menard, Gemery, Fischer, van den Boogaart and others). It gives destinations and a decade series for the Chesapeake. Fogleman's 17th-century estimate is by status only, not by ethnicity.
  * Origin labels follow the sources: "British", "English", "European (mostly British)" and "New Netherland colonists (Dutch and other Europeans)".
  * The decade ending 1700 overlaps Fogleman's 1700 start by one year.
* **1780/83–1819: no origin breakdown was obtainable.** Grabbe's 1989 PAPS article is paywalled.
  * I used Cohn's Grabbe-based average of 9,900 a year as the point estimate.
  * The low bound is the official Treasury/Bromwell figure of 250,000 for 1783–1819, which is also an `alt` row.
  * German-speaking subsets: 8,031 to Pennsylvania in 1800–08; about 15,000 Germans in 1815–20, or 13,500 German and Swiss passengers.
* **Gaps in the primary series:**
  * 1776–1779 (wartime) has no estimate.
  * Spanish Florida and New Mexico have no numbers.
  * French Louisiana before 1763 has only a population stock (550 in 1717), which is an `alt` row and should not be used as a flow.

### Ranges and uncertainty (from Tomlins' review, recorded as `alt` rows with low and high)

* **Germans 1700–75:** 84,500 (Fogleman) to 120,000. Wokeck (1999) gives 111,000 to all of North America.
* **Irish:** 65,000–108,600. Fogleman's 108,600 is described as a "well-documented upper bound". Purvis gives 114,000 for Ulster alone. Bailyn and Purvis together imply 150,000–250,000.
* **Scots:** 35,300 (Fogleman) against Purvis's 62,500, which Smout, Landsman and Devine accept. Bailyn gives 40,000 for 1760–75 alone, and Tomlins suggests adding about 30,000.
* **English and Welsh:** 73,100 (Fogleman), possibly 15,000 more. Canny gives 50,000 English including convicts. A Purvis-style ratio would put the Welsh at about 45,000 rather than 29,000.
* **All Europeans 1700–1780:** 307,000–350,000. Global estimates by Potter, Gemery and Galenson run 340,000–370,000.
* **17th century:**
  * Chesapeake: Menard's 123,000 (range 99,000–146,000). Horn gives about 120,000, and in his Virtual Jamestown essay 130,000. Tomlins uses 108,000.
  * Gemery: 155,000 British in 1630–1700.
  * Tomlins' all-region total: 161,000, against Fogleman's 165,200.
* **Through 1780:** total European migration was 470,000–515,000, including about 54,500 involuntary migrants.
* **Convicts:**
  * Fogleman: 52,200 convicts and prisoners in 1700–75.
  * Ekirch: about 36,000 in 1718–75.
  * Vaver: about 34,000 English plus more than 16,000 from Ireland, about 50,000 in total.

### Conflicts and source quality

* **Fogleman 1998 Table 1 (by status)** comes only from a UMBC teaching handout, which reproduces the 1607–1699 and 1700–1775 rows:
  * 1700–75: 278,400 slaves + 52,200 convicts + 103,600 servants + 151,600 free = **585,800**, of which 278,400 are Africans. This matches the sanity target.
  * 1607–1699 totals 198,400. The same total and the 33,200 slaves are confirmed by Nowrasteh's quotation.
  * One search summary quoted 96,600 servants for 1700–75. That figure is the 1607–99 servant number; the handout gives 103,600.
* **Fogleman's group figures** were cross-checked against a genealogy blog (germanna.org) that quotes *Hopeful Journeys*: the numbers agree, including Welsh 29,000. The blog's stated total of "585,000" is an arithmetic slip; the figures sum to 585,800.
* **Fogleman's 1776–1809 total** is derived: 973,600 for 1700–1809 (quoted by Nowrasteh) minus 585,800 = 387,800, including slaves. The 1776–1809 and 1810–1819 rows of Fogleman's Table 1 were **not** obtained. The JAH article is behind a paywall, and the Harvard working-paper page returned 403.
* **The Meyerink & Szucs (1997) "immigrants before 1790" table** (`alt`) comes from Wikipedia and was not verified against the book. It is the only fetched source for small groups across the whole colonial period: Netherlands 6,000, France 3,000, Jews 1,000, Sweden 500. Its Africa figure (360,000) is not comparable with TAST's direct-arrival estimates.
* **Tomlins Table 6, 1770s:** the printed total is 15,902 but the columns sum to 15,932. Recorded in the note.
* **Small-group figures from Wikipedia** are anecdotal. They are kept as `subset` or `alt`, except the Louisiana rows, which are primary because Louisiana was outside the Fogleman and Cohn coverage:
  * New Sweden: about 600 Swedes and Finns.
  * Jews: 23 arrivals at New Amsterdam in 1654.
  * Huguenots: 390 settlers at Manakin Town in 1700.
  * Isleños: 2,100 to Louisiana. The other Isleño groups are given only as families: 16 families to San Antonio in 1731 and 154 to Florida in 1757–59. Those were not converted to people.
  * Acadians: about 4,000, or 3,000 on the Acadians page. The end year of their arrivals is not stated; 1790 is a placeholder.

### Annual map

None of these sources gives annual European flows before 1820. To fill annual cells, a period total has to be spread across its years. There are two simple options:

* Spread it uniformly within each decade.
* Shape it with the TAST annual profile, as Nowrasteh did. That ties European timing to the slave trade, so it is a modelling choice and should be disclosed.

## 2. `slave_trade_arrivals.csv`

* **`basis=tast_estimates`** (the main series). Data come from the SlaveVoyages Trans-Atlantic **Estimates** database, queried through the site's own public API (`/api/assessment/crosstabs/`, authenticated with the front-end token served in `runtime-config.js`). The full request payloads are saved next to each response in `data/raw/slavevoyages/api/`.
  * Values are disembarked captives by year, African embarkation region (8 regions) and specific disembarkation region within "Mainland North America": Carolinas / Georgia, Chesapeake, Gulf states, Northern U.S., U.S.A. unspecified. Zero cells are dropped.
  * Coverage runs from 1628 to 1860. The estimates have no 1619 entry; the 1619 "20 and odd" landing appears in the intra-American data (29 people from "Other: Americas").
  * **Total: 388,744.** This matches the target of about 390,000. Every row, column and the independent year × region query reconcile by assertion.
  * By region: Carolinas/Georgia 210,481; Chesapeake 127,665; Northern U.S. 26,951; Gulf states 21,785; unspecified 1,862.
  * By embarkation region: West Central Africa 92,192; Senegambia 92,028; Bight of Biafra 64,781; Gold Coast 56,245; Sierra Leone 44,896; Windward Coast 21,784; Bight of Benin 9,228; South-east Africa 7,590.
  * By period: up to 1699, 14,143; 1700–1775, 265,799; 1776–1807, 101,750; 1808 and later (illegal), 7,052.
  * The estimates assign captives to the year of a representative voyage, so annual values are lumpy. Smoothing over 5 or 10 years is advisable on a map.
  * Spanish Florida has no region of its own in the Estimates' list of specific disembarkation regions. Louisiana arrivals fall under "Gulf states".
* **`basis=intra_american`**: the SlaveVoyages **Intra-American** voyages database (dataset 1). These are documented voyages only, so they give a lower bound, not an estimate.
  * Values are imputed captives disembarked by arrival year, region of purchase (written as "Broad: Principal", e.g. "Caribbean: Jamaica") and principal region of disembarkation (state level).
  * Canada was excluded. Two voyage groups with unknown arrival year (54 people, New York and South Carolina) were skipped.
  * Total: 133,269, of which 133,215 are in the CSV (the 54 unknown-year captives are not). Of the rows in the CSV, 47,751 were purchased **outside** mainland North America. For arrivals up to 1807 the outside-purchased total is 45,851, mostly from the Caribbean: 30,013 up to 1775 and 12,036 in 1776–1807.
  * Rows with `embark_region` starting "Mainland North America:" (85,464 people, mostly after 1808 to the Gulf coast and Texas) are the **domestic coastwise trade**. They are internal US migration, not immigration; exclude them from immigration flows.
  * The intra-American and trans-Atlantic series do not overlap: they are different voyages. Re-exports from the Caribbean are additional to direct African arrivals. Even so, treat the intra-American series as incomplete.
  * Cross-check: HSUS 1975 series Z 155–164 (Charleston imports by origin) gives 11,220 slaves from Caribbean ports in 1706–1775. For the same years the intra-American data give 12,540 from the Caribbean into South Carolina, which is consistent. The HSUS series itself was not transcribed.
* **Context:**
  * The trans-Atlantic **voyages** database (imputed, documented voyages) gives 306,322 for mainland North America, against 388,744 in the Estimates. Only totals were saved as a cross-check, and these rows were not added.
  * Fogleman's African totals (33,200 in 1607–99 and 278,400 in 1700–75) are higher than TAST direct arrivals (14,143 and 265,799). That is consistent with his inclusion of arrivals via the Caribbean.
  * Tomlins gives a range of 285,000–310,000 Africans to the mainland through 1780.

## 3. `population_1610_1840.csv`

* **1610–1780 (by decade, `hsus1975_Z1_19`):** total population and the Black ("Negro") population by colony, from HSUS Series Z 1–19. The census.gov PDF is a scanned image, so:
  * Totals were machine-read from Wikipedia's reproduction.
  * The Negro panel was transcribed by hand from the page image.
  * Both panels are verified by script. Every year's colony sum equals the printed HSUS Total row: 2,780,369 in 1780, 250,888 in 1700, and so on. Every Negro column sums to its printed total: 575,420 in 1780, 27,817 in 1700, and so on.
  * One Wikipedia cell is wrong and was corrected to the scan: New Hampshire 1700 is **4,958**, not 4,658. Wikipedia's Total row also has typos for 1630, 1640, 1650 and 1700.
  * 1620 has only Plymouth (102) and Virginia (2,200, which includes 20 Black people). 1610 has only Virginia (350).
  * The Rhode Island and Connecticut Black figures for 1780 include some Indians (HSUS footnote).
  * `enslaved` is blank for colonial rows. HSUS gives Black, not slave, population.
  * HSUS warns that these figures are estimates that likely undercount enslaved people, and that they exclude Native Americans outside colonial jurisdiction.
* **1790–1840 (`census_twps0056_appA`):** Census Working Paper 56, Appendix A (tables A-26 to A-21). Values are total, Black, and slave population by state.
  * Free Black = `black` − `enslaved`. This identity holds for every row by assertion.
  * WP56 uses **current state boundaries.** Virginia excludes West Virginia; West Virginia, Maine (before 1820), Kentucky (1790) and similar areas appear as separate units.
  * The "as published" rows (old Virginia, Northwest Territory, Indiana and Mississippi Territories, and the District of Columbia including the area retroceded to Virginia) were left out to avoid double counting.
  * The 1790 sum is **3,929,214**, which matches the target. Later sums: 1800, 5,308,483; 1810, 7,239,881; 1820, 9,638,453; 1830, 12,860,702; 1840, 17,063,353.
  * The 1800 state sum is 3,757 higher than WP56's own US total (5,304,726). The difference is the Michigan area (3,757), which WP56 lists as a state row but leaves out of its regional and US totals. The state sum equals the published 1800 total of 5,308,483, which appears in HSUS 1789–1945, ch. B.
* **`unit_type`:**
  * `colony` for 1610–1770.
  * `state` for the original 13 from 1780 on, and for later states from their admission year.
  * `territory` for any area that was not a state at that date. This is a catch-all: it covers organized territories, but also districts of a state (Maine before 1820, Kentucky in 1790, West Virginia), Vermont before 1791, Plymouth-era sub-areas, and the District of Columbia. Unit names are those used in the source.

## 4. Not obtained (time-boxed)

* **Fogleman (1992 JIH; 1998 JAH):** the original tables are behind JSTOR. The 1998 Table 1 rows for 1776–1809 and 1810–1819 are missing, and so is the 1992 decade series for Africans; TAST is used for Africans instead.
* **Grabbe (1989 PAPS):** the annual and by-origin estimates for 1783–1819 (British, Irish, German, French) were not obtained; only Cohn's period average is used. Grabbe's 2017 American Studies Journal article presents the series as graphs only.
* **Gemery, Galenson, McCusker & Menard, Horn (1994):** no direct copies. Their numbers are used only as reported by Tomlins and in Horn's web essay.
* **Not found:** Spanish Florida and New Mexico settler flows; French Louisiana European immigration (only the 1717 stock); Saint-Domingue refugees to Louisiana and the US (c.1791–1809); and a reliable aggregate Huguenot inflow.
* **Not transcribed:** the HSUS 1975 slave-import series Z 133–164 (New York 1701–64, Charleston 1706–75, origins 1768–72). The scan is image-only; only the Charleston totals were used, as a cross-check.
* **Blocked:** web.archive.org and the Harvard Atlantic History working-paper page (403). The Cato Institute pages were also blocked (Incapsula).
