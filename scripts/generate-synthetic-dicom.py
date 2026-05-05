#!/usr/bin/env python3
"""Generate a synthetic MR DICOM file at the given path.

Usage:
    uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py /tmp/x.dcm
"""

from __future__ import annotations

import sys
from pathlib import Path

# This script is intended to be run via `uv run --directory services/api-service`,
# which makes the api-service venv (with pydicom and the test fixtures) importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api-service"))

from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: generate-synthetic-dicom.py OUTPUT_PATH", file=sys.stderr)
        sys.exit(2)
    out = Path(sys.argv[1])
    out.write_bytes(make_synthetic_mr_dicom_bytes())
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
