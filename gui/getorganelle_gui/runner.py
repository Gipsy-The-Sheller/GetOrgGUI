"""Background job execution with streaming logs and one Cancel action."""
from __future__ import annotations

import os
import re
import subprocess
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional

from PyQt5.QtCore import QElapsedTimer, QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from .command import CommandPlan, build_plan
from .models import (
    MODE_ASSEMBLY,
    MODE_DATABASE,
    MODE_READS,
    STATUS_CANCELLED,
    STATUS_ERROR,
    RunConfig,
    now_iso,
    slugify,
)
from .results import build_run_result, write_run_json
from .settings import Settings

STAGE_TABLE = {
    MODE_READS: [
        (r"Pre-reading fastq", "Pre-reading reads"),
        (r"Making seed reads", "Making seed reads"),
        (r"Pre-assembling", "Pre-assembling reads"),
        (r"Assembling using SPAdes", "Assembling with SPAdes"),
        (r"Adding initial words|Round \d+:|Extending \.\.\.", "Extending reads"),
        (r"Assembling finished", "Assembly finished"),
        (r"Slimming|Loading labels|Disentangling|Extracting .* from the assemblies", "Extracting organelle"),
        (r"Writing output", "Writing output"),
    ],
    MODE_ASSEMBLY: [
        (r"Processing assembly graph", "Reading assembly graph"),
        (r"Slimming", "Slimming graph"),
        (r"Loading labels|parse_tab_file|Parsing", "Loading labels"),
        (r"Disentangling", "Disentangling"),
        (r"Writing output", "Writing output"),
    ],
    MODE_DATABASE: [
        (r"Downloading|Initializing|Adding|Checking|Installing", "Configuring database"),
        (r"Done|finished|finished\.", "Database ready"),
    ],
}

_ERROR_PATTERN = re.compile(r"\b(ERROR|Traceback|AssertionError|Exception|failed)\b", re.I)
_WARNING_PATTERN = re.compile(r"\bWARNING\b", re.I)


