"""Semantic design tokens and the application stylesheet.

The tokens follow the YR-MPE UI audit: 8 px spacing grid, a small type scale,
semantic colours (surface / text / primary / success / warning / error) and a
light/dark pair defined from scratch rather than by inverting one palette.
Colour never carries state alone; badges always pair it with an icon and text.
"""
from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PyQt5.QtWidgets import QApplication

SPACE = 8
RADIUS = 8
FOCUS_WIDTH = 2


@dataclass(frozen=True)
class Tokens:
    name: str
    surface: str
    surface_alt: str
    surface_sunken: str
    text: str
    text_secondary: str
    primary: str
    primary_hover: str
    primary_text: str
    primary_bg: str
    success: str
    success_bg: str
    warning: str
    warning_bg: str
    error: str
    error_bg: str
    outline: str
    outline_strong: str

    def as_dict(self) -> dict:
        return {
            "surface": self.surface,
            "surface_alt": self.surface_alt,
            "surface_sunken": self.surface_sunken,
            "text": self.text,
            "text_secondary": self.text_secondary,
            "primary": self.primary,
            "primary_hover": self.primary_hover,
            "primary_text": self.primary_text,
            "primary_bg": self.primary_bg,
            "success": self.success,
            "success_bg": self.success_bg,
            "warning": self.warning,
            "warning_bg": self.warning_bg,
            "error": self.error,
            "error_bg": self.error_bg,
            "outline": self.outline,
            "outline_strong": self.outline_strong,
            "radius": str(RADIUS),
        }


LIGHT = Tokens(
    name="light",
    surface="#F6F7F9",
    surface_alt="#FFFFFF",
    surface_sunken="#EEF1F4",
    text="#1F2328",
    text_secondary="#59636E",
    primary="#0969DA",
    primary_hover="#0550AE",
    primary_text="#FFFFFF",
    primary_bg="#DDF4FF",
    success="#1A7F37",
    success_bg="#DAFBE1",
    warning="#9A6700",
    warning_bg="#FFF8C5",
    error="#CF222E",
    error_bg="#FFEBE9",
    outline="#D0D7DE",
    outline_strong="#AFB8C1",
)

DARK = Tokens(
    name="dark",
    surface="#0D1117",
    surface_alt="#161B22",
    surface_sunken="#21262D",
    text="#E6EDF3",
    text_secondary="#9198A1",
    primary="#4493F8",
    primary_hover="#58A6FF",
    primary_text="#FFFFFF",
    primary_bg="#121D2F",
    success="#3FB950",
    success_bg="#12261E",
    warning="#D29922",
    warning_bg="#2A210F",
    error="#F85149",
    error_bg="#2D1214",
    outline="#30363D",
    outline_strong="#484F58",
)

THEMES = {"light": LIGHT, "dark": DARK}

