"""Main application window: 3-panel layout, signal wiring, background threads."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from app.config import Config
from app.dicom.loader import SeriesRef, StudyRef, scan_folder
from app.dicom.series import LoadedSeries, load_series
from app.upload.worker import UploadWorker
from app.widgets.browser_panel import BrowserPanel
from app.widgets.empty_state import EmptyState
from app.widgets.metadata_panel import MetadataPanel
from app.widgets.settings_dialog import SettingsDialog
from app.widgets.viewer_panel import ViewerPanel


class FolderScanWorker(QObject):
    """Runs scan_folder in a worker QThread."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root

    def run(self) -> None:
        try:
            studies = scan_folder(self._root)
        except Exception as exc:  # noqa: BLE001 — defensive
            self.failed.emit(str(exc))
            return
        self.finished.emit(studies)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.setWindowTitle("NeuroScan Desktop Viewer")
        self.resize(1400, 900)

        self._loaded_series: LoadedSeries | None = None
        self._scan_thread: QThread | None = None
        self._scan_worker: FolderScanWorker | None = None
        self._upload_worker: UploadWorker | None = None

        self._build_menus()
        self._build_status_bar()
        self._build_central_widget()

    # ---- UI ----

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

        self._browser = BrowserPanel()
        self._browser.setMinimumWidth(280)
        self._browser.setMaximumWidth(380)
        self._browser.seriesSelected.connect(self._on_series_selected)
        self._browser.instanceSelected.connect(self._on_instance_selected)

        # Center: stack of empty state and viewer
        self._center_stack = QStackedWidget()
        self._empty_state = EmptyState()
        self._empty_state.openFolderRequested.connect(self._on_open_folder)
        self._empty_state.loadSampleRequested.connect(self._load_folder)
        self._viewer = ViewerPanel()
        self._viewer.sliceChanged.connect(self._on_slice_changed)
        self._center_stack.addWidget(self._empty_state)
        self._center_stack.addWidget(self._viewer)
        self._center_stack.setCurrentWidget(self._empty_state)

        self._metadata = MetadataPanel()
        self._metadata.uploadRequested.connect(self._on_upload_requested)
        self._metadata.settingsRequested.connect(self._on_settings_requested)

        layout.addWidget(self._browser, 0)
        layout.addWidget(self._center_stack, 1)
        layout.addWidget(self._metadata, 0)
        self.setCentralWidget(central)

    # ---- Folder loading ----

    def _on_open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open DICOM Folder")
        if path:
            self._load_folder(Path(path))

    def _load_folder(self, root: Path) -> None:
        self._status.showMessage(f"Scanning {root}…")
        self._scan_thread = QThread(self)
        self._scan_worker = FolderScanWorker(root)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.start()

    def _on_scan_finished(self, studies: list[StudyRef]) -> None:
        self._scan_worker = None
        self._scan_thread = None
        if not studies:
            self._status.showMessage("No DICOM files found")
            QMessageBox.information(self, "No DICOMs", "No DICOM files were found in that folder.")
            return
        n_series = sum(len(s.series) for s in studies)
        n_inst = sum(len(se.instances) for s in studies for se in s.series)
        self._status.showMessage(
            f"Loaded {len(studies)} studies · {n_series} series · {n_inst} instances"
        )
        self._browser.set_studies(studies)

    def _on_scan_failed(self, message: str) -> None:
        self._scan_worker = None
        self._scan_thread = None
        self._status.showMessage(f"Scan failed: {message}")
        QMessageBox.critical(self, "Scan failed", message)

    # ---- Series / instance selection ----

    def _on_series_selected(self, series: SeriesRef) -> None:
        try:
            loaded = load_series(series)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", f"Could not load series:\n{exc}")
            self._status.showMessage(f"Load failed: {exc}")
            return
        self._loaded_series = loaded
        self._viewer.set_series(loaded)
        self._center_stack.setCurrentWidget(self._viewer)
        self._update_metadata_for_slice(0)

    def _on_instance_selected(self, _series: SeriesRef, idx: int) -> None:
        if self._loaded_series is None:
            return
        self._viewer.set_slice_index(idx)

    def _on_slice_changed(self, idx: int) -> None:
        self._update_metadata_for_slice(idx)

    def _update_metadata_for_slice(self, idx: int) -> None:
        if self._loaded_series is None:
            return
        ds = self._loaded_series.datasets[idx]
        path = self._loaded_series.series_ref.instances[idx].file_path
        self._metadata.show_dataset(ds, file_path=str(path))
        n = self._loaded_series.volume.shape[0]
        self._status.showMessage(f"Slice {idx + 1} / {n}  ·  {path.name}")

    # ---- Upload ----

    def _on_upload_requested(self) -> None:
        if self._loaded_series is None:
            return
        idx = self._viewer.current_slice_index()
        if idx < 0 or idx >= len(self._loaded_series.raw_bytes):
            return
        dicom_bytes = self._loaded_series.raw_bytes[idx]
        sop_uid = self._loaded_series.datasets[idx].SOPInstanceUID

        self._metadata.set_upload_busy(True)
        self._metadata.set_status("Uploading…", color="#666")

        self._upload_worker = UploadWorker(
            api_url=self.config.api_url,
            dicom_bytes=dicom_bytes,
            sop_uid=str(sop_uid),
        )
        self._upload_worker.succeeded.connect(self._on_upload_succeeded)
        self._upload_worker.failed.connect(self._on_upload_failed)
        self._upload_worker.finished.connect(self._upload_worker.deleteLater)
        self._upload_worker.start()

    def _on_upload_succeeded(self, result: dict) -> None:
        checksum = result.get("checksum_sha256", "")
        short = checksum[:12] if checksum else "?"
        self._metadata.set_status(f"Uploaded ✓  (sha256: {short}…)", color="#0a6b1f")
        self._metadata.set_upload_busy(False)
        self._upload_worker = None

    def _on_upload_failed(self, message: str) -> None:
        self._metadata.set_status(f"Failed: {message}", color="#a4282b")
        self._metadata.set_upload_busy(False)
        self._upload_worker = None

    # ---- Settings ----

    def _on_settings_requested(self) -> None:
        dialog = SettingsDialog(self.config.api_url, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            new_url = dialog.url() or self.config.api_url
            self.config.api_url = new_url
            self._status.showMessage(f"API URL set to {new_url}")
