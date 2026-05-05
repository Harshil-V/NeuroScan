#!/usr/bin/env bash
# Downloads a small public MR series from TCIA into data/sample-dicom/tcia-brain-mr/.
#
# This script is for manual demos and screenshots. It is NOT used by tests or CI.
# Tests use the synthetic generator at scripts/generate-synthetic-dicom.py.
#
# Reference dataset: TCGA-GBM (a public glioblastoma cohort).
# https://www.cancerimagingarchive.net/collection/tcga-gbm/
#
# Update the SERIES_INSTANCE_UID below to point at any public MR series. The
# WADO endpoint is the standard NBIA WADO interface.

set -euo pipefail

DEST="$(cd "$(dirname "$0")/.." && pwd)/data/sample-dicom/tcia-brain-mr"
mkdir -p "$DEST"

# Replace with the SeriesInstanceUID you want to download. Pick one from
# https://services.cancerimagingarchive.net/services/v4/TCIA/query/getSeries
# for a public collection.
SERIES_INSTANCE_UID="${TCIA_SERIES_UID:-1.3.6.1.4.1.14519.5.2.1.4591.4001.124543141213723121925723796837}"

WADO_URL="https://services.cancerimagingarchive.net/services/v4/TCIA/query/getImage?SeriesInstanceUID=${SERIES_INSTANCE_UID}"

echo "Downloading $SERIES_INSTANCE_UID -> $DEST/series.zip"
curl -L -o "$DEST/series.zip" "$WADO_URL"

echo "Unzipping..."
unzip -o "$DEST/series.zip" -d "$DEST"
rm "$DEST/series.zip"

echo "Done. DICOM files in $DEST"
