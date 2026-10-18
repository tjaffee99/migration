#!/usr/bin/env bash
# Download the raw inputs of the historical world layer (data/raw/* is git-ignored).
#   CShapes 2.0 + CShapes-Europe (ETH Zurich ICR, CC BY-NC-SA 4.0) -> data/raw/cshapes/
#   historical-basemaps (A. Ourednik, GPL-3.0): used from $HB_DIR if it exists, otherwise cloned (pinned commit)
#   into data/raw/cshapes/historical-basemaps/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
RAW="$REPO/data/raw/cshapes"
mkdir -p "$RAW"
BASE=https://icr.ethz.ch/data/cshapes
for f in CShapes-Europe.geojson cshapes_2.0.tar.gz CShapes-2.0_Codebook.pdf ChangeLog.txt; do
  [[ -s "$RAW/$f" ]] || { echo "downloading $BASE/$f"; curl -sSfL -o "$RAW/$f" "$BASE/$f"; }
done
# The CShapes 2.0 GeoJSON/CSV/shapefile downloads lack the status/owner (dependency) fields; the R package
# (cshapes 2.0, GW version) carries them, so its TopoJSON is used.
if [[ ! -s "$RAW/rpkg/cshapes/inst/extdata/cshapes_2_gw.topojson" ]]; then
  mkdir -p "$RAW/rpkg" && tar -xzf "$RAW/cshapes_2.0.tar.gz" -C "$RAW/rpkg"
  xz -dk "$RAW/rpkg/cshapes/inst/extdata/cshapes_2_gw.topojson.xz"
fi
HB_COMMIT=da7a4b735ecef70aebdc9c73e409d8a2500d50f3
HB_DIR="${HB_DIR:-$REPO/../aourednik/historical-basemaps}"
if [[ ! -d "$HB_DIR/geojson" ]]; then
  HB_DIR="$RAW/historical-basemaps"
  if [[ ! -d "$HB_DIR/geojson" ]]; then
    git clone --quiet https://github.com/aourednik/historical-basemaps "$HB_DIR"
    git -C "$HB_DIR" checkout --quiet "$HB_COMMIT"
  fi
fi
echo "historical-basemaps: $HB_DIR ($(git -C "$HB_DIR" rev-parse HEAD 2>/dev/null || echo 'not a git checkout'))"
(cd "$RAW" && sha256sum CShapes-Europe.geojson cshapes_2.0.tar.gz rpkg/cshapes/inst/extdata/cshapes_2_gw.topojson)
