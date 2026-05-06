"""Empty state shown in the viewer area before any folder is loaded."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


def _find_repo_sample_dir() -> Path | None:
    """Walk up from this file to find data/sample-dicom/real/ if present."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "data" / "sample-dicom" / "real"
        if candidate.is_dir() and any(candidate.iterdir()):
            return candidate
    return None


class EmptyState(QWidget):
    """Shown in the central panel when no folder is loaded."""

    openFolderRequested = Signal()
    loadSampleRequested = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background:#1a1a1a; color:#bbb;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        label = QLabel("No folder loaded.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size:16px; color:#ddd;")
        layout.addWidget(label)

        open_btn = QPushButton("Open folder…")
        open_btn.setMinimumWidth(180)
        open_btn.clicked.connect(self.openFolderRequested.emit)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        sample = _find_repo_sample_dir()
        if sample is not None:
            sample_btn = QPushButton(f"Load sample data ({sample.name}/)")
            sample_btn.setMinimumWidth(280)
            sample_btn.clicked.connect(lambda: self.loadSampleRequested.emit(sample))
            layout.addWidget(sample_btn, alignment=Qt.AlignmentFlag.AlignCenter)
