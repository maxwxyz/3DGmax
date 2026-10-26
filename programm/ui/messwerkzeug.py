"""Messwerkzeug: Art waehlen, Elemente im Modell anklicken, Ergebnisse als Liste und CSV."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..i18n import tr
from ..kern import messen

ART_TEXT = {"abstand": "Abstand", "winkel": "Winkel", "radius": "Radius / Ø", "wandstaerke": "Wandstärke",
            "koordinaten": "Koordinaten"}
HINWEIS = {
    "abstand": ("Erstes Element wählen (Punkt, Kante, Fläche)", "Zweites Element wählen"),
    "winkel": ("Erste Ebene, Achse oder Gerade wählen", "Zweite Ebene, Achse oder Gerade wählen"),
    "radius": ("Kreis, Bogen oder runde Fläche wählen",),
    "wandstaerke": ("Stelle auf einer Fläche wählen",),
    "koordinaten": ("Punkt wählen",),
}


def _woerter(text: str) -> str:
    """Elementnamen aus dem Rechenmodul uebersetzen (Ebene, Zylinder ...)."""
    import re
    return re.sub(r"[A-Za-zÄÖÜäöüß]+", lambda m: tr(m.group()) if m.group() in messen.WOERTER else m.group(), text)


class MessPanel(QtWidgets.QWidget):
    """Steuerung und Ergebnisliste. Die 3D-Ansicht meldet Klicks ueber element()."""

    messungen_geaendert = QtCore.Signal(list)
    modus_geaendert = QtCore.Signal(object)  # Art oder None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.modus: str | None = None
        self.auswahl: list = []  # [(form, punkt, fangart)]
        self.messungen: list[messen.Messung] = []
        self.koerper_von = lambda form: None  # vom Hauptfenster gesetzt
        self.toleranz = lambda: 1.0  # Fangweite in mm (abhaengig vom Zoom)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        reihe = QtWidgets.QGridLayout()
        self.knoepfe: dict[str, QtWidgets.QToolButton] = {}
        for i, art in enumerate(messen.ARTEN):
            k = QtWidgets.QToolButton()
            k.setText(tr(ART_TEXT[art]))
            k.setCheckable(True)
            k.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
            k.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            k.clicked.connect(lambda an, art=art: self.setze_modus(art if an else None))
            reihe.addWidget(k, i // 3, i % 3)
            self.knoepfe[art] = k
        lay.addLayout(reihe)
        self.fang = QtWidgets.QCheckBox(tr("Fangen an Endpunkt, Mitte, Kreismitte"))
        self.fang.setChecked(True)
        lay.addWidget(self.fang)
        self.hinweis = QtWidgets.QLabel(tr("Messart wählen, dann im Modell klicken"))
        self.hinweis.setObjectName("leise")
        self.hinweis.setWordWrap(True)
        lay.addWidget(self.hinweis)
        self.tabelle = QtWidgets.QTableWidget(0, 4)
        self.tabelle.setHorizontalHeaderLabels([tr("Nr"), tr("Art"), tr("Wert"), tr("Elemente")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tabelle, 1)
        unten = QtWidgets.QHBoxLayout()
        self.loeschen = QtWidgets.QPushButton(tr("Löschen"))
        self.alle_loeschen = QtWidgets.QPushButton(tr("Alle löschen"))
        self.csv = QtWidgets.QPushButton(tr("CSV speichern …"))
        self.kopieren = QtWidgets.QPushButton(tr("Kopieren"))
        for k in (self.loeschen, self.alle_loeschen, self.kopieren, self.csv):
            unten.addWidget(k)
        lay.addLayout(unten)
        self.loeschen.clicked.connect(self.loesche_gewaehlte)
        self.alle_loeschen.clicked.connect(self.loesche_alle)
        self.csv.clicked.connect(lambda: self.speichere_csv(""))
        self.kopieren.clicked.connect(self.kopiere)
        self.tabelle.itemSelectionChanged.connect(self._knoepfe_aktualisieren)
        self._knoepfe_aktualisieren()

    # --- Modus ---

    def setze_modus(self, art: str | None):
        self.modus = art
        self.auswahl = []
        for a, k in self.knoepfe.items():
            k.setChecked(a == art)
        self._zeige_hinweis()
        self.modus_geaendert.emit(art)

    def _zeige_hinweis(self, fehler: str = ""):
        if fehler:
            self.hinweis.setText(fehler)
        elif self.modus is None:
            self.hinweis.setText(tr("Messart wählen, dann im Modell klicken"))
        else:
            schritte = HINWEIS[self.modus]
            self.hinweis.setText(tr(schritte[min(len(self.auswahl), len(schritte) - 1)]))

    # --- Klick im Modell ---

    def element(self, form, punkt):
        """Gewaehltes Element mit Klickpunkt (x, y, z) aus der 3D-Ansicht."""
        if self.modus is None or form is None:
            return
        from OCC.Core.gp import gp_Pnt
        p = gp_Pnt(*punkt)
        fangart, p = messen.fange(form, p, self.toleranz()) if self.fang.isChecked() else ("", p)
        self.auswahl.append((form, p, fangart))
        if len(self.auswahl) < messen.ELEMENTE_NOETIG[self.modus]:
            self._zeige_hinweis()
            return
        try:
            m = self._rechne()
        except Exception as e:  # noqa: BLE001 - Grund dem Nutzer zeigen, Messung neu beginnen
            self.auswahl = []
            self._zeige_hinweis(tr("Nicht messbar: {}").format(tr(str(e))))
            return
        self.auswahl = []
        self.fuege_hinzu(m)
        self._zeige_hinweis()

    def _als_element(self, form, p, fangart):
        """Gefangener Punkt -> Vertex, sonst das Element selbst."""
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
        if fangart and not fangart.startswith("auf "):
            return BRepBuilderAPI_MakeVertex(p).Vertex()
        return form

    def _rechne(self) -> messen.Messung:
        art = self.modus
        if art == "abstand":
            (f1, p1, a1), (f2, p2, a2) = self.auswahl
            return messen.abstand(self._als_element(f1, p1, a1), self._als_element(f2, p2, a2))
        if art == "winkel":
            return messen.winkel(self.auswahl[0][0], self.auswahl[1][0])
        if art == "radius":
            return messen.radius(self.auswahl[0][0])
        if art == "wandstaerke":
            form, p, _ = self.auswahl[0]
            koerper = self.koerper_von(form)
            if koerper is None or form.ShapeType() != 4:  # 4 = TopAbs_FACE
                raise ValueError(tr("Fläche eines Körpers wählen"))
            return messen.wandstaerke(koerper, form, p)
        form, p, fangart = self.auswahl[0]
        return messen.koordinaten(p, fangart or messen.art_von(form))

    # --- Liste ---

    def fuege_hinzu(self, m: messen.Messung):
        m.nummer = (self.messungen[-1].nummer + 1) if self.messungen else 1
        self.messungen.append(m)
        self._fuelle()

    def _fuelle(self):
        t = self.tabelle
        t.setRowCount(len(self.messungen))
        for z, m in enumerate(self.messungen):
            for s, w in enumerate((str(m.nummer), tr(ART_TEXT[m.art]), _woerter(m.text()), _woerter(m.elemente))):
                t.setItem(z, s, QtWidgets.QTableWidgetItem(w))
        t.resizeColumnToContents(0)
        t.resizeColumnToContents(1)
        self._knoepfe_aktualisieren()
        self.messungen_geaendert.emit(list(self.messungen))

    def _knoepfe_aktualisieren(self):
        da = bool(self.messungen)
        self.alle_loeschen.setEnabled(da)
        self.csv.setEnabled(da)
        self.kopieren.setEnabled(da)
        self.loeschen.setEnabled(bool(self.tabelle.selectedIndexes()))

    def loesche_gewaehlte(self):
        zeilen = {i.row() for i in self.tabelle.selectedIndexes()}
        self.messungen = [m for z, m in enumerate(self.messungen) if z not in zeilen]
        self._fuelle()

    def loesche_alle(self):
        self.messungen = []
        self._fuelle()

    def speichere_csv(self, pfad: str = "") -> bool:
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Messungen speichern"), "messungen.csv",
                                                            "CSV (*.csv)")
            if not pfad:
                return False
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(messen.als_csv(self.messungen))
        return True

    def kopiere(self):
        QtWidgets.QApplication.clipboard().setText(messen.als_csv(self.messungen))
