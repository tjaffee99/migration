# Historical world borders, 1607–2026 (`world_hist.*`)

Political borders for every year of the map, drawn under the page's own US layer. Built by
`scripts/geo_hist/` from three open datasets: historical-basemaps (1607–1885), CShapes-Europe (Europe
1816–1885) and CShapes 2.0 (1886–2026), with small gaps filled from Natural Earth.

## Files

| File | Size (gzip -9) | Contents |
|---|---|---|
| `world_hist.topo.json` | 3.25 MB (0.85 MB) | TopoJSON, one object `polities`: 2,889 polygons (one per polity *version*: 1,877 `hb`, 904 `cshapes`, 108 `ne`), 16,331 arcs, 260,155 points. Unprojected lon/lat (WGS84). Quantization 1e5 over the data bounds (grid 0.0037° × 0.0014°, about 400 m × 160 m). |
| `world_hist_years.json` | 3.4 MB (42 KB) | `{description, snapshot: "July 1", first_year: 1607, last_year: 2026, years: {"1607": [ids…], …, "2026": [ids…]}}`. These are the ids in force on July 1 of each year (178–638 a year). The list holds no information beyond `from`/`to`, so the page can also compute it. |

### Polygon properties

| key | meaning |
|---|---|
| `id` | Unique id. `hb<snapshot>_<slug>[_<first year>]` for historical-basemaps polygons (e.g. `hb1815_russian_empire_1835`). `cse_<slug>[_<first year>]` for CShapes-Europe rows (e.g. `cse_prussia_1849`). `cs_<gwcode>_<YYYYMMDD start>` for CShapes 2.0 (e.g. `cs_365_19221230`, the Soviet Union). `ne_<slug>_<YYYYMMDD>` for Natural Earth fills. |
| `name` | Display name of the polity *at that time*. Names are cleaned and dated, for example: Russian Empire → Russia (1917-03-15) → Soviet Union (1922-12-30) → Russia (1991-12-26); Ottoman Empire → Turkey (1923-10-14); Persia → Iran (1935-03-21); Qing Empire → China (1912); Congo Free State → Belgian Congo → Congo (Léopoldville) → Zaire → DR Congo; British India → India; Austrian Empire → Austria-Hungary; Prussia → North German Confederation → German Empire → Germany. |
| `sub` | The sovereign the polity was subject to, or `""` for none. For CShapes this is the owner of a colony, protectorate, mandate or occupied territory (e.g. `"United Kingdom"`, `"France"`, `"Japan"`, `"League of Nations"` for Danzig). For HB it is the cleaned SUBJECTO (e.g. `"Spain"`, `"Great Britain"`, `"Dutch Republic"`, `"Habsburg Monarchy"`), with the sovereign's name as it was at the snapshot date: England (to 1700), Great Britain (1715–1800), United Kingdom (1815+). |
| `src` | `"hb"` historical-basemaps · `"cshapes"` CShapes 2.0 or CShapes-Europe · `"ne"` Natural Earth fill. (`"cshapes+hb"` appears only if the optional `--merge-across-sources` build is used; it is not in the published file.) |
| `from`, `to` | Inclusive dates `YYYY-MM-DD` for which the map uses this polygon. **CShapes 2.0**: the exact CShapes dates, split at name changes; `to: "2026-12-31"` means "still current" (CShapes ends on 2019-12-31). **CShapes-Europe**: `From-01-01` to `To-12-31` (the dataset is yearly). **HB**: the years for which the selection rule below uses this polygon. They are written `YYYY-01-01` … `YYYY-12-31`, and the first polygon of a snapshot starts on the snapshot year (e.g. `hb1600_*` from `1600-01-01`, first shown 1607). |
| `precision` | 3 for CShapes and Natural Earth. For HB it is BORDERPRECISION: 1 approximate, 2 moderately precise, 3 fixed by international law (0/missing read as 1; the minimum when parts are merged). HB marks most polygons 3 even where the border was vague, so treat HB precision as indicative only. Of the published polygons, 645 are 1, 2 are 2 and the rest are 3. |

