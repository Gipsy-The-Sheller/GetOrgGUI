"""QApplication entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from . import APP_NAME, __version__
from .main_window import MainWindow
from .settings import Settings


def main(argv=None) -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("GetOrganelle")
    app.setApplicationVersion(__version__)
    icon_dir = Path(__file__).resolve().parent / "icons"
    for icon_name in ("getorg.svg", "workbench.svg"):
        icon = icon_dir / icon_name
        if icon.is_file():
            app.setWindowIcon(QIcon(str(icon)))
            break
    window = MainWindow(Settings.load())
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
