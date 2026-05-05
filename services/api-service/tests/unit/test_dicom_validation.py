import pytest

from app.services.dicom_validation import (
    DicomValidationError,
    InvalidDicomError,
    MissingRequiredTagError,
    validate_dicom,
)
from tests.fixtures.synthetic_dicom import (
    make_dicom_missing_modality,
    make_synthetic_mr_dicom_bytes,
)


def test_validate_synthetic_mr_returns_dataset():
    raw = make_synthetic_mr_dicom_bytes()
    ds = validate_dicom(raw)
    assert ds.Modality == "MR"
    assert ds.StudyInstanceUID
    assert ds.SeriesInstanceUID
    assert ds.SOPInstanceUID


def test_validate_empty_bytes_raises_invalid():
    with pytest.raises(InvalidDicomError):
        validate_dicom(b"")


def test_validate_garbage_raises_invalid():
    with pytest.raises(InvalidDicomError):
        validate_dicom(b"this is not a dicom file at all")


def test_validate_missing_modality_raises_missing_tag():
    raw = make_dicom_missing_modality()
    with pytest.raises(MissingRequiredTagError) as exc:
        validate_dicom(raw)
    assert "Modality" in str(exc.value)


def test_errors_share_base_class():
    assert issubclass(InvalidDicomError, DicomValidationError)
    assert issubclass(MissingRequiredTagError, DicomValidationError)
