# Atlas of Arrivals

An interactive map of migration into the territory of the present-day United States, **every year from
1607 to 2024**, by country of origin.

Open **[`docs/index.html`](docs/index.html)** in a browser (it is one self-contained file; it loads d3 and
topojson from cdnjs and fonts from Google Fonts). With GitHub Pages pointed at `/docs`, it is served as is.

## What the page shows

- **Year slider and Play** (1607–2024, arrow keys step a year, Shift+arrow ten years; `#1880` in the URL
  opens a year).
- **US map** with the colonies, states and territories as they stood on July 1 of the chosen year, and
  areas then held by other powers (Spanish Florida, New France, Mexico, Russian America, the Kingdom of
  Hawaii…). Three views:
  - *Share born abroad* per state (from 1850), labelled with each state's largest birthplace where state
    birthplace tables exist (1900–1950, 2000–2024);
  - *Born in…* a chosen country, by state;
  - *Population* (colonial estimates from 1610, censuses from 1790), shown automatically before 1850.
  - Yellow circles mark enslaved Africans landed that year, by landing region.
- **Arrivals panel**: that year's arrivals with the mix by region and a ranked, searchable list of every
  origin (about 200 countries a year in recent decades). Selecting an origin shows its arrivals over four
  centuries and switches the map to that origin.
- **Composition over time**: stacked shares (or numbers) by region, for arrivals each year (1607–2024) or
  for immigrants living in the US (1850–2024). Click or drag to move through time.
- **World map** of where that year's arrivals came from, and a timeline of 41 turning points
  (laws, wars, famines).

Every number carries its provenance in the page: official counts are plain; estimates carry `≈` and an
outlined marker; interpolated values say which years they sit between.

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
- State-by-birthplace data are missing for 1850–1890, 1930–1940 and 1960–1990 (they exist only in scanned
  census volumes or behind NHGIS); the page interpolates a state's mix only across gaps of 30 years or less.
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
docs/index.html     the built page
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
