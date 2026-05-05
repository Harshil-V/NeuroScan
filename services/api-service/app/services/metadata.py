from typing import Any

from pydicom.dataset import Dataset


def _str_or_none(ds: Dataset, tag: str) -> str | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    return str(value)


def _int_or_none(ds: Dataset, tag: str) -> int | None:
    value = getattr(ds, tag, None)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_metadata(ds: Dataset) -> dict[str, Any]:
    return {
        "patient_id": _str_or_none(ds, "PatientID"),
        "study_instance_uid": _str_or_none(ds, "StudyInstanceUID"),
        "series_instance_uid": _str_or_none(ds, "SeriesInstanceUID"),
        "sop_instance_uid": _str_or_none(ds, "SOPInstanceUID"),
        "modality": _str_or_none(ds, "Modality"),
        "study_date": _str_or_none(ds, "StudyDate"),
        "study_description": _str_or_none(ds, "StudyDescription"),
        "series_description": _str_or_none(ds, "SeriesDescription"),
        "series_number": _int_or_none(ds, "SeriesNumber"),
        "instance_number": _int_or_none(ds, "InstanceNumber"),
        "rows": _int_or_none(ds, "Rows"),
        "columns": _int_or_none(ds, "Columns"),
    }