**The rule:** polity `p` is drawn in year `Y` if and only if `p.from <= "Y-07-01" <= p.to`. `world_hist_years.json` is exactly this list (checked by `verify_hist.mjs`). In addition, 36 CShapes polygons last only a few weeks or months and contain no July 1, for example Germany 1918-11-09 → 1919-06-27 or Poland's 1918–1921 stages. They are kept in the file for exact dates but are listed in no year.

## Year rule (which source is drawn when)

| Years | Europe | Latin America & Caribbean | South Asia | Rest of the world |
|---|---|---|---|---|
| 1607–1815 | HB snapshot | HB snapshot | HB snapshot | HB snapshot |
| 1816–1818 | **CShapes-Europe** (row valid that year) | HB 1815 | HB 1815 | HB 1815 |
| 1819–1821 | CShapes-Europe | HB 1815 | **HB 1878** | HB 1815 |
| 1822–1877 | CShapes-Europe | **HB 1878** | HB 1878 | HB 1815 |
| 1878–1879 | CShapes-Europe | HB 1878 | HB 1878 | HB 1878 |
| 1880–1885 | CShapes-Europe | HB 1880 | HB 1880 | HB 1880 |
| 1886–2019 | CShapes 2.0, polygons valid on July 1 | ← | ← | ← plus Natural Earth fills |
| 2020–2026 | CShapes 2.0 as on 2019-12-31 (no internationally recognised border change since) | ← | ← | ← |

* **HB snapshot** means the latest historical-basemaps snapshot dated on or before the year: 1600 for 1607–1649 (HB has no map for 1607), 1650 for 1650–1699, 1700 for 1700–1714, 1715 for 1715–1782, 1783 for 1783–1799, 1800 for 1800–1814 and 1815 for 1815.
* **Europe 1816–1885** uses CShapes-Europe, a yearly dataset by the same ETH team, instead of freezing the 1815 map until 1877. It shows the independence of Greece and Belgium, the unification of Italy and Germany, Romania, Serbia and Bulgaria. "Europe" is wherever CShapes-Europe has a polygon in that year: Europe including European Russia up to the Urals and the Caucasus, the Ottoman Balkans, Crete and Cyprus, Malta and Iceland. Outside that footprint the HB polygons are clipped to it. Leftover HB slivers are dropped, but HB pieces that CShapes-Europe leaves as holes are kept (Tuscany, the Thuringian states). So the Russian and Ottoman Empires each appear as two polygons with the same name: a CShapes-Europe part and an HB part (Asia; Anatolia and the Middle East).
* **Latin America from 1822**: by 1822 most of Spanish America was independent (Mexico 1821, Gran Colombia, Peru, Chile, Argentina, Brazil 1822). Showing the 1815 viceroyalties until 1877 would be wrong for 55 years. So the area south of today's US–Mexico border (Natural Earth line), the Caribbean and the tropical Pacific east of 180° use HB 1878 from 1822.
* **South Asia from 1819**: after the Third Anglo-Maratha War (1817–18) British paramountcy covered the subcontinent. The HB 1878 India, Nepal, Bhutan and Ceylon are used from 1819 instead of the 1815 Maratha map. Burma is cut off along the India–Burma line (Upper Burma was annexed only in 1885/86), and the 1815 Burma and Arakan stay. The name is "British India (East India Company)" until 1857 and "British India" (Crown rule) from 1858.
* **North America 1816–1877** keeps the 1815 shapes north of today's US–Mexico border, with dated changes:
  * Spanish Florida, split out of the HB 1815 US polygon, stays Spanish until 1821 and joins the US from 1822.
  * The New Spain north of the border is part of **Mexico** 1822–1847 (merged with the HB 1878 Mexico into one polygon) and part of the **United States** 1848–1877.
  * Russian America becomes **Alaska** (sub United States) from 1868, and British North America becomes **Canada** from 1868.
