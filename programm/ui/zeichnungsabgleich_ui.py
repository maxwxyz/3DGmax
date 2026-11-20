"""Blattbezogener Abgleich von Modell-PMI mit nativer und grafischer PDF-Beschriftung."""

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
    def __init__(self, einzelteil, modellkreise, kreise):
        super().__init__()
        self.einzelteil, self.modellkreise, self.kreise = einzelteil, modellkreise, kreise
        self.treffer, self.fehler = [], ""

    def _pruefe(self):
        if self.abgebrochen:
            raise Abbruch

    def run(self):
        try:
            if self.modellkreise is None:
                self.modellkreise = ansichtsabgleich.modellkreise(self.einzelteil, self._pruefe)
            self.treffer = ansichtsabgleich.zuordnen(self.kreise, self.modellkreise, self._pruefe)
        except Abbruch:
            pass
        except Exception as e:  # noqa: BLE001 - unlesbare Modellgeometrie im Dialog melden
            self.fehler = str(e)


class Blattansicht(QtWidgets.QGraphicsView):
    bereich = QtCore.Signal(tuple)
    gewaehlt = QtCore.Signal(object)
    kreis_gewaehlt = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(self.DragMode.RubberBandDrag)
        self.beginn = None
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

    def markiere(self, angaben, aktiv):
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

    def zeige_kreise(self, kreise, ziel):
        for _, item in self.kreismarken:
            self.scene().removeItem(item)
        self.kreismarken.clear()
        for k in kreise:
            stift = QtGui.QPen(QtGui.QColor("#cc5300" if k == ziel else "#167748"), 2 if k == ziel else 1)
            stift.setCosmetic(True)
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
                if item.rect().contains(self.mapToScene(ende)):
                    self.gewaehlt.emit(a)
                    return
            pos = self.mapToScene(ende)
            abstand = [(abs(math.hypot(k.x-pos.x(), k.y-pos.y()) - k.r), k) for k, _ in self.kreismarken]
            treffer = sorted(abstand, key=lambda t: t[0])
            skala = self.transform().m11()
            if (treffer and treffer[0][0]*skala < 5
                    and (len(treffer) == 1 or (treffer[1][0]-treffer[0][0])*skala > 1)):
                self.kreis_gewaehlt.emit(treffer[0][1])
        else:
            box = QtCore.QRectF(self.mapToScene(start), self.mapToScene(ende)).normalized().intersected(self.sceneRect())
            w, h = self.sceneRect().width(), self.sceneRect().height()
            if box.width() > 1 and box.height() > 1:
                self.bereich.emit((box.left()/w, box.top()/h, box.right()/w, box.bottom()/h))


