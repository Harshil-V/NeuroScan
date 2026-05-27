from io import BytesIO

import pydicom

from app.deid.scanner import Finding, scan_phi
from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes


def _ds_with(**fields):
    """Build a dataset with the given attributes set on top of the synthetic fixture."""
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    for k, v in fields.items():
        setattr(ds, k, v)
    return ds


def test_scan_returns_list_of_findings():
    ds = _ds_with()
    findings = scan_phi(ds, salt="test-salt")
    assert isinstance(findings, list)
    assert all(isinstance(f, Finding) for f in findings)


def test_scan_flags_patient_name_high_severity():
    ds = _ds_with(PatientName="DOE^JOHN")
    findings = scan_phi(ds, salt="test-salt")
    pn = next((f for f in findings if f.tag == "0010,0010"), None)
    assert pn is not None
    assert pn.tag_name == "PatientName"
    assert pn.severity == "high"
    assert pn.value_sha256 is not None
    assert len(pn.value_sha256) == 64  # SHA-256 hex


def test_scan_flags_institution_name_medium_severity():
    ds = _ds_with(InstitutionName="General Hospital")
    findings = scan_phi(ds, salt="test-salt")
    inst = next((f for f in findings if f.tag == "0008,0080"), None)
    assert inst is not None
    assert inst.severity == "medium"


def test_scan_ignores_non_phi_tags():
    ds = _ds_with()
    findings = scan_phi(ds, salt="test-salt")
    tags = {f.tag for f in findings}
    assert "0028,0010" not in tags  # Rows — not PHI
    assert "0028,0011" not in tags  # Columns — not PHI


def test_scan_empty_value_yields_null_hash():
    ds = _ds_with(PatientID="")
    findings = scan_phi(ds, salt="test-salt")
    pid = next((f for f in findings if f.tag == "0010,0020"), None)
    # PatientID tag exists but value is empty
    assert pid is not None
    assert pid.value_sha256 is None


def test_scan_missing_tag_not_flagged():
    raw = make_synthetic_mr_dicom_bytes()
    ds = pydicom.dcmread(BytesIO(raw))
    del ds.PatientName
    findings = scan_phi(ds, salt="test-salt")
    tags = {f.tag for f in findings}
    assert "0010,0010" not in tags


def test_scan_deterministic_hash_with_same_salt():
    ds = _ds_with(PatientName="DOE^JOHN")
    a = scan_phi(ds, salt="salt-A")
    b = scan_phi(ds, salt="salt-A")
    ha = next(f.value_sha256 for f in a if f.tag == "0010,0010")
    hb = next(f.value_sha256 for f in b if f.tag == "0010,0010")
    assert ha == hb


def test_scan_different_salt_yields_different_hash():
    ds = _ds_with(PatientName="DOE^JOHN")
    a = scan_phi(ds, salt="salt-A")
    b = scan_phi(ds, salt="salt-B")
    ha = next(f.value_sha256 for f in a if f.tag == "0010,0010")
    hb = next(f.value_sha256 for f in b if f.tag == "0010,0010")
    assert ha != hb


def test_scan_counts_high_and_medium_correctly():
    ds = _ds_with(
        PatientName="DOE^JOHN",
        PatientID="MRN-001",
        PatientBirthDate="19800101",
        InstitutionName="General Hospital",
        ReferringPhysicianName="SMITH^J",
    )
    findings = scan_phi(ds, salt="test-salt")
    high = [f for f in findings if f.severity == "high"]
    medium = [f for f in findings if f.severity == "medium"]
    assert len(high) >= 3  # PatientName, PatientID, PatientBirthDate
    assert len(medium) >= 2  # InstitutionName, ReferringPhysicianName


def test_scan_performance_under_50ms_on_large_dataset():
    import time

    ds = _ds_with(PatientName="DOE^JOHN")
    # pydicom Dataset supports arbitrary private tags; add 500 of them
    for i in range(500):
        ds.add_new((0x0099, 0x1000 + i), "LO", f"value-{i}")

    t0 = time.perf_counter()
    findings = scan_phi(ds, salt="test-salt")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 50, f"scan_phi took {elapsed_ms:.1f}ms, expected < 50ms"
    assert any(f.tag == "0010,0010" for f in findings)
