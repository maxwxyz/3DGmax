"""Fenster Funktion -> Tolerierung: Funktionsrollen der Flaechen vergeben, Bezugssystem und ISO-GPS-Tolerierung
vorschlagen (kern.funktion) und als eigene PMI uebernehmen."""

from __future__ import annotations

import html

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern import funktion as fu
from .tabellen import leer_hinweis, spalten_anpassen

ROLLEN_HILFE = {
    "auflage": "Fläche, mit der das Teil aufliegt oder anliegt – Kandidat für den Primärbezug",
    "zentrierung": "Bohrung oder Zapfen, der das Teil in der Ebene ausrichtet (Passung H7/h6)",
    "fuehrung": "Gleitende Führung mit Spiel (Passung H7/f7, Zylinderform)",
    "presssitz": "Fest gefügte Verbindung (Übermaßpassung H7/p6)",
    "verdrehsicherung": "Stift oder Bohrung gegen Verdrehen (Übergangspassung H7/m6, Position mit Ⓜ)",
    "dichtung": "Dichtfläche (Ebenheit, Rauheit, drallfrei)",
    "anschlag": "Anschlag, der eine Richtung begrenzt (Flächenprofil zum Bezugssystem)",
    "frei": "Ohne Funktion – Allgemeintoleranz genügt",
}


