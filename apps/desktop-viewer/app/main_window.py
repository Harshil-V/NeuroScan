"""Main application window: 3-panel layout, menus, status bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QWidget,
)

from app.config import Config


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.setWindowTitle("NeuroScan Desktop Viewer")
        self.resize(1400, 900)

        self._build_menus()
        self._build_status_bar()
        self._build_central_widget()

    def _build_menus(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        open_action = QAction("Open Folder…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _build_central_widget(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Placeholder panels until D-tasks land.
        self._left = QLabel("Browser panel")
        self._left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._left.setMinimumWidth(280)
        self._left.setStyleSheet("background:#f0f0f0; border-right:1px solid #ccc;")

        self._center = QLabel("Viewer panel")
        self._center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._center.setStyleSheet("background:#1a1a1a; color:#888;")

        self._right = QLabel("Metadata panel")
        self._right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._right.setMinimumWidth(320)
        self._right.setStyleSheet("background:#f0f0f0; border-left:1px solid #ccc;")

        layout.addWidget(self._left, 0)
        layout.addWidget(self._center, 1)
        layout.addWidget(self._right, 0)

        self.setCentralWidget(central)

    def _on_open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open DICOM Folder")
        if path:
            self._status.showMessage(f"Selected: {path}")