_QSS = Template(
    """
* {
    outline: none;
}
QWidget {
    background-color: transparent;
    color: $text;
    font-family: "Segoe UI Variable Text", "Segoe UI", "Noto Sans", sans-serif;
    font-size: 12pt;
}
QMainWindow, QDialog {
    background-color: $surface;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QToolTip {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $outline_strong;
    border-radius: 4px;
    padding: 6px 8px;
}

/* ---------------------------------------------------------------- chrome */
#TopBar {
    background-color: $surface_alt;
    border-bottom: 1px solid $outline;
}
#Rail {
    background-color: $surface;
    border-right: 1px solid $outline;
}
#RailButton {
    text-align: left;
    padding: 10px 12px;
    border: 1px solid transparent;
    border-radius: $radius;
    background: transparent;
    color: $text_secondary;
    font-size: 11pt;
}
#RailButton:hover {
    background-color: $surface_alt;
    color: $text;
}
#RailButton:checked {
    background-color: $primary_bg;
    border: 1px solid $primary;
    color: $text;
}
#RailButton:focus {
    border: 2px solid $primary;
}
#Inspector {
    background-color: $surface_alt;
    border-left: 1px solid $outline;
}
#JobCenter {
    background-color: $surface_alt;
    border-top: 1px solid $outline;
}
#StatusBar {
    background-color: $surface_sunken;
    color: $text_secondary;
    font-size: 9pt;
}
#StatusBar QLabel {
    background: transparent;
    color: $text_secondary;
    font-size: 9pt;
}

/* --------------------------------------------------------------- headings */
#PageTitle {
    font-size: 18pt;
    font-weight: 500;
    color: $text;
}
#PageSubtitle {
    font-size: 11pt;
    color: $text_secondary;
}
#Card {
    background-color: $surface_alt;
    border: 1px solid $outline;
    border-radius: $radius;
}
#CardTitle {
    font-size: 14pt;
    font-weight: 500;
    color: $text;
}
#CardSubtitle {
    font-size: 10pt;
    color: $text_secondary;
}
#FieldLabel {
    color: $text;
    font-size: 10pt;
}
#Hint, #Caption {
    color: $text_secondary;
    font-size: 9pt;
}
#FieldError {
    color: $error;
    font-size: 9pt;
}
#EmptyTitle {
    font-size: 14pt;
    font-weight: 500;
    color: $text;
}
#EmptyText {
    color: $text_secondary;
    font-size: 11pt;
}
#Mono {
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 10pt;
}

/* ----------------------------------------------------------------- badges */
#Badge {
    border-radius: 10px;
    padding: 2px 9px;
    font-size: 9pt;
    font-weight: 500;
    background-color: $surface_sunken;
    color: $text_secondary;
    border: 1px solid $outline;
}
#Badge[state="success"] {
    color: $success;
    background-color: $success_bg;
    border: 1px solid $success;
}
#Badge[state="warning"] {
    color: $warning;
    background-color: $warning_bg;
    border: 1px solid $warning;
}
#Badge[state="error"] {
    color: $error;
    background-color: $error_bg;
    border: 1px solid $error;
}
#Badge[state="info"] {
    color: $primary;
    background-color: $primary_bg;
    border: 1px solid $primary;
}
#Badge[state="running"] {
    color: $primary;
    background-color: $primary_bg;
    border: 1px solid $primary;
}
#Badge[state="idle"] {
    color: $text_secondary;
    background-color: $surface_sunken;
    border: 1px solid $outline;
}

/* ---------------------------------------------------------------- buttons */
QPushButton {
    font-size: 11pt;
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $outline;
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 22px;
}
QPushButton:hover {
    border-color: $primary;
}
QPushButton:pressed {
    background-color: $surface_sunken;
}
QPushButton:focus {
    border: 2px solid $primary;
}
QPushButton:disabled {
    color: $text_secondary;
    background-color: $surface_sunken;
    border-color: $outline;
}
#PrimaryButton {
    background-color: $primary;
    color: $primary_text;
    border: 1px solid $primary;
    font-weight: 500;
    padding: 8px 20px;
    min-height: 26px;
}
#PrimaryButton:hover {
    background-color: $primary_hover;
    border-color: $primary_hover;
}
#PrimaryButton:disabled {
    background-color: $surface_sunken;
    color: $text_secondary;
    border-color: $outline;
}
#DangerButton {
    background-color: $surface_alt;
    color: $error;
    border: 1px solid $error;
}
#DangerButton:hover {
    background-color: $error_bg;
}
#DangerButton:disabled {
    color: $text_secondary;
    background-color: $surface_sunken;
    border-color: $outline;
}
#IconButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
    min-width: 28px;
    min-height: 28px;
}
#IconButton:hover {
    background-color: $surface_sunken;
    border-color: $outline;
}
#IconButton:focus {
    border: 2px solid $primary;
}
#SegmentButton {
    background-color: $surface_alt;
    border: 1px solid $outline;
    border-radius: 6px;
    padding: 8px 18px;
    color: $text_secondary;
}
#SegmentButton:checked {
    background-color: $primary_bg;
    border: 1px solid $primary;
    color: $text;
    font-weight: 500;
}
#SegmentButton:focus {
    border: 2px solid $primary;
}
#Disclosure {
    text-align: left;
    border: none;
    background: transparent;
    color: $text;
    font-weight: 500;
    padding: 2px 0;
}
#Disclosure:hover {
    color: $primary;
}
#LinkButton {
    background: transparent;
    border: none;
    color: $primary;
    padding: 2px 4px;
    text-align: left;
}
#LinkButton:hover {
    text-decoration: underline;
}

/* ----------------------------------------------------------------- inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    font-size: 11pt;
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $outline;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 22px;
    selection-background-color: $primary;
    selection-color: $primary_text;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid $primary;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: $text_secondary;
    background-color: $surface_sunken;
}
QLineEdit[invalid="true"], QComboBox[invalid="true"], QSpinBox[invalid="true"] {
    border: 2px solid $error;
}
QComboBox::drop-down {
    width: 22px;
    border: none;
}
QComboBox QAbstractItemView {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $outline;
    selection-background-color: $primary_bg;
    selection-color: $text;
    outline: none;
}
QCheckBox {
    spacing: 8px;
    color: $text;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $outline_strong;
    border-radius: 3px;
    background: $surface_alt;
}
QCheckBox::indicator:checked {
    background-color: $primary;
    border-color: $primary;
}
QCheckBox:focus {
    color: $primary;
}
QGroupBox {
    border: 1px solid $outline;
    border-radius: $radius;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: 500;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}

/* ------------------------------------------------------------------ tabs */
QTabWidget::pane {
    border: 1px solid $outline;
    border-radius: $radius;
    background: $surface_alt;
}
QTabBar::tab {
    background: transparent;
    color: $text_secondary;
    padding: 8px 14px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: $text;
    border-bottom: 2px solid $primary;
}
QTabBar::tab:hover {
    color: $text;
}

/* ----------------------------------------------------------------- tables */
QTableWidget, QTableView {
    font-size: 10pt;
    background-color: $surface_alt;
    alternate-background-color: $surface_sunken;
    color: $text;
    border: 1px solid $outline;
    border-radius: 6px;
    gridline-color: $outline;
    selection-background-color: $primary_bg;
    selection-color: $text;
}
QHeaderView::section {
    background-color: $surface_sunken;
    color: $text_secondary;
    border: none;
    border-bottom: 1px solid $outline;
    padding: 6px 8px;
    font-size: 9pt;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget:focus {
    border: 2px solid $primary;
}

/* ------------------------------------------------------------------- log */
QPlainTextEdit#LogView {
    background-color: $surface_sunken;
    color: $text;
    border: 1px solid $outline;
    border-radius: 6px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 10pt;
    selection-background-color: $primary;
    selection-color: $primary_text;
}
QPlainTextEdit#LogView:focus {
    border: 2px solid $primary;
}
QTextEdit#Preview {
    background-color: $surface_sunken;
    color: $text;
    border: 1px solid $outline;
    border-radius: 6px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 10pt;
}

/* --------------------------------------------------------------- progress */
QProgressBar {
    background-color: $surface_sunken;
    border: 1px solid $outline;
    border-radius: 4px;
    text-align: center;
    min-height: 8px;
    max-height: 8px;
    color: transparent;
}
QProgressBar::chunk {
    background-color: $primary;
    border-radius: 4px;
}

/* ------------------------------------------------------------- scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: $outline_strong;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: $text_secondary;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: $outline_strong;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0;
    background: transparent;
}

/* --------------------------------------------------------------- splitter */
QSplitter::handle {
    background: $outline;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

QMenu {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $outline;
}
QMenu::item:selected {
    background-color: $primary_bg;
}
    """
)


def stylesheet(tokens: Tokens) -> str:
    return _QSS.substitute(tokens.as_dict())


def apply_theme(app: QApplication, name: str) -> Tokens:
    tokens = THEMES.get(name, LIGHT)
    app.setStyleSheet(stylesheet(tokens))
    return tokens
