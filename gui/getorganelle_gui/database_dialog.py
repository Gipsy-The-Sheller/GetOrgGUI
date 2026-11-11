"""Non-modal database manager backed by get_organelle_config.py."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .models import MODE_DATABASE, ORGANELLES, RunConfig, STATUS_SUCCESS
from .pages.common import caption, hint
from .runner import JobRunner
from .widgets import Badge, LogView

RECOMMENDED = "embplant_pt,embplant_mt"


class DatabaseDialog(QDialog):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self.setWindowTitle("Databases")
        self.setMinimumSize(780, 600)
        self.setModal(False)
        self.runner = JobRunner(self)
        self.runner.log_line.connect(self._on_log)
        self.runner.stage_changed.connect(self._on_stage)
        self.runner.tick.connect(self._on_tick)
        self.runner.completed.connect(self._on_completed)
        self.runner.failed.connect(self._on_failed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Seed and label databases")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(
            caption(
                "GetOrganelle needs a seed FASTA and a BLAST label database for each organelle type. "
                "Installing downloads the latest version from the GetOrganelle database repository."
            )
        )

        self.table = QTableWidget(len(ORGANELLES), 4)
        self.table.setHorizontalHeaderLabels(["Organelle", "Seed", "Label", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        controls = QHBoxLayout()
        self.install_button = QPushButton("Install plastome + mitogenome")
        self.install_button.setObjectName("PrimaryButton")
        self.install_button.setToolTip("Runs: get_organelle_config.py -a embplant_pt,embplant_mt")
        self.install_button.clicked.connect(self._install_recommended)
        self.check_button = QPushButton("Check again")
        self.check_button.clicked.connect(self._refresh)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        controls.addWidget(self.install_button)
        controls.addWidget(self.check_button)
        controls.addStretch(1)
        controls.addWidget(self.close_button)
        layout.addLayout(controls)

        status_row = QHBoxLayout()
        self.badge = Badge("Idle", "idle")
        self.stage_label = caption("No installation running.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.elapsed = caption("00:00")
        status_row.addWidget(self.badge)
        status_row.addWidget(self.progress, 1)
        status_row.addWidget(self.stage_label)
        status_row.addWidget(self.elapsed)
        layout.addLayout(status_row)

        self.log = LogView()
        self.log.setMinimumHeight(180)
        layout.addWidget(self.log, 1)
        layout.addWidget(
            hint(
                "The database lives under %USERPROFILE%\\.GetOrganelle by default. "
                "Closing this window while a download runs asks before cancelling."
            )
        )
        self._refresh()

    # ------------------------------------------------------------------ table
    def _refresh(self) -> None:
        self.wb.refresh_databases()
        for row, (key, meta) in enumerate(ORGANELLES.items()):
            status = self.wb.db_status.get(key)
            seed = bool(status and status.seed)
            label = bool(status and status.label_db)
            self.table.setItem(row, 0, QTableWidgetItem(meta["label"]))
            self.table.setItem(row, 1, QTableWidgetItem("✓ present" if seed else "⚠ missing"))
            self.table.setItem(row, 2, QTableWidgetItem("✓ present" if label else "⚠ missing"))
            ready = seed and label
            self.table.setItem(row, 3, QTableWidgetItem("✓ Ready" if ready else "Incomplete"))

    # ------------------------------------------------------------------- run
    def _install_recommended(self) -> None:
        if self.runner.is_running:
            return
        types = RECOMMENDED
        config = RunConfig(
            mode=MODE_DATABASE,
            organelle=types,
            database_types=types,
            output_root=str(Path(self.wb.settings.workspace_root) / "runs"),
            run_name="database-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
        )
        self.log.clear()
        self.badge.set_state("running", "Installing")
        self.install_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self.progress.setValue(0)
        self.stage_label.setText("Starting database download…")
        self.runner.start(
            config, self.wb.settings, tool_version=self.wb.deps.getorganelle_version
        )

    def _on_log(self, text: str, kind: str) -> None:
        self.log.append_line(text, kind)

    def _on_stage(self, index: int, total: int, label: str) -> None:
        if total:
            self.progress.setValue(int(min(index, total) / total * 100))
        self.stage_label.setText(label)

    def _on_tick(self, text: str) -> None:
        self.elapsed.setText(text)

    def _on_completed(self, result) -> None:
        self.install_button.setEnabled(True)
        self.check_button.setEnabled(True)
        self.progress.setValue(100 if result.status == STATUS_SUCCESS else 0)
        if result.status == STATUS_SUCCESS:
            self.badge.set_state("success", "Installed")
            self.stage_label.setText("Database installation finished.")
        else:
            self.badge.set_state("error", "Failed")
            self.stage_label.setText("Database installation failed; see the log above.")
        self._refresh()

    def _on_failed(self, message: str) -> None:
        self.badge.set_state("error", "Failed")

    # ----------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.runner.is_running:
            answer = QMessageBox.question(
                self,
                "Cancel database installation?",
                "A database download is still running. Cancel it and close the window?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.runner.cancel()
        event.accept()
