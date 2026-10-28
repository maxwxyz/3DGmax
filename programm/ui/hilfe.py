"""Hilfe: Anleitung (F1) mit automatischer Menuereferenz, Ueber."""

from __future__ import annotations

import html
import os
import platform

from PySide6 import QtCore, QtGui, QtWidgets

from .. import i18n
from ..i18n import tr
from ..version import VERSION

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
    ("Asymptote PRC (Kodierungstabelle, Bitleser)", "LGPL 3", "https://github.com/vectorgraphics/asymptote"),
    ("isofits (ISO-286-Werte j/J, a), © Parker Greene", "MIT", "https://github.com/parkergreene/isofits"),
    ("TKJT (nur Programmvariante mit JT), © OPEN CASCADE SAS", "GPL 2 oder später", "https://github.com/mmaenz/TKJT"),
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


def anleitung_datei(fenster) -> str:
    """Anleitung mit Menuereferenz als Datei im Temp-Ordner (Bilder ueber <base> aus dem Programmordner)."""
    import tempfile
    ordner = os.path.join(tempfile.gettempdir(), "3DGmax-Anleitung")
    os.makedirs(ordner, exist_ok=True)
    basis = QtCore.QUrl.fromLocalFile(i18n.HIER + os.sep).toString()
    text = anleitung_html(fenster).replace("<head>", f'<head>\n<base href="{basis}">', 1)
    pfad = os.path.join(ordner, i18n.anleitung())
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(text)
    return pfad


def zeige_anleitung(fenster):
    """Im Browser (Seitenleiste, Bilder zum Vergroessern); ohne Browser im eigenen Fenster."""
    try:
        if QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(anleitung_datei(fenster))):
            return None
    except OSError:
        pass
    return HilfeFenster.zeige(fenster)


class HilfeFenster(QtWidgets.QDialog):
    _offen = None

    def __init__(self, fenster):
        super().__init__(fenster)
        self.setWindowTitle(tr("Anleitung"))
        self.resize(900, 760)
        lay = QtWidgets.QVBoxLayout(self)
        self.browser = QtWidgets.QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setSearchPaths([i18n.HIER])  # Bilder doc_img/...
        self.browser.setHtml(anleitung_html(fenster))
        lay.addWidget(self.browser)

    @classmethod
    def zeige(cls, fenster):
        if cls._offen is None or cls._offen.parent() is not fenster:
            cls._offen = cls(fenster)
        cls._offen.show()
        cls._offen.raise_()
        return cls._offen


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
