"""Settings dialog: edit api_url."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, current_url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Backend Settings")
        self.setModal(True)
        self.resize(420, 120)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._url_edit = QLineEdit(current_url)
        self._url_edit.setPlaceholderText("http://localhost:8000")
        form.addRow("API service URL:", self._url_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def url(self) -> str:
        return self._url_edit.text().strip()
