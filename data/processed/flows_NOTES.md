# Immigrant arrivals (flows) to the US by origin, 1820–2023: notes

These files cover **flows**: people arriving as immigrants, or since 1892 "admitted" / "obtaining lawful permanent resident (LPR) status". They are counted by fiscal year and by origin. The latest year you can get from an archive is **FY2023**.

| file | content | rows |
|---|---|---|
| `flows_totals_1820_present.csv` | official annual national total (DHS Yearbook Table 1), FY1820–FY2023 | 204 |
| `flows_by_origin_1820_present.csv` | counts by **country/region of last residence** (Table 2 family; HSUS 1960 for 1820–1957), long format | 9,697 |
| `flows_by_birth_1989_present.csv` | counts by **country of birth** (Table 3), FY1989–FY2023, all countries; same columns as by-origin | 7,648 |
| `sources_flows.csv` | the 7 sources (`source_id`, citation, archive URL, accessed, notes) | 7 |

Scripts are in `scripts/flows/`:
- `fetch_archives.sh` downloads the raw files.
- `ocr_hsus1960.py` re-runs OCR on the 1960 Historical Statistics (HSUS) scan. It needs `tesseract`. Its output, `C88_114_tesseract_ocr.csv`, is already saved under `data/raw/hsus1960_chC/`.
- `build_flows.py` and `hsus1960.py` build every processed file and print all the validation messages quoted below.
- `warc_extract.py` and `pdf_pages.py` are helpers.

Raw inputs take 8.1 MB:
- `data/raw/archiveit_ohss/`: 5 files, each with a `.memento` file giving its exact capture URL
- `data/raw/perma_cc_dhs/`: pages 12–22 of the 2019 Yearbook PDF
- `data/raw/hsus1960_chC/`

## Where each series came from

The live sites `ohss.dhs.gov` and `www.dhs.gov` return 403 to this environment, so **every DHS or INS file is an archived copy**:
- **Archive-It (Internet Archive)** captures from 15–16 Nov 2024, part of the End-of-Term web crawl
- a **Perma.cc** capture deposited at archive.org (`perma_cc_C24E-JGKR`)

Early on, a third-party reader proxy (r.jina.ai) was briefly used to look at OHSS pages. All of that output was deleted. **No number in these files comes from it**; everything was re-sourced from the archive copies listed here.

| series | years | source_id | notes |
|---|---|---|---|
| Annual totals | 1820–2022 | `ohss_yb2022_lpr_xlsx` | unrounded |
| Annual total | 2023 | `ohss_yb2023_lpr_xlsx` | **rounded to nearest 10 by OHSS** (1,172,910) |
| Last residence, **decades** 1820s–2010s, 88 rows | 20 decades | `ohss_yb2022_lpr_xlsx` | "selected country" list with the hierarchy below |
| Last residence, **annual** | 1820–1957 | `hsus1960_C88_114` | 26 categories: 9 countries, plus "Scandinavia", "U.S.S.R. and Baltic States", "Australia and New Zealand", and "Other …" residuals. Scanned table that was OCR'd and then checked (see below) |
| Last residence, annual | **1958–1987** | — | **not obtained** (decade rows only) |
| Last residence, annual, ~60 rows | 1988–1993 | `ins_syb1996_xls` | INS-era figures, not revised |
| Last residence, annual, ~60 rows | 1994–1999 | `ins_syb1999_xls` | INS-era figures; FY1998 was revised in this edition |
| Last residence, annual, 88 rows | 2000–2009 | `dhs_yb2009_xls` | selected countries |
| Last residence, annual, 88 rows | 2010–2013 | `dhs_yb2019_pdf_perma` | selected countries (clean, born-digital PDF text) |
| Last residence, annual, **all ~205 countries** | 2014–2023 | `ohss_yb2023_lpr_xlsx` | rounded to 10; region parent assigned by lookup (see below) |
| Birth, annual, all countries | 1989–1999 | `ins_syb1999_xls` | INS grouping by region as printed |
| Birth, annual | 2000–2009 | `dhs_yb2009_xls` | |
| Birth, annual | 2010–2012 | `dhs_yb2019_pdf_perma` | |
| Birth, annual | 2013–2022 | `ohss_yb2022_lpr_xlsx` | unrounded |
| Birth, annual | 2023 | `ohss_yb2023_lpr_xlsx` | rounded to 10 |

Each period comes from exactly one source; the build script checks this. Overlapping editions were used only for cross-checks.

## Schema conventions (`flows_by_origin`, `flows_by_birth`)

- `period_start == period_end` for annual rows; decade rows are e.g. `1820,1829`.
- `origin_label` is the source wording with footnote reference digits and dot leaders removed: "Austria-Hungary2,3" becomes "Austria-Hungary". Spellings are kept as printed, e.g. INS "Columbia". For HSUS the European "Other …" columns are written with their group heading, e.g. "Other Northwestern Europe".
- `level` takes these values:
  - `total`
  - `region`
  - `subregion`: Caribbean, Central America and South America under America; also multi-country aggregates with no detail, such as Scandinavia
  - `country`
  - `residual`: "Other …", "Not specified", "All other countries", "Unknown"
  - `subcountry` (extra): Austria and Hungary under "Austria-Hungary", Norway and Sweden under "Norway-Sweden". The source prints these as components of a combined country row. **Never add `subcountry` rows to `country` rows.**
