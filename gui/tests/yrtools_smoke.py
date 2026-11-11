"""Offscreen smoke test for the YRTools/YR-MPE host entry point.

    QT_QPA_PLATFORM=offscreen python gui/tests/yrtools_smoke.py

Checks that the manifest entry constructs the workbench, that
``MainWindow.run()`` returns ``self``, that the widget can be inserted into a
host tab, and that embedded mode does not overwrite the host application
stylesheet.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["GETORGANELLE_WORKBENCH_HOME"] = tempfile.mkdtemp(prefix="getorg-yrtools-")
GUI_ROOT = Path(__file__).resolve().parents[1]
if str(GUI_ROOT) not in sys.path:
    sys.path.insert(0, str(GUI_ROOT))

from PyQt5.QtWidgets import QApplication, QTabWidget  # noqa: E402

from getorganelle_gui.yrtools_entry import GetOrganelleEntry  # noqa: E402


def main() -> int:
    app = QApplication([])
    host_style = "QWidget { background: #123456; }"
    app.setStyleSheet(host_style)
    entry = GetOrganelleEntry(
        config={"meta": {"name": "GetOrganelle Workbench"}},
        plugin_path=str(GUI_ROOT),
    )
    widget = entry.run()
    if widget is None or widget.run() is not widget:
        raise SystemExit("MainWindow.run() did not return self")
    if app.styleSheet() != host_style:
        raise SystemExit("embedded mode overwrote the host stylesheet")
    if not widget.styleSheet():
        raise SystemExit("embedded mode did not apply the local stylesheet")
    tabs = QTabWidget()
    tabs.resize(1100, 760)
    tabs.addTab(widget, "GetOrganelle")
    tabs.show()
    for _ in range(5):
        app.processEvents()
    print("YRTools entry:", type(widget).__name__)
    print("host style preserved:", app.styleSheet() == host_style)
    print("run() returns self:", widget.run() is widget)
    widget.runner.cancel()
    tabs.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
