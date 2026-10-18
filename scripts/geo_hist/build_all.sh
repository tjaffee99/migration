#!/usr/bin/env bash
# Regenerate web/geo/world_hist.topo.json and web/geo/world_hist_years.json.
#   cd scripts/geo_hist && npm ci && bash build_all.sh [RENDER_DIR]
# Needs python3 with shapely>=2 and numpy, node>=18. HB_DIR overrides the historical-basemaps checkout.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$HERE"
bash download.sh
HB_DIR="${HB_DIR:-$REPO/../aourednik/historical-basemaps}"
[[ -d "$HB_DIR/geojson" ]] || HB_DIR="$REPO/data/raw/cshapes/historical-basemaps"
WORK="$REPO/data/raw/cshapes/_build"
python3 -I build_world_hist.py --hb-dir "$HB_DIR/geojson" --cshapes-dir "$REPO/data/raw/cshapes" \
  --ne-topo "$REPO/web/geo/world_50m.topo.json" --work "$WORK" --years-out "$REPO/web/geo/world_hist_years.json"
node build_topo.mjs "$WORK" "$REPO/web/geo/world_hist.topo.json" --interval=0.002 --quantization=100000
node verify_hist.mjs
python3 -I verify_overlaps.py
if [[ -n "${1:-}" ]]; then
  node render_hist.mjs "$1"                                          # 1610 ... 2026, page projection
  node render_hist.mjs "$1" 1850 1885 1950 --gaps
  node render_hist.mjs "$1" 1820 1850 1866 1871 1885 1886 --zoom=-11,34,45,62:europe
  node render_hist.mjs "$1" 1830 1886 2026 --zoom=-90,9,-59,27:caribbean
  node render_hist.mjs "$1" 1750 1790 1840 1890 --zoom=-128,14,-60,58:northamerica
  node render_hist.mjs "$1" 1818 1850 1886 --zoom=58,4,100,38:southasia --rotate=-80
fi
ls -la "$REPO/web/geo/world_hist.topo.json" "$REPO/web/geo/world_hist_years.json"