* **1886 onward** uses CShapes 2.0 (Gleditsch & Ward system membership; independent states plus colonies, protectorates, mandates and occupied territories). It is completed with:
  * the **Kingdom of Hawaii** 1886-01-01 → 1893-01-16, the Provisional Government → 1894-07-03 and the Republic of Hawaii → 1898-07-05, all on CShapes' own Hawaii polygon (CShapes starts Hawaii at annexation);
  * **Natural Earth 1:50m fills** (`src: "ne"`, 108 polygons) for territories CShapes never maps. Each has a dated sovereignty timeline in `names.py` and the geometry is the Natural Earth shape minus every CShapes polygon valid at the time, so fills never overlap CShapes. They cover Greenland (Denmark), Svalbard (Norway from 1925-08-14), Franz Josef Land and Severnaya Zemlya (USSR from 1926-04-15), the Falklands, South Georgia, the French Southern Lands, Heard Island, the Faroes, Isle of Man, Jersey, Guernsey, Andorra, Liechtenstein, Monaco, San Marino, Bermuda, the Caymans, Turks & Caicos, the British and US (Danish until 1917) Virgin Islands, Anguilla, Montserrat, Antigua, St Kitts, Dominica, St Lucia, St Vincent, Grenada (UK until independence), Aruba, Curaçao, Sint Maarten, Saint-Martin, Saint-Barthélemy, Saint-Pierre, Samoa / American Samoa, Tonga, Kiribati, Nauru, the Marshall, Caroline and Mariana Islands, Palau, Guam, the Cook Islands, Niue, Wallis & Futuna, Pitcairn, Norfolk Island, Vanuatu (New Hebrides from 1906), French Polynesia, São Tomé, Seychelles, Comoros, St Helena, Chagos, Hong Kong, Macau, Bahrain (to 1971), Kuwait (1899–1961) and Qatar (to 1916).

## Within the present-day United States

The page draws its own US layer on top. Where that layer leaves a present-day-US area outside the US, the world layer shows:

| Period | Area | Name and sovereign |
|---|---|---|
| to 1782 | French and Spanish claims | New France / Louisiana (France), Florida and New Spain (Spain), Rupert's Land (Great Britain), and many Indigenous nations (HB 1600–1715). HB 1715 has no New France, so the HB 1700 polygon fills that gap. |
| 1783–1821 | Florida and Louisiana | Spanish Florida, split from the HB US polygon (HB draws Florida as American); Louisiana (Spain) 1783–1814 |
| to 1821 | Southwest | Viceroyalty of New Spain |
| 1822–1847 | Southwest | Mexico (this includes Texas during the Texas Republic, which the US layer draws) |
| to 1867 | Alaska | Russian America (Russian Empire) |
| to 1898-07-05 | Hawaii | Kingdom of Hawaii → Provisional Government → Republic of Hawaii |

## Sources and licences

| Source | Files / URL | Licence | Used for |
|---|---|---|---|
| André Ourednik, **historical-basemaps** | https://github.com/aourednik/historical-basemaps, commit `da7a4b735ecef70aebdc9c73e409d8a2500d50f3` (2026-09-15), `geojson/world_{1600,1650,1700,1715,1783,1800,1815,1878,1880}.geojson` | **GPL-3.0** | 1607–1885 outside Europe; Europe to 1815 |
| Schvitz, Rüegger, Girardin, Cederman, Weidmann & Gleditsch, **CShapes 2.0** (ETH Zürich, International Conflict Research) | https://icr.ethz.ch/data/cshapes/ → `cshapes_2.0.tar.gz` (R package 2.0; `inst/extdata/cshapes_2_gw.topojson.xz`, the only download with the `status`/`owner` dependency fields; the `CShapes-2.0.geojson/.csv/.zip` downloads lack them). Codebook `CShapes-2.0_Codebook.pdf`, `ChangeLog.txt`. | **CC BY-NC-SA 4.0** | 1886–2026 |
| Cederman, Girardin, Müller-Crepon & Pengl, **CShapes-Europe** | https://icr.ethz.ch/data/cshapes/CShapes-Europe.geojson (yearly rows `From`/`To`, 1806–2023) | **CC BY-NC-SA 4.0**. This is the CShapes page's licence statement; the file carries no separate notice. | Europe 1816–1885 |
| **Natural Earth** 1:50m admin-0 (via world-atlas 2.0.2, `web/geo/world_50m.topo.json`) | — | Public domain (world-atlas: ISC) | US–Mexico mask line, fills, land check |

