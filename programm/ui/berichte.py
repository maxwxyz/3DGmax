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

    def tabelle(self, spalten: list[tuple[str, float]], zeilen: list[list[str]], groesse: float = 8.5,
                fett: set[int] | None = None):
        """spalten: (Titel, Anteil der Breite); fett: Nummern der fett gedruckten Zeilen."""
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
            self.schrift(groesse, bool(fett and i in fett))
            x = self.p(RAND)
            for t, w in zip(zeile, breiten):
                self.maler.drawText(QtCore.QRectF(x + self.p(3), self.y, w - self.p(6), h), flags, str(t))
                x += w
            self.y += h

    def fertig(self) -> str:
        self.maler.end()
        return self.pfad


PMI_SPALTEN = [("Nr", 0.05), ("Art", 0.10), ("Name", 0.25), ("Wert", 0.37), ("Bezüge", 0.13), ("Flächen", 0.10)]


# Breitengewichte der PMI-Spalten im PDF (nicht genannte: 1)
PMI_GEWICHT = {"Nr": 0.5, "Ballon": 0.6, "Flächen": 0.6, "Art": 0.9, "Merkmal": 1.4, "Name": 2.0, "Wert": 3.0,
               "Bezüge": 1.1, "Ansichten": 1.4, "Modifikatoren": 1.4, "Semantisch": 0.8}


def _pmi_zeilen(pmi_liste):
    from .panels import ART_TEXT
    return [[str(p.nummer), tr(ART_TEXT.get(p.art, p.art)), p.name, p.wert_text(), p.bezug_text(), str(len(p.flaechen))]
            for p in pmi_liste]


def pmi_tabelle(fenster, pmi_liste) -> tuple[list[tuple[str, float]], list[list[str]]]:
    """Spalten wie in der PMI-Liste sichtbar (Reihenfolge, Auswahl); ohne Liste die Standardspalten."""
    panel = getattr(fenster, "pmi", None)
    if panel is None or not hasattr(panel, "sichtbare_spalten"):
        return [(tr(t), w) for t, w in PMI_SPALTEN], _pmi_zeilen(pmi_liste)
    spalten = panel.sichtbare_spalten() or ["Nr", "Wert"]
    gewichte = [PMI_GEWICHT.get(s, 1.0) for s in spalten]
    summe = sum(gewichte)
    return [(tr(s), g / summe) for s, g in zip(spalten, gewichte)], panel.zeilen(pmi_liste, spalten)


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
        bericht.tabelle(*pmi_tabelle(fenster, [nach_nr[n] for n in a.pmi_nummern]))


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


KETTE_GEWICHT = {"Glied": 2.4, "Quelle": 1.3, "Verteilung": 1.6}


