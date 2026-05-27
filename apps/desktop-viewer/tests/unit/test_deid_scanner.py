"""Smoke tests for the desktop's local PHI scanner."""

import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.deid.scanner import Finding, scan_phi


def _make_ds():
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "MRN-12345"
    ds.InstitutionName = "Test Hospital"
    ds.Modality = "MR"
    return ds


def test_scanner_imports_cleanly():
    assert Finding is not None
    assert scan_phi is not None


def test_scanner_finds_high_severity_tags():
    ds = _make_ds()
    findings = scan_phi(ds, salt="test")
    severities = {f.severity for f in findings}
    assert "high" in severities
    assert any(f.tag == "0010,0010" for f in findings)


def test_scanner_finds_medium_severity_tags():
    ds = _make_ds()
    findings = scan_phi(ds, salt="test")
    assert any(f.severity == "medium" and f.tag == "0008,0080" for f in findings)
