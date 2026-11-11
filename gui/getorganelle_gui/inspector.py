"""Right-hand inspector: current setup, toolchain and selected result."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .models import ORGANELLES
from .widgets import Badge, Separator, human_bp

GETORGANELLE_CITATION = (
    "Jin J-J, Yu W-B, Yang J-B, Song Y, dePamphilis CW, Yi T-S, Li D-Z. "
    "GetOrganelle: a fast and versatile toolkit for accurate de novo assembly of "
    "organelle genomes. Genome Biology 21, 241 (2020). "
    '<a href="https://doi.org/10.1186/s13059-020-02154-5">doi:10.1186/s13059-020-02154-5</a>'
)


class _Row(QWidget):
    """Caption above value; keeps long paths readable in a narrow panel."""

    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.left = QLabel(label)
        self.left.setObjectName("Caption")
        self.right = QLabel(value)
        self.right.setWordWrap(True)
        self.right.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.right.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        from PyQt5.QtWidgets import QSizePolicy
        self.right.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.left)
        layout.addWidget(self.right)
        self.set_value(value)

    def set_value(self, value: str) -> None:
        self.right.setText(value)


class InspectorPanel(QFrame):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self.setObjectName("Inspector")
        self.setFixedWidth(308)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(16, 18, 16, 18)
        self.body_layout.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        title = QLabel("Inspector")
        title.setObjectName("CardTitle")
        self.body_layout.addWidget(title)

        self._add_section("Run setup")
        self.mode_row = self._add_row("Mode", "")
        self.organelle_row = self._add_row("Organelle", "")
        self.output_row = self._add_row("Output", "")
        self.threads_row = self._add_row("Threads", "")
        self.scheme_row = self._add_row("Extending", "")
        self.body_layout.addWidget(Separator())

        self._add_section("Toolchain")
        self.tool_badge = Badge("Checking…", "idle")
        self.body_layout.addWidget(self.tool_badge)
        self.getorg_row = self._add_row("GetOrganelle", "")
        self.spades_row = self._add_row("SPAdes", "")
        self.bowtie2_row = self._add_row("Bowtie2", "")
        self.blast_row = self._add_row("BLAST+", "")
        self.python_row = self._add_row("Python", "")
        self.body_layout.addWidget(Separator())

        self._add_section("Selected result")
        self.selected_placeholder = QLabel("Select a result file to see its details.")
        self.selected_placeholder.setObjectName("Hint")
        self.selected_placeholder.setWordWrap(True)
        self.body_layout.addWidget(self.selected_placeholder)
        self.selected_rows = QWidget()
        self.selected_layout = QVBoxLayout(self.selected_rows)
        self.selected_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_layout.setSpacing(6)
        self.sel_kind = self._add_row_to(self.selected_layout, "Type", "")
        self.sel_name = self._add_row_to(self.selected_layout, "File", "")
        self.sel_sequences = self._add_row_to(self.selected_layout, "Sequences", "")
        self.sel_length = self._add_row_to(self.selected_layout, "Longest", "")
        self.sel_gc = self._add_row_to(self.selected_layout, "GC", "")
        self.selected_rows.hide()
        self.body_layout.addWidget(self.selected_rows)
        self.body_layout.addWidget(Separator())

        self._add_section("Citation")
        citation = QLabel(GETORGANELLE_CITATION)
        citation.setWordWrap(True)
        citation.setOpenExternalLinks(True)
        citation.setObjectName("Hint")
        citation.setTextInteractionFlags(Qt.TextBrowserInteraction)
        from PyQt5.QtWidgets import QSizePolicy
        citation.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        citation.setMinimumWidth(0)
        self.body_layout.addWidget(citation)
        self.body_layout.addStretch(1)

    def _add_section(self, text: str) -> None:
        label = QLabel(text.upper())
        label.setObjectName("Caption")
        font = label.font()
        font.setLetterSpacing(font.AbsoluteSpacing, 0.8)
        label.setFont(font)
        self.body_layout.addWidget(label)

    def _add_row(self, label: str, value: str) -> _Row:
        row = _Row(label, value)
        self.body_layout.addWidget(row)
        return row

    def _add_row_to(self, layout, label: str, value: str) -> _Row:
        row = _Row(label, value)
        layout.addWidget(row)
        return row

    def refresh(self) -> None:
        config = self.wb.config
        self.mode_row.set_value(config.mode.capitalize())
        self.organelle_row.set_value(
            ORGANELLES.get(config.organelle, {}).get("label", config.organelle)
        )
        self.output_row.set_value(config.output_dir.name)
        self.output_row.right.setToolTip(str(config.output_dir))
        self.threads_row.set_value(str(config.threads))
        self.scheme_row.set_value(
            f"-R {config.rounds} · {config.kmers}"
            if config.mode == "reads" and config.kmer_mode == "custom"
            else f"-R {config.rounds} · auto k-mers"
            if config.mode == "reads"
            else "Graph mode"
        )
        deps = self.wb.deps
        self.tool_badge.set_state(
            "success" if deps.ok else "warning",
            deps.summary_text(),
        )
        version = deps.getorganelle_version or "—"
        self.getorg_row.set_value(version)
        for row, key in (
            (self.spades_row, "spades"),
            (self.bowtie2_row, "bowtie2"),
            (self.blast_row, "blast"),
            (self.python_row, "python"),
        ):
            tool = deps.tools.get(key)
            if tool is None:
                row.set_value("missing")
            else:
                row.set_value(tool.version or ("found" if tool.ok else "missing"))
            row.right.setToolTip(tool.path if tool else "")

    def set_selected_item(self, item) -> None:
        if item is None:
            self.selected_placeholder.show()
            self.selected_rows.hide()
            return
        self.selected_placeholder.hide()
        self.selected_rows.show()
        self.sel_kind.set_value(item.kind.capitalize())
        self.sel_name.set_value(item.name)
        self.sel_name.right.setToolTip(item.path)
        self.sel_sequences.set_value(str(item.sequences) if item.sequences else "—")
        self.sel_length.set_value(human_bp(item.max_len) if item.max_len else "—")
        self.sel_gc.set_value(f"{item.gc_percent:.1f} %" if item.total_bp else "—")
