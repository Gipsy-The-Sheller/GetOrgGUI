"""Inputs page: choose reads or an assembly graph and an output folder."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from ..models import MODE_ASSEMBLY, MODE_READS, ORGANELLES, slugify
from ..widgets import Badge, Card, FileInput
from .common import ScrollPage, caption, hint, page_header

FASTQ_FILTER = (
    "FASTQ reads (*.fq *.fastq *.fq.gz *.fastq.gz *.tar.gz);;All files (*)"
)
GRAPH_FILTER = "Assembly graph (*.gfa *.fastg);;All files (*)"


class InputsPage(ScrollPage):
    organelle_changed = pyqtSignal(str)

    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self._loading = True
        self._run_name_manual = False

        self.add(page_header("Inputs", "Choose the sequencing reads or an existing assembly graph, then name the run."))

        self._build_mode_switch()
        self._build_reads_card()
        self._build_assembly_card()
        self._build_organelle_card()
        self._build_output_card()

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.continue_button = QPushButton("Continue to parameters  →")
        self.continue_button.setObjectName("PrimaryButton")
        self.continue_button.clicked.connect(lambda: self.wb.show_page("parameters"))
        footer.addWidget(self.continue_button)
        self.add_layout(footer)
        self.add_stretch()

        self.load_from_config()
        self._loading = False
        self._mode_changed()
        self.refresh_databases()

    # ------------------------------------------------------------------ build
    def _build_mode_switch(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(caption("Input type"))
        row.addStretch(1)
        self.reads_mode_button = QPushButton("Reads")
        self.reads_mode_button.setObjectName("SegmentButton")
        self.reads_mode_button.setCheckable(True)
        self.reads_mode_button.setChecked(True)
        self.assembly_mode_button = QPushButton("Assembly graph")
        self.assembly_mode_button.setObjectName("SegmentButton")
        self.assembly_mode_button.setCheckable(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.reads_mode_button)
        self.mode_group.addButton(self.assembly_mode_button)
        self.reads_mode_button.clicked.connect(self._mode_changed)
        self.assembly_mode_button.clicked.connect(self._mode_changed)
        row.addWidget(self.reads_mode_button)
        row.addWidget(self.assembly_mode_button)
        self.add_layout(row)

    def _build_reads_card(self) -> None:
        self.reads_card = Card(
            "Sequencing reads",
            "Paired FASTQ is recommended. Single-end or unpaired reads can be added as a fallback.",
        )
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.r1_input = FileInput(filters=FASTQ_FILTER, placeholder="sample_1.fq.gz")
        self.r2_input = FileInput(filters=FASTQ_FILTER, placeholder="sample_2.fq.gz (optional)")
        self.unpaired_input = FileInput(
            filters=FASTQ_FILTER,
            placeholder="one.fq, two.fq (optional, comma-separated)",
        )
        for widget in (self.r1_input, self.r2_input, self.unpaired_input):
            widget.path_changed.connect(self._on_input_path_changed)
            widget.path_changed.connect(self._changed)
        form.addRow("Forward reads (R1)", self.r1_input)
        form.addRow("Reverse reads (R2)", self.r2_input)
        form.addRow("Unpaired reads", self.unpaired_input)
        self.reads_card.body.addLayout(form)
        self.reads_card.body.addWidget(
            hint("GetOrganelle trims and extends reads before assembly; FASTQ.GZ is accepted directly.")
        )
        self.add(self.reads_card)

    def _build_assembly_card(self) -> None:
        self.assembly_card = Card(
            "Assembly graph",
            "Run GetOrganelle's graph-only mode on a SPAdes/GetOrganelle GFA or FASTG file.",
        )
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.graph_input = FileInput(filters=GRAPH_FILTER, placeholder="assembly_graph.gfa")
        self.graph_input.path_changed.connect(self._on_input_path_changed)
        self.graph_input.path_changed.connect(self._changed)
        form.addRow("Graph file", self.graph_input)
        self.assembly_card.body.addLayout(form)
        self.assembly_card.body.addWidget(
            hint("The file suffix selects the parser: .gfa or .fastg.")
        )
        self.add(self.assembly_card)
        self.assembly_card.hide()

    def _build_organelle_card(self) -> None:
        self.organelle_card = Card(
            "Organelle",
            "The organelle type selects the seed and label databases and the default number of rounds.",
        )
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.organelle_combo = QComboBox()
        for key, meta in ORGANELLES.items():
            self.organelle_combo.addItem(meta["label"], key)
        self.organelle_combo.currentIndexChanged.connect(self._on_organelle_changed)
        form.addRow("Organelle type", self.organelle_combo)
        self.organelle_detail = caption("")
        form.addRow("", self.organelle_detail)
        db_row = QHBoxLayout()
        self.db_badge = Badge("Checking database…", "idle")
        self.manage_db_button = QPushButton("Manage databases…")
        self.manage_db_button.clicked.connect(self.wb.open_database_dialog)
        db_row.addWidget(self.db_badge)
        db_row.addStretch(1)
        db_row.addWidget(self.manage_db_button)
        form.addRow("Local database", db_row)
        self.db_detail = caption("")
        form.addRow("", self.db_detail)
        self.organelle_card.body.addLayout(form)
        self.add(self.organelle_card)

    def _build_output_card(self) -> None:
        self.output_card = Card(
            "Output",
            "Each run gets its own folder under the workspace. The run name is used for the folder and result files.",
        )
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.workspace_input = FileInput(
            mode="directory", placeholder="Workspace folder"
        )
        self.workspace_input.path_changed.connect(self._on_output_changed)
        form.addRow("Workspace", self.workspace_input)
        self.run_name_edit = QLineEdit()
        self.run_name_edit.setPlaceholderText("sample_embplant_pt")
        self.run_name_edit.textEdited.connect(self._on_run_name_edited)
        self.run_name_edit.textChanged.connect(self._on_output_changed)
        form.addRow("Run name", self.run_name_edit)
        self.output_preview = QLabel("")
        self.output_preview.setObjectName("Mono")
        self.output_preview.setWordWrap(True)
        form.addRow("Output folder", self.output_preview)
        self.overwrite_check = QCheckBox("Replace existing output in this folder")
        self.overwrite_check.setToolTip(
            "Required when the output folder already contains files. The previous contents may be overwritten."
        )
        self.overwrite_check.toggled.connect(self._changed)
        form.addRow("", self.overwrite_check)
        self.output_card.body.addLayout(form)
        self.add(self.output_card)

    # ------------------------------------------------------------------ state
    def load_from_config(self) -> None:
        config = self.wb.config
        self._loading = True
        self.reads_mode_button.setChecked(config.mode != MODE_ASSEMBLY)
        self.assembly_mode_button.setChecked(config.mode == MODE_ASSEMBLY)
        self.r1_input.setText(config.reads_1)
        self.r2_input.setText(config.reads_2)
        self.unpaired_input.setText(config.unpaired)
        self.graph_input.setText(config.graph)
        index = self.organelle_combo.findData(config.organelle)
        if index >= 0:
            self.organelle_combo.setCurrentIndex(index)
        self.workspace_input.setText(config.output_root or self.wb.settings.workspace_root)
        self.run_name_edit.setText(config.run_name)
        self.overwrite_check.setChecked(config.overwrite)
        self._loading = False
        self._update_organelle_detail()
        self._update_output_preview()

    def sync_to_config(self) -> None:
        config = self.wb.config
        config.mode = MODE_ASSEMBLY if self.assembly_mode_button.isChecked() else MODE_READS
        config.reads_1 = self.r1_input.text()
        config.reads_2 = self.r2_input.text()
        config.unpaired = self.unpaired_input.text()
        config.graph = self.graph_input.text()
        config.organelle = self.organelle_combo.currentData() or "embplant_pt"
        config.output_root = self.workspace_input.text() or self.wb.settings.workspace_root
        config.run_name = self.run_name_edit.text().strip()
        config.overwrite = self.overwrite_check.isChecked()

    def _changed(self) -> None:
        if self._loading:
            return
        self.sync_to_config()
        self._update_output_preview()
        self.wb.on_config_changed()

    def _mode_changed(self) -> None:
        reads = self.reads_mode_button.isChecked()
        self.reads_card.setVisible(reads)
        self.assembly_card.setVisible(not reads)
        if not self._loading:
            if not self._run_name_manual:
                self.sync_to_config()
                self.run_name_edit.setText(self.wb.config.suggested_run_name())
            self._changed()
        elif not self._run_name_manual and not self.run_name_edit.text():
            self.sync_to_config()
            self.run_name_edit.setText(self.wb.config.suggested_run_name())

    def _on_input_path_changed(self, path: str) -> None:
        if self._loading:
            return
        self.sync_to_config()
        if not self._run_name_manual:
            self.run_name_edit.setText(self.wb.config.suggested_run_name())
        if path:
            self.wb.settings.add_recent_input(path)

    def _on_run_name_edited(self, text: str) -> None:
        self._run_name_manual = bool(text.strip())

    def _on_output_changed(self) -> None:
        self._update_output_preview()
        self._changed()

    def _on_organelle_changed(self) -> None:
        self._update_organelle_detail()
        self.refresh_databases()
        if self._loading:
            return
        self.sync_to_config()
        if not self._run_name_manual:
            self.run_name_edit.setText(self.wb.config.suggested_run_name())
        self.organelle_changed.emit(self.wb.config.organelle)
        self._changed()

    def _update_organelle_detail(self) -> None:
        data = self.organelle_combo.currentData()
        meta = ORGANELLES.get(data, {})
        self.organelle_detail.setText(
            f"{meta.get('detail', '')}  Default -R {meta.get('rounds', 15)} · target ≈ {int(meta.get('target_size', '0')):,} bp."
        )

    def _update_output_preview(self) -> None:
        root = self.workspace_input.text().strip() or self.wb.settings.workspace_root
        name = self.run_name_edit.text().strip() or "<run name>"
        self.output_preview.setText(str(Path(root) / slugify(name)))

    # -------------------------------------------------------------- databases
    def refresh_databases(self) -> None:
        organelle = self.organelle_combo.currentData()
        status = self.wb.db_status.get(organelle)
        if status is None:
            self.db_badge.set_state("idle", "Not checked")
            self.db_detail.setText("")
            return
        if status.ready:
            self.db_badge.set_state("success", "Seed + label installed")
            self.db_detail.setText(str(Path(status.seed_path).parent))
        else:
            missing = []
            if not status.seed:
                missing.append("seed")
            if not status.label_db:
                missing.append("label")
            self.db_badge.set_state("warning", "Database incomplete")
            self.db_detail.setText(
                "Missing " + " and ".join(missing) + " database. Open Manage databases to install it."
            )

    # -------------------------------------------------------------- validation
    def apply_issues(self, grouped: dict) -> None:
        mapping = {
            "reads_1": self.r1_input,
            "reads_2": self.r2_input,
            "unpaired": self.unpaired_input,
            "graph": self.graph_input,
        }
        for field, widget in mapping.items():
            issues = grouped.get(field, [])
            error = next((issue for issue in issues if issue.is_error), None)
            widget.set_invalid(bool(error), error.message if error else "")
        issues = grouped.get("run_name", [])
        error = next((issue for issue in issues if issue.is_error), None)
        self.run_name_edit.setProperty("invalid", "true" if error else "false")
        self.run_name_edit.style().unpolish(self.run_name_edit)
        self.run_name_edit.style().polish(self.run_name_edit)
        self.run_name_edit.setToolTip(error.message if error else "")
