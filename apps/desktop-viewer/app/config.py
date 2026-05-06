"""Persistent settings via QSettings.

Stored under the macOS plist `com.NeuroScan.DesktopViewer.plist`,
the Linux equivalent under `~/.config/NeuroScan/DesktopViewer.conf`,
or the Windows registry under HKCU\\Software\\NeuroScan\\DesktopViewer.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

DEFAULT_API_URL = "http://localhost:8000"


class Config:
    def __init__(self) -> None:
        self._settings = QSettings("NeuroScan", "DesktopViewer")

    @property
    def api_url(self) -> str:
        value = self._settings.value("api_url", DEFAULT_API_URL)
        return str(value) if value else DEFAULT_API_URL

    @api_url.setter
    def api_url(self, value: str) -> None:
        self._settings.setValue("api_url", value)
        self._settings.sync()
