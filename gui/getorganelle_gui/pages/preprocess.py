"""Optional fastp preprocessing page (adapter trimming / read filtering)."""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
)

from ..models import MODE_ASSEMBLY
from ..preprocess import ADAPTER_MODES, build_preprocess_plan
from ..widgets import Badge, Card, CollapsibleSection
from .common import ScrollPage, page_header


class PreprocessPage(ScrollPage):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self._loading = True
        self._error_labels = {}
        self.add(
            page_header(
                "Preprocess",
                "Optional: trim adapters and filter low-quality reads with fastp before assembly.",
            )
        )
        self._build_card()
        self._build_advanced()
        self._build_preview()
        footer = QHBoxLayout()
        back = QPushButton("←  Back to inputs")
        back.clicked.connect(lambda: self.wb.show_page("inputs"))
        footer.addWidget(back)
        footer.addStretch(1)
        self.continue_button = QPushButton("Continue to parameters  →")
        self.continue_button.setObjectName("PrimaryButton")
        self.continue_button.clicked.connect(lambda: self.wb.show_page("parameters"))
        footer.addWidget(self.continue_button)
        self.add_layout(footer)
        self.add_stretch()
        self.load_from_config()
        self._loading = False

    # ------------------------------------------------------------------ build
    def _build_card(self) -> None:
        self.card = Card(
            "fastp preprocessing",
            "fastp runs before GetOrganelle and writes trimmed reads plus JSON/HTML reports "
            "under <workspace>/_workbench/preprocess.",
        )
        header = QHBoxLayout()
        self.enable_check = QCheckBox("Trim adapters and filter reads with fastp")
        self.enable_check.toggled.connect(self._on_enabled)
        self.fastp_badge = Badge("Checking…", "idle")
        self.settings_button = QPushButton("Tool settings")
        self.settings_button.clicked.connect(self.wb.open_settings)
        header.addWidget(self.enable_check)
        header.addStretch(1)
        header.addWidget(self.fastp_badge)
        header.addWidget(self.settings_button)
        self.card.body.addLayout(header)

        self.body_widget = QGroupBox()
        form = QFormLayout(self.body_widget)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.adapter_combo = QComboBox()
        for key, label in ADAPTER_MODES.items():
            self.adapter_combo.addItem(label, key)
        self.adapter_combo.currentIndexChanged.connect(self._on_adapter_mode)
        form.addRow("Adapters", self.adapter_combo)
        self.adapter_edit = QLineEdit()
        self.adapter_edit.setPlaceholderText("R1 adapter, 5′→3′ (e.g. AGATCGGAAGAGCACACGTCTGAACTCCAGTCA)")
        self.adapter_edit.textChanged.connect(self._changed)
        form.addRow("Adapter R1", self.adapter_edit)
        self.adapter_row_label = form.labelForField(self.adapter_edit)
        self._add_error(form, "adapter_sequence")
        self.adapter_r2_edit = QLineEdit()
        self.adapter_r2_edit.setPlaceholderText("Optional R2 adapter; empty = same as R1")
        self.adapter_r2_edit.textChanged.connect(self._changed)
        form.addRow("Adapter R2", self.adapter_r2_edit)
        self.adapter_r2_row_label = form.labelForField(self.adapter_r2_edit)
        self._add_error(form, "adapter_sequence_r2")
        self.gbase_spin = QDoubleSpinBox()
        self.gbase_spin.setDecimals(1)
        self.gbase_spin.setRange(0.0, 10000.0)
        self.gbase_spin.setSingleStep(0.1)
        self.gbase_spin.setSuffix(" Gb")
        self.gbase_spin.setSpecialValueText("All reads")
        self.gbase_spin.setToolTip(
            "Approximate total bases from the primary R1/R2 (or single-end) input; "
            "fastp stops after the first N reads/pairs. 0 = all reads. The read "
            "count is estimated from the mean length of the first reads; unpaired "
            "extra files are not capped."
        )
        self.gbase_spin.valueChanged.connect(self._changed)
        form.addRow("Reads to request", self.gbase_spin)
        self._add_error(form, "fastp_gbase_limit")
        self.min_length_spin = QSpinBox()
        self.min_length_spin.setRange(0, 10000)
        self.min_length_spin.setValue(15)
        self.min_length_spin.setToolTip("Reads shorter than this after trimming are discarded (fastp default 15).")
        self.min_length_spin.valueChanged.connect(self._changed)
        form.addRow("Minimum length", self.min_length_spin)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(0, 40)
        self.quality_spin.setValue(15)
        self.quality_spin.setToolTip("A base is qualified when its Phred quality is at least this value.")
        self.quality_spin.valueChanged.connect(self._changed)
        form.addRow("Qualified quality", self.quality_spin)
        self.unqualified_spin = QSpinBox()
        self.unqualified_spin.setRange(0, 100)
        self.unqualified_spin.setValue(40)
        self.unqualified_spin.setToolTip("Discard a read when more than this percent of bases are unqualified.")
        self.unqualified_spin.valueChanged.connect(self._changed)
        form.addRow("Unqualified %", self.unqualified_spin)
        self.card.body.addWidget(self.body_widget)
        self.add(self.card)

    def _add_error(self, form: QFormLayout, field: str) -> None:
        label = QLabel("")
        label.setObjectName("FieldError")
        label.setWordWrap(True)
        label.hide()
        form.addRow("", label)
        self._error_labels[field] = label

    def _build_advanced(self) -> None:
        self.advanced = CollapsibleSection("Advanced fastp options")
        group = QGroupBox("Trimming and performance")
        form = QFormLayout(group)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.trim_front1 = QSpinBox()
        self.trim_front1.setRange(0, 10000)
        self.trim_front1.valueChanged.connect(self._changed)
        self.trim_tail1 = QSpinBox()
        self.trim_tail1.setRange(0, 10000)
        self.trim_tail1.valueChanged.connect(self._changed)
        self.trim_front2 = QSpinBox()
        self.trim_front2.setRange(0, 10000)
        self.trim_front2.valueChanged.connect(self._changed)
        self.trim_tail2 = QSpinBox()
        self.trim_tail2.setRange(0, 10000)
        self.trim_tail2.valueChanged.connect(self._changed)
        form.addRow("Trim front R1", self.trim_front1)
        form.addRow("Trim tail R1", self.trim_tail1)
        form.addRow("Trim front R2", self.trim_front2)
        form.addRow("Trim tail R2", self.trim_tail2)
        self.dedup_check = QCheckBox("Drop duplicated reads (--dedup)")
        self.dedup_check.toggled.connect(self._changed)
        form.addRow("", self.dedup_check)
        self.fastp_threads_spin = QSpinBox()
        self.fastp_threads_spin.setRange(0, 256)
        self.fastp_threads_spin.setSpecialValueText("Same as GetOrganelle")
        self.fastp_threads_spin.valueChanged.connect(self._changed)
        form.addRow("fastp threads", self.fastp_threads_spin)
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("Optional extra fastp options")
        self.extra_edit.textChanged.connect(self._changed)
        form.addRow("Extra options", self.extra_edit)
        self._add_error(form, "fastp_extra_args")
        self.advanced.content_layout.addWidget(group)
        self.add(self.advanced)

    def _build_preview(self) -> None:
        self.preview_card = Card(
            "fastp command preview",
            "Shown for the current inputs. Trimmed paths are generated per run.",
        )
        self.command_preview = QPlainTextEdit()
        self.command_preview.setObjectName("Preview")
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(86)
        self.preview_card.body.addWidget(self.command_preview)
        actions = QHBoxLayout()
        actions.addStretch(1)
        copy = QPushButton("Copy command")
        copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.command_preview.toPlainText())
        )
        actions.addWidget(copy)
        self.preview_card.body.addLayout(actions)
        self.add(self.preview_card)

    # ------------------------------------------------------------------ state
    def load_from_config(self) -> None:
        config = self.wb.config
        self._loading = True
        self.enable_check.setChecked(config.preprocess)
        index = self.adapter_combo.findData(config.adapter_mode)
        if index >= 0:
            self.adapter_combo.setCurrentIndex(index)
        self.adapter_edit.setText(config.adapter_sequence)
        self.adapter_r2_edit.setText(config.adapter_sequence_r2)
        self.gbase_spin.setValue(config.fastp_gbase_limit)
        self.min_length_spin.setValue(config.fastp_min_length)
        self.quality_spin.setValue(config.fastp_quality)
        self.unqualified_spin.setValue(config.fastp_unqualified_percent)
        self.trim_front1.setValue(config.trim_front1)
        self.trim_tail1.setValue(config.trim_tail1)
        self.trim_front2.setValue(config.trim_front2)
        self.trim_tail2.setValue(config.trim_tail2)
        self.dedup_check.setChecked(config.fastp_dedup)
        self.fastp_threads_spin.setValue(config.fastp_threads)
        self.extra_edit.setText(config.fastp_extra_args)
        self._loading = False
        self._on_adapter_mode()
        self.update_availability()
        self.update_preview()

    def sync_to_config(self) -> None:
        config = self.wb.config
        config.preprocess = self.enable_check.isChecked()
        config.adapter_mode = self.adapter_combo.currentData() or "auto"
        config.adapter_sequence = self.adapter_edit.text().strip()
        config.adapter_sequence_r2 = self.adapter_r2_edit.text().strip()
        config.fastp_gbase_limit = round(self.gbase_spin.value(), 1)
        config.fastp_min_length = self.min_length_spin.value()
        config.fastp_quality = self.quality_spin.value()
        config.fastp_unqualified_percent = self.unqualified_spin.value()
        config.trim_front1 = self.trim_front1.value()
        config.trim_tail1 = self.trim_tail1.value()
        config.trim_front2 = self.trim_front2.value()
        config.trim_tail2 = self.trim_tail2.value()
        config.fastp_dedup = self.dedup_check.isChecked()
        config.fastp_threads = self.fastp_threads_spin.value()
        config.fastp_extra_args = self.extra_edit.text().strip()

    def _changed(self) -> None:
        if self._loading:
            return
        self.sync_to_config()
        self.update_preview()
        self.wb.on_config_changed()

    def _on_enabled(self, enabled: bool) -> None:
        self.body_widget.setEnabled(enabled)
        if enabled:
            self.advanced.setExpanded(True)
        self._changed()

    def _on_adapter_mode(self) -> None:
        custom = self.adapter_combo.currentData() == "custom"
        self.adapter_edit.setVisible(custom)
        self.adapter_r2_edit.setVisible(custom)
        if self.adapter_row_label is not None:
            self.adapter_row_label.setVisible(custom)
        if self.adapter_r2_row_label is not None:
            self.adapter_r2_row_label.setVisible(custom)
        self._changed()

    def update_for_mode(self, mode: str) -> None:
        reads = mode != MODE_ASSEMBLY
        self.enable_check.setEnabled(reads and self._fastp_available())
        if not reads:
            if self.enable_check.isChecked():
                self.enable_check.blockSignals(True)
                self.enable_check.setChecked(False)
                self.enable_check.blockSignals(False)
                self.sync_to_config()
            self.enable_check.setToolTip("Preprocessing applies to reads only.")
            self.body_widget.setEnabled(False)
        else:
            self.enable_check.setToolTip("")
            self.body_widget.setEnabled(self.enable_check.isChecked())

    def _fastp_available(self) -> bool:
        tool = self.wb.deps.tools.get("fastp")
        return bool(tool and tool.ok)

    def update_availability(self) -> None:
        tool = self.wb.deps.tools.get("fastp")
        if tool is None or not tool.ok:
            self.fastp_badge.set_state("warning", "fastp missing")
            self.enable_check.setEnabled(False)
        else:
            self.fastp_badge.set_state(
                "success", f"fastp {tool.version}" if tool.version else "fastp ready"
            )
            self.enable_check.setEnabled(self.wb.config.mode != MODE_ASSEMBLY)
        self.body_widget.setEnabled(self.enable_check.isChecked())
        self.update_preview()

    def update_preview(self) -> None:
        if self.wb.config.mode == MODE_ASSEMBLY or not self.enable_check.isChecked():
            self.command_preview.setPlainText("Preprocessing is off.")
            return
        try:
            preview_config = self.wb.config
            plan = build_preprocess_plan(
                preview_config,
                self.wb.settings,
                self.wb.settings.workspace_root + r"\_workbench\preprocess\<run_id>",
            )
            lines = [cmd.display for cmd in plan.commands]
            self.command_preview.setPlainText("\n".join(lines) or "Preprocessing is off.")
        except Exception as exc:  # keep the page usable while fields are incomplete
            self.command_preview.setPlainText(f"<cannot build fastp command: {exc}>")

    # -------------------------------------------------------------- validation
    def apply_issues(self, grouped: dict) -> None:
        for field, label in self._error_labels.items():
            issues = grouped.get(field, [])
            error = next((issue for issue in issues if issue.is_error), None)
            if error:
                label.setText(error.message)
                label.show()
            else:
                label.hide()
        preprocess_errors = grouped.get("preprocess", [])
        if any(issue.is_error for issue in preprocess_errors):
            self.enable_check.setToolTip(preprocess_errors[0].message)
