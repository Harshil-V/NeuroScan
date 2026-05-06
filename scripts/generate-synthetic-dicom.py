#!/usr/bin/env python3
"""Generate synthetic MR DICOM file(s).

Usage:
    # Single instance (slice 1 backward-compatible form):
    uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py /tmp/x.dcm

    # Multi-instance series (slice 2):
    uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py \\
        --count 32 --output /tmp/multi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api-service"))

import numpy as np  # noqa: E402
from pydicom.uid import generate_uid  # noqa: E402

from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes  # noqa: E402


def _gradient_pixels(rows: int, cols: int, slice_idx: int, n_slices: int) -> np.ndarray:
    """Per-slice gradient so navigation is visually obvious.

    Combines an X gradient with a Y gradient that shifts based on slice index.
    """
    x = np.linspace(0, 4095, cols, dtype=np.float32)
    y = np.linspace(0, 4095, rows, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    phase = (slice_idx / max(n_slices - 1, 1)) * np.pi
    return ((xx + yy * np.cos(phase)) % 4096).astype(np.uint16)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic MR DICOM(s).")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output file path (single-instance mode) — required if --output not given.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of instances to generate (default: 1).",
    )
    parser.add_argument(
        "--output",
        dest="output_dir",
        help="Output directory (multi-instance mode) — required if --count > 1.",
    )
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--columns", type=int, default=64)
    args = parser.parse_args()

    if args.count == 1 and args.output and not args.output_dir:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = make_synthetic_mr_dicom_bytes(rows=args.rows, columns=args.columns)
        out.write_bytes(data)
        print(f"Wrote {out} ({out.stat().st_size} bytes)")
        return 0

    if args.count > 1:
        if not args.output_dir:
            print("--output DIR is required when --count > 1", file=sys.stderr)
            return 2
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        study_uid = generate_uid()
        series_uid = generate_uid()
        for i in range(args.count):
            sop_uid = generate_uid()
            pixels = _gradient_pixels(args.rows, args.columns, i, args.count)
            data = make_synthetic_mr_dicom_bytes(
                study_instance_uid=study_uid,
                series_instance_uid=series_uid,
                sop_instance_uid=sop_uid,
                rows=args.rows,
                columns=args.columns,
                pixel_array_override=pixels,
                instance_number=i + 1,
            )
            (out_dir / f"slice_{i:03d}.dcm").write_bytes(data)
        print(f"Wrote {args.count} instances to {out_dir}")
        return 0

    print("Specify either OUTPUT (single instance) or --count N --output DIR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
