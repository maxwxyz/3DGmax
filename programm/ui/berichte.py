"""PDF-Berichte: eine Seite je gespeicherter Ansicht, Vergleichsbericht, PMI-Aenderungstabelle.

Gezeichnet mit QPdfWriter/QPainter (laeuft auch ohne Bildschirm; dann ohne 3D-Bild).
"""

from __future__ import annotations

import datetime
import os

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..version import VERSION

RAND = 36  # Punkte


class PdfBericht:
    """Seitenaufbau mit Kopf, Fuss (Seitenzahl), Bildern und Tabellen mit Seitenumbruch."""

    def __init__(self, pfad: str, titel: str, quer: bool = True):
        self.pfad = pfad
        self.titel = titel
        self.schreiber = QtGui.QPdfWriter(pfad)
        self.schreiber.setTitle(titel)
        self.schreiber.setCreator(f"3DGmax {VERSION}")
        self.schreiber.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
        self.schreiber.setPageOrientation(QtGui.QPageLayout.Orientation.Landscape if quer
                                          else QtGui.QPageLayout.Orientation.Portrait)
        self.schreiber.setResolution(144)
        self.maler = QtGui.QPainter(self.schreiber)
        self.seite = 1
        self.massstab = self.schreiber.resolution() / 72.0  # Punkte -> Geraeteeinheiten
        self.breite = self.schreiber.width()
        self.hoehe = self.schreiber.height()
        self.y = 0.0
        self.datum = datetime.date.today().isoformat()
        self._kopf_fuss()

    def p(self, punkte: float) -> float:
        return punkte * self.massstab

    def schrift(self, groesse: float, fett: bool = False):
        f = QtGui.QFont("Helvetica")
        f.setPointSizeF(groesse)
        f.setBold(fett)
        self.maler.setFont(f)

    def _kopf_fuss(self):
        m = self.maler
        self.schrift(8)
        m.setPen(QtGui.QColor("#555555"))
        m.drawText(QtCore.QRectF(self.p(RAND), self.p(12), self.breite - 2 * self.p(RAND), self.p(14)),
                   QtCore.Qt.AlignmentFlag.AlignLeft, f"3DGmax {VERSION} · {self.titel}")
        m.drawText(QtCore.QRectF(self.p(RAND), self.p(12), self.breite - 2 * self.p(RAND), self.p(14)),
                   QtCore.Qt.AlignmentFlag.AlignRight, self.datum)
        m.drawText(QtCore.QRectF(self.p(RAND), self.hoehe - self.p(22), self.breite - 2 * self.p(RAND), self.p(14)),
                   QtCore.Qt.AlignmentFlag.AlignRight, tr("Seite {}").format(self.seite))
        m.setPen(QtGui.QColor("#000000"))
        self.y = self.p(34)

    def neue_seite(self):
        self.schreiber.newPage()
        self.seite += 1
        self._kopf_fuss()

    def platz(self) -> float:
        return self.hoehe - self.p(30) - self.y

    def ueberschrift(self, text: str, groesse: float = 15):
        self.schrift(groesse, True)
        h = self.p(groesse * 1.6)
        self.maler.drawText(QtCore.QRectF(self.p(RAND), self.y, self.breite - 2 * self.p(RAND), h),
                            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, text)
        self.y += h

    def absatz(self, text: str, groesse: float = 9.5):
        self.schrift(groesse)
        rect = QtCore.QRectF(self.p(RAND), self.y, self.breite - 2 * self.p(RAND), self.hoehe)
        flags = int(QtCore.Qt.AlignmentFlag.AlignLeft) | int(QtCore.Qt.TextFlag.TextWordWrap)
        benoetigt = self.maler.boundingRect(rect, flags, text)
        if benoetigt.height() > self.platz():
            self.neue_seite()
            rect.moveTop(self.y)
        self.maler.drawText(rect, flags, text)
        self.y += benoetigt.height() + self.p(4)

    def bild(self, img: QtGui.QImage, max_hoehe_anteil: float = 0.55):
        if img is None or img.isNull():
            return
        b = self.breite - 2 * self.p(RAND)
        h = min(self.platz(), self.hoehe * max_hoehe_anteil)
        groesse = img.size().scaled(int(b), int(h), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        if groesse.height() > self.platz():
            self.neue_seite()
        x = self.p(RAND) + (b - groesse.width()) / 2
        self.maler.drawImage(QtCore.QRectF(x, self.y, groesse.width(), groesse.height()), img)
        self.maler.setPen(QtGui.QColor("#bbbbbb"))
        self.maler.drawRect(QtCore.QRectF(x, self.y, groesse.width(), groesse.height()))
        self.maler.setPen(QtGui.QColor("#000000"))
        self.y += groesse.height() + self.p(8)

    def tabelle(self, spalten: list[tuple[str, float]], zeilen: list[list[str]], groesse: float = 8.5):
        """spalten: (Titel, Anteil der Breite)."""
        gesamt = self.breite - 2 * self.p(RAND)
        breiten = [gesamt * anteil for _, anteil in spalten]
        zeile_h = self.p(groesse * 1.7)

        def kopf():
            self.schrift(groesse, True)
            x = self.p(RAND)
            self.maler.fillRect(QtCore.QRectF(x, self.y, gesamt, zeile_h), QtGui.QColor("#e8edf5"))
            for (titel, _), w in zip(spalten, breiten):
                self.maler.drawText(QtCore.QRectF(x + self.p(3), self.y, w - self.p(6), zeile_h),
                                    QtCore.Qt.AlignmentFlag.AlignVCenter, titel)
                x += w
            self.y += zeile_h
            self.schrift(groesse)

        if self.platz() < 3 * zeile_h:
            self.neue_seite()
        kopf()
        for i, zeile in enumerate(zeilen):
            flags = int(QtCore.Qt.AlignmentFlag.AlignVCenter) | int(QtCore.Qt.TextFlag.TextWordWrap)
            hoehen = [self.maler.boundingRect(QtCore.QRectF(0, 0, w - self.p(6), self.hoehe), flags, str(t)).height()
                      for t, w in zip(zeile, breiten)]
            h = max(zeile_h, max(hoehen) + self.p(4))
            if h > self.platz():
                self.neue_seite()
                kopf()
            if i % 2:
                self.maler.fillRect(QtCore.QRectF(self.p(RAND), self.y, gesamt, h), QtGui.QColor("#f6f7f9"))
            x = self.p(RAND)
            for t, w in zip(zeile, breiten):
                self.maler.drawText(QtCore.QRectF(x + self.p(3), self.y, w - self.p(6), h), flags, str(t))
                x += w
            self.y += h

    def fertig(self) -> str:
        self.maler.end()
        return self.pfad


PMI_SPALTEN = [("Nr", 0.05), ("Art", 0.10), ("Name", 0.25), ("Wert", 0.37), ("Bezüge", 0.13), ("Flächen", 0.10)]


def _pmi_zeilen(pmi_liste):
    from .panels import ART_TEXT
    return [[str(p.nummer), tr(ART_TEXT.get(p.art, p.art)), p.name, p.wert_text(), p.bezug_text(), str(len(p.flaechen))]
            for p in pmi_liste]


def _warte():
    for _ in range(3):
        QtWidgets.QApplication.processEvents()


class _BreiteAnsicht:
    """Seitenleisten waehrend des Exports ausblenden, damit die 3D-Bilder im Querformat entstehen."""

    def __init__(self, fenster):
        self.fenster = fenster
        self.docks = [d for d in fenster.findChildren(QtWidgets.QDockWidget) if d.isVisible()]

    def __enter__(self):
        for d in self.docks:
            d.hide()
        _warte()
        return self

    def __exit__(self, *_):
        for d in self.docks:
            d.show()
        _warte()


def ansichten_pdf(fenster, pfad: str, nur_mit_pmi: bool = True) -> str:
    """Eine Seite je gespeicherter Ansicht: Ansichtsname, Modellname, Bild, Liste der sichtbaren PMI."""
    erg = fenster.erg
    ansichten = [a for a in erg.ansichten if a.pmi_nummern or not nur_mit_pmi]
    modell = os.path.basename(erg.pfad)
    bericht = PdfBericht(pfad, tr("Gespeicherte Ansichten – {}").format(modell))
    nach_nr = {p.nummer: p for p in erg.pmi}
    alte_zeile = fenster.ansichten.liste.currentRow()
    with _BreiteAnsicht(fenster):
        _ansichten_seiten(fenster, bericht, ansichten, modell, nach_nr, erg)
    if not ansichten:
        bericht.ueberschrift(tr("Keine gespeicherten Ansichten mit PMI"))
    fenster.ansichten.liste.setCurrentRow(max(alte_zeile, 0))
    return bericht.fertig()


def _ansichten_seiten(fenster, bericht, ansichten, modell, nach_nr, erg):
    for i, a in enumerate(ansichten):
        if i:
            bericht.neue_seite()
        fenster.ansichten.waehle_name(a.name)
        _warte()
        bericht.ueberschrift(f"{a.name}")
        bericht.absatz(tr("Modell: {} · Ansicht {} von {} · {} von {} PMI").format(
            modell, i + 1, len(ansichten), len(a.pmi_nummern), len(erg.pmi)))
        bericht.bild(fenster.ansicht.bild_qimage(), 0.58)
        bericht.tabelle([(tr(t), w) for t, w in PMI_SPALTEN], _pmi_zeilen([nach_nr[n] for n in a.pmi_nummern]))


AENDERUNG_SPALTEN = [("Nr", 0.05), ("Art", 0.09), ("Änderung", 0.34), ("Beschreibung", 0.30), ("Prüfstatus", 0.09),
                     ("Kommentar", 0.13)]


def _aenderung_zeilen(vergleich):
    from .vergleich_ui import KATEGORIE_TEXT, PRUEF_TEXT
    return [[str(a.nummer), tr(KATEGORIE_TEXT[a.kategorie]), a.titel, a.beschreibung, tr(PRUEF_TEXT[a.pruefstatus]),
             a.kommentar] for a in vergleich.aenderungen]


def vergleich_pdf(fenster, pfad: str, bilder: bool = True) -> str:
    """Vergleichsbericht: Uebersicht mit Gesamtbild, Aenderungsliste, je Aenderung eine Seite mit Bild."""
    from ..kern import pruefung
    v = fenster.vergleich
    alt, neu = os.path.basename(v.alt.pfad), os.path.basename(v.neu.pfad)
    bericht = PdfBericht(pfad, tr("Vergleich {} → {}").format(alt, neu))
    bericht.ueberschrift(tr("Vergleich zweier Stände"))
    z = v.geo.zaehler
    bericht.absatz(tr("Alter Stand: {} (SHA-256 {})").format(alt, pruefung.datei_hash(v.alt.pfad)[:16] + "…"))
    bericht.absatz(tr("Neuer Stand: {} (SHA-256 {})").format(neu, pruefung.datei_hash(v.neu.pfad)[:16] + "…"))
    bericht.absatz(tr("Toleranz {} mm, Suchweite {} mm, Ausrichtung: {}. Flächen: {} gleich, {} geändert, {} neu, "
                      "{} entfernt. {} Änderungen ({} PMI, {} Geometrie).").format(
        v.toleranz, v.suchweite, v.ausrichtung.methode, z.get("gleich", 0), z.get("geaendert", 0), z.get("neu", 0),
        z.get("entfernt", 0), len(v.aenderungen), sum(a.kategorie == "pmi" for a in v.aenderungen),
        sum(a.kategorie == "geometrie" for a in v.aenderungen)))
    with _BreiteAnsicht(fenster):
        _vergleich_seiten(fenster, bericht, v, bilder)
    return bericht.fertig()


def _vergleich_seiten(fenster, bericht, v, bilder):
    if bilder:
        fenster.ansicht.hebe_flaechen(set())
        fenster.ansicht.standard("iso")
        _warte()
        bericht.bild(fenster.ansicht.bild_qimage(), 0.5)
    bericht.tabelle([(tr(t), w) for t, w in AENDERUNG_SPALTEN], _aenderung_zeilen(v))
    if bilder:
        for a in v.aenderungen:
            bericht.neue_seite()
            bericht.ueberschrift(f"{a.nummer}: {a.titel}", 13)
            bericht.absatz(a.beschreibung)
            from .vergleich_ui import PRUEF_TEXT
            bericht.absatz(tr("Prüfstatus: {}").format(tr(PRUEF_TEXT[a.pruefstatus]))
                           + (f" · {tr('Kommentar')}: {a.kommentar}" if a.kommentar else ""))
            fenster._aenderung_gewaehlt(a)
            _warte()
            bericht.bild(fenster.ansicht.bild_qimage(), 0.7)


def pmi_aenderungen_pdf(vergleich, pfad: str) -> str:
    """Tabelle der PMI-Aenderungen (alt/neu) fuer Lieferanten und Fertigung, ohne Bilder."""
    from .vergleich_ui import PRUEF_TEXT, STATUS_TEXT
    alt, neu = os.path.basename(vergleich.alt.pfad), os.path.basename(vergleich.neu.pfad)
    bericht = PdfBericht(pfad, tr("PMI-Änderungen {} → {}").format(alt, neu))
    bericht.ueberschrift(tr("PMI-Änderungen"))
    bericht.absatz(tr("Alter Stand: {} · Neuer Stand: {}").format(alt, neu))
    zeilen = []
    for a in vergleich.aenderungen:
        if a.kategorie != "pmi":
            continue
        zeilen.append([str(a.nummer), tr(STATUS_TEXT.get(a.status, a.status)),
                       a.pmi_alt.wert_text() if a.pmi_alt is not None else "–",
                       a.pmi_neu.wert_text() if a.pmi_neu is not None else "–",
                       a.beschreibung, tr(PRUEF_TEXT[a.pruefstatus]), a.kommentar])
    spalten = [("Nr", 0.05), ("Status", 0.10), ("Alt", 0.17), ("Neu", 0.17), ("Änderung", 0.28), ("Prüfstatus", 0.09),
               ("Kommentar", 0.14)]
    bericht.tabelle([(tr(t), w) for t, w in spalten], zeilen or [["–", tr("keine PMI-Änderungen"), "", "", "", "", ""]])
    return bericht.fertig()


MERKMAL_BREITEN = (0.05, 0.04, 0.12, 0.17, 0.07, 0.07, 0.07, 0.08, 0.09, 0.05, 0.07, 0.04, 0.08)


def merkmale_pdf(fenster, pfad: str, bild: bool = True) -> str:
    """Merkmalsliste mit Ballonnummern: Uebersichtsbild mit Ballonen, dann Tabelle mit Spalten fuer Messwerte."""
    from ..kern import merkmale
    erg = fenster.erg
    modell = os.path.basename(erg.pfad)
    liste = merkmale.liste(erg.pmi)
    bericht = PdfBericht(pfad, tr("Merkmalsliste – {}").format(modell))
    bericht.ueberschrift(tr("Merkmalsliste"))
    bericht.absatz(tr("Modell: {} · {} Merkmale · Norm: {}").format(
        modell, len(liste), getattr(fenster, "norm_text", "") or "–"))
    if bild:
        war_an = fenster.aktionen["ballone"].isChecked()
        fenster.aktionen["ballone"].setChecked(True)
        fenster.zeige_ballone_aktuell()
        with _BreiteAnsicht(fenster):
            fenster.ansicht.alles_zeigen()
            _warte()
            bericht.bild(fenster.ansicht.bild_qimage(), 0.62)
        fenster.aktionen["ballone"].setChecked(war_an)
        fenster.zeige_ballone_aktuell()
        bericht.neue_seite()
    spalten = [(tr(t), b) for t, b in zip(merkmale.SPALTEN, MERKMAL_BREITEN)]
    bericht.tabelle(spalten, merkmale.zeilen(liste, erg.ansichten) or [["–"] + [""] * (len(spalten) - 1)])
    return bericht.fertig()


MESS_SPALTEN = [("Nr", 0.05), ("Art", 0.13), ("Wert", 0.22), ("Elemente", 0.25), ("Punkte (mm)", 0.35)]


def messungen_pdf(fenster, pfad: str, bild: bool = True) -> str:
    """Messprotokoll: Bild mit den Messungen im Modell, Tabelle mit Werten, Elementen und Punkten."""
    from .messwerkzeug import ART_TEXT, _woerter
    erg = fenster.erg
    modell = os.path.basename(erg.pfad)
    liste = list(fenster.messen.messungen)
    bericht = PdfBericht(pfad, tr("Messprotokoll – {}").format(modell))
    bericht.ueberschrift(tr("Messprotokoll"))
    bericht.absatz(tr("Modell: {} · {} Messungen · Werte aus der exakten Geometrie").format(modell, len(liste)))
    if bild and liste:
        with _BreiteAnsicht(fenster):
            bericht.bild(fenster.ansicht.bild_qimage(), 0.58)
    zeilen = [[str(m.nummer), tr(ART_TEXT.get(m.art, m.art)), _woerter(m.text()), _woerter(m.elemente),
               " | ".join(f"{x:.3f}, {y:.3f}, {z:.3f}" for x, y, z in m.punkte)] for m in liste]
    bericht.tabelle([(tr(t), w) for t, w in MESS_SPALTEN], zeilen or [["–", tr("keine Messungen"), "", "", ""]])
    return bericht.fertig()
