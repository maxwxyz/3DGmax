"""Farbschema hell/dunkel: Palette, Stylesheet, Farben der 3D-Ansicht."""

from __future__ import annotations

import os
import sys

from PySide6 import QtGui, QtWidgets

SCHRIFT = "Segoe UI" if os.name == "nt" else ("Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")

THEMEN = {
    "hell": dict(
        name="hell", fenster="#f4f5f7", flaeche="#ffffff", rand="#dfe3e8", rand2="#cbd2db",
        text="#1f2937", text2="#4b5563", leise="#6b7280", aus="#9ca3af", hover="#eef1f6",
        wahl="#dbe7fd", wahl_text="#111827", akzent="#2563eb", akzent_hover="#1d4ed8",
        eingabe="#ffffff", eingabe_text="#111827",
        # 3D-Ansicht (RGB 0..1)
        hg_oben=(0.86, 0.89, 0.93), hg_unten=(0.70, 0.74, 0.80),
        modell=(0.78, 0.80, 0.84), kante=(0.15, 0.17, 0.20), pmi=(0.05, 0.20, 0.55),
        hervor=(1.0, 0.45, 0.0), pmi_hervor=(0.85, 0.25, 0.0), schnitt=(1.0, 0.55, 0.1),
        v_geaendert=(0.96, 0.72, 0.05), v_neu=(0.15, 0.70, 0.30), v_entfernt=(0.90, 0.15, 0.15)),
    "dunkel": dict(
        name="dunkel", fenster="#1c1f24", flaeche="#262a31", rand="#353b44", rand2="#4a515c",
        text="#e5e7eb", text2="#cbd0d8", leise="#9ca3af", aus="#6b7280", hover="#323842",
        wahl="#1e3a6e", wahl_text="#f3f4f6", akzent="#3b82f6", akzent_hover="#2563eb",
        eingabe="#15171b", eingabe_text="#f3f4f6",
        hg_oben=(0.20, 0.22, 0.26), hg_unten=(0.09, 0.10, 0.12),
        modell=(0.62, 0.65, 0.70), kante=(0.08, 0.09, 0.10), pmi=(0.55, 0.80, 1.0),
        hervor=(1.0, 0.55, 0.1), pmi_hervor=(1.0, 0.65, 0.2), schnitt=(1.0, 0.6, 0.15),
        v_geaendert=(1.0, 0.80, 0.15), v_neu=(0.30, 0.85, 0.40), v_entfernt=(1.0, 0.30, 0.30)),
}
AKTUELL = dict(THEMEN["hell"])