class Zeichnungsabgleich(QtWidgets.QDialog):
    def __init__(self, doc, modell_pmi, zeige_modell, quellen, parent=None, *, einzelteil=None):
        super().__init__(parent)
        self.doc, self.zeige_modell = doc, zeige_modell
        self.quellen = quellen
        self.blatt = self.aktiv = None
        self.seiten = {}
        self.auftrag = None
        self.einzelteil = einzelteil
        self.modellkreise = self.blattgeometrie = None
        self.kreise = {}
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
        self.registrieren.setToolTip(tr("Eine Hauptansicht eines Einzelteils mit mindestens drei verteilten Kreismittelpunkten einrahmen."))
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
        self.ansicht.gewaehlt.connect(self.waehle)
        self.tabelle.currentCellChanged.connect(self._auswahl)
        self.zuordnung.currentIndexChanged.connect(self._vorschau)
        self.zuordnung.activated.connect(self._manuelle_wahl)
        self.text.textChanged.connect(self._vorschau)
        self.grundmass.toggled.connect(self._vorschau)
        self.bestaetigen.clicked.connect(self.uebernehmen)
        self.entfernen.clicked.connect(self._entferne)
        self.setze_modell(modell_pmi)
        self.blatt_zeigen(0)

    def setze_modell(self, pmi):
        self.modell = [p for p in pmi if p.semantisch and p.art in (MASS, BEZUG, TOLERANZ)]
        self.modellindex = {id(p): i for i, p in enumerate(self.modell)}
        self.nur_modell.intersection_update(self.modellindex)
        for angaben in self.seiten.values():
            for a in angaben:
                if a.modell is not None and id(a.modell) not in self.modellindex:
                    a.modell = None
                    a.blattziel = None
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
        zugeordnet = {id(a.modell) for angaben in self.seiten.values() for a in angaben if a.modell is not None}
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
            self.status.setText(tr("Keine eindeutige Zuordnung. Eine Hauptansicht mit weiteren Kreisen einrahmen."))
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
        self.auftrag = Ansichtsauftrag(self.einzelteil, self.modellkreise, kreise)
        self.auftrag.finished.connect(self._zugeordnet)
        self.auftrag.starte()
        self._status()

    def _abbrechen(self):
        if self.auftrag is not None:
            self.auftrag.abgebrochen = True
            self.auftrag = None

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
        for a in self.seiten[nr]:
            k = self._hinweisziel(a)
            self.zielvorschlaege[a] = k
            if k and a.modell is not None:
                a.zielkonflikt = not bool(k.flaechen & a.modell.flaechen)
            elif k and a.nur_zeichnung:
                p = za.lese_angabe(a.text, self.einheit.currentData(), a.grundmass)
                a.zielkonflikt = any(m.flaechen & k.flaechen for m in za.kandidaten(p, self.modell))
        for i, a in enumerate(self.seiten[nr]):
            self.tabelle.item(i, 2).setText(self._befunde()[za.befund(a, self.einheit.currentData())])
        if isinstance(self.aktiv, za.Blattangabe) and self.manuelle_wahl:
            self.ansicht.zeige_kreise(arbeit.treffer, self.zielvorschlaege.get(self.aktiv))
        else:
            self._auswahl(self.tabelle.currentRow(), entwurf=True)
        self._status()

    def _hinweisziel(self, a):
        pruefe = self.blatt.durchmesseranfang if "|" in a.text else None
        return self.blattgeometrie.hinweisziel(a.box, self.kreise.get(a.seite, []), pruefe)

    def _kreis_waehlen(self, k):
        if isinstance(self.aktiv, za.Blattangabe):
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
        self.aktiv = a = self.zeilen[i] if i >= 0 else None
        zeichnung = isinstance(a, za.Blattangabe)
        self.manuelle_wahl = False
        behalten = zeichnung and (neues_ziel or entwurf)
        text = self.text.toPlainText() if behalten else a.text if zeichnung else ""
        grundmass = self.grundmass.isChecked() if behalten else zeichnung and a.grundmass
        self.ansicht.markiere(self.seiten[self.blatt.nummer], a)
        kreis = self.zielvorschlaege.get(a) if zeichnung else None
        self.ansicht.zeige_kreise(self.kreise.get(self.blatt.nummer, []), kreis)
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
                vorn = {id(m) for m in bevorzugt}
                sortiert = sorted(bevorzugt, key=lambda m: not (kreis and m.flaechen & kreis.flaechen))
                sortiert += [m for m in self.modell if id(m) not in vorn]
                moeglich = am_ziel if self.blatt.nummer in self.kreise else [m for m in bevorzugt if not za.unterschiede(p, m)]
                vorschlag = None if neues_ziel or a.zielkonflikt else a.modell
                if vorschlag is None and (neues_ziel or a.zielkonflikt or not a.nur_zeichnung) and len(moeglich) == 1:
                    vorschlag = moeglich[0]
                ziel = 1 if a.nur_zeichnung and not neues_ziel and not a.zielkonflikt else 0
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
        if a is None:
            return
        if not isinstance(a, za.Blattangabe):
            self.zeige_modell(a)
            return
        idx = self.zuordnung.currentData()
        m = self.modell[idx] if idx is not None and idx >= 0 else None
        self.zeige_modell(m)
        p = za.lese_angabe(self.text.toPlainText(), self.einheit.currentData(), self.grundmass.isChecked())
        if p is None:
            self.detail.setText(tr("Angabe oder Zeichnungseinheit ungeklärt"))
        elif m is None and self.zielvorschlaege.get(a):
            self.detail.setText(tr("Hinweisziel gefunden. Die zugehörige Modell-PMI ist noch offen."))
        elif m is not None:
            k = self.zielvorschlaege.get(a)
            if k and not k.flaechen & m.flaechen:
                self.detail.setText(tr("Die gewählte Modell-PMI gehört zu einer anderen Fläche als das erkannte Hinweisziel."))
                return
            if za.grenzen_vertauscht(m):
                self.detail.setText(tr("Das Mindestmaß im Modell liegt über dem Höchstmaß."))
                return
            felder = za.unterschiede(p, m)
            namen = dict(FELD_TEXT, typ=tr("Typ"), art=tr("Art"), minimum=tr("Mindestmaß"), maximum=tr("Höchstmaß"))
            self.detail.setText(tr("Abweichende Felder: {}").format(", ".join(tr(namen[k]) for k in felder))
                                if felder else tr("Angegebene Werte stimmen überein."))

    def uebernehmen(self):
        a = self.aktiv
        if isinstance(a, za.Blattangabe):
            a.text, a.grundmass = self.text.toPlainText().strip(), self.grundmass.isChecked()
            idx = self.zuordnung.currentData()
            vorher = a.modell
            a.modell = self.modell[idx] if idx is not None and idx >= 0 else None
            a.nur_zeichnung = idx == -1
            a.zielkonflikt = False
            k = self.zielvorschlaege.get(a)
            h, w = self.blatt.bild.shape[:2]
            if k and a.modell and k.flaechen & a.modell.flaechen:
                a.blattziel = (k.x/w, k.y/h, k.r/w)
            elif a.modell is None or a.modell is not vorher or k:
                a.blattziel = None
            self.nur_modell.discard(id(a.modell))
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
                            tr("Hinweisziel (x/Breite, y/Höhe, Radius/Breite)")])
                verbunden = set()
                for nr, angaben in sorted(self.seiten.items()):
                    for a in angaben:
                        m = a.modell
                        verbunden.add(id(m))
                        w.writerow([*self.quellen, nr+1, " ".join(f"{v:.6f}" for v in a.box), a.text, self.einheit.currentText(),
                                    self._befunde()[za.befund(a, self.einheit.currentData())], m.nummer if m else "",
                                    m.wert_text() if m else "", sorted(m.flaechen) if m else "", int(a.grundmass),
                                    m.step_id if m and m.step_id > 0 else "",
                                    " ".join(f"{v:.6f}" for v in a.blattziel) if a.blattziel else ""])
                for m in self.modell:
                    if id(m) not in verbunden:
                        w.writerow([*self.quellen, "", "", "", "", tr("Nur im Modell") if id(m) in self.nur_modell else
                                    tr("Modell-PMI offen"), m.nummer, m.wert_text(), sorted(m.flaechen), "", m.step_id if m.step_id > 0 else "", ""])
                for nr in sorted(set(range(len(self.doc))) - self.seiten.keys()):
                    w.writerow([*self.quellen, nr+1, "", "", "", tr("Blatt ungeprüft"), "", "", "", "", "", ""])
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
