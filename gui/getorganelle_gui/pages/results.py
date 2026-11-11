"""Results page: typed result table, preview, warnings and provenance."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import ORGANELLES, STATUS_CANCELLED, STATUS_ERROR, STATUS_SUCCESS, STATUS_WARNING
from ..widgets import Badge, Card, EmptyState, human_bp, human_size
from .common import ScrollPage, caption, page_header

PREVIEW_LIMIT = 200_000


class ResultsPage(ScrollPage):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self.result = None
        self.items = []
        self.add(
            page_header(
                "Results",
                "Inspect assembled sequences and graphs, then open the output folder or export provenance.",
            )
        )
        self.empty_state = EmptyState(
            "No results yet",
            "Run GetOrganelle to see assemblies, graphs and provenance here.",
            icon="◇",
        )
        go_button = QPushButton("Go to inputs")
        go_button.setObjectName("PrimaryButton")
        go_button.clicked.connect(lambda: self.wb.show_page("inputs"))
        self.empty_state.add_action(go_button)
        self.add(self.empty_state)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        self.add(self.content)
        self.content.hide()

        self._build_summary()
        self._build_browser()
        self._build_warnings()
        self._build_provenance()
        self.add_stretch()

    # ------------------------------------------------------------------ build
    def _build_summary(self) -> None:
        self.summary_card = Card("")
        top = QHBoxLayout()
        self.status_badge = Badge("Idle", "idle")
        self.title_label = QLabel("")
        self.title_label.setObjectName("CardTitle")
        top.addWidget(self.status_badge)
        top.addWidget(self.title_label, 1)
        self.summary_card.body.addLayout(top)
        self.summary_text = caption("")
        self.summary_card.body.addWidget(self.summary_text)
        actions = QHBoxLayout()
        self.open_folder_button = QPushButton("Open output folder")
        self.open_folder_button.clicked.connect(self.wb.open_output_folder)
        self.export_button = QPushButton("Open run.json")
        self.export_button.clicked.connect(self.wb.open_run_json)
        self.copy_button = QPushButton("Copy command")
        self.copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.wb.last_command_display())
        )
        actions.addWidget(self.open_folder_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        self.summary_card.body.addLayout(actions)
        self.content_layout.addWidget(self.summary_card)

    def _build_browser(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = Card("Output files")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Type", "File", "Size"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 104)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setMinimumHeight(240)
        left.body.addWidget(self.table)
        splitter.addWidget(left)

        right = Card("Preview")
        preview_header = QHBoxLayout()
        self.preview_label = caption("Select a file to preview it.")
        self.open_file_button = QPushButton("Open file")
        self.open_file_button.setEnabled(False)
        self.open_file_button.clicked.connect(self._open_selected_file)
        preview_header.addWidget(self.preview_label, 1)
        preview_header.addWidget(self.open_file_button)
        right.body.addLayout(preview_header)
        self.preview_stats = caption("")
        right.body.addWidget(self.preview_stats)
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("Preview")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setMinimumHeight(240)
        right.body.addWidget(self.preview)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([500, 394])
        self.content_layout.addWidget(splitter)

    def _build_warnings(self) -> None:
        self.warnings_card = Card("Warnings")
        self.warnings_layout = QVBoxLayout()
        self.warnings_layout.setSpacing(6)
        self.warnings_card.body.addLayout(self.warnings_layout)
        self.warnings_card.hide()
        self.content_layout.addWidget(self.warnings_card)

    def _build_provenance(self) -> None:
        self.provenance_card = Card(
            "Provenance",
            "Every run writes run.json next to its outputs. The command below is the exact argument list that ran.",
        )
        self.provenance_text = caption("")
        self.provenance_card.body.addWidget(self.provenance_text)
        self.command_view = QPlainTextEdit()
        self.command_view.setObjectName("Preview")
        self.command_view.setReadOnly(True)
        self.command_view.setMaximumHeight(86)
        self.provenance_card.body.addWidget(self.command_view)
        self.content_layout.addWidget(self.provenance_card)

    # ------------------------------------------------------------------ state
    def show_result(self, result) -> None:
        self.result = result
        if result is None:
            self.clear()
            return
        self.empty_state.hide()
        self.content.show()
        self.items = list(result.items)
        self.title_label.setText(result.run_name)
        self.summary_text.setText(
            f"{ORGANELLES.get(result.organelle, {}).get('label', result.organelle)} · "
            f"{result.mode} · {result.elapsed_s:.1f} s · "
            f"{len(result.sequence_items)} sequence file(s) · {human_bp(result.total_bp)}"
        )
        state = {
            STATUS_SUCCESS: ("success", "Success"),
            STATUS_WARNING: ("warning", "Completed with warnings"),
            STATUS_ERROR: ("error", "Failed"),
            STATUS_CANCELLED: ("warning", "Cancelled"),
        }.get(result.status, ("idle", result.status))
        self.status_badge.set_state(*state)
        self.command_view.setPlainText(self.wb.last_command_display())
        self.provenance_text.setText(
            f"Run ID {result.run_id} · exit code {result.exit_code} · "
            f"started {result.started_at} · finished {result.finished_at}\n"
            f"Output: {result.output_dir}"
        )
        self._fill_table()
        self._fill_warnings()
        if self.items:
            self.table.selectRow(0)
        else:
            self.preview.setPlainText("No output files were produced.")

    def clear(self) -> None:
        self.result = None
        self.items = []
        self.table.setRowCount(0)
        self.preview.clear()
        self.content.hide()
        self.empty_state.show()

    def _fill_table(self) -> None:
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            type_item = QTableWidgetItem(item.kind.capitalize())
            type_item.setData(Qt.UserRole, item.path)
            self.table.setItem(row, 0, type_item)
            name_item = QTableWidgetItem(item.name)
            name_item.setToolTip(item.path)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(human_size(item.size)))

    def _fill_warnings(self) -> None:
        while self.warnings_layout.count():
            item = self.warnings_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        warnings = self.result.warnings if self.result else []
        self.warnings_card.setVisible(bool(warnings))
        for line in warnings[:12]:
            label = QLabel("⚠  " + line)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setObjectName("Hint")
            self.warnings_layout.addWidget(label)

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.open_file_button.setEnabled(False)
            return
        row = rows[0].row()
        if row < 0 or row >= len(self.items):
            return
        item = self.items[row]
        self.open_file_button.setEnabled(True)
        self.preview_label.setText(f"{item.name} · {human_size(item.size)}")
        if item.sequences:
            self.preview_stats.setText(
                f"{item.sequences} sequences · {human_bp(item.total_bp)} total · "
                f"{human_bp(item.max_len)} longest · {item.gc_percent:.1f}% GC"
            )
        else:
            self.preview_stats.setText(item.detail or "")
        self.preview.setPlainText(self._read_preview(item.path))
        self.wb.set_selected_item(item)

    def _open_selected_file(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self.items):
            self.wb.open_path(self.items[row].path)

    @staticmethod
    def _read_preview(path: str) -> str:
        file_path = Path(path)
        if not file_path.is_file():
            return "File is missing."
        try:
            if file_path.suffix.lower() in (".log", ".txt"):
                with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                    lines = handle.readlines()
                return "".join(lines[-400:])
            with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                data = handle.read(PREVIEW_LIMIT)
            if file_path.stat().st_size > PREVIEW_LIMIT:
                data += "\n… preview truncated …\n"
            return data
        except OSError as exc:
            return f"Cannot read file: {exc}"