SHA-256 of the downloads (also printed by `download.sh`):
* `CShapes-Europe.geojson` `9831764d2ad17e37bc009031829265621534de097f7b3e8d6928d1a828436279`
* `cshapes_2.0.tar.gz` `6708b263224888c368aab136cdcae8a24c220bd07929af10f8bd69cf53634caa`
* `cshapes_2_gw.topojson` (unpacked) `9f73468bb56aae6a6b22bb5e56bf5f3e013b9ee17c641aba37db97bcb5c1c3bc`

### Attribution to show on the page

> Historical borders: 1607–1885 adapted from A. Ourednik, *historical-basemaps* (github.com/aourednik/historical-basemaps), GPL-3.0. Europe 1816–1885 from *CShapes-Europe* (Cederman, Girardin, Müller-Crepon & Pengl 2025); 1886–2026 from *CShapes 2.0* (Schvitz, Rüegger, Girardin, Cederman, Weidmann & Gleditsch 2022), ETH Zürich, icr.ethz.ch/data/cshapes, licensed CC BY-NC-SA 4.0 (creativecommons.org/licenses/by-nc-sa/4.0). Small territories from Natural Earth. Borders simplified, renamed and re-dated for this map.

Citations, as the CShapes page asks:
* Schvitz, Guy, Seraina Rüegger, Luc Girardin, Lars-Erik Cederman, Nils Weidmann, and Kristian Skrede Gleditsch. 2022. "Mapping the International System, 1886–2017: The CShapes 2.0 Dataset." *Journal of Conflict Resolution* 66(1): 144–61.
* Cederman, Lars-Erik, Luc Girardin, Carl Müller-Crepon, and Yannick Pengl. 2025. *Nationalism and the Transformation of the State: Border Change and Political Violence in the Modern World.* Cambridge University Press.

### Licence obligations and a caution

* **CC BY-NC-SA 4.0** (the CShapes polygons):
  * attribution, with a link to the licence and a note that the data was changed (as above);
  * **non-commercial use only**;
  * the derived polygons must be shared under the same licence.
* **GPL-3.0** (the HB polygons): keep the licence notice, and keep the "source" available. Here that means the build scripts in `scripts/geo_hist/` plus the HB commit above. Derived HB data stays GPL-3.0.
* **The two licences are generally considered incompatible for a single combined work.** GPL-3.0 forbids adding restrictions such as "non-commercial", and BY-NC-SA requires them. The build therefore keeps the sources **separable**:
  * every polygon comes from one source (`src`);
  * arcs are never shared between sources, because each source gets its own topology;
  * no polygon merges geometry from two sources (`--merge-across-sources` is off).

  Seams follow the CShapes outline: HB polygons are clipped along CShapes-Europe borders, and Natural Earth fills along CShapes borders. Whether publishing both in one file and one page counts as an aggregate is a decision for the project owner. If in doubt, split `world_hist.topo.json` by `src` into a GPL-3.0 file and a CC BY-NC-SA 4.0 file; the page logic stays the same.

## Processing (`scripts/geo_hist/`)

