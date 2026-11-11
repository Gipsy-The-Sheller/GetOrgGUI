"""Run a real GetOrganelle job through the GUI's JobRunner (no interaction)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
GUI_ROOT = Path(__file__).resolve().parents[1]
if str(GUI_ROOT) not in sys.path:
    sys.path.insert(0, str(GUI_ROOT))

from PyQt5.QtCore import QTimer  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from getorganelle_gui.main_window import MainWindow  # noqa: E402
from getorganelle_gui.settings import Settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
READS = ROOT / "build" / "testdata" / "reads_err"
OUT = ROOT / "build" / "gui_run_test"


def main() -> int:
    os.environ["GETORGANELLE_WORKBENCH_HOME"] = tempfile.mkdtemp(prefix="getorg-gui-run-")
    app = QApplication([])
    settings = Settings.load()
    settings.workspace_root = str(OUT)
    window = MainWindow(settings)
    window.config.reads_1 = str(READS / "1.fq")
    window.config.reads_2 = str(READS / "2.fq")
    window.config.organelle = "embplant_pt"
    window.config.run_name = "gui_smoke"
    window.config.threads = 2
    window.config.rounds = 1
    window.config.kmer_mode = "custom"
    window.config.kmers = "21,45,65"
    window.config.overwrite = True
    window.inputs_page.load_from_config()
    window.parameters_page.load_from_config()
    window.show()

    state = {"done": False}

    def check():
        if window.result is not None:
            state["done"] = True
            result = window.result
            print("STATUS:", result.status)
            print("EXIT:", result.exit_code)
            print("ELAPSED:", round(result.elapsed_s, 1))
            print("ITEMS:", [(item.kind, item.name, item.sequences) for item in result.items])
            print("OUTPUT:", result.output_dir)
            print("RUN_JSON:", (Path(result.output_dir) / "run.json").is_file())
            app.quit()
        elif not window.runner.is_running and window.run_page.run_button.isEnabled():
            print("NO RESULT; issues:", [(i.level, i.field, i.message) for i in window.issues])
            app.quit()
        else:
            QTimer.singleShot(500, check)

    QTimer.singleShot(300, window.start_run)
    QTimer.singleShot(1200, check)
    app.exec_()
    return 0 if state["done"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
