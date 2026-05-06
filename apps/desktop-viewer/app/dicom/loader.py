"""DICOM folder scanner.

Walks a directory recursively, parses any file pydicom can read, and groups
the results into a Study → Series → Instance hierarchy. Pure logic — no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pydicom
from pydicom.errors import InvalidDicomError


@dataclass(frozen=True)
class InstanceRef:
    file_path: Path
    sop_instance_uid: str
    instance_number: int | None
    rows: int | None
    columns: int | None


@dataclass(frozen=True)
class SeriesRef:
    series_instance_uid: str
    series_description: str | None
    modality: str | None
    series_number: int | None
    instances: tuple[InstanceRef, ...]


@dataclass(frozen=True)
class StudyRef:
    study_instance_uid: str
    patient_id: str | None
    patient_name: str | None
    study_date: str | None
    study_description: str | None
    series: tuple[SeriesRef, ...]


def is_dicom(path: Path) -> bool:
    """Quick header check — no full parse, no pixel decode."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except OSError:
        return False


def _read_metadata(path: Path) -> pydicom.Dataset | None:
    try:
        return pydicom.dcmread(path, stop_before_pixels=True, force=False)
    except (InvalidDicomError, OSError, Exception):
        return None


def _str_or_none(ds: pydicom.Dataset, tag: str) -> str | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    return str(value)


def _int_or_none(ds: pydicom.Dataset, tag: str) -> int | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def scan_folder(root: Path) -> list[StudyRef]:
    """Walk root recursively, parse every file with pydicom, group hierarchically.

    Returns a list of StudyRef. Files that are not parseable as DICOM are silently
    skipped. Within a series, instances are sorted by InstanceNumber (None last,
    then by filename).
    """
    if not root.exists() or not root.is_dir():
        return []

    by_study: dict[str, dict] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not is_dicom(path):
            continue
        ds = _read_metadata(path)
        if ds is None:
            continue
        study_uid = _str_or_none(ds, "StudyInstanceUID")
        series_uid = _str_or_none(ds, "SeriesInstanceUID")
        sop_uid = _str_or_none(ds, "SOPInstanceUID")
        if not (study_uid and series_uid and sop_uid):
            continue

        study_entry = by_study.setdefault(
            study_uid,
            {
                "study_instance_uid": study_uid,
                "patient_id": _str_or_none(ds, "PatientID"),
                "patient_name": _str_or_none(ds, "PatientName"),
                "study_date": _str_or_none(ds, "StudyDate"),
                "study_description": _str_or_none(ds, "StudyDescription"),
                "series": {},
            },
        )

        series_entry = study_entry["series"].setdefault(
            series_uid,
            {
                "series_instance_uid": series_uid,
                "series_description": _str_or_none(ds, "SeriesDescription"),
                "modality": _str_or_none(ds, "Modality"),
                "series_number": _int_or_none(ds, "SeriesNumber"),
                "instances": [],
            },
        )

        series_entry["instances"].append(
            InstanceRef(
                file_path=path,
                sop_instance_uid=sop_uid,
                instance_number=_int_or_none(ds, "InstanceNumber"),
                rows=_int_or_none(ds, "Rows"),
                columns=_int_or_none(ds, "Columns"),
            )
        )

    studies: list[StudyRef] = []
    for study_data in by_study.values():
        series_list: list[SeriesRef] = []
        for series_data in study_data["series"].values():
            sorted_instances = tuple(
                sorted(
                    series_data["instances"],
                    key=lambda i: (
                        i.instance_number if i.instance_number is not None else 1_000_000,
                        str(i.file_path),
                    ),
                )
            )
            series_list.append(
                SeriesRef(
                    series_instance_uid=series_data["series_instance_uid"],
                    series_description=series_data["series_description"],
                    modality=series_data["modality"],
                    series_number=series_data["series_number"],
                    instances=sorted_instances,
                )
            )
        studies.append(
            StudyRef(
                study_instance_uid=study_data["study_instance_uid"],
                patient_id=study_data["patient_id"],
                patient_name=study_data["patient_name"],
                study_date=study_data["study_date"],
                study_description=study_data["study_description"],
                series=tuple(series_list),
            )
        )
    return studies
