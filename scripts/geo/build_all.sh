#!/usr/bin/env bash
# Regenerate everything in web/geo/ from the raw downloads.
#   cd scripts/geo && npm ci && bash build_all.sh [RENDER_DIR]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
bash download_raw.sh
node build_us_historical.mjs
node verify_us_historical.mjs
node build_modern_states.mjs
node build_world.mjs
if [[ -n "${1:-}" ]]; then
  node render_checks.mjs "$1"                                   # AlbersUsa, default year list
  node render_checks.mjs "$1" 1650 1700 1750 1776 --proj=ne     # colonial north-east close-up
fi
ls -la ../../web/geo
