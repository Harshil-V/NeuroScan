"""Right-side metadata table + Upload button + status label + Settings gear."""

from __future__ import annotations

from PySide6.QtCore import Signal
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

    def clear(self) -> None:
        for row, _ in enumerate(METADATA_FIELDS):
            self._table.item(row, 1).setText("—")
        self._table.item(len(METADATA_FIELDS), 1).setText("—")
        self._upload_btn.setEnabled(False)
        self._status.setText("Idle")

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
