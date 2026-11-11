"""Settings dialog with an explicit, asynchronous dependency check."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .models import ORGANELLES
from .paths import probe_dependencies
from .settings import Settings
from .widgets import Badge, FileInput
from .pages.common import caption, hint

EXE_FILTER = "Executables (*.exe);;All files (*)"
PYTHON_FILTER = "Python (*.exe python.exe);;All files (*)"


class _ProbeThread(QThread):
    report_ready = pyqtSignal(object)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:  # noqa: D401 - QThread API
        try:
            self.report_ready.emit(probe_dependencies(self.settings, check_versions=True))
        except Exception as exc:  # never let a probe crash the dialog
            self.report_ready.emit(exc)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, deps, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(760, 620)
        self.settings = Settings.from_dict(settings.to_dict())
        self._probe_thread = None
        self.result_settings = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(
            caption("Paths are validated before saving. The dependency check actually starts each tool.")
        )

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_paths_tab(), "Paths")
        self.tabs.addTab(self._build_runtime_tab(), "Runtime")
        self.tabs.addTab(self._build_appearance_tab(), "Appearance")
        self.tabs.addTab(self._build_dependencies_tab(), "Dependencies")
        layout.addWidget(self.tabs, 1)

        self.error_label = QLabel("")
        self.error_label.setObjectName("Hint")
        self.error_label.setStyleSheet("color: palette(highlight);")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        self._load_values()

    # ------------------------------------------------------------------ tabs
    def _build_paths_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.getorg_input = FileInput(mode="directory", placeholder="Folder containing get_organelle_from_reads.py")
        self.dep_input = FileInput(mode="directory", placeholder="GetOrganelleDep/Windows")
        self.python_input = FileInput(filters=PYTHON_FILTER, placeholder="python.exe")
        self.workspace_input = FileInput(mode="directory", placeholder="Folder for runs")
        self.config_input = FileInput(mode="directory", placeholder="Optional: custom GetOrganelle config folder")
        self.extra_path_edit = QLineEdit()
        self.extra_path_edit.setPlaceholderText("Optional: extra PATH entries separated by ;")
        form.addRow("GetOrganelle source", self.getorg_input)
        form.addRow("Bundled dependencies", self.dep_input)
        form.addRow("Python interpreter", self.python_input)
        form.addRow("Workspace", self.workspace_input)
        form.addRow("GetOrganelle config", self.config_input)
        form.addRow("Extra PATH", self.extra_path_edit)
        form.addRow("", hint("Use python.exe, not pythonw.exe, so logs can be streamed from GetOrganelle."))
        return page

    def _build_runtime_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setSuffix(" threads")
        self.organelle_combo = QComboBox()
        for key, meta in ORGANELLES.items():
            self.organelle_combo.addItem(meta["label"], key)
        self.keep_temp_check = QCheckBox("Keep temporary files by default")
        form.addRow("Default threads", self.threads_spin)
        form.addRow("Default organelle", self.organelle_combo)
        form.addRow("", self.keep_temp_check)
        form.addRow("", hint("These values seed a new session; every run can override them."))
        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.currentIndexChanged.connect(self._update_theme_preview)
        self.theme_preview = Badge("Preview", "info")
        form.addRow("Theme", self.theme_combo)
        form.addRow("State preview", self.theme_preview)
        form.addRow("", hint("Status colours always come with an icon and text label."))
        return page

    def _build_dependencies_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.deps_badge = Badge("Not checked", "idle")
        self.check_button = QPushButton("Check now")
        self.check_button.clicked.connect(self._check_dependencies)
        top.addWidget(self.deps_badge)
        top.addStretch(1)
        top.addWidget(self.check_button)
        layout.addLayout(top)
        self.deps_detail = caption("")
        layout.addWidget(self.deps_detail)
        self.deps_table = QTableWidget(0, 4)
        self.deps_table.setHorizontalHeaderLabels(["Component", "Status", "Version", "Path"])
        self.deps_table.verticalHeader().setVisible(False)
        self.deps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.deps_table.setSelectionMode(QTableWidget.NoSelection)
        self.deps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.deps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.deps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.deps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.deps_table, 1)
        return page

    # ----------------------------------------------------------------- values
    def _load_values(self) -> None:
        settings = self.settings
        self.getorg_input.setText(settings.getorganelle_root)
        self.dep_input.setText(settings.dep_root)
        self.python_input.setText(settings.python_executable)
        self.workspace_input.setText(settings.workspace_root)
        self.config_input.setText(settings.config_dir)
        self.extra_path_edit.setText(settings.extra_path)
        self.threads_spin.setValue(settings.threads)
        index = self.organelle_combo.findData(settings.organelle)
        if index >= 0:
            self.organelle_combo.setCurrentIndex(index)
        self.keep_temp_check.setChecked(settings.keep_temp)
        theme_index = self.theme_combo.findData(settings.theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
        self._update_theme_preview()

    def _update_theme_preview(self) -> None:
        self.theme_preview.set_state("info", "Info  ·  running")
        self.theme_preview.setVisible(True)

    def _collect(self) -> Settings:
        settings = Settings()
        settings.getorganelle_root = self.getorg_input.text()
        settings.dep_root = self.dep_input.text()
        settings.python_executable = self.python_input.text()
        settings.workspace_root = self.workspace_input.text()
        settings.config_dir = self.config_input.text()
        settings.extra_path = self.extra_path_edit.text().strip()
        settings.threads = self.threads_spin.value()
        settings.organelle = self.organelle_combo.currentData() or "embplant_pt"
        settings.keep_temp = self.keep_temp_check.isChecked()
        settings.theme = self.theme_combo.currentData() or "light"
        settings.window_geometry = self.settings.window_geometry
        settings.recent_inputs = list(self.settings.recent_inputs)
        return settings.normalize()

    def _save(self) -> None:
        settings = self._collect()
        problems = []
        getorg_root = Path(settings.getorganelle_root)
        if not (getorg_root / "get_organelle_from_reads.py").is_file():
            problems.append("GetOrganelle source folder does not contain get_organelle_from_reads.py.")
        if not Path(settings.dep_root).is_dir():
            problems.append("Bundled dependencies folder does not exist.")
        if not Path(settings.python_executable).is_file():
            problems.append("Python interpreter does not exist.")
        if not settings.workspace_root:
            problems.append("Workspace folder is required.")
        if problems:
            self.error_label.setText(" ".join(problems))
            self.error_label.show()
            return
        self.error_label.hide()
        self.result_settings = settings
        self.accept()

    # ------------------------------------------------------------- dependency
    def _check_dependencies(self) -> None:
        if self._probe_thread is not None and self._probe_thread.isRunning():
            return
        self.error_label.hide()
        self.check_button.setEnabled(False)
        self.deps_badge.set_state("running", "Checking…")
        self.deps_detail.setText("Starting each configured executable…")
        snapshot = self._collect()
        self._probe_thread = _ProbeThread(snapshot, self)
        self._probe_thread.report_ready.connect(self._on_probe_ready)
        self._probe_thread.start()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._probe_thread is not None and self._probe_thread.isRunning():
            self._probe_thread.quit()
            self._probe_thread.wait(5000)
        super().closeEvent(event)

    def _on_probe_ready(self, report) -> None:
        self.check_button.setEnabled(True)
        if isinstance(report, Exception):
            self.deps_badge.set_state("error", "Check failed")
            self.deps_detail.setText(str(report))
            return
        self.deps_badge.set_state(
            "success" if report.ok else "warning",
            "Ready" if report.ok else "Needs attention",
        )
        self.deps_detail.setText(
            f"GetOrganelle {report.getorganelle_version or '—'} · "
            f"config {report.config_dir}"
        )
        rows = list(report.tools.values())
        self.deps_table.setRowCount(len(rows) + len(report.modules))
        for row, tool in enumerate(rows):
            self.deps_table.setItem(row, 0, QTableWidgetItem(tool.label))
            status = "✓ Ready" if tool.ok else ("○ Optional" if not tool.required else "⚠ Missing")
            self.deps_table.setItem(row, 1, QTableWidgetItem(status))
            self.deps_table.setItem(row, 2, QTableWidgetItem(tool.version or "—"))
            self.deps_table.setItem(row, 3, QTableWidgetItem(tool.path))
        offset = len(rows)
        for row, (name, ok) in enumerate(report.modules.items(), start=offset):
            self.deps_table.setItem(row, 0, QTableWidgetItem(f"Python: {name}"))
            self.deps_table.setItem(row, 1, QTableWidgetItem("✓ Ready" if ok else "⚠ Missing"))
            self.deps_table.setItem(row, 2, QTableWidgetItem(""))
            self.deps_table.setItem(row, 3, QTableWidgetItem(""))
