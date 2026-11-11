"""Non-modal reference BLAST dialog for the assembly-graph viewer."""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .graph_model import AssemblyGraph
from .paths import open_in_file_manager
from .reference_blast import (
    BlastCancelled,
    BlastFilters,
    BlastResult,
    BlastRunConfig,
    DEFAULT_HIGHLIGHT_EVALUE,
    NodeHitView,
    ReferenceBlastRunner,
    format_evalue,
    filter_node_hits,
    parse_evalue,
    resolve_blast_tools,
    write_fasta,
)
from .theme import LIGHT, Tokens
from .widgets import FileInput, human_bp

GENBANK_FILTER = (
    "GenBank / GenBank flat file (*.gb *.gbk *.gbff *.genbank *.gb.gz *.gbk.gz);;"
    "All files (*.*)"
)


class _BlastWorker(QThread):
    status = pyqtSignal(str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, runner: ReferenceBlastRunner, parent=None):
        super().__init__(parent)
        self.runner = runner

    def run(self) -> None:  # noqa: D401 - Qt thread entry point
        try:
            result = self.runner.run(self.status.emit)
        except BlastCancelled:
            self.failed.emit("BLAST cancelled.")
        except Exception as exc:  # noqa: BLE001 - report worker failures inline
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class BlastReferenceDialog(QDialog):
    """Search a GenBank reference against graph nodes and live-highlight hits."""

    def __init__(
        self,
        graph: AssemblyGraph,
        canvas,
        settings=None,
        tokens: Optional[Tokens] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.graph = graph
        self.canvas = canvas
        self.settings = settings
        self.tokens = tokens or LIGHT
        self.result: Optional[BlastResult] = None
        self.views: List[NodeHitView] = []
        self.worker: Optional[_BlastWorker] = None
        self._runner: Optional[ReferenceBlastRunner] = None
        self._work_dir = ""
        self._tools: Dict[str, str] = {}
        self._running = False
        self._closing = False
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(250)
        self._apply_timer.timeout.connect(self._apply_filters)

        graph_name = Path(graph.path).name if graph.path else "assembly graph"
        self.setWindowTitle(f"Reference BLAST · {graph_name}")
        self.setWindowModality(Qt.NonModal)
        self.resize(1000, 720)
        self._build_ui()
        self._resolve_tools()
        self._update_run_state()
        self._update_filter_state()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Reference BLAST screening")
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Search a GenBank reference against graph node sequences to find "
            "organelle contigs. blastn uses the complete record; tblastn uses "
            "translated CDS annotations. Hits are cached, so the E-value and "
            "evidence filters update highlights without rerunning BLAST."
        )
        subtitle.setObjectName("CardSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_reference_group())
        layout.addWidget(self._build_filter_group())
        layout.addLayout(self._build_status_row())
        layout.addWidget(self._build_results_group(), 1)
        layout.addLayout(self._build_footer())

    def _build_reference_group(self) -> QGroupBox:
        group = QGroupBox("Reference and search")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.reference_input = FileInput(
            mode="open",
            filters=GENBANK_FILTER,
            placeholder="Reference .gb / .gbk / .gbff",
        )
        self.reference_input.path_changed.connect(self._reference_changed)
        grid.addWidget(QLabel("GenBank file"), 0, 0)
        grid.addWidget(self.reference_input, 0, 1, 1, 5)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Full reference — blastn", "blastn")
        self.mode_combo.addItem("Annotated CDS — tblastn", "tblastn")
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        grid.addWidget(QLabel("Mode"), 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)

        self.search_combo = QComboBox()
        self.search_combo.setEditable(True)
        self.search_combo.setInsertPolicy(QComboBox.NoInsert)
        self.search_combo.addItems(["1e-3", "1e-5", "1e-10"])
        self.search_combo.setCurrentText("1e-3")
        self.search_combo.setMaximumWidth(100)
        self.search_combo.setToolTip(
            "BLAST search threshold. Hits above this value are not retrieved; "
            "the highlight threshold can be stricter."
        )
        grid.addWidget(QLabel("Search E ≤"), 1, 2)
        grid.addWidget(self.search_combo, 1, 3)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 64)
        default_threads = getattr(self.settings, "threads", 0) or 4
        self.threads_spin.setValue(max(1, min(64, default_threads)))
        self.threads_spin.setMaximumWidth(80)
        grid.addWidget(QLabel("Threads"), 1, 4)
        grid.addWidget(self.threads_spin, 1, 5)

        self.run_button = QPushButton("Run BLAST")
        self.run_button.setObjectName("PrimaryButton")
        self.run_button.clicked.connect(self._start_run)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_run)
        run_row = QHBoxLayout()
        run_row.setSpacing(6)
        run_row.addWidget(self.run_button)
        run_row.addWidget(self.cancel_button)
        run_row.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(180)
        self.progress.hide()
        run_row.addWidget(self.progress)
        grid.addLayout(run_row, 2, 0, 1, 6)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        self.status_label.setWordWrap(True)
        grid.addWidget(self.status_label, 3, 0, 1, 6)
        return group

    def _build_filter_group(self) -> QGroupBox:
        group = QGroupBox("Highlight filters")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.evalue_combo = QComboBox()
        self.evalue_combo.setEditable(True)
        self.evalue_combo.setInsertPolicy(QComboBox.NoInsert)
        self.evalue_combo.addItems(["1e-5", "1e-10", "1e-20", "1e-50", "1e-100"])
        self.evalue_combo.setCurrentText(f"{DEFAULT_HIGHLIGHT_EVALUE:g}")
        self.evalue_combo.setMaximumWidth(110)
        self.evalue_combo.setToolTip(
            "Only hits at or below this E-value highlight a node. "
            "Changing it does not rerun BLAST."
        )
        self.evalue_combo.currentTextChanged.connect(self._schedule_apply)

        self.identity_spin = QDoubleSpinBox()
        self.identity_spin.setRange(0, 100)
        self.identity_spin.setDecimals(1)
        self.identity_spin.setSuffix(" %")
        self.identity_spin.setValue(0)
        self.identity_spin.setMaximumWidth(100)
        self.identity_spin.valueChanged.connect(self._schedule_apply)

        self.alignment_spin = QSpinBox()
        self.alignment_spin.setRange(0, 1_000_000)
        self.alignment_spin.setValue(0)
        self.alignment_spin.setMaximumWidth(110)
        self.alignment_spin.valueChanged.connect(self._schedule_apply)

        self.query_coverage_spin = QDoubleSpinBox()
        self.query_coverage_spin.setRange(0, 100)
        self.query_coverage_spin.setDecimals(0)
        self.query_coverage_spin.setSuffix(" %")
        self.query_coverage_spin.setValue(0)
        self.query_coverage_spin.setMaximumWidth(100)
        self.query_coverage_spin.valueChanged.connect(self._schedule_apply)

        self.distinct_spin = QSpinBox()
        self.distinct_spin.setRange(1, 100)
        self.distinct_spin.setValue(1)
        self.distinct_spin.setMaximumWidth(80)
        self.distinct_spin.setToolTip(
            "tblastn only: require hits to this many annotated genes/features. "
            "A single-gene hit is more likely to be a NUPT/NUMT-like insertion."
        )
        self.distinct_spin.valueChanged.connect(self._schedule_apply)

        grid.addWidget(QLabel("Highlight E ≤"), 0, 0)
        grid.addWidget(self.evalue_combo, 0, 1)
        grid.addWidget(QLabel("Identity ≥"), 0, 2)
        grid.addWidget(self.identity_spin, 0, 3)
        grid.addWidget(QLabel("Alignment ≥"), 0, 4)
        grid.addWidget(self.alignment_spin, 0, 5)
        grid.addWidget(QLabel("Query coverage ≥"), 1, 0)
        grid.addWidget(self.query_coverage_spin, 1, 1)
        grid.addWidget(QLabel("Distinct genes ≥"), 1, 2)
        grid.addWidget(self.distinct_spin, 1, 3)
        grid.setColumnStretch(6, 1)

        hint = QLabel(
            "E-value alone cannot prove organelle origin: NUPTs/NUMTs can match "
            "a reference almost perfectly. For screening, prefer tblastn with "
            "≥ 2 annotated genes, high identity/alignment length, and inspect "
            "node coverage and read support."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 2, 0, 1, 7)
        return group

    def _build_status_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.summary_label = QLabel("No BLAST result yet.")
        self.summary_label.setObjectName("Caption")
        self.summary_label.setWordWrap(True)
        row.addWidget(self.summary_label, 1)
        self.folder_button = QPushButton("Open BLAST folder")
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self._open_work_dir)
        row.addWidget(self.folder_button)
        return row

    def _build_results_group(self) -> QGroupBox:
        group = QGroupBox("Passing nodes")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Node",
                "Length",
                "Node cov.",
                "Best E",
                "Identity",
                "Alignment",
                "Query cov.",
                "Aligned node %",
                "Genes",
                "Best query",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self._focus_row)
        layout.addWidget(self.table, 1)
        return group

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.copy_button = QPushButton("Copy node IDs")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_ids)
        self.export_button = QPushButton("Export TSV…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_tsv)
        self.fasta_button = QPushButton("Export node FASTA…")
        self.fasta_button.setEnabled(False)
        self.fasta_button.clicked.connect(self._export_fasta)
        self.clear_button = QPushButton("Clear highlight")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self._clear_highlight)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        row.addWidget(self.copy_button)
        row.addWidget(self.export_button)
        row.addWidget(self.fasta_button)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        row.addWidget(close_button)
        return row

    # ----------------------------------------------------------------- state
    def _resolve_tools(self) -> None:
        try:
            self._tools = resolve_blast_tools(self.settings)
        except FileNotFoundError as exc:
            self._tools = {}
            self._set_status(str(exc), error=True)
        else:
            blastn = Path(self._tools["blastn"])
            self._set_status(f"BLAST+ ready: {blastn.parent}")

    def _update_run_state(self) -> None:
        reference = self.reference_input.text().strip()
        has_file = bool(reference) and Path(reference).is_file()
        self.run_button.setEnabled(
            bool(self._tools) and has_file and not self._running
        )

    def _update_filter_state(self) -> None:
        mode = self.mode_combo.currentData() or "blastn"
        self.distinct_spin.setEnabled(mode == "tblastn" and self.result is not None)
        self.alignment_spin.setSuffix(" aa" if mode == "tblastn" else " bp")
        has_result = self.result is not None
        for widget in (
            self.evalue_combo,
            self.identity_spin,
            self.alignment_spin,
            self.query_coverage_spin,
            self.distinct_spin,
        ):
            widget.setEnabled(has_result and not self._running)
        if not has_result:
            self.distinct_spin.setEnabled(False)

    def _set_status(self, text: str, error: bool = False) -> None:
        color = self.tokens.error if error else self.tokens.text_secondary
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(text)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._closing = False
        super().showEvent(event)

    def _reference_changed(self, _path: str = "") -> None:
        self._update_run_state()
        if self.result is not None:
            self._reset_result("Reference changed — run BLAST again.")

    def _mode_changed(self) -> None:
        self._update_filter_state()
        if self.result is not None:
            self._reset_result("Mode changed — run BLAST again.")

    def _reset_result(self, message: str = "") -> None:
        self.result = None
        self.views = []
        self._work_dir = ""
        self.table.setRowCount(0)
        self.summary_label.setText("No BLAST result yet.")
        self.folder_button.setEnabled(False)
        self.folder_button.setToolTip("")
        self.copy_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.fasta_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.canvas.clear_blast()
        self._update_filter_state()
        if message:
            self._set_status(message)

    # ------------------------------------------------------------------- run
    def _start_run(self) -> None:
        if self._running:
            return
        reference = self.reference_input.text().strip()
        if not reference or not Path(reference).is_file():
            self._set_status("Choose an existing GenBank reference file.", error=True)
            return
        try:
            search_evalue = parse_evalue(self.search_combo.currentText())
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        if not self._tools:
            self._resolve_tools()
            if not self._tools:
                return
        mode = self.mode_combo.currentData() or "blastn"
        workspace = getattr(self.settings, "workspace_root", "") or ""
        base = Path(workspace) if workspace else Path.home()
        graph_name = Path(self.graph.path).stem if self.graph.path else "graph"
        graph_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", graph_name) or "graph"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        work_dir = base / "_workbench" / "blast" / f"{stamp}_{graph_name}"
        self._work_dir = str(work_dir)
        config = BlastRunConfig(
            reference_path=reference,
            mode=mode,
            evalue=search_evalue,
            threads=self.threads_spin.value(),
            work_dir=self._work_dir,
            blastn=self._tools["blastn"],
            tblastn=self._tools["tblastn"],
            makeblastdb=self._tools["makeblastdb"],
        )
        self._reset_result()
        self._set_running(True)
        self._set_status(f"Starting {mode}…")
        self._runner = ReferenceBlastRunner(self.graph, config)
        self.worker = _BlastWorker(self._runner, self)
        self.worker.status.connect(self._on_worker_status)
        self.worker.completed.connect(self._on_completed)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_status(self, message: str) -> None:
        if not self._closing:
            self._set_status(message)

    def _on_completed(self, result: BlastResult) -> None:
        if self._closing:
            return
        self.result = result
        self._set_running(False)
        self._update_filter_state()
        self.folder_button.setEnabled(bool(result.work_dir))
        self.folder_button.setToolTip(result.work_dir)
        self.summary_label.setText(
            f"{result.mode} · {result.query_count} queries · "
            f"{len(result.nodes)} hit nodes / {result.total_nodes} · "
            f"{len(result.hits)} HSPs · search E ≤ {format_evalue(result.evalue)}"
            + (
                f" · {result.skipped_nodes} node(s) without sequence skipped"
                if result.skipped_nodes
                else ""
            )
        )
        if result.hits:
            self._set_status(
                f"BLAST finished. Work directory: {result.work_dir}"
            )
        else:
            self._set_status(
                "BLAST finished without hits at the search E-value. "
                "Loosen the search E-value or check the reference."
            )
        self._apply_filters()

    def _on_failed(self, message: str) -> None:
        if self._closing:
            return
        self._set_running(False)
        self._set_status(message, error=True)
        self.summary_label.setText("BLAST did not complete.")

    def _on_worker_finished(self) -> None:
        worker = self.worker
        self.worker = None
        self._runner = None
        if worker is not None:
            worker.deleteLater()

    def _cancel_run(self) -> None:
        if self._runner is not None:
            self._set_status("Cancelling BLAST…")
            self.cancel_button.setEnabled(False)
            self._runner.cancel()

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.reference_input.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.search_combo.setEnabled(not running)
        self.threads_spin.setEnabled(not running)
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.progress.setVisible(running)
        self.clear_button.setEnabled(not running and bool(self.views))
        if running:
            for widget in (
                self.evalue_combo,
                self.identity_spin,
                self.alignment_spin,
                self.query_coverage_spin,
                self.distinct_spin,
            ):
                widget.setEnabled(False)
        else:
            self._update_filter_state()
            self._update_run_state()

    # --------------------------------------------------------------- filters
    def _schedule_apply(self) -> None:
        if self.result is not None and not self._running:
            self._apply_timer.start()

    def _apply_filters(self) -> None:
        if self.result is None:
            return
        try:
            evalue = parse_evalue(self.evalue_combo.currentText())
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        filters = BlastFilters(
            evalue=evalue,
            min_identity=self.identity_spin.value(),
            min_alignment=self.alignment_spin.value(),
            min_query_coverage=self.query_coverage_spin.value(),
            min_distinct_genes=(
                self.distinct_spin.value()
                if (self.mode_combo.currentData() or "blastn") == "tblastn"
                else 1
            ),
        )
        views = filter_node_hits(self.result, filters)
        self.views = views
        canvas_hits = {view.node_id: view for view in views}
        summary = (
            f"BLAST {len(views)}/{self.result.total_nodes} nodes · "
            f"E ≤ {format_evalue(evalue)}"
        )
        self.canvas.set_blast_hits(canvas_hits, summary)
        self._fill_table(views)
        self.summary_label.setText(
            f"{len(views)} / {self.result.total_nodes} nodes pass · "
            f"{self.result.mode} · {self.result.query_count} queries · "
            f"search E ≤ {format_evalue(self.result.evalue)}"
        )
        if evalue > self.result.evalue:
            self._set_status(
                "The highlight E-value is looser than the BLAST search "
                "E-value; rerun with a looser search threshold to retrieve "
                "additional hits.",
                error=False,
            )
        elif not views:
            self._set_status("No nodes pass the current filters.")
        else:
            self._set_status(
                f"Highlighting {len(views)} node(s). "
                "Double-click a table row to focus that node."
            )
        self.copy_button.setEnabled(bool(views))
        self.export_button.setEnabled(bool(views))
        self.fasta_button.setEnabled(bool(views))
        self.clear_button.setEnabled(bool(views))

    def _fill_table(self, views: List[NodeHitView]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(views))
        for row, view in enumerate(views):
            node = self.graph.nodes.get(view.node_id)
            hit = view.best_hit
            values = [
                view.node_id,
                human_bp(node.length) if node is not None else "",
                f"{node.coverage:.1f}×" if node is not None else "",
                format_evalue(hit.evalue),
                f"{hit.pident:.1f}%",
                str(hit.length),
                f"{view.max_query_coverage * 100:.0f}%",
                f"{view.max_subject_coverage * 100:.0f}%",
                str(view.distinct_genes),
                hit.query_label,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, view.node_id)
                if column == 9:
                    item.setToolTip(
                        f"{hit.query_label}\n{hit.strand} strand · "
                        f"subject {hit.sstart}–{hit.send}"
                    )
                self.table.setItem(row, column, item)
        self.table.resizeRowsToContents()

    def _focus_row(self, row: int, _column: int = 0) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        node_id = item.data(Qt.UserRole)
        if node_id:
            self.canvas.focus_node(str(node_id))
            self.canvas.setFocus()

    def _copy_ids(self) -> None:
        ids = sorted(view.node_id for view in self.views)
        if ids:
            QApplication.clipboard().setText("\n".join(ids))
            self._set_status(f"Copied {len(ids)} node ID(s) to the clipboard.")

    def _export_tsv(self) -> None:
        if not self.views:
            return
        graph_name = Path(self.graph.path).stem if self.graph.path else "graph"
        default = str(Path(self._work_dir or ".") / f"{graph_name}.blast_nodes.tsv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export BLAST node hits", default, "TSV (*.tsv);;All files (*.*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t")
                writer.writerow(
                    [
                        "node_id",
                        "node_length",
                        "node_coverage",
                        "best_evalue",
                        "identity_percent",
                        "alignment_length",
                        "query_coverage_percent",
                        "node_coverage_percent",
                        "distinct_genes",
                        "best_query",
                        "gene",
                        "strand",
                    ]
                )
                for view in self.views:
                    node = self.graph.nodes.get(view.node_id)
                    hit = view.best_hit
                    writer.writerow(
                        [
                            view.node_id,
                            node.length if node is not None else "",
                            f"{node.coverage:.3f}" if node is not None else "",
                            format_evalue(hit.evalue),
                            f"{hit.pident:.2f}",
                            hit.length,
                            f"{view.max_query_coverage * 100:.2f}",
                            f"{view.max_subject_coverage * 100:.2f}",
                            view.distinct_genes,
                            hit.query_label,
                            hit.gene,
                            hit.strand,
                        ]
                    )
        except OSError as exc:
            self._set_status(f"Cannot write TSV: {exc}", error=True)
            return
        self._set_status(f"Exported {len(self.views)} node hit(s) to {path}.")

    def _export_fasta(self) -> None:
        if not self.views:
            return
        graph_name = Path(self.graph.path).stem if self.graph.path else "graph"
        default = str(Path(self._work_dir or ".") / f"{graph_name}.blast_nodes.fasta")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export BLAST node sequences", default,
            "FASTA (*.fasta *.fa *.fna);;All files (*.*)"
        )
        if not path:
            return
        entries = []
        missing = 0
        for view in self.views:
            node = self.graph.nodes.get(view.node_id)
            if node is None or not node.sequence:
                missing += 1
                continue
            hit = view.best_hit
            query = re.sub(r"\s+", "_", hit.query_label)
            header = (
                f"{node.id} length={node.length} coverage={node.coverage:.2f} "
                f"evalue={format_evalue(hit.evalue)} query={query}"
            )
            entries.append((header, node.sequence))
        if not entries:
            self._set_status(
                "Passing nodes have no stored nucleotide sequences to export.",
                error=True,
            )
            return
        try:
            write_fasta(Path(path), entries)
        except OSError as exc:
            self._set_status(f"Cannot write FASTA: {exc}", error=True)
            return
        suffix = f" ({missing} node(s) without sequence skipped)" if missing else ""
        self._set_status(f"Exported {len(entries)} node sequence(s) to {path}{suffix}.")

    def _clear_highlight(self) -> None:
        self.canvas.clear_blast()
        self.clear_button.setEnabled(False)
        self._set_status("Highlight cleared; BLAST results remain in the table.")

    def _open_work_dir(self) -> None:
        if self._work_dir:
            open_in_file_manager(self._work_dir)

    # --------------------------------------------------------------- lifecycle
    def _shutdown_worker(self) -> None:
        self._closing = True
        if self._runner is not None:
            self._runner.cancel()
        worker = self.worker
        if worker is not None and worker.isRunning():
            worker.wait(5000)
            if worker.isRunning():
                worker.terminate()
                worker.wait(1000)
        self.worker = None
        self._runner = None

    def reject(self) -> None:  # noqa: D401 - Qt dialog API
        self._shutdown_worker()
        self._apply_timer.stop()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._shutdown_worker()
        self._apply_timer.stop()
        super().closeEvent(event)