def kette_pdf(fenster, pfad: str, bild: bool = True) -> str:
    """Toleranzkette: Bild mit den Flaechen der Kette, Ergebnistabelle (anwendbares Verfahren fett, im Planspiel
    neben dem Ist), Begruendung, Histogramm, Glieder mit Beitragsanteil."""
    from ..kern import toleranzkette as tk
    k = fenster._kette
    e = k.e
    modell = os.path.basename(fenster.erg.pfad)
    bericht = PdfBericht(pfad, tr("Toleranzkette – {}").format(modell))
    bericht.ueberschrift(tr("Toleranzkette") + (" – " + tr("Planspiel") if k.im_planspiel else ""))
    bericht.absatz(tr("Modell: {} · {} Glieder · Cp der Kette {:.2f} · Schlussmaß {:.4f} mm").format(
        modell, len(k.glieder), k.cp.value(), e.nenn))
    flaechen = {f for g in k.glieder for f in g.flaechen}
    if bild and flaechen:
        alt = set(fenster.ansicht.hervor)
        fenster.ansicht.hebe_flaechen(flaechen)
        with _BreiteAnsicht(fenster):
            bericht.bild(fenster.ansicht.bild_qimage(), 0.42)
        fenster.ansicht.hebe_flaechen(alt)
    koepfe, zeilen = k.ergebnis_zeilen()
    breite = [0.34] + [0.66 / (len(koepfe) - 1)] * (len(koepfe) - 1)
    bericht.tabelle(list(zip(koepfe, breite)), [z for z, _ in zeilen], 9,
                    fett={i for i, (_, f) in enumerate(zeilen) if f})
    bericht.absatz(tk.anwendbar_text(e) + (" · " + tr("Ist: {}").format(tk.anwendbar_text(k.e_ist))
                                           if k.e_ist is not None else ""), 9.5)
    if e.cp is not None:
        u, o = k.anforderung_werte()
        bericht.absatz(tr("Anforderung {:.4f} … {:.4f} mm: Cp {:.2f}, Cpk {:.2f}, außerhalb {:.0f} ppm (Normalverteilung), "
                          "{:.0f} ppm (Monte Carlo)").format(u, o, e.cp, e.cpk, e.ausserhalb * 1e6,
                                                            e.mc_ausserhalb * 1e6), 9.5)
    bericht.bild(k.histogramm.grab().toImage(), 0.16)
    gewicht = [KETTE_GEWICHT.get(s, 1.0) for s in tk.SPALTEN]
    spalten = [(tr(s), w / sum(gewicht)) for s, w in zip(tk.SPALTEN, gewicht)]
    tabelle, geaendert = [], set()
    for i, (g, anteil) in enumerate(zip(k.glieder, e.anteile)):
        form = (f"{g.cp or k.cp.value():.2f}" if g.verteilung == "normal" else
                f"a = {g.form:.2f}" if g.verteilung == "trapez" else "–")
        zeile = [g.name, "+" if g.richtung > 0 else "−", "–" if g.quelle == "lage" else f"{g.nenn:.4g}",
                 f"{g.hoechst:.4g}", f"{g.mindest:.4g}", f"{g.toleranz:.4g}", tr(tk.QUELLE[g.quelle]),
                 tr(tk.VERTEILUNG[g.verteilung]), form, f"{g.versatz:g}", f"{anteil:.0%}"]
        ist = k._ist_glied(i)
        if ist is not None and (ist.hoechst, ist.mindest, ist.nenn, ist.richtung, ist.verteilung, ist.cp, ist.form,
                                ist.versatz) != (g.hoechst, g.mindest, g.nenn, g.richtung, g.verteilung, g.cp, g.form,
                                                 g.versatz):
            geaendert.add(i)
            zeile[0] += " *"
        tabelle.append(zeile)
    bericht.tabelle(spalten, tabelle, fett=geaendert)
    if geaendert:
        bericht.absatz(tr("* im Planspiel geändert (fett); das Ist steht in der Ergebnistabelle daneben."), 8.5)
    bericht.absatz(tr("Verteilung je Glied: normal σ = T / (6 · Cp), Dreieck σ = T / (2√6), Trapez σ = T/2 · "
                      "√((1 + a²) / 6), gleichverteilt σ = T / (2√3); Anteil = Varianzanteil. Statistisch anwendbar ab "
                      "{} wirksamen Beitragsleistern n_eff = (Σσ²)² / Σσ⁴, sonst gilt das arithmetische Ergebnis. "
                      "Lagetoleranzen ohne Bonus bei Ⓜ/Ⓛ.").format(tk.MINDEST_BEITRAGSLEISTER), 8.5)
    return bericht.fertig()


def messgroessen_pdf(fenster, pfad: str) -> str:
    """Baugruppenvariation: Verbindungen mit Spielraum, je Messgroesse Ergebnis und Beitragende."""
    from ..kern import baugruppe_mass as bm
    from ..kern import verbindung as vb
    from .baugruppe_ui import BaugruppePanel
    b = fenster.baugruppe
    namen = fenster._teil_namen()
    ergebnisse = fenster.messgroessen_ergebnisse()
    modell = os.path.basename(fenster.erg.pfad)
    bericht = PdfBericht(pfad, tr("Baugruppenvariation – {}").format(modell))
    bericht.ueberschrift(tr("Baugruppenvariation"))
    bericht.absatz(tr("Modell: {} · {} Verbindungen · {} Messgrößen").format(modell, len(b.verbindungen),
                                                                              len(b.masse)))
    spalten = [(tr(s), w) for s, w in (("Nr", 0.06), ("Teil", 0.2), ("Gegenteil", 0.2), ("Art", 0.2),
                                        ("Spielraum", 0.12), ("Herkunft", 0.22))]
    bericht.tabelle(spalten, [[str(v.nummer), namen.get(v.teil, str(v.teil)), namen.get(v.gegen_teil, str(v.gegen_teil)),
                               tr(vb.ART_TEXT[v.art]), f"{v.toleranz:.4g}", v.quelle] for v in b.verbindungen])
    for m in b.masse:
        e = ergebnisse[m.nummer]
        bericht.ueberschrift(f"{m.nummer}: {bm.text(m, namen)}")
        bericht.absatz(tr("Nennwert {:.4f} mm · Worst Case {:.4f} … {:.4f} mm · Monte Carlo {:.4f} … {:.4f} mm "
                          "(99,73 %), Mittelwert {:.4f}, σ {:.4f}").format(e.nenn, e.wc_min, e.wc_max, e.mc_min,
                                                                         e.mc_max, e.mittel, e.std), 10)
        if e.aussen is not None:
            bericht.absatz(tr("Soll {}: außerhalb {:.2%}{}").format(
                bm.soll_text(m), e.aussen, "" if e.cpk is None else tr(", Cpk {:.2f}").format(e.cpk)), 10)
        if e.unbestimmt:
            bericht.absatz(tr("Hängt von offenen Freiheitsgraden ab (in Nennlage gerechnet)."), 9)
        spalten = [(tr(s), 1 / len(BaugruppePanel.BEITRAG_SPALTEN)) for s in BaugruppePanel.BEITRAG_SPALTEN]
        bericht.tabelle(spalten, [[str(x.verbindung), tr(vb.ART_TEXT[next(v.art for v in b.verbindungen
                                                                         if v.nummer == x.verbindung)]),
                                   f"{x.bereich:.4f}", f"{x.anteil_wc:.0%}", f"{x.anteil_var:.0%}"]
                                  for x in e.beitraege])
    bericht.absatz(tr("Lineares Modell: Teile bewegen sich in den Spielräumen ihrer Verbindungen; Worst Case per "
                      "linearem Programm, Monte Carlo normalverteilt (Spielraum = 3σ) mit gewichtetem Ausgleich bei "
                      "Überbestimmung. Bereich: Worst-Case-Breite, wenn nur diese Verbindung streut."), 8.5)
    return bericht.fertig()


