#!/usr/bin/env bash
# Regenerate the foreign-born stock outputs in data/processed/ from data/raw/.
#   FETCH=1 scripts/stock/run_all.sh   also (re)fetches missing raw inputs first.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [[ "${FETCH:-0}" == 1 ]]; then
  bash scripts/stock/fetch_misc.sh
  bash scripts/stock/fetch_acs_api.sh
  python3 -I scripts/stock/fetch_acs_sf_2005_2009.py
  python3 -I scripts/stock/fetch_acs_sf_multiyear.py
fi
python3 -I -W ignore scripts/stock/build_state_totals.py
python3 -I -W ignore scripts/stock/build_national.py
python3 -I scripts/stock/build_hist_1920_t10.py
python3 -I scripts/stock/build_hist_1950_t71.py
python3 -I -W ignore scripts/stock/build_state_by_country.py
python3 -I scripts/stock/write_sources.py
python3 -I scripts/stock/check_outputs.py
