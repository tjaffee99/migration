#!/usr/bin/env bash
# Build every "recent" (2024-2026) processed file from the raw inputs.
# FETCH=1 bash scripts/recent/run_all.sh   also (re)downloads missing raw inputs first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ "${FETCH:-0}" = 1 ] && bash "$ROOT/scripts/recent/fetch_recent.sh"
python3 -I "$ROOT/scripts/recent/build_flows_recent.py"
python3 -I "$ROOT/scripts/recent/build_stock_cps.py"
python3 -I "$ROOT/scripts/recent/build_us_population.py"
python3 -I "$ROOT/scripts/recent/build_net_migration.py"
python3 -I "$ROOT/scripts/recent/write_sources_recent.py"
python3 -I "$ROOT/scripts/recent/check_recent.py"
