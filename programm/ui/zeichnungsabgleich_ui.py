"""Blattbezogener Abgleich von Modell-PMI mit nativer und grafischer PDF-Beschriftung."""

from dataclasses import replace
import math
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .lader import Modellauftrag, Abbruch
from ..i18n import tr
from ..kern import zeichnungsabgleich as za
from ..kern.zeichnungsblatt import Zeichnungsblatt
from ..kern import zeichnungsansicht as ansichtsabgleich
from ..kern.pmi import MASS, BEZUG, TOLERANZ
from ..kern.vergleich_pmi import FELD_TEXT


class Ansichtsauftrag(Modellauftrag):
    def __init__(self, einzelteil, modellkreise, kreise, bereich, geometrie):
        super().__init__()
        self.einzelteil, self.modellkreise, self.kreise = einzelteil, modellkreise, kreise
        self.bereich, self.geometrie = bereich, geometrie
        self.schriftenden = []
        self.treffer, self.fehler = [], ""

    def _pruefe(self):
        if self.abgebrochen:
            raise Abbruch

    def run(self):
        try:
            if self.modellkreise is None:
                self.modellkreise = ansichtsabgleich.modellkreise(self.einzelteil, self._pruefe)
            self.treffer = ansichtsabgleich.zuordnen(self.kreise, self.modellkreise, self._pruefe, mit_gruppen=True)
            self.schriftenden = self.geometrie.schriftenden(self.kreise, self._pruefe)
        except Abbruch:
            pass
        except Exception as e:  # noqa: BLE001 - unlesbare Modellgeometrie im Dialog melden
            self.fehler = str(e)


