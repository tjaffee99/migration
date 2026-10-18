# Atlas of Arrivals

An interactive map of migration into the territory of the present-day United States, **every year from
1607 to 2024**, by country of origin.

**Live site: <https://tjaffee99.github.io/migration/>** (published from `docs/` by
`.github/workflows/pages.yml`). You can also open [`docs/index.html`](docs/index.html) directly: it is one
self-contained file that loads d3 and topojson from cdnjs and the Public Sans font from Google Fonts.

## What the page shows

- **A world map of that year's arrivals.** An arrow runs from each origin to the United States, its width
  growing with the square root of the number of people, on one scale for every year (or fitted to the
  chosen year). Arrows are colored by region and animated toward the US; the largest origins are labelled.
  The United States is shaded as it stood on July 1 of the year, from the first colonies to fifty states.
  Arrows carrying enslaved Africans end at the landing region SlaveVoyages records; other arrows end at a
  schematic point of arrival (the main East Coast port of the era, Florida, the Mexican border, San
  Francisco or the Canadian border).
- **The year and a one-line reading of it**: how many people arrived, the largest origins, the share of US
  residents born abroad, and the nearest turning point (laws, wars, famines).
- **A 418-year timeline** of where arrivals came from, by region, which doubles as the scrubber (click or
  drag; Play runs through the years; arrow keys step a year, Shift+arrow ten). It can switch to the
  birthplaces of immigrants living in the US (1850–2024). `#1880` in the URL opens a year.
- **That year's origins**, ranked, with every origin searchable (about 200 countries a year in recent
  decades). Selecting an origin highlights its arrows and shows its arrivals over four centuries.

Every number carries its provenance: official counts are plain; estimates carry `≈` and an outlined
marker; values between census years are interpolated.

## Data, by era

| Years | Arrivals by origin | Immigrants living here |
|---|---|---|
| 1607–1775 | Historians' estimates by period (Menard; Tomlins 2001; Fogleman 1992, 1998), spread evenly within each period. Enslaved Africans: SlaveVoyages Trans-Atlantic Slave Trade estimates (by African embarkation region) plus documented intra-American voyages from the Caribbean. | Colonial population, Historical Statistics of the US (1975) series Z 1–19. |
| 1776–1819 | No estimate for Europeans during the war; then about 9,900 a year (Grabbe 1989 via Cohn), split by the 1820s origin mix (an assumption, flagged in the page). Slave trade as above. | Censuses 1790–1840 by state (Census Working Paper 56). |
| 1820–1987 | Official yearly totals (DHS Yearbook Table 1). Official decade totals by country of last residence (Table 2) spread across years by iterative proportional fitting, seeded through 1957 with yearly counts for 22 country groups (Historical Statistics of the US, 1960, series C 88–114). | Census birthplace counts every 10 years from 1850 (Census Working Papers 29 and 81); state birthplace tables for 1900–1920 (1920 census) and 1950. |
| 1988–2023 | Official yearly counts: last residence (1988), country of birth (1989–2023, INS/DHS yearbooks). FY2024 by country was not available to this build. | Census 1990 and 2000; American Community Survey 2005–2024 (B05006, B05002), national and by state. |

Full citations are in the page's Sources list and in `data/processed/sources_*.csv`; detailed coverage,
validation results and known gaps are in:

- [`data/processed/colonial_NOTES.md`](data/processed/colonial_NOTES.md)
- [`data/processed/flows_NOTES.md`](data/processed/flows_NOTES.md)
- [`data/processed/stock_NOTES.md`](data/processed/stock_NOTES.md)
- [`web/geo/GEO_NOTES.md`](web/geo/GEO_NOTES.md)

### Main caveats

- Before 1820 nobody counted arrivals; colonial figures are reconstructions with wide ranges, and their
  year-to-year shape is an artifact of spreading period totals.
- Official arrivals count immigrants admitted or (since the 1980s) people granted permanent residence that
  year, including people already living in the US. The 1989–1991 spike is the 1986 IRCA legalization.
  Unauthorized migration and temporary workers are not counted as arrivals.
- Origins follow each source's own names. Empires and unions that later split (Austria-Hungary, the Soviet
  Union, Yugoslavia, Czechoslovakia) keep their historical names.
- The 1940 and 1950 censuses tabulated birthplace for white residents only.
- Arrow endpoints are schematic, not ports of entry from the records (except for the slave trade).
- State-level tables (foreign-born by state, 1850–2024; by state and country of birth for 1900–1920, 1950,
  2000 and 2005–2024) are in `data/processed/` but the current page draws national figures only.
- Two historical tables (1920 Vol. II ch. VI Table 10; 1950 Vol. II Tables 49 and 71) and HSUS 1960 series
  C 88–114 were transcribed from scans and kept only where they pass the printed row and column totals.

## Rebuilding

```bash
# 1. source tables (each folder has its own fetch + build scripts; raw downloads land in data/raw/, which is git-ignored)
bash scripts/stock/run_all.sh            # foreign-born stock (FETCH=1 to re-download)
python3 -I scripts/flows/build_flows.py  # arrivals 1820–2023 (fetch_archives.sh downloads raw files)
python3 -I scripts/colonial/build_flows.py && python3 -I scripts/colonial/build_slave_trade.py \
  && python3 -I scripts/colonial/build_population.py
(cd scripts/geo && npm ci && bash build_all.sh)   # boundaries and world geometry

# 2. harmonize into one yearly dataset (prints ~350 consistency checks)
python3 -I scripts/build/build_data.py   # -> web/data/data.json

# 3. inline app + data + geometry into the standalone page
python3 -I scripts/build/build_site.py   # -> docs/index.html
```

Layout:

```
web/src/            app source: index.html (template), app.css, app.js
web/data/data.json  harmonized yearly dataset (built)
web/geo/            historical US jurisdictions, modern states, world countries (TopoJSON)
scripts/build/      origin crosswalk (origins.py), dataset builder, page builder
scripts/{colonial,flows,stock,geo}/   per-source fetch and processing scripts
data/processed/     cleaned source tables with sources_*.csv and *_NOTES.md
data/curated/       hand-written event timeline
docs/index.html     the built page (served by GitHub Pages)
.github/workflows/pages.yml   deploys docs/ to GitHub Pages on every push that changes it
```

## Licences and credits

- US government data (Census Bureau, DHS/INS) are public domain.
- Boundaries: Newberry Library, *Atlas of Historical County Boundaries* (CC0); us-atlas and world-atlas
  (ISC, from Census and Natural Earth); `web/geo/world_countries.csv` derives from the `world-countries`
  package and is ODbL.
- Slave-trade data: SlaveVoyages (Trans-Atlantic and Intra-American Slave Trade Databases); see
  slavevoyages.org for terms of use.
- Colonial estimates are cited to their authors (Fogleman, Tomlins, Menard, Grabbe, Cohn and others) in
  `data/processed/sources_colonial.csv`.
