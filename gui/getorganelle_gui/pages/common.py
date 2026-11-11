"""Small helpers shared by the workflow pages."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class ScrollPage(QScrollArea):
    """A page whose body scrolls instead of squeezing controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.layout = QVBoxLayout(self.body)
        self.layout.setContentsMargins(16, 14, 16, 16)
        self.layout.setSpacing(12)
        self.setWidget(self.body)

    def add(self, widget: QWidget) -> QWidget:
        self.layout.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self.layout.addLayout(layout)

    def add_stretch(self) -> None:
        self.layout.addStretch(1)


def page_header(title: str, subtitle: str) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    subtitle_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return container


def caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Caption")
    label.setWordWrap(True)
    return label


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label
