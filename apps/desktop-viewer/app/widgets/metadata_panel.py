"""Right-side metadata table + Upload button + status label + Settings gear."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.deid.scanner import scan_phi

METADATA_FIELDS: list[tuple[str, str]] = [
    ("Patient ID", "PatientID"),
    ("Patient Name", "PatientName"),
    ("Study Instance UID", "StudyInstanceUID"),
    ("Study Date", "StudyDate"),
    ("Study Description", "StudyDescription"),
    ("Series Instance UID", "SeriesInstanceUID"),
    ("Series Description", "SeriesDescription"),
    ("Series Number", "SeriesNumber"),
    ("Modality", "Modality"),
    ("SOP Instance UID", "SOPInstanceUID"),
    ("Instance Number", "InstanceNumber"),
    ("Rows", "Rows"),
    ("Columns", "Columns"),
    ("Pixel Spacing", "PixelSpacing"),
    ("Slice Thickness", "SliceThickness"),
    ("Bits Allocated", "BitsAllocated"),
    ("Window Center", "WindowCenter"),
    ("Window Width", "WindowWidth"),
]


class MetadataPanel(QWidget):
    uploadRequested = Signal()  # MainWindow looks up the current bytes
    settingsRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Metadata")
        title.setStyleSheet("font-weight:bold; font-size:13px;")
        layout.addWidget(title)

        self._phi_summary = QLabel("")
        self._phi_summary.setWordWrap(True)
        layout.addWidget(self._phi_summary)

        self._table = QTableWidget(len(METADATA_FIELDS) + 1, 2)
        self._table.setHorizontalHeaderLabels(["Tag", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, (label, _) in enumerate(METADATA_FIELDS):
            self._table.setItem(row, 0, QTableWidgetItem(label))
            self._table.setItem(row, 1, QTableWidgetItem("—"))
        # File path row at the end (filled separately)
        self._table.setItem(len(METADATA_FIELDS), 0, QTableWidgetItem("File Path"))
        self._table.setItem(len(METADATA_FIELDS), 1, QTableWidgetItem("—"))
        layout.addWidget(self._table, 1)

        # Upload row
        upload_row = QWidget()
        h = QHBoxLayout(upload_row)
        h.setContentsMargins(0, 0, 0, 0)
        self._upload_btn = QPushButton("Upload to backend")
        self._upload_btn.setEnabled(False)
        self._upload_btn.clicked.connect(self.uploadRequested.emit)
        h.addWidget(self._upload_btn, 1)
        gear = QToolButton()
        gear.setText("⚙")
        gear.setToolTip("Backend settings")
        gear.clicked.connect(self.settingsRequested.emit)
        h.addWidget(gear)
        layout.addWidget(upload_row)

        self._status = QLabel("Idle")
        self._status.setStyleSheet("color:#666;")
        layout.addWidget(self._status)

    # ---- public API ----

    def show_dataset(self, dataset, file_path: str | None = None) -> None:
        for row, (_, attr) in enumerate(METADATA_FIELDS):
            value = getattr(dataset, attr, None)
            self._table.item(row, 1).setText(self._format_value(value))
        last_row = len(METADATA_FIELDS)
        self._table.item(last_row, 1).setText(file_path or "—")
        self._upload_btn.setEnabled(True)

        findings = scan_phi(dataset, salt="desktop-local")
        phi_by_attr = {f.tag_name: f.severity for f in findings}

        high_bg = QColor("#fee2e2")
        medium_bg = QColor("#fef3c7")

        for row, (_, attr) in enumerate(METADATA_FIELDS):
            sev = phi_by_attr.get(attr)
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is None:
                    continue
                if sev == "high":
                    item.setBackground(high_bg)
                elif sev == "medium":
                    item.setBackground(medium_bg)
                else:
                    item.setBackground(QColor(0, 0, 0, 0))

        high = sum(1 for s in phi_by_attr.values() if s == "high")
        medium = sum(1 for s in phi_by_attr.values() if s == "medium")
        if high or medium:
            self._phi_summary.setText(f"⚠ {high} high · {medium} medium PHI tags detected")
            self._phi_summary.setStyleSheet(
                "background:#fef9c3; color:#92400e; padding:4px; border-radius:4px;"
            )
        else:
            self._phi_summary.setText("")
            self._phi_summary.setStyleSheet("")

    def clear(self) -> None:
        for row, _ in enumerate(METADATA_FIELDS):
            self._table.item(row, 1).setText("—")
        self._table.item(len(METADATA_FIELDS), 1).setText("—")
        self._upload_btn.setEnabled(False)
        self._status.setText("Idle")
        self._phi_summary.setText("")
        self._phi_summary.setStyleSheet("")

    def set_status(self, text: str, *, color: str = "#666") -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color:{color};")

    def set_upload_busy(self, busy: bool) -> None:
        self._upload_btn.setEnabled(not busy)

    def _format_value(self, value: object) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, list | tuple):
            return ", ".join(str(v) for v in value)
        return str(value)
