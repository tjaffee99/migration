#!/usr/bin/env bash
# Fetch one URL from Archive-It (Internet Archive's wayback.archive-it.org/all), retrying through its rate limit.
# Usage: ait_get.sh <original-url> <out-file> [timestamp-prefix, default 2025]
# The live DHS/OHSS sites block this environment, so DHS files come only from web-archive captures.
set -uo pipefail
url="$1"; out="$2"; ts="${3:-2025}"
mkdir -p "$(dirname "$out")"
if [ -s "$out" ] && ! grep -q -s "Rate limit reached" "$out"; then echo "have $out"; exit 0; fi
for try in $(seq 1 12); do
  code=$(curl -sS -L -m 600 -o "$out" -w '%{http_code} %{url_effective}' "https://wayback.archive-it.org/all/${ts}/${url}" 2>&1) || true
  if grep -q -s "Rate limit reached" "$out"; then sleep $((30 * try)); continue; fi
  break
done
echo "$code" > "$out.memento"
echo "$(stat -c %s "$out" 2>/dev/null) $(file -b "$out" | cut -c1-30) $code"
sleep 10
