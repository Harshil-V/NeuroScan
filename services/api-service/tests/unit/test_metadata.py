from io import BytesIO

import pydicom

from app.services.metadata import extract_metadata
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def test_extract_metadata_returns_expected_fields():
    raw = make_synthetic_mr_dicom_bytes(patient_id="P-1")
    ds = pydicom.dcmread(BytesIO(raw))
    md = extract_metadata(ds)
    assert md["patient_id"] == "P-1"
    assert md["modality"] == "MR"
    assert md["study_instance_uid"] == ds.StudyInstanceUID
    assert md["series_instance_uid"] == ds.SeriesInstanceUID
    assert md["sop_instance_uid"] == ds.SOPInstanceUID
    assert md["rows"] == 16
    assert md["columns"] == 16


def test_extract_metadata_handles_missing_optional_fields():
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    del ds.StudyDescription
    md = extract_metadata(ds)
    assert md["study_description"] is None
    assert md["modality"] == "MR"  # required fields still there
