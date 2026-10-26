"""Seitenleisten: Baugruppenbaum, PMI-Liste, gespeicherte Ansichten."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..kern.pmi import BEZUG, HINWEIS, MASS, MATERIAL, TOLERANZ

ART_TEXT = {MASS: "Maß", TOLERANZ: "Toleranz", BEZUG: "Bezug", HINWEIS: "Hinweis"}


class BaumPanel(QtWidgets.QWidget):
    """Struktur mit Haken zum Ein-/Ausblenden; Kontextmenue: isolieren, transparent."""

    sichtbar_geaendert = QtCore.Signal(set, bool)  # Blatt-Nummern, sichtbar
    isolieren = QtCore.Signal(object)  # set oder None (alle zeigen)
    transparent = QtCore.Signal(set, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.suche = QtWidgets.QLineEdit()
        self.suche.setPlaceholderText(tr("Teil suchen"))
        self.suche.setClearButtonEnabled(True)
        self.suche.textChanged.connect(self._filtern)
        lay.addWidget(self.suche)
        self.baum = QtWidgets.QTreeWidget()
        self.baum.setHeaderHidden(True)
        self.baum.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.baum.customContextMenuRequested.connect(self._menue)
        self.baum.itemChanged.connect(self._haken)
        lay.addWidget(self.baum)
        self._transparent: set[int] = set()

    def zeige(self, wurzel):
        self.baum.blockSignals(True)
        self.baum.clear()
        self._transparent = set()
        if wurzel is not None:
            self.baum.addTopLevelItem(self._eintrag(wurzel))
            self.baum.expandToDepth(1)
        self.baum.blockSignals(False)

    def _eintrag(self, k):
        it = QtWidgets.QTreeWidgetItem([k.name + (tr(" (Hilfsgeometrie)") if k.hilfsgeometrie else "")])
        it.setData(0, QtCore.Qt.ItemDataRole.UserRole, k)
        flags = it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
        it.setFlags(flags)
        it.setCheckState(0, QtCore.Qt.CheckState.Unchecked if k.hilfsgeometrie else QtCore.Qt.CheckState.Checked)
        for kind in k.kinder:
            it.addChild(self._eintrag(kind))
        return it

    @staticmethod
    def blaetter(it) -> set[int]:
        k = it.data(0, QtCore.Qt.ItemDataRole.UserRole)
        return {b.nummer for b in k.blaetter() if not b.hilfsgeometrie}

    def _haken(self, it, _spalte):
        an = it.checkState(0) == QtCore.Qt.CheckState.Checked
        self.baum.blockSignals(True)
        _setze_kinder(it, it.checkState(0))
        self.baum.blockSignals(False)
        self.sichtbar_geaendert.emit(self.blaetter(it), an)

    def gewaehlte_blaetter(self) -> set[int]:
        out = set()
        for it in self.baum.selectedItems():
            out |= self.blaetter(it)
        return out

    def _menue(self, pos):
        it = self.baum.itemAt(pos)
        m = QtWidgets.QMenu(self)
        a_iso = m.addAction(tr("Isolieren"))
        a_alle = m.addAction(tr("Alle zeigen"))
        a_tr = m.addAction(tr("Transparent ein/aus"))
        a_iso.setEnabled(it is not None)
        a_tr.setEnabled(it is not None)
        gewaehlt = m.exec(self.baum.viewport().mapToGlobal(pos))
        if gewaehlt is a_iso:
            self.isolieren.emit(self.blaetter(it))
        elif gewaehlt is a_alle:
            self.alle_zeigen()
        elif gewaehlt is a_tr:
            self.schalte_transparent(self.blaetter(it))

    def schalte_transparent(self, nummern: set[int]):
        an = not nummern <= self._transparent
        self._transparent = (self._transparent | nummern) if an else (self._transparent - nummern)
        self.transparent.emit(nummern, an)

    def _filtern(self):
        """Nur Eintraege zeigen, deren Name den Suchtext enthaelt (mit ihren uebergeordneten Baugruppen)."""
        s = self.suche.text().strip().lower()

        def pruefe(it) -> bool:
            treffer = not s or s in it.text(0).lower()
            kinder = [pruefe(it.child(i)) for i in range(it.childCount())]
            sichtbar = treffer or any(kinder)
            it.setHidden(not sichtbar)
            if s and any(kinder):
                it.setExpanded(True)
            return sichtbar

        for i in range(self.baum.topLevelItemCount()):
            pruefe(self.baum.topLevelItem(i))

    def setze_sichtbar(self, nummern: set[int], sichtbar: bool):
        """Teile ein-/ausblenden und die Haken im Baum mitfuehren."""
        zustand = QtCore.Qt.CheckState.Checked if sichtbar else QtCore.Qt.CheckState.Unchecked

        def gehe(it):
            k = it.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if k is not None and not k.kinder and k.nummer in nummern:
                it.setCheckState(0, zustand)
            for i in range(it.childCount()):
                gehe(it.child(i))

        self.baum.blockSignals(True)
        for i in range(self.baum.topLevelItemCount()):
            gehe(self.baum.topLevelItem(i))
        self.baum.blockSignals(False)
        self.sichtbar_geaendert.emit(set(nummern), sichtbar)

    def alle_zeigen(self):
        self.baum.blockSignals(True)
        for i in range(self.baum.topLevelItemCount()):
            _setze_kinder(self.baum.topLevelItem(i), QtCore.Qt.CheckState.Checked, hilfe_auslassen=True)
        self.baum.blockSignals(False)
        self.isolieren.emit(None)


def _setze_kinder(it, zustand, hilfe_auslassen=False):
    k = it.data(0, QtCore.Qt.ItemDataRole.UserRole)
    if not (hilfe_auslassen and k is not None and k.hilfsgeometrie):
        it.setCheckState(0, zustand)
    for i in range(it.childCount()):
        _setze_kinder(it.child(i), zustand, hilfe_auslassen)


class PmiPanel(QtWidgets.QWidget):
    """Tabelle aller PMI mit Artfilter, Suche (Wert, Bezug, Name, Ansicht) und Kontextmenue."""

    gewaehlt = QtCore.Signal(list)  # Liste von Pmi
    filter_geaendert = QtCore.Signal(object)  # STEP-#IDs der gefilterten PMI oder None (kein Art-/Suchfilter)
    befehl = QtCore.Signal(str, object)  # Kontextmenue: ("zoomen"|"ausrichten"|"ansicht", Wert)

    SPALTEN = ("Nr", "Ballon", "Art", "Merkmal", "Name", "Wert", "Bezüge", "Ansichten", "Flächen", "Nennmaß",
               "Oberes Abmaß", "Unteres Abmaß", "Höchstmaß", "Mindestmaß", "Maßtoleranz", "Toleranzklasse",
               "Toleranzwert", "Toleranzzone", "Materialbedingung", "Modifikatoren", "Semantisch")
    STANDARD = {"Nr", "Art", "Merkmal", "Name", "Wert", "Bezüge", "Ansichten", "Flächen"}  # sichtbar ab Werk
    RECHTS = {"Nr", "Ballon", "Flächen", "Nennmaß", "Oberes Abmaß", "Unteres Abmaß", "Höchstmaß", "Mindestmaß",
              "Maßtoleranz", "Toleranzwert"}

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        oben = QtWidgets.QHBoxLayout()
        self.art = QtWidgets.QComboBox()
        for text, art in ((tr("Alle Arten"), None), (tr("Maße"), MASS), (tr("Toleranzen"), TOLERANZ),
                          (tr("Bezüge"), BEZUG), (tr("Hinweise"), HINWEIS)):
            self.art.addItem(text, art)
        self.suche = QtWidgets.QLineEdit()
        self.suche.setPlaceholderText(tr("Suchen: Text oder bezug:A, wert:0.5, typ:position, ansicht:MBD_A"))
        self.suche.setToolTip(tr("Freier Text sucht überall. Gezielt: bezug:A, wert:0.5, typ:position (Merkmal), "
                                 "art:toleranz, ansicht:MBD_A, name:…, nr:12, ballon:3 – mehrere Begriffe = alle"))
        self.suche.setClearButtonEnabled(True)
        oben.addWidget(self.art)
        oben.addWidget(self.suche, 1)
        lay.addLayout(oben)
        self.hinweis = QtWidgets.QLabel("")
        self.hinweis.setObjectName("leise")
        lay.addWidget(self.hinweis)
        self.tabelle = QtWidgets.QTableWidget(0, len(self.SPALTEN))
        self.tabelle.setHorizontalHeaderLabels([tr(s) for s in self.SPALTEN])
        for i, name in enumerate(self.SPALTEN):
            self.tabelle.horizontalHeaderItem(i).setData(QtCore.Qt.ItemDataRole.UserRole, name)
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setAlternatingRowColors(True)
        self.tabelle.setWordWrap(False)
        self.tabelle.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._menue)
        kopf = self.tabelle.horizontalHeader()
        for i, name in enumerate(self.SPALTEN):
            kopf.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.Stretch if name == "Wert"
                                      else QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            kopf.setSectionHidden(i, name not in self.STANDARD)
        lay.addWidget(self.tabelle, 1)
        self.pmi: list = []
        self.norm_text = ""  # z. B. "ASME Y14.5 (erkannt)", Anzeige neben der Anzahl
        self.merkmale: list = []
        self.ballon: dict[int, int] = {}  # PMI-Nummer -> Ballonnummer
        self.ansichten_je_pmi: dict[int, list[str]] = {}
        self.ansichten: list = []
        self.nur_nummern: set[int] | None = None
        self.art.currentIndexChanged.connect(self._filtern)
        self.suche.textChanged.connect(self._filtern)
        self.tabelle.itemSelectionChanged.connect(self._auswahl)

    def zeige(self, pmi: list, ansichten: list | None = None):
        from ..kern import merkmale
        self.pmi = pmi
        self.merkmale = merkmale.liste(pmi)
        self.ballon = merkmale.ballon_je_pmi(self.merkmale)
        self.ansichten = list(ansichten or [])
        self.ansichten_je_pmi = {}
        for a in self.ansichten:
            for nr in a.pmi_nummern:
                self.ansichten_je_pmi.setdefault(nr, []).append(a.name)
        self.nur_nummern = None
        t = self.tabelle
        t.blockSignals(True)
        t.setRowCount(len(pmi))
        for z, p in enumerate(pmi):
            namen = self.ansichten_je_pmi.get(p.nummer, [])
            werte = self._werte(p, namen, self.ballon)
            for s, spalte in enumerate(self.SPALTEN):
                it = QtWidgets.QTableWidgetItem(werte.get(spalte, ""))
                if spalte in self.RECHTS:
                    it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if spalte == "Wert":
                    it.setToolTip(_tooltip(p))
                if spalte == "Ansichten" and namen:
                    it.setToolTip(tr("In Ansichten: {}").format(", ".join(namen)))
                t.setItem(z, s, it)
        t.blockSignals(False)
        self._filtern()

    @staticmethod
    def _werte(p, namen, ballon: dict | None = None) -> dict[str, str]:
        ballon = ballon or {}
        hoechst, mindest = p.grenzen()
        oben, unten = p.abmasse()
        return {"Nr": str(p.nummer), "Ballon": str(ballon.get(p.nummer, "")), "Art": tr(ART_TEXT.get(p.art, p.art)), "Merkmal": tr(p.merkmal()),
                "Name": p.name, "Wert": p.wert_text(), "Bezüge": p.bezug_text(), "Ansichten": ", ".join(namen),
                "Flächen": str(len(p.flaechen)), "Nennmaß": _z(p.nennwert if p.art == MASS else None),
                "Oberes Abmaß": _z(oben, True), "Unteres Abmaß": _z(unten, True), "Höchstmaß": _z(hoechst),
                "Mindestmaß": _z(mindest), "Maßtoleranz": _z(p.masstoleranz()), "Toleranzklasse": p.passung,
                "Toleranzwert": _z(p.wert if p.art == TOLERANZ else None), "Toleranzzone": p.zonen_text(),
                "Materialbedingung": tr(MATERIAL[p.material]) if p.material in MATERIAL else "",
                "Modifikatoren": ", ".join(p.modifikatoren),
                "Semantisch": tr("ja") if p.semantisch else tr("nein")}

    def setze_ansichten(self, ansichten: list):
        """Ansichten neu zuordnen (z. B. nach eigener Ansicht), ohne Filter und Auswahl zu verlieren."""
        self.ansichten = list(ansichten)
        self.ansichten_je_pmi = {}
        for a in self.ansichten:
            for nr in a.pmi_nummern:
                self.ansichten_je_pmi.setdefault(nr, []).append(a.name)
        spalte = self.SPALTEN.index("Ansichten")
        for z, p in enumerate(self.pmi):
            it = self.tabelle.item(z, spalte)
            if it is not None:
                it.setText(", ".join(self.ansichten_je_pmi.get(p.nummer, [])))

    def nur_ansicht(self, nummern: set[int] | None):
        self.nur_nummern = None if nummern is None else set(nummern)
        self._filtern()

    def _passt(self, p) -> bool:
        art = self.art.currentData()
        if art is not None and p.art != art:
            return False
        if self.nur_nummern is not None and p.nummer not in self.nur_nummern:
            return False
        s = self.suche.text().strip().lower()
        if s:
            return all(self._passt_teil(p, teil) for teil in s.split())
        return True

    # gezielte Suche: schluessel:wert (deutsch und englisch)
    FELDER = {"bezug": "bezug", "datum": "bezug", "wert": "wert", "value": "wert", "typ": "typ", "type": "typ",
              "merkmal": "typ", "art": "art", "kind": "art", "ansicht": "ansicht", "view": "ansicht",
              "name": "name", "nr": "nr", "no": "nr", "ballon": "ballon", "balloon": "ballon"}

    def _passt_teil(self, p, teil: str) -> bool:
        schluessel, _, wert = teil.partition(":")
        feld = self.FELDER.get(schluessel) if wert else None
        if feld is None:
            text = " ".join((p.wert_text(), p.bezug_text(), p.name, p.typ, tr(ART_TEXT.get(p.art, "")), tr(p.merkmal()),
                             " ".join(self.ansichten_je_pmi.get(p.nummer, [])), " ".join(p.modifikatoren))).lower()
            return teil in text
        if feld == "bezug":
            namen = {n.lower() for b in p.bezuege for n in b.name.split("-")}
            return wert in namen or (p.art == BEZUG and p.name.lower() == wert)
        if feld == "wert":
            zahlen = [x for x in (p.nennwert, p.wert, p.oben, p.unten) if x is not None]
            try:
                ziel = float(wert.replace(",", "."))
            except ValueError:
                return wert in p.wert_text().lower()
            return any(abs(abs(x) - ziel) < 1e-9 for x in zahlen)
        if feld == "typ":
            return wert in p.typ.lower() or wert in tr(p.merkmal()).lower() or wert in p.merkmal().lower()
        if feld == "art":
            return wert in p.art or wert in tr(ART_TEXT.get(p.art, "")).lower()
        if feld == "ansicht":
            return any(wert in a.lower() for a in self.ansichten_je_pmi.get(p.nummer, []))
        if feld == "name":
            return wert in p.name.lower()
        if feld == "nr":
            return wert == str(p.nummer)
        return wert == str(self.ballon.get(p.nummer, ""))

    def _filtern(self):
        sichtbar = 0
        for z, p in enumerate(self.pmi):
            zeigen = self._passt(p)
            self.tabelle.setRowHidden(z, not zeigen)
            sichtbar += zeigen
        text = tr("{} von {} PMI").format(sichtbar, len(self.pmi))
        self.hinweis.setText(f"{text}   ·   {self.norm_text}" if self.norm_text and self.pmi else text)
        aktiv = self.art.currentData() is not None or bool(self.suche.text().strip())
        self.filter_geaendert.emit({p.step_id for p in self.sichtbare() if p.step_id} if aktiv else None)

    def sichtbare(self) -> list:
        return [p for z, p in enumerate(self.pmi) if not self.tabelle.isRowHidden(z)]

    def gewaehlte(self) -> list:
        return [self.pmi[z] for z in sorted({i.row() for i in self.tabelle.selectedIndexes()})]

    def _auswahl(self):
        self.gewaehlt.emit(self.gewaehlte())

    def waehle(self, pred) -> int:
        """Zeilen waehlen, fuer die pred(pmi) gilt; gibt die Anzahl zurueck."""
        t = self.tabelle
        t.blockSignals(True)
        t.clearSelection()
        erste = None
        n = 0
        modus = QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows
        for z, p in enumerate(self.pmi):
            if pred(p):
                if t.isRowHidden(z):
                    t.setRowHidden(z, False)
                t.selectionModel().select(t.model().index(z, 0), modus)
                erste = z if erste is None else erste
                n += 1
        t.blockSignals(False)
        if erste is not None:
            t.scrollToItem(t.item(erste, 0))
        self._auswahl()
        return n

    # --- Bezuege ---

    def waehle_bezuege(self, auswahl: list) -> int:
        """Bezuege der gewaehlten Toleranzen waehlen (Gruppen wie E-F-G einzeln)."""
        namen = set()
        for p in auswahl:
            for b in p.bezuege:
                namen |= set(b.name.split("-"))
        return self.waehle(lambda q: q.art == BEZUG and q.typ == "Datum" and q.name in namen)

    def waehle_mit_bezug(self, auswahl: list) -> int:
        """Alle Toleranzen, die einen der gewaehlten Bezuege verwenden."""
        namen = {p.name for p in auswahl if p.art == BEZUG}
        return self.waehle(lambda q: q.art == TOLERANZ and any(set(b.name.split("-")) & namen for b in q.bezuege))

    # --- Kontextmenue ---

    def _menue(self, pos):
        auswahl = self.gewaehlte()
        m = QtWidgets.QMenu(self)
        a_zoom = m.addAction(tr("Auf Auswahl zoomen"))
        a_normal = m.addAction(tr("Normal auf Auswahl ausrichten"))
        m.addSeparator()
        a_bez = m.addAction(tr("Bezüge dieser Toleranz wählen"))
        a_mit = m.addAction(tr("Toleranzen mit diesem Bezug wählen"))
        a_bez.setEnabled(any(p.bezuege for p in auswahl))
        a_mit.setEnabled(any(p.art == BEZUG for p in auswahl))
        m.addSeparator()
        menue_ansicht = m.addMenu(tr("In Ansicht zeigen"))
        namen = sorted({n for p in auswahl for n in self.ansichten_je_pmi.get(p.nummer, [])})
        for n in namen:
            menue_ansicht.addAction(n).setData(n)
        menue_ansicht.setEnabled(bool(namen))
        m.addSeparator()
        a_kopie = m.addAction(tr("Kopieren"))
        for a in (a_zoom, a_normal, a_kopie):
            a.setEnabled(bool(auswahl))
        gewaehlt = m.exec(self.tabelle.viewport().mapToGlobal(pos))
        if gewaehlt is None:
            return
        if gewaehlt is a_zoom:
            self.befehl.emit("zoomen", auswahl)
        elif gewaehlt is a_normal:
            self.befehl.emit("ausrichten", auswahl)
        elif gewaehlt is a_bez:
            self.waehle_bezuege(auswahl)
        elif gewaehlt is a_mit:
            self.waehle_mit_bezug(auswahl)
        elif gewaehlt is a_kopie:
            self.kopiere(auswahl)
        elif gewaehlt.data():
            self.befehl.emit("ansicht", gewaehlt.data())

    def kopiere(self, auswahl: list):
        zeilen = ["\t".join((str(p.nummer), tr(ART_TEXT.get(p.art, p.art)), p.name, p.wert_text(), p.bezug_text()))
                  for p in auswahl]
        QtWidgets.QApplication.clipboard().setText("\n".join(zeilen))


def _z(x, vorzeichen: bool = False) -> str:
    if x is None:
        return ""
    t = f"{x:.6f}".rstrip("0").rstrip(".")
    t = "0" if t in ("-0", "") else t
    return ("+" + t) if vorzeichen and x > 1e-12 else t


def _breite_nach_inhalt(tabelle, i: int, grenze: int = 320):
    """Neu eingeblendete Spalte auf Inhalt und Kopf verbreitern (begrenzt)."""
    tabelle.resizeColumnToContents(i)
    kopf = tabelle.horizontalHeader()
    kopf.resizeSection(i, min(max(kopf.sectionSize(i) + 8, kopf.sectionSizeHint(i)), grenze))


def spalten_menue(tabelle, pos, standard: set[str] | None = None, gespeichert=None):
    """Rechtsklick auf die Spaltenkoepfe: Spalten ein-/ausblenden (mindestens eine bleibt)."""
    kopf = tabelle.horizontalHeader()
    m = QtWidgets.QMenu(tabelle)
    for i in range(tabelle.columnCount()):
        a = m.addAction(tabelle.horizontalHeaderItem(i).text())
        a.setCheckable(True)
        a.setChecked(not kopf.isSectionHidden(i))
        a.setData(i)
    m.addSeparator()
    a_breite = m.addAction(tr("Breiten an Inhalt anpassen"))
    a_std = m.addAction(tr("Standardspalten")) if standard is not None else None
    gewaehlt = m.exec(kopf.mapToGlobal(pos))
    if gewaehlt is None:
        return
    if gewaehlt is a_breite:
        tabelle.resizeColumnsToContents()
        tabelle.setProperty("breiten_gemerkt", True)
    elif gewaehlt is a_std:
        for i in range(tabelle.columnCount()):
            war_aus = kopf.isSectionHidden(i)
            kopf.setSectionHidden(i, tabelle.horizontalHeaderItem(i).data(QtCore.Qt.ItemDataRole.UserRole)
                                  not in standard)
            if war_aus and not kopf.isSectionHidden(i):
                _breite_nach_inhalt(tabelle, i)
    else:
        i = gewaehlt.data()
        sichtbar = sum(not kopf.isSectionHidden(j) for j in range(tabelle.columnCount()))
        if gewaehlt.isChecked() or sichtbar > 1:
            kopf.setSectionHidden(i, not gewaehlt.isChecked())
        if gewaehlt.isChecked():
            _breite_nach_inhalt(tabelle, i)
    if gespeichert is not None:
        gespeichert()


def _tooltip(p) -> str:
    teile = [p.name or p.typ, tr("Typ: {}").format(p.typ)]
    if p.modifikatoren:
        teile.append(tr("Modifikatoren: {}").format(", ".join(p.modifikatoren)))
    teile.append(tr("Flächen: {}").format(len(p.flaechen)))
    if p.huelle_text():
        teile.append(tr(p.huelle_text()))
    abw = p.klassen_abmasse() if p.oben is None and p.unten is None else None
    if abw is not None:
        teile.append(tr("{}: Abmaße {:+.4g} / {:+.4g} mm nach ISO 286").format(p.passung, *abw))
    if not p.semantisch:
        teile.append(tr("nur grafisch (keine auswertbare Semantik)"))
    return "\n".join(teile)


class AnsichtenPanel(QtWidgets.QWidget):
    """Gespeicherte Ansichten des Modells (mit Suche nach Name)."""

    gewaehlt = QtCore.Signal(object)  # Ansicht oder None (alle PMI)
    merken = QtCore.Signal()  # aktuelle Kamera als eigene Ansicht
    entfernen = QtCore.Signal(object)  # eigene Ansicht loeschen

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.suche = QtWidgets.QLineEdit()
        self.suche.setPlaceholderText(tr("Ansicht suchen"))
        self.suche.setClearButtonEnabled(True)
        self.suche.textChanged.connect(self._filtern)
        lay.addWidget(self.suche)
        self.liste = QtWidgets.QListWidget()
        self.liste.setIconSize(QtCore.QSize(96, 64))
        lay.addWidget(self.liste)
        reihe = QtWidgets.QHBoxLayout()
        self.zurueck = QtWidgets.QPushButton("◀")
        self.zurueck.setToolTip(tr("Vorherige Ansicht (Bild auf, ←)"))
        self.vor = QtWidgets.QPushButton("▶")
        self.vor.setToolTip(tr("Nächste Ansicht (Bild ab, →)"))
        self.zurueck.clicked.connect(lambda: self.gehe(-1))
        self.vor.clicked.connect(lambda: self.gehe(+1))
        self.plus = QtWidgets.QPushButton(tr("＋ Merken"))
        self.plus.setToolTip(tr("Aktuelle Kamera, sichtbare PMI und Messungen als eigene Ansicht merken"))
        self.plus.clicked.connect(self.merken.emit)
        reihe.addWidget(self.zurueck)
        reihe.addWidget(self.vor)
        reihe.addWidget(self.plus)
        lay.addLayout(reihe)
        self.liste.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.liste.customContextMenuRequested.connect(self._menue)
        self.liste.itemChanged.connect(self._umbenannt)
        self.ansichten: list = []
        self.liste.currentRowChanged.connect(self._zeile)
        # erneuter Klick auf die aktuelle Ansicht stellt die Kamera wieder her
        self.liste.itemClicked.connect(lambda it: self._zeile(self.liste.row(it)))
        self.liste.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.liste and ev.type() == QtCore.QEvent.Type.KeyPress and \
                ev.key() in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right):
            self.gehe(+1 if ev.key() == QtCore.Qt.Key.Key_Right else -1)
            return True
        return super().eventFilter(obj, ev)

    def zeige(self, ansichten: list):
        self.ansichten = ansichten
        self.liste.blockSignals(True)
        self.liste.clear()
        self.liste.addItem(tr("(Keine Ansicht – alle PMI)"))
        for a in ansichten:
            n = len(a.pmi_nummern)
            it = QtWidgets.QListWidgetItem(f"{a.name}   ({tr('{} PMI').format(n)})" if not a.eigen else a.name)
            if a.eigen:
                it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
                it.setToolTip(tr("Eigene Ansicht – Doppelklick benennt um, Rechtsklick löscht"))
                schrift = it.font()
                schrift.setItalic(True)
                it.setFont(schrift)
            if n == 0 and not a.eigen:
                it.setForeground(QtGui.QBrush(self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText)))
            self.liste.addItem(it)
        self.liste.setCurrentRow(0)
        self.liste.blockSignals(False)

    def _menue(self, pos):
        it = self.liste.itemAt(pos)
        z = self.liste.row(it) if it is not None else -1
        if z <= 0 or not self.ansichten[z - 1].eigen:
            return
        m = QtWidgets.QMenu(self)
        a_name = m.addAction(tr("Umbenennen"))
        a_weg = m.addAction(tr("Löschen"))
        gewaehlt = m.exec(self.liste.viewport().mapToGlobal(pos))
        if gewaehlt is a_name:
            self.liste.editItem(it)
        elif gewaehlt is a_weg:
            self.entfernen.emit(self.ansichten[z - 1])

    def _umbenannt(self, it):
        z = self.liste.row(it)
        if 0 < z <= len(self.ansichten) and self.ansichten[z - 1].eigen and it.text().strip():
            self.ansichten[z - 1].name = it.text().strip()

    def _zeile(self, z):
        self.gewaehlt.emit(None if z <= 0 else self.ansichten[z - 1])

    def _filtern(self):
        s = self.suche.text().strip().lower()
        for z, a in enumerate(self.ansichten, 1):
            self.liste.item(z).setHidden(bool(s) and s not in a.name.lower())

    def gehe(self, schritt: int):
        """Naechste/vorherige sichtbare Ansicht in Listenreihenfolge (Durchklicken der Captures)."""
        kandidaten = [z for z in range(1, self.liste.count()) if not self.liste.item(z).isHidden()]
        if not kandidaten:
            return
        jetzt = self.liste.currentRow()
        if len(kandidaten) == 1 and jetzt == kandidaten[0]:
            self._zeile(jetzt)  # nur eine Ansicht: Kamera wiederherstellen
            return
        if schritt > 0:
            ziel = next((z for z in kandidaten if z > jetzt), kandidaten[0])
        else:
            ziel = next((z for z in reversed(kandidaten) if z < jetzt), kandidaten[-1])
        self.liste.setCurrentRow(ziel)
        self.liste.setFocus()  # danach weiter mit Pfeiltasten

    def setze_vorschau(self, i: int, svg: str):
        """Vorschaubild der Ansicht i (Index in self.ansichten)."""
        it = self.liste.item(i + 1)
        if it is not None:
            it.setIcon(svg_symbol(svg))

    def waehle_name(self, name: str):
        for z, a in enumerate(self.ansichten, 1):
            if a.name == name:
                self.liste.setCurrentRow(z)
                return


class VorschauLader(QtCore.QThread):
    """Vorschaubilder der gespeicherten Ansichten als Kantenzeichnung (HLR) im Hintergrund."""

    fertig = QtCore.Signal(int, str)  # Index der Ansicht, SVG

    def __init__(self, form, ansichten, grafik_je_ansicht, pmi_text, parent=None):
        super().__init__(parent)
        self.form, self.ansichten = form, list(ansichten)
        self.grafik_je_ansicht, self.pmi_text = grafik_je_ansicht, pmi_text
        self.abbrechen = False

    def run(self):
        from ..kern import zeichnung
        for i, a in enumerate(self.ansichten):
            if self.abbrechen:
                return
            try:
                z = zeichnung.projiziere(self.form, a.richtung, a.oben, a.name, verdeckt=False, abweichung=0.5)
                zeichnung.pmi_hinzu(z, self.grafik_je_ansicht[i], self.pmi_text, a.richtung, a.oben)
                self.fertig.emit(i, zeichnung.als_svg([z], a.name))
            except Exception:  # noqa: BLE001 - ohne Vorschau weiter
                continue


def svg_symbol(svg: str, breite: int = 96, hoehe: int = 64) -> QtGui.QIcon:
    from PySide6 import QtSvg
    r = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
    bild = QtGui.QPixmap(breite * 2, hoehe * 2)
    bild.setDevicePixelRatio(2.0)
    bild.fill(QtGui.QColor("white"))
    maler = QtGui.QPainter(bild)
    maler.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    g = r.defaultSize()
    if g.width() > 0 and g.height() > 0:
        k = min(breite / g.width(), hoehe / g.height())
        w, h = g.width() * k, g.height() * k
        r.render(maler, QtCore.QRectF((breite - w) / 2, (hoehe - h) / 2, w, h))
    maler.end()
    return QtGui.QIcon(bild)