def qss(t: dict) -> str:
    return f"""
* {{ font-family: "{SCHRIFT}", Arial; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {t['fenster']}; color: {t['text']}; }}
QToolBar {{ background: {t['flaeche']}; border: none; border-bottom: 1px solid {t['rand']}; spacing: 2px; padding: 3px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px 8px; color: {t['text']}; }}
QToolButton:hover {{ background: {t['hover']}; }}
QToolButton:checked {{ background: {t['wahl']}; color: {t['akzent']}; }}
QToolButton:disabled, QToolButton:checked:disabled {{ color: {t['aus']}; background: transparent; }}
QDockWidget {{ color: {t['text']}; }}
QDockWidget::title {{ background: {t['fenster']}; padding: 7px 10px 5px 10px; font-weight: 600; color: {t['text2']}; }}
QMainWindow::separator {{ background: {t['rand']}; width: 1px; height: 1px; }}
QMainWindow::separator:hover {{ background: {t['akzent']}; }}
QTreeWidget, QTableWidget, QListWidget, QTextBrowser {{ background: {t['flaeche']}; color: {t['text']};
    border: 1px solid {t['rand']}; border-radius: 6px; alternate-background-color: {t['fenster']}; }}
QTreeWidget::item, QListWidget::item {{ padding: 3px 4px; border-radius: 4px; }}
QTableWidget::item {{ padding: 0px 6px; }}
QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover {{ background: {t['hover']}; }}
QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
    background: {t['wahl']}; color: {t['wahl_text']}; }}
QTableCornerButton::section {{ background: {t['fenster']}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {t['rand2']}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {t['leise']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QComboBox {{ background: {t['eingabe']}; color: {t['eingabe_text']}; border: 1px solid {t['rand2']};
    border-radius: 6px; padding: 4px 8px; }}
QComboBox:hover {{ border-color: {t['akzent']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {t['flaeche']}; color: {t['text']}; border: 1px solid {t['rand']};
    selection-background-color: {t['wahl']}; selection-color: {t['wahl_text']}; outline: none; }}
QMenu {{ background: {t['flaeche']}; color: {t['text']}; border: 1px solid {t['rand']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: {t['wahl']}; color: {t['wahl_text']}; }}
QMenu::item:disabled {{ color: {t['aus']}; }}
QMenu::separator {{ height: 1px; background: {t['rand']}; margin: 4px 8px; }}
QToolTip {{ background: {t['flaeche']}; color: {t['text']}; border: 1px solid {t['rand2']}; border-radius: 6px; padding: 4px 6px; }}
QHeaderView::section {{ background: {t['fenster']}; color: {t['leise']}; border: none;
    border-bottom: 1px solid {t['rand']}; padding: 4px 6px; font-weight: 600; }}
QLineEdit {{ background: {t['eingabe']}; color: {t['eingabe_text']}; border: 1px solid {t['rand2']};
    border-radius: 6px; padding: 4px 8px; selection-background-color: {t['akzent']}; }}
QLineEdit:focus {{ border: 1px solid {t['akzent']}; }}
QPushButton {{ background: {t['flaeche']}; color: {t['text']}; border: 1px solid {t['rand2']}; border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ background: {t['hover']}; }}
QPushButton:disabled {{ color: {t['aus']}; }}
QPushButton#primaer {{ background: {t['akzent']}; border-color: {t['akzent']}; color: white; font-weight: 600; }}
QPushButton#primaer:hover {{ background: {t['akzent_hover']}; }}
QLabel {{ color: {t['text']}; }}
QLabel#leise {{ color: {t['leise']}; }}
QLabel#titel {{ font-size: 15pt; font-weight: 600; }}
QStatusBar {{ background: {t['flaeche']}; color: {t['text2']}; border-top: 1px solid {t['rand']}; }}
QProgressBar {{ border: none; background: {t['rand']}; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {t['akzent']}; border-radius: 3px; }}
QTabBar::tab {{ padding: 5px 12px; color: {t['leise']}; background: transparent; border: none; }}
QTabBar::tab:selected {{ color: {t['text']}; font-weight: 600; border-bottom: 2px solid {t['akzent']}; }}
"""


def palette(t: dict) -> QtGui.QPalette:
    p = QtGui.QPalette()
    c = QtGui.QColor
    R = QtGui.QPalette.ColorRole
    p.setColor(R.Window, c(t["fenster"]))
    p.setColor(R.WindowText, c(t["text"]))
    p.setColor(R.Base, c(t["eingabe"]))
    p.setColor(R.AlternateBase, c(t["fenster"]))
    p.setColor(R.Text, c(t["eingabe_text"]))
    p.setColor(R.Button, c(t["flaeche"]))
    p.setColor(R.ButtonText, c(t["text"]))
    p.setColor(R.Highlight, c(t["akzent"]))
    p.setColor(R.HighlightedText, c("#ffffff"))
    p.setColor(R.ToolTipBase, c(t["flaeche"]))
    p.setColor(R.ToolTipText, c(t["text"]))
    p.setColor(R.PlaceholderText, c(t["leise"]))
    p.setColor(QtGui.QPalette.ColorGroup.Disabled, R.Text, c(t["aus"]))
    p.setColor(QtGui.QPalette.ColorGroup.Disabled, R.ButtonText, c(t["aus"]))
    return p


def system_dunkel() -> bool:
    try:
        from PySide6.QtCore import Qt
        return QtGui.QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:  # noqa: BLE001
        return False


def wende_an(app: QtWidgets.QApplication, name: str) -> dict:
    """name: hell, dunkel oder auto (wie das System)."""
    if name not in THEMEN:
        name = "dunkel" if system_dunkel() else "hell"
    AKTUELL.clear()
    AKTUELL.update(THEMEN[name])
    app.setStyle("Fusion")
    app.setPalette(palette(AKTUELL))
    app.setStyleSheet(qss(AKTUELL))
    return AKTUELL
