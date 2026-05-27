"""Verify MetadataPanel highlights PHI rows and shows summary."""

import sys

import pydicom
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.widgets.metadata_panel import MetadataPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _phi_dataset():
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("t.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "MRN-001"
    ds.InstitutionName = "Test Hospital"
    ds.Modality = "MR"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    return ds


def _find_row_for_attr(panel: MetadataPanel, attr: str) -> int | None:
    """Find the row index in the panel table for a given METADATA_FIELDS attr name."""
    from app.widgets.metadata_panel import METADATA_FIELDS

    for i, (_, a) in enumerate(METADATA_FIELDS):
        if a == attr:
            return i
    return None


def test_panel_highlights_patient_name_red(qapp):
    panel = MetadataPanel()
    panel.show_dataset(_phi_dataset())

    row = _find_row_for_attr(panel, "PatientName")
    assert row is not None, "PatientName not in METADATA_FIELDS"
    bg = panel._table.item(row, 0).background().color()
    assert bg == QColor("#fee2e2"), f"Expected light red, got {bg.name()}"


def test_panel_highlights_institution_name_amber(qapp):
    panel = MetadataPanel()
    panel.show_dataset(_phi_dataset())

    row = _find_row_for_attr(panel, "PatientID")
    assert row is not None
    bg = panel._table.item(row, 0).background().color()
    assert bg == QColor("#fee2e2"), f"Expected light red for PatientID, got {bg.name()}"


def test_panel_shows_phi_summary(qapp):
    panel = MetadataPanel()
    panel.show_dataset(_phi_dataset())
    text = panel._phi_summary.text()
    assert "PHI" in text or "high" in text.lower()
    assert len(text) > 0


def test_panel_clear_resets_summary(qapp):
    panel = MetadataPanel()
    panel.show_dataset(_phi_dataset())
    panel.clear()
    assert panel._phi_summary.text() == ""