1. **historical-basemaps** (`build_world_hist.py`, `names.py`). Each snapshot goes through these steps:
   * geometries are made valid (shapely 2.2), antimeridian jumps are unwrapped and Antarctica is dropped;
   * every polygon *part* is named by `hb_props()`. It strips suffixes like "(UK)", fixes spellings and maps SUBJECTO to dated sovereigns. It also splits mixed multipolygons: the Caribbean parts of the UK, France and Spain become British, French and Spanish West Indies; Greenland and Iceland are split from Denmark (1815); Russian America is split from the Russian Empire. It drops the 1878/1880 Russian copies of US Aleutian islands.
   * A few dozen clear dating and labelling errors are fixed: no Inca Empire in 1600; no British Hong Kong before 1841; New Netherland/New York; Dutch Brazil and Formosa in 1700; Essequibo (Dutch) in 1783; Quebec British, not French; Louisiana Spanish in 1783/1800; the Cape British from 1800; Naples, Sicily and Sardinia Spanish in 1700; the Danish West Indies (not "US Virgin Islands") and Samoa (not "American Samoa") in 1878/80; and the Cyclades mislabelled Bulgaria in 1878/80.
   * Unnamed parts: hand fixes for Tasmania and the Faroes. Other islands under 40,000 km² join the nearest named polity within 1.5°. Larger unnamed areas (interior Africa, Arabia, Patagonia, Sakhalin…) are dropped and left as gaps.
   * Polygons are dissolved by (name, sub) and split at the antimeridian, then stitched again (see below).
   * Overlaps are resolved with smaller polygons winning: HB draws vassals and enclaves on top. Remaining overlap is under 300 km² per year, mostly Aboriginal Australian groups.
   * Gaps are filled from the neighbouring snapshot: HB 1715 gets New France from HB 1700, and HB 1600 gets Portuguese Brazil from HB 1650.
   * A polygon identical (name, sub and geometry) in consecutive snapshots becomes **one** feature spanning both, e.g. `hb1600_alawa` 1600–1877.
2. **CShapes-Europe** rows with `To >= 1816` and `From <= 1885`:
   * Overlapping rows (data errors) are resolved per year. Southern Bessarabia 1849–54 goes to Russia (Russian until the 1856 Treaty of Paris), Saxony 1816 to Saxony, not Prussia, and Savoy/Nice 1861 to France. Balaklava 1855–56 goes to Russia (the British occupation was wartime only). Elsewhere the smaller polygon wins.
   * CShapes-Europe draws the Grand Duchy of Tuscany inside the Austrian Empire, so HB 1815's Tuscany is cut out of it for 1816–1860.
   * Names follow `names.cse_props()`.
3. **CShapes 2.0** (GW TopoJSON from the R package):
   * every country-period is split at name changes;
   * `sub` is the owner's name on that date;
   * Transvaal and the Orange Free State become British colonies from the Treaty of Vereeniging (1902-05-31), where CShapes keeps them "independent" until 1910;
   * the western zones of occupied Germany 1945–49 get sub "Allied occupation (US, UK, France)".
4. **Antimeridian.** Polygons cut at ±180° (Russia/Chukotka, Fiji, Tonga…) are stitched into one piece, so the page's `rotate([90,0])` projection shows no seam along 180°. Their longitudes therefore run up to **190.3°**. d3-geo handles this on the sphere; planar tools need to wrap them.
5. **Topology** (`build_topo.mjs`):
   * one mapshaper 0.7.89 run **per source**: all of a source's polygons in one layer, so borders repeated across year-versions are stored once;
   * Visvalingam/weighted simplification `interval=0.002°` (≈200 m, about ¼ px at 8× zoom on a 1200 px map), `keep-shapes`;
   * the arc tables are merged and quantized on one 1e5 grid;
   * a d3-geo winding check runs on every polygon. Two degenerate sub-km² Aboriginal islands (`hb1600_gunibidji`, `hb1650_gunibidji`) had their rings reversed; nothing else was inverted.

   Unsimplified, the file would be about 3.5 MB, so the detail is kept nearly in full for zooming in to Italy, the Balkans or the Caribbean.

## Verification

* `verify_hist.mjs` passes:
  * the object and property schema is as described;
  * every year from 1607 to 2026 is present;
  * every listed id exists and is valid on July 1;
  * every id valid on July 1 is listed, with no duplicates;
  * no polygon has an empty geometry or an inverted ring (d3 `geoArea` < 2π for every polygon; the largest polygon is 4.3 % of the sphere).
