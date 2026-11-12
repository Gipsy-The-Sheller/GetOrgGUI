"""Main window: workflow rail + page stack + inspector + job center."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QByteArray, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, __version__
from .command import build_plan, display_command
from .database_dialog import DatabaseDialog
from .inspector import InspectorPanel
from .job_center import JobCenter
from .models import (
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SUCCESS,
    STATUS_WARNING,
    RunConfig,
)
from .pages.inputs import InputsPage
from .pages.parameters import ParametersPage
from .pages.preprocess import PreprocessPage
from .pages.results import ResultsPage
from .pages.run import RunPage
from .paths import (
    database_status,
    open_in_file_manager,
    probe_dependencies,
)
from .runner import JobRunner
from .settings import Settings
from .settings_dialog import SettingsDialog
from .theme import THEMES, Tokens, apply_theme, stylesheet
from .validation import has_errors, issues_by_field, validate_config
from .widgets import LogView, make_icon_button, path_name

INPUT_FIELDS = {"reads_1", "reads_2", "unpaired", "graph", "run_name", "database"}
OUTPUT_FIELDS = {"output_root", "overwrite"}
PREPROCESS_FIELDS = {
    "preprocess",
    "adapter_mode",
    "adapter_sequence",
    "adapter_sequence_r2",
    "fastp_quality",
    "fastp_unqualified_percent",
    "fastp_min_length",
    "trim_front1",
    "trim_tail1",
    "trim_front2",
    "trim_tail2",
    "fastp_threads",
    "fastp_extra_args",
}
PARAM_FIELDS = {
    "threads",
    "rounds",
    "kmers",
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


class LogDialog(QDialog):
    """Non-modal full console window."""

    def __init__(self, parent, tokens: Tokens):
        super().__init__(parent)
        self.setWindowTitle("GetOrganelle console")
        self.resize(960, 640)
        self.setModal(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        toolbar = QHBoxLayout()
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        toolbar.addWidget(self.auto_scroll)
        toolbar.addStretch(1)
        toolbar.addWidget(clear)
        toolbar.addWidget(close)
        layout.addLayout(toolbar)
        self.log = LogView()
        self.log.set_tokens(tokens)
        layout.addWidget(self.log)
        self.auto_scroll.toggled.connect(self._set_auto_scroll)

    def _set_auto_scroll(self, enabled: bool) -> None:
        self.log.auto_scroll = enabled

    def _clear(self) -> None:
        self.log.clear()

    def append_line(self, text: str, kind: str) -> None:
        self.log.append_line(text, kind)

    def set_tokens(self, tokens: Tokens) -> None:
        self.log.set_tokens(tokens)


class MainWindow(QMainWindow):
    log_appended = pyqtSignal(str, str)

    def __init__(self, settings: Settings, apply_global_theme: bool = True):
        super().__init__()
        self._apply_global_theme = bool(apply_global_theme)
        self.settings = settings.normalize()
        self.deps = probe_dependencies(self.settings, check_versions=False)
        self.db_status = database_status(self.settings)
        self.config = RunConfig(
            organelle=self.settings.organelle,
            threads=self.settings.threads,
            output_root=self.settings.workspace_root,
            keep_temp=self.settings.keep_temp,
        )
        self.config.run_name = self.config.suggested_run_name()
        self.result = None
        self.selected_item = None
        self.issues = []
        self._pages_ready = False
        self._console_dialog = None
        self._database_dialog = None
        self._tokens = self._apply_theme_scope()

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setMinimumSize(1024, 640)
        self.resize(1280, 800)
        self._build_ui()

        self.runner = JobRunner(self)
        self.runner.started.connect(self._on_job_started)
        self.runner.log_line.connect(self._on_job_log)
        self.runner.stage_changed.connect(self._on_job_stage)
        self.runner.tick.connect(self._on_job_tick)
        self.runner.completed.connect(self._on_job_completed)
        self.runner.state_changed.connect(self._on_job_state)

        self._install_shortcuts()
        self._restore_geometry()
        self._pages_ready = True
        self.theme_button.setText("☀" if self.settings.theme == "dark" else "☾")
        self._apply_log_tokens()
        self.on_config_changed()

    # ------------------------------------------------------------------- build
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_rail())
        self.pages = QStackedWidget()
        self.inputs_page = InputsPage(self)
        self.preprocess_page = PreprocessPage(self)
        self.parameters_page = ParametersPage(self)
        self.run_page = RunPage(self)
        self.results_page = ResultsPage(self)
        for page in (
            self.inputs_page,
            self.preprocess_page,
            self.parameters_page,
            self.run_page,
            self.results_page,
        ):
            self.pages.addWidget(page)
        self.pages.currentChanged.connect(self._on_page_changed)
        body.addWidget(self.pages, 1)
        self.inspector = InspectorPanel(self)
        body.addWidget(self.inspector)
        root.addLayout(body, 1)

        self.job_center = JobCenter(self)
        root.addWidget(self.job_center)
        self.setCentralWidget(central)

        status = QStatusBar()
        status.setObjectName("StatusBar")
        status.setSizeGripEnabled(False)
        self.status_workspace = QLabel("")
        self.status_deps = QLabel("")
        self.status_python = QLabel("")
        self.status_version = QLabel(f"v{__version__}")
        status.addWidget(self.status_workspace, 1)
        status.addPermanentWidget(self.status_deps)
        status.addPermanentWidget(self.status_python)
        status.addPermanentWidget(self.status_version)
        self.setStatusBar(status)

        self.inputs_page.organelle_changed.connect(self.parameters_page.update_for_organelle)

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 8, 16, 8)
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("CardTitle")
        subtitle = QLabel("Native organelle assembly")
        subtitle.setObjectName("Caption")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)

        self.workspace_button = QPushButton("Workspace")
        self.workspace_button.setObjectName("SecondaryButton")
        self.workspace_button.clicked.connect(self.change_workspace)
        layout.addWidget(self.workspace_button)

        self.deps_button = QPushButton("Toolchain")
        self.deps_button.setObjectName("SecondaryButton")
        self.deps_button.clicked.connect(self.open_settings)
        layout.addWidget(self.deps_button)

        self.theme_button = make_icon_button("☾", "Toggle light/dark theme", "Toggle theme")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.settings_button = make_icon_button("⚙", "Settings (Ctrl+,)", "Open settings")
        self.settings_button.clicked.connect(self.open_settings)
        self.about_button = make_icon_button("?", "About GetOrganelle Workbench", "About")
        self.about_button.clicked.connect(self.show_about)
        layout.addWidget(self.theme_button)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.about_button)
        return bar

    def _build_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("Rail")
        rail.setFixedWidth(196)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(5)
        heading = QLabel("WORKFLOW")
        heading.setObjectName("Caption")
        layout.addWidget(heading)
        self.rail_group = QButtonGroup(self)
        self.rail_group.setExclusive(True)
        self.rail_buttons = {}
        for key, number, title, subtitle in (
            ("inputs", "1", "Inputs", "Choose data"),
            ("preprocess", "2", "Preprocess", "fastp trimming"),
            ("parameters", "3", "Parameters", "Tune options"),
            ("run", "4", "Run", "Start and monitor"),
            ("results", "5", "Results", "Inspect outputs"),
        ):
            button = QPushButton(f"  {number}   {title}\n      {subtitle}")
            button.setObjectName("RailButton")
            button.setCheckable(True)
            button.setMinimumHeight(42)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, page=key: self.show_page(page))
            self.rail_group.addButton(button)
            layout.addWidget(button)
            self.rail_buttons[key] = button
        self.rail_buttons["inputs"].setChecked(True)
        layout.addStretch(1)
        version = QLabel(f"GetOrganelle {self.deps.getorganelle_version or '—'}\nWorkbench {__version__}")
        version.setObjectName("Hint")
        layout.addWidget(version)
        return rail

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("F5"), self, activated=self.start_run)
        QShortcut(QKeySequence("Esc"), self, activated=self._escape)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=lambda: self.show_page("inputs"))
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self.open_output_folder)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.open_console)

    # ------------------------------------------------------------------ state
    def show_page(self, key: str) -> None:
        index = {
            "inputs": 0,
            "preprocess": 1,
            "parameters": 2,
            "run": 3,
            "results": 4,
        }.get(key, 0)
        if key == "results" and self.result is None:
            self.results_page.clear()
        self.pages.setCurrentIndex(index)
        self.rail_buttons[key].setChecked(True)

    def _on_page_changed(self, index: int) -> None:
        self.on_config_changed()

    def on_config_changed(self) -> None:
        if not self._pages_ready:
            return
        self.parameters_page.set_mode(self.config.mode)
        self.preprocess_page.update_for_mode(self.config.mode)
        self.issues = validate_config(self.config, self.settings, self.deps, self.db_status)
        grouped = issues_by_field(self.issues)
        self.inputs_page.apply_issues(grouped)
        self.preprocess_page.apply_issues(grouped)
        self.parameters_page.apply_issues(grouped)
        self.parameters_page.update_command_preview()
        self.run_page.refresh_summary(self.issues)
        self.inspector.refresh()
        self._update_rail_status()
        self._update_status_bar()

    def command_display(self) -> str:
        try:
            return build_plan(self.config, self.settings).display
        except Exception as exc:  # keep the preview useful while fields are incomplete
            return f"<cannot build command: {exc}>"

    def last_command_display(self) -> str:
        if self.result is not None and self.result.command:
            return display_command(self.result.command)
        return self.command_display()

    def _update_rail_status(self) -> None:
        errors = {issue.field for issue in self.issues if issue.is_error}
        input_ok = not (errors & INPUT_FIELDS)
        preprocess_ok = not (errors & PREPROCESS_FIELDS)
        param_ok = not (errors & PARAM_FIELDS)
        run_ok = not errors
        results_ok = self.result is not None
        states = {
            "inputs": input_ok,
            "preprocess": preprocess_ok,
            "parameters": param_ok,
            "run": run_ok,
            "results": results_ok,
        }
        labels = {
            "inputs": ("1", "Inputs", "Choose data"),
            "preprocess": ("2", "Preprocess", "fastp trimming"),
            "parameters": ("3", "Parameters", "Tune options"),
            "run": ("4", "Run", "Start and monitor"),
            "results": ("5", "Results", "Inspect outputs"),
        }
        for key, ready in states.items():
            number, title, subtitle = labels[key]
            symbol = "✓" if ready else "!"
            button = self.rail_buttons[key]
            button.setText(f"{symbol}  {number}   {title}\n      {subtitle}")
            button.setToolTip(
                "Ready" if ready else "Needs attention — open this step and check the highlighted fields."
            )

    def _update_status_bar(self) -> None:
        workspace = self.config.output_root or self.settings.workspace_root
        self.status_workspace.setText(f"Workspace: {workspace}")
        self.status_workspace.setToolTip(workspace)
        self.workspace_button.setText(f"Workspace: {path_name(workspace, 30)}")
        self.workspace_button.setToolTip(workspace)
        self.deps_button.setText(
            ("✓  Toolchain ready" if self.deps.ok else "⚠  Toolchain needs attention")
        )
        self.deps_button.setToolTip(self.deps.summary_text())
        self.status_deps.setText(
            f"Toolchain: {'ready' if self.deps.ok else self.deps.summary_text()}"
        )
        self.status_python.setText(f"Python: {Path(self.settings.python_executable).name}")
        self.status_version.setText(f"v{__version__}")

    # -------------------------------------------------------------------- run
    def start_run(self) -> None:
        if self.runner.is_running:
            return
        self.inputs_page.sync_to_config()
        self.preprocess_page.sync_to_config()
        self.parameters_page.sync_to_config()
        self.on_config_changed()
        if has_errors(self.issues):
            self.show_page("run")
            self.run_page.append_log(
                "[workbench] Fix the highlighted fields before starting the run.", "error"
            )
            return
        output_dir = self.config.output_dir
        if output_dir.is_dir() and any(output_dir.iterdir()):
            answer = QMessageBox.question(
                self,
                "Replace existing output?",
                f"{output_dir}\n\nThis folder already contains files. "
                "Continuing will overwrite results in this folder. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self.config.overwrite = True
            self.inputs_page.overwrite_check.setChecked(True)
        self.settings.workspace_root = self.config.output_root
        self.settings.organelle = (self.config.organelle.split(",") or ["embplant_pt"])[0]
        self.settings.threads = self.config.threads
        self.settings.keep_temp = self.config.keep_temp
        for path in (
            self.config.reads_1,
            self.config.reads_2,
            self.config.graph,
        ):
            if path:
                self.settings.add_recent_input(path)
        try:
            self.settings.save()
        except OSError:
            pass
        self.run_page.clear_log()
        self.run_page.set_running(True)
        self.job_center.set_running(True)
        self._set_editing_enabled(False)
        self.show_page("run")
        if not self.runner.start(
            self.config,
            self.settings,
            tool_version=self.deps.getorganelle_version,
        ):
            self.run_page.set_running(False)
            self.job_center.set_running(False)
            self._set_editing_enabled(True)

    def _set_editing_enabled(self, enabled: bool) -> None:
        self.inputs_page.setEnabled(enabled)
        self.preprocess_page.setEnabled(enabled)
        self.parameters_page.setEnabled(enabled)
        self.rail_buttons["inputs"].setEnabled(enabled)
        self.rail_buttons["preprocess"].setEnabled(enabled)
        self.rail_buttons["parameters"].setEnabled(enabled)

    def cancel_run(self) -> None:
        if self.runner.is_running:
            self.runner.cancel()
            self.job_center.cancel_button.setEnabled(False)

    def _escape(self) -> None:
        if self.runner.is_running:
            self.cancel_run()

    def _on_job_started(self) -> None:
        self.job_center.set_running(True)
        self.job_center.badge.set_state("running", "Running")
        self.run_page.ensureWidgetVisible(self.run_page.log_card)

    def _on_job_log(self, text: str, kind: str) -> None:
        self.run_page.append_log(text, kind)
        self.job_center.set_last_line(text)
        if self._console_dialog is not None:
            self._console_dialog.append_line(text, kind)
        self.log_appended.emit(text, kind)

    def _on_job_stage(self, index: int, total: int, label: str) -> None:
        self.run_page.set_stage(index, total, label)
        self.job_center.set_stage(index, total, label)

    def _on_job_tick(self, text: str) -> None:
        self.run_page.set_elapsed(text)
        self.job_center.set_tick(text)

    def _on_job_state(self, state: str) -> None:
        if state == "running":
            self.job_center.set_running(True)

    def _on_job_completed(self, result) -> None:
        self.result = result
        self.selected_item = None
        self.inspector.set_selected_item(None)
        self.run_page.set_running(False)
        self.run_page.show_result(result)
        self.results_page.show_result(result)
        self.job_center.set_result(result)
        self._set_editing_enabled(True)
        self._update_rail_status()
        self.inspector.refresh()
        self._update_status_bar()
        if result.status == STATUS_SUCCESS:
            self.statusBar().showMessage("Run completed successfully.", 8000)
        elif result.status == STATUS_ERROR:
            self.statusBar().showMessage("Run failed. Open the log for details.", 12000)
        elif result.status == STATUS_CANCELLED:
            self.statusBar().showMessage("Run cancelled.", 8000)
        elif result.status == STATUS_WARNING:
            self.statusBar().showMessage("Run completed without an organelle sequence file.", 12000)

    # ------------------------------------------------------------------ output
    def open_output_folder(self) -> None:
        directory = Path(self.result.output_dir) if self.result else self.config.output_dir
        if not directory.exists():
            QMessageBox.information(
                self, "Output not found", f"The output folder does not exist yet:\n{directory}"
            )
            return
        try:
            open_in_file_manager(str(directory))
        except OSError as exc:
            QMessageBox.warning(self, "Cannot open folder", str(exc))

    def open_run_json(self) -> None:
        if self.result is None:
            return
        path = Path(self.result.output_dir) / "run.json"
        if not path.is_file():
            QMessageBox.information(self, "run.json missing", f"Not found:\n{path}")
            return
        try:
            open_in_file_manager(str(path))
        except OSError as exc:
            QMessageBox.warning(self, "Cannot open file", str(exc))

    def open_path(self, path: str) -> None:
        try:
            open_in_file_manager(path)
        except OSError as exc:
            QMessageBox.warning(self, "Cannot open file", str(exc))

    def set_selected_item(self, item) -> None:
        self.selected_item = item
        self.inspector.set_selected_item(item)

    # ---------------------------------------------------------------- dialogs
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.deps, self)
        if dialog.exec_() != QDialog.Accepted or dialog.result_settings is None:
            return
        self.settings = dialog.result_settings.normalize()
        try:
            self.settings.save()
        except OSError:
            pass
        self.deps = probe_dependencies(self.settings, check_versions=False)
        self.db_status = database_status(self.settings)
        self.results_page.set_settings(self.settings)
        self.config.output_root = self.settings.workspace_root
        self.config.threads = self.settings.threads
        self.inputs_page.workspace_input.setText(self.settings.workspace_root)
        self.inputs_page.refresh_databases()
        self.preprocess_page.update_availability()
        self._tokens = self._apply_theme_scope()
        self.theme_button.setText("☀" if self.settings.theme == "dark" else "☾")
        self._apply_log_tokens()
        self.on_config_changed()

    def open_database_dialog(self) -> None:
        if self._database_dialog is not None and self._database_dialog.isVisible():
            self._database_dialog.raise_()
            self._database_dialog.activateWindow()
            return
        self._database_dialog = DatabaseDialog(self, self)
        self._database_dialog.finished.connect(self._on_database_dialog_closed)
        self._database_dialog.show()

    def _on_database_dialog_closed(self, _result: int) -> None:
        self.db_status = database_status(self.settings)
        self.inputs_page.refresh_databases()
        self.on_config_changed()

    def open_console(self) -> None:
        if self._console_dialog is None:
            self._console_dialog = LogDialog(self, self._tokens)
            self._console_dialog.finished.connect(self._on_console_closed)
        self._console_dialog.log.setPlainText(self.run_page.log_view.toPlainText())
        self._console_dialog.show()
        self._console_dialog.raise_()
        self._console_dialog.activateWindow()

    def _on_console_closed(self, _result: int) -> None:
        self._console_dialog = None

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>A YR-MPE-style workbench for the native desktop build of GetOrganelle.</p>"
            f"<p>GetOrganelle {self.deps.getorganelle_version or '—'}<br>"
            "SPAdes, Bowtie2 and BLAST+ are bundled under GetOrganelleDep.</p>"
            '<p>GetOrganelle: Jin et al. 2020, <i>Genome Biology</i> 21:241. '
            '<a href="https://doi.org/10.1186/s13059-020-02154-5">doi:10.1186/s13059-020-02154-5</a></p>'
            "<p>GUI license: AGPL-3.0-only. Bundled tools keep their original licenses.</p>",
        )

    def toggle_theme(self) -> None:
        self.settings.theme = "dark" if self.settings.theme == "light" else "light"
        try:
            self.settings.save()
        except OSError:
            pass
        self._tokens = self._apply_theme_scope()
        self.theme_button.setText("☀" if self.settings.theme == "dark" else "☾")
        self._apply_log_tokens()

    def _apply_theme_scope(self) -> Tokens:
        """Apply the theme globally standalone, or locally when embedded."""
        if self._apply_global_theme:
            return apply_theme(QApplication.instance(), self.settings.theme)
        tokens = THEMES.get(self.settings.theme, THEMES["light"])
        self.setStyleSheet(stylesheet(tokens))
        return tokens

    def _apply_log_tokens(self) -> None:
        self.run_page.log_view.set_tokens(self._tokens)
        self.results_page.set_tokens(self._tokens)
        if self._console_dialog is not None:
            self._console_dialog.set_tokens(self._tokens)

    def change_workspace(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select workspace folder", self.config.output_root
        )
        if not directory:
            return
        self.settings.workspace_root = directory
        self.config.output_root = directory
        self.inputs_page.workspace_input.setText(directory)
        try:
            self.settings.save()
        except OSError:
            pass
        self.on_config_changed()

    def refresh_databases(self) -> None:
        self.db_status = database_status(self.settings)
        self.inputs_page.refresh_databases()

    # ---------------------------------------------------------------- window
    def run(self, import_from=None, import_data=None, workdir=None, **kwargs):
        """Return this widget for YRTools/YR-MPE host insertion.

        The YRTools plugin loader creates an entry object and calls
        ``entry.run()``; returning ``self`` keeps the main workbench widget
        intact for a host tab or splitter.  Standalone startup still calls
        ``show()`` from :mod:`getorganelle_gui.app`.
        """
        return self

    def _restore_geometry(self) -> None:
        encoded = self.settings.window_geometry
        if encoded:
            try:
                self.restoreGeometry(QByteArray.fromBase64(encoded.encode("ascii")))
            except (ValueError, UnicodeEncodeError):
                pass

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.runner.is_running:
            answer = QMessageBox.question(
                self,
                "A run is still active",
                "GetOrganelle is still running. Cancel the run and quit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.runner.cancel()
            if self.runner.process is not None:
                self.runner.process.waitForFinished(3000)
        self.results_page.shutdown_graph_view()
        self.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        try:
            self.settings.save()
        except OSError:
            pass
        event.accept()
