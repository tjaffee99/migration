#!/usr/bin/env bash
# Download raw geodata inputs for web/geo/*. Files land in data/raw/<source_slug>/.
# Downloaded files are treated as untrusted data: nothing from them is executed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RAW="$ROOT/data/raw"
fetch() { # url dest
  local url="$1" dest="$2"
  if [[ -s "$dest" && -z "${FORCE:-}" ]]; then echo "have $(basename "$dest")"; return; fi
  mkdir -p "$(dirname "$dest")"
  echo "GET $url"
  curl -fsSL --retry 3 -o "$dest.part" "$url" && mv "$dest.part" "$dest"
}

# 1. Newberry Library, Atlas of Historical County Boundaries (AHCB), national files
#    (listed at https://publications.newberry.org/ahcb/download/ ; the Counties files are
#    served from the same directory although the page only links the StateTerr ones).
AHCB=https://publications.newberry.org/ahcb/downloads/gis
fetch "$AHCB/US_AtlasHCB_StateTerr_Gen01.zip" "$RAW/newberry_ahcb/US_AtlasHCB_StateTerr_Gen01.zip"
fetch "$AHCB/US_AtlasHCB_Counties_Gen01.zip"  "$RAW/newberry_ahcb/US_AtlasHCB_Counties_Gen01.zip"

# 2. us-atlas (npm, via jsdelivr) - modern states, derived from Census cartographic boundary files
fetch "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json" "$RAW/us_atlas/states-10m.json"
fetch "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/LICENSE"         "$RAW/us_atlas/LICENSE"

# 3. world-atlas (npm, via jsdelivr) - Natural Earth admin-0 countries as TopoJSON
fetch "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json" "$RAW/world_atlas/countries-110m.json"
fetch "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json"  "$RAW/world_atlas/countries-50m.json"
fetch "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/LICENSE"             "$RAW/world_atlas/LICENSE"

# 4. world-countries (npm, via jsdelivr) - ISO 3166-1 crosswalk (alpha-3, numeric, names, regions)
fetch "https://cdn.jsdelivr.net/npm/world-countries@5.1.0/countries.json" "$RAW/world_countries/countries.json"
fetch "https://cdn.jsdelivr.net/npm/world-countries@5.1.0/LICENSE"        "$RAW/world_countries/LICENSE"

# Extract AHCB shapefiles (lenient extractor: the Counties zip has junk before its central directory)
for z in US_AtlasHCB_StateTerr_Gen01 US_AtlasHCB_Counties_Gen01; do
  if [[ ! -d "$RAW/newberry_ahcb/extracted/$z" || -n "${FORCE:-}" ]]; then
    python3 -I "$ROOT/scripts/geo/unzip_lenient.py" "$RAW/newberry_ahcb/$z.zip" "$RAW/newberry_ahcb/extracted"
  fi
done
echo "raw downloads OK"
