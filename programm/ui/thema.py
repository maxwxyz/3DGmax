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
        # PMI: aus der Datei (blau), erzeugt (violett), Vorschau (petrol), hervorgehoben (rost); Kontrast >= 4,5:1
        pmi_erzeugt=(0.38, 0.14, 0.58), pmi_vorschau=(0.0, 0.31, 0.28),
        hervor=(1.0, 0.45, 0.0), pmi_hervor=(0.54, 0.12, 0.0), schnitt=(1.0, 0.55, 0.1),
        v_geaendert=(0.96, 0.72, 0.05), v_neu=(0.15, 0.70, 0.30), v_entfernt=(0.90, 0.15, 0.15)),
    "dunkel": dict(
        name="dunkel", fenster="#1c1f24", flaeche="#262a31", rand="#353b44", rand2="#4a515c",
        text="#e5e7eb", text2="#cbd0d8", leise="#9ca3af", aus="#6b7280", hover="#323842",
        wahl="#1e3a6e", wahl_text="#f3f4f6", akzent="#3b82f6", akzent_hover="#2563eb",
        eingabe="#15171b", eingabe_text="#f3f4f6",
        # OCCT zeigt den Verlauf gammakorrigiert (0,045 -> #3c3f46): wirklich dunkel wie das Fenster
        hg_oben=(0.045, 0.05, 0.062), hg_unten=(0.012, 0.013, 0.016),
        modell=(0.62, 0.65, 0.70), kante=(0.08, 0.09, 0.10), pmi=(0.55, 0.80, 1.0),
        pmi_erzeugt=(0.84, 0.62, 1.0), pmi_vorschau=(0.30, 0.85, 0.75),
        hervor=(1.0, 0.55, 0.1), pmi_hervor=(1.0, 0.65, 0.2), schnitt=(1.0, 0.6, 0.15),
        v_geaendert=(1.0, 0.80, 0.15), v_neu=(0.30, 0.85, 0.40), v_entfernt=(1.0, 0.30, 0.30)),
}
AKTUELL = dict(THEMEN["hell"])
MIN_KONTRAST = 4.5  # wie WCAG AA fuer normalen Text


def leuchtdichte(rgb) -> float:
    """Relative Leuchtdichte nach WCAG 2 (RGB 0..1)."""
    def linear(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(float(c)) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(a, b) -> float:
    """Kontrastverhaeltnis 1..21 zweier Farben nach WCAG 2."""
    la, lb = sorted((leuchtdichte(a), leuchtdichte(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def kleinster_kontrast(farbe, hintergruende) -> float:
    return min(kontrast(farbe, h) for h in hintergruende)


def lesbar(farbe, hintergruende, ziel: float = MIN_KONTRAST) -> tuple:
    """Farbe so weit zu Schwarz bzw. Weiss hin mischen, bis sie auf allen Hintergrundfarben (z. B. Verlauf oben
    und unten) den Mindestkontrast hat; der Farbton bleibt so weit wie moeglich erhalten."""
    farbe = tuple(float(c) for c in farbe[:3])
    if kleinster_kontrast(farbe, hintergruende) >= ziel:
        return farbe
    ende = (0.0, 0.0, 0.0) if kleinster_kontrast((0, 0, 0), hintergruende) >= \
        kleinster_kontrast((1, 1, 1), hintergruende) else (1.0, 1.0, 1.0)
    for i in range(1, 21):
        t = i / 20
        neu = tuple(c + (e - c) * t for c, e in zip(farbe, ende))
        if kleinster_kontrast(neu, hintergruende) >= ziel:
            return neu
    return ende


def schrift_auf(farbe) -> tuple:
    """Schwarz oder Weiss, je nachdem was auf der Flaechenfarbe besser lesbar ist (Text in Farbfeldern)."""
    return (1.0, 1.0, 1.0) if kontrast((1, 1, 1), farbe) >= kontrast((0, 0, 0), farbe) else (0.0, 0.0, 0.0)


def srgb(rgb) -> tuple:
    """Lineares RGB als sRGB (so zeigt OCCT den Hintergrundverlauf; Linien und Texte erscheinen unveraendert)."""
    return tuple(12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in rgb[:3])


def hintergrund_3d(t: dict, eigen=None) -> tuple:
    """Hintergrundfarben der 3D-Ansicht (oben, unten; eigene oder die des Farbschemas), jeweils wie angegeben und
    gammakorrigiert: je nach Grafiktreiber erscheint der Verlauf so oder so, lesbar soll es in beiden Faellen sein."""
    oben, unten = tuple(eigen) if eigen else (t.get("hg_oben", (1, 1, 1)), t.get("hg_unten", (1, 1, 1)))
    return tuple(oben), tuple(unten), srgb(oben), srgb(unten)


def rgb_hex(farbe: str) -> tuple:
    """#rrggbb als RGB 0..1."""
    farbe = farbe.lstrip("#")
    return tuple(int(farbe[i:i + 2], 16) / 255 for i in (0, 2, 4))


def schliessen_symbol(farbe: str, name: str) -> str:
    """Schlankes X als SVG (fuer Reiter und Leisten); Qt-Stylesheets brauchen dafuer eine Datei. Pfad mit /."""
    import tempfile
    ordner = os.path.join(tempfile.gettempdir(), "3DGmax-symbole")
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, f"schliessen_{name}.svg")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
           f'<path d="M4 4 L12 12 M12 4 L4 12" stroke="{farbe}" stroke-width="1.6" stroke-linecap="round"/></svg>')
    try:
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(svg)
    except OSError:
        return ""
    return pfad.replace(os.sep, "/")


def pfeil_symbol(farbe: str, name: str, hoch: bool = False) -> str:
    """Pfeil nach unten (bzw. oben) als SVG fuer Auswahllisten und Zahlenfelder (mit eigenem Rahmen zeichnet Qt
    keinen Standardpfeil)."""
    import tempfile
    ordner = os.path.join(tempfile.gettempdir(), "3DGmax-symbole")
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, f"pfeil_{name}{'_hoch' if hoch else ''}.svg")
    weg = "M2.5 7.5 L6 4 L9.5 7.5" if hoch else "M2.5 4.5 L6 8 L9.5 4.5"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
           f'<path d="{weg}" fill="none" stroke="{farbe}" stroke-width="1.6" stroke-linecap="round" '
           f'stroke-linejoin="round"/></svg>')
    try:
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(svg)
    except OSError:
        return ""
    return pfad.replace(os.sep, "/")