SCAN_GEWICHT = {"Nr": 0.5, "PMI": 2.0, "Ergebnis": 1.2, "Istwert": 1.0, "Zulässig": 1.0, "Punkte": 0.8,
                "Auswertung": 3.2}


def scan_pdf(fenster, pfad: str, bilder: bool = True) -> str:
    """Pruefbericht der Scanpruefung: Kopf (Modell, Scan, Ausrichtung), Uebersicht mit Farbkarte, Tabelle aller PMI,
    je PMI ausserhalb oder am Grenzwert eine Seite mit Bild (Zone und Flaechen)."""
    from ..kern import scanpruefung as sp
    from .scan_ui import STATUS_TEXT, ScanPanel
    d = fenster._scan
    erg = fenster.erg
    modell = os.path.basename(erg.pfad)
    bericht = PdfBericht(pfad, tr("Prüfbericht – {}").format(modell))
    bericht.ueberschrift(tr("Prüfbericht Scan gegen Toleranzen"))
    bericht.absatz(tr("Modell: {} · Scan: {}").format(modell, os.path.basename(d["pfad"])))
    bericht.absatz(fenster._scan_kopf(d))
    z = fenster.scan.zaehler()
    bericht.absatz(tr("Ergebnis: {} i. O., {} n. i. O., {} am Grenzwert, {} nicht auswertbar · Messunsicherheit ±{} mm "
                      "· Näherung für die Sichtprüfung, keine normgerechte Auswertung nach Messstrategie").format(
        z[sp.OK], z[sp.NOK], z[sp.GRENZ], z[sp.OFFEN], sp.UNSICHERHEIT), 10)
    if bilder:
        with _BreiteAnsicht(fenster):
            fenster.pmi.waehle(lambda p: False)
            bericht.bild(fenster.ansicht.bild_qimage(), 0.45)
    gewicht = [SCAN_GEWICHT.get(s, 1.0) for s in ScanPanel.SPALTEN]
    spalten = [(tr(s), w / sum(gewicht)) for s, w in zip(ScanPanel.SPALTEN, gewicht)]
    zeilen = [[str(e.pmi.nummer), e.pmi.wert_text(), tr(STATUS_TEXT[e.status]),
               "" if e.ist is None else f"{e.ist:.4f}", "" if e.zulaessig is None else f"{e.zulaessig:.4f}",
               str(e.punkte), e.text] for e in fenster.scan.ergebnisse]
    bericht.tabelle(spalten, zeilen)
    if bilder:
        for e in [e for e in fenster.scan.ergebnisse if e.status in (sp.NOK, sp.GRENZ)]:
            bericht.neue_seite()
            bericht.ueberschrift(f"{e.pmi.nummer}: {e.pmi.wert_text()} – {tr(STATUS_TEXT[e.status])}", 13)
            bericht.absatz(e.text)
            fenster.pmi.waehle(lambda p, q=e.pmi: p is q)
            fenster.ansicht.zoome_auf(set(e.pmi.flaechen), None, {e.pmi.step_id})
            _warte()
            with _BreiteAnsicht(fenster):
                bericht.bild(fenster.ansicht.bild_qimage(), 0.7)
        fenster.pmi.waehle(lambda p: False)
        fenster.ansicht.alles_zeigen()
    return bericht.fertig()


