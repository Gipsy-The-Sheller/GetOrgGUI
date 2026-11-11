"""Offscreen smoke test: build the window, render light/dark screenshots.

Run with:
    QT_QPA_PLATFORM=offscreen python gui/tests/gui_smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI_ROOT = Path(__file__).resolve().parents[1]
if str(GUI_ROOT) not in sys.path:
    sys.path.insert(0, str(GUI_ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

from getorganelle_gui.main_window import MainWindow  # noqa: E402
from getorganelle_gui.models import MODE_READS  # noqa: E402
from getorganelle_gui.settings import Settings  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "build"
OUT.mkdir(exist_ok=True)


def main() -> int:
    home = tempfile.mkdtemp(prefix="getorganelle-gui-")
    os.environ["GETORGANELLE_WORKBENCH_HOME"] = home
    app = QApplication([])
    settings = Settings.load()
    settings.workspace_root = str(Path(home) / "runs")
    window = MainWindow(settings)
    window.config.mode = MODE_READS
    window.config.run_name = "demo_embplant_pt"
    window.inputs_page.load_from_config()
    window.show()
    for _ in range(4):
        app.processEvents()
    light = OUT / "gui_preview_light.png"
    window.grab().save(str(light))
    window.toggle_theme()
    for _ in range(4):
        app.processEvents()
    dark = OUT / "gui_preview_dark.png"
    window.grab().save(str(dark))
    print("light:", light)
    print("dark:", dark)
    print("issues:", [(issue.level, issue.field) for issue in window.issues][:12])
    window.runner.cancel()
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
