"""Center pane: pyqtgraph image view + slice/window/level sliders + presets."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.dicom.series import LoadedSeries
from app.dicom.window_level import apply_window_level

WL_PRESETS: dict[str, tuple[float, float]] = {
    # name -> (window, level)
    "Brain": (80, 40),
    "Bone": (2000, 300),
    "Lung": (1500, -600),
    "Soft Tissue": (400, 50),
}


class ViewerPanel(QWidget):
    sliceChanged = Signal(int)  # current slice index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._series: LoadedSeries | None = None
        self._slice_idx = 0
        self._level = 0.0
        self._window = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._image_view = pg.ImageView()
        self._image_view.ui.histogram.hide()
        self._image_view.ui.roiBtn.hide()
        self._image_view.ui.menuBtn.hide()
        self._image_view.getView().setBackgroundColor("#1a1a1a")
        self._image_view.installEventFilter(self)
        self._image_view.scene.installEventFilter(self)
        layout.addWidget(self._image_view, 1)

        layout.addWidget(self._build_slice_controls())
        layout.addWidget(self._build_wl_controls())
        layout.addWidget(self._build_preset_row())

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_slice_controls(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 0)
        self._slice_slider = QSlider(Qt.Orientation.Horizontal)
        self._slice_slider.setMinimum(0)
        self._slice_slider.setMaximum(0)
        self._slice_slider.valueChanged.connect(self._on_slice_slider_changed)
        self._slice_label = QLabel("Slice 0 / 0")
        self._slice_label.setMinimumWidth(110)
        h.addWidget(QLabel("Slice"))
        h.addWidget(self._slice_slider, 1)
        h.addWidget(self._slice_label)
        return row

    def _build_wl_controls(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 0)
        self._level_slider = QSlider(Qt.Orientation.Horizontal)
        self._window_slider = QSlider(Qt.Orientation.Horizontal)
        self._level_slider.valueChanged.connect(self._on_wl_slider_changed)
        self._window_slider.valueChanged.connect(self._on_wl_slider_changed)
        self._wl_label = QLabel("L: 0  W: 0")
        self._wl_label.setMinimumWidth(160)
        h.addWidget(QLabel("Level"))
        h.addWidget(self._level_slider, 1)
        h.addWidget(QLabel("Window"))
        h.addWidget(self._window_slider, 1)
        h.addWidget(self._wl_label)
        return row

    def _build_preset_row(self) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 4)
        for name in WL_PRESETS:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _checked=False, n=name: self._apply_preset(n))
            h.addWidget(btn)
        default_btn = QPushButton("Default")
        default_btn.clicked.connect(self._reset_wl)
        h.addWidget(default_btn)
        h.addStretch(1)
        return row

    # ---- public API ----

    def set_series(self, loaded: LoadedSeries) -> None:
        self._series = loaded
        n = loaded.volume.shape[0]
        self._slice_idx = 0

        vmin = float(np.min(loaded.volume))
        vmax = float(np.max(loaded.volume))
        self._slice_slider.blockSignals(True)
        self._slice_slider.setMaximum(max(n - 1, 0))
        self._slice_slider.setValue(0)
        self._slice_slider.blockSignals(False)

        self._level_slider.blockSignals(True)
        self._window_slider.blockSignals(True)
        # Map level/window into integer slider range matching pixel-value extents.
        self._level_slider.setMinimum(int(vmin))
        self._level_slider.setMaximum(int(vmax))
        self._level_slider.setValue(int(loaded.default_level))
        self._window_slider.setMinimum(1)
        self._window_slider.setMaximum(int(max(vmax - vmin, 1)))
        self._window_slider.setValue(int(loaded.default_window))
        self._level_slider.blockSignals(False)
        self._window_slider.blockSignals(False)

        self._level = float(loaded.default_level)
        self._window = float(loaded.default_window)

        self._render()

    def set_slice_index(self, idx: int) -> None:
        if self._series is None:
            return
        idx = max(0, min(idx, self._series.volume.shape[0] - 1))
        if idx == self._slice_idx:
            return
        self._slice_idx = idx
        self._slice_slider.blockSignals(True)
        self._slice_slider.setValue(idx)
        self._slice_slider.blockSignals(False)
        self._render()
        self.sliceChanged.emit(idx)

    def current_slice_index(self) -> int:
        return self._slice_idx

    # ---- internals ----

    def _on_slice_slider_changed(self, v: int) -> None:
        self._slice_idx = v
        self._render()
        self.sliceChanged.emit(v)

    def _on_wl_slider_changed(self, _v: int) -> None:
        self._level = float(self._level_slider.value())
        self._window = float(max(self._window_slider.value(), 1))
        self._render()

    def _apply_preset(self, name: str) -> None:
        window, level = WL_PRESETS[name]
        self._level_slider.blockSignals(True)
        self._window_slider.blockSignals(True)
        self._level_slider.setValue(int(level))
        self._window_slider.setValue(int(window))
        self._level_slider.blockSignals(False)
        self._window_slider.blockSignals(False)
        self._level = float(level)
        self._window = float(window)
        self._render()

    def _reset_wl(self) -> None:
        if self._series is None:
            return
        self._level_slider.setValue(int(self._series.default_level))
        self._window_slider.setValue(int(self._series.default_window))

    def _render(self) -> None:
        if self._series is None:
            return
        slice_arr = self._series.volume[self._slice_idx]
        rendered = apply_window_level(slice_arr, level=self._level, window=self._window)
        # pyqtgraph expects [W, H] for default axisOrder; transpose so (rows, cols)
        # numpy array displays correctly.
        self._image_view.setImage(rendered.T, autoLevels=False, autoRange=False)
        n = self._series.volume.shape[0]
        self._slice_label.setText(f"Slice {self._slice_idx + 1} / {n}")
        self._wl_label.setText(f"L: {int(self._level)}  W: {int(self._window)}")

    # ---- input handling ----

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._series is None:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.set_slice_index(self._slice_idx + 1)
            event.accept()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.set_slice_index(self._slice_idx - 1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):  # type: ignore[override]
        # Plain wheel = slice nav. Ctrl/Cmd + wheel = pyqtgraph default zoom.
        if event.type() == event.Type.GraphicsSceneWheel or event.type() == event.Type.Wheel:
            modifiers = event.modifiers() if hasattr(event, "modifiers") else None
            if modifiers and (
                modifiers & Qt.KeyboardModifier.ControlModifier
                or modifiers & Qt.KeyboardModifier.MetaModifier
            ):
                return False  # let pyqtgraph zoom
            if self._series is None:
                return False
            delta = 0
            if isinstance(event, QWheelEvent):
                delta = event.angleDelta().y()
            else:
                delta = event.delta() if hasattr(event, "delta") else 0
            if delta == 0:
                return False
            step = -1 if delta > 0 else 1
            self.set_slice_index(self._slice_idx + step)
            return True
        return False
