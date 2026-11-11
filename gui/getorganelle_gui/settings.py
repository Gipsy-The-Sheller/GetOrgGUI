"""Persistent application settings.

The GUI stores one small JSON document per user under
``%APPDATA%/GetOrganelleWorkbench/settings.json`` (override with the
``GETORGANELLE_WORKBENCH_HOME`` environment variable).  Tool paths are kept
explicit so the application can run from the repository checkout, from the
portable release package, or from a YR-MPE installation.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

APP_DIR_NAME = "GetOrganelleWorkbench"


def repository_root() -> Path:
    """Return the GetOrganelle Windows repository/package root."""
    return Path(__file__).resolve().parents[2]


def default_python() -> str:
    """Prefer python.exe over pythonw.exe for subprocesses.

    When the GUI is started with ``pythonw.exe`` there is no console and
    ``sys.stdout`` may be unusable inside the child.  GetOrganelle writes its
    progress to stdout/stderr, so we always launch the console interpreter.
    """
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        candidate = executable.with_name("python.exe")
        if candidate.is_file():
            return str(candidate)
    return str(executable)


def default_threads() -> int:
    return max(1, min(os.cpu_count() or 4, 8))


def settings_directory() -> Path:
    override = os.environ.get("GETORGANELLE_WORKBENCH_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / ".getorganelle_workbench"


def settings_file() -> Path:
    return settings_directory() / "settings.json"


@dataclass
class Settings:
    workspace_root: str = ""
    getorganelle_root: str = ""
    dep_root: str = ""
    python_executable: str = ""
    config_dir: str = ""
    extra_path: str = ""
    theme: str = "light"
    threads: int = 0
    organelle: str = "embplant_pt"
    keep_temp: bool = False
    window_geometry: str = ""
    recent_inputs: List[str] = field(default_factory=list)

    def normalize(self) -> "Settings":
        root = repository_root()
        if not self.getorganelle_root:
            self.getorganelle_root = str(root / "GetOrganelle")
        if not self.dep_root:
            self.dep_root = str(
                Path(self.getorganelle_root) / "GetOrganelleDep" / "Windows"
            )
        if not self.python_executable:
            self.python_executable = default_python()
        if not self.workspace_root:
            self.workspace_root = str(root / "GetOrganelleRuns")
        if not self.threads:
            self.threads = default_threads()
        if self.theme not in ("light", "dark"):
            self.theme = "light"
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {field_name for field_name in cls.__dataclass_fields__}
        filtered = {key: value for key, value in (data or {}).items() if key in known}
        return cls(**filtered).normalize()

    @classmethod
    def load(cls) -> "Settings":
        path = settings_file()
        if path.is_file():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    return cls.from_dict(json.load(handle))
            except (OSError, ValueError):
                pass
        return cls().normalize()

    def save(self) -> None:
        path = settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temporary.replace(path)

    def add_recent_input(self, path: str, limit: int = 12) -> None:
        if not path:
            return
        resolved = str(Path(path))
        self.recent_inputs = [resolved] + [
            item for item in self.recent_inputs if Path(item) != Path(resolved)
        ]
        del self.recent_inputs[limit:]
