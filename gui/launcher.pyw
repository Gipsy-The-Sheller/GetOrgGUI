"""Double-click entry point for pythonw.exe.

Kept deliberately defensive: pythonw has no console, so import errors and
uncaught exceptions are surfaced through a native message box and a log file.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _message(text: str, title: str = "GetOrganelle Workbench") -> None:
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    else:
        print(text, file=sys.stderr)


def _log_exception() -> Path:
    home = os.environ.get("APPDATA") or str(Path.home())
    log_dir = Path(home) / "GetOrganelleWorkbench"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "error.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n=== " + __import__("datetime").datetime.now().isoformat() + " ===\n")
        traceback.print_exc(file=handle)
    return path


def main() -> int:
    try:
        from PyQt5.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        _message(
            "PyQt5 is not installed for this Python.\n\n"
            "Run setup_venv.bat in the GetOrganelle folder to install the GUI "
            "dependencies, then start GetOrganelleGUI.bat again.\n\n"
            "If you are on Windows ARM64, use the x64 Python interpreter "
            "(PyQt5 has no native arm64 wheel)."
        )
        return 1
    try:
        from getorganelle_gui.app import main as run_app

        return run_app()
    except Exception:
        log_path = _log_exception()
        _message(
            "GetOrganelle Workbench could not start.\n\n"
            + traceback.format_exc(limit=4)
            + f"\n\nDetails were written to:\n{log_path}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
