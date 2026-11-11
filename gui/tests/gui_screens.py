"""Render every workflow page with a synthetic result for visual review."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
GUI_ROOT = Path(__file__).resolve().parents[1]
if str(GUI_ROOT) not in sys.path:
    sys.path.insert(0, str(GUI_ROOT))

from PyQt5.QtWidgets import QApplication  # noqa: E402

from getorganelle_gui.main_window import MainWindow  # noqa: E402
from getorganelle_gui.models import MODE_READS, RunConfig  # noqa: E402
from getorganelle_gui.results import build_run_result  # noqa: E402
from getorganelle_gui.settings import Settings  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "build"
OUT.mkdir(exist_ok=True)
TEMP = Path(tempfile.mkdtemp(prefix="getorganelle-screens-"))
os.environ["GETORGANELLE_WORKBENCH_HOME"] = str(TEMP / "home")


def make_inputs():
    r1 = TEMP / "sample_1.fq"
    r2 = TEMP / "sample_2.fq"
    for path, tag in ((r1, "1"), (r2, "2")):
        path.write_text(
            f"@read{tag}\nACGTACGTACGT\n+\nIIIIIIIIIIII\n",
            encoding="utf-8",
        )
    return r1, r2


def make_result(window):
    config = RunConfig(
        mode=MODE_READS,
        reads_1=str(TEMP / "sample_1.fq"),
        reads_2=str(TEMP / "sample_2.fq"),
        organelle="embplant_pt",
        output_root=str(TEMP / "runs"),
        run_name="sample_embplant_pt",
        threads=8,
        rounds=15,
    )
    out = config.output_dir
    out.mkdir(parents=True)
    (out / "sample_embplant_pt.K65.scaffolds.graph1.1.path_sequence.fasta").write_text(
        ">scaffold_1\nACGTACGTACGTACGTACGTACGTACGTACGTACGT\n>scaffold_2\nGGCCGGCCGGCCGGCC\n",
        encoding="utf-8",
    )
    (out / "sample_embplant_pt.K65.contigs.graph1.path_sequence.gfa").write_text(
        "H\tVN:Z:1.0\nS\t1\tACGTACGTACGT\nL\t1\t+\t2\t+\t0M\nS\t2\tGGCCGGCC\n",
        encoding="utf-8",
    )
    (out / "get_org.log.txt").write_text(
        "2026-01-01 - INFO: Making seed reads\n"
        "2026-01-01 - INFO: Assembling using SPAdes\n"
        "2026-01-01 - WARNING: Example warning shown in the results page.\n"
        "2026-01-01 - INFO: Writing output\n",
        encoding="utf-8",
    )
    result = build_run_result(
        config,
        run_id="20260101-120000_sample",
        exit_code=0,
        log_lines=[
            "Pre-reading fastq ...",
            "Making seed reads ...",
            "Assembling using SPAdes ...",
            "Writing output ...",
        ],
        started_at="2026-01-01T12:00:00",
        finished_at="2026-01-01T12:02:30",
        elapsed_s=150.0,
    )
    result.command = ["python", "get_organelle_from_reads.py", "-1", str(TEMP / "sample_1.fq")]
    window.result = result
    window.run_page.show_result(result)
    window.results_page.show_result(result)
    window.job_center.set_result(result)
    window._update_rail_status()
    window.inspector.refresh()


def render(window, app, name):
    for _ in range(4):
        app.processEvents()
    path = OUT / f"gui_{name}.png"
    window.grab().save(str(path))
    print(path)


def main():
    r1, r2 = make_inputs()
    app = QApplication([])
    settings = Settings.load()
    settings.workspace_root = str(TEMP / "runs")
    window = MainWindow(settings)
    window.resize(1440, 900)
    window.config.reads_1 = str(r1)
    window.config.reads_2 = str(r2)
    window.config.run_name = "sample_embplant_pt"
    window.inputs_page.load_from_config()
    window.show()
    for _ in range(4):
        app.processEvents()
    render(window, app, "1_inputs")
    window.show_page("parameters")
    window.parameters_page.advanced.setExpanded(True)
    render(window, app, "2_parameters")
    make_result(window)
    window.run_page.append_log("Pre-reading fastq ...", "output")
    window.run_page.append_log("Making seed reads ...", "stage")
    window.run_page.append_log("WARNING: Example warning line.", "warning")
    window.show_page("run")
    render(window, app, "3_run")
    window.show_page("results")
    render(window, app, "4_results")
    window.runner.cancel()
    window.close()
    app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
