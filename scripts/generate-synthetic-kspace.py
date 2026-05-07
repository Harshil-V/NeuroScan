#!/usr/bin/env python3
"""Generate a synthetic k-space file from a DICOM image.

Output is a .npz containing both 'kspace' (complex64) and 'ground_truth_image'
(float32, normalized to [0, 1]). The reconstruction service uses the embedded
ground truth to compute PSNR/SSIM on completion.

Usage:
    uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
        INPUT_DICOM OUTPUT_NPZ

Example:
    uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
        /Users/me/repo/data/sample-dicom/real-multislice/slice_010.dcm /tmp/brain.npz
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api-service"))

import numpy as np  # noqa: E402

from app.services.reconstruction.forward_fft import dicom_to_kspace  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: generate-synthetic-kspace.py INPUT_DICOM OUTPUT_NPZ",
            file=sys.stderr,
        )
        return 2
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    if not input_path.exists():
        print(f"Input DICOM not found: {input_path}", file=sys.stderr)
        return 1

    dicom_bytes = input_path.read_bytes()
    kspace, ground_truth = dicom_to_kspace(dicom_bytes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output_path,
        kspace=kspace,
        ground_truth_image=ground_truth,
    )
    print(
        f"Wrote {output_path} ({output_path.stat().st_size} bytes)\n"
        f"  kspace shape: {kspace.shape}, dtype: {kspace.dtype}\n"
        f"  ground_truth_image shape: {ground_truth.shape}, "
        f"range: [{ground_truth.min():.3f}, {ground_truth.max():.3f}]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