class FunktionFenster(QtWidgets.QDialog):
    """Elemente (eine oder mehrere Flaechen, z. B. zwei Halbschalen) mit Rolle, Passung und Toleranz; Passung und
    Toleranz leer bzw. "auto" = Startwert aus der Rolle."""

    flaechen_zeigen = QtCore.Signal(set)
    anlegen = QtCore.Signal(list)  # PMI-Vorschlaege (kern.pmi_vorschlag.Vorschlag) zum Uebernehmen
    vorschau = QtCore.Signal(object)  # Vorschau im 3D: {"bezuege", "offen", "vorschlaege", "zonen"} oder None
    SPALTEN = ("Fläche", "Geometrie", "Funktion", "Bezug", "Passung", "Toleranz (mm)")
    SP_FUNKTION, SP_BEZUG, SP_PASSUNG, SP_TOLERANZ = 2, 3, 4, 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Funktion → Tolerierung"))
        self.resize(760, 540)
        self.rollen: dict[int, str] = {}  # erste Flaeche des Elements -> Rolle
        self.gruppen: dict[int, tuple] = {}  # erste Flaeche -> alle Flaechen (nur Elemente aus mehreren Flaechen)
        self.werte: dict[int, dict] = {}  # erste Flaeche -> {"toleranz": mm, "passung": "H8"} von Hand
        self.bezuege_hand: dict[int, str] = {}  # erste Flaeche -> "A"/"B"/"C" von Hand (leer: Vorschlag)
        self.modell = None
        self.auswahl = lambda: []  # gewaehlte Flaechenindizes (setzt das Hauptfenster)
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(tr("Flächen im Modell wählen und ihre Funktion zuordnen – mehrere Flächen auf "
                                      "demselben Zylinder oder in derselben Ebene (z. B. zwei Halbschalen) werden ein "
                                      "Element. Daraus folgen das Bezugssystem (3-2-1 nach ISO 5459) und die "
                                      "Tolerierung nach ISO 1101/286; Funktion, Passung und Toleranz sind in der "
                                      "Tabelle änderbar."))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("leise")
        lay.addWidget(hinweis)
        reihe = QtWidgets.QHBoxLayout()
        self.rolle = QtWidgets.QComboBox()
        self._fuelle_rollen(self.rolle)
        self.rolle.setToolTip(tr("Funktion der gewählten Flächen"))
        self.setzen = QtWidgets.QPushButton(tr("Rolle für Auswahl"))
        self.setzen.setToolTip(tr("Den im Modell gewählten Flächen diese Funktion zuordnen (Flächen eines Zylinders "
                                  "bzw. einer Ebene als ein Element)"))
        self.setzen.clicked.connect(lambda: self.setze_rolle(self.auswahl(), self.rolle.currentData()))
        self.tauschen = QtWidgets.QPushButton(tr("Flächen aus Auswahl"))
        self.tauschen.setToolTip(tr("Die Flächen des in der Tabelle gewählten Elements durch die im Modell gewählten "
                                    "ersetzen (Funktion und Werte bleiben)"))
        self.tauschen.clicked.connect(lambda: self.ersetze_flaechen(self.auswahl()))
        self.weg = QtWidgets.QPushButton(tr("Entfernen"))
        self.weg.setToolTip(tr("Rolle der in der Tabelle gewählten Flächen entfernen"))
        self.weg.clicked.connect(self._entfernen)
        for w in (self.rolle, self.setzen, self.tauschen, self.weg):
            reihe.addWidget(w)
        reihe.addStretch(1)
        lay.addLayout(reihe)
        self.tabelle = QtWidgets.QTableWidget(0, len(self.SPALTEN))
        leer_hinweis(self.tabelle, tr("Noch keine Elemente – Flächen im Modell wählen, oben die Funktion wählen und "
                                      "„Rolle für Auswahl“"))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in self.SPALTEN])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        trigger = QtWidgets.QAbstractItemView.EditTrigger
        self.tabelle.setEditTriggers(trigger.SelectedClicked | trigger.DoubleClicked | trigger.EditKeyPressed |
                                     trigger.AnyKeyPressed)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.itemSelectionChanged.connect(self._zeige)
        self.tabelle.itemChanged.connect(self._wert_geaendert)
        lay.addWidget(self.tabelle, 1)
        self.bezug_text = QtWidgets.QLabel("")
        self.bezug_text.setWordWrap(True)
        self.bezug_text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lay.addWidget(self.bezug_text)
        knoepfe = QtWidgets.QHBoxLayout()
        self.bezuege_knopf = QtWidgets.QPushButton(tr("Bezüge vorschlagen"))
        self.bezuege_knopf.setToolTip(tr("Bezugssystem A|B|C aus den Rollen: größte Auflage, Zentrierung, "
                                         "Verdrehsicherung bzw. Anschlag – die Bezugsflächen werden hervorgehoben"))
        self.bezuege_knopf.clicked.connect(self.zeige_bezuege)
        self.tol_knopf = QtWidgets.QPushButton(tr("Tolerierung vorschlagen …"))
        self.tol_knopf.setObjectName("primaer")
        self.tol_knopf.setToolTip(tr("Bezüge, Passungen, Form-, Richtungs- und Lagetoleranzen je Rolle vorschlagen und "
                                     "als eigene PMI übernehmen (danach als STEP speicherbar)"))
        self.tol_knopf.clicked.connect(lambda: self.anlegen.emit(self.vorschlaege()))
        self.vorschau_knopf = QtWidgets.QPushButton(tr("Vorschau im 3D"))
        self.vorschau_knopf.setCheckable(True)
        self.vorschau_knopf.setChecked(True)
        self.vorschau_knopf.setToolTip(tr("Vorschlag live im Modell zeigen: Bezugsflächen A/B/C farbig, offene "
                                          "Freiheitsgrade als Pfeile bzw. Kreise, die vorgeschlagenen Angaben als "
                                          "Vorschau-Callouts – jede Änderung in der Tabelle zieht nach"))
        self.vorschau_knopf.toggled.connect(lambda _a: self._vorschau_planen())
        self.zonen_knopf = QtWidgets.QPushButton(tr("Toleranzzonen"))
        self.zonen_knopf.setCheckable(True)
        self.zonen_knopf.setToolTip(tr("In der Vorschau auch die Toleranzzonen der vorgeschlagenen Toleranzen zeigen"))
        self.zonen_knopf.toggled.connect(lambda _a: self._vorschau_planen())
        knoepfe.addWidget(self.bezuege_knopf)
        knoepfe.addWidget(self.vorschau_knopf)
        knoepfe.addWidget(self.zonen_knopf)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.tol_knopf)
        lay.addLayout(knoepfe)
        self._vorschau_uhr = QtCore.QTimer(self)  # mehrere Aenderungen hintereinander: einmal neu zeigen
        self._vorschau_uhr.setSingleShot(True)
        self._vorschau_uhr.setInterval(250)
        self._vorschau_uhr.timeout.connect(self.sende_vorschau)
        self._vorschau_an = False  # zuletzt eine Vorschau gesendet (beim Ausblenden entfernen)
        self._fuelle()

    @staticmethod
    def _fuelle_rollen(box: QtWidgets.QComboBox):
        for schluessel, (name, _) in fu.ROLLEN.items():
            box.addItem(tr(name), schluessel)
            box.setItemData(box.count() - 1, tr(ROLLEN_HILFE[schluessel]), QtCore.Qt.ItemDataRole.ToolTipRole)

    def setze_modell(self, modell):
        if modell is not self.modell:
            self.modell = modell
            self.rollen, self.gruppen, self.werte, self.bezuege_hand = {}, {}, {}, {}
            self._fuelle()

    def flaechen(self, erste: int) -> tuple:
        return self.gruppen.get(erste, (erste,))

    def _element_von(self, flaeche: int) -> int | None:
        return next((e for e in self.rollen if flaeche in self.flaechen(e)), None)

    def _loese(self, flaechen):
        """Flaechen aus bestehenden Elementen nehmen (ein Element ohne Flaechen faellt weg)."""
        for f in flaechen:
            e = self._element_von(f)
            if e is None:
                continue
            rest = tuple(x for x in self.flaechen(e) if x != f)
            rolle, werte = self.rollen.pop(e), self.werte.pop(e, None)
            self.gruppen.pop(e, None)
            if rest:
                self._setze(rest, rolle, werte)

    def _setze(self, flaechen, rolle: str, werte: dict | None = None) -> int:
        erste = min(flaechen)
        self.rollen[erste] = rolle
        if len(flaechen) > 1:
            self.gruppen[erste] = tuple(sorted(flaechen))
        if werte:
            self.werte[erste] = werte
        return erste

    def setze_rolle(self, flaechen, rolle: str) -> int:
        """Rolle fuer Flaechen (nur Ebenen und Zylinder): mehrere Flaechen eines Zylinders bzw. einer Ebene als ein
        Element, sonst je Flaeche; Anzahl der zugeordneten Flaechen."""
        flaechen = [i for i in flaechen if self.modell is not None and fu._geometrie(self.modell.flaechen[i])]
        if not flaechen:
            return 0
        bisher = {self._element_von(i) for i in flaechen} - {None}
        if len(flaechen) == 1 and len(bisher) == 1:  # Flaeche eines Elements gewaehlt: Rolle des Elements
            self.rollen[bisher.pop()] = rolle
        elif len(flaechen) > 1 and fu.ein_element(self.modell, flaechen):
            self._loese(flaechen)
            self._setze(flaechen, rolle)
        else:
            self._loese(flaechen)
            for i in flaechen:
                self._setze((i,), rolle)
        self._fuelle()
        return len(flaechen)

    def ersetze_flaechen(self, flaechen) -> bool:
        """Flaechen des gewaehlten Elements durch die Auswahl ersetzen; False ohne genau ein Element oder wenn die
        Auswahl kein Element bildet."""
        zeilen = sorted({i.row() for i in self.tabelle.selectedIndexes()})
        flaechen = [i for i in flaechen if self.modell is not None and fu._geometrie(self.modell.flaechen[i])]
        if len(zeilen) != 1 or not flaechen or (len(flaechen) > 1 and not fu.ein_element(self.modell, flaechen)):
            return False
        alt = self.tabelle.item(zeilen[0], 0).data(QtCore.Qt.ItemDataRole.UserRole)
        rolle, werte, bezug = self.rollen.pop(alt), self.werte.pop(alt, None), self.bezuege_hand.pop(alt, None)
        self.gruppen.pop(alt, None)
        self._loese(flaechen)
        erste = self._setze(flaechen, rolle, werte)
        if bezug:
            self.bezuege_hand[erste] = bezug
        self._fuelle()
        self.tabelle.selectRow(sorted(self.rollen).index(erste))
        return True

    def _entfernen(self):
        for z in sorted({i.row() for i in self.tabelle.selectedIndexes()}, reverse=True):
            e = self.tabelle.item(z, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            self.rollen.pop(e, None)
            self.gruppen.pop(e, None)
            self.werte.pop(e, None)
            self.bezuege_hand.pop(e, None)
        self._fuelle()

    def _fuelle(self):
        from .toleranzkette_ui import AENDERBAR_FARBE
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(self.rollen))
        # Vorschlag ohne Vorgaben: welcher Buchstabe ergaebe sich (Anzeige "auto (A)")
        vorschlag = {b.flaeche: b.buchstabe for b in fu.bezugssystem(self.modell, self.rollen, self.gruppen).bezuege} \
            if self.modell is not None and self.rollen else {}
        for z, (i, rolle) in enumerate(sorted(self.rollen.items())):
            g = fu._geo(self.modell, i, self.gruppen) if self.modell is not None else None
            art = "" if g is None else (tr("Ebene") if g["art"] == "ebene" else
                                        tr("Bohrung ⌀{:g}").format(round(g["groesse"], 3)) if g["bohrung"] else
                                        tr("Zapfen ⌀{:g}").format(round(g["groesse"], 3)))
            start = fu.startwerte(self.modell, i, rolle, self.gruppen) if self.modell is not None else {}
            w = self.werte.get(i, {})
            flaechen = " + ".join(str(x) for x in self.flaechen(i))
            for s, text in enumerate((flaechen, art)):
                it = QtWidgets.QTableWidgetItem(text)
                it.setData(QtCore.Qt.ItemDataRole.UserRole, i)
                it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if s == 0 and len(self.flaechen(i)) > 1:
                    it.setToolTip(tr("Ein Element aus {} Flächen").format(len(self.flaechen(i))))
                t.setItem(z, s, it)
            box = QtWidgets.QComboBox()
            self._fuelle_rollen(box)
            box.setCurrentIndex(box.findData(rolle))
            box.setToolTip(tr(ROLLEN_HILFE[rolle]))
            box.currentIndexChanged.connect(lambda _k, e=i, b=box: self._rolle_geaendert(e, b.currentData()))
            t.setItem(z, self.SP_FUNKTION, QtWidgets.QTableWidgetItem(""))
            t.setCellWidget(z, self.SP_FUNKTION, box)
            bezug = QtWidgets.QComboBox()  # Bezug von Hand: auto = aus den Rollen vorgeschlagen
            bezug.addItem(tr("auto") + (f" ({vorschlag[i]})" if i in vorschlag and not self.bezuege_hand else ""), "")
            for b in "ABC":
                bezug.addItem(b, b)
            bezug.setCurrentIndex(max(0, bezug.findData(self.bezuege_hand.get(i, ""))))
            bezug.setToolTip(tr("Bezug von Hand festlegen (A, B, C); auto: aus den Funktionsrollen vorschlagen – sobald "
                                "ein Bezug von Hand gesetzt ist, gilt nur die Zuordnung von Hand"))
            bezug.currentIndexChanged.connect(lambda _k, e=i, b=bezug: self._bezug_geaendert(e, b.currentData()))
            t.setItem(z, self.SP_BEZUG, QtWidgets.QTableWidgetItem(""))
            t.setCellWidget(z, self.SP_BEZUG, bezug)
            zylinder = g is not None and g["art"] == "zylinder"
            for s, eigen, auto, hilfe in (
                    (self.SP_PASSUNG, w.get("passung"), start.get("passung", ""),
                     tr("Toleranzklasse nach ISO 286, z. B. H7 oder g6; leer = aus der Funktion ({})")),
                    (self.SP_TOLERANZ, w.get("toleranz"), "",
                     tr("Wert aller Form- und Lagetoleranzen dieses Elements in mm; leer = Startwert aus dem IT-Grad "
                        "({})"))):
                it = QtWidgets.QTableWidgetItem("" if eigen is None else (f"{eigen:g}" if s == self.SP_TOLERANZ
                                                                         else eigen))
                if s == self.SP_PASSUNG and not zylinder:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    it.setToolTip(tr("Passungen nur an Zylindern"))
                else:
                    it.setBackground(AENDERBAR_FARBE)
                    if eigen is None:  # Startwert grau anzeigen; Eingabe ersetzt ihn
                        it.setText(auto if s == self.SP_PASSUNG else tr("auto"))
                        it.setForeground(QtGui.QColor(128, 128, 128))
                    stand = auto if s == self.SP_PASSUNG else (
                        tr("Form {:g}, Lage {:g} mm").format(start["form"], start["lage"]) if start else "–")
                    it.setToolTip(hilfe.format(stand or "–"))
                it.setData(QtCore.Qt.ItemDataRole.UserRole, i)
                t.setItem(z, s, it)
        t.blockSignals(False)
        spalten_anpassen(t, strecken=True)  # misst auch die Auswahllisten in den Zellen
        for k in (self.bezuege_knopf, self.tol_knopf):
            k.setEnabled(bool(self.rollen))
        self.tauschen.setEnabled(bool(self.rollen))
        self._vorschau_planen()  # jede Aenderung der Tabelle zieht die Vorschau nach

    def _bezug_geaendert(self, erste: int, buchstabe: str):
        """Buchstabe von Hand (ein Buchstabe nur einmal: bei einem anderen Element wird er dort geloescht)."""
        for e in [e for e, b in self.bezuege_hand.items() if b == buchstabe and e != erste]:
            self.bezuege_hand.pop(e)
        if buchstabe:
            self.bezuege_hand[erste] = buchstabe
        else:
            self.bezuege_hand.pop(erste, None)
        QtCore.QTimer.singleShot(0, self._fuelle)
        self.zeige_bezuege()

    def _rolle_geaendert(self, erste: int, rolle: str):
        self.rollen[erste] = rolle
        zeile = sorted(self.rollen).index(erste)
        self._fuelle()
        self.tabelle.selectRow(zeile)

    def _wert_geaendert(self, it: QtWidgets.QTableWidgetItem):
        """Passung oder Toleranz von Hand; leer oder "auto" = Startwert."""
        if it.column() not in (self.SP_PASSUNG, self.SP_TOLERANZ):
            return
        erste = it.data(QtCore.Qt.ItemDataRole.UserRole)
        text = it.text().strip()
        start = fu.startwerte(self.modell, erste, self.rollen.get(erste, "frei"), self.gruppen)
        w = self.werte.setdefault(erste, {})
        if it.column() == self.SP_PASSUNG:
            w.pop("passung", None)
            if text and text != start.get("passung"):
                w["passung"] = text
        else:
            w.pop("toleranz", None)
            try:
                wert = float(text.replace(",", ".")) if text and text != tr("auto") else None
            except ValueError:
                wert = None
            if wert is not None and wert > 0:
                w["toleranz"] = wert
        if not w:
            self.werte.pop(erste, None)
        QtCore.QTimer.singleShot(0, self._fuelle)  # nicht waehrend des Editors neu aufbauen

    def zustand(self) -> dict:
        """Fuer das Projekt: Rollen, Gruppen und von Hand gesetzte Werte."""
        return {"rollen": dict(self.rollen), "gruppen": {e: list(f) for e, f in self.gruppen.items()},
                "werte": {e: dict(w) for e, w in self.werte.items()}, "bezuege": dict(self.bezuege_hand)}

    def setze_zustand(self, d: dict):
        """Aus zustand() oder dem alten Format (nur Rollen je Flaeche)."""
        if "rollen" not in d:
            d = {"rollen": d}
        zahl = lambda x: {int(k): v for k, v in (x or {}).items()}  # noqa: E731 - JSON-Schluessel sind Text
        self.rollen = zahl(d.get("rollen"))
        self.gruppen = {e: tuple(f) for e, f in zahl(d.get("gruppen")).items()}
        self.werte = zahl(d.get("werte"))
        self.bezuege_hand = zahl(d.get("bezuege"))
        self._fuelle()

    def _zeige(self):
        self.flaechen_zeigen.emit({f for i in self.tabelle.selectedIndexes()
                                   for f in self.flaechen(self.tabelle.item(i.row(), 0).data(
                                       QtCore.Qt.ItemDataRole.UserRole))})

    def _vorschau_planen(self):
        self.zonen_knopf.setEnabled(self.vorschau_knopf.isChecked())
        self._vorschau_uhr.start()

    def vorschau_daten(self) -> dict | None:
        """Was die Vorschau zeigt: Bezuege [(Buchstabe, Stelle, Flaechen)], offene Bewegungen
        (kern.bezug_vorschau), PMI-Vorschlaege und ob die Zonen dazukommen; None ohne Vorschau."""
        from ..kern import bezug_vorschau as bv
        if not (self.vorschau_knopf.isChecked() and self.rollen and self.modell is not None and self.isVisible()):
            return None
        s = self.bezugssystem()
        v = bv.vorschau(self.modell, s, self.gruppen)
        self._zeige_bezug_text(s, v)
        return {"bezuege": [(b.buchstabe, "ABC".index(b.buchstabe) + 1, set(self.flaechen(b.flaeche)))
                            for b in s.bezuege],
                "offen": v.offen, "vorschlaege": fu.tolerierung(self.modell, self.rollen, s, self.gruppen, self.werte),
                "zonen": self.zonen_knopf.isChecked()}

    def sende_vorschau(self):
        d = self.vorschau_daten()
        if d is not None or self._vorschau_an:
            self.vorschau.emit(d)
        self._vorschau_an = d is not None

    def hideEvent(self, ev):
        super().hideEvent(ev)
        if self._vorschau_an:  # Fenster zu: Vorschau weg
            self._vorschau_an = False
            self.vorschau.emit(None)

    def showEvent(self, ev):
        super().showEvent(ev)
        self._vorschau_planen()

    def _zeige_bezug_text(self, s: fu.Bezugssystem, v=None):
        zeilen = [f"<b>{b.buchstabe}</b> ({tr('Ebene') if b.element == 'ebene' else tr('Achse')}, "
                  f"{tr('Fläche')} {' + '.join(str(x) for x in self.flaechen(b.flaeche))}"
                  + (f", {tr('sperrt {}').format(v.gesperrt.get(b.buchstabe, 0))}" if v is not None else "")
                  + f"): {html.escape(tr(b.grund))}" for b in s.bezuege]
        if v is not None and s.bezuege:
            offen = [(tr("Verschiebung entlang ({})") if o.art == "verschiebung" else tr("Drehung um ({})")).format(
                ", ".join(f"{x:.2g}" for x in o.richtung.round(3) + 0.0)) for o in v.offen]
            zeilen.append(tr("Offen: {}").format(", ".join(offen)) if offen else tr("Alle 6 Freiheitsgrade gesperrt"))
        else:
            zeilen += [html.escape(h) for h in s.hinweise]
        self.bezug_text.setText("<br>".join(zeilen))

    def bezugssystem(self) -> fu.Bezugssystem:
        return fu.bezugssystem(self.modell, self.rollen, self.gruppen,
                               {e: b for e, b in self.bezuege_hand.items() if e in self.rollen})

    def zeige_bezuege(self) -> fu.Bezugssystem:
        s = self.bezugssystem()
        self._zeige_bezug_text(s)
        self.flaechen_zeigen.emit({f for b in s.bezuege for f in self.flaechen(b.flaeche)})
        return s

    def vorschlaege(self) -> list:
        return fu.tolerierung(self.modell, self.rollen, self.zeige_bezuege(), self.gruppen, self.werte) \
            if self.rollen else []
