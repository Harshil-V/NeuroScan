"""NeuroScan Desktop Viewer entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def main() -> int:
    QCoreApplication.setOrganizationName("NeuroScan")
    QCoreApplication.setOrganizationDomain("neuroscan.local")
    QCoreApplication.setApplicationName("DesktopViewer")

    app = QApplication(sys.argv)

    # MainWindow is wired in Task C2.
    from app.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
