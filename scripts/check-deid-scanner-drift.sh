#!/usr/bin/env bash
# Verify the duplicated PHI scanner files match byte-for-byte across
# api-service and desktop-viewer. Slice 5 ships two copies of the scanner
# because the desktop viewer is standalone (no backend dep) — this script
# is the safety net against drift.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_SCANNER="$ROOT/services/api-service/app/deid/scanner.py"
DESKTOP_SCANNER="$ROOT/apps/desktop-viewer/app/deid/scanner.py"
RULES_SOURCE="$ROOT/data/deid-rules.json"
RULES_DESKTOP="$ROOT/apps/desktop-viewer/app/deid/rules.json"

if ! cmp -s "$API_SCANNER" "$DESKTOP_SCANNER"; then
  echo "DRIFT: api-service scanner.py != desktop-viewer scanner.py" >&2
  diff -u "$API_SCANNER" "$DESKTOP_SCANNER" >&2 || true
  exit 1
fi

if ! cmp -s "$RULES_SOURCE" "$RULES_DESKTOP"; then
  echo "DRIFT: data/deid-rules.json != apps/desktop-viewer/app/deid/rules.json" >&2
  diff -u "$RULES_SOURCE" "$RULES_DESKTOP" >&2 || true
  exit 1
fi

echo "OK: scanner.py and rules.json match across api-service and desktop-viewer"