* `verify_overlaps.py` checks the final, decoded file for sample years:

  | Year | Overlap between same-year polities | NE land covered (excl. Antarctica) |
  |---|---|---|
  | 1610–1871 | 180–290 km² (Aboriginal Australian polygons) | 69–77 % (HB leaves interior Africa, Arabia and parts of Asia unmapped) |
  | 1880 / 1885 | 5 km² | 83 % |
  | 1886 | 4 km² | 82 % |
  | 1914 | 8 km² | 96 % |
  | 1950–2026 | 6 km² | 98 % (the rest is mostly lakes and coastline differences) |

* **Renders** (d3 `geoEqualEarth().rotate([90,0])`, 1200 px, polities lightly coloured by sovereign, Natural Earth land in grey underneath) were inspected for 1610, 1700, 1776, 1815, 1850, 1880, 1890, 1914, 1925, 1950, 1990 and 2026. Further renders: gap checks (1850, 1885, 1950); Europe 1820–1886; Italy 1860/71; the Balkans 1878–2026; the Caribbean 1830/86/2026; North America 1750–1890; South Asia 1818–1886; the Bering Strait and Fiji (antimeridian); the Ural seam.
  * 1850 shows the Ottoman Empire, Austrian Empire, Russian Empire and British India (East India Company).
  * 1914 shows Austria-Hungary; 1925 the Soviet Union; 1950 a still-colonial Africa (Belgian Congo, Gold Coast, Nigeria, Kenya, French West Africa…); 2026 the modern map.
  * No antimeridian stripes appear and no ring is inverted.

  Regenerate the renders with `node render_hist.mjs OUT_DIR [years] [--zoom=lon0,lat0,lon1,lat1:tag] [--rotate=LON] [--gaps]`. The PNGs are not in the repo.

## Known issues and inaccuracies

* **Stale snapshots.** HB has no snapshot between 1815 and 1878, so outside Europe, Latin America and South Asia the 1815 map is used until 1877. That covers Africa (Algeria shown under the Dey of Algiers until 1877, no Boer republics), the Middle East, Central Asia (no Russian Turkestan), the Amur region (Qing until 1877), Australia (1815 NSW plus Aboriginal groups; no Victoria, South Australia or Queensland colonies) and New Zealand. The earlier snapshots are likewise used for up to 68 years: the 1715 map runs to 1782, so the Mughal Empire, the "Tsardom of Russia" and the uncut Polish–Lithuanian Commonwealth all appear in 1776.
* **Regional switches are approximations.** Latin America 1822–1877 shows 1878 borders. Gran Colombia (1819–31) and the Central American Federation (1823–41) appear as their successor states, and Haiti's rule over Santo Domingo (1822–44) does not appear. Uruguay appears before 1828 and Bolivia before 1825, and Paraguay and Bolivia keep their post-war extents. 1816–21 still shows the viceroyalties, though Argentina, Chile and Gran Colombia had declared independence. South Asia 1819–77 shows 1878 British India, including the Punjab (annexed 1849), Sindh (1843), Oudh (1856) and Baluchistan, all too early. Small gaps remain in Manipur and the Chittagong hills.
* **CShapes-Europe is yearly** (the state at about Jan 1 of each year), so July 1 lags changes made in the first half of a year. Examples: the 1860 Italian annexations appear in 1861, the Kingdom of Italy from 1862, and Venetia in Italy from 1867.
* **Seam 1885/1886.** Africa, Arabia and Asia jump from HB 1880 to CShapes 2.0. CShapes maps only states and their dependencies, so the pre-colonial African and Arabian polities of HB 1880 disappear in 1886 and the land shows as a gap: interior Africa until it is colonised (about 1900), Arabia until Saudi Arabia in 1932, the Yemen hinterland until 1918. Polygon shapes also change at the seam: the Ottoman Empire, Persia, Siam, and southern Africa.
* **Ural seam 1816–1885.** The Russian Empire is two same-name polygons: CShapes-Europe for European Russia and HB for Asia. A thin line therefore runs along the CShapes-Europe edge (the Urals to the Caspian). The Ottoman parts meet at the Bosporus, where no line shows. Building with `--merge-across-sources` removes the line but mixes licences (see above).
* **CShapes coding choices** (de jure, with documented exceptions):
  * Crimea is part of Russia from 2014-03-18 (CShapes 2.0), so the 2014–2026 maps show it as Russian;
  * Western Sahara is part of Morocco from 1979;
  * Kashmir follows the CShapes lines;
  * July 1, 1913 has no polity for Macedonia, Thrace and Crete (ceded by the Treaty of London on May 30, assigned by the Treaty of Bucharest on Aug 10);
  * territorial changes under 10,000 km² are not coded.
