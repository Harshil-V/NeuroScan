"""Left-side study/series/instance tree."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.dicom.loader import InstanceRef, SeriesRef, StudyRef

ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_PAYLOAD = Qt.ItemDataRole.UserRole + 1


class BrowserPanel(QWidget):
    seriesSelected = Signal(object)  # SeriesRef
    instanceSelected = Signal(object, int)  # SeriesRef, instance index within series

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Studies / Series / Instances"])
        self._tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._tree)

        self._studies: list[StudyRef] = []

    def set_studies(self, studies: list[StudyRef]) -> None:
        self._studies = studies
        self._tree.clear()
        for study in studies:
            study_item = QTreeWidgetItem(
                [self._study_label(study)],
            )
            study_item.setData(0, ROLE_KIND, "study")
            study_item.setData(0, ROLE_PAYLOAD, study)
            for series in study.series:
                series_item = QTreeWidgetItem([self._series_label(series)])
                series_item.setData(0, ROLE_KIND, "series")
                series_item.setData(0, ROLE_PAYLOAD, series)
                for idx, inst in enumerate(series.instances):
                    inst_item = QTreeWidgetItem([self._instance_label(inst, idx)])
                    inst_item.setData(0, ROLE_KIND, "instance")
                    inst_item.setData(0, ROLE_PAYLOAD, (series, idx))
                    series_item.addChild(inst_item)
                study_item.addChild(series_item)
            self._tree.addTopLevelItem(study_item)
            study_item.setExpanded(True)

    def _study_label(self, study: StudyRef) -> str:
        bits = []
        if study.patient_id:
            bits.append(study.patient_id)
        if study.study_date:
            bits.append(study.study_date)
        if study.study_description:
            bits.append(study.study_description)
        if not bits:
            bits.append(study.study_instance_uid[:24] + "…")
        return "📁 " + " · ".join(bits)

    def _series_label(self, series: SeriesRef) -> str:
        bits = []
        if series.modality:
            bits.append(series.modality)
        if series.series_number is not None:
            bits.append(f"#{series.series_number}")
        if series.series_description:
            bits.append(series.series_description)
        bits.append(f"({len(series.instances)} inst)")
        return "📂 " + " · ".join(bits)

    def _instance_label(self, inst: InstanceRef, idx: int) -> str:
        n = inst.instance_number if inst.instance_number is not None else idx + 1
        return f"  {n}"

    def _on_selection_changed(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        kind = item.data(0, ROLE_KIND)
        payload = item.data(0, ROLE_PAYLOAD)
        if kind == "series":
            self.seriesSelected.emit(payload)
        elif kind == "instance":
            series, idx = payload
            self.seriesSelected.emit(series)
            self.instanceSelected.emit(series, idx)
