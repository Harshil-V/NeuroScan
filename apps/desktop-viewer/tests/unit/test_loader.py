from pathlib import Path

import pytest

from app.dicom.loader import (
    InstanceRef,
    SeriesRef,
    StudyRef,
    is_dicom,
    scan_folder,
)
from tests.fixtures.make_test_series import write_test_series, write_two_studies


def test_scan_folder_empty_returns_empty_list(tmp_path: Path):
    assert scan_folder(tmp_path) == []


def test_scan_folder_skips_non_dicom_silently(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "image.png").write_bytes(b"\x89PNG-fake")
    assert scan_folder(tmp_path) == []


def test_scan_folder_groups_one_series(tmp_path: Path):
    study_uid, series_uid, paths = write_test_series(tmp_path, n_instances=4)
    studies = scan_folder(tmp_path)
    assert len(studies) == 1
    s = studies[0]
    assert isinstance(s, StudyRef)
    assert s.study_instance_uid == study_uid
    assert s.patient_id == "TEST-001"
    assert len(s.series) == 1
    series = s.series[0]
    assert isinstance(series, SeriesRef)
    assert series.series_instance_uid == series_uid
    assert series.modality == "MR"
    assert len(series.instances) == 4


def test_scan_folder_sorts_instances_by_instance_number(tmp_path: Path):
    write_test_series(tmp_path, n_instances=5)
    studies = scan_folder(tmp_path)
    instances = studies[0].series[0].instances
    numbers = [i.instance_number for i in instances]
    assert numbers == sorted(numbers)


def test_scan_folder_groups_two_studies(tmp_path: Path):
    info = write_two_studies(tmp_path)
    studies = scan_folder(tmp_path)
    assert len(studies) == 2
    uids = {s.study_instance_uid for s in studies}
    assert uids == {info["study_a"]["study_uid"], info["study_b"]["study_uid"]}


def test_scan_folder_recurses_into_subdirectories(tmp_path: Path):
    subdir = tmp_path / "deep" / "nested" / "path"
    write_test_series(subdir, n_instances=2)
    studies = scan_folder(tmp_path)
    assert len(studies) == 1
    assert len(studies[0].series[0].instances) == 2


def test_instance_ref_carries_file_path(tmp_path: Path):
    _, _, paths = write_test_series(tmp_path, n_instances=2)
    studies = scan_folder(tmp_path)
    instance_paths = {i.file_path for i in studies[0].series[0].instances}
    assert instance_paths == set(paths)


def test_is_dicom_recognizes_valid_file(tmp_path: Path):
    _, _, paths = write_test_series(tmp_path, n_instances=1)
    assert is_dicom(paths[0]) is True


def test_is_dicom_rejects_text_file(tmp_path: Path):
    text_path = tmp_path / "fake.dcm"
    text_path.write_text("this is not a DICOM at all even with the .dcm extension")
    assert is_dicom(text_path) is False


def test_instance_ref_dataclass_is_frozen():
    ref = InstanceRef(
        file_path=Path("/x.dcm"),
        sop_instance_uid="1.2.3",
        instance_number=1,
        rows=64,
        columns=64,
    )
    with pytest.raises(AttributeError):
        ref.sop_instance_uid = "different"  # type: ignore[misc]