class Blattansicht(QtWidgets.QGraphicsView):
    bereich = QtCore.Signal(tuple)
    gewaehlt = QtCore.Signal(object)
    kreis_gewaehlt = QtCore.Signal(object)
    musterkreis_gewaehlt = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(self.DragMode.RubberBandDrag)
        self.beginn = None
        self.auswaehlbar = None
        self.marken = []
        self.kreismarken = []

    def zeige(self, bild):
        self.scene().clear()
        self.kreismarken.clear()
        self.marken.clear()
        h, w = bild.shape[:2]
        im = QtGui.QImage(bild.data, w, h, bild.strides[0], QtGui.QImage.Format.Format_RGB888)
        hintergrund = self.scene().addPixmap(QtGui.QPixmap.fromImage(im))
        hintergrund.setTransformationMode(QtCore.Qt.TransformationMode.SmoothTransformation)
        self.setSceneRect(0, 0, w, h)
        self.einpassen()

    def einpassen(self):
        self.fitInView(self.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def markiere(self, angaben, aktiv, auswaehlbar=None):
        self.auswaehlbar = None if auswaehlbar is None else set(auswaehlbar)
        for _, item in self.marken:
            self.scene().removeItem(item)
        self.marken.clear()
        w, h = self.sceneRect().width(), self.sceneRect().height()
        for a in angaben:
            l, t, r, b = a.box
            stift = QtGui.QPen(QtGui.QColor("#cc5300" if a is aktiv else "#007a91"), 2 if a is aktiv else 1)
            stift.setCosmetic(True)
            item = self.scene().addRect(l*w, t*h, (r-l)*w, (b-t)*h, stift)
            self.marken.append((a, item))

    def zeige_kreise(self, kreise, ziel, muster=()):
        for _, item in self.kreismarken:
            self.scene().removeItem(item)
        self.kreismarken.clear()
        marken = set(muster)
        for k in dict.fromkeys((*kreise, *muster)):
            markiert = k == ziel or k in marken
            stift = QtGui.QPen(QtGui.QColor("#cc5300" if markiert else "#167748"), 2 if markiert else 1)
            stift.setCosmetic(True)
            if k.tauschgruppe:
                stift.setStyle(QtCore.Qt.PenStyle.DashLine)
            item = self.scene().addEllipse(k.x-k.r, k.y-k.r, 2*k.r, 2*k.r, stift)
            self.kreismarken.append((k, item))

    def wheelEvent(self, e):
        if e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            zoom = 1.25 if e.angleDelta().y() > 0 else .8
            if .05 < self.transform().m11() * zoom < 12:
                self.scale(zoom, zoom)
            e.accept()
        else:
            super().wheelEvent(e)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self.beginn = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self.beginn is None or e.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        ende = e.position().toPoint()
        start, self.beginn = self.beginn, None
        if (ende - start).manhattanLength() < 6:
            for a, item in reversed(self.marken):
                if (self.auswaehlbar is None or a in self.auswaehlbar) and item.rect().contains(self.mapToScene(ende)):
                    self.gewaehlt.emit(a)
                    return
            pos = self.mapToScene(ende)
            abstand = [(abs(math.hypot(k.x-pos.x(), k.y-pos.y()) - k.r), k) for k, _ in self.kreismarken]
            treffer = sorted(abstand, key=lambda t: t[0])
            skala = self.transform().m11()
            if (treffer and treffer[0][0]*skala < 5
                    and (len(treffer) == 1 or (treffer[1][0]-treffer[0][0])*skala > 1)):
                signal = self.musterkreis_gewaehlt if e.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier else self.kreis_gewaehlt
                signal.emit(treffer[0][1])
        else:
            box = QtCore.QRectF(self.mapToScene(start), self.mapToScene(ende)).normalized().intersected(self.sceneRect())
            w, h = self.sceneRect().width(), self.sceneRect().height()
            if box.width() > 1 and box.height() > 1:
                self.bereich.emit((box.left()/w, box.top()/h, box.right()/w, box.bottom()/h))


class Einzelmasse(QtWidgets.QWidget):
    """Je Blattkreis eine Entscheidung mit eigenem Modellbezug."""
    geaendert = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.ziele = []
        self.kandidaten = []
        self.bohrung = QtWidgets.QComboBox()
        self.mass = QtWidgets.QComboBox()
        reihe = QtWidgets.QHBoxLayout(self)
        reihe.setContentsMargins(0, 0, 0, 0)
        reihe.addWidget(self.bohrung)
        reihe.addWidget(self.mass, 1)
        self.bohrung.currentIndexChanged.connect(self._bohrung)
        self.mass.currentIndexChanged.connect(self._mass)
        self.hide()

    def setze(self, ziele, modelle, bestaetigt):
        self.ziele = list(ziele)
        self.kandidaten = [[] for _ in ziele]
        reserviert = {z.flaechen: z for z in bestaetigt}
        index = {f: i for i, z in enumerate(ziele) for f in z.flaechen}
        for m in modelle:
            if m.flaechen:
                i = index.get(next(iter(m.flaechen)))
                if i is not None and m.flaechen <= ziele[i].flaechen:
                    self.kandidaten[i].append(m)
        with QtCore.QSignalBlocker(self.bohrung):
            self.bohrung.clear()
            for i, (z, auswahl) in enumerate(zip(ziele, self.kandidaten)):
                alt = reserviert.get(z.flaechen)
                if alt is not None:
                    m = next((m for m in auswahl if m is alt.modell), None)
                    self.ziele[i] = replace(z, modell=m, nur_zeichnung=alt.nur_zeichnung)
                elif len(auswahl) == 1:
                    self.ziele[i] = replace(z, modell=auswahl[0])
                self.bohrung.addItem(tr("Bohrung {} von {}").format(i+1, len(ziele)))
        self._bohrung(self.bohrung.currentIndex())

    def _bohrung(self, i):
        with QtCore.QSignalBlocker(self.mass):
            self.mass.clear()
            if i >= 0:
                z = self.ziele[i]
                self.mass.addItems([tr("Zuordnung offen"), tr("Nur in Zeichnung")])
                idx = int(z.nur_zeichnung)
                for j, m in enumerate(self.kandidaten[i], start=2):
                    self.mass.addItem(f"#{m.nummer}  {m.wert_text()}")
                    if m is z.modell:
                        idx = j
                self.mass.setCurrentIndex(idx)
        self.geaendert.emit()

    def _mass(self, idx):
        i = self.bohrung.currentIndex()
        if i >= 0:
            m = self.kandidaten[i][idx-2] if idx >= 2 else None
            self.ziele[i] = replace(self.ziele[i], modell=m, nur_zeichnung=idx == 1)
            self.geaendert.emit()


class Zeichnungsabgleich(QtWidgets.QDialog):
    def __init__(self, doc, modell_pmi, zeige_modell, quellen, parent=None, *, einzelteil=None):
        super().__init__(parent)
        self.doc, self.zeige_modell = doc, zeige_modell
        self.quellen = quellen
        self.blatt = self.aktiv = None
        self.seiten = {}
        self.entfernte_bereiche = {}
        self.auftrag = None
        self.einzelteil = einzelteil
        self.modellkreise = self.blattgeometrie = None
        self.kreise = {}
        self.sichtkreise = {}
        self.bereiche = {}
        self.musterwahl = {}
        self.geometrien = {}
        self.zielvorschlaege = {}
        self.nur_modell = set()
        self.setWindowTitle(tr("Modell-PMI mit Zeichnung vergleichen"))
        self.resize(1150, 740)
        layout = QtWidgets.QVBoxLayout(self)
        oben = QtWidgets.QHBoxLayout()
        layout.addLayout(oben)
        oben.addWidget(QtWidgets.QLabel(tr("Blatt")))
        self.seite = QtWidgets.QSpinBox()
        self.seite.setRange(1, len(doc))
        self.seite.setSuffix(f" / {len(doc)}")
        oben.addWidget(self.seite)
        fit = QtWidgets.QPushButton(tr("Blatt einpassen"))
        oben.addWidget(fit)
        self.registrieren = QtWidgets.QPushButton(tr("Bohrbild zuordnen"))
        self.registrieren.setCheckable(True)
        self.registrieren.setEnabled(einzelteil is not None)
        self.registrieren.setToolTip(tr("Ein Bohrbild in Achsrichtung einrahmen. Mindestens drei Mittelpunkte müssen ein Dreieck bilden."))
        oben.addWidget(self.registrieren)
        oben.addStretch()
        oben.addWidget(QtWidgets.QLabel(tr("Zeichnungseinheit")))
        self.einheit = QtWidgets.QComboBox()
        for name, faktor in [(tr("Bitte wählen"), None), ("mm", 1.), (tr("Zoll"), 25.4)]:
            self.einheit.addItem(name, faktor)
        oben.addWidget(self.einheit)
        split = QtWidgets.QSplitter()
        layout.addWidget(split, 1)
        self.ansicht = Blattansicht()
        split.addWidget(self.ansicht)
        rechts = QtWidgets.QWidget()
        panel = QtWidgets.QVBoxLayout(rechts)
        split.addWidget(rechts)
        split.setSizes([690, 440])
        info = QtWidgets.QLabel(tr("Markierung anklicken oder ein Rechteck um eine Angabe ziehen. "
                                   "Mit Strg und Mausrad zoomen. Zuordnung anhand der Ansicht und Hinweislinie prüfen."))
        info.setWordWrap(True)
        panel.addWidget(info)
        self.tabelle = QtWidgets.QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels([tr("Blatt"), tr("Angabe"), tr("Befund")])
        self.tabelle.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tabelle.verticalHeader().hide()
        self.tabelle.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        panel.addWidget(self.tabelle, 1)
        self.ausschnitt = QtWidgets.QLabel()
        self.ausschnitt.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        panel.addWidget(self.ausschnitt)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setPlaceholderText(tr("Beschriftung der Zeichnung"))
        self.text.setMaximumHeight(56)
        panel.addWidget(self.text)
        self.grundmass = QtWidgets.QCheckBox(tr("Eingerahmtes theoretisch genaues Maß"))
        panel.addWidget(self.grundmass)
        self.zuordnung = QtWidgets.QComboBox()
        panel.addWidget(self.zuordnung)
        self.einzel = Einzelmasse()
        panel.addWidget(self.einzel)
        self.detail = QtWidgets.QLabel()
        self.detail.setWordWrap(True)
        panel.addWidget(self.detail)
        reihe = QtWidgets.QHBoxLayout()
        panel.addLayout(reihe)
        self.bestaetigen = QtWidgets.QPushButton(tr("Prüfung übernehmen"))
        self.entfernen = QtWidgets.QPushButton(tr("Fundstelle entfernen"))
        for btn in [self.bestaetigen, self.entfernen]:
            reihe.addWidget(btn)
        self.status = QtWidgets.QLabel()
        layout.addWidget(self.status)
        ende = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        export = ende.addButton(tr("Prüfliste als CSV …"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        export.clicked.connect(self._export)
        layout.addWidget(ende)
        ende.rejected.connect(self.close)
        self.seite.valueChanged.connect(lambda n: self.blatt_zeigen(n-1))
        self.einheit.currentIndexChanged.connect(self._einheit_geaendert)
        fit.clicked.connect(self.ansicht.einpassen)
        self.registrieren.toggled.connect(self._status)
        self.finished.connect(self._abbrechen)
        self.ansicht.bereich.connect(self._bereich)
        self.ansicht.kreis_gewaehlt.connect(self._kreis_waehlen)
        self.ansicht.musterkreis_gewaehlt.connect(self._musterkreis_waehlen)
        self.ansicht.gewaehlt.connect(self.waehle)
        self.tabelle.currentCellChanged.connect(self._auswahl)
        self.zuordnung.currentIndexChanged.connect(self._vorschau)
        self.einzel.geaendert.connect(self._vorschau)
        self.zuordnung.activated.connect(self._manuelle_wahl)
        self.text.textChanged.connect(self._vorschau)
        self.grundmass.toggled.connect(self._vorschau)
        self.bestaetigen.clicked.connect(self.uebernehmen)
        self.entfernen.clicked.connect(self._entferne)
        self.setze_modell(modell_pmi)
        self.blatt_zeigen(0)

    def setze_modell(self, pmi):
        vorher = getattr(self, "modellindex", {})
        self.modell = [p for p in pmi if p.semantisch and p.art in (MASS, BEZUG, TOLERANZ)]
        self.modellindex = {id(p): i for i, p in enumerate(self.modell)}
        self.nur_modell.intersection_update(self.modellindex)
        for angaben in self.seiten.values():
            for a in angaben:
                if a.einzelpruefung:
                    neu = [m for m in self.modell if id(m) not in vorher and m.typ == "Size_Diameter" and m.flaechen]
                    a.musterziele = tuple(replace(z, modell=None, nur_zeichnung=False)
                                          if (z.modell is not None and id(z.modell) not in self.modellindex)
                                          or (z.nur_zeichnung and any(m.flaechen <= z.flaechen for m in neu))
                                          else z for z in a.musterziele)
                if a.modell is not None and id(a.modell) not in self.modellindex:
                    a.modell = None
                    a.blattziel = None
                    a.musterziele = ()
        if self.blatt is not None:
            self._liste(self.aktiv)

    def showEvent(self, e):
        super().showEvent(e)
        self.ansicht.einpassen()

    def blatt_zeigen(self, nr):
        from pypdfium2 import PdfiumError
        try:
            neu = Zeichnungsblatt(self.doc, nr)
            if nr not in self.seiten:
                self.seiten[nr] = neu.fundstellen()
        except (PdfiumError, ValueError, OSError) as e:
            if self.blatt is None:
                raise
            with QtCore.QSignalBlocker(self.seite):
                self.seite.setValue(self.blatt.nummer + 1)
            QtWidgets.QMessageBox.warning(self, tr("2D-Zeichnung öffnen"), str(e))
            return
        self._abbrechen()
        if self.blatt is not None:
            self.blatt.schliesse()
        self.blatt = neu
        self.blattgeometrie = self.geometrien.get(nr)
        self.registrieren.setChecked(False)
        self.ansicht.zeige(neu.bild)
        self._liste()

    def _liste(self, wahl=None):
        self.zeilen = list(self.seiten[self.blatt.nummer])
        zugeordnet = {id(m) for angaben in self.seiten.values() for a in angaben for m in a.zugeordnete_pmi()}
        self.zeilen.extend(p for p in self.modell if id(p) not in zugeordnet)
        befunde = self._befunde()
        with QtCore.QSignalBlocker(self.tabelle):
            self.tabelle.clearContents()
            self.tabelle.setRowCount(len(self.zeilen))
            self.tabelle.setCurrentCell(-1, -1)
            for i, a in enumerate(self.zeilen):
                if isinstance(a, za.Blattangabe):
                    daten = (str(a.seite+1), a.text or "?", befunde[za.befund(a, self.einheit.currentData())])
                else:
                    daten = ("–", f"#{a.nummer}  {a.wert_text()}",
                             tr("Nur im Modell") if id(a) in self.nur_modell else tr("Modell-PMI offen"))
                for j, wort in enumerate(daten):
                    self.tabelle.setItem(i, j, QtWidgets.QTableWidgetItem(wort))
        self.tabelle.resizeColumnToContents(0)
        self.tabelle.resizeColumnToContents(2)
        self._status()
        self.waehle(wahl if wahl is not None else next(iter(self.zeilen), None))

    def _status(self):
        if self.registrieren.isChecked():
            self.status.setText(tr("Ein Rechteck um das Bohrbild einer einzelnen Zeichnungsansicht ziehen."))
        elif self.auftrag is not None:
            self.status.setText(tr("Bohrbild wird mit dem Modell verglichen …"))
        elif self.blatt is not None and self.kreise.get(self.blatt.nummer) == []:
            self.status.setText(tr("Keine eindeutige Zuordnung. Eine Ansicht entlang der Bohrungsachsen mit weiteren Kreisen einrahmen."))
        elif self.blatt is not None and any(k.tauschgruppe for k in self.kreise.get(self.blatt.nummer, [])):
            self.status.setText(tr("Gestrichelte Kreise sind nur als vollständige Gruppe zuordenbar."))
        elif self.blatt is not None and self.blatt.nummer in self.kreise:
            self.status.setText(tr("{} Kreise zugeordnet. Eine Angabe wählen und den Kreis am Hinweisziel anklicken.")
                                .format(len(self.kreise[self.blatt.nummer])))
        else:
            self.status.setText(tr("{} von {} Blättern geöffnet. Die Befunde gelten für einzeln geprüfte Angaben.")
                                .format(len(self.seiten), len(self.doc)))

    def _bereich(self, box):
        if not self.registrieren.isChecked():
            return self._neue_angabe(box)
        self.registrieren.setChecked(False)
        from pypdfium2 import PdfiumError
        self._abbrechen()
        try:
            if self.blattgeometrie is None:
                self.blattgeometrie = ansichtsabgleich.Blattgeometrie(self.blatt)
                self.geometrien[self.blatt.nummer] = self.blattgeometrie
        except (PdfiumError, ValueError, OSError) as e:
            QtWidgets.QMessageBox.warning(self, tr("Bohrbild zuordnen"), str(e))
            return
        kreise = self.blattgeometrie.im_bereich(box)
        self.auftrag = Ansichtsauftrag(self.einzelteil, self.modellkreise, kreise, box, self.blattgeometrie)
        self.auftrag.finished.connect(self._zugeordnet)
        self.auftrag.starte()
        self._status()

    def _abbrechen(self):
        if self.auftrag is not None:
            self.auftrag.abgebrochen = True
            self.auftrag = None

    def _ergaenze_masszeilen(self, schriftenden):
        nr = self.blatt.nummer
        angaben = self.seiten[nr]
        belegt = [a.box for a in angaben] + self.entfernte_bereiche.get(nr, [])
        belegt.extend(box for box, _ in self.blatt.textbereiche)
        neu = []
        for ort, sinn, achse in schriftenden:
            a = self.blatt.freie_masszeile(ort, sinn, achse, belegt)
            if a is not None:
                belegt.append(a.box)
                neu.append(a)
        with QtCore.QSignalBlocker(self.tabelle):
            for a in sorted(neu, key=lambda a: (a.box[1], a.box[0])):
                i = len(angaben)
                angaben.append(a)
                self.zeilen.insert(i, a)
                self.tabelle.insertRow(i)
                for j, wort in enumerate((str(nr+1), a.text, tr("Zu prüfen"))):
                    self.tabelle.setItem(i, j, QtWidgets.QTableWidgetItem(wort))
        return len(neu)

    @QtCore.Slot()
    def _zugeordnet(self):
        arbeit = self.sender()
        if arbeit is not self.auftrag:
            return
        self.auftrag = None
        if arbeit.fehler:
            self.status.setText(arbeit.fehler)
            return
        self.modellkreise = arbeit.modellkreise
        nr = self.blatt.nummer
        self.kreise[nr] = arbeit.treffer
        self.sichtkreise[nr] = arbeit.kreise
        self.bereiche[nr] = arbeit.bereich
        neu = self._ergaenze_masszeilen(arbeit.schriftenden)
        for a in self.seiten[nr]:
            self.musterwahl.pop(a, None)
            k = self._hinweisziel(a)
            self.zielvorschlaege[a] = k
            anzahl = za.musteranzahl(a.text)
            if anzahl and (a.modell is not None or a.einzelpruefung):
                ziele = self._muster(a, anzahl)
                if k or not self._anderer_bereich(a):
                    a.zielkonflikt = ((not a.einzelpruefung and not za.muster_deckt(anzahl, ziele, a.modell))
                                      or set(self._blattziele(ziele)) != {replace(z, modell=None, nur_zeichnung=False) for z in a.musterziele})
            elif k and a.modell is not None:
                a.zielkonflikt = not bool(k.flaechen & a.modell.flaechen)
            elif k and a.nur_zeichnung:
                p = za.lese_angabe(a.text, self.einheit.currentData(), a.grundmass)
                a.zielkonflikt = any(za.muster_deckt(anzahl, self._muster(a, anzahl), m) if anzahl else m.flaechen & k.flaechen
                                     for m in za.kandidaten(p, self.modell))
        for i, a in enumerate(self.seiten[nr]):
            self.tabelle.item(i, 2).setText(self._befunde()[za.befund(a, self.einheit.currentData())])
        if isinstance(self.aktiv, za.Blattangabe) and self.manuelle_wahl and self.zuordnung.currentData() != -2:
            muster = self._muster(self.aktiv, za.musteranzahl(self.text.toPlainText()))
            self.ansicht.zeige_kreise(arbeit.treffer, self.zielvorschlaege.get(self.aktiv), muster)
        else:
            self._auswahl(self.tabelle.currentRow(), entwurf=True)
        self._status()
        if neu:
            meldung = tr("Eine weitere Durchmesserangabe gefunden.") if neu == 1 else tr("{} weitere Durchmesserangaben gefunden.").format(neu)
            self.status.setText(f"{self.status.text()} {meldung}")

    def _hinweisziel(self, a):
        pruefe = self.blatt.durchmesseranfang if "|" in a.text else None
        kreise = self.kreise.get(a.seite, [])
        anzahl = za.musteranzahl(a.text)
        if anzahl > 1:
            gruppe = self.blattgeometrie.hinweisgruppe(a.box, kreise, anzahl)
            if gruppe:
                self.musterwahl[a] = gruppe
                return gruppe[0]
        return self.blattgeometrie.hinweisziel(a.box, kreise, pruefe, musterzeile=bool(anzahl) or a.text.lstrip().startswith(("⌀", "Ø", "∅")))

    def _anderer_bereich(self, a):
        if not a.blattziel or a.seite not in self.bereiche:
            return False
        x, y, _ = a.blattziel
        l, t, r, b = self.bereiche[a.seite]
        return not (l <= x <= r and t <= y <= b)

    def _muster(self, a, anzahl):
        if not anzahl:
            return ()
        if a in self.musterwahl:
            return self.musterwahl[a]
        anker = self.zielvorschlaege.get(a)
        if not anker and a.musterziele and self._anderer_bereich(a):
            h, w = self.blatt.bild.shape[:2]
            return tuple(ansichtsabgleich.Blattkreis(z.ort[0]*w, z.ort[1]*h, z.ort[2]*w, z.flaechen, z.tauschgruppe)
                         for z in a.musterziele)
        return ansichtsabgleich.muster_am_ziel(anker, anzahl,
                                               self.sichtkreise.get(a.seite, []), self.kreise.get(a.seite, []))

    def _blattziele(self, muster):
        h, w = self.blatt.bild.shape[:2]
        return tuple(za.Musterziel((q.x/w, q.y/h, q.r/w), q.flaechen, tauschgruppe=q.tauschgruppe) for q in muster)

    def _musterkreis_waehlen(self, k):
        a = self.aktiv
        anzahl = za.musteranzahl(self.text.toPlainText())
        if not isinstance(a, za.Blattangabe) or not anzahl or not self.zielvorschlaege.get(a):
            return self._kreis_waehlen(k)
        anker = self.zielvorschlaege[a]
        if k == anker or abs(k.r-anker.r) > .75:
            return
        auswahl = list(self._muster(a, anzahl))
        if k in auswahl:
            auswahl.remove(k)
        elif all(math.hypot(k.x-q.x, k.y-q.y) > 1.5 for q in auswahl):
            auswahl.append(k)
        self.musterwahl[a] = tuple(auswahl)
        self._auswahl(self.tabelle.currentRow(), neues_ziel=True)

    def _kreis_waehlen(self, k):
        if isinstance(self.aktiv, za.Blattangabe):
            self.musterwahl.pop(self.aktiv, None)
            self.zielvorschlaege[self.aktiv] = k
            self._auswahl(self.tabelle.currentRow(), neues_ziel=True)

    def waehle(self, objekt):
        i = next((i for i,a in enumerate(self.zeilen) if a is objekt), -1)
        if i >= 0:
            self.tabelle.setCurrentCell(i, 1)
        else:
            self._auswahl(-1)

    def _manuelle_wahl(self):
        self.manuelle_wahl = True

    def _auswahl(self, i, *_, neues_ziel=False, entwurf=False):
        alt = self.aktiv
        self.aktiv = a = self.zeilen[i] if i >= 0 else None
        zeichnung = isinstance(a, za.Blattangabe)
        self.manuelle_wahl = False
        behalten = zeichnung and (neues_ziel or entwurf)
        text = self.text.toPlainText() if behalten else a.text if zeichnung else ""
        grundmass = self.grundmass.isChecked() if behalten else zeichnung and a.grundmass
        self.ansicht.markiere(self.seiten[self.blatt.nummer], a)
        kreis = self.zielvorschlaege.get(a) if zeichnung else None
        anzahl = za.musteranzahl(text)
        muster = self._muster(a, anzahl)
        self.ansicht.zeige_kreise(self.kreise.get(self.blatt.nummer, []), kreis, muster)
        self.ausschnitt.clear()
        self.ausschnitt.setVisible(zeichnung)
        if zeichnung:
            l, t, r, b = a.box
            rand = .22 * (b-t)
            dx = rand * self.blatt.hoehe / self.blatt.breite
            box = (max(0, l-dx), max(0, t-rand), min(1, r+dx), min(1, b+rand))
            bild = self.blatt.ausschnitt(box, min(520, max(200, self.tabelle.width()-4)), 62)
            if bild is not None:
                try:
                    im = QtGui.QImage(bild.buffer, bild.width, bild.height, bild.stride, QtGui.QImage.Format.Format_RGB888)
                    self.ausschnitt.setPixmap(QtGui.QPixmap.fromImage(im))
                finally:
                    bild.close()
        with QtCore.QSignalBlocker(self.zuordnung), QtCore.QSignalBlocker(self.text), QtCore.QSignalBlocker(self.grundmass):
            self.text.setPlainText(text)
            self.grundmass.setChecked(grundmass)
            self.zuordnung.clear()
            if zeichnung:
                self.zuordnung.addItem(tr("Zuordnung offen"), None)
                self.zuordnung.addItem(tr("Nur in Zeichnung"), -1)
                p = za.lese_angabe(text, self.einheit.currentData(), grundmass)
                bevorzugt = za.kandidaten(p, self.modell)
                am_ziel = [m for m in bevorzugt if kreis and m.flaechen & kreis.flaechen]
                if anzahl:
                    am_ziel = [m for m in bevorzugt if za.muster_deckt(anzahl, muster, m)]
                einzelmodus = anzahl > 1 and len(muster) == anzahl and p is not None and all(k.flaechen for k in muster)
                if einzelmodus:
                    altziele = a.musterziele if a.einzelpruefung else ()
                    if alt is a and behalten and not self.einzel.isHidden():
                        altziele = self.einzel.ziele
                    with QtCore.QSignalBlocker(self.einzel):
                        self.einzel.setze(self._blattziele(muster), bevorzugt, altziele)
                    self.zuordnung.addItem(tr("Einzel-PMI je Bohrung"), -2)
                vorn = {id(m) for m in bevorzugt}
                ziel_ids = {id(m) for m in am_ziel}
                sortiert = sorted(bevorzugt, key=lambda m: id(m) not in ziel_ids)
                sortiert += [m for m in self.modell if id(m) not in vorn]
                moeglich = am_ziel if anzahl or self.blatt.nummer in self.kreise else [m for m in bevorzugt if not za.unterschiede(p, m)]
                vorschlag = None if neues_ziel or a.zielkonflikt else a.modell
                if vorschlag is None and (neues_ziel or a.zielkonflikt or not a.nur_zeichnung) and len(moeglich) == 1:
                    vorschlag = moeglich[0]
                ziel = 1 if a.nur_zeichnung and not neues_ziel and not a.zielkonflikt else 0
                if einzelmodus and not a.nur_zeichnung:
                    alle_einzeln = all(self.einzel.kandidaten)
                    if (a.einzelpruefung or (alt is a and behalten and not self.einzel.isHidden())
                            or (a.modell is None and not am_ziel and any(self.einzel.kandidaten))):
                        ziel, vorschlag = 2, None
                    elif a.modell is None and alle_einzeln and am_ziel:
                        vorschlag = None
                for m in sortiert:
                    self.zuordnung.addItem(f"#{m.nummer}  {m.wert_text()}", self.modellindex[id(m)])
                    if m is vorschlag:
                        ziel = self.zuordnung.count()-1
                self.zuordnung.setCurrentIndex(ziel)
            elif a is not None:
                self.zuordnung.addItems([tr("Vorkommen auf Zeichnung offen"), tr("Nur im Modell")])
                self.zuordnung.setCurrentIndex(int(id(a) in self.nur_modell))
        self.text.setEnabled(zeichnung)
        self.grundmass.setEnabled(zeichnung)
        self.entfernen.setEnabled(zeichnung)
        self.bestaetigen.setEnabled(a is not None)
        self._vorschau()

    def _vorschau(self):
        a = self.aktiv
        self.detail.clear()
        einzelmodus = isinstance(a, za.Blattangabe) and self.zuordnung.currentData() == -2
        vorher_einzeln = not self.einzel.isHidden()
        self.einzel.setVisible(einzelmodus)
        if a is None:
            return
        if not isinstance(a, za.Blattangabe):
            self.zeige_modell(a)
            return
        idx = self.zuordnung.currentData()
        m = self.modell[idx] if idx is not None and idx >= 0 else None
        p = za.lese_angabe(self.text.toPlainText(), self.einheit.currentData(), self.grundmass.isChecked())
        anzahl = za.musteranzahl(self.text.toPlainText())
        muster = self._muster(a, anzahl)
        if einzelmodus:
            if not anzahl or len(muster) != anzahl or len(self.einzel.ziele) != anzahl:
                self.zeige_modell(None)
                self.detail.setText(tr("{} von {} Bohrungen gewählt. Erste Bohrung anklicken, weitere mit Umschalt+Klick wählen.").format(len(muster), anzahl))
                return
            i = self.einzel.bohrung.currentIndex()
            if i >= 0 and i < len(muster):
                z = self.einzel.ziele[i]
                self.zeige_modell(z.modell)
                self.ansicht.zeige_kreise(self.kreise.get(a.seite, []), muster[i], (muster[i],))
                if z.modell is not None and p is not None:
                    self.detail.setText(self._wertdetails(p, z.modell))
                else:
                    self.detail.setText(self._befunde()[za.einzelbefund(p, z)])
            return
        self.zeige_modell(m)
        if vorher_einzeln:
            self.ansicht.zeige_kreise(self.kreise.get(a.seite, []), self.zielvorschlaege.get(a), muster)
        if anzahl and not muster and not self.kreise.get(a.seite):
            self.detail.setText(tr("Für dieses Bohrbild sind noch keine Modellflächen zugeordnet."))
        elif anzahl and len(muster) != anzahl:
            self.detail.setText(tr("{} von {} Bohrungen gewählt. Erste Bohrung anklicken, weitere mit Umschalt+Klick wählen.").format(len(muster), anzahl))
        elif anzahl and m is not None and not za.muster_deckt(anzahl, muster, m):
            self.detail.setText(tr("Die gewählte Modell-PMI deckt das markierte Bohrbild nicht vollständig und ausschließlich ab."))
        elif p is None:
            self.detail.setText(tr("Angabe oder Zeichnungseinheit ungeklärt"))
        elif not anzahl and (k := self.zielvorschlaege.get(a)) and k.tauschgruppe:
            self.detail.setText(tr("Diese Bohrung ist nur zusammen mit den übrigen Bohrungen eindeutig."))
        elif m is None and self.zielvorschlaege.get(a):
            self.detail.setText(tr("Hinweisziel gefunden. Die zugehörige Modell-PMI ist noch offen."))
        elif m is not None:
            k = self.zielvorschlaege.get(a)
            if k and not anzahl and not k.flaechen & m.flaechen:
                self.detail.setText(tr("Die gewählte Modell-PMI gehört zu einer anderen Fläche als das erkannte Hinweisziel."))
                return
            detail = self._wertdetails(p, m)
            if any(z.tauschgruppe for z in muster):
                detail = tr("Modellflächen als Bohrbild zugeordnet.") + " " + detail
            self.detail.setText(detail)

    @staticmethod
    def _wertdetails(p, m):
        if za.grenzen_vertauscht(m):
            return tr("Das Mindestmaß im Modell liegt über dem Höchstmaß.")
        felder = za.unterschiede(p, m)
        namen = dict(FELD_TEXT, typ=tr("Typ"), art=tr("Art"), minimum=tr("Mindestmaß"), maximum=tr("Höchstmaß"))
        if felder:
            return tr("Abweichende Felder: {}").format(", ".join(tr(namen[k]) for k in felder))
        return tr("Angegebene Werte stimmen überein.")

    def uebernehmen(self):
        a = self.aktiv
        if isinstance(a, za.Blattangabe):
            a.text, a.grundmass = self.text.toPlainText().strip(), self.grundmass.isChecked()
            idx = self.zuordnung.currentData()
            vorher = a.modell
            a.modell = self.modell[idx] if idx is not None and idx >= 0 else None
            a.nur_zeichnung = idx == -1
            k = self.zielvorschlaege.get(a)
            h, w = self.blatt.bild.shape[:2]
            anzahl = za.musteranzahl(a.text)
            muster = self._muster(a, anzahl)
            a.zielkonflikt = bool(k and not anzahl and a.modell and not k.flaechen & a.modell.flaechen)
            a.einzelpruefung = (idx == -2 and anzahl > 1 and len(muster) == anzahl
                                and [z.flaechen for z in self.einzel.ziele] == [k.flaechen for k in muster])
            a.musterziele = tuple(self.einzel.ziele) if a.einzelpruefung else self._blattziele(muster)
            self.nur_modell.difference_update(id(m) for m in a.zugeordnete_pmi())
            if k and (anzahl or (a.modell and k.flaechen & a.modell.flaechen)):
                a.blattziel = (k.x/w, k.y/h, k.r/w)
            elif not (anzahl and muster and self._anderer_bereich(a)):
                if a.modell is None or a.modell is not vorher or k or anzahl:
                    a.blattziel = None
        elif a is not None:
            if self.zuordnung.currentIndex() == 1:
                self.nur_modell.add(id(a))
            else:
                self.nur_modell.discard(id(a))
        self._liste(a)

    def _neue_angabe(self, box):
        a = za.Blattangabe(self.blatt.nummer, box, self.blatt.lies(box))
        self.seiten[a.seite].append(a)
        if self.blattgeometrie is not None:
            self.zielvorschlaege[a] = self._hinweisziel(a)
        self._liste(a)

    def _entferne(self):
        self.entfernte_bereiche.setdefault(self.aktiv.seite, []).append(self.aktiv.box)
        self.musterwahl.pop(self.aktiv, None)
        self.zielvorschlaege.pop(self.aktiv, None)
        self.seiten[self.blatt.nummer] = [a for a in self.seiten[self.blatt.nummer] if a is not self.aktiv]
        self._liste()

    def _einheit_geaendert(self):
        self._liste(self.aktiv)

    def _export(self):
        import csv
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Prüfliste speichern"), "", "CSV (*.csv)")
        if not pfad:
            return
        try:
            with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([tr("Zeichnungsdatei"), tr("Modelldatei"), tr("Blatt"),
                            tr("Blattbereich (links, oben, rechts, unten relativ)"), tr("Angabe"),
                            tr("Zeichnungseinheit"), tr("Befund"), tr("Modell-PMI"), tr("Modellwert"), tr("Flächen"),
                            tr("Eingerahmtes theoretisch genaues Maß"), tr("Quell-ID der Modell-PMI"),
                            tr("Hinweisziel (x/Breite, y/Höhe, Radius/Breite)"),
                            tr("Bohrbild (x/Breite, y/Höhe, Radius/Breite je Bohrung)"),
                            tr("Bohrung im Muster"), tr("Gesamtbefund des Bohrbilds"), tr("Nur als Gruppe zugeordnet")])
                verbunden = set()
                for nr, angaben in sorted(self.seiten.items()):
                    for a in angaben:
                        faktor = self.einheit.currentData()
                        gesamt = self._befunde()[za.befund(a, faktor)]
                        prefix = [*self.quellen, nr+1, " ".join(f"{v:.6f}" for v in a.box), a.text, self.einheit.currentText()]
                        ziele = a.musterziele
                        if a.einzelpruefung:
                            p = za.lese_angabe(a.text, faktor, a.grundmass)
                            zeilen = [(z.modell, self._befunde()["offen" if a.zielkonflikt else za.einzelbefund(p, z)],
                                       (z,), f"{i}/{len(ziele)}") for i,z in enumerate(ziele, 1)]
                        else:
                            zeilen = [(a.modell, gesamt, ziele, "")]
                        for m, befund, orte, nummer in zeilen:
                            verbunden.add(id(m))
                            w.writerow([*prefix, befund, m.nummer if m else "", m.wert_text() if m else "",
                                        sorted(m.flaechen) if m else "", int(a.grundmass),
                                        m.step_id if m and m.step_id > 0 else "",
                                        " ".join(f"{v:.6f}" for v in a.blattziel) if a.blattziel else "",
                                        " | ".join(" ".join(f"{v:.6f}" for v in z.ort) for z in orte),
                                        nummer, gesamt if a.einzelpruefung else "",
                                        int(any(z.tauschgruppe for z in orte)) if orte else ""])
                for m in self.modell:
                    if id(m) not in verbunden:
                        w.writerow([*self.quellen, "", "", "", "", tr("Nur im Modell") if id(m) in self.nur_modell else
                                    tr("Modell-PMI offen"), m.nummer, m.wert_text(), sorted(m.flaechen), "", m.step_id if m.step_id > 0 else "", "", "", "", "", ""])
                for nr in sorted(set(range(len(self.doc))) - self.seiten.keys()):
                    w.writerow([*self.quellen, nr+1, "", "", "", tr("Blatt ungeprüft"), "", "", "", "", "", "", "", "", "", ""])
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, tr("Prüfliste speichern"), str(e))

    @staticmethod
    def _befunde():
        return {"offen": tr("Zu prüfen"), "gleich": tr("Werte gleich"), "geaendert": tr("Abweichend"),
                "zeichnung": tr("Nur in Zeichnung")}


def oeffne_zeichnung(fenster, pfad):
    import pypdfium2 as pdf
    doc = None

    def markiere(p):
        fenster.pmi.waehle(lambda item: item is p)

    try:
        doc = pdf.PdfDocument(pfad)
        if not len(doc):
            raise ValueError(tr("Die Zeichnung enthält keine Seiten."))
        quellen = (str(pfad), str(fenster.erg.pfad))
        blaetter = (k for k in fenster.erg.baum.blaetter() if not k.hilfsgeometrie)
        einzelteil = fenster.erg.modell if next(blaetter, None) is not None and next(blaetter, None) is None else None
        dialog = Zeichnungsabgleich(doc, fenster.erg.pmi, markiere, quellen, fenster, einzelteil=einzelteil)
    except (pdf.PdfiumError, OSError, ValueError) as e:
        if doc is not None:
            doc.close()
        QtWidgets.QMessageBox.warning(fenster, tr("2D-Zeichnung öffnen"), str(e))
        return None

    def schliessen():
        fenster.pmi.bestand_geaendert.disconnect(dialog.setze_modell)
        dialog.blatt.schliesse()
        doc.close()
        fenster.zeichnungsabgleich = None

    dialog.setWindowTitle(f"{dialog.windowTitle()} – {Path(pfad).name}")
    dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    fenster.pmi.bestand_geaendert.connect(dialog.setze_modell)
    dialog.finished.connect(schliessen)
    dialog.show()
    return dialog
