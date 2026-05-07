"""Build a valid MR DICOM file from a uint16 numpy image.

Generates fresh Patient/Study/Series/SOP UIDs for each call. Stamps
metadata that identifies the image as a NeuroScan reconstruction output
(distinguishable from clinical data).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


@dataclass(frozen=True)
class DicomWriteResult:
    dicom_bytes: bytes
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str


def image_to_mr_dicom(
    image: np.ndarray,
    *,
    source_name: str,
    patient_id: str = "RECON-001",
    study_description: str = "MRI Reconstruction",
    series_description: str = "Reconstructed",
) -> DicomWriteResult:
    """Build an MR DICOM from a uint16 image.

    Args:
        image: uint16 array, shape (rows, cols).
        source_name: filename of the source k-space (recorded in ImageComments).
        patient_id, study_description, series_description: provenance metadata.

    Returns:
        DicomWriteResult with the bytes plus all generated UIDs.
    """
    if image.dtype != np.uint16:
        image = image.astype(np.uint16)
    rows, cols = image.shape

    study_uid = generate_uid()
    series_uid = generate_uid()
    sop_uid = generate_uid()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(
        f"{source_name}.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128
    )
    ds.SOPClassUID = pydicom.uid.MRImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = patient_id
    ds.PatientName = "Reconstruction^Output"
    ds.Modality = "MR"
    now = datetime.now()
    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.StudyDescription = study_description
    ds.SeriesDescription = series_description
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1
    ds.ImageComments = f"Reconstructed from {source_name}"
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = image.tobytes()
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    buf = BytesIO()
    ds.save_as(buf, write_like_original=False)
    return DicomWriteResult(
        dicom_bytes=buf.getvalue(),
        study_instance_uid=study_uid,
        series_instance_uid=series_uid,
        sop_instance_uid=sop_uid,
    )