def inhalt_hoehe() -> int:
    """Hoehe des Inhalts aller Bedienelemente (Text oder 16-px-Symbol) aus der Schrift; mit Innenabstand 4 px und
    Rahmen 1 px ergibt das eine gemeinsame Hoehe fuer Knoepfe, Auswahllisten, Zahlen- und Eingabefelder. In
    logischen Pixeln, folgt also auch der Groesse der Oberflaeche (QT_SCALE_FACTOR)."""
    schrift = QtGui.QFont(SCHRIFT)
    schrift.setPointSizeF(10)
    return max(QtGui.QFontMetrics(schrift).height(), 16)


SYMBOLE = {"abspielen": '<path d="M5 3.5 L12.5 8 L5 12.5 Z" fill="{f}"/>',
           "anhalten": '<path d="M4.5 3.5 h2.5 v9 h-2.5 Z M9 3.5 h2.5 v9 h-2.5 Z" fill="{f}"/>'}


def symbol(name: str) -> QtGui.QIcon:
    """Kleines Symbol (16 px, SVG) in der Textfarbe des Themas - Qts Standardsymbole sind im Dunklen schwarz."""
    from PySide6 import QtCore
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">' +
           SYMBOLE[name].replace("{f}", AKTUELL["text"]) + "</svg>").encode()
    bild = QtGui.QPixmap()
    bild.loadFromData(QtCore.QByteArray(svg), "SVG")
    return QtGui.QIcon(bild)


def schliessen_groesse() -> int:
    """Kantenlaenge der X zum Schliessen (Reiter, Leistentitel): etwas groesser als die Schrift, damit man es so
    leicht trifft wie den Reiter selbst; folgt der Groesse der Oberflaeche."""
    return inhalt_hoehe() + 6


def bedien_hoehe() -> int:
    """Gemeinsame Hoehe der Bedienelemente (Inhalt + 2 x 4 px Innenabstand + 2 x 1 px Rahmen)."""
    return inhalt_hoehe() + 10


def nur_symbol(knopf: QtWidgets.QAbstractButton) -> QtWidgets.QAbstractButton:
    """Knopf nur mit Symbol: quadratisch in der gemeinsamen Hoehe (Stylesheet-Eigenschaft symbol)."""
    knopf.setProperty("symbol", True)
    knopf.style().unpolish(knopf)
    knopf.style().polish(knopf)
    return knopf


