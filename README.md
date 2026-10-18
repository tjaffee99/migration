# Atlas of Arrivals

An interactive map of migration into the territory of the present-day United States, **every year from
1607 to 2026**, by country of origin, legal and illegal.

**Live site: <https://tjaffee99.github.io/migration/>** (published from `docs/` by
`.github/workflows/pages.yml`). You can also open [`docs/index.html`](docs/index.html) directly: it is one
self-contained file that loads d3 and topojson from cdnjs and the Public Sans font from Google Fonts.

## What the page shows

- **A world map of that year's arrivals, with the borders of that year.** An arrow leaves each origin, joins
  the arrows from its world region, and the merged arrow runs into the United States. Width is proportional
  to the number of people, on one scale for every year (or fitted to the chosen year). Countries, empires
  and peoples are drawn as they stood on July 1 of the year, and so are the US colonies, states and
  territories. The map zooms and pans (buttons, pinch, Ctrl/⌘ + scroll, double-click).
- **A circle for the United States**, sized by population and split into native-born residents and
  immigrants by birthplace. Zoom in on it (the US button) to read the slices.
- **The year and a one-line reading of it**: how many people arrived legally and, from 1970, an estimated
  number illegally; the share of residents born abroad; and the nearest turning point (laws, wars, famines).
- **A scrub bar** (Play, drag, arrow keys; Shift+arrow steps ten years; `#1880` in the URL opens a year).
- **A chart of arrivals by region**, in numbers by default or as shares, with illegal arrivals hatched. It
  can switch to immigrants living in the US (1850–2026). Click it to jump to a year.
- **That year's origins**, ranked, with every origin searchable. Selecting an origin highlights its arrows
  and shows its arrivals over four centuries.

Every number carries its provenance: official counts are plain; estimates carry `≈`; values between census
years are interpolated; projections and survey figures are labelled.

## Data, by era

| Years | Arrivals by origin | Immigrants living here |
|---|---|---|
| 1607–1775 | Historians' estimates by period (Menard; Tomlins 2001; Fogleman 1992, 1998), spread evenly within each period. Enslaved Africans: SlaveVoyages Trans-Atlantic Slave Trade estimates (by African embarkation region) plus documented intra-American voyages from the Caribbean. | Colonial population, Historical Statistics of the US (1975) series Z 1–19. Foreign-born share modelled from arrivals, calibrated to the 1850 census. |
| 1776–1819 | No estimate for Europeans during the war; then about 9,900 a year (Grabbe 1989 via Cohn), split by the 1820s origin mix (an assumption, flagged in the page). Slave trade as above. | Censuses 1790–1840 for population; foreign-born modelled as above. |
| 1820–1987 | Official yearly totals (DHS Yearbook Table 1). Official decade totals by country of last residence (Table 2) spread across years by iterative proportional fitting, seeded through 1957 with yearly counts for 22 country groups (Historical Statistics of the US, 1960, series C 88–114). | Census birthplace counts every 10 years from 1850 (Census Working Papers 29 and 81); state birthplace tables for 1900–1920 (1920 census) and 1950. |
| 1988–2023 | Official yearly counts: last residence (1988), country of birth (1989–2023, INS/DHS yearbooks). | Census 1990 and 2000; American Community Survey 2005–2024 (B05006, B05002). |
| 2024–2026 | FY2024: preliminary DHS counts by nationality. FY2025: projected from its first quarter. 2026: no arrival counts published yet; the page shows Census Bureau net-migration estimates instead. | Current Population Survey (2025; 2026 = January–September), scaled to the 2024 ACS. Population: Census Bureau estimates and the 2026 projection. |
| Illegal, 1970–2025 | 1980 census survivors (1970–80, a lower bound); a model between published figures (1981–89, 2010–20); Warren & Warren 2013 (1990–2009); Center for Migration Studies (2016); CBO (2021–2025). Origins split with Passel & Woodrow, INS, Pew and CMS population estimates. No credible estimate exists before 1970. | Illegal immigrant population estimates (INS, DHS, Pew, CMS) are noted in the circle's tooltip. |

Full citations are in the page's Sources list and in `data/processed/sources_*.csv`; detailed coverage,
validation results and known gaps are in:

- [`data/processed/colonial_NOTES.md`](data/processed/colonial_NOTES.md)
- [`data/processed/flows_NOTES.md`](data/processed/flows_NOTES.md)
- [`data/processed/stock_NOTES.md`](data/processed/stock_NOTES.md)
- [`data/processed/unauthorized_NOTES.md`](data/processed/unauthorized_NOTES.md) (illegal immigration)
- [`data/processed/recent_NOTES.md`](data/processed/recent_NOTES.md) (2024–2026)
- [`web/geo/GEO_NOTES.md`](web/geo/GEO_NOTES.md)
- [`web/geo/WORLD_HIST_NOTES.md`](web/geo/WORLD_HIST_NOTES.md) (historical world borders)