def zeichnung_pdf(svg, pfad: str, titel: str, zeile: str) -> str:
    """Zeichnung(en) (SVG, vektoriell) auf A3 quer mit einfachem Schriftfeld; svg: Text oder Liste
    [(svg, titel, zeile)] fuer mehrere Seiten."""
    from PySide6 import QtCore, QtGui
    schreiber = QtGui.QPdfWriter(pfad)
    schreiber.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A3))
    schreiber.setPageOrientation(QtGui.QPageLayout.Orientation.Landscape)
    schreiber.setPageMargins(QtCore.QMarginsF(10, 10, 10, 10), QtGui.QPageLayout.Unit.Millimeter)
    schreiber.setTitle(titel)
    seiten = svg if isinstance(svg, list) else [(svg, titel, zeile)]
    maler = QtGui.QPainter(schreiber)
    for i, (inhalt, t, z) in enumerate(seiten):
        if i:
            schreiber.newPage()
        _zeichnung_seite(maler, schreiber, inhalt, t, z)
    maler.end()
    return pfad


def _zeichnung_seite(maler, schreiber, svg, titel, zeile):
    from PySide6 import QtCore, QtGui, QtSvg
    flaeche = QtCore.QRectF(0, 0, schreiber.width(), schreiber.height())
    feld_h = flaeche.height() * 0.07
    zeichnung = flaeche.adjusted(0, 0, 0, -feld_h * 1.2)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
    groesse = renderer.defaultSize()
    if groesse.width() > 0 and groesse.height() > 0:
        k = min(zeichnung.width() / groesse.width(), zeichnung.height() / groesse.height())
        ziel = QtCore.QRectF(zeichnung.x(), zeichnung.y(), groesse.width() * k, groesse.height() * k)
        renderer.render(maler, ziel)
    feld = QtCore.QRectF(flaeche.right() - flaeche.width() * 0.42, flaeche.bottom() - feld_h, flaeche.width() * 0.42,
                         feld_h)
    maler.setPen(QtGui.QPen(QtGui.QColor("black"), max(schreiber.resolution() / 150, 1)))
    maler.drawRect(feld)
    schrift = QtGui.QFont("Helvetica")
    schrift.setPointSizeF(11)
    schrift.setBold(True)
    maler.setFont(schrift)
    rand = feld.height() * 0.12
    maler.drawText(feld.adjusted(rand, rand, -rand, -feld.height() / 2), QtCore.Qt.AlignmentFlag.AlignLeft |
                   QtCore.Qt.AlignmentFlag.AlignVCenter, titel)
    schrift.setBold(False)
    schrift.setPointSizeF(8)
    maler.setFont(schrift)
    maler.drawText(feld.adjusted(rand, feld.height() / 2, -rand, -rand), QtCore.Qt.AlignmentFlag.AlignLeft |
                   QtCore.Qt.AlignmentFlag.AlignVCenter, zeile)


KOMMENTAR_BREITEN = (0.05, 0.12, 0.08, 0.42, 0.10, 0.12, 0.06, 0.05)


def kommentare_pdf(fenster, pfad: str, bild: bool = True) -> str:
    """Kommentarliste: Bild mit den Markierungen und Tabelle (Art, Status, Text, Autor, Datum, Bezug)."""
    from ..kern import kommentare as km
    liste = list(fenster.kommentare.kommentare)
    modell = os.path.basename(fenster.erg.pfad)
    bericht = PdfBericht(pfad, tr("Kommentare – {}").format(modell))
    bericht.ueberschrift(tr("Kommentare"))
    offen = sum(1 for k in liste if k.status != "erledigt")
    bericht.absatz(tr("Modell: {} · {} Kommentare, davon {} offen").format(modell, len(liste), offen))
    if bild and liste:
        with _BreiteAnsicht(fenster):
            fenster.ansicht.alles_zeigen()
            _warte()
            bericht.bild(fenster.ansicht.bild_qimage(), 0.55)
    spalten = [(tr(t), b) for t, b in zip(km.SPALTEN[:8], KOMMENTAR_BREITEN)]
    zeilen = [z[:8] for z in km.zeilen(liste)]
    bericht.tabelle(spalten, zeilen or [["–", tr("keine Kommentare")] + [""] * 6])
    return bericht.fertig()