* **HB quality.** Borders are often approximate even where `precision` says 3. Some HB 1878 coastlines in the Caribbean and the Bering Sea are offset about 5–10 km from Natural Earth, which shows as a fringe if a base land layer is drawn underneath. HB polygons do not cut out lakes (CShapes cuts out large ones). Some HB polities are cultural regions rather than states ("Australian aboriginal hunter-gatherers", "Amazon hunter-gatherers", "Central Asian khanates", "Turan", "Arabia", "Islamic and Hindu states"). HB's US polygons include Oregon Country (1815), and Louisiana stays "Louisiana (Spain)" until 1814 although it was American from 1803. The US layer draws both areas.
* **Gaps.** Uncovered land should be drawn as plain land. It is 23–31 % of land in the HB years and 2–18 % in the CShapes years. A few small CShapes-Europe gaps remain: Hamburg and Lübeck (1816–70), part of Dagestan in 1816–18, and lakes.
* **Labels.** Many polities cross the projection's cut at 90°E (Russia, China, British India, Mongolia, Tibet, the Qing Empire). Their `path.centroid` falls in the middle of the map, so place labels from the largest visible part instead.

## Using it on the page

* Draw only the ids of the selected year, or filter by `from <= Y-07-01 <= to`. Arcs are shared across years (within each source), so a `topojson.mesh` over the whole object would mix years; build the mesh from the year's geometries only (`topojson.mesh(topo, {type: 'GeometryCollection', geometries: yearGeoms})`).
* Within a year, neighbouring polygons from the same source share arcs, so a mesh draws each border once. Where sources meet (the Europe/HB seam in 1816–1885, the Natural Earth fills from 1886), the border is two coincident lines.
* For the sea, use the Natural Earth land under the polities (`world.topo.json` land, or `world_50m.topo.json` when zoomed) in a neutral colour, so gaps read as "no state mapped".

## Rebuild

```bash
cd scripts/geo_hist && npm ci          # mapshaper 0.7.89, d3-geo 3.1.1, topojson-client 3.1.0, playwright-core 1.64.1
bash build_all.sh [RENDER_DIR]         # download.sh -> build_world_hist.py -> build_topo.mjs -> verify_hist.mjs
                                       # -> verify_overlaps.py [-> render_hist.mjs]
```
You need Python 3 with shapely ≥ 2 and numpy. The full build takes about 3½ minutes.
* `download.sh` fetches the CShapes files into `data/raw/cshapes/` (git-ignored) and unpacks the R package.
* It uses the historical-basemaps checkout at `$HB_DIR` (default `../aourednik/historical-basemaps`). If there is none, it clones the pinned commit into `data/raw/cshapes/historical-basemaps/`.
* Intermediate files go to `data/raw/cshapes/_build/`. `render_geojson.mjs IN.geojson OUT.png [--zoom=…] [--fix-winding]` draws any raw source file the same way, for inspection.
* `build_world_hist.py --merge-across-sources` merges each polity's CShapes-Europe and HB parts. That removes the Ural seam, but those polygons then carry `src: "cshapes+hb"`.
