"""YRTools / YR-MPE plugin entry point.

YRTools loads a ``polypyplug`` by importing ``package.module:Class``, calling
``Class(config=..., plugin_path=...).run()`` and inserting the returned QWidget
into a host tab.  The standalone launcher keeps using
:func:`getorganelle_gui.app.main`; this adapter only exists for host embedding.

The host owns the application stylesheet, so the embedded workbench applies
its design tokens to its own widget subtree instead of calling
``QApplication.setStyleSheet``.  Standalone startup still uses the global
application stylesheet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt

from .main_window import MainWindow
from .settings import Settings


class GetOrganelleEntry:
    """Construct a GetOrganelle Workbench widget for a YRTools/YR-MPE host."""

    def __init__(
        self,
        config: Optional[dict] = None,
        plugin_path: Optional[str] = None,
    ):
        self.config = config
        self.plugin_path = plugin_path or str(Path(__file__).resolve().parents[1])

    def run(self, import_from=None, import_data=None, workdir=None, **kwargs):
        settings = Settings.load()
        if workdir:
            settings.workspace_root = str(Path(workdir))
        window = MainWindow(settings, apply_global_theme=False)
        # The host reparents the widget into a tab.  Mark it as a child widget
        # up front so a QMainWindow does not retain top-level window flags.
        window.setWindowFlag(Qt.Widget, True)
        window.import_from = import_from
        window.import_data = import_data
        return window.run()
