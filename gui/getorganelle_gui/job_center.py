"""Persistent job center: one place for progress, Cancel and output."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .models import STATUS_CANCELLED, STATUS_ERROR, STATUS_SUCCESS, STATUS_WARNING
from .widgets import Badge


class JobCenter(QFrame):
    def __init__(self, workbench, parent=None):
        super().__init__(parent)
        self.wb = workbench
        self.setObjectName("JobCenter")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.badge = Badge("Idle", "idle")
        self.stage = QLabel("No job is running.")
        self.stage.setObjectName("Caption")
        self.elapsed = QLabel("00:00")
        self.elapsed.setObjectName("Caption")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumWidth(140)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("DangerButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.wb.cancel_run)
        self.console_button = QPushButton("Console")
        self.console_button.clicked.connect(self.wb.open_console)
        self.output_button = QPushButton("Open output")
        self.output_button.setEnabled(False)
        self.output_button.clicked.connect(self.wb.open_output_folder)
        row.addWidget(self.badge)
        row.addWidget(self.progress, 2)
        row.addWidget(self.stage, 2)
        row.addWidget(self.elapsed)
        row.addWidget(self.console_button)
        row.addWidget(self.cancel_button)
        row.addWidget(self.output_button)
        outer.addLayout(row)

        self.last_line = QLabel("")
        self.last_line.setObjectName("Hint")
        self.last_line.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.last_line)

    def set_running(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)
        if running:
            self.badge.set_state("running", "Running")
            self.progress.setValue(0)
            self.stage.setText("Starting…")
            self.output_button.setEnabled(False)
        else:
            self.progress.setValue(self.progress.maximum() if self.progress.value() else 0)

    def set_stage(self, index: int, total: int, label: str) -> None:
        if total <= 0:
            return
        percent = int(max(0, min(index, total)) / total * 100)
        self.progress.setValue(percent)
        self.stage.setText(label)

    def set_tick(self, text: str) -> None:
        self.elapsed.setText(text)

    def set_last_line(self, text: str) -> None:
        self.last_line.setText(text[-220:])

    def set_result(self, result) -> None:
        self.cancel_button.setEnabled(False)
        self.output_button.setEnabled(True)
        self.progress.setValue(100)
        if result.status == STATUS_SUCCESS:
            self.badge.set_state("success", "Completed")
        elif result.status in (STATUS_WARNING, STATUS_CANCELLED):
            self.badge.set_state("warning", "Cancelled" if result.status == STATUS_CANCELLED else "Warning")
        elif result.status == STATUS_ERROR:
            self.badge.set_state("error", "Failed")
        else:
            self.badge.set_state("idle", "Idle")
        self.stage.setText(f"Finished in {result.elapsed_s:.1f} s")
        self.elapsed.setText("00:00")

    def reset(self) -> None:
        self.badge.set_state("idle", "Idle")
        self.progress.setValue(0)
        self.stage.setText("No job is running.")
        self.elapsed.setText("00:00")
        self.last_line.clear()
        self.cancel_button.setEnabled(False)