### Main caveats

- Before 1820 nobody counted arrivals; colonial figures are reconstructions with wide ranges, and their
  year-to-year shape is an artifact of spreading period totals.
- Official arrivals count immigrants admitted or (since the 1980s) people granted permanent residence that
  year, including people already living in the US. The 1989–1991 spike is the 1986 IRCA legalization, so
  people legalized then appear twice: once arriving illegally, once as legal residents.
- Illegal arrivals are estimates. They include people who crossed illegally (including those caught and
  released into immigration court) and visa overstays; lawful paroles at ports of entry are left out, and the
  2021–2022 CBO figures are net increases that include some parolees.
- 2025 legal arrivals are projected from one quarter; 2026 has no arrival counts yet. The 2025 American
  Community Survey (due in late October 2026) will replace the CPS figures: rerun `scripts/recent/run_all.sh`.
- Origins follow each source's own names. Empires and unions that later split (Austria-Hungary, the Soviet
  Union, Yugoslavia, Czechoslovakia) keep their historical names.
- The 1940 and 1950 censuses tabulated birthplace for white residents only.
- Arrows are schematic: they start at an anchor for each origin and merge by region before the US.
- World borders before 1886 (1816 in Europe) come from snapshots for selected years, each used until the
  next, and are approximate in the interior of Africa, the Americas and Asia. Borders after 2019 are carried
  forward. The map is cut at 90°E, through Russia, China and India.
- State-level tables are in `data/processed/` but the page draws national figures only.
- Two historical tables (1920 Vol. II ch. VI Table 10; 1950 Vol. II Tables 49 and 71) and HSUS 1960 series
  C 88–114 were transcribed from scans and kept only where they pass the printed row and column totals.

## Rebuilding

```bash
# 1. source tables (each folder has its own fetch + build scripts; raw downloads land in data/raw/, which is git-ignored)
bash scripts/stock/run_all.sh            # foreign-born stock (FETCH=1 to re-download)
python3 -I scripts/flows/build_flows.py  # arrivals 1820–2023 (fetch_archives.sh downloads raw files)
python3 -I scripts/colonial/build_flows.py && python3 -I scripts/colonial/build_slave_trade.py \
  && python3 -I scripts/colonial/build_population.py
bash scripts/recent/run_all.sh           # 2024–2026 arrivals, CPS stock, population
(cd scripts/geo && npm ci && bash build_all.sh)   # US boundaries and modern world geometry
bash scripts/geo_hist/build_all.sh       # historical world borders (download.sh fetches the sources)

# 2. harmonize into one yearly dataset (prints ~600 consistency checks)
python3 -I scripts/build/build_data.py   # -> web/data/data.json

# 3. inline app + data + geometry into the standalone page
python3 -I scripts/build/build_site.py   # -> docs/index.html
```

Layout:

```
web/src/            app source: index.html (template), app.css, app.js
web/data/data.json  harmonized yearly dataset (built)
web/geo/            historical US jurisdictions, historical world borders, modern countries (TopoJSON)
scripts/build/      origin crosswalk (origins.py), illegal-arrival model (illegal.py), dataset and page builders
scripts/{colonial,flows,stock,recent,unauthorized,geo,geo_hist}/   per-source fetch and processing scripts
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
- Historical world borders (`web/geo/world_hist.topo.json`) combine three sources, tagged per polygon by
  `src`:
  - `hb`: 1607–1885, adapted from A. Ourednik, [historical-basemaps](https://github.com/aourednik/historical-basemaps),
    **GPL-3.0**;
  - `cs*`: Europe 1816–1885 from CShapes-Europe (Cederman, Girardin, Müller-Crepon & Pengl 2025), and
    1886–2019 from CShapes 2.0 (Schvitz, Rüegger, Girardin, Cederman, Weidmann & Gleditsch 2022), ETH
    Zürich, [icr.ethz.ch/data/cshapes](https://icr.ethz.ch/data/cshapes/), **CC BY-NC-SA 4.0**
    (non-commercial, share-alike);
  - `ne`: small territories from Natural Earth (public domain).

  GPL-3.0 and CC BY-NC-SA 4.0 are not compatible with each other, so the combined file sits under both
  sets of terms. That is fine for this non-commercial page, but anyone reusing it commercially or
  relicensing it should drop or replace the `cs*` polygons (or the `hb` ones). See
  [`web/geo/WORLD_HIST_NOTES.md`](web/geo/WORLD_HIST_NOTES.md).
- Slave-trade data: SlaveVoyages (Trans-Atlantic and Intra-American Slave Trade Databases); see
  slavevoyages.org for terms of use.
- Colonial estimates are cited to their authors (Fogleman, Tomlins, Menard, Grabbe, Cohn and others) in
  `data/processed/sources_colonial.csv`.
