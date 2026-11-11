"""Run page: review, validate, start and watch a non-modal job."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    MODE_ASSEMBLY,
    MODE_DATABASE,
    MODE_READS,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SUCCESS,
    STATUS_WARNING,
    organelle_label,
)
from ..widgets import Badge, Card, LogView, Separator
from .common import ScrollPage, caption, page_header


class RunPage(ScrollPage):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self._build_ui()

    def _build_ui(self) -> None:
        self.add(
            page_header(
                "Run",
                "Review the setup, fix any inline issues, then start the assembly. The job runs in the background.",
            )
        )

        self.banner = Card("")
        self.banner.hide()
        self.banner_badge = Badge("Idle", "idle")
        self.banner_text = QLabel("")
        self.banner_text.setWordWrap(True)
        banner_top = QHBoxLayout()
        banner_top.addWidget(self.banner_badge)
        banner_top.addWidget(self.banner_text, 1)
        self.banner.body.addLayout(banner_top)
        banner_actions = QHBoxLayout()
        banner_actions.addStretch(1)
        self.banner_results_button = QPushButton("View results  →")
        self.banner_results_button.setObjectName("PrimaryButton")
        self.banner_results_button.clicked.connect(lambda: self.wb.show_page("results"))
        self.banner_folder_button = QPushButton("Open output folder")
        self.banner_folder_button.clicked.connect(self.wb.open_output_folder)
        banner_actions.addWidget(self.banner_folder_button)
        banner_actions.addWidget(self.banner_results_button)
        self.banner.body.addLayout(banner_actions)
        self.add(self.banner)

        self.summary_card = Card("Run setup")
        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.mode_value = QLabel("")
        self.input_value = QLabel("")
        self.input_value.setWordWrap(True)
        self.organelle_value = QLabel("")
        self.output_value = QLabel("")
        self.output_value.setWordWrap(True)
        self.threads_value = QLabel("")
        self.scheme_value = QLabel("")
        form.addRow("Mode", self.mode_value)
        form.addRow("Input", self.input_value)
        form.addRow("Organelle", self.organelle_value)
        form.addRow("Output", self.output_value)
        form.addRow("Threads", self.threads_value)
        form.addRow("Extending", self.scheme_value)
        self.preprocess_value = QLabel("")
        self.preprocess_value.setWordWrap(True)
        form.addRow("Preprocess", self.preprocess_value)
        self.summary_card.body.addLayout(form)
        self.summary_card.body.addWidget(Separator())

        self.validation_title = QLabel("Readiness")
        self.validation_title.setObjectName("CardTitle")
        self.summary_card.body.addWidget(self.validation_title)
        self.validation_container = QWidget()
        self.validation_layout = QVBoxLayout(self.validation_container)
        self.validation_layout.setContentsMargins(0, 0, 0, 0)
        self.validation_layout.setSpacing(8)
        self.summary_card.body.addWidget(self.validation_container)

        actions = QHBoxLayout()
        self.run_button = QPushButton("▶  Run GetOrganelle")
        self.run_button.setObjectName("PrimaryButton")
        self.run_button.setToolTip("Start the job (F5).")
        self.run_button.clicked.connect(self.wb.start_run)
        self.copy_button = QPushButton("Copy command")
        self.copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.wb.command_display())
        )
        self.settings_button = QPushButton("Open settings")
        self.settings_button.clicked.connect(self.wb.open_settings)
        actions.addWidget(self.run_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.settings_button)
        actions.addStretch(1)
        self.summary_card.body.addLayout(actions)
        self.add(self.summary_card)

        self.log_card = Card(
            "Live log",
            "Progress is streamed here and mirrored to workbench_run.log in the output folder.",
        )
        log_toolbar = QHBoxLayout()
        self.log_badge = Badge("Idle", "idle")
        self.stage_label = caption("Waiting for a run.")
        self.elapsed_label = caption("00:00")
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self._on_auto_scroll)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_log)
        self.console_button = QPushButton("Open console window")
        self.console_button.clicked.connect(self.wb.open_console)
        log_toolbar.addWidget(self.log_badge)
        log_toolbar.addWidget(self.stage_label, 1)
        log_toolbar.addWidget(self.elapsed_label)
        log_toolbar.addWidget(self.auto_scroll_check)
        log_toolbar.addWidget(self.clear_button)
        log_toolbar.addWidget(self.console_button)
        self.log_card.body.addLayout(log_toolbar)
        self.log_view = LogView()
        self.log_view.setMinimumHeight(190)
        self.log_card.body.addWidget(self.log_view)
        self.add(self.log_card)
        self.add_stretch()

    # ------------------------------------------------------------------ update
    def refresh_summary(self, issues) -> None:
        config = self.wb.config
        mode_label = {
            MODE_READS: "Reads",
            MODE_ASSEMBLY: "Assembly graph",
            MODE_DATABASE: "Database",
        }.get(config.mode, config.mode)
        self.mode_value.setText(mode_label)
        if config.mode == MODE_ASSEMBLY:
            self.input_value.setText(config.graph or "No graph selected")
        else:
            parts = [path for path in (config.reads_1, config.reads_2, config.unpaired) if path]
            self.input_value.setText("\n".join(parts) if parts else "No reads selected")
        self.organelle_value.setText(organelle_label(config.organelle))
        self.output_value.setText(str(config.output_dir))
        self.threads_value.setText(str(config.threads))
        if config.mode == MODE_READS:
            scheme = (
                f"-R {config.rounds} · k-mers "
                + (config.kmers if config.kmer_mode == "custom" else "auto")
            )
        else:
            scheme = "Graph mode"
        self.scheme_value.setText(scheme)
        if config.preprocess and config.mode == MODE_READS:
            self.preprocess_value.setText("fastp adapter trimming / filtering")
        else:
            self.preprocess_value.setText("Off")

        while self.validation_layout.count():
            item = self.validation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        errors = [issue for issue in issues if issue.is_error]
        warnings = [issue for issue in issues if issue.level == "warning"]
        if not issues:
            self._add_validation_row("success", "Ready to run", "All required inputs and components are available.")
        for issue in errors[:8]:
            self._add_validation_row("error", issue.message, issue.hint)
        for issue in warnings[:6]:
            self._add_validation_row("warning", issue.message, issue.hint)
        if len(errors) > 8:
            self._add_validation_row("info", f"{len(errors) - 8} more errors", "Fix the fields highlighted above.")
        self.run_button.setEnabled(not errors and not self.wb.runner.is_running)

    def _add_validation_row(self, state: str, message: str, detail: str = "") -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        badge = Badge("", state)
        text = QLabel(message + (("\n" + detail) if detail else ""))
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(badge, 0, Qt.AlignTop)
        layout.addWidget(text, 1)
        self.validation_layout.addWidget(row)

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.run_button.setText("Running…" if running else "▶  Run GetOrganelle")
        if running:
            self.banner.hide()
            self.log_badge.set_state("running", "Running")
        elif self.log_badge.property("state") == "running":
            self.log_badge.set_state("idle", "Idle")

    def append_log(self, text: str, kind: str) -> None:
        self.log_view.append_line(text, kind)

    def clear_log(self) -> None:
        self.log_view.clear()

    def set_stage(self, index: int, total: int, label: str) -> None:
        if index >= total:
            self.stage_label.setText(label)
        else:
            self.stage_label.setText(f"Step {index}/{total} · {label}")

    def set_elapsed(self, text: str) -> None:
        self.elapsed_label.setText(text)

    def _on_auto_scroll(self, enabled: bool) -> None:
        self.log_view.auto_scroll = enabled

    def show_result(self, result) -> None:
        self.banner.show()
        if result.status == STATUS_SUCCESS:
            self.banner_badge.set_state("success", "Completed")
        elif result.status == STATUS_WARNING:
            self.banner_badge.set_state("warning", "Completed with warnings")
        elif result.status == STATUS_CANCELLED:
            self.banner_badge.set_state("warning", "Cancelled")
        else:
            self.banner_badge.set_state("error", "Failed")
        if result.status == STATUS_SUCCESS:
            text = (
                f"{len(result.sequence_items)} sequence file(s), "
                f"{result.total_bp:,} bp in {result.elapsed_s:.1f} s."
            )
        elif result.status == STATUS_CANCELLED:
            text = "The run was cancelled. Partial files may remain in the output folder."
        elif result.status == STATUS_ERROR:
            text = result.error_message.splitlines()[0] if result.error_message else "The run failed."
        else:
            text = "GetOrganelle finished, but no organelle sequence file was produced. Inspect the log and graph."
        self.banner_text.setText(text)
        self.banner_results_button.setVisible(bool(result.items))
        self.log_badge.set_state(
            "success"
            if result.status == STATUS_SUCCESS
            else "warning"
            if result.status in (STATUS_WARNING, STATUS_CANCELLED)
            else "error",
            "Completed"
            if result.status == STATUS_SUCCESS
            else "Warning"
            if result.status == STATUS_WARNING
            else "Cancelled"
            if result.status == STATUS_CANCELLED
            else "Failed",
        )
        self.stage_label.setText(f"Finished in {result.elapsed_s:.1f} s")