- **Summing rule:** in every period, `country` + `residual` rows add up to the `total`. The script verifies this for all 194 periods with 0 mismatches, apart from rounding and withheld cells (see Validation). Where a region or aggregate has no breakdown in the source, a residual child is added with `basis=derived_region_without_detail` and the same count. This covers Africa and Oceania in the INS tables, and Africa, Scandinavia, U.S.S.R. & Baltic and Australia & NZ in HSUS. Use `origin_label` "X (no country detail in source)" for these.
- `basis` takes these values:
  - `reported_decade`
  - `reported_annual`
  - `reported_annual_ocr_reconciled` (HSUS cells where the kept value differs from the Tesseract reading; 510 cells)
  - `derived_region_without_detail`
  - `derived_unvalidated_remainder` (HSUS, see below)
- `count` is blank for cells DHS withheld for disclosure ("D"; 32 cells, all in the birth file). Source "-" (zero / not reported) is written as 0.
- Region parents in the all-country tables need a lookup, because DHS lists countries alphabetically. These tables are FY2023 Table 2, and the Table 3 birth tables from 2000 onward.
  - The lookup comes from the region grouping printed in INS 1999 Table 3, plus a few later names.
  - One change was needed: Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan and Uzbekistan go under **Asia**, not Europe as in INS 1999. Making exactly this change closes the DHS Asia/Europe gap in every year.
  - Children now match region totals within rounding. The remaining gaps are 30 or less, from "All other countries" (parent = Total) and withheld cells.
- Region labels differ between eras, as in the sources:
  - Selected-country tables (decades, 1988–2013): "America", containing Canada and Newfoundland, Mexico, Caribbean, Central America, South America and Other America.
  - All-country tables (2014+, birth 2000+): "North America", including the Caribbean and Central America, and a separate "South America".
  - HSUS: "America" and "Australasia".

## Validation results

- **Well-known values:**
  - FY1907 total = **1,285,349**, close to the expected 1.29 million.
  - FY1991 total = **1,826,595**, close to the expected 1.83 million; Mexico 1991 = 947,923 (INS).
  - Germany 1880–1889 = **1,445,181**, close to the expected 1.45 million. The 10 HSUS annual Germany values for 1880–89 also add up exactly to 1,445,181.
- **Table 1 cross-checks:** the 2019 PDF matches the FY2022 workbook in all 199 years (1820–2019). The 2009 xls matches in all 189 years. The rounded FY2023 workbook differs by at most 5 in every year.
- **Decade table:** the FY2022 workbook and the 2019 PDF agree in all 1,653 cells (1820s–2000s). In every decade, countries + residuals = Total (0 mismatches). Two parent/child gaps come from the sources' own footnotes:
  - Austria + Hungary < Austria-Hungary in the 1860s (−192), 1890s (−62,491) and 1900s (−783,393), because they were "not reported separately for all years".
  - Norway and Sweden are 0 before 1870 (not reported separately).
  - The Table 2 decade totals equal the sums of Table 1 years.
- **Annual selected tables (1988–2013):** 0 mismatches between leaf sums and totals.
  - INS-era totals differ from today's revised DHS Table 1: 1990 +611, 1991 +572, 1999 +1,781.
  - The rounded all-country table (2014–2023) and the unrounded selected tables differ by at most 5 for the same countries, in 2014, 2019 and 2022.
  - Leaf sums in the rounded tables differ from the total by at most 170, because of rounding.
- **Birth tables:**
  - INS 1999 Table 3, FY1990: Europe's countries add up to 50 less than the printed Europe total, and so does the grand total. This is in the source.
  - DHS tables: leaf sums are 0–9 below the total because of withheld "D" cells.
- **HSUS 1960 (annual 1820–1957):**
  - The scan's own text layer is noisy, so digits were read twice: Tesseract column by column, and the PDF text layer. Candidate values are those readings plus 3↔8 variants; Tesseract systematically reads this typeface's 3 as 8.
  - The kept values satisfy the table's five accounting identities:
    - Europe = its 11 columns
    - Asia = its 4 columns
    - America = its 3 columns
    - Australasia = its 2 columns
    - All = the regions + Africa + "All other countries"
  - The "All countries" total equals DHS Table 1 in all 138 years.
  - **86 years are fully reconciled.** In **52 years** only the regional groups whose identity held (usually Europe) are kept. The unvalidated rest is a single row, "Remainder not validated from OCR…", with `basis=derived_unvalidated_remainder`. Europe detail is present in 129 of 138 years.
  - Independent check against the DHS decade table: annual sums equal the DHS decade figure **exactly** for:
    - Germany, 1870s–1920s
    - Italy, 1870s–1940s
    - Ireland and Great Britain/"United Kingdom", 1870s–1910s
    - Poland, 1870s–1910s (Poland is 0 in the 1900s–1910s in both sources)
  - In total, 42 of 72 decade comparisons match exactly and 57 are within 1%. The non-exact cases come from definitions: DHS moved Northern Ireland to the UK from 1925, HSUS puts Austria in Germany for 1938–45, and DHS regrouped Europe/America.

