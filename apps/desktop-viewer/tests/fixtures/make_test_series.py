"""Helpers to write synthetic DICOM files to disk for desktop-viewer tests.

This module is independent of the api-service venv. We re-implement a minimal
synthetic generator here rather than imposing cross-project imports.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def _make_one_dicom_bytes(
    *,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    instance_number: int,
    rows: int = 32,
    columns: int = 32,
    series_description: str = "Test Series",
    modality: str = "MR",
    patient_id: str = "TEST-001",
) -> bytes:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = patient_id
    ds.PatientName = "Test^Subject"
    ds.Modality = modality
    now = datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyDescription = "Desktop Viewer Test Study"
    ds.SeriesDescription = series_description
    ds.SeriesNumber = 1
    ds.InstanceNumber = instance_number
    ds.Rows = rows
    ds.Columns = columns
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    seed = abs(hash(sop_uid)) % (2**32)
    pixels = np.random.default_rng(seed).integers(0, 4096, (rows, columns), dtype=np.uint16)
    ds.PixelData = pixels.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


def write_test_series(
    out_dir: Path,
    *,
    n_instances: int = 4,
    series_description: str = "Test Series",
    rows: int = 32,
    columns: int = 32,
) -> tuple[str, str, list[Path]]:
    """Write a series of N DICOM files into out_dir.

    Returns (study_instance_uid, series_instance_uid, list_of_file_paths).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    study_uid = generate_uid()
    series_uid = generate_uid()
    paths: list[Path] = []
    for i in range(n_instances):
        sop_uid = generate_uid()
        data = _make_one_dicom_bytes(
            study_uid=study_uid,
            series_uid=series_uid,
            sop_uid=sop_uid,
            instance_number=i + 1,
            rows=rows,
            columns=columns,
            series_description=series_description,
        )
        path = out_dir / f"slice_{i:03d}.dcm"
        path.write_bytes(data)
        paths.append(path)
    return study_uid, series_uid, paths


def write_two_studies(out_dir: Path) -> dict:
    """Write two separate studies (different StudyInstanceUIDs) into the same dir.

    Useful for testing folder scanning + grouping. Returns a dict describing what was written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    s1_study, s1_series, s1_paths = write_test_series(
        out_dir / "studyA", n_instances=3, series_description="Study A Series"
    )
    s2_study, s2_series, s2_paths = write_test_series(
        out_dir / "studyB", n_instances=2, series_description="Study B Series"
    )
    return {
        "study_a": {"study_uid": s1_study, "series_uid": s1_series, "paths": s1_paths},
        "study_b": {"study_uid": s2_study, "series_uid": s2_series, "paths": s2_paths},
    }
