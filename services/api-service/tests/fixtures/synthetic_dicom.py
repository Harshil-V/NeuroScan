"""Synthetic MR DICOM generator used by all tests.

Produces small but valid DICOM bytes that exercise the same code path as
real DICOM files (parsable by pydicom, has all required tags).
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def make_synthetic_mr_dicom_bytes(
    *,
    study_instance_uid: str | None = None,
    series_instance_uid: str | None = None,
    sop_instance_uid: str | None = None,
    rows: int = 16,
    columns: int = 16,
    patient_id: str = "TEST-001",
    modality: str = "MR",
    instance_number: int = 1,
    pixel_array_override: np.ndarray | None = None,
) -> bytes:
    """Generate a valid MR DICOM as bytes."""
    study_uid = study_instance_uid or generate_uid()
    series_uid = series_instance_uid or generate_uid()
    sop_uid = sop_instance_uid or generate_uid()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("synthetic.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = patient_id
    ds.PatientName = "Synthetic^Test"
    ds.Modality = modality
    now = datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.StudyDescription = "Synthetic Test Study"
    ds.SeriesDescription = "Synthetic Test Series"
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

    if pixel_array_override is not None:
        if pixel_array_override.shape != (rows, columns):
            raise ValueError(
                f"pixel_array_override shape {pixel_array_override.shape} "
                f"does not match rows×columns ({rows}×{columns})"
            )
        pixel_array = pixel_array_override.astype(np.uint16)
    else:
        seed = abs(hash(sop_uid)) % (2**32)
        pixel_array = np.random.default_rng(seed).integers(
            0, 4096, (rows, columns), dtype=np.uint16
        )
    ds.PixelData = pixel_array.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


def make_dicom_missing_modality() -> bytes:
    """Generate a DICOM that is structurally valid but missing the Modality tag.

    Used to test the missing-required-tag negative path.
    """
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    del ds.Modality
    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()
