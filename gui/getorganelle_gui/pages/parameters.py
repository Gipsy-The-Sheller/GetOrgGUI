"""Parameters page with Basic/Advanced progressive disclosure."""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from ..models import DEFAULT_KMERS, MODE_ASSEMBLY, organelle_default_rounds
from ..widgets import Card, CollapsibleSection, FileInput
from .common import ScrollPage, hint, page_header

FASTQ_FILTER = "FASTA (*.fa *.fasta *.fna);;All files (*)"
GRAPH_FILTER = "Assembly graph (*.gfa *.fastg);;All files (*)"


class ParametersPage(ScrollPage):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self._loading = True
        self._rounds_manual = False
        self._setting_rounds = False
        self._error_labels = {}

        self.add(
            page_header(
                "Parameters",
                "Only a few settings are needed for a first run. Advanced options stay folded away.",
            )
        )
        self._build_basic_card()
        self._build_advanced_section()
        self._build_command_card()

        footer = QHBoxLayout()
        back = QPushButton("←  Back to inputs")
        back.clicked.connect(lambda: self.wb.show_page("preprocess"))
        footer.addWidget(back)
        footer.addStretch(1)
        self.continue_button = QPushButton("Continue to run  →")
        self.continue_button.setObjectName("PrimaryButton")
        self.continue_button.clicked.connect(lambda: self.wb.show_page("run"))
        footer.addWidget(self.continue_button)
        self.add_layout(footer)
        self.add_stretch()

        self.load_from_config()
        self._loading = False

    # ------------------------------------------------------------------ build
    def _build_basic_card(self) -> None:
        self.basic_card = Card("Basic parameters", "Safe defaults are selected; change them if your data needs it.")
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setSuffix(" threads")
        self.threads_spin.setToolTip("Passed to GetOrganelle as -t. Leave one thread free on a laptop.")
        self.threads_spin.valueChanged.connect(self._changed)
        form.addRow("CPU threads", self.threads_spin)

        self.rounds_spin = QSpinBox()
        self.rounds_spin.setRange(1, 1_000_000)
        self.rounds_spin.setSuffix(" rounds")
        self.rounds_spin.setToolTip(
            "Maximum extension rounds (-R). Plastomes usually need 15; mitogenomes often need 30."
        )
        self.rounds_spin.valueChanged.connect(self._on_rounds_changed)
        form.addRow("Extending rounds", self.rounds_spin)
        self.rounds_row_label = form.labelForField(self.rounds_spin)

        kmer_row = QWidget()
        kmer_layout = QHBoxLayout(kmer_row)
        kmer_layout.setContentsMargins(0, 0, 0, 0)
        kmer_layout.setSpacing(8)
        self.kmer_mode_combo = QComboBox()
        self.kmer_mode_combo.addItem("Auto (recommended)", "auto")
        self.kmer_mode_combo.addItem("Custom list", "custom")
        self.kmer_mode_combo.currentIndexChanged.connect(self._on_kmer_mode_changed)
        self.kmer_edit = QLineEdit(DEFAULT_KMERS)
        self.kmer_edit.setPlaceholderText(DEFAULT_KMERS)
        self.kmer_edit.setToolTip("Odd k-mers between 21 and 127, increasing, comma-separated.")
        self.kmer_edit.textChanged.connect(self._changed)
        self.kmer_edit.setEnabled(False)
        kmer_layout.addWidget(self.kmer_mode_combo, 1)
        kmer_layout.addWidget(self.kmer_edit, 2)
        form.addRow("SPAdes k-mers", kmer_row)
        self._add_error_row(form, "kmers")

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Balanced (default)", "balanced")
        self.preset_combo.addItem("Fast — homogeneous high coverage", "fast")
        self.preset_combo.addItem("Memory-saving", "memory_save")
        self.preset_combo.setToolTip(
            "Passes --fast or --memory-save. Any explicit control above overrides the preset."
        )
        self.preset_combo.currentIndexChanged.connect(self._changed)
        form.addRow("Preset", self.preset_combo)

        self.basic_card.body.addLayout(form)
        self.add(self.basic_card)

    def _build_advanced_section(self) -> None:
        self.advanced = CollapsibleSection("Advanced options")
        self.add(self.advanced)

        reads_group = QGroupBox("Reads options")
        reads_form = QFormLayout(reads_group)
        reads_form.setSpacing(10)
        reads_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.max_reads_edit = QLineEdit()
        self.max_reads_edit.setPlaceholderText("GetOrganelle default (e.g. 1.5E7)")
        self.max_reads_edit.setToolTip("Hard cap per input file (--max-reads). Empty uses the organelle default.")
        self.max_reads_edit.textChanged.connect(self._changed)
        reads_form.addRow("Maximum reads", self.max_reads_edit)
        self._add_error_row(reads_form, "max_reads")

        self.reduce_cov_edit = QLineEdit("500")
        self.reduce_cov_edit.setToolTip(
            "Soft coverage cap (--reduce-reads-for-coverage). Use inf to disable reduction."
        )
        self.reduce_cov_edit.textChanged.connect(self._changed)
        reads_form.addRow("Coverage limit", self.reduce_cov_edit)
        self._add_error_row(reads_form, "reduce_coverage")

        self.max_ext_edit = QLineEdit("inf")
        self.max_ext_edit.setToolTip(
            "Maximum extension length (--max-extending-len): a number, auto, or inf. Use inf with seed loci."
        )
        self.max_ext_edit.textChanged.connect(self._changed)
        reads_form.addRow("Max extending length", self.max_ext_edit)
        self._add_error_row(reads_form, "max_extending_len")
        self.reads_options_group = reads_group
        self.advanced.content_layout.addWidget(reads_group)

        assembly_group = QGroupBox("Assembly graph options")
        assembly_form = QFormLayout(assembly_group)
        assembly_form.setSpacing(10)
        assembly_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.min_depth_edit = QLineEdit("0")
        self.min_depth_edit.setToolTip("Minimum graph depth (--min-depth).")
        self.min_depth_edit.textChanged.connect(self._changed)
        assembly_form.addRow("Minimum depth", self.min_depth_edit)
        self.max_depth_edit = QLineEdit("inf")
        self.max_depth_edit.setToolTip("Maximum graph depth (--max-depth); inf disables the cap.")
        self.max_depth_edit.textChanged.connect(self._changed)
        assembly_form.addRow("Maximum depth", self.max_depth_edit)
        self.no_slim_check = QCheckBox("Skip the slimming step (--no-slim)")
        self.no_slim_check.toggled.connect(self._changed)
        assembly_form.addRow("", self.no_slim_check)
        self.spades_out_input = FileInput(
            mode="directory", placeholder="Optional SPAdes scaffolds folder"
        )
        self.spades_out_input.setToolTip(
            "Optional: use SPAdes scaffolds.fasta/scaffolds.paths to bridge disconnected contigs."
        )
        self.spades_out_input.path_changed.connect(self._changed)
        assembly_form.addRow("SPAdes scaffolds", self.spades_out_input)
        self.assembly_options_group = assembly_group
        self.advanced.content_layout.addWidget(assembly_group)

        output_group = QGroupBox("Output options")
        output_form = QFormLayout(output_group)
        output_form.setSpacing(10)
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Optional prefix for result files")
        self.prefix_edit.setToolTip("Added to result file names (--prefix). No path separators.")
        self.prefix_edit.textChanged.connect(self._changed)
        output_form.addRow("Result prefix", self.prefix_edit)
        self._add_error_row(output_form, "prefix")
        self.keep_temp_check = QCheckBox("Keep temporary files (--keep-temp)")
        self.keep_temp_check.toggled.connect(self._changed)
        output_form.addRow("", self.keep_temp_check)
        self.out_per_round_check = QCheckBox("Write output every round (--out-per-round)")
        self.out_per_round_check.setToolTip("Saves memory at the cost of more time.")
        self.out_per_round_check.toggled.connect(self._changed)
        output_form.addRow("", self.out_per_round_check)
        self.zip_files_check = QCheckBox("Compress intermediate FASTQ/SAM (--zip-files)")
        self.zip_files_check.toggled.connect(self._changed)
        output_form.addRow("", self.zip_files_check)
        self.advanced.content_layout.addWidget(output_group)

        database_group = QGroupBox("Custom seed / gene database")
        database_form = QFormLayout(database_group)
        database_form.setSpacing(10)
        database_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.seed_input = FileInput(filters=FASTQ_FILTER, placeholder="Optional seed FASTA")
        self.seed_input.setToolTip("Overrides the default seed (-s). Required for “Unknown organelle”.")
        self.seed_input.path_changed.connect(self._changed)
        database_form.addRow("Seed sequence", self.seed_input)
        self.genes_input = FileInput(
            filters="Gene database (*.fa *.fasta *.fna);;All files (*)",
            placeholder="Optional gene FASTA / BLAST database",
        )
        self.genes_input.setToolTip("Overrides the label database (--genes). Required for “Unknown organelle”.")
        self.genes_input.path_changed.connect(self._changed)
        database_form.addRow("Gene database", self.genes_input)
        self.advanced.content_layout.addWidget(database_group)

        extra_group = QGroupBox("Extra GetOrganelle options")
        extra_form = QFormLayout(extra_group)
        extra_form.setSpacing(10)
        extra_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText('e.g. --bowtie2-options "--very-fast -t"')
        self.extra_edit.setToolTip(
            "Raw options are appended to the command. Do not set inputs, output, -F, -t or -R here."
        )
        self.extra_edit.textChanged.connect(self._changed)
        extra_form.addRow("Additional options", self.extra_edit)
        self._add_error_row(extra_form, "extra_args")
        extra_form.addRow("", hint("Quoted groups are preserved; backslashes in Windows paths are not treated as escapes."))
        self.advanced.content_layout.addWidget(extra_group)

    def _build_command_card(self) -> None:
        self.command_card = Card(
            "Command preview",
            "Exactly what will run. The same command is written to run.json for provenance.",
        )
        self.command_preview = QPlainTextEdit()
        self.command_preview.setObjectName("Preview")
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(96)
        self.command_preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.command_card.body.addWidget(self.command_preview)
        row = QHBoxLayout()
        row.addStretch(1)
        self.copy_button = QPushButton("Copy command")
        self.copy_button.clicked.connect(self._copy_command)
        row.addWidget(self.copy_button)
        self.command_card.body.addLayout(row)
        self.add(self.command_card)

    def _add_error_row(self, form: QFormLayout, field: str) -> None:
        label = QLabel("")
        label.setObjectName("FieldError")
        label.setWordWrap(True)
        label.hide()
        form.addRow("", label)
        self._error_labels[field] = label

    # ------------------------------------------------------------------ state
    def load_from_config(self) -> None:
        config = self.wb.config
        self._loading = True
        self.threads_spin.setValue(config.threads)
        self._setting_rounds = True
        self.rounds_spin.setValue(config.rounds)
        self._setting_rounds = False
        self.kmer_mode_combo.setCurrentIndex(0 if config.kmer_mode == "auto" else 1)
        self.kmer_edit.setText(config.kmers or DEFAULT_KMERS)
        index = self.preset_combo.findData(config.preset)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.max_reads_edit.setText(config.max_reads)
        self.reduce_cov_edit.setText(config.reduce_coverage)
        self.max_ext_edit.setText(config.max_extending_len)
        self.min_depth_edit.setText(config.min_depth)
        self.max_depth_edit.setText(config.max_depth)
        self.no_slim_check.setChecked(config.no_slim)
        self.spades_out_input.setText(config.spades_out_dir)
        self.prefix_edit.setText(config.prefix)
        self.keep_temp_check.setChecked(config.keep_temp)
        self.out_per_round_check.setChecked(config.out_per_round)
        self.zip_files_check.setChecked(config.zip_files)
        self.seed_input.setText(config.seed_file)
        self.genes_input.setText(config.genes_db)
        self.extra_edit.setText(config.extra_args)
        self._loading = False
        self.set_mode(config.mode)
        self.update_command_preview()

    def sync_to_config(self) -> None:
        config = self.wb.config
        config.threads = self.threads_spin.value()
        config.rounds = self.rounds_spin.value()
        config.kmer_mode = self.kmer_mode_combo.currentData() or "auto"
        config.kmers = self.kmer_edit.text().strip()
        config.preset = self.preset_combo.currentData() or "balanced"
        config.max_reads = self.max_reads_edit.text().strip()
        config.reduce_coverage = self.reduce_cov_edit.text().strip()
        config.max_extending_len = self.max_ext_edit.text().strip()
        config.min_depth = self.min_depth_edit.text().strip()
        config.max_depth = self.max_depth_edit.text().strip()
        config.no_slim = self.no_slim_check.isChecked()
        config.spades_out_dir = self.spades_out_input.text()
        config.prefix = self.prefix_edit.text().strip()
        config.keep_temp = self.keep_temp_check.isChecked()
        config.out_per_round = self.out_per_round_check.isChecked()
        config.zip_files = self.zip_files_check.isChecked()
        config.seed_file = self.seed_input.text()
        config.genes_db = self.genes_input.text()
        config.extra_args = self.extra_edit.text().strip()

    def _changed(self) -> None:
        if self._loading:
            return
        self.sync_to_config()
        self.update_command_preview()
        self.wb.on_config_changed()

    def _on_rounds_changed(self) -> None:
        if self._setting_rounds:
            return
        self._rounds_manual = True
        self._changed()

    def _on_kmer_mode_changed(self) -> None:
        custom = self.kmer_mode_combo.currentData() == "custom"
        self.kmer_edit.setEnabled(custom)
        self._changed()

    def set_mode(self, mode: str) -> None:
        reads = mode != MODE_ASSEMBLY
        self.reads_options_group.setVisible(reads)
        self.assembly_options_group.setVisible(not reads)
        self.rounds_spin.setVisible(reads)
        if self.rounds_row_label is not None:
            self.rounds_row_label.setVisible(reads)

    def update_for_organelle(self, organelle: str) -> None:
        if self._rounds_manual:
            return
        self._setting_rounds = True
        self.rounds_spin.setValue(organelle_default_rounds(organelle))
        self._setting_rounds = False
        self.sync_to_config()
        self.update_command_preview()
        self.wb.on_config_changed()

    def update_command_preview(self) -> None:
        self.command_preview.setPlainText(self.wb.command_display())
        self.command_preview.verticalScrollBar().setValue(0)

    def _copy_command(self) -> None:
        QApplication.clipboard().setText(self.wb.command_display())

    # -------------------------------------------------------------- validation
    def apply_issues(self, grouped: dict) -> None:
        mapping = {
            "threads": self.threads_spin,
            "rounds": self.rounds_spin,
            "kmers": self.kmer_edit,
            "max_reads": self.max_reads_edit,
            "reduce_coverage": self.reduce_cov_edit,
            "max_extending_len": self.max_ext_edit,
            "prefix": self.prefix_edit,
            "extra_args": self.extra_edit,
            "min_depth": self.min_depth_edit,
            "max_depth": self.max_depth_edit,
            "spades_out_dir": self.spades_out_input,
            "seed_file": self.seed_input,
            "genes_db": self.genes_input,
        }
        for field, widget in mapping.items():
            issues = grouped.get(field, [])
            error = next((issue for issue in issues if issue.is_error), None)
            if isinstance(widget, FileInput):
                widget.set_invalid(bool(error), error.message if error else "")
            else:
                widget.setProperty("invalid", "true" if error else "false")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.setToolTip(error.message if error else "")
            label = self._error_labels.get(field)
            if label is not None:
                if error:
                    label.setText(error.message)
                    label.show()
                else:
                    label.hide()
        # If there is an error in a folded section, open it so it is visible.
        advanced_fields = {
            "max_reads",
            "reduce_coverage",
            "max_extending_len",
            "prefix",
            "extra_args",
            "min_depth",
            "max_depth",
            "spades_out_dir",
            "seed_file",
            "genes_db",
        }
        if any(
            issue.is_error
            for field, issues in grouped.items()
            if field in advanced_fields
            for issue in issues
        ):
            self.advanced.setExpanded(True)
