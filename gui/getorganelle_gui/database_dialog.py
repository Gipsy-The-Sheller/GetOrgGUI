"""Non-modal database manager backed by get_organelle_config.py."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt
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

from .models import (
    DATABASE_TYPES,
    MODE_DATABASE,
    ORGANELLES,
    RunConfig,
    STATUS_SUCCESS,
)
from .pages.common import caption, hint
from .runner import JobRunner
from .widgets import Badge, LogView

ACTION_LABELS = {
    "install": "Installing",
    "update": "Updating",
    "remove": "Removing",
}
PAIRED_TYPES = {"embplant_pt", "embplant_mt"}


class DatabaseDialog(QDialog):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self.setWindowTitle("Databases")
        self.setMinimumSize(860, 620)
        self.setModal(False)
        self.runner = JobRunner(self)
        self.runner.log_line.connect(self._on_log)
        self.runner.stage_changed.connect(self._on_stage)
        self.runner.tick.connect(self._on_tick)
        self.runner.completed.connect(self._on_completed)
        self.runner.failed.connect(self._on_failed)
        self._action = "install"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Seed and label databases")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(
            caption(
                "GetOrganelle downloads a seed FASTA and a BLAST label database "
                "for each selected organelle type. Tick any supported type, or "
                "install every missing database in one go. “Unknown organelle” "
                "uses a custom seed and gene FASTA instead and has no "
                "downloadable database."
            )
        )

        self.table = QTableWidget(len(DATABASE_TYPES), 5)
        self.table.setHorizontalHeaderLabels(
            ["Select", "Organelle", "Seed", "Label", "Status"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(250)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeToContents
            )
        self.table.itemChanged.connect(self._selection_changed)
        layout.addWidget(self.table)

        controls = QHBoxLayout()
        self.install_button = QPushButton("Install selected")
        self.install_button.setObjectName("PrimaryButton")
        self.install_button.setToolTip(
            "Run: get_organelle_config.py -a <selected types>"
        )
        self.install_button.clicked.connect(self._install_selected)
        self.missing_button = QPushButton("Install missing")
        self.missing_button.setToolTip(
            "Install every supported seed/label database that is not present"
        )
        self.missing_button.clicked.connect(self._install_missing)
        self.update_button = QPushButton("Update installed")
        self.update_button.setToolTip(
            "Run: get_organelle_config.py --update (all installed databases)"
        )
        self.update_button.clicked.connect(self._update_installed)
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.setToolTip(
            "Run: get_organelle_config.py -r <selected types>"
        )
        self.remove_button.clicked.connect(self._remove_selected)
        self.check_button = QPushButton("Check again")
        self.check_button.clicked.connect(self._refresh)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        controls.addWidget(self.install_button)
        controls.addWidget(self.missing_button)
        controls.addWidget(self.update_button)
        controls.addWidget(self.remove_button)
        controls.addWidget(self.check_button)
        controls.addStretch(1)
        controls.addWidget(self.close_button)
        layout.addLayout(controls)

        status_row = QHBoxLayout()
        self.badge = Badge("Idle", "idle")
        self.stage_label = caption("No database operation running.")
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
                "The table shows every database that GetOrganelleDB ships; "
                "closing this window while a download runs asks before cancelling."
            )
        )
        self._refresh()

    # ------------------------------------------------------------------ table
    def _refresh(self) -> None:
        self.wb.refresh_databases()
        self.table.blockSignals(True)
        for row, key in enumerate(DATABASE_TYPES):
            meta = ORGANELLES[key]
            status = self.wb.db_status.get(key)
            seed = bool(status and status.seed)
            label = bool(status and status.label_db)
            select_item = QTableWidgetItem("")
            select_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
            )
            select_item.setCheckState(Qt.Unchecked)
            select_item.setData(Qt.UserRole, key)
            self.table.setItem(row, 0, select_item)
            self.table.setItem(row, 1, QTableWidgetItem(meta["label"]))
            self.table.setItem(
                row, 2, QTableWidgetItem("✓ present" if seed else "⚠ missing")
            )
            self.table.setItem(
                row, 3, QTableWidgetItem("✓ present" if label else "⚠ missing")
            )
            self.table.setItem(
                row, 4, QTableWidgetItem("✓ Ready" if (seed and label) else "Incomplete")
            )
            tooltip = (
                f"{meta['label']}\n{meta['detail']}\n"
                f"Database folder: {self.wb.deps.config_dir or '~/.GetOrganelle'}"
            )
            for column in range(1, 5):
                item = self.table.item(row, column)
                if item is not None:
                    item.setToolTip(tooltip)
        self.table.blockSignals(False)
        self._selection_changed()

    def _selected_types(self) -> List[str]:
        selected: List[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                key = item.data(Qt.UserRole)
                if key:
                    selected.append(str(key))
        return selected

    def _missing_types(self) -> List[str]:
        missing = []
        for key in DATABASE_TYPES:
            status = self.wb.db_status.get(key)
            if status is None or not status.ready:
                missing.append(key)
        return missing

    def _installed_types(self) -> List[str]:
        installed = []
        for key in DATABASE_TYPES:
            status = self.wb.db_status.get(key)
            if status is not None and status.ready:
                installed.append(key)
        return installed

    def _selection_changed(self, _item=None) -> None:
        self._update_buttons()

    def _update_buttons(self) -> None:
        running = self.runner.is_running
        selected = bool(self._selected_types())
        missing = bool(self._missing_types())
        installed = bool(self._installed_types())
        self.install_button.setEnabled(selected and not running)
        self.missing_button.setEnabled(missing and not running)
        self.update_button.setEnabled(installed and not running)
        self.remove_button.setEnabled(selected and not running)
        self.check_button.setEnabled(not running)
        self.table.setEnabled(not running)

    # ------------------------------------------------------------------- run
    @staticmethod
    def _install_types(types: List[str]) -> List[str]:
        """Keep land-plant plastome and mitogenome databases paired."""
        selected = set(types)
        if selected & PAIRED_TYPES:
            selected |= PAIRED_TYPES
        return [key for key in DATABASE_TYPES if key in selected]

    def _install_selected(self) -> None:
        types = self._install_types(self._selected_types())
        if types:
            self._start_action("install", types)

    def _install_missing(self) -> None:
        types = self._install_types(self._missing_types())
        if types:
            self._start_action("install", types)
        else:
            self.badge.set_state("success", "Complete")
            self.stage_label.setText("All supported databases are already installed.")
            self._set_status("All supported databases are already installed.")

    def _update_installed(self) -> None:
        if self._installed_types():
            self._start_action("update", [])

    def _remove_selected(self) -> None:
        types = self._selected_types()
        if not types:
            return
        labels = ", ".join(ORGANELLES[key]["label"] for key in types)
        answer = QMessageBox.question(
            self,
            "Remove selected databases?",
            f"Remove the seed and label databases for:\n\n{labels}\n\n"
            "This cannot be undone without downloading them again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._start_action("remove", types)

    def _start_action(self, action: str, types: List[str]) -> None:
        if self.runner.is_running:
            return
        if action in ("install", "remove") and not types:
            return
        self._action = action
        type_value = ",".join(types)
        config = RunConfig(
            mode=MODE_DATABASE,
            organelle=type_value or "embplant_pt",
            database_types=type_value,
            database_action=action,
            output_root=str(Path(self.wb.settings.workspace_root) / "runs"),
            run_name="database-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
            config_dir=self.wb.settings.config_dir.strip(),
        )
        label = ACTION_LABELS.get(action, action.title())
        self.log.clear()
        self.badge.set_state("running", label)
        self.install_button.setEnabled(False)
        self.missing_button.setEnabled(False)
        self.update_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self.progress.setValue(0)
        self.stage_label.setText(f"Starting database {action}…")
        self._set_status(f"Starting database {action}…")
        self.runner.start(
            config, self.wb.settings, tool_version=self.wb.deps.getorganelle_version
        )
        self._update_buttons()

    def _set_status(self, message: str) -> None:
        self.badge.setToolTip(message)

    def _on_log(self, text: str, kind: str) -> None:
        self.log.append_line(text, kind)

    def _on_stage(self, index: int, total: int, label: str) -> None:
        if total:
            self.progress.setValue(int(min(index, total) / total * 100))
        self.stage_label.setText(label)

    def _on_tick(self, text: str) -> None:
        self.elapsed.setText(text)

    def _on_completed(self, result) -> None:
        success = result.status == STATUS_SUCCESS
        if success:
            self.badge.set_state("success", "Done")
            self.stage_label.setText(
                "Database operation finished."
                if self._action != "install"
                else "Database installation finished."
            )
        else:
            self.badge.set_state("error", "Failed")
            self.stage_label.setText("Database operation failed; see the log above.")
        self.progress.setValue(100 if success else 0)
        self._refresh()

    def _on_failed(self, message: str) -> None:
        self.badge.set_state("error", "Failed")
        self.stage_label.setText("Database operation failed; see the log above.")
        self._update_buttons()

    # ----------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.runner.is_running:
            answer = QMessageBox.question(
                self,
                "Cancel database operation?",
                "A database download is still running. Cancel it and close the window?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.runner.cancel()
        event.accept()