## Caveats on definitions

- **Last residence vs birth.** Before 1906 the "country" is the country the person came from. From 1906 it is the country of last permanent residence, except FY1980–83, which INS reported by birth. Table 3 is country of birth. The two differ: for example, many people born in Asia had their last residence in Europe or the Americas. Do not mix them in one series.
- **What is counted:**
  - 1820–1867: alien *passengers* arrived at seaports.
  - 1868–1891 and 1895–1897: immigrant alien arrivals.
  - 1892–1894 and 1898 onward: immigrants admitted.
  - Today the series counts persons *obtaining LPR status*, which includes people already in the US who adjust status.
  - Cabin-class arrivals were not counted in 1892–1903.
  - Land arrivals were not fully counted until 1908, so Canada and Mexico are undercounted. There are no Canada or Mexico data for 1886–1893.
  - Before 1867, figures exclude returning citizens, and data quality is weak: clerks recorded the port of embarkation, not nationality, and the "Not specified" share is large (e.g. 83,495 in the 1830s).
- **Fiscal years:**
  - Years end Sep 30 for 1820–1831 and 1844–1849, and Dec 31 for 1833–1842 and 1851–1867.
  - 1832 is 15 months, 1843 is 9 months, 1850 is 15 months, and 1868 is 6 months.
  - Years end Jun 30 for 1869–1975.
  - **FY1976 is 15 months** (Jul 1975–Sep 1976).
  - Years end Sep 30 from 1977.
  - Each total row's `note` gives this.
- **IRCA legalization:** the 1986 amendments legalized ~2.7 million people, counted as new LPRs mainly in **FY1989–1991**, peaking at 1,826,595 in 1991, with a tail to about 1994. Mexico alone was 947,923 in 1991. This is not new arrival flow.
- **COVID:** FY2020–21 are low (707,362 and 740,002) because of processing slowdowns. "Unknown" country of last residence jumps to 114,600 in FY2022 and 88,350 in FY2023.
- **Changing country definitions** (from the DHS footnotes):
  - Austria and Hungary were not separated in all years of the 1860s, 1890s and 1900s.
  - Poland is included in Austria, Germany, Hungary and Russia from 1899 to 1919, which is why Poland = 0 in the 1900s and 1910s.
  - "Russia" means the Russian Empire to 1920 and the USSR from 1920 to 1990. For 1991–1999 it means Russia plus the other ex-Soviet republics (INS "Soviet Union"); from 2000 it means Russia only.
  - Finland is in Russia from 1899 to 1919.
  - Yugoslavia includes all its successor states; Czechoslovakia includes Czechia and Slovakia.
  - Northern Ireland is in Ireland before 1925.
  - Norway and Sweden are combined before 1861.
  - Bulgaria includes Serbia and Montenegro (1899–1919).
  - Syria is in Turkey from 1886 to 1923.
  - New Zealand is in Australia from 1892 to 1924; Jamaica is in the British West Indies (1892–1952); Cape Verde is in Portugal (1892–1952).
  - "Canada and Newfoundland" means British North America before 1920.
  - HSUS-specific groupings:
    - "Great Britain" excludes Ireland; "Ireland" is Eire and Northern Ireland.
    - Scandinavia = Norway, Sweden, Denmark and Iceland.
    - Other Northwestern Europe = the Netherlands, Belgium, Luxembourg, Switzerland and France.
    - Other Central Europe = Czechoslovakia, Yugoslavia, Hungary and Austria.
    - U.S.S.R. & Baltic = the USSR in Europe, Latvia, Estonia, Lithuania and Finland.
    - Other Eastern Europe = Romania, Bulgaria and Turkey in Europe.
    - Other Southern Europe = Spain, Portugal, Greece and Europe n.e.c.
    - Germany includes Austria in 1938–45.
    - From 1934 to 1951 the Philippines are in "All other countries".
- **Rounding:** from the FY2023 edition onward, OHSS rounds every cell to the nearest 10, including the historical years. For that reason unrounded values are used wherever they exist (FY2022 edition or earlier).

## What could NOT be obtained

- **FY2024.** OHSS published the FY2024 LPR workbook in June 2026, but no archived copy exists: the Archive-It captures predate it, and perma.cc has none. The latest year is therefore FY2023, and its figures are rounded.
- **Annual counts by country of last residence for FY1958–1987.** Only decades are available. The INS Annual Reports and Statistical Yearbooks for those years exist on archive.org only as microfilm OCR; they were not attempted.
- **The HSUS 1975 edition (series C 89–119, 1820–1970, more countries).** Its text layer is unusable, so the 1960 edition (C 88–114, to 1957, coarser groups) was used instead.
- **Unrounded country detail for 2023.**
- **All-country detail by last residence before 2014.** Earlier editions publish only "selected countries"; use the birth file for full country detail from 1989.
- **Country-of-birth tables before 1989.**