def qss(t: dict) -> str:
    x = schliessen_symbol(t["leise"], t["name"])
    x_hover = schliessen_symbol(t["text"], t["name"] + "_hover")
    pfeil = pfeil_symbol(t["text2"] if "text2" in t else t["text"], t["name"])
    pfeil_aus = pfeil_symbol(t["aus"], t["name"] + "_aus")
    hoch = pfeil_symbol(t["text2"] if "text2" in t else t["text"], t["name"], hoch=True)
    hoch_aus = pfeil_symbol(t["aus"], t["name"] + "_aus", hoch=True)
    h = inhalt_hoehe()
    return f"""
* {{ font-family: "{SCHRIFT}", Arial; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {t['fenster']}; color: {t['text']}; }}
QToolBar {{ background: {t['flaeche']}; border: none; border-bottom: 1px solid {t['rand']}; spacing: 2px; padding: 3px 6px; }}
QPushButton, QToolButton, QComboBox, QAbstractSpinBox, QLineEdit {{ min-height: {h}px; max-height: {h}px; }}
QCheckBox, QRadioButton {{ min-height: {h + 10}px; }}
QToolButton {{ background: {t['flaeche']}; border: 1px solid {t['rand2']}; border-radius: 6px; padding: 4px 12px;
    color: {t['text']}; }}
QToolButton:hover {{ background: {t['hover']}; }}
QToolButton:checked {{ background: {t['wahl']}; color: {t['akzent']}; border: 1px solid {t['akzent']}; font-weight: 600; }}
QToolButton:disabled, QToolButton:checked:disabled {{ color: {t['aus']}; background: transparent; }}
QToolButton[popupMode="2"] {{ padding-right: 24px; }}
QToolButton::menu-indicator {{ image: url({pfeil}); subcontrol-origin: padding; subcontrol-position: center right;
    width: 12px; height: 12px; right: 6px; }}
QToolButton::menu-indicator:disabled {{ image: url({pfeil_aus}); }}
QToolButton[popupMode="1"] {{ padding-right: 26px; }}
QToolButton::menu-button {{ border: none; border-left: 1px solid {t['rand2']}; width: 20px; }}
QToolBar QToolButton::menu-button {{ border-left: 1px solid {t['rand']}; }}
QToolButton::menu-arrow {{ image: url({pfeil}); width: 12px; height: 12px; }}
QToolButton::menu-arrow:disabled {{ image: url({pfeil_aus}); }}
QToolBar QToolButton {{ background: transparent; border: 1px solid transparent; padding: 4px 8px; }}
QToolBar QToolButton:hover {{ background: {t['hover']}; }}
QToolBar QToolButton:checked {{ background: {t['wahl']}; border: 1px solid transparent; font-weight: normal; }}
QTabBar QToolButton {{ background: transparent; border: none; padding: 2px; min-height: 0px; max-height: 9999px; }}
QDockWidget {{ color: {t['text']}; }}
QDockWidget::title {{ background: {t['fenster']}; padding: 7px 10px 5px 10px; font-weight: 600; color: {t['text2']}; }}
QMainWindow::separator {{ background: {t['rand']}; width: 5px; height: 5px; }}
QMainWindow::separator:hover {{ background: {t['akzent']}; }}
QTreeWidget, QTableWidget, QTableView#festeSpalte, QListWidget, QTextBrowser {{ background: {t['flaeche']}; color: {t['text']};
    border: 1px solid {t['rand']}; border-radius: 6px; alternate-background-color: {t['fenster']}; }}
QTreeWidget::item, QListWidget::item {{ padding: 3px 4px; border-radius: 4px; }}
QTableView#festeSpalte {{ border: none; border-right: 1px solid {t['rand']}; border-radius: 0px; }}
QTableWidget::item, QTableView#festeSpalte::item {{ padding: 0px 6px; }}
QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover, QTableView#festeSpalte::item:hover {{ background: {t['hover']}; }}
QTreeWidget::item:selected, QTableWidget::item:selected, QTableView#festeSpalte::item:selected,
QListWidget::item:selected {{
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
QComboBox {{ padding-right: 24px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 22px;
    border: none; border-left: 1px solid {t['rand2']}; }}
QComboBox::down-arrow {{ image: url({pfeil}); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url({pfeil_aus}); }}
QAbstractSpinBox {{ background: {t['eingabe']}; color: {t['eingabe_text']}; border: 1px solid {t['rand2']};
    border-radius: 6px; padding: 4px 24px 4px 8px; selection-background-color: {t['akzent']}; }}
QAbstractSpinBox:hover, QAbstractSpinBox:focus {{ border-color: {t['akzent']}; }}
QAbstractSpinBox:disabled {{ color: {t['aus']}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ subcontrol-origin: border; width: 20px; border: none;
    border-left: 1px solid {t['rand2']}; }}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {t['hover']}; }}
QAbstractSpinBox::up-arrow {{ image: url({hoch}); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url({pfeil}); width: 10px; height: 10px; }}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {{ image: url({hoch_aus}); }}
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {{ image: url({pfeil_aus}); }}
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
QComboBox QLineEdit, QAbstractSpinBox QLineEdit {{ background: transparent; border: none; border-radius: 0px;
    padding: 0px; min-height: 0px; max-height: 9999px; }}
QPushButton {{ background: {t['flaeche']}; color: {t['text']}; border: 1px solid {t['rand2']}; border-radius: 6px; padding: 4px 12px; }}
QPushButton:hover {{ background: {t['hover']}; }}
QPushButton:disabled {{ color: {t['aus']}; }}
QPushButton:checked {{ background: {t['wahl']}; color: {t['akzent']}; border: 1px solid {t['akzent']}; font-weight: 600; }}
QPushButton#primaer {{ background: {t['akzent']}; border-color: {t['akzent']}; color: white; font-weight: 600; }}
QPushButton#primaer:hover {{ background: {t['akzent_hover']}; }}
QPushButton::menu-indicator {{ image: url({pfeil}); subcontrol-origin: padding; subcontrol-position: center right;
    width: 12px; height: 12px; }}
QPushButton::menu-indicator:disabled {{ image: url({pfeil_aus}); }}
QPushButton[symbol="true"], QToolButton[symbol="true"] {{ padding: 4px; min-width: {h}px; max-width: {h}px; }}
QLabel {{ color: {t['text']}; }}
QLabel#leise {{ color: {t['leise']}; }}
QLabel#titel {{ font-size: 15pt; font-weight: 600; }}
QStatusBar {{ background: {t['flaeche']}; color: {t['text2']}; border-top: 1px solid {t['rand']}; }}
QProgressBar {{ border: none; background: {t['rand']}; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {t['akzent']}; border-radius: 3px; }}
QTabBar::tab {{ padding: 5px 12px; color: {t['leise']}; background: transparent; border: none; }}
QTabBar::tab:selected {{ color: {t['text']}; font-weight: 600; border-bottom: 2px solid {t['akzent']}; }}
QTabBar::close-button {{ image: url("{x}"); subcontrol-position: right; margin-left: 4px; border-radius: 5px; }}
QTabBar::close-button:hover {{ image: url("{x_hover}"); background: {t['rand']}; }}
QDockWidget {{ titlebar-close-icon: url("{x}"); }}
QDockWidget::close-button {{ border: none; border-radius: 5px; background: transparent; }}
QDockWidget::close-button:hover {{ background: {t['rand']}; }}
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


class _Stil(QtWidgets.QProxyStyle):
    """Fusion mit Beschriftungen in Formularen mittig zur Zeile: Qt setzt sie oben in eine Zeile von hoechstens 7/4
    Schrifthoehe, neben den gemeinsam hohen Feldern sassen sie dadurch hoeher als deren Text. Dazu gut treffbare X
    zum Schliessen der Reiter."""

    def pixelMetric(self, mass, option=None, widget=None):  # noqa: N802 - Qt
        # Groesse der X in Reitern: das Stylesheet (width/height) wirkt dort nicht, Qt fragt nur den Stil
        if mass in (QtWidgets.QStyle.PixelMetric.PM_TabCloseIndicatorWidth,
                    QtWidgets.QStyle.PixelMetric.PM_TabCloseIndicatorHeight):
            return schliessen_groesse()
        if mass == QtWidgets.QStyle.PixelMetric.PM_DockWidgetTitleBarButtonMargin:  # um das 16-px-Symbol
            return max(1, (schliessen_groesse() - 16) // 2)
        return super().pixelMetric(mass, option, widget)

    def styleHint(self, hinweis, option=None, widget=None, rueckgabe=None):  # noqa: N802 - Qt
        if hinweis == QtWidgets.QStyle.StyleHint.SH_DockWidget_ButtonsHaveFrame:
            return 0  # sonst begrenzt Qt das X im Leistentitel auf 10 px (auf dem Mac 7 px); Rahmen kommt aus dem QSS
        if hinweis == QtWidgets.QStyle.StyleHint.SH_FormLayoutLabelAlignment:
            from PySide6 import QtCore
            return int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        return super().styleHint(hinweis, option, widget, rueckgabe)

    def polish(self, w):  # noqa: D102 - Qt
        super().polish(w)
        if isinstance(w, QtWidgets.QLabel) and _formular_beschriftung(w):
            w.setMinimumHeight(bedien_hoehe())


def _formular_beschriftung(label: QtWidgets.QLabel) -> bool:
    eltern = label.parentWidget()
    if eltern is None:
        return False
    rolle = QtWidgets.QFormLayout.ItemRole.LabelRole
    return any(f.getWidgetPosition(label)[1] == rolle for f in eltern.findChildren(QtWidgets.QFormLayout))


def wende_an(app: QtWidgets.QApplication, name: str) -> dict:
    """name: hell, dunkel oder auto (wie das System)."""
    if name not in THEMEN:
        name = "dunkel" if system_dunkel() else "hell"
    AKTUELL.clear()
    AKTUELL.update(THEMEN[name])
    app.setStyle(_Stil("Fusion"))
    app.setPalette(palette(AKTUELL))
    app.setStyleSheet(qss(AKTUELL))
    return AKTUELL
