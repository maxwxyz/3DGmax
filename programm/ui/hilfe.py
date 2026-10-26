"""Hilfe: Anleitung (F1) mit automatischer Menuereferenz, Einfuehrung, Was ist neu, Ueber."""

from __future__ import annotations

import html
import os
import platform

from PySide6 import QtCore, QtGui, QtWidgets

from .. import i18n
from ..i18n import tr
from ..version import VERSION, aenderungen_html

MARKE = "<!--MENUEBEFEHLE-->"
AUTOR = "Max Wilfinger"
COPYRIGHT_JAHRE = "2026"

LIZENZEN = (
    ("Open CASCADE Technology 8.0", "LGPL 2.1 mit Ausnahme", "https://dev.opencascade.org"),
    ("pythonocc-core 8.0", "LGPL 3", "https://github.com/tpaviot/pythonocc-core"),
    ("Qt 6 / PySide6", "LGPL 3", "https://www.qt.io"),
    ("Python", "PSF", "https://www.python.org"),
    ("NumPy", "BSD", "https://numpy.org"),
    ("SciPy", "BSD", "https://scipy.org"),
    ("lxml", "BSD", "https://lxml.de"),
    ("pypdf", "BSD", "https://github.com/py-pdf/pypdf"),
)


def _text(a: QtGui.QAction) -> str:
    return a.text().replace("&", "")


def menue_befehle(fenster: QtWidgets.QMainWindow) -> list[tuple[str, str, str, str]]:
    """(Menuepfad, Befehl, Tastenkuerzel, Beschreibung) fuer alle Menueeintraege."""
    out = []

    def lauf(menue: QtWidgets.QMenu, pfad: str):
        for a in menue.actions():
            if a.isSeparator():
                continue
            if a.menu() is not None:
                lauf(a.menu(), f"{pfad} › {_text(a)}")
                continue
            kurz = a.shortcut().toString(QtGui.QKeySequence.SequenceFormat.NativeText)
            out.append((pfad, _text(a), kurz, a.statusTip() or a.toolTip().replace(_text(a), "")))

    for a in fenster.menuBar().actions():
        if a.menu() is not None:
            lauf(a.menu(), _text(a))
    return out


def menue_html(fenster) -> str:
    zeilen = [f"<h2 id='menue'>{html.escape(tr('Alle Menübefehle'))}</h2>",
              f"<table><tr><th>{tr('Menü')}</th><th>{tr('Befehl')}</th><th>{tr('Taste')}</th>"
              f"<th>{tr('Beschreibung')}</th></tr>"]
    for pfad, befehl, kurz, text in menue_befehle(fenster):
        zeilen.append(f"<tr><td>{html.escape(pfad)}</td><td>{html.escape(befehl)}</td>"
                      f"<td>{html.escape(kurz)}</td><td>{html.escape(text)}</td></tr>")
    zeilen.append("</table>")
    return "\n".join(zeilen)


