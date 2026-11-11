"""Reusable widgets implementing the YR-MPE UI constraints."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .theme import Tokens

BADGE_SYMBOLS = {
    "success": "✓",
    "warning": "⚠",
    "error": "✕",
    "info": "●",
    "running": "▶",
    "idle": "○",
}


class Card(QFrame):
    """A surface container with an optional heading and subtitle."""

    def __init__(self, title: str = "", subtitle: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        self.title_label: Optional[QLabel] = None
        self.subtitle_label: Optional[QLabel] = None
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("CardTitle")
            outer.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("CardSubtitle")
            self.subtitle_label.setWordWrap(True)
            outer.addWidget(self.subtitle_label)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        outer.addLayout(self.body)
        outer.addStretch(1)


class Badge(QLabel):
    """State chip: symbol + text + colour (never colour alone)."""

    def __init__(self, text: str = "", state: str = "idle", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Badge")
        self.setProperty("state", state)
        self.set_state(state, text)

    def set_state(self, state: str, text: str) -> None:
        symbol = BADGE_SYMBOLS.get(state, "○")
        self.setText(f"{symbol} {text}" if text else symbol)
        self.setProperty("state", state)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()


class FileInput(QWidget):
    """Path field with Browse, drag-and-drop and inline error text."""

    path_changed = pyqtSignal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        mode: str = "open",
        filters: str = "All files (*.*)",
        placeholder: str = "",
    ):
        super().__init__(parent)
        self._mode = mode
        self._filters = filters
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self._on_text_changed)
        self.button = QPushButton("Browse…")
        self.button.clicked.connect(self._browse)
        row.addWidget(self.edit, 1)
        row.addWidget(self.button)
        layout.addLayout(row)
        self.error_label = QLabel("")
        self.error_label.setObjectName("FieldError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.setAcceptDrops(True)

    def _on_text_changed(self, text: str) -> None:
        self.set_invalid(False)
        self.path_changed.emit(text)

    def _browse(self) -> None:
        if self._mode == "directory":
            path = QFileDialog.getExistingDirectory(self, "Select folder", self.text())
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file", self.text(), self._filters)
        if path:
            self.setText(path)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str) -> None:
        self.edit.setText(value or "")

    def clear(self) -> None:
        self.edit.clear()

    def set_invalid(self, invalid: bool, message: str = "") -> None:
        self.edit.setProperty("invalid", "true" if invalid else "false")
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)
        if invalid and message:
            self.error_label.setText(message)
            self.error_label.show()
        else:
            self.error_label.hide()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local:
                self.setText(local)
                break
        event.acceptProposedAction()


class CollapsibleSection(QWidget):
    """Progressive disclosure: advanced options stay hidden until opened."""

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.header = QToolButton()
        self.header.setObjectName("Disclosure")
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.header.setText(f"▸  {title}")
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.toggled.connect(self._on_toggled)
        layout.addWidget(self.header)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.content.hide()
        layout.addWidget(self.content)
        self._title = title

    def _on_toggled(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.header.setText(("▾  " if checked else "▸  ") + self._title)
        self.toggled.emit(checked)

    def setExpanded(self, expanded: bool) -> None:
        self.header.setChecked(expanded)

    def isExpanded(self) -> bool:
        return self.header.isChecked()


class EmptyState(QWidget):
    """Empty block with an explicit next step."""

    def __init__(
        self,
        title: str,
        text: str,
        icon: str = "◇",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)
        icon_label = QLabel(icon)
        icon_font = QFont()
        icon_font.setPointSize(30)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(icon_label)
        title_label = QLabel(title)
        title_label.setObjectName("EmptyTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        text_label = QLabel(text)
        text_label.setObjectName("EmptyText")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)
        self.actions = QHBoxLayout()
        self.actions.setAlignment(Qt.AlignCenter)
        layout.addLayout(self.actions)

    def add_action(self, button: QPushButton) -> QPushButton:
        self.actions.addWidget(button)
        return button


class Separator(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Plain)
        self.setStyleSheet("color: palette(mid);")


class LogView(QPlainTextEdit):
    """Read-only console with semantic colours and bounded memory."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("LogView")
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setMaximumBlockCount(20000)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tokens: Optional[Tokens] = None
        self.auto_scroll = True
        self._formats = {}

    def set_tokens(self, tokens: Tokens) -> None:
        self._tokens = tokens
        self._formats = {
            "error": self._format(tokens.error),
            "warning": self._format(tokens.warning),
            "command": self._format(tokens.primary),
            "stage": self._format(tokens.success),
            "info": self._format(tokens.text_secondary),
            "output": self._format(tokens.text),
        }

    @staticmethod
    def _format(color: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        return fmt

    def append_line(self, text: str, kind: str = "output") -> None:
        scrollbar = self.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if self.document().characterCount() > 1:
            cursor.insertText("\n")
        fmt = self._formats.get(kind, self._formats.get("output", QTextCharFormat()))
        cursor.insertText(text, fmt)
        if self.auto_scroll and (at_bottom or kind in ("error", "command")):
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


def make_icon_button(text: str, tooltip: str, accessible_name: str = "") -> QToolButton:
    button = QToolButton()
    button.setObjectName("IconButton")
    button.setText(text)
    button.setToolTip(tooltip)
    button.setAccessibleName(accessible_name or tooltip)
    font = QFont()
    font.setPointSize(12)
    button.setFont(font)
    button.setCursor(Qt.PointingHandCursor)
    return button


def set_widget_invalid(widget: QWidget, invalid: bool) -> None:
    widget.setProperty("invalid", "true" if invalid else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def path_name(path: str, limit: int = 52) -> str:
    if not path:
        return ""
    name = Path(path).name or path
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size} B"


def human_bp(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} Mb"
    if value >= 1_000:
        return f"{value / 1_000:.1f} kb"
    return f"{value} bp"


def text_labels(pairs: Iterable[tuple]) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for label, value in pairs:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        left = QLabel(label)
        left.setObjectName("Caption")
        right = QLabel(value)
        right.setWordWrap(True)
        right.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(left)
        row.addStretch(1)
        row.addWidget(right)
        layout.addLayout(row)
    return container
