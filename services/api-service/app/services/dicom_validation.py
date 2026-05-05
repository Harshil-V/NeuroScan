from io import BytesIO

import pydicom
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError as PydicomInvalidDicomError

REQUIRED_TAGS: tuple[str, ...] = (
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "Modality",
)


class DicomValidationError(Exception):
    """Base class for DICOM validation failures."""


class InvalidDicomError(DicomValidationError):
    """Bytes are not a parseable DICOM file."""


class MissingRequiredTagError(DicomValidationError):
    """DICOM is parseable but missing a required tag."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        super().__init__(f"Missing required DICOM tag: {tag}")


def validate_dicom(data: bytes) -> Dataset:
    """Parse and validate DICOM bytes.

    Raises:
        InvalidDicomError: bytes cannot be parsed as DICOM.
        MissingRequiredTagError: parsed but missing a required tag.
    """
    if not data:
        raise InvalidDicomError("Empty bytes")
    try:
        ds = pydicom.dcmread(BytesIO(data), force=False)
    except (PydicomInvalidDicomError, Exception) as exc:
        # Force=False rejects non-DICOM. Anything else (truncated, etc.)
        # we also classify as invalid.
        raise InvalidDicomError(str(exc)) from exc

    for tag in REQUIRED_TAGS:
        if not getattr(ds, tag, None):
            raise MissingRequiredTagError(tag)
    return ds