class JobRunner(QObject):
    """Owns one GetOrganelle process.

    The runner never touches widgets.  It emits plain text and a final
    :class:`RunResult`, which is the same object the CLI writes to JSON.
    """

    started = pyqtSignal()
    log_line = pyqtSignal(str, str)
    stage_changed = pyqtSignal(int, int, str)
    tick = pyqtSignal(str)
    state_changed = pyqtSignal(str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[QProcess] = None
        self.plan: Optional[CommandPlan] = None
        self.config: Optional[RunConfig] = None
        self.settings: Optional[Settings] = None
        self.run_id = ""
        self.log_path = ""
        self._log_handle = None
        self._buffer = b""
        self._lines: Deque[str] = deque(maxlen=20000)
        self._stage_index = 0
        self._stage_total = 1
        self._stage_label = ""
        self._cancelled = False
        self._finished = False
        self._elapsed = QElapsedTimer()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._emit_tick)
        self._started_at = ""
        self._tool_version = ""

    # ------------------------------------------------------------------ state
    @property
    def is_running(self) -> bool:
        return bool(self.process and self.process.state() != QProcess.NotRunning)

    @property
    def stage_index(self) -> int:
        return self._stage_index

    @property
    def stage_total(self) -> int:
        return self._stage_total

    @property
    def elapsed_seconds(self) -> float:
        return self._elapsed.elapsed() / 1000.0 if self._elapsed.isValid() else 0.0

    def _set_state(self, state: str) -> None:
        self.state_changed.emit(state)

    # ------------------------------------------------------------------- start
    def start(
        self,
        config: RunConfig,
        settings: Settings,
        plan: Optional[CommandPlan] = None,
        tool_version: str = "",
    ) -> bool:
        if self.is_running:
            return False
        self.config = config
        self.settings = settings
        self._tool_version = tool_version
        self.plan = plan or build_plan(config, settings)
        self._cancelled = False
        self._finished = False
        self._buffer = b""
        self._lines.clear()
        self._stage_index = 0
        self._stage_label = ""
        stage_table = STAGE_TABLE.get(config.mode, STAGE_TABLE[MODE_READS])
        self._stage_total = len(stage_table)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = f"{stamp}_{slugify(config.run_name)}"
        # Never create the GetOrganelle output directory here: with
        # --overwrite GetOrganelle removes it itself, and an open log file in
        # that directory would make the removal fail on Windows.
        log_root = Path(settings.workspace_root) / "_workbench" / "logs"
        log_root.mkdir(parents=True, exist_ok=True)
        self.log_path = str(log_root / f"{self.run_id}.log")
        self._log_handle = open(self.log_path, "w", encoding="utf-8", errors="replace")
        self._started_at = now_iso()
        self._write_header()

        environment = QProcessEnvironment()
        for key, value in self.plan.env.items():
            environment.insert(str(key), str(value))
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.setWorkingDirectory(self.plan.cwd)
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self._elapsed.start()
        self._tick_timer.start()
        self._set_state("running")
        self.stage_changed.emit(0, self._stage_total, "Starting")
        self.started.emit()
        self.process.start(self.plan.program, self.plan.arguments)
        return True

    def _write_header(self) -> None:
        assert self._log_handle is not None
        header = [
            "# GetOrganelle Workbench run",
            f"# run_id: {self.run_id}",
            f"# started: {self._started_at}",
            f"# mode: {self.config.mode}",
            f"# organelle: {self.config.organelle}",
            f"# command: {self.plan.display}",
            "",
        ]
        self._log_handle.write("\n".join(header) + "\n")
        self._log_handle.flush()
        self.log_line.emit("Command: " + self.plan.display, "command")

    # ------------------------------------------------------------------ output
    def _read_output(self) -> None:
        if self.process is None:
            return
        chunk = bytes(self.process.readAllStandardOutput())
        if not chunk:
            return
        self._buffer += chunk
        while b"\n" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\n", 1)
            self._append_log(raw.decode("utf-8", errors="replace").rstrip("\r"), None)

    def _append_log(self, text: str, kind: Optional[str]) -> None:
        if self._log_handle is not None:
            self._log_handle.write(text + "\n")
            self._log_handle.flush()
        self._lines.append(text)
        if kind is None:
            kind = self._classify(text)
        self.log_line.emit(text, kind)
        self._detect_stage(text)

    @staticmethod
    def _classify(text: str) -> str:
        if not text.strip():
            return "output"
        if "Command:" in text and text.startswith("Command:"):
            return "command"
        if _WARNING_PATTERN.search(text):
            return "warning"
        if _ERROR_PATTERN.search(text):
            return "error"
        return "output"

    def _detect_stage(self, text: str) -> None:
        if self.config is None:
            return
        table = STAGE_TABLE.get(self.config.mode, STAGE_TABLE[MODE_READS])
        for index, (pattern, label) in enumerate(table, start=1):
            if re.search(pattern, text, re.I):
                if index > self._stage_index:
                    self._stage_index = index
                    self._stage_label = label
                    self.stage_changed.emit(index, self._stage_total, label)
                break

    def _emit_tick(self) -> None:
        seconds = int(self.elapsed_seconds)
        self.tick.emit(f"{seconds // 60:02d}:{seconds % 60:02d}")

    # ------------------------------------------------------------------- stop
    def cancel(self) -> None:
        if not self.is_running or self._cancelled:
            return
        self._cancelled = True
        self._append_log("[workbench] Cancelling the run…", "warning")
        if os.name == "nt" and self.process is not None:
            pid = int(self.process.processId())
            try:
                subprocess.Popen(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,
                )
            except OSError:
                self.process.kill()
        else:
            self.process.terminate()
        QTimer.singleShot(4000, self._force_kill)

    def _force_kill(self) -> None:
        if self.process is not None and self.is_running:
            self.process.kill()

    # ---------------------------------------------------------------- finish
    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart and not self._finished:
            self._append_log("[workbench] The process could not be started.", "error")
            self._finalize(-1, start_error=True)

    def _process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._finished:
            return
        self._read_output()
        if self._buffer:
            self._append_log(self._buffer.decode("utf-8", errors="replace").rstrip("\r"), None)
            self._buffer = b""
        crashed = exit_status == QProcess.CrashExit
        self._finalize(exit_code, crashed=crashed)

    def _finalize(self, exit_code: int, start_error: bool = False, crashed: bool = False) -> None:
        if self._finished:
            return
        self._finished = True
        self._tick_timer.stop()
        if self._elapsed.isValid():
            elapsed = self._elapsed.elapsed() / 1000.0
        else:
            elapsed = 0.0
        if self._log_handle is not None:
            self._log_handle.write(f"\n# finished: {now_iso()}\n# exit_code: {exit_code}\n")
            self._log_handle.flush()
            self._log_handle.close()
            self._log_handle = None
        if start_error:
            exit_code = -1
        result = build_run_result(
            self.config,
            run_id=self.run_id,
            exit_code=exit_code,
            log_lines=list(self._lines),
            started_at=self._started_at,
            finished_at=now_iso(),
            elapsed_s=elapsed,
            cancelled=self._cancelled,
        )
        if self.plan is not None:
            result.command = list(self.plan.argv)
            result.summary["command"] = list(self.plan.argv)
            result.summary["cwd"] = self.plan.cwd
            result.summary["log_path"] = self.log_path
        try:
            write_run_json(result)
        except OSError as exc:
            self._append_log(f"[workbench] Could not write run.json: {exc}", "warning")
        if crashed and result.status == STATUS_ERROR and not result.error_message:
            result.error_message = "The process crashed before it could report an error."
        self._set_state(
            "cancelled"
            if result.status == STATUS_CANCELLED
            else "failed"
            if result.status == STATUS_ERROR
            else "finished"
        )
        self.stage_changed.emit(self._stage_total, self._stage_total, "Finished")
        self.completed.emit(result)
        if result.status == STATUS_ERROR:
            self.failed.emit(result.error_message)

    # --------------------------------------------------------------- helpers
    def tail(self, count: int = 80) -> List[str]:
        return list(self._lines)[-count:]