def anleitung_html(fenster) -> str:
    pfad = os.path.join(i18n.HIER, i18n.anleitung())
    try:
        with open(pfad, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = f"<p>{tr('Anleitung nicht gefunden')}: {html.escape(pfad)}</p>{MARKE}"
    return text.replace(MARKE, menue_html(fenster))


class HilfeFenster(QtWidgets.QDialog):
    _offen = None

    def __init__(self, fenster):
        super().__init__(fenster)
        self.setWindowTitle(tr("Anleitung"))
        self.resize(900, 760)
        lay = QtWidgets.QVBoxLayout(self)
        self.browser = QtWidgets.QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(anleitung_html(fenster))
        lay.addWidget(self.browser)

    @classmethod
    def zeige(cls, fenster):
        if cls._offen is None or cls._offen.parent() is not fenster:
            cls._offen = cls(fenster)
        cls._offen.show()
        cls._offen.raise_()
        return cls._offen


SCHRITTE = (
    ("1 · Modell öffnen",
     "Öffnen Sie eine STEP-Datei (AP242 mit PMI) über „Datei › Öffnen“ oder ziehen Sie sie ins Fenster. "
     "Links sehen Sie die Struktur, rechts die PMI-Liste."),
    ("2 · Bewegen",
     "Wie in CATIA: Mitteltaste ziehen verschiebt, Mitteltaste halten und links oder rechts zusätzlich halten "
     "dreht, Mitteltaste halten und links/rechts einmal klicken, dann ziehen zoomt. Mausrad zoomt ebenfalls. "
     "Trackpad: zwei Finger verschieben, aufziehen zoomt, mit Wahltaste/Alt drehen. "
     "F passt alles ein, Tasten 1–7 wählen Standardansichten. Andere Steuerung: Datei › Einstellungen."),
    ("3 · PMI prüfen",
     "Klick auf eine PMI in der Liste hebt die zugehörigen Flächen orange hervor. Klick auf eine Fläche zeigt "
     "ihre PMI. „Gespeicherte Ansichten“ zeigen die Ansichten aus dem Modell mit ihren PMI. F1 öffnet die Anleitung."),
)


class Einfuehrung(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Einführung"))
        self.setMinimumWidth(520)
        lay = QtWidgets.QVBoxLayout(self)
        self.titel = QtWidgets.QLabel()
        self.titel.setObjectName("titel")
        self.text = QtWidgets.QLabel()
        self.text.setWordWrap(True)
        self.text.setMinimumHeight(110)
        lay.addWidget(self.titel)
        lay.addWidget(self.text, 1)
        knoepfe = QtWidgets.QHBoxLayout()
        self.zurueck = QtWidgets.QPushButton(tr("Zurück"))
        self.weiter = QtWidgets.QPushButton(tr("Weiter"))
        self.weiter.setObjectName("primaer")
        self.zurueck.clicked.connect(lambda: self._gehe(self.seite - 1))
        self.weiter.clicked.connect(self._weiter)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.zurueck)
        knoepfe.addWidget(self.weiter)
        lay.addLayout(knoepfe)
        self.seite = 0
        self._gehe(0)

    def _gehe(self, i):
        self.seite = max(0, min(i, len(SCHRITTE) - 1))
        t, x = SCHRITTE[self.seite]
        self.titel.setText(tr(t))
        self.text.setText(tr(x))
        self.zurueck.setEnabled(self.seite > 0)
        self.weiter.setText(tr("Fertig") if self.seite == len(SCHRITTE) - 1 else tr("Weiter"))

    def _weiter(self):
        if self.seite == len(SCHRITTE) - 1:
            self.accept()
        else:
            self._gehe(self.seite + 1)


def _html_fenster(parent, titel, inhalt):
    d = QtWidgets.QDialog(parent)
    d.setWindowTitle(titel)
    d.resize(640, 520)
    lay = QtWidgets.QVBoxLayout(d)
    b = QtWidgets.QTextBrowser()
    b.setOpenExternalLinks(True)
    b.setHtml(inhalt)
    lay.addWidget(b)
    ok = QtWidgets.QPushButton(tr("Schließen"))
    ok.clicked.connect(d.accept)
    lay.addWidget(ok, 0, QtCore.Qt.AlignmentFlag.AlignRight)
    d.show()
    return d


def zeige_neu(parent):
    return _html_fenster(parent, tr("Was ist neu"), aenderungen_html(i18n.SPRACHE))


def ueber_html() -> str:
    zeilen = "".join(f"<tr><td>{html.escape(n)}</td><td>{html.escape(l)}</td>"
                     f"<td><a href='{u}'>{html.escape(u)}</a></td></tr>" for n, l, u in LIZENZEN)
    return (f"<h2>3DGmax {VERSION}</h2><p>{tr('3D-Modelle mit PMI ansehen, messen und vergleichen.')}</p>"
            f"<p>© {COPYRIGHT_JAHRE} {AUTOR}</p>"
            f"<p>{tr('Lizenz')}: <a href='https://www.gnu.org/licenses/gpl-3.0.html'>GNU GPL v3 {tr('oder später')}</a>"
            f" (GPL-3.0-or-later). {tr('Ohne Gewährleistung.')}</p>"
            f"<p>Python {platform.python_version()} · {platform.system()} {platform.machine()}</p>"
            f"<h3>{tr('Verwendete Bibliotheken und Lizenzen')}</h3><table>{zeilen}</table>"
            f"<p>{tr('Testmodelle: NIST MBE PMI Validation and Conformance Testing (gemeinfrei).')}</p>")


def zeige_ueber(parent):
    return _html_fenster(parent, tr("Über 3DGmax"), ueber_html())
