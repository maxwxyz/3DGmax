"""Hauptfenster: Menues, Werkzeugleiste, Seitenleisten, 3D-Ansicht, Laden."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets

from .. import i18n
from ..i18n import tr
from ..version import VERSION
from . import ansicht3d, thema
from .lader import Lader
from .messwerkzeug import MessPanel
from .vergleich_ui import AbschlussDialog, AenderungenPanel, AusrichtPanel, VergleichDialog, VergleichsLader
from .panels import AnsichtenPanel, BaumPanel, PmiPanel

DATEIFILTER = ("{} (*.stp *.step *.p21 *.igs *.iges *.stl *.obj *.gltf *.glb *.3mf *.qif *.3dgmax);;"
               "STEP (*.stp *.step *.p21);;QIF (*.qif);;IGES (*.igs *.iges);;{} (*.stl *.obj *.gltf *.glb *.3mf);;"
               "3DGmax (*.3dgmax)")  # Platzhalter: uebersetzte Namen
ENDUNGEN = (".stp", ".step", ".p21", ".igs", ".iges", ".stl", ".obj", ".gltf", ".glb", ".3mf", ".qif", ".3dgmax")
MAX_ZULETZT = 10


def einstellungen() -> QtCore.QSettings:
    """Einstellungen; DG_EINSTELLUNGEN=<datei.ini> fuer Tests (beruehrt nie die echten)."""
    pfad = os.environ.get("DG_EINSTELLUNGEN")
    if pfad:
        return QtCore.QSettings(pfad, QtCore.QSettings.Format.IniFormat)
    return QtCore.QSettings(i18n.ORG, i18n.APP)


class Startseite(QtWidgets.QWidget):
    """Anzeige ohne Modell: Datei oeffnen, zuletzt verwendet, Hinweis Drag-and-drop."""

    oeffnen = QtCore.Signal(str)  # leer = Dialog

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addStretch(1)
        titel = QtWidgets.QLabel("3DGmax")
        titel.setObjectName("titel")
        titel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(titel)
        text = QtWidgets.QLabel(tr("3D-Modelle mit PMI ansehen, messen und vergleichen"))
        text.setObjectName("leise")
        text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(text)
        knopf = QtWidgets.QPushButton(tr("STEP-Datei öffnen …"))
        knopf.setObjectName("primaer")
        knopf.clicked.connect(lambda: self.oeffnen.emit(""))
        zeile = QtWidgets.QHBoxLayout()
        zeile.addStretch(1)
        zeile.addWidget(knopf)
        zeile.addStretch(1)
        lay.addSpacing(12)
        lay.addLayout(zeile)
        hinweis = QtWidgets.QLabel(tr("oder Datei hierher ziehen"))
        hinweis.setObjectName("leise")
        hinweis.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hinweis)
        lay.addSpacing(16)
        self.zuletzt = QtWidgets.QListWidget()
        self.zuletzt.setMaximumWidth(520)
        self.zuletzt.setMaximumHeight(220)
        self.zuletzt.itemActivated.connect(lambda it: self.oeffnen.emit(it.data(QtCore.Qt.ItemDataRole.UserRole)))
        self.zuletzt_titel = QtWidgets.QLabel(tr("Zuletzt verwendet"))
        self.zuletzt_titel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.zuletzt_titel)
        z2 = QtWidgets.QHBoxLayout()
        z2.addStretch(1)
        z2.addWidget(self.zuletzt)
        z2.addStretch(1)
        lay.addLayout(z2)
        lay.addStretch(2)

    def zeige_zuletzt(self, pfade: list[str]):
        self.zuletzt.clear()
        for p in pfade:
            it = QtWidgets.QListWidgetItem(os.path.basename(p))
            it.setToolTip(p)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            self.zuletzt.addItem(it)
        self.zuletzt.setVisible(bool(pfade))
        self.zuletzt_titel.setVisible(bool(pfade))


class Hauptfenster(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self._titel())
        self.setAcceptDrops(True)
        self.resize(1400, 860)
        self.ein = einstellungen()
        self.erg = None  # Ergebnis des Ladens
        self._lader: Lader | None = None
        self.aktionen: dict[str, QtGui.QAction] = {}
        self.thema = thema.wende_an(QtWidgets.QApplication.instance(), self.ein.value("thema", "auto"))

        self.ansicht = ansicht3d.erzeuge(self)
        self.ansicht.setze_thema(self.thema)
        self.ansicht.setze_navigation(self.ein.value("navigation", "catia"))
        self.ansicht.setze_pmi_kontrast(self.ein.value("pmi_kontrast", True, type=bool))
        self._farben_anwenden()
        self.start = Startseite()
        self.stapel = QtWidgets.QStackedWidget()
        self.stapel.addWidget(self.start)
        self.stapel.addWidget(self.ansicht)
        self.setCentralWidget(self.stapel)

        self.baum = BaumPanel()
        self.pmi = PmiPanel()
        self.ansichten = AnsichtenPanel()
        self.dock_baum = self._dock(tr("Struktur"), self.baum, QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_ansichten = self._dock(tr("Gespeicherte Ansichten"), self.ansichten,
                                         QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_pmi = self._dock(tr("PMI"), self.pmi, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.messen = MessPanel()
        self.dock_messen = self._dock(tr("Messen"), self.messen, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.tabifyDockWidget(self.dock_pmi, self.dock_messen)
        from .analyse_ui import AnalysePanel
        self.analyse = AnalysePanel()
        self.aenderungen = AenderungenPanel()
        self.dock_analyse = self._dock(tr("Analyse"), self.analyse, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_analyse.hide()
        self.dock_aenderungen = self._dock(tr("Änderungen"), self.aenderungen,
                                           QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.tabifyDockWidget(self.dock_pmi, self.dock_aenderungen)
        self.dock_aenderungen.hide()
        self.vergleich = None
        self._vlader = None
        self.dock_pmi.raise_()
        self.resizeDocks([self.dock_pmi], [430], QtCore.Qt.Orientation.Horizontal)

        self.fortschritt = QtWidgets.QProgressBar()
        self.fortschritt.setRange(0, 0)
        self.fortschritt.setMaximumWidth(160)
        self.fortschritt.hide()
        self.abbrechen = QtWidgets.QPushButton(tr("Abbrechen"))
        self.abbrechen.hide()
        self.abbrechen.clicked.connect(self.lade_abbrechen)
        self.statusBar().addPermanentWidget(self.fortschritt)
        self.statusBar().addPermanentWidget(self.abbrechen)
        # Schnellmessung rechts: Kennwerte der Auswahl, Rechtsklick waehlt die Angaben
        self.schnell = QtWidgets.QLabel("")
        self.schnell.setObjectName("schnell")
        self.schnell.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.schnell.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.schnell.customContextMenuRequested.connect(self._schnell_menue)
        self.schnell.setToolTip(tr("Schnellmessung der Auswahl – Rechtsklick: Angaben wählen"))
        self.statusBar().addPermanentWidget(self.schnell)
        self._schnell_formen, self._schnell_pmi = [], []

        self._baue_aktionen()
        self._baue_menues()
        self._baue_leiste()
        self._verbinde()
        self._modell_da(False)
        self.start.zeige_zuletzt(self.zuletzt())
        self._spalten_verschiebbar()
        self._fenster_herstellen()
        self.aktionen["zeichnung_pmi"].setChecked(str(self.ein.value("zeichnung_pmi", True)).lower() in ("true", "1"))
        an = str(self.ein.value("perspektive", False)).lower() in ("true", "1")
        self.aktionen["perspektive"].setChecked(an)
        self.ansicht.setze_perspektive(an)

    def _kamera_zurueck(self):
        if not self.ansicht.kamera_zurueck():
            self.statusBar().showMessage(tr("Keine frühere Ansicht"), 3000)

    def _kamera_vor(self):
        if not self.ansicht.kamera_vor():
            self.statusBar().showMessage(tr("Keine spätere Ansicht"), 3000)

    def _perspektive(self):
        an = self.aktionen["perspektive"].isChecked()
        self.ein.setValue("perspektive", an)
        self.ansicht.setze_perspektive(an)

    def spalten_anpassen(self):
        """Tabellen ohne gemerkte Breiten an den Inhalt anpassen (begrenzt, damit nichts ausufert)."""
        for t in self._tabellen().values():
            if t.property("breiten_gemerkt") or t.rowCount() == 0:
                continue
            t.resizeColumnsToContents()
            kopf = t.horizontalHeader()
            for i in range(t.columnCount()):
                kopf.resizeSection(i, min(kopf.sectionSize(i) + 8, 320))

    def _fenster_herstellen(self):
        """Fenstergroesse und Anordnung der Seitenleisten wie beim letzten Beenden."""
        geometrie, zustand = self.ein.value("fenster_geometrie"), self.ein.value("fenster_zustand_1")
        if geometrie:
            self.restoreGeometry(geometrie)
        if zustand:
            self.restoreState(zustand)
        self.dock_aenderungen.hide()  # nur im Vergleich

    def _fenster_merken(self):
        for merken in self._spalten_merken:
            merken()
        self.ein.setValue("fenster_geometrie", self.saveGeometry())
        self.ein.setValue("fenster_zustand_1", self.saveState())
        self.ein.sync()

    def _tabellen(self):
        return {"pmi": self.pmi.tabelle, "messen": self.messen.tabelle, "aenderungen": self.aenderungen.tabelle}

    def _spalten_verschiebbar(self):
        """Spalten per Drag-and-drop umordnen, per Rechtsklick ein-/ausblenden; je Tabelle gemerkt."""
        from .panels import spalten_menue
        self._spalten_merken = []
        for name, t in self._tabellen().items():
            # kompakte Zeilen ohne Gitter
            t.setShowGrid(False)
            t.verticalHeader().setDefaultSectionSize(t.fontMetrics().height() + 10)
            t.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
            kopf = t.horizontalHeader()
            kopf.setHighlightSections(False)
            kopf.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            kopf.setSectionsMovable(True)
            kopf.setToolTip(tr("Spalten ziehen zum Umordnen, Trennlinie ziehen für die Breite, Rechtsklick: Spalten ein-/ausblenden"))
            # Version 2: Breiten ziehbar (fruehere Zustaende hatten automatische Breiten)
            schluessel = f"spalten_{name}_{t.columnCount()}_2"  # neue Spalten -> alter Zustand passt nicht mehr
            zustand = self.ein.value(schluessel)
            if zustand:
                kopf.restoreState(zustand)
                t.setProperty("breiten_gemerkt", True)
            # Breiten per Ziehen, Doppelklick auf die Trennlinie passt an den Inhalt an
            kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
            kopf.setStretchLastSection(True)
            kopf.sectionResized.connect(lambda *_a, tab=t: QtWidgets.QApplication.mouseButtons()
                                        != QtCore.Qt.MouseButton.NoButton and tab.setProperty("breiten_gemerkt", True))
            merken = (lambda n=schluessel, k=kopf: self.ein.setValue(n, k.saveState()))
            self._spalten_merken.append(merken)
            kopf.sectionMoved.connect(lambda *_a, m=merken: m())
            kopf.sectionResized.connect(lambda *_a, m=merken: m())
            kopf.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            standard = self.pmi.STANDARD if name == "pmi" else None
            kopf.customContextMenuRequested.connect(
                lambda pos, tab=t, st=standard, m=merken: spalten_menue(tab, pos, st, m))

    @staticmethod
    def _titel(datei: str = "") -> str:
        return f"3DGmax {VERSION}" + (f" – {datei}" if datei else "")

    # --- Aufbau ---

    def _dock(self, titel, widget, bereich):
        d = QtWidgets.QDockWidget(titel, self)
        d.setObjectName("dock_" + type(widget).__name__)  # sprachunabhaengig (Fensterzustand merken)
        d.setWidget(widget)
        d.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
                      QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(bereich, d)
        return d

    def _aktion(self, name, text, slot=None, kurz=None, pruefbar=False, tipp=None, modell=True):
        a = QtGui.QAction(text, self)
        if kurz:
            a.setShortcut(QtGui.QKeySequence(kurz))
        a.setCheckable(pruefbar)
        if tipp:
            a.setToolTip(tipp)
            a.setStatusTip(tipp)
        if slot:
            a.triggered.connect(slot)
        a.setProperty("braucht_modell", modell)
        # macOS: Ueber, Einstellungen, Beenden gehoeren ins Programmmenue; sonst keine Raterei nach dem Text
        rolle = {"ueber": QtGui.QAction.MenuRole.AboutRole, "einstellungen": QtGui.QAction.MenuRole.PreferencesRole,
                 "beenden": QtGui.QAction.MenuRole.QuitRole}.get(name, QtGui.QAction.MenuRole.NoRole)
        a.setMenuRole(rolle)
        self.aktionen[name] = a
        return a

    def _baue_aktionen(self):
        A = self._aktion
        A("oeffnen", tr("Öffnen …"), lambda: self.oeffnen(""), QtGui.QKeySequence.StandardKey.Open,
          tipp=tr("STEP-Datei öffnen"), modell=False)
        A("vergleichen", tr("Vergleichen …"), lambda: self.starte_vergleich(), "Ctrl+Shift+V",
          tipp=tr("Zwei Stände eines Modells vergleichen (Geometrie und PMI)"), modell=False)
        A("vergleich_beenden", tr("Vergleich beenden"), self.beende_vergleich, tipp=tr("Zurück zur normalen Ansicht"))
        A("manuell_ausrichten", tr("Manuell ausrichten …"), self.starte_manuell_ausrichten,
          tipp=tr("Punktpaare am neuen und alten Stand wählen, wenn die automatische Ausrichtung nicht passt"))
        A("umdrehen", tr("Ansicht umdrehen"), lambda: self.ansicht.umdrehen(), "U",
          tipp=tr("Von der Gegenseite schauen (180° um die Hochachse)"))
        A("ordnervergleich", tr("Ordner vergleichen …"), self.zeige_ordnervergleich,
          tipp=tr("Alle Modelle zweier Ordner paarweise vergleichen (Übersicht)"), modell=False)
        A("zoom_auswahl", tr("Auf Auswahl zoomen"), self._zoome_auswahl, "Z",
          tipp=tr("Gewählte Flächen, Kanten, PMI, Messung oder Änderung bildfüllend zeigen"))
        A("normal_auswahl", tr("Normal auf Auswahl ausrichten"), self._normal_auswahl, "N",
          tipp=tr("Blick senkrecht auf die gewählte Fläche (Mittel bei mehreren) oder Beschriftung"))
        A("auswahl_aufheben", tr("Auswahl aufheben"), self._auswahl_aufheben, tipp=tr("Gewählte Flächen und Kanten abwählen"))
        A("teil_ausblenden", tr("Auswahl ausblenden"), lambda: self._teil_befehl("ausblenden"), "H",
          tipp=tr("Die Teile der gewählten Flächen und Kanten ausblenden"))
        A("teil_isolieren", tr("Teil isolieren"), lambda: self._teil_befehl("isolieren"),
          tipp=tr("Nur das Teil der gewählten Fläche zeigen"))
        A("pdf_ansichten", tr("Ansichten als PDF …"), lambda: self.exportiere_pdf("ansichten"),
          tipp=tr("Eine Seite je gespeicherter Ansicht mit Bild und sichtbaren PMI"))
        A("pdf_vergleich", tr("Vergleichsbericht (PDF) …"), lambda: self.exportiere_pdf("vergleich"),
          tipp=tr("Übersicht, Änderungsliste und ein Bild je Änderung"))
        A("pdf_pmi_aenderungen", tr("PMI-Änderungen (PDF) …"), lambda: self.exportiere_pdf("pmi_aenderungen"),
          tipp=tr("Tabelle der PMI-Änderungen alt/neu für Lieferanten und Fertigung"))
        A("projekt_speichern", tr("Projekt speichern …"), lambda: self.speichere_projekt(),
          QtGui.QKeySequence.StandardKey.Save,
          tipp=tr("Modell bzw. Vergleich mit Prüfstand, Kommentaren und Messungen als eine Datei (.3dgmax)"))
        for n, text in (("auto", tr("Norm automatisch erkennen")), ("iso", "ISO GPS"), ("asme", "ASME Y14.5")):
            A("norm_" + n, text, lambda _=False, n=n: self.setze_norm(n), pruefbar=True,
              tipp=tr("Normsystem für Begriffe, Prüfregeln und Hüllbedingung (ohne Hinweis in der Datei: ISO GPS)"))
        gruppe = QtGui.QActionGroup(self)
        for n in ("auto", "iso", "asme"):
            gruppe.addAction(self.aktionen["norm_" + n])
        A("explosion", tr("Explosion"), self._explosion_umschalten, "X", pruefbar=True,
          tipp=tr("Explosionsansicht: Teile auseinanderziehen (Regler daneben); PMI und Messen ruhen solange"))
        A("stueckliste", tr("Stückliste …"), self.zeige_stueckliste,
          tipp=tr("Teile mit Anzahl, Volumen und Masse – Export als CSV"))
        A("analyse", tr("Analyse …"), self.zeige_analyse_leiste,
          tipp=tr("Entformungsschräge, Krümmungsradius oder Wandstärke als Farbkarte"))
        A("ballone", tr("Ballonnummern zeigen"), self.zeige_ballone_aktuell, "B", pruefbar=True,
          tipp=tr("Nummern der Merkmale (Maße, Form- und Lagetoleranzen) im Modell, wie in der Merkmalsliste"))
        A("merkmale_csv", tr("Merkmalsliste (CSV) …"), lambda: self.exportiere_merkmale(),
          tipp=tr("Prüfbare Merkmale mit Ballonnummer, Grenzen und Spalten für Messwerte"))
        A("zeichnung_blatt", tr("Zeichnung: Normansichten …"), lambda: self.exportiere_zeichnung("blatt"),
          tipp=tr("Vorder-, Drauf- und Seitenansicht nach Projektionsmethode der Norm plus Iso, verdeckte Kanten "
                  "gestrichelt – als PDF, SVG oder DXF"))
        A("zeichnung_aktuell", tr("Zeichnung: aktuelle Ansicht …"), lambda: self.exportiere_zeichnung("aktuell"),
          tipp=tr("Kantenansicht in der aktuellen Blickrichtung mit den sichtbaren PMI – als PDF, SVG oder DXF"))
        A("zeichnung_ansichten", tr("Zeichnung: gespeicherte Ansichten (PDF) …"),
          lambda: self.exportiere_zeichnung("ansichten"),
          tipp=tr("Eine Zeichnungsseite je gespeicherter Ansicht, aus deren Kamera und mit deren PMI"))
        A("zeichnung_pmi", tr("PMI in Zeichnungen"), lambda: self.ein.setValue(
            "zeichnung_pmi", self.aktionen["zeichnung_pmi"].isChecked()), pruefbar=True,
          tipp=tr("Grafische PMI der Ansicht in die Zeichnung übernehmen"))
        A("pdf_messungen", tr("Messprotokoll (PDF) …"), lambda: self.exportiere_pdf("messungen"),
          tipp=tr("Bild mit den Messungen und Tabelle der Messwerte"))
        A("merkmale_pdf", tr("Merkmalsliste (PDF) …"), lambda: self.exportiere_pdf("merkmale"),
          tipp=tr("Übersichtsbild mit Ballonnummern und Merkmalstabelle"))
        A("eigenschaften", tr("Modelleigenschaften …"), self.zeige_eigenschaften, "Ctrl+I",
          tipp=tr("Volumen, Masse, Schwerpunkt, Größe, Dateikopf – für gewählte Teile oder das ganze Modell"))
        A("bild_speichern", tr("Bild speichern …"), self.bild_speichern, tipp=tr("Aktuelle Ansicht als PNG"))
        A("bild_kopieren", tr("Bild in Zwischenablage"), self.bild_kopieren, "Ctrl+Shift+C",
          tipp=tr("Aktuelle Ansicht in die Zwischenablage"))
        A("schliessen", tr("Modell schließen"), self.schliesse_modell, QtGui.QKeySequence.StandardKey.Close)
        A("einstellungen", tr("Einstellungen …"), self.zeige_einstellungen, QtGui.QKeySequence.StandardKey.Preferences,
          tipp=tr("Kamerasteuerung, Farbschema, Sprache"), modell=False)
        self.aktionen["einstellungen"].setMenuRole(QtGui.QAction.MenuRole.PreferencesRole)
        A("beenden", tr("Beenden"), self.close, QtGui.QKeySequence.StandardKey.Quit, modell=False)
        namen = {"vorne": tr("Vorne"), "hinten": tr("Hinten"), "oben": tr("Oben"), "unten": tr("Unten"),
                 "links": tr("Links"), "rechts": tr("Rechts"), "iso": tr("Isometrisch")}
        for i, n in enumerate(ansicht3d.STANDARDANSICHTEN, 1):
            A("ansicht_" + n, namen[n], lambda _=False, n=n: self.ansicht.standard(n), str(i),
              tipp=tr("Standardansicht: {}").format(namen[n]))
        A("alles", tr("Ganzes Modell zeigen"), self.ansicht.alles_zeigen, "F", tipp=tr("Alles einpassen"))
        A("kamera_zurueck", tr("Ansicht zurück"), self._kamera_zurueck, "Alt+Left",
          tipp=tr("Vorherige Kameraposition"))
        A("kamera_vor", tr("Ansicht vor"), self._kamera_vor, "Alt+Right", tipp=tr("Nächste Kameraposition"))
        A("perspektive", tr("Perspektive"), self._perspektive, "P", pruefbar=True,
          tipp=tr("Zentralperspektive statt Parallelprojektion"))
        A("drehpunkt", tr("Drehpunkt zurücksetzen"), self.ansicht.drehpunkt_zuruecksetzen,
          tipp=tr("Drehen wieder um die Mitte (Doppelklick setzt einen Drehpunkt)"))
        gruppe = QtGui.QActionGroup(self)
        for n, text, k in (("kanten", tr("Schattiert mit Kanten"), "E"), ("schattiert", tr("Schattiert"), "S"),
                           ("draht", tr("Drahtmodell"), "W")):
            a = A("darstellung_" + n, text, lambda _=False, n=n: self.ansicht.darstellung(n), k, pruefbar=True)
            gruppe.addAction(a)
        self.aktionen["darstellung_kanten"].setChecked(True)
        A("grafik_auswahl", tr("Nur gewählte PMI zeigen"), self._grafik_umschalten, "Shift+G", pruefbar=True,
          tipp=tr("Beschriftungen nur für die in der Liste gewählten PMI zeigen"))
        A("grafik", tr("Grafische PMI zeigen"), self._grafik_umschalten, "G", pruefbar=True,
          tipp=tr("PMI-Beschriftungen im 3D-Modell ein/aus"))
        self.aktionen["grafik"].setChecked(True)
        A("hilfsgeometrie", tr("Hilfsgeometrie zeigen"), self._hilfe_umschalten, pruefbar=True,
          tipp=tr("Punkte und Linien ohne Flächen (z. B. Konstruktionsgeometrie)"))
        sg = QtGui.QActionGroup(self)
        for n, text, tipp in ((None, tr("Kein Schnitt"), tr("Schnitt aufheben")),
                              ("x", tr("Schnitt X"), tr("Schnittebene senkrecht zur Achse")),
                              ("y", tr("Schnitt Y"), tr("Schnittebene senkrecht zur Achse")),
                              ("z", tr("Schnitt Z"), tr("Schnittebene senkrecht zur Achse")),
                              ("auswahl", tr("Schnitt an Auswahl"), tr("Ebene durch die gewählte Fläche (bzw. senkrecht zur Kante)")),
                              ("blick", tr("Schnitt aus Blickrichtung"), tr("Ebene senkrecht zur Blickrichtung, Abstand über den Regler"))):
            a = A("schnitt_" + (n or "aus"), text, lambda _=False, n=n: self._waehle_schnitt(n), pruefbar=True,
                  tipp=tipp)
            sg.addAction(a)
        self.aktionen["schnitt_aus"].setChecked(True)
        A("schnitt_umkehren", tr("Schnittseite umkehren"), self._schnitt_umkehren, pruefbar=True)
        A("alle_zeigen", tr("Alle Teile zeigen"), self.baum.alle_zeigen, "Shift+H",
          tipp=tr("Ausgeblendete Teile wieder zeigen"))
        A("isolieren", tr("Gewählte Teile isolieren"), self._isolieren, "I")
        A("transparent", tr("Gewählte Teile transparent"), self._transparent, "T")
        A("pmi_suche", tr("PMI suchen"), self._suche_fokus, QtGui.QKeySequence.StandardKey.Find)
        A("pmi_export", tr("PMI exportieren (CSV) …"), lambda: self.exportiere_pmi(),
          tipp=tr("Alle PMI mit Werten, Bezügen, Flächen und Ansichten als Tabelle"))
        A("pmi_pruefen", tr("PMI prüfen …"), self.pruefe_pmi,
          tipp=tr("Unbenutzte oder fehlende Bezüge, PMI ohne Fläche, Doppelte und andere Unstimmigkeiten"))
        A("aenderungen_export", tr("Änderungen exportieren (CSV) …"), lambda: self.exportiere_aenderungen(),
          tipp=tr("Änderungsliste des Vergleichs mit Alt/Neu als Tabelle"))
        A("ansicht_vor", tr("Nächste gespeicherte Ansicht"), lambda: self.ansichten.gehe(+1), "PgDown")
        A("ansicht_zurueck", tr("Vorherige gespeicherte Ansicht"), lambda: self.ansichten.gehe(-1), "PgUp")
        A("messen", tr("Messen"), self._messen_umschalten, "M", pruefbar=True,
          tipp=tr("Abstand, Winkel, Radius, Wandstärke, Koordinaten messen"))
        A("messen_ende", tr("Werkzeug beenden"), self._werkzeug_ende, "Esc", tipp=tr("Messen beenden"))
        tg = QtGui.QActionGroup(self)
        for n, text in (("auto", tr("Wie System")), ("hell", tr("Hell")), ("dunkel", tr("Dunkel"))):
            a = A("thema_" + n, text, lambda _=False, n=n: self.setze_thema(n), pruefbar=True, modell=False)
            tg.addAction(a)
        self.aktionen["thema_" + self.ein.value("thema", "auto")].setChecked(True)
        spg = QtGui.QActionGroup(self)
        for n, text in (("auto", tr("Wie System")), ("de", "Deutsch"), ("en", "English")):
            a = A("sprache_" + n, text, lambda _=False, n=n: self.setze_sprache(n), pruefbar=True, modell=False)
            spg.addAction(a)
        self.aktionen["sprache_" + i18n.einstellung()].setChecked(True)
        A("anleitung", tr("Anleitung"), self.zeige_anleitung, QtGui.QKeySequence.StandardKey.HelpContents,
          modell=False)
        A("einfuehrung", tr("Einführung"), self.zeige_einfuehrung, modell=False)
        A("neu", tr("Was ist neu"), self.zeige_neu, modell=False)
        A("ueber", tr("Über 3DGmax"), self.zeige_ueber, modell=False)

    VERGLEICH_AKTIONEN = ("vergleich_beenden", "aenderungen_export", "pdf_vergleich", "pdf_pmi_aenderungen",
                          "manuell_ausrichten")

    def _baue_menues(self):
        mb = self.menuBar()
        a = self.aktionen
        m = mb.addMenu(tr("&Datei"))
        m.addAction(a["oeffnen"])
        self.menue_zuletzt = m.addMenu(tr("Zuletzt verwendet"))
        m.addSeparator()
        m.addAction(a["vergleichen"])
        m.addAction(a["ordnervergleich"])
        m.addAction(a["manuell_ausrichten"])
        m.addAction(a["vergleich_beenden"])
        m.addSeparator()
        m.addAction(a["projekt_speichern"])
        me = m.addMenu(tr("Exportieren"))
        for n in ("pdf_ansichten", "merkmale_pdf", "pdf_messungen", "pdf_vergleich", "pdf_pmi_aenderungen"):
            me.addAction(a[n])
        me.addSeparator()
        for n in ("zeichnung_blatt", "zeichnung_aktuell", "zeichnung_ansichten", "zeichnung_pmi"):
            me.addAction(a[n])
        me.addSeparator()
        for n in ("pmi_export", "merkmale_csv", "aenderungen_export"):
            me.addAction(a[n])
        for n in ("bild_speichern", "bild_kopieren"):
            m.addAction(a[n])
        m.addSeparator()
        m.addAction(a["schliessen"])
        m.addSeparator()
        m.addAction(a["einstellungen"])
        m.addAction(a["beenden"])
        m = mb.addMenu(tr("&Ansicht"))
        for n in ansicht3d.STANDARDANSICHTEN:
            m.addAction(a["ansicht_" + n])
        m.addAction(a["alles"])
        m.addAction(a["zoom_auswahl"])
        m.addAction(a["normal_auswahl"])
        m.addAction(a["umdrehen"])
        m.addAction(a["kamera_zurueck"])
        m.addAction(a["kamera_vor"])
        m.addAction(a["perspektive"])
        m.addSeparator()
        m.addAction(a["ansicht_vor"])
        m.addAction(a["ansicht_zurueck"])
        m.addAction(a["drehpunkt"])
        m.addSeparator()
        for n in ansicht3d.DARSTELLUNGEN:
            m.addAction(a["darstellung_" + n])
        m.addSeparator()
        m.addAction(a["grafik"])
        m.addAction(a["grafik_auswahl"])
        m.addAction(a["ballone"])
        m.addAction(a["hilfsgeometrie"])
        m.addSeparator()
        ms = m.addMenu(tr("Schnitt"))
        for n in ("schnitt_aus", "schnitt_x", "schnitt_y", "schnitt_z", "schnitt_auswahl", "schnitt_blick"):
            ms.addAction(a[n])
        ms.addSeparator()
        ms.addAction(a["schnitt_umkehren"])
        m.addSeparator()
        mt = m.addMenu(tr("Farbschema"))
        for n in ("thema_auto", "thema_hell", "thema_dunkel"):
            mt.addAction(a[n])
        msp = m.addMenu(tr("Sprache"))
        for n in ("sprache_auto", "sprache_de", "sprache_en"):
            msp.addAction(a[n])
        m = mb.addMenu(tr("&Modell"))
        m.addAction(a["eigenschaften"])
        m.addAction(a["stueckliste"])
        m.addAction(a["explosion"])
        m.addAction(a["analyse"])
        mn = m.addMenu(tr("Norm"))
        for n in ("norm_auto", "norm_iso", "norm_asme"):
            mn.addAction(a[n])
        m.addSeparator()
        for n in ("alle_zeigen", "isolieren", "transparent", "teil_ausblenden", "teil_isolieren", "auswahl_aufheben"):
            m.addAction(a[n])
        m.addSeparator()
        m.addAction(a["pmi_suche"])
        m.addAction(a["pmi_pruefen"])
        m.addAction(a["pmi_export"])
        m.addAction(a["aenderungen_export"])
        m = mb.addMenu(tr("&Werkzeuge"))
        m.addAction(a["messen"])
        m.addAction(a["messen_ende"])
        self.menue_fenster = mb.addMenu(tr("&Fenster"))
        for d in (self.dock_baum, self.dock_ansichten, self.dock_pmi, self.dock_messen, self.dock_analyse,
                  self.dock_aenderungen):
            self.menue_fenster.addAction(d.toggleViewAction())
        m = mb.addMenu(tr("&Hilfe"))
        for n in ("anleitung", "einfuehrung", "neu", "ueber"):
            m.addAction(a[n])
        self._fuelle_zuletzt()

    def _baue_leiste(self):
        tb = self.addToolBar(tr("Werkzeuge"))
        tb.setObjectName("werkzeuge")
        tb.setMovable(False)
        tb.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        a = self.aktionen
        tb.addAction(a["oeffnen"])
        tb.addAction(a["vergleichen"])
        tb.addSeparator()
        tb.addAction(a["alles"])  # Standardansichten: Ansichtswuerfel in der 3D-Ansicht und Menue Ansicht
        tb.addSeparator()
        for n in ansicht3d.DARSTELLUNGEN:
            tb.addAction(a["darstellung_" + n])
        tb.addSeparator()
        tb.addAction(a["grafik"])
        tb.addAction(a["messen"])
        tb.addSeparator()
        knopf = QtWidgets.QToolButton()
        knopf.setText(tr("Schnitt"))
        knopf.setToolTip(tr("Schnittebene wählen"))
        knopf.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menue = QtWidgets.QMenu(knopf)
        for n in ("schnitt_aus", "schnitt_x", "schnitt_y", "schnitt_z", "schnitt_auswahl", "schnitt_blick",
                  "schnitt_umkehren"):
            menue.addAction(a[n])
        knopf.setMenu(menue)
        self.schnitt_knopf = knopf
        tb.addWidget(knopf)
        self.schnitt_regler = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.schnitt_regler.setRange(0, 1000)
        self.schnitt_regler.setValue(500)
        self.schnitt_regler.setMaximumWidth(160)
        self.schnitt_regler.setToolTip(tr("Lage der Schnittebene"))
        self.schnitt_regler.valueChanged.connect(lambda _: self._schnitt(self._schnitt_achse))
        self.schnitt_regler_aktion = tb.addWidget(self.schnitt_regler)
        self.schnitt_regler_aktion.setVisible(False)  # nur bei aktivem Schnitt
        self._schnitt_achse = None
        tb.addAction(a["explosion"])
        self.explosion_regler = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.explosion_regler.setRange(0, 100)
        self.explosion_regler.setValue(50)
        self.explosion_regler.setMaximumWidth(140)
        self.explosion_regler.setToolTip(tr("Abstand der Teile in der Explosionsansicht"))
        self.explosion_regler.valueChanged.connect(lambda w: self.ansicht.setze_explosion(w / 100.0))
        self.explosion_regler.sliderReleased.connect(self._explosion_einpassen)
        self.explosion_regler_aktion = tb.addWidget(self.explosion_regler)
        self.explosion_regler_aktion.setVisible(False)  # nur bei aktiver Explosionsansicht

    def _verbinde(self):
        self.start.oeffnen.connect(self.oeffnen)
        self.pmi.gewaehlt.connect(self._pmi_gewaehlt)
        self.pmi.filter_geaendert.connect(self._pmi_filter)
        self.pmi.befehl.connect(self._pmi_befehl)
        self.ansichten.gewaehlt.connect(self._ansicht_gewaehlt)
        self.ansichten.merken.connect(lambda: self.merke_ansicht())
        self.ansichten.entfernen.connect(self._ansicht_entfernen)
        self.ansicht.flaeche_gewaehlt.connect(self._flaeche_gewaehlt)
        self.ansicht.pmi_gewaehlt.connect(self._grafik_pmi_gewaehlt)
        self.ansicht.meldung.connect(lambda t: self.statusBar().showMessage(t, 5000))
        self.ansicht.auswahl_geaendert.connect(self._schnell_auswahl)
        self.baum.sichtbar_geaendert.connect(self.ansicht.knoten_sichtbar)
        self.baum.isolieren.connect(self.ansicht.isoliere)
        self.baum.transparent.connect(self.ansicht.knoten_transparent)
        self.ansicht.element_gewaehlt.connect(self.messen.element)
        self.ansicht.kontextmenue.connect(self._kontextmenue_3d)
        self.messen.messungen_geaendert.connect(self.ansicht.zeige_messungen)
        self.messen.modus_geaendert.connect(self._messmodus)
        self.messen.koerper_von = self._koerper_von
        self.messen.toleranz = self.ansicht.fang_toleranz
        self.aenderungen.gewaehlt.connect(self._aenderung_gewaehlt)
        self.aenderungen.abschliessen.connect(self.schliesse_pruefung_ab)
        self.aenderungen.beenden.connect(self.beende_vergleich)
        self.aenderungen.karte.connect(self.zeige_farbkarte)
        self.analyse.berechnen.connect(self.starte_analyse)
        self.analyse.aus.connect(self.analyse_aus)

    def _modell_da(self, da: bool):
        for a in self.aktionen.values():
            if a.property("braucht_modell"):
                a.setEnabled(da)
        self.schnitt_knopf.setEnabled(da)
        self.schnitt_regler.setEnabled(da and self._schnitt_achse is not None)
        self.schnitt_regler_aktion.setVisible(da and self._schnitt_achse is not None)
        self.aktionen["schnitt_umkehren"].setEnabled(da and self._schnitt_achse is not None)
        self.stapel.setCurrentWidget(self.ansicht if da else self.start)
        for d in (self.dock_baum, self.dock_ansichten, self.dock_pmi):
            d.setVisible(da)
        if not da:
            self.dock_messen.hide()
            self.messen.setze_modus(None)
        for n in self.VERGLEICH_AKTIONEN:
            self.aktionen[n].setEnabled(da and self.vergleich is not None)

    # --- Laden ---

    def zuletzt(self) -> list[str]:
        werte = self.ein.value("zuletzt", []) or []
        if isinstance(werte, str):
            werte = [werte]
        return [p for p in werte if os.path.isfile(p)]

    def _merke_zuletzt(self, pfad):
        liste = [pfad] + [p for p in self.zuletzt() if p != pfad]
        self.ein.setValue("zuletzt", liste[:MAX_ZULETZT])
        self._fuelle_zuletzt()
        self.start.zeige_zuletzt(self.zuletzt())

    def _fuelle_zuletzt(self):
        self.menue_zuletzt.clear()
        liste = self.zuletzt()
        for p in liste:
            a = self.menue_zuletzt.addAction(os.path.basename(p))
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, p=p: self.oeffnen(p))
        self.menue_zuletzt.setEnabled(bool(liste))

    def oeffnen(self, pfad: str = ""):
        if not pfad:
            start = os.path.dirname(self.zuletzt()[0]) if self.zuletzt() else ""
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Modell öffnen"), start,
                                                        DATEIFILTER.format(tr("Alle Modelle"), tr("Netze")))
            if not pfad:
                return
        self.lade(pfad)

    def lade(self, pfad: str, warten: bool = False):
        """Laedt im Hintergrund; warten=True blockiert bis fertig (Tests, Selbsttest)."""
        if pfad.lower().endswith(".3dgmax"):
            return self.oeffne_projekt(pfad, warten)
        self.lade_abbrechen()
        self.statusBar().showMessage(tr("Lade {} …").format(os.path.basename(pfad)))
        self.fortschritt.show()
        self.abbrechen.show()
        self._lader = Lader(pfad, self)
        self._lader.stand.connect(lambda t: self.statusBar().showMessage(t))
        self._lader.fertig.connect(self._geladen)
        self._lader.fehler.connect(self._ladefehler)
        self._lader.start()
        if warten:
            self._lader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def lade_abbrechen(self):
        if getattr(self, "_vlader", None) is not None and self._vlader.isRunning():
            self._vlader.abgebrochen = True
            self._vlader = None
        if self._lader is not None and self._lader.isRunning():
            self._lader.abgebrochen = True
            self.statusBar().showMessage(tr("Laden abgebrochen"), 4000)
        self._lader = None
        self.fortschritt.hide()
        self.abbrechen.hide()

    def _geladen(self, erg):
        if self.sender() is not self._lader:
            return
        self._lader = None
        self.fortschritt.hide()
        self.abbrechen.hide()
        self.zeige_ergebnis(erg)
        self._projekt_messungen()

    def zeige_ergebnis(self, erg, vergleich=None):
        if vergleich is None and self.vergleich is not None:
            self.beende_vergleich(neu_zeigen=False)
        if self.aktionen["explosion"].isChecked():
            self.aktionen["explosion"].setChecked(False)
            self._explosion_umschalten()
        if vergleich is None and self.ansicht.abweichung is not None:
            self.ansicht.zeige_analyse(None)  # Analyse gehoert zum alten Modell
        self.erg = erg
        self.setWindowTitle(self._titel(os.path.basename(erg.pfad)))
        szene = ansicht3d.Szene(erg.modell, erg.baum, erg.farben, erg.grafik, erg.pmi)
        self._modell_da(True)
        self.ansicht.zeige(szene)
        self.baum.zeige(erg.baum)
        self._ansicht_pmi_ids = None
        self._wende_norm_an(erg, self._norm_wahl(erg.pfad))
        self.pmi.zeige(erg.pmi, erg.ansichten)
        self.spalten_anpassen()
        self.ansichten.zeige(erg.ansichten)
        self._merke_zuletzt(erg.pfad)
        n = len(erg.pmi)
        self.statusBar().showMessage(tr("{} geladen: {} Flächen, {} PMI, {} Ansichten ({:.1f} s)").format(
            os.path.basename(erg.pfad), len(erg.modell.flaechen), n, len(erg.ansichten), erg.modell.ladezeit), 8000)

    def _ladefehler(self, text):
        self._lader = None
        self._vlader = None
        self.fortschritt.hide()
        self.abbrechen.hide()
        self.statusBar().clearMessage()
        QtWidgets.QMessageBox.warning(self, tr("Laden fehlgeschlagen"), text)

    def schliesse_modell(self):
        self.beende_vergleich(neu_zeigen=False)
        self.messen.loesche_alle()
        self._schnell_formen, self._schnell_pmi = [], []
        self._schnell_zeigen()
        self.erg = None
        self.ansicht.zeige(None)
        self.baum.zeige(None)
        self.pmi.zeige([])
        self.ansichten.zeige([])
        self.setWindowTitle(self._titel())
        self._modell_da(False)

    # --- Drag-and-drop ---

    def dragEnterEvent(self, ev):
        if any(u.toLocalFile().lower().endswith(ENDUNGEN) for u in ev.mimeData().urls()):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for u in ev.mimeData().urls():
            if u.toLocalFile().lower().endswith(ENDUNGEN):
                self.lade(u.toLocalFile())
                break

    # --- Auswahl ---

    # --- Schnellmessung ---

    def _schnell_aus(self) -> set[str]:
        wert = self.ein.value("schnellinfo_aus", []) or []
        return {wert} if isinstance(wert, str) else set(wert)  # QSettings liefert eine Einzelangabe als Text

    def _schnell_auswahl(self, formen):
        self._schnell_formen = list(formen)
        if formen:
            self._schnell_pmi = []  # die zuletzt getroffene Auswahl zaehlt
        self._schnell_zeigen()

    def _schnell_zeigen(self):
        from ..kern import schnellinfo
        aus = self._schnell_aus()
        if "alles" in aus:
            self.schnell.setText("")
            return
        if self.ansicht.explosion > 0 and len(self._schnell_formen) >= 2:
            self.schnell.setText(tr("Explosionsansicht: Abstände erst nach dem Zurücksetzen"))
            return
        teile = schnellinfo.info(self._schnell_formen) + schnellinfo.pmi_info(self._schnell_pmi)
        self.schnell.setText("   ·   ".join(t for k, t in teile if k not in aus))

    def _schnell_menue(self, pos):
        from ..kern import schnellinfo
        aus = self._schnell_aus()
        m = QtWidgets.QMenu(self)
        a_alles = m.addAction(tr("Schnellmessung zeigen"))
        a_alles.setCheckable(True)
        a_alles.setChecked("alles" not in aus)
        m.addSeparator()
        for schluessel, text in schnellinfo.GRUPPEN.items():
            a = m.addAction(tr(text))
            a.setCheckable(True)
            a.setChecked(schluessel not in aus)
            a.setData(schluessel)
            a.setEnabled("alles" not in aus)
        a_kopie = m.addAction(tr("Kopieren"))
        a_kopie.setEnabled(bool(self.schnell.text()))
        m.insertSeparator(a_kopie)
        gewaehlt = m.exec(self.schnell.mapToGlobal(pos))
        if gewaehlt is None:
            return
        if gewaehlt is a_kopie:
            QtWidgets.QApplication.clipboard().setText(self.schnell.text().replace("   ·   ", "\n"))
            return
        schluessel = "alles" if gewaehlt is a_alles else gewaehlt.data()
        aus = aus - {schluessel} if gewaehlt.isChecked() else aus | {schluessel}
        self.ein.setValue("schnellinfo_aus", sorted(aus))
        self._schnell_zeigen()

    def _pmi_gewaehlt(self, liste):
        self._schnell_pmi = list(liste)
        if liste:
            self._schnell_formen = []
        self._schnell_zeigen()
        flaechen = set()
        for p in liste:
            flaechen |= p.flaechen
        self.ansicht.hebe_flaechen(flaechen)
        self.ansicht.hebe_pmi({p.step_id for p in liste if p.step_id})
        self.ansicht.zeige_bezugssystem(self._bezugssystem(liste))
        if len(liste) == 1:
            p = liste[0]
            self.statusBar().showMessage(f"{p.nummer}: {p.wert_text()}  ({tr('{} Flächen').format(len(p.flaechen))})")

    def _flaeche_gewaehlt(self, idx):
        if idx < 0 or self.erg is None:
            self.pmi.waehle(lambda p: False)
            return
        # Auswahl in der Liste hebt die Flaechen der PMI hervor; ohne PMI nur die Flaeche selbst
        n = self.pmi.waehle(lambda p: idx in p.flaechen)
        if n == 0:
            self.ansicht.hebe_flaechen({idx})
        self.statusBar().showMessage(tr("Fläche {}: {} PMI").format(idx, n), 6000)

    def _grafik_pmi_gewaehlt(self, ids):
        self.pmi.waehle(lambda p: p.step_id in ids)

    # --- Normsystem ---

    def _norm_wahl(self, pfad: str) -> str:
        return str(self.ein.value("norm/" + os.path.abspath(pfad).replace("/", "|"), "auto"))

    def _wende_norm_an(self, erg, wahl: str):
        """Norm an die PMI geben: Wahl des Nutzers oder erkannt (Rueckfall ISO GPS)."""
        from ..kern import norm
        erkannt = erg.norm or norm.Norm(norm.ISO, "", False)
        art = erkannt.art if wahl == "auto" else wahl
        norm.setze(erg.pmi, art)
        if wahl != "auto":
            text = tr("{} (gewählt)").format(norm.NAME[art])
        elif erkannt.erkannt:
            text = tr("{} (erkannt)").format(norm.NAME[art])
        else:
            text = tr("{} (Standard, kein Hinweis in der Datei)").format(norm.NAME[art])
        self.norm_text = text
        self.pmi.norm_text = text
        self.pmi.setToolTip(tr("Norm: {}").format(text) + (f"\n{erkannt.grund}" if erkannt.grund else ""))
        self.aktionen["norm_" + wahl].setChecked(True)

    def setze_norm(self, wahl: str):
        if self.erg is None:
            return
        self.ein.setValue("norm/" + os.path.abspath(self.erg.pfad).replace("/", "|"), wahl)
        self._wende_norm_an(self.erg, wahl)
        self.pmi.zeige(self.erg.pmi, self.erg.ansichten)
        self.statusBar().showMessage(tr("Norm: {}").format(self.norm_text), 6000)

    def _bezugssystem(self, liste) -> list:
        """Bezugselemente einer einzeln gewaehlten Toleranz: [(Name, Stelle 1..3, Flaechen)]."""
        if len(liste) != 1 or not liste[0].bezuege or self.erg is None:
            return []
        bezuege = {p.name: p for p in self.erg.pmi if p.art == "bezug" and p.typ == "Datum"}
        out = []
        for b in sorted(liste[0].bezuege, key=lambda b: b.stelle):
            for name in b.name.split("-"):  # gemeinsamer Bezug A-B: beide Elemente
                p = bezuege.get(name)
                if p is not None and p.flaechen:
                    out.append((name, b.stelle, set(p.flaechen)))
        return out

    # --- Eigene Ansichten ---

    def merke_ansicht(self, name: str = ""):
        """Aktuelle Kamera mit den sichtbaren PMI und Messungen als eigene Ansicht."""
        if self.erg is None:
            return None
        n = sum(1 for a in self.erg.ansichten if a.eigen) + 1
        a = self.ansicht.aktuelle_ansicht(name or tr("Eigene Ansicht {}").format(n))
        sichtbar = self.pmi.sichtbare()
        a.pmi_nummern = [p.nummer for p in sichtbar]
        a.pmi_ids = {p.step_id for p in sichtbar if p.step_id}
        a.messungen = [m.nummer for m in self.messen.messungen]
        self.erg.ansichten.append(a)
        self._ansichten_neu(a)
        self.statusBar().showMessage(tr("Ansicht gemerkt: {} (wird mit dem Projekt gespeichert)").format(a.name), 6000)
        return a

    def _ansicht_entfernen(self, a):
        if self.erg is not None and a in self.erg.ansichten:
            self.erg.ansichten.remove(a)
            self._ansichten_neu(None)

    def _ansichten_neu(self, waehlen):
        self.ansichten.zeige(self.erg.ansichten)
        self.pmi.setze_ansichten(self.erg.ansichten)
        if waehlen is not None:
            self.ansichten.liste.blockSignals(True)
            self.ansichten.liste.setCurrentRow(self.erg.ansichten.index(waehlen) + 1)
            self.ansichten.liste.blockSignals(False)

    def _pmi_filter(self, ids):
        """3D zeigt die PMI, die die Liste nach Art/Suche zeigt; ohne Filter wie die gewaehlte Ansicht."""
        self._pmi_filter_ids = ids
        ansicht_ids = getattr(self, "_ansicht_pmi_ids", None)
        self.ansicht.zeige_pmi(ansicht_ids if ids is None else ids)
        if "ballone" in self.aktionen and self.aktionen["ballone"].isChecked():
            self.zeige_ballone_aktuell()

    def _ansicht_gewaehlt(self, ansicht):
        self._ansicht_pmi_ids = None if ansicht is None else set(ansicht.pmi_ids)
        if ansicht is None:
            self.pmi.nur_ansicht(None)
            self.ansicht.zeige_pmi(getattr(self, "_pmi_filter_ids", None))
            return
        self.pmi.nur_ansicht(set(ansicht.pmi_nummern))
        self.ansicht.zeige_pmi(ansicht.pmi_ids if getattr(self, "_pmi_filter_ids", None) is None
                               else self._pmi_filter_ids)
        self.ansicht.kamera(ansicht)
        self.statusBar().showMessage(tr("Ansicht {}: {} von {} PMI").format(
            ansicht.name, len(ansicht.pmi_nummern), len(self.erg.pmi) if self.erg else 0), 6000)

    # --- Befehle ---

    def _messen_umschalten(self):
        an = self.aktionen["messen"].isChecked()
        if an:
            self.dock_messen.show()
            self.dock_messen.raise_()
            self.messen.setze_modus(self.messen.modus or "abstand")
        else:
            self.messen.setze_modus(None)

    def _messmodus(self, art):
        self.ansicht.setze_messmodus(art is not None)
        self.aktionen["messen"].setChecked(art is not None)
        if art:
            self.statusBar().showMessage(tr("Messen: Elemente im Modell anklicken – Esc beendet"), 6000)

    def _werkzeug_ende(self):
        self.messen.setze_modus(None)

    def _koerper_von(self, form):
        """Teil (Koerper) des Baums, zu dem eine Flaeche gehoert (fuer die Wandstaerke)."""
        if self.erg is None:
            return None
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        ziel = self.erg.modell.flaechen_index(form)
        for k in self.erg.baum.blaetter():
            if k.hilfsgeometrie:
                continue
            ex = TopExp_Explorer(k.form, TopAbs_FACE)
            while ex.More():
                if self.erg.modell.flaechen_index(ex.Current()) == ziel:
                    if self.vergleich is not None:  # wie angezeigt: ins System des alten Stands verschoben
                        from OCC.Core.TopLoc import TopLoc_Location
                        return k.form.Moved(TopLoc_Location(self.vergleich.ausrichtung.gp_trsf()))
                    return k.form
                ex.Next()
        return None

    # --- Vergleich ---

    def starte_vergleich(self, werte: dict | None = None, warten: bool = False):
        if werte is None:
            d = VergleichDialog(self.erg.pfad if self.erg else (self.zuletzt()[0] if self.zuletzt() else ""), self)
            if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return
            werte = d.werte()
        self.lade_abbrechen()
        self.statusBar().showMessage(tr("Vergleiche …"))
        self.fortschritt.show()
        self.abbrechen.show()
        self._vlader = VergleichsLader(werte, self.erg, self)
        self._vlader.stand.connect(lambda t: self.statusBar().showMessage(t))
        self._vlader.fertig.connect(self._vergleich_fertig)
        self._vlader.fehler.connect(self._ladefehler)
        self._vlader.start()
        if warten:
            self._vlader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def _vergleich_fertig(self, v):
        self._vlader = None
        self.fortschritt.hide()
        self.abbrechen.hide()
        if getattr(self, "_projekt", None):
            from ..kern import projekt
            projekt.uebernimm_pruefstand(v, self._projekt.get("vergleich", {}).get("aenderungen", []))
        self.zeige_vergleich(v)
        self._projekt_messungen()

    def zeige_ordnervergleich(self):
        from .ordnervergleich_ui import OrdnerVergleich
        d = OrdnerVergleich(self)
        d.oeffnen.connect(self.zeige_vergleich)
        d.show()
        return d

    # --- Projekt ---

    def speichere_projekt(self, pfad: str = "") -> str | None:
        from ..kern import projekt
        if self.erg is None:
            return None
        quelle = self.vergleich.neu.pfad if self.vergleich else self.erg.pfad
        pfad = pfad or self._speicherpfad(tr("Projekt speichern"), os.path.splitext(quelle)[0] + ".3dgmax",
                                          "3DGmax (*.3dgmax)")
        if not pfad:
            return None
        ziel = projekt.speichere(pfad, self.erg.pfad, self.vergleich, self.messen.messungen, VERSION,
                                 self.erg.ansichten)
        self.statusBar().showMessage(tr("Projekt gespeichert: {}").format(ziel), 6000)
        return ziel

    def oeffne_projekt(self, pfad: str, warten: bool = False):
        from ..kern import projekt
        try:
            self._projekt = projekt.lade(pfad)
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            QtWidgets.QMessageBox.warning(self, tr("Projekt öffnen"), str(e))
            return
        d = self._projekt
        if d["typ"] == "vergleich":
            v = d["vergleich"]
            self.starte_vergleich({"alt": d["pfade"]["alt"], "neu": d["pfade"]["neu"], "toleranz": v["toleranz"],
                                   "suchweite": v["suchweite"]}, warten)
        else:
            self.lade(d["pfade"]["modell"], warten)

    def _projekt_messungen(self):
        d = getattr(self, "_projekt", None)
        if d and d.get("messungen"):
            self.messen.messungen = list(d["messungen"])
            self.messen._fuelle()
            self.dock_messen.show()
        if d and d.get("ansichten") and self.erg is not None:
            self.erg.ansichten.extend(d["ansichten"])
            self._ansichten_neu(None)
        self._projekt = None

    def zeige_vergleich(self, v):
        self.vergleich = v
        self.zeige_ergebnis(v.neu, vergleich=v)
        entfernt = [v.alt.modell.flaechen[i] for i, st in v.geo.status_a.items() if st == "entfernt"]
        self.ansicht.zeige_vergleich(v.geo.status_b, entfernt, v.ausrichtung.gp_trsf())
        self.aenderungen.zeige(v, self.thema)
        self.spalten_anpassen()
        self.dock_aenderungen.show()
        self.dock_aenderungen.raise_()
        for n in self.VERGLEICH_AKTIONEN:
            self.aktionen[n].setEnabled(True)
        self.setWindowTitle(self._titel(f"{os.path.basename(v.alt.pfad)} → {os.path.basename(v.neu.pfad)}"))
        self.statusBar().showMessage(tr("Vergleich fertig: {} Änderungen").format(len(v.aenderungen)), 8000)

    def starte_manuell_ausrichten(self):
        if self.vergleich is None:
            return None
        v = self.vergleich
        self._ausricht = AusrichtPanel(v.ausrichtung.matrix, self.ansicht.fang_toleranz, self)
        self.ansicht.setze_ausrichtmodus(v.alt.modell.form)
        self.ansicht.ausricht_punkt.connect(self._ausricht.punkt)
        self._ausricht.ausrichten.connect(self._neu_ausrichten)
        self._ausricht.beendet.connect(self._ausrichten_beenden)
        self._ausricht.show()
        return self._ausricht

    def _ausrichten_beenden(self):
        try:
            self.ansicht.ausricht_punkt.disconnect(self._ausricht.punkt)
        except (RuntimeError, TypeError):
            pass
        self.ansicht.setze_ausrichtmodus(None)
        self.ansicht.setze_messmodus(self.messen.modus is not None)

    def _neu_ausrichten(self, ausrichtung, warten: bool = False):
        """Vergleich mit der manuell bestimmten Ausrichtung neu rechnen (Pruefstand wird uebernommen)."""
        v = self.vergleich
        self._projekt = {"vergleich": {"aenderungen": [{"nr": a.nummer, "titel": a.titel, "pruefstatus": a.pruefstatus,
                                                         "kommentar": a.kommentar} for a in v.aenderungen]}}
        werte = {"alt": v.alt.pfad, "neu": v.neu.pfad, "toleranz": v.toleranz, "suchweite": v.suchweite}
        self.statusBar().showMessage(tr("Vergleiche …"))
        self.fortschritt.show()
        self._vlader = VergleichsLader(werte, v.alt, self, neu_geladen=v.neu, ausrichtung=ausrichtung)
        self._vlader.stand.connect(lambda t: self.statusBar().showMessage(t))
        self._vlader.fertig.connect(self._vergleich_fertig)
        self._vlader.fehler.connect(self._ladefehler)
        self._vlader.start()
        if warten:
            self._vlader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def zeige_farbkarte(self, an: bool, grenze: float = 0.0, warten: bool = False):
        """Abweichungs-Farbkarte ein/aus; wird einmal je Vergleich im Hintergrund berechnet."""
        v = self.vergleich
        if v is None:
            return
        if not an:
            self.ansicht.zeige_abweichung(None)
            return
        karte = getattr(v, "karte", None)
        if karte is None:
            from .vergleich_ui import KartenLader
            if getattr(self, "_karten_lader", None) is not None and self._karten_lader.isRunning():
                return
            lader = KartenLader(v, self)
            lader.stand.connect(lambda p: self.statusBar().showMessage(tr("Farbkarte berechnen … {} %").format(p)))
            lader.fehler.connect(lambda t: QtWidgets.QMessageBox.warning(self, tr("Farbkarte"), t))
            lader.fertig.connect(lambda k, v=v: self._farbkarte_fertig(v, k))
            self._karten_lader = lader
            lader.start()
            if warten:
                lader.wait()
                QtWidgets.QApplication.processEvents()
            return
        from ..kern import abweichung
        grenze = grenze or abweichung.standard_grenze(karte, v.toleranz)
        grenze = max(grenze, 2 * v.toleranz)
        self.ansicht.zeige_abweichung(karte, v.toleranz, grenze)
        lo, hi = karte.bereich()
        self.statusBar().showMessage(tr("Farbkarte: Abweichung {:+.3f} bis {:+.3f} mm, Skala ±{:.3f} mm, "
                                        "Toleranz ±{:.3f} mm").format(lo, hi, grenze, v.toleranz), 10000)

    def _farbkarte_fertig(self, v, karte):
        v.karte = karte
        if self.vergleich is v and self.aenderungen.karte_an.isChecked():
            self.zeige_farbkarte(True, self.aenderungen.skala.value())

    def beende_vergleich(self, neu_zeigen: bool = True):
        if self.vergleich is None:
            return
        self.vergleich = None
        self.ansicht.zeige_vergleich(None)
        self.aenderungen.zeige(None)
        self.dock_aenderungen.hide()
        for n in self.VERGLEICH_AKTIONEN:
            self.aktionen[n].setEnabled(False)
        if neu_zeigen and self.erg is not None:
            self.setWindowTitle(self._titel(os.path.basename(self.erg.pfad)))

    def _aenderung_gewaehlt(self, a):
        if a is None or self.vergleich is None:
            self.ansicht.hebe_flaechen(set())
            return
        self.ansicht.hebe_flaechen(a.flaechen_neu)
        alt_formen = [] if a.flaechen_neu else [self.vergleich.alt.modell.flaechen[i] for i in a.flaechen_alt]
        self.ansicht.zoome_auf(a.flaechen_neu, alt_formen)
        if a.pmi_neu is not None:
            self.pmi.waehle(lambda p: p is a.pmi_neu)
            self.ansicht.hebe_flaechen(a.flaechen_neu)
        self.statusBar().showMessage(f"{a.nummer}: {a.titel} – {a.beschreibung}", 8000)

    def schliesse_pruefung_ab(self, pfad: str = "", werte: dict | None = None):
        from ..kern import pruefung
        if self.vergleich is None:
            return None
        if werte is None:
            d = AbschlussDialog(self.vergleich, self.ein.value("pruefer", ""), self)
            if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return None
            werte = d.werte()
        self.ein.setValue("pruefer", werte["pruefer"])
        if not pfad:
            vorschlag = os.path.splitext(self.vergleich.neu.pfad)[0] + "_pruefprotokoll"
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Prüfprotokoll speichern"), vorschlag + ".json",
                                                            "JSON (*.json)")
            if not pfad:
                return None
        daten = pruefung.protokoll(self.vergleich, werte["pruefer"], werte["ergebnis"], werte["bemerkung"], VERSION)
        dateien = pruefung.speichere(daten, os.path.splitext(pfad)[0])
        self.statusBar().showMessage(tr("Prüfprotokoll gespeichert: {}").format(dateien[1]), 8000)
        return dateien

    def _auswahl_ziel(self):
        """(Flaechen, Formen, PMI-IDs) der aktuellen Auswahl: 3D-Auswahl, gewaehlte PMI, Messung, Aenderung."""
        from OCC.Core.TopAbs import TopAbs_FACE
        if self.vergleich is not None and self.dock_aenderungen.isVisible() and self.aenderungen.gewaehlte():
            a = self.aenderungen.gewaehlte()
            alt = [] if a.flaechen_neu else [self.vergleich.alt.modell.flaechen[i] for i in a.flaechen_alt]
            return set(a.flaechen_neu), alt, set()
        zeilen = {i.row() for i in self.messen.tabelle.selectedIndexes()}
        if self.dock_messen.isVisible() and zeilen:
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
            from OCC.Core.gp import gp_Pnt
            return set(), [BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
                           for z in zeilen for p in self.messen.messungen[z].punkte], set()
        flaechen, formen = set(), []
        if self.erg is not None:
            for f in self.ansicht.auswahl3d:
                idx = self.erg.modell.flaechen_index(f) if f.ShapeType() == TopAbs_FACE else None
                if idx is not None:
                    flaechen.add(idx)
                else:
                    formen.append(f)
        pmi = self.pmi.gewaehlte()
        for p in pmi:
            flaechen |= p.flaechen
        return flaechen, formen, {p.step_id for p in pmi if p.step_id}

    def _zoome_auswahl(self):
        """Gewaehlte Flaechen/Kanten, PMI (auch mehrere), Messung oder Aenderung bildfuellend zeigen."""
        flaechen, formen, ids = self._auswahl_ziel()
        if flaechen or formen or ids:
            self.ansicht.zoome_auf(flaechen, formen, ids)
        else:
            self.statusBar().showMessage(tr("Erst Fläche, Kante, PMI, Messung oder Änderung wählen"), 4000)

    def _normal_auswahl(self):
        flaechen, formen, ids = self._auswahl_ziel()
        if flaechen or formen or ids:
            self.ansicht.richte_normal_aus(flaechen, formen, ids)
        else:
            self.statusBar().showMessage(tr("Erst Fläche, Kante, PMI, Messung oder Änderung wählen"), 4000)

    def _auswahl_aufheben(self):
        self.ansicht.setze_auswahl([])
        self.pmi.waehle(lambda p: False)

    def zeige_eigenschaften(self, nur_anlegen: bool = False):
        """Kennwerte der gewaehlten Teile (Baum oder 3D-Auswahl), sonst des ganzen Modells."""
        if self.erg is None:
            return None
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        from .eigenschaften_ui import EigenschaftenDialog
        nummern = self.baum.gewaehlte_blaetter()
        for f in self.ansicht.auswahl3d:
            k = self._knoten_von(f)
            if k is not None:
                nummern.add(k.nummer)
        teile = [k for k in self.erg.baum.blaetter() if k.nummer in nummern and not k.hilfsgeometrie]
        if teile:
            form = TopoDS_Compound()
            bb = BRep_Builder()
            bb.MakeCompound(form)
            for k in teile:
                bb.Add(form, k.form)
            umfang = tr("{} gewählte Teile").format(len(teile)) if len(teile) > 1 else teile[0].name
        else:
            form, umfang = self.erg.modell.form, tr("ganzes Modell")
        d = EigenschaftenDialog(form, self.erg.pfad, self.erg.modell.datei, self.ein, umfang, self,
                                norm_text=getattr(self, "norm_text", ""))
        if not nur_anlegen:
            d.exec()
        return d

    def _knoten_von(self, form):
        if self.erg is None:
            return None
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        if form.ShapeType() != TopAbs_FACE:
            # Kante/Punkt: Teil, das dieses Element enthaelt (Lage ignoriert)
            for k in self.erg.baum.blaetter():
                ex = TopExp_Explorer(k.form, form.ShapeType())
                while ex.More():
                    if ex.Current().IsPartner(form):
                        return k
                    ex.Next()
            return None
        ziel = self.erg.modell.flaechen_index(form)
        for k in self.erg.baum.blaetter():
            ex = TopExp_Explorer(k.form, TopAbs_FACE)
            while ex.More():
                if self.erg.modell.flaechen_index(ex.Current()) == ziel:
                    return k
                ex.Next()
        return None

    def _teil_befehl(self, art):
        knoten = {k.nummer for f in self.ansicht.auswahl3d for k in [self._knoten_von(f)] if k is not None}
        if not knoten:
            self.statusBar().showMessage(tr("Erst eine Fläche oder Kante des Teils wählen"), 4000)
            return
        if art == "ausblenden":
            self.baum.setze_sichtbar(knoten, False)
            self.ansicht.setze_auswahl([])
        else:
            self.ansicht.isoliere(knoten)

    def _kontextmenue_3d(self, pos):
        a = self.aktionen
        m = QtWidgets.QMenu(self)
        for n in ("zoom_auswahl", "normal_auswahl", "auswahl_aufheben"):
            m.addAction(a[n])
        m.addSeparator()
        for n in ("schnitt_auswahl", "schnitt_blick", "schnitt_aus"):
            m.addAction(a[n])
        m.addSeparator()
        for n in ("teil_ausblenden", "teil_isolieren", "alle_zeigen"):
            m.addAction(a[n])
        m.addSeparator()
        m.addAction(a["messen"])
        m.addAction(a["eigenschaften"])
        m.addAction(a["alles"])
        m.addAction(a["umdrehen"])
        std = m.addMenu(tr("Standardansicht"))
        for n in ansicht3d.STANDARDANSICHTEN:
            std.addAction(a["ansicht_" + n])
        m.exec(pos)

    def _speicherpfad(self, titel, vorschlag, filter_text):
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, titel, vorschlag, filter_text)
        return pfad

    def exportiere_pmi(self, pfad: str = "") -> bool:
        from ..kern import pmi_bericht
        if self.erg is None:
            return False
        pfad = pfad or self._speicherpfad(tr("PMI exportieren"), os.path.splitext(self.erg.pfad)[0] + "_pmi.csv",
                                          "CSV (*.csv)")
        if not pfad:
            return False
        text = pmi_bericht.als_csv(pmi_bericht.tabelle(self.erg.pmi, self.erg.ansichten, self.erg.modell))
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(text)
        self.statusBar().showMessage(tr("Exportiert: {}").format(pfad), 6000)
        return True

    def exportiere_aenderungen(self, pfad: str = "") -> bool:
        from ..kern import pmi_bericht
        if self.vergleich is None:
            return False
        pfad = pfad or self._speicherpfad(tr("Änderungen exportieren"),
                                          os.path.splitext(self.vergleich.neu.pfad)[0] + "_aenderungen.csv",
                                          "CSV (*.csv)")
        if not pfad:
            return False
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(pmi_bericht.vergleich_csv(self.vergleich))
        self.statusBar().showMessage(tr("Exportiert: {}").format(pfad), 6000)
        return True

    def exportiere_pdf(self, art: str, pfad: str = "") -> str | None:
        from . import berichte
        if self.erg is None or (art not in ("ansichten", "merkmale", "messungen") and self.vergleich is None):
            return None
        basis = os.path.splitext((self.vergleich.neu.pfad if self.vergleich else self.erg.pfad))[0]
        endung = {"ansichten": "_ansichten.pdf", "vergleich": "_vergleich.pdf", "pmi_aenderungen": "_pmi_aenderungen.pdf",
                  "merkmale": "_merkmale.pdf", "messungen": "_messprotokoll.pdf"}[art]
        pfad = pfad or self._speicherpfad(tr("PDF speichern"), basis + endung, "PDF (*.pdf)")
        if not pfad:
            return None
        self.statusBar().showMessage(tr("PDF wird erstellt …"))
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            if art == "ansichten":
                berichte.ansichten_pdf(self, pfad)
            elif art == "merkmale":
                berichte.merkmale_pdf(self, pfad)
            elif art == "messungen":
                berichte.messungen_pdf(self, pfad)
            elif art == "vergleich":
                berichte.vergleich_pdf(self, pfad)
            else:
                berichte.pmi_aenderungen_pdf(self.vergleich, pfad)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(tr("PDF gespeichert: {}").format(pfad), 8000)
        return pfad

    def exportiere_zeichnung(self, art: str, pfad: str = "") -> str | None:
        """Kantenzeichnung (HLR) der sichtbaren Teile als PDF, SVG oder DXF (nach Endung)."""
        import datetime
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        from ..kern import norm, zeichnung
        from . import berichte
        if self.erg is None:
            return None
        basis = os.path.splitext(self.erg.pfad)[0] + {"blatt": "_zeichnung", "aktuell": "_ansicht",
                                                      "ansichten": "_ansichten_zeichnung"}[art]
        filter_text = "PDF (*.pdf)" if art == "ansichten" else "PDF (*.pdf);;SVG (*.svg);;DXF (*.dxf)"
        pfad = pfad or self._speicherpfad(tr("Zeichnung speichern"), basis + ".pdf", filter_text)
        if not pfad:
            return None
        form = TopoDS_Compound()
        bb = BRep_Builder()
        bb.MakeCompound(form)
        for k in self.erg.baum.blaetter():
            if not k.hilfsgeometrie and k.nummer not in self.ansicht.versteckt:
                bb.Add(form, k.form)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            art_norm = self.erg.pmi[0].norm if self.erg.pmi else norm.ISO
            mit_pmi = self.aktionen["zeichnung_pmi"].isChecked()
            name = os.path.basename(self.erg.pfad)
            pmi_text = {p.step_id: p.wert_text() for p in self.erg.pmi if p.step_id}
            if art == "ansichten":
                seiten = []
                for a in self.erg.ansichten:
                    z = zeichnung.projiziere(form, a.richtung, a.oben, a.name)
                    if mit_pmi:
                        zeichnung.pmi_hinzu(z, self._grafik_fuer(a.pmi_ids), pmi_text, a.richtung, a.oben)
                    seiten.append((zeichnung.als_svg([z], a.name), f"{name} – {a.name}",
                                   f"{tr('{} PMI').format(len(a.pmi_nummern))} · {tr('Maße in mm')} · 3DGmax {VERSION}"))
                if not pfad.lower().endswith(".pdf"):
                    pfad += ".pdf"
                if seiten:
                    berichte.zeichnung_pdf(seiten, pfad, name, "")
                self.statusBar().showMessage(tr("Zeichnung gespeichert: {}").format(pfad), 8000)
                return pfad if seiten else None
            if art == "blatt":
                ansichten = zeichnung.blatt(form, art_norm)
                methode = tr("Projektionsmethode 3 (ASME)") if art_norm == norm.ASME else tr("Projektionsmethode 1 (ISO E)")
            else:
                richtung = tuple(-c for c in self.ansicht.blick_zum_betrachter())
                oben = self.ansicht.oben_richtung()
                ansichten = [zeichnung.projiziere(form, richtung, oben, tr("Ansicht"))]
                if mit_pmi and self.ansicht.grafik_an:
                    zeichnung.pmi_hinzu(ansichten[0], self._grafik_fuer(self.ansicht.pmi_ids_sichtbar), pmi_text,
                                        richtung, oben)
                methode = tr("aktuelle Blickrichtung")
            endung = os.path.splitext(pfad)[1].lower()
            if endung == ".svg":
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write(zeichnung.als_svg(ansichten, name))
            elif endung == ".dxf":
                with open(pfad, "w", encoding="ascii", errors="replace") as f:
                    f.write(zeichnung.als_dxf(ansichten))
            else:
                if not pfad.lower().endswith(".pdf"):
                    pfad += ".pdf"
                zeile = f"{methode} · {tr('Maße in mm')} · 3DGmax {VERSION} · {datetime.date.today().isoformat()}"
                berichte.zeichnung_pdf(zeichnung.als_svg(ansichten, name), pfad, name, zeile)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(tr("Zeichnung gespeichert: {}").format(pfad), 8000)
        return pfad

    def _grafik_fuer(self, pmi_ids) -> list:
        """Grafiken (Callouts) zu PMI-IDs; None = alle."""
        return [g for g in self.erg.grafik.values()
                if not g.leer() and (pmi_ids is None or g.pmi_ids & set(pmi_ids))]

    def exportiere_merkmale(self, pfad: str = "") -> str | None:
        from ..kern import merkmale
        if self.erg is None:
            return None
        pfad = pfad or self._speicherpfad(tr("Merkmalsliste speichern"),
                                          os.path.splitext(self.erg.pfad)[0] + "_merkmale.csv", "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(merkmale.als_csv(merkmale.liste(self.erg.pmi), self.erg.ansichten))
        self.statusBar().showMessage(tr("Merkmalsliste gespeichert: {}").format(pfad), 8000)
        return pfad

    def zeige_stueckliste(self, nur_anlegen: bool = False):
        if self.erg is None:
            return None
        from .stueckliste_ui import StuecklisteFenster
        f = StuecklisteFenster(self.erg.baum, self.ein, os.path.splitext(self.erg.pfad)[0] + "_stueckliste.csv", self)
        f.isolieren.connect(self.ansicht.isoliere)
        f.isolieren.connect(lambda _n: self.statusBar().showMessage(
            tr("Teil isoliert – Umschalt+H zeigt wieder alle Teile"), 6000))
        if not nur_anlegen:
            f.show()
        self._stueckliste = f
        return f

    # --- Analyse ---

    def zeige_analyse_leiste(self):
        self.dock_analyse.show()
        self.dock_analyse.raise_()

    def starte_analyse(self, art: str, werte: dict, warten: bool = False):
        from .analyse_ui import AnalyseLader
        if self.erg is None:
            return
        if self.vergleich is not None:
            self.statusBar().showMessage(tr("Analysen im Vergleich nicht möglich – erst Vergleich beenden"), 6000)
            return
        richtung = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1),
                    "-z": (0, 0, -1)}.get(werte.get("richtung"), None) or self.ansicht.blick_zum_betrachter()
        teile = [k.form for k in self.erg.baum.blaetter()
                 if not k.hilfsgeometrie and k.nummer not in self.ansicht.versteckt]
        lader = AnalyseLader(art, teile, richtung, self)
        lader.stand.connect(lambda p: self.statusBar().showMessage(tr("Analyse … {} %").format(p)))
        lader.fehler.connect(lambda t: QtWidgets.QMessageBox.warning(self, tr("Analyse"), t))
        lader.fertig.connect(lambda k, a=art, w=dict(werte): self._analyse_fertig(a, w, k))
        self._analyse_lader = lader
        self.analyse.start.setEnabled(False)
        lader.start()
        if warten:
            lader.wait()
            QtWidgets.QApplication.processEvents()

    def _analyse_fertig(self, art, werte, karte):
        from ..kern import analyse as an
        self.analyse.start.setEnabled(True)
        skala = {an.ENTFORMUNG: lambda: an.skala_entformung(werte["mindest"]),
                 an.KRUEMMUNG: lambda: an.skala_kruemmung(werte["klein"], werte["gross"]),
                 an.WANDSTAERKE: lambda: an.skala_wandstaerke(karte.alle())}[art]()
        self.ansicht.zeige_analyse(karte, skala)
        self.statusBar().showMessage(tr("Analyse fertig – Klick ins Modell zeigt den Wert"), 8000)

    def analyse_aus(self):
        self.ansicht.zeige_analyse(None)

    def _explosion_einpassen(self):
        """Alle Teile im Bild halten; ein gesetzter Drehpunkt bleibt dabei erhalten."""
        self.ansicht.alles_zeigen()

    def _explosion_umschalten(self):
        an = self.aktionen["explosion"].isChecked()
        self.explosion_regler_aktion.setVisible(an)
        self.ansicht.setze_explosion(self.explosion_regler.value() / 100.0 if an else 0.0)
        self._explosion_einpassen()
        if an and self.erg is not None and len([k for k in self.erg.baum.blaetter() if not k.hilfsgeometrie]) < 2:
            self.statusBar().showMessage(tr("Das Modell hat nur ein Teil – die Explosion zeigt nichts Neues"), 6000)

    def zeige_ballone_aktuell(self):
        """Ballone fuer die Merkmale, die die PMI-Liste gerade zeigt (Ansicht, Art, Suche)."""
        from ..kern import merkmale
        if self.erg is None or not self.aktionen["ballone"].isChecked():
            self.ansicht.zeige_ballone([])
            return
        sichtbar = {p.nummer for p in self.pmi.sichtbare()}
        ballone = []
        for m in merkmale.liste(self.erg.pmi):
            if m.pmi.nummer in sichtbar:
                ort = merkmale.anker(m.pmi, self.erg.grafik, self.ansicht.mitte_von)
                if ort is not None:
                    ballone.append((m.ballon, ort))
        self.ansicht.zeige_ballone(ballone)
        spalte = self.pmi.SPALTEN.index("Ballon")
        kopf = self.pmi.tabelle.horizontalHeader()
        if kopf.isSectionHidden(spalte):
            from .panels import _breite_nach_inhalt
            kopf.setSectionHidden(spalte, False)
            _breite_nach_inhalt(self.pmi.tabelle, spalte)

    def pruefe_pmi(self):
        from ..kern import pmi_bericht
        from .pmi_pruefen import PruefFenster
        if self.erg is None:
            return None
        fenster = PruefFenster(pmi_bericht.pruefe(self.erg.pmi, self.erg.ansichten), self)
        fenster.pmi_waehlen.connect(lambda nummern: self.pmi.waehle(lambda p: p.nummer in nummern))
        fenster.show()
        return fenster

    def _pmi_befehl(self, art, wert):
        if art == "zoomen":
            flaechen = set().union(*(p.flaechen for p in wert)) if wert else set()
            self.ansicht.zoome_auf(flaechen, None, {p.step_id for p in wert})
        elif art == "ausrichten":
            self.ansicht.richte_normal_aus(set().union(*(p.flaechen for p in wert)) if wert else set(), None,
                                           {p.step_id for p in wert})
        elif art == "ansicht":
            self.dock_ansichten.show()
            self.ansichten.waehle_name(wert)

    def _grafik_umschalten(self):
        an = self.aktionen["grafik"].isChecked()
        self.aktionen["grafik_auswahl"].setEnabled(an and self.erg is not None)
        self.ansicht.setze_grafik(an, self.aktionen["grafik_auswahl"].isChecked())

    def _hilfe_umschalten(self):
        self.ansicht.setze_hilfsgeometrie(self.aktionen["hilfsgeometrie"].isChecked())

    def _waehle_schnitt(self, achse):
        """Schnittart waehlen; bei Auswahl/Blick wird die Ebene jetzt festgelegt."""
        if achse == "auswahl" and not self.ansicht.schnitt_aus_auswahl():
            self.statusBar().showMessage(tr("Erst eine Fläche oder gerade/runde Kante im Modell wählen"), 5000)
            self.aktionen["schnitt_" + (self._schnitt_achse or "aus")].setChecked(True)
            return
        if achse == "blick":
            self.ansicht.schnitt_aus_blick()
        if achse in ("auswahl", "blick"):
            anteil = self.ansicht.schnitt_anteil_von_punkt(achse)
            self.schnitt_regler.blockSignals(True)
            self.schnitt_regler.setValue(int(1000 * (anteil if anteil is not None else 0.5)))
            self.schnitt_regler.blockSignals(False)
        self._schnitt(achse)

    def _schnitt(self, achse):
        self._schnitt_achse = achse
        da = self.erg is not None
        self.schnitt_regler.setEnabled(da and achse is not None)
        self.schnitt_regler_aktion.setVisible(da and achse is not None)
        self.aktionen["schnitt_umkehren"].setEnabled(da and achse is not None)
        self.ansicht.schnitt(achse, self.schnitt_regler.value() / 1000.0,
                             self.aktionen["schnitt_umkehren"].isChecked())

    def _schnitt_umkehren(self):
        self._schnitt(self._schnitt_achse)

    def _isolieren(self):
        nummern = self.baum.gewaehlte_blaetter()
        if nummern:
            self.ansicht.isoliere(nummern)
        else:
            self.statusBar().showMessage(tr("Erst Teile in der Struktur wählen"), 4000)

    def _transparent(self):
        nummern = self.baum.gewaehlte_blaetter()
        if nummern:
            self.baum.schalte_transparent(nummern)
        else:
            self.statusBar().showMessage(tr("Erst Teile in der Struktur wählen"), 4000)

    def _suche_fokus(self):
        self.dock_pmi.show()
        self.pmi.suche.setFocus()
        self.pmi.suche.selectAll()

    def _bildpfad_vorschlag(self):
        name = os.path.splitext(os.path.basename(self.erg.pfad))[0] if self.erg else "ansicht"
        return name + ".png"

    def bild_speichern(self, pfad: str = ""):
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, tr("Bild speichern"), self._bildpfad_vorschlag(),
                                                            "PNG (*.png)")
            if not pfad:
                return False
        ok = self.ansicht.bild(pfad)
        self.statusBar().showMessage((tr("Bild gespeichert: {}") if ok else tr("Bild nicht gespeichert: {}"))
                                     .format(pfad), 5000)
        return ok

    def bild_kopieren(self):
        import tempfile
        pfad = os.path.join(tempfile.mkdtemp(), "ansicht.png")
        if self.ansicht.bild(pfad):
            QtWidgets.QApplication.clipboard().setImage(QtGui.QImage(pfad))
            self.statusBar().showMessage(tr("Bild in die Zwischenablage kopiert"), 4000)

    def setze_thema(self, name):
        self.ein.setValue("thema", name)
        self.thema = thema.wende_an(QtWidgets.QApplication.instance(), name)
        self.ansicht.setze_thema(self.thema)

    def setze_sprache(self, name):
        self.ein.setValue("sprache", name)
        QtWidgets.QMessageBox.information(self, tr("Sprache"),
                                          tr("Die Sprache wird beim nächsten Start übernommen."))

    def zeige_einstellungen(self):
        from .einstellungen import EinstellungenDialog
        d = EinstellungenDialog(self.ein, self)
        if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.wende_einstellungen_an(d.werte())

    def wende_einstellungen_an(self, w: dict):
        self.ein.setValue("navigation", w["navigation"])
        self.ansicht.setze_navigation(w["navigation"])
        self.ein.setValue("pmi_kontrast", w.get("pmi_kontrast", True))
        self.ansicht.setze_pmi_kontrast(w.get("pmi_kontrast", True))
        for k in ("pmi_eigen", "pmi_eigene_farbe", "hg_eigen", "hg_oben", "hg_unten"):
            if k in w:
                self.ein.setValue(k, w[k])
        self._farben_anwenden()
        if w["thema"] != self.ein.value("thema", "auto"):
            self.setze_thema(w["thema"])
            self.aktionen["thema_" + w["thema"]].setChecked(True)
        if w["sprache"] != self.ein.value("sprache", "auto"):
            self.ein.setValue("sprache", w["sprache"])
            self.aktionen["sprache_" + w["sprache"]].setChecked(True)
            QtWidgets.QMessageBox.information(self, tr("Sprache"),
                                              tr("Die Sprache wird beim nächsten Start übernommen."))

    def _farben_anwenden(self):
        from .einstellungen import rgb
        e = self.ein
        pmi = rgb(e.value("pmi_eigene_farbe", "#d4145a")) if e.value("pmi_eigen", False, type=bool) else None
        hg = (rgb(e.value("hg_oben", "#dfe5ee")), rgb(e.value("hg_unten", "#a9b3c2"))) \
            if e.value("hg_eigen", False, type=bool) else None
        self.ansicht.setze_farben(pmi, hg)

    def zeige_anleitung(self):
        from .hilfe import HilfeFenster
        HilfeFenster.zeige(self)

    def zeige_einfuehrung(self):
        from .hilfe import Einfuehrung
        Einfuehrung(self).exec()

    def zeige_neu(self):
        from .hilfe import zeige_neu
        zeige_neu(self)

    def zeige_ueber(self):
        from .hilfe import zeige_ueber
        zeige_ueber(self)

    def erster_start(self):
        """Einfuehrung beim ersten Start und 'Was ist neu' nach einem Update."""
        if not self.ein.value("einfuehrung_gesehen", False, type=bool):
            self.ein.setValue("einfuehrung_gesehen", True)
            self.ein.setValue("version_gesehen", VERSION)
            self.zeige_einfuehrung()
        elif self.ein.value("version_gesehen", "") != VERSION:
            self.ein.setValue("version_gesehen", VERSION)
            self.zeige_neu()

    def closeEvent(self, ev):
        self._fenster_merken()
        self.lade_abbrechen()
        if self._vlader is not None and self._vlader.isRunning():
            self._vlader.abgebrochen = True
            self._vlader.wait(30000)
        super().closeEvent(ev)
