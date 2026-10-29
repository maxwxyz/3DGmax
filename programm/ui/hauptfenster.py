"""Hauptfenster: Menues, Werkzeugleiste, Seitenleisten, 3D-Ansicht, Laden."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets

from .. import i18n
from ..i18n import tr
from ..version import VERSION
from . import ansicht3d, tabellen, thema
from .groesse import SKALEN, skalierung
from .lader import Lader
from .messwerkzeug import MessPanel
from .vergleich_ui import AbschlussDialog, AenderungenPanel, AusrichtPanel, VergleichDialog, VergleichsLader
from .panels import AnsichtenPanel, BaumPanel, PmiPanel

DATEIFILTER = ("{} (*.stp *.step *.p21 *.stpz *.stepz *.gz *.igs *.iges *.stl *.obj *.gltf *.glb *.3mf *.ply *.qif "
               "*.prc *.pdf *.jt *.3dgmax *.3dgkette);;STEP (*.stp *.step *.p21 *.stpz *.stepz *.stp.gz *.step.gz);;QIF (*.qif);;"
               "PRC / 3D-PDF (*.prc *.pdf);;JT (*.jt);;IGES (*.igs *.iges);;{} (*.stl *.obj *.gltf *.glb *.3mf *.ply);;"
               "3DGmax (*.3dgmax *.3dgkette)")  # Platzhalter: uebersetzte Namen
MAX_ZULETZT = 10


def ablegbar(pfad: str) -> bool:
    """Datei zum Ablegen per Drag & Drop: alle ladbaren Formate (Liste aus kern.laden, z. B. auch JT) und Projekte;
    kern.laden erst hier laden (zieht OCCT nach, Start bleibt schnell)."""
    from ..kern.laden import ENDUNGEN
    return pfad.lower().endswith(tuple(ENDUNGEN) + (".3dgmax",))


def einstellungen() -> QtCore.QSettings:
    """Einstellungen; DG_EINSTELLUNGEN=<datei.ini> fuer Tests (beruehrt nie die echten)."""
    pfad = os.environ.get("DG_EINSTELLUNGEN")
    if pfad:
        return QtCore.QSettings(pfad, QtCore.QSettings.Format.IniFormat)
    return QtCore.QSettings(i18n.ORG, i18n.APP)


class Startseite(QtWidgets.QWidget):
    """Anzeige ohne Modell: Datei oeffnen, zuletzt verwendet, Hinweis Drag-and-drop."""

    oeffnen = QtCore.Signal(str)  # leer = Dialog
    vergleichen = QtCore.Signal()

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
        knopf = QtWidgets.QPushButton(tr("Modell öffnen …"))
        knopf.setToolTip(tr("STEP, QIF, JT, 3D-PDF, IGES oder Netz öffnen (auch per Ziehen ins Fenster)"))
        knopf.setObjectName("primaer")
        knopf.clicked.connect(lambda: self.oeffnen.emit(""))
        vergleich = QtWidgets.QPushButton(tr("Zwei Stände vergleichen …"))
        vergleich.setToolTip(tr("Alten und neuen Stand eines Modells wählen: Geometrie, PMI und Baugruppe werden "
                                "verglichen"))
        vergleich.clicked.connect(self.vergleichen.emit)
        self.beispiele = QtWidgets.QPushButton(tr("Beispiele"))
        self.beispiele.setToolTip(tr("Jede Funktion an freien Testdaten ausprobieren"))
        self.beispiele_menue = QtWidgets.QMenu(self.beispiele)
        self.beispiele.setMenu(self.beispiele_menue)
        self.gefuehrt = QtWidgets.QPushButton(tr("Geführt"))  # Schritt fuer Schritt fuer Einsteiger
        self.gefuehrt.setToolTip(tr("Eine Aufgabe Schritt für Schritt: Scan prüfen oder Spalt messen"))
        self.gefuehrt_menue = QtWidgets.QMenu(self.gefuehrt)
        self.gefuehrt.setMenu(self.gefuehrt_menue)
        zeile = QtWidgets.QHBoxLayout()
        zeile.addStretch(1)
        for k in (knopf, vergleich, self.beispiele, self.gefuehrt):
            zeile.addWidget(k)
        zeile.addStretch(1)
        lay.addSpacing(12)
        lay.addLayout(zeile)
        hinweis = self.formate = QtWidgets.QLabel(tr("STEP, IGES, QIF, PRC/3D-PDF, STL, OBJ, glTF, 3MF, PLY – oder "
                                                     "Datei hierher ziehen · Befehl suchen mit Strg/⌘+K"))
        # JT nur in der Programmvariante mit Konverter; erst nach dem Start pruefen (kern.laden laedt OCCT)
        QtCore.QTimer.singleShot(0, self._jt_nennen)
        hinweis.setWordWrap(True)  # schmales Fenster: umbrechen statt die Mindestbreite vorzugeben
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

    def _jt_nennen(self):
        from ..kern.laden import jt_wandler
        if jt_wandler() is not None:
            self.formate.setText(tr("STEP, IGES, QIF, JT, PRC/3D-PDF, STL, OBJ, glTF, 3MF, PLY – oder Datei hierher "
                                    "ziehen · Befehl suchen mit Strg/⌘+K"))

    def zeige_zuletzt(self, pfade: list[str]):
        self.zuletzt.clear()
        for p in pfade:
            it = QtWidgets.QListWidgetItem(os.path.basename(p))
            it.setToolTip(p)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            self.zuletzt.addItem(it)
        self.zuletzt.setVisible(bool(pfade))
        self.zuletzt_titel.setVisible(bool(pfade))


FENSTER: list = []  # offene Hauptfenster (Datei > Neues Fenster); haelt sie am Leben
_KOPPLUNG = {"uhr": None, "zuletzt": {}}


def _fenster_uhr() -> QtCore.QTimer:
    """Gemeinsamer Takt fuer gekoppelte Fensterkameras: die zuletzt bewegte Kamera gilt fuer alle."""
    if _KOPPLUNG["uhr"] is None:
        uhr = QtCore.QTimer()
        uhr.setInterval(60)
        uhr.timeout.connect(kameras_abgleichen)
        _KOPPLUNG["uhr"] = uhr
    return _KOPPLUNG["uhr"]


def kameras_abgleichen():
    zuletzt = _KOPPLUNG["zuletzt"]
    ansichten = [f.ansicht for f in FENSTER if f.erg is not None]
    bewegt = next((a for a in ansichten if a.kamera_daten() is not None and id(a) in zuletzt
                   and a.kamera_daten() != zuletzt[id(a)]), None)
    if bewegt is not None:
        k = bewegt.kamera_daten()
        for a in ansichten:
            if a is not bewegt:
                a.setze_kamera_daten(k)
    _KOPPLUNG["zuletzt"] = {id(a): a.kamera_daten() for a in ansichten}


def _alle_fenster() -> list:
    """Alle offenen Hauptfenster (Einstellungen und Thema gelten fuer alle)."""
    return [w for w in QtWidgets.QApplication.topLevelWidgets() if isinstance(w, Hauptfenster)]

class Hauptfenster(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        from . import radsperre
        radsperre.installieren(QtWidgets.QApplication.instance())  # Rad rollt Tabellen, aendert keine Werte
        from ..i18n import qt_uebersetzung
        qt_uebersetzung(QtWidgets.QApplication.instance())  # Qt-Knoepfe deutsch, auch ohne app.main (Skripte, Tests)
        FENSTER.append(self)
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
        self.ansicht.setze_draht_kontrast(self.ein.value("draht_kontrast", True, type=bool))
        self._farben_anwenden()
        self.start = Startseite()
        self.stapel = QtWidgets.QStackedWidget()
        self.stapel.addWidget(self.start)
        self.stapel.addWidget(self._baue_mitte())
        self.setCentralWidget(self.stapel)

        self.baum = BaumPanel()
        self.pmi = PmiPanel()
        self.ansichten = AnsichtenPanel()
        self.ansichten.setze_vorschaugroesse(str(self.ein.value("vorschau", "klein")))
        self.ansichten.vorschau_geaendert.connect(lambda v: self.ein.setValue("vorschau", v))
        self.baum_alt = BaumPanel()  # Nebeneinander: Struktur des alten Stands unter der des neuen
        self.baum_alt.hide()
        self._baum_titel = (QtWidgets.QLabel(tr("Neuer Stand")), QtWidgets.QLabel(tr("Alter Stand")))
        baeume = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        for titel, panel in zip(self._baum_titel, (self.baum, self.baum_alt)):
            teil = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(teil)
            lay.setContentsMargins(0, 0, 0, 0)
            titel.setStyleSheet("font-weight: bold; padding: 2px 4px;")
            titel.hide()
            lay.addWidget(titel)
            lay.addWidget(panel, 1)
            baeume.addWidget(teil)
        struktur = QtWidgets.QWidget()  # oben Schnitt und Explosion (fuellt _baue_leiste), darunter die Baeume
        struktur_lay = QtWidgets.QVBoxLayout(struktur)
        struktur_lay.setContentsMargins(0, 0, 0, 0)
        self._struktur_werkzeuge = QtWidgets.QWidget()
        struktur_lay.addWidget(self._struktur_werkzeuge)
        struktur_lay.addWidget(baeume, 1)
        self.dock_baum = self._dock(tr("Struktur"), struktur, QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_baum.setObjectName("dock_Struktur")  # eindeutig fuer den gemerkten Fensterzustand
        self.dock_ansichten = self._dock(tr("Gespeicherte Ansichten"), self.ansichten,
                                         QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
        self._berichte_gespeichert: set[str] = set()  # gespeicherte Berichte (gefuehrte Ablaeufe pruefen sie)
        self._ausrichtung_bestaetigt = False
        from .fuehrung import FuehrungPanel
        self.fuehrung = FuehrungPanel()  # gefuehrte Ablaeufe (Hilfe › Gefuehrt)
        self.dock_fuehrung = self._dock(tr("Geführt"), self.fuehrung, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_fuehrung.hide()
        from .inspektor import InspektorPanel
        self.inspektor = InspektorPanel()  # Eigenschaften und Befehle der aktuellen Auswahl
        self.dock_inspektor = self._dock(tr("Inspektor"), self.inspektor, QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
        self.tabifyDockWidget(self.dock_ansichten, self.dock_inspektor)
        self.dock_pmi = self._dock(tr("PMI"), self.pmi, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.messen = MessPanel()
        self.dock_messen = self._dock(tr("Messen"), self.messen, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.tabifyDockWidget(self.dock_pmi, self.dock_messen)
        from .analyse_ui import AnalysePanel
        from .kommentar_ui import KommentarPanel
        self.analyse = AnalysePanel()
        self.kommentare = KommentarPanel()
        self.aenderungen = AenderungenPanel()
        self.dock_analyse = self._dock(tr("Analyse"), self.analyse, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_analyse.hide()
        self.dock_kommentare = self._dock(tr("Kommentare"), self.kommentare, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_kommentare.hide()
        from .scan_ui import ScanPanel
        self.scan = ScanPanel()
        self.dock_scan = self._dock(tr("Scanprüfung"), self.scan, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_scan.hide()
        from .kollision_ui import KollisionPanel
        self.kollision = KollisionPanel()
        self.dock_kollision = self._dock(tr("Kollisionen"), self.kollision, QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.tabifyDockWidget(self.dock_pmi, self.dock_kollision)
        self.dock_kollision.hide()
        self.kollision.starten.connect(self.starte_kollision)
        self.kollision.gewaehlt.connect(self._kollision_gewaehlt)
        self.kollision.pdf.connect(lambda: self.exportiere_kollision_pdf())
        self.kollision.beenden.connect(self.kollision_aus)
        from ..kern.verbindung import Baugruppe
        from .baugruppe_ui import BaugruppePanel
        self.baugruppe = Baugruppe()
        self.zusammenbau = BaugruppePanel()
        self.dock_zusammenbau = self._dock(tr("Zusammenbau"), self.zusammenbau,
                                           QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.tabifyDockWidget(self.dock_pmi, self.dock_zusammenbau)
        self.dock_zusammenbau.hide()
        self.zusammenbau.verbinden.connect(self.verbinde_auswahl)
        self.zusammenbau.verbinden_321.connect(self.verbinde_321)
        self.zusammenbau.entfernen.connect(self._verbindung_entfernen)
        self.zusammenbau.zuruecksetzen.connect(self.zusammenbau_zuruecksetzen)
        self.zusammenbau.wiggle.connect(self._wiggle)
        self.zusammenbau.toleranz.connect(self._spielraum)
        self.zusammenbau.umkehren.connect(lambda n: self._verbindung_aendern(self.baugruppe.umkehren, n))
        self.zusammenbau.teile.itemSelectionChanged.connect(self._frei_anzeigen)
        self.zusammenbau.masse.itemSelectionChanged.connect(self.messgroesse_zeigen)
        self.zusammenbau.frei_bewegen.connect(self._frei_bewegen)
        self.ansicht.manipulator_bewegt.connect(self._manipulator_bewegt)
        self.ansicht.manipulator_fertig.connect(self._manipulator_fertig)
        self.dock_zusammenbau.visibilityChanged.connect(lambda _an: self._manipulator_zeigen())
        self.dock_zusammenbau.visibilityChanged.connect(lambda an: setattr(self.ansicht, "teil_ziehen_an", an))
        self.ansicht.teil_ziehen_start.connect(self.teil_ziehen_start)
        self.ansicht.teil_gezogen.connect(self.teil_gezogen)
        self.ansicht.teil_ziehen_ende.connect(self.teil_ziehen_ende)
        self.zusammenbau.frei_zurueck.connect(lambda: self._frei_bewegen([]))
        self.zusammenbau.tauschen.connect(lambda n: self._verbindung_aendern(self.baugruppe.tauschen, n))
        self.zusammenbau.mass_anlegen.connect(self.messgroesse_auswahl)
        self.zusammenbau.mass_entfernen.connect(self._messgroesse_entfernen)
        self.zusammenbau.neu_rechnen.connect(self._zusammenbau_zeigen)
        self.zusammenbau.soll.connect(self._soll)
        self.zusammenbau.freigabe.connect(self._mass_freigabe)
        self.zusammenbau.mass_pdf.connect(lambda: self.exportiere_messgroessen_pdf())
        self.zusammenbau.mass_kette.connect(self.messgroesse_als_kette3d)
        self.zusammenbau.hinzufuegen.connect(lambda: self.modell_hinzufuegen(""))
        self.scan.gewaehlt.connect(lambda p: self.pmi.waehle(lambda q: q is p))
        self.scan.beenden.connect(self.scan_aus)
        self.scan.neu_auswerten.connect(lambda b: self.pruefe_scan(self._scan["pfad"], bezug=b)
                                        if getattr(self, "_scan", None) else None)
        self.scan.bericht.connect(lambda: self.exportiere_scan_pdf())
        self.scan.manuell.connect(self.scan_von_hand)
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
        self._aufgaben = []  # laufende Hintergrundrechnungen (Analyse, Farbkarte, Material, Scan)
        self.vergleich_stand = QtWidgets.QLabel("")  # im Vergleich: welche zwei Staende geladen sind
        self.vergleich_stand.setObjectName("leise")
        self.vergleich_stand.setToolTip(tr("Im Vergleich geladene Stände: alt → neu"))
        self.vergleich_stand.hide()
        self.statusBar().addPermanentWidget(self.vergleich_stand)
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
        self._allgemein = None  # gewaehlte Allgemeintoleranzen (kern.toleranzzone.Allgemein)
        self._zonen_alle = (None, None)  # (Schluessel, Ergebnis) der Darstellung aller Zonen

        self._baue_aktionen()
        self._baue_menues()
        self._baue_leiste()
        self._verbinde()
        self._modell_da(False)
        self.start.zeige_zuletzt(self.zuletzt())
        self._spalten_verschiebbar()
        self._fenster_herstellen()
        an_ani = str(self.ein.value("animation", True)).lower() in ("true", "1")
        self.aktionen["animation"].setChecked(an_ani)
        self.ansicht.animation = an_ani
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

    def _animation(self):
        an = self.aktionen["animation"].isChecked()
        self.ein.setValue("animation", an)
        self.ansicht.animation = an

    def _perspektive(self):
        an = self.aktionen["perspektive"].isChecked()
        self.ein.setValue("perspektive", an)
        self.ansicht.setze_perspektive(an)

    def spalten_anpassen(self):
        """Neuer Inhalt (Modell, Vergleich): Spalten an den Inhalt anpassen, auch wenn vorher von Hand gezogen;
        danach bleiben gezogene Breiten bis zum naechsten Modell."""
        for t in self._tabellen().values():
            if t.rowCount():
                tabellen.spalten_anpassen(t, neu=True, strecken=True)

    def _fenster_herstellen(self):
        """Fenstergroesse und Anordnung der Seitenleisten wie beim letzten Beenden."""
        geometrie, zustand = self.ein.value("fenster_geometrie"), self.ein.value("fenster_zustand_1")
        if geometrie:
            self.restoreGeometry(geometrie)
        if zustand:
            self.restoreState(zustand)
        self.dock_aenderungen.hide()  # nur im Vergleich
        self.dock_aenderungen.toggleViewAction().setEnabled(False)  # Menue: ohne Vergleich nicht leer oeffnen
        bereich = str(self.ein.value("arbeitsbereich", "ansehen"))
        self.bereiche.zeige(bereich, melden=False)
        if not zustand:  # gemerkte Anordnung (auch geschlossene Leisten) geht vor; sonst die des Bereichs
            self.setze_arbeitsbereich(self.bereiche.schluessel())

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
            if zustand:  # Reihenfolge und sichtbare Spalten; die Breiten passt das naechste Modell an
                kopf.restoreState(zustand)
            # Breiten per Ziehen, Doppelklick auf die Trennlinie passt an den Inhalt an
            kopf.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
            kopf.setStretchLastSection(True)
            if name == "messen":  # waechst je Messung: neue Zeilen passen die Spalten an (gezogene bleiben)
                tabellen.automatisch_anpassen(t, strecken=True)
            merken = (lambda n=schluessel, k=kopf: self.ein.setValue(n, k.saveState()))
            self._spalten_merken.append(merken)
            spaeter = QtCore.QTimer(self)  # beim Ziehen der Seitenleiste nicht bei jedem Pixel speichern
            spaeter.setSingleShot(True)
            spaeter.setInterval(500)
            spaeter.timeout.connect(merken)
            kopf.sectionMoved.connect(lambda *_a, m=merken: m())
            kopf.sectionResized.connect(lambda *_a, z=spaeter: z.start())
            kopf.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            standard = self.pmi.STANDARD if name == "pmi" else None
            kopf.customContextMenuRequested.connect(
                lambda pos, tab=t, st=standard, m=merken: spalten_menue(tab, pos, st, m))

    @staticmethod
    def _titel(datei: str = "") -> str:
        return f"3DGmax {VERSION}" + (f" – {datei}" if datei else "")

    # --- Aufbau ---

    def _dock(self, titel, widget, bereich, rollen: bool = True):
        d = QtWidgets.QDockWidget(titel, self)
        d.setObjectName("dock_" + type(widget).__name__)  # sprachunabhaengig (Fensterzustand merken)
        # in einem Rollbereich: der Inhalt bestimmt nicht die Mindestgroesse des Fensters (sonst passt es bei
        # skalierter Oberflaeche nicht auf den Bildschirm und Teile der Leisten - z. B. der Wiggle-Knopf - fehlen)
        if rollen:
            bereich_rollen = QtWidgets.QScrollArea()
            bereich_rollen.setWidgetResizable(True)
            bereich_rollen.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            bereich_rollen.setWidget(widget)
            bereich_rollen.setMinimumSize(180, 120)
            d.setWidget(bereich_rollen)
        else:  # Werkzeugleiste mit eigenen rollenden Tabellen: Knoepfe bleiben beim Rollen stehen
            d.setWidget(widget)
        d.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
                      QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(bereich, d)
        # Reiterleisten legt Qt erst beim Stapeln an -> danach mit X versehen
        # Methoden statt Lambdas: Qt trennt sie, wenn das Fenster geloescht wird
        d.visibilityChanged.connect(self._dock_sichtbarkeit)
        d.dockLocationChanged.connect(self._tabs_spaeter)
        return d

    def _dock_sichtbarkeit(self, sichtbar: bool):
        d = self.sender()
        self._tabs_spaeter()
        if isinstance(d, QtWidgets.QDockWidget):
            self._leiste_sichtbar(d, sichtbar)

    def _tabs_spaeter(self, *_):
        QtCore.QTimer.singleShot(0, self, self._tabs_schliessbar)

    def _tabs_schliessbar(self):
        """Reiter gestapelter Leisten mit X schliessen (wie das X in der Titelleiste der Leiste)."""
        nur_direkt = QtCore.Qt.FindChildOption.FindDirectChildrenOnly
        for leiste in self.findChildren(QtWidgets.QTabBar, options=nur_direkt):
            if not leiste.tabsClosable():
                leiste.setTabsClosable(True)
                leiste.tabCloseRequested.connect(lambda i, l=leiste: self._tab_schliessen(l, i))
                leiste.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
                leiste.customContextMenuRequested.connect(lambda pos, l=leiste: self._tab_menue(l, pos))

    def _alle_docks(self) -> list:
        return [d for d in self.findChildren(QtWidgets.QDockWidget) if d.parent() is self]

    def _tab_menue(self, leiste, pos, ausfuehren: bool = True):
        """Rechtsklick auf die Reiter: alle Leisten ein-/ausblenden; eingeblendete kommen in diese Reitergruppe."""
        titel = [leiste.tabText(i) for i in range(leiste.count())]
        gruppe = next((d for d in self._alle_docks() if d.windowTitle() in titel and d.isVisible()), None)
        m = QtWidgets.QMenu(self)
        for d in sorted(self._alle_docks(), key=lambda d: d.windowTitle().lower()):
            a = m.addAction(d.windowTitle())
            a.setCheckable(True)
            a.setChecked(d.isVisible())
            a.toggled.connect(lambda an, d=d: self._dock_umschalten(d, an, gruppe))
        if ausfuehren:
            m.exec(leiste.mapToGlobal(pos))
        return m

    WERKZEUG_LEISTEN = ("kette", "kette2d", "kette3d", "funktion")  # Fenster, die als Leiste unten liegen

    def _als_leiste(self, f, titel: str, name: str):
        """Werkzeugfenster (QDialog) als Seitenleiste unten, mit den anderen Werkzeugleisten in Reitern (Regel: was zum
        Modell gehoert und neben der 3D-Ansicht benutzt wird, ist eine Leiste). Schliessen/Esc schliesst die Leiste,
        Wiederoeffnen zeigt den Inhalt wieder."""
        f.setWindowFlags(QtCore.Qt.WindowType.Widget)
        # im Rollbereich: die Leiste (auch herausgeloest) laesst sich schmaler ziehen als der Inhalt mindestens braucht,
        # darunter rollt sie quer; bei normaler Hoehe rollen nur die Tabellen, die Knoepfe bleiben stehen
        d = self._dock(titel, f, QtCore.Qt.DockWidgetArea.BottomDockWidgetArea)
        setattr(self, "dock_" + name, d)
        gruppe = next((x for n in self.WERKZEUG_LEISTEN if n != name and (x := getattr(self, "dock_" + n, None))
                       is not None and not x.isFloating()), None)
        if gruppe is not None:
            self.tabifyDockWidget(gruppe, d)
        f.rejected.connect(d.close)
        d.visibilityChanged.connect(lambda sichtbar: sichtbar and f.isHidden() and f.show())
        if hasattr(f, "wiggle"):  # Toleranzkette: mit der Leiste endet auch der Wiggle der Schlussflaechen
            d.toggleViewAction().toggled.connect(lambda an: an or f.wiggle.setChecked(False))
        self.menue_fenster.insertAction(self.menue_fenster.actions()[-2], d.toggleViewAction())
        d.hide()
        return d

    def _leiste_zeigen(self, f, name: str):
        d = getattr(self, "dock_" + name)
        f.show()
        erstes_mal = not d.isVisible() and not getattr(d, "_groesse_gesetzt", False)
        d.show()
        d.raise_()
        if erstes_mal and not d.isFloating():  # Tabellen und Histogramm brauchen Hoehe: knapp die Haelfte
            self.resizeDocks([d], [int(self.height() * 0.45)], QtCore.Qt.Orientation.Vertical)
            d._groesse_gesetzt = True

    def setze_arbeitsbereich(self, schluessel: str):
        """Seitenleisten des Arbeitsbereichs zeigen, die anderen ausblenden; Leisten, die nur in einem Zustand Sinn
        ergeben (Aenderungen im Vergleich, Scanpruefung mit Scan), nur dann."""
        from .arbeitsbereiche import BEREICHE, GEMEINSAM, leisten
        self._bereich_schaltet = True
        try:
            gewollt = leisten(schluessel)
            alle = {n for b in BEREICHE for n in b[4]}
            for name in sorted(alle):
                d = getattr(self, "dock_" + name, None)
                if d is None:
                    continue
                if name in gewollt and self._leiste_moeglich(name, schluessel):
                    d.show()
                elif name not in GEMEINSAM:  # Struktur, PMI, Ansichten verschwinden beim Umschalten nie
                    d.hide()
            vorne = next((n for n in gewollt if n not in ("baum", "ansichten", "inspektor") and self._leiste_moeglich(n, schluessel)),
                         None)
            if vorne is not None:
                getattr(self, "dock_" + vorne).raise_()
            self.ein.setValue("arbeitsbereich", schluessel)
        finally:
            self._bereich_schaltet = False

    def _leiste_moeglich(self, name: str, bereich: str = "") -> bool:
        if name == "aenderungen":  # im Bereich Vergleich auch ohne Vergleich: Hinweis und "Zwei Staende vergleichen"
            return self.vergleich is not None or bereich == "vergleichen"
        if name == "scan":
            return getattr(self, "_scan", None) is not None
        return True

    def _leiste_sichtbar(self, d, sichtbar: bool):
        """Ein Werkzeug oeffnet eine Leiste eines anderen Bereichs: die Bereichsleiste folgt (ohne umzuschalten)."""
        from .arbeitsbereiche import bereich_von, leisten
        if not sichtbar or getattr(self, "_bereich_schaltet", False) or getattr(self, "bereiche", None) is None:
            return
        name = next((n[5:] for n in vars(self) if n.startswith("dock_") and getattr(self, n) is d), None)
        ziel = bereich_von(name) if name else None
        if ziel is not None and name not in leisten(self.bereiche.schluessel()):
            self.bereiche.zeige(ziel, melden=False)
            self.ein.setValue("arbeitsbereich", ziel)

    def _dock_umschalten(self, d, an: bool, gruppe=None):
        if not an:
            d.close()
            return
        if gruppe is not None and gruppe is not d and not d.isFloating():
            self.tabifyDockWidget(gruppe, d)
        d.show()
        d.raise_()

    def _tab_schliessen(self, leiste, i: int):
        titel = leiste.tabText(i)
        for d in self.findChildren(QtWidgets.QDockWidget):
            if d.windowTitle() == titel and d.isVisible():
                d.close()
                return

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
        A("modell_hinzufuegen", tr("Modell hinzufügen …"), lambda: self.modell_hinzufuegen(""),
          tipp=tr("Weitere Datei als zusätzliche Teile ins geladene Modell aufnehmen (z. B. für den Zusammenbau); "
                  "sie liegt zunächst neben dem Modell"))
        A("neues_fenster", tr("Neues Fenster"), lambda: self.neues_fenster(), QtGui.QKeySequence.StandardKey.New,
          tipp=tr("Weiteres Fenster für ein anderes Modell (Einstellungen und zuletzt verwendet gemeinsam)"),
          modell=False)
        A("in_neuem_fenster", tr("In neuem Fenster öffnen …"), lambda: self.neues_fenster(""), modell=False)
        A("kameras_koppeln", tr("Kameras der Fenster koppeln"), self._fenster_koppeln, pruefbar=True, modell=False,
          tipp=tr("Drehen und Zoomen wirkt in allen Fenstern gleich (z. B. zwei Modelle nebeneinander)"))
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
        A("teil_isolieren", tr("Teil der gewählten Fläche isolieren"), lambda: self._teil_befehl("isolieren"),
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
        A("verzahnung", tr("Verzahnung erkennen …"), lambda: self.erkenne_verzahnung(),
          tipp=tr("Zähnezahl, Modul, Eingriffswinkel, Schrägung, Profilverschiebung und Zahnweite der gewählten Teile "
                  "(ohne Auswahl: aller sichtbaren) aus der Geometrie – Export CSV/JSON"))
        A("step_pmi_speichern", tr("STEP mit geänderten PMI speichern …"), lambda: self.speichere_step_pmi(),
          tipp=tr("Kopie der STEP-Datei: bearbeitete PMI-Werte ersetzt, eigene PMI als semantische AP242-PMI angehängt "
                  "– alles andere bleibt unverändert"))
        A("messergebnisse", tr("Messergebnisse (QIF) einlesen …"), lambda: self.lies_messergebnisse(),
          tipp=tr("QIF-Messergebnisse den Merkmalen zuordnen (Kennung = Ballonnummer, sonst Name) und bewerten – "
                  "die Merkmalsliste übernimmt die Messwerte"))
        A("stueckliste", tr("Stückliste …"), self.zeige_stueckliste,
          tipp=tr("Teile mit Anzahl, Volumen und Masse – Export als CSV"))
        A("kommentar", tr("Kommentar …"), lambda: self.neuer_kommentar(), "K",
          tipp=tr("Kommentar, Frage oder Änderungsvorschlag an den gewählten Flächen oder PMI"))
        A("kommentare_csv", tr("Kommentare (CSV) …"), lambda: self.exportiere_kommentare(),
          tipp=tr("Alle Kommentare mit Art, Status, Autor, Datum und Bezug"))
        A("pdf_kommentare", tr("Kommentare (PDF) …"), lambda: self.exportiere_pdf("kommentare"),
          tipp=tr("Bild mit den Kommentar-Markierungen und Liste der Kommentare"))
        A("pmi_anlegen", tr("PMI anlegen …"), lambda: self.pmi_anlegen(),
          tipp=tr("Tolerierungsberater: passende Maße und Toleranzen für die gewählten Flächen vorschlagen und anlegen"))
        A("funktion", tr("Funktion → Tolerierung …"), lambda: self.zeige_funktion(),
          tipp=tr("Funktionen der Flächen festlegen (Auflage, Zentrierung, Führung …): Bezugssystem und ISO-GPS-"
                  "Tolerierung vorschlagen"))
        A("kette2d", tr("2D-Toleranzkette …"), lambda: self.zeige_kette2d(),
          tipp=tr("Kette als Vektorzug in der Ebene (Längen und Winkel) von Hand aufbauen, linear und nichtlinear "
                  "rechnen und in die Toleranzkette übernehmen"))
        A("kette3d", tr("3D-Toleranzkette …"), lambda: self.zeige_kette3d(),
          tipp=tr("Kette aus Lagen im Raum (Verschiebungen und Drehungen mit Abmaßen) von Hand aufbauen, Kippungen "
                  "als Hebel erfassen und in die Toleranzkette übernehmen"))
        A("toleranzkette", tr("Toleranzkette …"), lambda: self.zeige_toleranzkette(),
          tipp=tr("Maßkette aus gewählten Maßen: Worst Case, statistisch (RSS) und Monte Carlo"))
        A("analyse", tr("Analyse …"), self.zeige_analyse_leiste,
          tipp=tr("Entformungsschräge, Krümmungsradius oder Wandstärke als Farbkarte"))
        A("toleranzzone", tr("Toleranzzone zeigen"), lambda: self._zone_aktualisieren(self.pmi.gewaehlte()),
          pruefbar=True, tipp=tr("Zonen der gewählten Toleranzen (oder der PMI an den gewählten Flächen) als "
                                 "Hüllgeometrie: gelb Zone, magenta Bonus bei Ⓜ/Ⓛ, türkis Raum der Fläche "
                                 "(schmale Zonen überhöht)"))
        A("toleranzzonen_alle", tr("Alle Toleranzzonen zeigen"), lambda: self._zone_aktualisieren(self.pmi.gewaehlte()),
          pruefbar=True, tipp=tr("Zonen aller Toleranzen und Maße des Modells, mit Allgemeintoleranzen (violett)"))
        A("allgemeintoleranzen", tr("Allgemeintoleranzen …"), self.waehle_allgemeintoleranzen,
          tipp=tr("ISO 2768 / ISO 22081 für Flächen ohne eigene Angabe (Zonendarstellung)"))
        A("allgemein_zeigen", tr("Allgemeintoleranzen zeigen"), self._allgemein_umschalten, pruefbar=True,
          tipp=tr("Zonen der Allgemeintoleranzen (violett) an Flächen ohne eigene Angabe: alle oder an der "
                  "Auswahl"))
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
        A("zeichnung_schnitt", tr("Zeichnung: Schnittansichten …"), lambda: self.exportiere_zeichnung("schnitt"),
          tipp=tr("Je Schnittebene (festgehaltene und aktuelle) eine Ansicht auf die Schnittfläche, schraffiert – als "
                  "PDF, SVG oder DXF"))
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
        A("animation", tr("Weiche Kamerafahrten"), self._animation, pruefbar=True,
          tipp=tr("Standardansichten und Würfelklicks fahren weich an statt zu springen"))
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
        A("grafik_erzeugt", tr("Erzeugte PMI-Darstellung zeigen"), self._grafik_umschalten, pruefbar=True,
          tipp=tr("Aus der Semantik erzeugte Beschriftungen (PMI ohne Grafik in der Datei) ein/aus"))
        self.aktionen["grafik_erzeugt"].setChecked(True)
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
        A("schnitt_merken", tr("Schnittebene festhalten"), self._schnitt_merken,
          tipp=tr("Aktuelle Schnittebene behalten und eine weitere wählen (bis zu drei Ebenen)"))
        A("schnitt_kette", tr("Nur gemeinsamen Bereich wegschneiden"), self._schnitt_kette, pruefbar=True,
          tipp=tr("Mehrere Schnittebenen schneiden nur den Bereich weg, den alle wegschneiden (z. B. Viertelschnitt)"))
        A("schnitt_loeschen", tr("Festgehaltene Schnittebenen entfernen"), self._schnitt_ebenen_loeschen)
        A("schnitt_kontur", tr("Schnittkontur exportieren …"), lambda: self.exportiere_schnittkontur(),
          tipp=tr("Kontur der Schnittebenen als SVG, DXF oder PDF"))
        A("schnittbox", tr("Schnittbox um Auswahl"), self._schnittbox, pruefbar=True,
          tipp=tr("Nur den Bereich um die gewählten Flächen zeigen, alles außerhalb der Box ist weggeschnitten"))
        A("alle_zeigen", tr("Alle Teile zeigen"), self.baum.alle_zeigen, "Shift+H",
          tipp=tr("Ausgeblendete Teile wieder zeigen"))
        A("isolieren", tr("Gewählte Teile isolieren"), self._isolieren, "I")
        A("transparent", tr("Gewählte Teile transparent"), self._transparent, "T")
        A("fokus", tr("Auswahl hervorheben (Rest durchscheinend)"), self._fokus_umschalten, "Shift+T", pruefbar=True,
          tipp=tr("Alles außer den gewählten Flächen, PMI und Teilen wird durchscheinend"))
        A("pmi_suche", tr("PMI suchen"), self._suche_fokus, QtGui.QKeySequence.StandardKey.Find)
        A("pmi_export", tr("PMI exportieren (CSV) …"), lambda: self.exportiere_pmi(),
          tipp=tr("Alle PMI mit Werten, Bezügen, Flächen und Ansichten als Tabelle"))
        A("pmi_pruefen", tr("PMI prüfen …"), self.pruefe_pmi,
          tipp=tr("Unbenutzte oder fehlende Bezüge, PMI ohne Fläche, Doppelte und andere Unstimmigkeiten"))
        A("aenderungen_export", tr("Änderungen exportieren (CSV) …"), lambda: self.exportiere_aenderungen(),
          tipp=tr("Änderungsliste des Vergleichs mit Alt/Neu als Tabelle"))
        A("ansicht_vor", tr("Nächste gespeicherte Ansicht"), lambda: self.ansichten.gehe(+1), "PgDown")
        A("ansicht_zurueck", tr("Vorherige gespeicherte Ansicht"), lambda: self.ansichten.gehe(-1), "PgUp")
        A("zusammenbau", tr("Zusammenbau und Freiheitsgrade …"), self.zeige_zusammenbau,
          tipp=tr("Teile über Flächenpaare fangen (Ebene auf Ebene, koaxial), offene Freiheitsgrade zeigen, Wiggle"))
        A("kollision", tr("Kollisionen und Abstände …"), self.zeige_kollision_leiste,
          tipp=tr("Durchdringungen, Kontakte und Abstände außerhalb eines Bands zwischen Teilen finden"))
        A("scan_pruefen", tr("Scan gegen Toleranzen prüfen …"), lambda: self.pruefe_scan(),
          tipp=tr("Netz (z. B. 3D-Scan) laden, automatisch ausrichten, Abweichungen zeigen und jede PMI bewerten"))
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
        sg = QtGui.QActionGroup(self)
        jetzt = skalierung(self.ein)
        for v in SKALEN:
            text = f"{v * 100:.0f} %" + ("  " + tr("(Standard)") if v == 1.0 else "")
            a = A(f"skala_{round(v * 100)}", text, lambda _=False, v=v: self.setze_skalierung(v), pruefbar=True,
                  modell=False, tipp=tr("Schrift und Bedienelemente größer oder kleiner (nach einem Neustart)"))
            a.setChecked(abs(v - jetzt) < 0.01)
            sg.addAction(a)
        A("anleitung", tr("Anleitung"), self.zeige_anleitung, QtGui.QKeySequence.StandardKey.HelpContents,
          modell=False)
        A("ueber", tr("Über 3DGmax"), self.zeige_ueber, modell=False)
        A("befehlssuche", tr("Befehl suchen …"), self.zeige_befehlssuche, "Ctrl+K", modell=False,
          tipp=tr("Alle Befehle nach Namen durchsuchen und ausführen"))
        A("gefuehrt_scan", tr("Geführt: Scan prüfen"), lambda: self.starte_fuehrung("scan"), modell=False,
          tipp=tr("Schritt für Schritt: Modell, Scan, Ausrichtung, Ergebnisse prüfen, Prüfbericht"))
        A("gefuehrt_spalt", tr("Geführt: Spalt messen"), lambda: self.starte_fuehrung("spalt"), modell=False,
          tipp=tr("Schritt für Schritt: Baugruppe, Teile verbinden, Spielräume, Messgröße, Soll, Ergebnis"))

    VERGLEICH_AKTIONEN = ("vergleich_beenden", "aenderungen_export", "pdf_vergleich", "pdf_pmi_aenderungen",
                          "manuell_ausrichten")

    def _baue_menues(self):
        mb = self.menuBar()
        a = self.aktionen
        m = mb.addMenu(tr("&Datei"))
        m.addAction(a["oeffnen"])
        m.addAction(a["modell_hinzufuegen"])
        m.addAction(a["neues_fenster"])
        m.addAction(a["in_neuem_fenster"])
        self.menue_zuletzt = m.addMenu(tr("Zuletzt verwendet"))
        self._beispiel_menue(m.addMenu(tr("Beispiele")))
        m.addSeparator()
        m.addAction(a["vergleichen"])
        m.addAction(a["ordnervergleich"])
        m.addAction(a["manuell_ausrichten"])
        m.addAction(a["vergleich_beenden"])
        m.addSeparator()
        m.addAction(a["projekt_speichern"])
        m.addAction(a["step_pmi_speichern"])
        me = m.addMenu(tr("Exportieren"))
        for n in ("pdf_ansichten", "merkmale_pdf", "pdf_messungen", "pdf_kommentare", "pdf_vergleich",
                  "pdf_pmi_aenderungen"):
            me.addAction(a[n])
        me.addSeparator()
        for n in ("zeichnung_blatt", "zeichnung_aktuell", "zeichnung_ansichten", "zeichnung_schnitt", "zeichnung_pmi"):
            me.addAction(a[n])
        self._menue_blattformat(me.addMenu(tr("Blattformat")))
        me.addSeparator()
        for n in ("pmi_export", "merkmale_csv", "kommentare_csv", "aenderungen_export"):
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
        m.addAction(a["animation"])
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
        m.addAction(a["grafik_erzeugt"])
        m.addAction(a["ballone"])
        m.addAction(a["fokus"])
        m.addAction(a["toleranzzone"])
        m.addAction(a["toleranzzonen_alle"])
        m.addAction(a["allgemein_zeigen"])
        m.addAction(a["allgemeintoleranzen"])
        m.addAction(a["hilfsgeometrie"])
        m.addSeparator()
        ms = m.addMenu(tr("Schnitt"))
        for n in ("schnitt_aus", "schnitt_x", "schnitt_y", "schnitt_z", "schnitt_auswahl", "schnitt_blick"):
            ms.addAction(a[n])
        ms.addSeparator()
        ms.addAction(a["schnittbox"])
        ms.addSeparator()
        ms.addAction(a["schnitt_umkehren"])
        ms.addAction(a["schnitt_merken"])
        ms.addAction(a["schnitt_kette"])
        ms.addAction(a["schnitt_loeschen"])
        ms.addSeparator()
        ms.addAction(a["schnitt_kontur"])
        m.addSeparator()
        mt = m.addMenu(tr("Farbschema"))
        for n in ("thema_auto", "thema_hell", "thema_dunkel"):
            mt.addAction(a[n])
        msp = m.addMenu(tr("Sprache"))
        for n in ("sprache_auto", "sprache_de", "sprache_en"):
            msp.addAction(a[n])
        mg = m.addMenu(tr("Größe der Oberfläche"))
        for v in SKALEN:
            mg.addAction(a[f"skala_{round(v * 100)}"])
        m = mb.addMenu(tr("&Modell"))
        m.addAction(a["eigenschaften"])
        m.addAction(a["stueckliste"])
        m.addAction(a["explosion"])
        m.addAction(a["analyse"])
        m.addAction(a["toleranzkette"])
        m.addAction(a["kette2d"])
        m.addAction(a["kette3d"])
        m.addAction(a["funktion"])
        m.addAction(a["pmi_anlegen"])
        m.addAction(a["kommentar"])
        mn = m.addMenu(tr("Norm"))
        for n in ("norm_auto", "norm_iso", "norm_asme"):
            mn.addAction(a[n])
        m.addSeparator()
        for n in ("alle_zeigen", "isolieren", "transparent", "teil_ausblenden", "teil_isolieren", "auswahl_aufheben"):
            m.addAction(a[n])
        m.addSeparator()
        m.addAction(a["pmi_suche"])
        m.addAction(a["pmi_pruefen"])
        m = mb.addMenu(tr("&Werkzeuge"))
        m.addAction(a["messen"])
        m.addAction(a["messen_ende"])
        m.addSeparator()
        m.addAction(a["zusammenbau"])
        m.addAction(a["kollision"])
        m.addAction(a["scan_pruefen"])
        m.addAction(a["verzahnung"])
        m.addAction(a["messergebnisse"])
        self.menue_fenster = mb.addMenu(tr("&Fenster"))
        for d in (self.dock_baum, self.dock_ansichten, self.dock_pmi, self.dock_messen, self.dock_analyse,
                  self.dock_kommentare, self.dock_aenderungen, self.dock_scan, self.dock_kollision,
                  self.dock_zusammenbau):
            self.menue_fenster.addAction(d.toggleViewAction())
        self.menue_fenster.addSeparator()
        self.menue_fenster.addAction(a["kameras_koppeln"])
        m = mb.addMenu(tr("&Hilfe"))
        for n in ("befehlssuche", "gefuehrt_scan", "gefuehrt_spalt", "anleitung", "ueber"):
            m.addAction(a[n])
        self._fuelle_zuletzt()

    def _baue_leiste(self):
        """Eine Werkzeugzeile: ganz links Oeffnen/Vergleichen, dann die Arbeitsbereiche, Ansicht und Darstellung; was
        nicht passt, liegt unter ». Schnitt und Explosion (mit Reglern) stehen oben in der Leiste Struktur, Messen in
        der Leiste Messen."""
        from .arbeitsbereiche import Bereichsleiste
        from .fluss import FlussLayout
        tb = self.addToolBar(tr("Werkzeuge"))
        tb.setObjectName("werkzeuge")
        tb.setMovable(False)
        tb.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        a = self.aktionen
        datei = QtWidgets.QToolButton()  # ganz links: Oeffnen (Klick) und Vergleichen (Menue) in einem Knopf
        datei.setDefaultAction(a["oeffnen"])
        datei.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        datei_menue = QtWidgets.QMenu(datei)
        datei_menue.addAction(a["oeffnen"])
        datei_menue.addAction(a["vergleichen"])
        datei.setMenu(datei_menue)
        datei.setToolTip(tr("Modell öffnen; Pfeil: auch zwei Stände vergleichen"))
        self.datei_knopf = datei
        tb.addWidget(datei)
        tb.addSeparator()
        self.bereiche = Bereichsleiste()
        self.bereiche.gewaehlt.connect(self.setze_arbeitsbereich)
        tb.addWidget(self.bereiche)
        tb.addSeparator()
        tb.addAction(a["alles"])  # Standardansichten: Ansichtswuerfel in der 3D-Ansicht und Menue Ansicht
        darstellung = QtWidgets.QToolButton()  # drei Darstellungen in einem Knopf, er nennt die aktive
        darstellung.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        darstellung.setToolTip(tr("Darstellung: schattiert mit Kanten, schattiert oder Drahtmodell"))
        menue = QtWidgets.QMenu(darstellung)
        for n in ansicht3d.DARSTELLUNGEN:
            menue.addAction(a["darstellung_" + n])
            a["darstellung_" + n].toggled.connect(
                lambda an, n=n: an and darstellung.setText(a["darstellung_" + n].text().replace("&", "")))
        darstellung.setMenu(menue)
        darstellung.setText(next(a["darstellung_" + n].text().replace("&", "") for n in ansicht3d.DARSTELLUNGEN
                                 if a["darstellung_" + n].isChecked()))
        self.darstellung_knopf = darstellung
        tb.addWidget(darstellung)
        tb.addAction(a["grafik"])  # Messen schaltet die Leiste Messen (Knopf oben in ihr, Taste M)
        messen = QtWidgets.QToolButton()  # Schalter Messen oben in der Leiste Messen
        messen.setDefaultAction(a["messen"])
        self.messen.layout().insertWidget(1, messen, 0, QtCore.Qt.AlignmentFlag.AlignLeft)  # unter dem Satz zum Zweck
        # Leiste zu (x, Menue, anderer Arbeitsbereich): Messen aus
        self.dock_messen.toggleViewAction().toggled.connect(
            lambda an: an or not a["messen"].isChecked() or a["messen"].trigger())
        # Schnitt und Explosion: Zeile oben in der Leiste Struktur (Ansicht der Teile, wie die Sichtbarkeit im Baum)
        zeile = FlussLayout(self._struktur_werkzeuge)
        knopf = QtWidgets.QToolButton()
        knopf.setText(tr("Schnitt"))
        knopf.setToolTip(tr("Schnittebene wählen"))
        knopf.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menue = QtWidgets.QMenu(knopf)
        for n in ("schnitt_aus", "schnitt_x", "schnitt_y", "schnitt_z", "schnitt_auswahl", "schnitt_blick",
                  "schnitt_umkehren", "schnittbox"):
            menue.addAction(a[n])
        knopf.setMenu(menue)
        self.schnitt_knopf = knopf
        zeile.addWidget(knopf)
        self.schnitt_regler = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.schnitt_regler.setRange(0, 1000)
        self.schnitt_regler.setValue(500)
        self.schnitt_regler.setFixedWidth(130)
        self.schnitt_regler.setToolTip(tr("Lage der Schnittebene"))
        self.schnitt_regler.valueChanged.connect(lambda _: self._schnitt(self._schnitt_achse))
        zeile.addWidget(self.schnitt_regler)
        self.schnitt_regler_aktion = self.schnitt_regler  # sichtbar nur bei aktivem Schnitt
        self.schnitt_regler.setVisible(False)
        self._schnitt_achse = None
        explosion = QtWidgets.QToolButton()
        explosion.setDefaultAction(a["explosion"])
        zeile.addWidget(explosion)
        self.explosion_regler = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.explosion_regler.setRange(0, 100)
        self.explosion_regler.setValue(50)
        self.explosion_regler.setFixedWidth(110)
        self.explosion_regler.setToolTip(tr("Abstand der Teile in der Explosionsansicht"))
        self.explosion_regler.valueChanged.connect(lambda w: self.ansicht.setze_explosion(w / 100.0))
        self.explosion_regler.sliderReleased.connect(self._explosion_einpassen)
        zeile.addWidget(self.explosion_regler)
        self.explosion_regler_aktion = self.explosion_regler  # sichtbar nur bei aktiver Explosionsansicht
        self.explosion_regler.setVisible(False)
        self.explosion_achse = QtWidgets.QComboBox()
        for daten, text in ((None, tr("radial")), ("x", tr("entlang X")), ("y", tr("entlang Y")), ("z", tr("entlang Z"))):
            self.explosion_achse.addItem(text, daten)
        self.explosion_achse.setToolTip(tr("Richtung der Explosion: von der Mitte weg oder nur entlang einer Achse"))
        self.explosion_achse.currentIndexChanged.connect(lambda _i: self.ansicht.setze_explosion_achse(
            self.explosion_achse.currentData()))
        zeile.addWidget(self.explosion_achse)
        self.explosion_achse_aktion = self.explosion_achse
        self.explosion_achse.setVisible(False)

    def _verbinde(self):
        self.start.oeffnen.connect(self.oeffnen)
        self.start.vergleichen.connect(lambda: self.starte_vergleich())
        self.start.gefuehrt_menue.addAction(self.aktionen["gefuehrt_scan"])
        self.start.gefuehrt_menue.addAction(self.aktionen["gefuehrt_spalt"])
        self._beispiel_menue(self.start.beispiele_menue)
        self.pmi.gewaehlt.connect(self._pmi_gewaehlt)
        self.pmi.gewaehlt.connect(lambda pmi: pmi and self.inspektor_zeigen("pmi"))
        self.pmi.filter_geaendert.connect(self._pmi_filter)
        self.pmi.befehl.connect(self._pmi_befehl)
        self.ansichten.gewaehlt.connect(self._ansicht_gewaehlt)
        self.ansichten.merken.connect(lambda: self.merke_ansicht())
        self.kommentare.neu.connect(lambda: self.neuer_kommentar())
        self.kommentare.geaendert.connect(self._kommentare_zeigen)
        self.kommentare.gewaehlt.connect(self._kommentar_gewaehlt)
        self.ansichten.entfernen.connect(self._ansicht_entfernen)
        self.ansicht.flaeche_gewaehlt.connect(self._flaeche_gewaehlt)
        self.ansicht.pmi_gewaehlt.connect(self._grafik_pmi_gewaehlt)
        self.ansicht.meldung.connect(lambda t: self.statusBar().showMessage(t, 5000))
        self.ansicht.auswahl_geaendert.connect(self._schnell_auswahl)
        self.ansicht.auswahl_geaendert.connect(lambda _f: self._zone_aktualisieren(self.pmi.gewaehlte()))
        self.ansicht.sichtbarkeit_geaendert.connect(self._sichtbarkeit_zonen)
        # der Baum gehoert im Vergleichsmodus "Alt" zur Ansicht des alten Stands
        self.baum.sichtbar_geaendert.connect(lambda n, an: self._baum_ansicht().knoten_sichtbar(n, an))
        self.baum.isolieren.connect(lambda n: self._baum_ansicht().isoliere(n))
        self.baum.transparent.connect(lambda n, an: self._baum_ansicht().knoten_transparent(n, an))
        self.baum_alt.sichtbar_geaendert.connect(lambda n, an: self.ansicht_alt and self.ansicht_alt.knoten_sichtbar(n, an))
        self.baum_alt.isolieren.connect(lambda n: self.ansicht_alt and self.ansicht_alt.isoliere(n))
        self.baum_alt.transparent.connect(
            lambda n, an: self.ansicht_alt and self.ansicht_alt.knoten_transparent(n, an))
        self.baum.baum.itemSelectionChanged.connect(
            lambda: self.ansicht.setze_fokus(self.ansicht.fokus, self.baum.gewaehlte_blaetter()))
        self.baum.baum.itemSelectionChanged.connect(lambda: self.inspektor_zeigen("baum"))
        self.ansicht.auswahl_geaendert.connect(lambda formen: self.inspektor_zeigen("3d" if formen else None))
        self.ansicht.element_gewaehlt.connect(self.messen.element)
        self.messen.elemente_zeigen.connect(lambda formen: self.ansicht.setze_auswahl(formen))
        self.ansicht.kontextmenue.connect(self._kontextmenue_3d)
        self.messen.messungen_geaendert.connect(self.ansicht.zeige_messungen)
        self.messen.modus_geaendert.connect(self._messmodus)
        self.messen.koerper_von = self._koerper_von
        self.messen.toleranz = self.ansicht.fang_toleranz
        self.aenderungen.gewaehlt.connect(self._aenderung_gewaehlt)
        self.aenderungen.abschliessen.connect(self.schliesse_pruefung_ab)
        self.aenderungen.beenden.connect(self.beende_vergleich)
        self.aenderungen.vergleich_starten.connect(lambda: self.starte_vergleich())
        self.aenderungen.karte.connect(self.zeige_farbkarte)
        self.aenderungen.material.connect(self.zeige_material)
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
        self._schnitt_aktionen()
        self.stapel.setCurrentWidget(self.mitte if da else self.start)
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

    def lade(self, pfad: str, warten: bool = False, zusaetze=()):
        """Laedt im Hintergrund; warten=True blockiert bis fertig (Tests, Selbsttest); zusaetze: weitere Dateien
        [(Pfad, Verschiebung)], die dazukommen (Projekt mit hinzugefuegten Modellen)."""
        if pfad.lower().endswith(".3dgmax"):
            return self.oeffne_projekt(pfad, warten)
        if pfad.lower().endswith(".3dgkette"):
            return self.oeffne_kette(pfad, warten)
        self.lade_abbrechen()
        self.statusBar().showMessage(tr("Lade {} …").format(os.path.basename(pfad)))
        self.fortschritt.show()
        self.abbrechen.show()
        self._lader = Lader(pfad, self, zusaetze)
        self._lader.stand.connect(lambda t: self.statusBar().showMessage(t))
        self._lader.fertig.connect(self._geladen)
        self._lader.fehler.connect(self._ladefehler)
        self._lader.start()
        if warten:
            self._lader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def _aufgabe(self, lader, text: str = ""):
        """Hintergrundrechnung in der Statuszeile anzeigen: Laufbalken (Prozent, wenn gemeldet), Abbrechen."""
        self._aufgaben.append(lader)
        if text:
            self.statusBar().showMessage(text)
        self.fortschritt.setRange(0, 0)
        self.fortschritt.show()
        self.abbrechen.show()
        lader.finished.connect(lambda l=lader: self._aufgabe_ende(l))

    def _prozent(self, p: int):
        self.fortschritt.setRange(0, 100)
        self.fortschritt.setValue(p)

    def _aufgabe_ende(self, lader):
        if lader in self._aufgaben:
            self._aufgaben.remove(lader)
        self._laufbalken_pruefen()

    def _laufbalken_pruefen(self):
        """Laufbalken ausblenden, sobald nichts mehr im Hintergrund rechnet."""
        laeuft = self._aufgaben or any(x is not None and x.isRunning()
                                       for x in (self._lader, getattr(self, "_vlader", None)))
        if not laeuft:
            self.fortschritt.hide()
            self.abbrechen.hide()
            self.fortschritt.setRange(0, 0)

    def _aufgaben_abbrechen(self) -> bool:
        """Laufende Rechnungen verwerfen; die Threads enden beim naechsten Fortschrittsschritt."""
        for lader in self._aufgaben:
            lader.abgebrochen = True
        da = bool(self._aufgaben)
        self._aufgaben = []
        self._karten_lader = None
        self.analyse.start.setEnabled(True)
        self.kollision.start.setEnabled(True)
        return da

    def lade_abbrechen(self):
        if self._aufgaben_abbrechen():
            self.statusBar().showMessage(tr("Abgebrochen"), 4000)
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
        self._laufbalken_pruefen()
        self.zeige_ergebnis(erg)
        self._projekt_messungen()
        self._danach()

    def zeige_ergebnis(self, erg, vergleich=None):
        self.scan_aus()  # die Scanpruefung gehoert zum vorigen Modell
        if vergleich is None and self.vergleich is not None:
            self.beende_vergleich(neu_zeigen=False)
        if self.aktionen["explosion"].isChecked():
            self.aktionen["explosion"].setChecked(False)
            self._explosion_umschalten()
        if self.aktionen["schnittbox"].isChecked():
            self.aktionen["schnittbox"].setChecked(False)
            self.ansicht.schnittbox(None)
        if self.erg is not None and erg.pfad != self.erg.pfad:
            self.kommentare.setze([])  # Kommentare gehoeren zum vorigen Modell
            if getattr(self, "_kette", None) is not None:
                self._kette.leeren()  # Kettenglieder verweisen auf PMI des vorigen Modells
            self._allgemein = None  # Allgemeintoleranzen gehoeren zum vorigen Modell
            self.kollision_aus()
            self._wiggle(None)
            self.zusammenbau.wiggle_an.setChecked(False)
            self._frei = None  # 3D-Griff und Freiheitsgrade gehoeren zum vorigen Modell
            self._manipulator_zeigen()
            self.baugruppe.zuruecksetzen()
            self.zusammenbau.zeige(self.baugruppe, {})
            self.ansicht.setze_teil_lagen({})
            self.aktionen["allgemein_zeigen"].setChecked(False)
        if vergleich is None and self.ansicht.abweichung is not None:
            self.ansicht.zeige_analyse(None)  # Analyse gehoert zum alten Modell
        self.erg = erg
        self.ansicht.setze_ansicht_schnitt([])  # Schnitt gehoert zur Ansicht des vorigen Modells
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
        self._starte_vorschau()
        self._merke_zuletzt(erg.pfad)
        n = len(erg.pmi)
        self.statusBar().showMessage(tr("{} geladen: {} Flächen, {} PMI, {} Ansichten ({:.1f} s)").format(
            os.path.basename(erg.pfad), len(erg.modell.flaechen), n, len(erg.ansichten), erg.modell.ladezeit), 8000)

    def _danach(self):
        """Naechster Schritt eines Beispiels, sobald das Modell bzw. der Vergleich steht."""
        schritt, self._nach_laden = getattr(self, "_nach_laden", None), None
        if schritt is not None:
            schritt()

    def zeige_befehlssuche(self):
        """Befehlssuche oben mittig ueber dem Fenster (Strg/⌘+K)."""
        from .befehle_ui import BefehlsSuche
        d = BefehlsSuche(self.menuBar(), self)
        mitte = self.mapToGlobal(QtCore.QPoint(self.width() // 2, 0))
        d.move(mitte.x() - d.width() // 2, mitte.y() + 60)
        self._befehlssuche = d
        d.open()
        d.eingabe.setFocus()
        return d

    def _beispiel_menue(self, menue):
        from ..kern import beispiele
        for b in beispiele.BEISPIELE:
            a = menue.addAction(tr(b.titel), lambda _=False, n=b.name: self.oeffne_beispiel(n))
            a.setToolTip(tr(b.text))
            a.setEnabled(beispiele.dateien(b) is not None)
        menue.setToolTipsVisible(True)

    def oeffne_beispiel(self, name: str, warten: bool = False) -> bool:
        """Beispiel oeffnen und vorfuehren (Dateien aus kern.beispiele)."""
        from ..kern import beispiele
        b = beispiele.finde(name)
        pfade = beispiele.dateien(b)
        if pfade is None:
            self.statusBar().showMessage(tr("Dateien des Beispiels nicht gefunden"), 6000)
            return False
        text = tr("Beispiel: {}").format(tr(b.text))
        if name == "kette_getriebe":  # Kettendatei laedt ihr Modell selbst
            self.oeffne_kette(pfade[0], warten)
            self.statusBar().showMessage(text, 20000)
            return True
        if name == "kette2d":  # ohne Modell
            self.zeige_kette2d().lade_vorlage("hebel")
            self.statusBar().showMessage(text, 20000)
            return True

        def zeigen(*schritte):
            def weiter():
                for s in schritte:
                    s()
                self.statusBar().showMessage(text, 20000)
            return weiter
        vergleich = {"alt": pfade[0], "neu": pfade[-1], "toleranz": 0.01, "suchweite": 2.0}
        if name in ("vergleich_pmi", "vergleich_geo", "baugruppe"):
            schritte = [lambda: self.aenderungen.karte_an.setChecked(True)] if name == "vergleich_geo" else []
            self._nach_laden = zeigen(*schritte)
            self.starte_vergleich(vergleich, warten)
            return True
        schritte = {
            "pmi": [lambda: self.ansichten.liste.setCurrentRow(1)],
            "pruefen": [self.pruefe_pmi],
            "zonen": [self._beispiel_zonen],
            "schnittansicht": [lambda: self.ansichten.liste.setCurrentRow(1), lambda: self.ansicht.standard("iso")],
            "scan": [lambda: self.pruefe_scan(pfade[1], warten)],
            "kette": [self._beispiel_kette],
            "kollision": [lambda: self._beispiel_kollision(warten)],
            "zusammenbau": [self._beispiel_zusammenbau],
            "variation": [self._beispiel_variation],
            "funktion": [self._beispiel_funktion],
            "messen": [lambda: self.aktionen["messen"].isChecked() or self.aktionen["messen"].trigger()],
            "analyse": [lambda: (self.zeige_analyse_leiste(), self.ansicht.standard("iso"),
                                 self.starte_analyse("entformung", {"richtung": "+z", "mindest": 1.0}, warten))],
            "merkmale": [lambda: self.aktionen["ballone"].isChecked() or self.aktionen["ballone"].trigger()],
            "kette3d": [self._beispiel_variation, lambda: self.messgroesse_als_kette3d(2)],
        }[name]
        self._nach_laden = zeigen(*schritte)
        self.lade(pfade[0], warten)
        return True

    def _beispiel_funktion(self):
        """FTC-10: groesste ebene Flaeche als Auflage, groesste Bohrung senkrecht dazu als Zentrierung, eine weitere
        Bohrung als Verdrehsicherung, eine Seitenflaeche als Anschlag; Bezuege vorschlagen."""
        from ..kern import funktion as fu
        m = self.erg.modell
        geo = {i: g for i in range(len(m.flaechen)) if (g := fu._geometrie(m.flaechen[i])) is not None}
        ebenen = sorted((i for i in geo if geo[i]["art"] == "ebene"), key=lambda i: -geo[i]["inhalt"])
        auflage = ebenen[0]
        n = geo[auflage]["richtung"]
        bohrungen = sorted((i for i in geo if geo[i]["art"] == "zylinder" and geo[i]["bohrung"]
                            and fu._parallel(geo[i]["richtung"], n)), key=lambda i: -geo[i]["groesse"])
        seite = next((i for i in ebenen if fu._senkrecht(geo[i]["richtung"], n)), None)
        w = self.zeige_funktion()
        w.setze_rolle([auflage], "auflage")
        if bohrungen:
            w.setze_rolle([bohrungen[0]], "zentrierung")
        if len(bohrungen) > 1:
            w.setze_rolle([bohrungen[-1]], "verdrehsicherung")
        if seite is not None:
            w.setze_rolle([seite], "anschlag")
        w.zeige_bezuege()

    def _beispiel_zonen(self):
        from ..kern.toleranzzone import Allgemein
        self._allgemein = Allgemein("m", "K")
        self.aktionen["toleranzzonen_alle"].setChecked(True)
        self.aktionen["allgemein_zeigen"].setChecked(True)
        self._allgemein_umschalten()

    def _beispiel_kollision(self, warten: bool):
        self.kollision.mindest.setValue(1.0)
        self._nach_laden = lambda: self.kollision.tabelle.selectRow(0)  # ersten Befund zeigen
        self.starte_kollision(self.kollision.werte(), warten)

    def _beispiel_zusammenbau(self):
        from ..kern.verbindung import flaeche_im_teil
        knoten = {k.nummer: k for k in self.erg.baum.blaetter()}
        schraube = next(k.nummer for k in self.erg.baum.blaetter() if k.name.startswith("Schraube"))
        fl = lambda t, i: flaeche_im_teil(knoten[t].form, i, self.erg.modell)  # noqa: E731
        deckel = next(k.nummer for k in knoten.values() if k.name == "Deckel")
        platte = next(k.nummer for k in knoten.values() if k.name == "Grundplatte")
        # Flaechen der Testbaugruppe: Kopfunterseite 18, Deckeloberseite 15, Schaft 19, Bohrung 6
        for paar in (((schraube, 18), (deckel, 15)), ((schraube, 19), (platte, 6))):
            self.ansicht.setze_auswahl([fl(*paar[0]), fl(*paar[1])], [paar[0][0], paar[1][0]])
            self.verbinde_auswahl()
        self.ansicht.setze_auswahl([])
        self.zeige_zusammenbau()
        self.zusammenbau.teile.selectRow(self.zusammenbau._teil_nummern.index(schraube))
        self.zusammenbau.wiggle_an.setChecked(True)

    def _beispiel_variation(self):
        """Deckel auf Grundplatte, zwei Schrauben; Kopfueberstand und Buendigkeit der Koepfe mit Soll."""
        from ..kern import baugruppe_mass as bm
        from ..kern.verbindung import flaeche_im_teil
        knoten = {k.nummer: k for k in self.erg.baum.blaetter()}
        fl = lambda t, i: flaeche_im_teil(knoten[t].form, i, self.erg.modell)  # noqa: E731
        nr = {k.name: k.nummer for k in knoten.values()}
        schrauben = sorted(k.nummer for k in knoten.values() if k.name.startswith("Schraube"))[:2]
        deckel, platte = nr["Deckel"], nr["Grundplatte"]
        # Flaechen der Testbaugruppe: Deckel unten 14 / oben 15, Platte oben 2, Bohrungen 6 und 7, Kopf unten 18 /
        # oben 17, Schaft 19
        paare = [((deckel, 14), (platte, 2))]
        for s, loch in zip(schrauben, (6, 7)):
            paare += [((s, 18), (deckel, 15)), ((s, 19), (platte, loch))]
        for a, b in paare:
            self.ansicht.setze_auswahl([fl(*a), fl(*b)], [a[0], b[0]])
            self.verbinde_auswahl()
        self.baugruppe.setze_toleranz(1, 0.05, 0.0005, tr("Beispiel"))
        for v in self.baugruppe.verbindungen:
            if v.art == "eben" and v.nummer != 1:
                self.baugruppe.setze_toleranz(v.nummer, 0.02, 0.001, tr("Beispiel"))
        for a, b, soll in (((schrauben[0], 17), (deckel, 15), "3,95 … 4,05"),
                           ((schrauben[0], 17), (schrauben[1], 17), "-0,05 … 0,05")):
            m = self.baugruppe.neue_messgroesse(a[0], fl(*a), a[1], b[0], fl(*b), b[1])
            m.soll_min, m.soll_max = bm.lies_soll(soll)
        self.ansicht.setze_auswahl([])
        self.zeige_zusammenbau()
        self.zusammenbau.reiter.setCurrentIndex(1)
        self.zusammenbau.masse.selectRow(1)

    def _beispiel_kette(self):
        from ..kern import toleranzkette as tk
        k = self.zeige_toleranzkette()
        self.pmi.waehle(lambda p: p.art == "mass" and p.nennwert is not None and not tk.ist_winkel(p)
                        and not any(t in (p.typ or "") for t in ("Diameter", "Radius")))
        self._kette_uebernehmen(+1)
        k.cp.setValue(1.33)

    def _ladefehler(self, text):
        self._nach_laden = None
        self._lader = None
        self._vlader = None
        self._laufbalken_pruefen()
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
        if any(ablegbar(u.toLocalFile()) for u in ev.mimeData().urls()):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for u in ev.mimeData().urls():
            if ablegbar(u.toLocalFile()):
                self.lade(u.toLocalFile())
                break

    # --- Auswahl ---

    # --- Schnellmessung ---

    def _schnell_aus(self) -> set[str]:
        wert = self.ein.value("schnellinfo_aus", []) or []
        return {wert} if isinstance(wert, str) else set(wert)  # QSettings liefert eine Einzelangabe als Text

    def starte_fuehrung(self, art: str):
        """Gefuehrter Ablauf "scan" (Scan pruefen) oder "spalt" (Spalt messen in der Baugruppenvariation)."""
        from ..kern import beispiele
        from .fuehrung import Schritt
        scan = lambda: getattr(self, "_scan", None)  # noqa: E731
        if art == "scan":
            self._ausrichtung_bestaetigt = False
            self._berichte_gespeichert.discard("scan")
            schritte = [
                Schritt("CAD-Modell öffnen", "Das Modell mit PMI öffnen, gegen das geprüft wird (STEP, QIF …). Zum "
                        "Ausprobieren: das Beispielmodell mit passendem Scan.", lambda: self.erg is not None,
                        "Beispiel öffnen", lambda: self.lade(beispiele.datei(beispiele.CTC01), warten=True)),
                Schritt("Scan öffnen", "Den Scan als Netz (STL, PLY, OBJ) oder Punktwolke (E57) wählen; er wird "
                        "ausgerichtet und je PMI bewertet.", lambda: scan() is not None,
                        "Scan öffnen …", self._fuehrung_scan_oeffnen),
                Schritt("Ausrichtung prüfen", "Im Modus Nebeneinander oder Vergleich ansehen, ob der Scan richtig "
                        "liegt. Sonst in der Leiste Scanprüfung ein Bezugssystem wählen und neu auswerten oder von "
                        "Hand ausrichten.", lambda: scan() is not None and self._ausrichtung_bestaetigt,
                        "Ausrichtung passt", self._fuehrung_ausrichtung_ok),
                Schritt("Ergebnisse prüfen", "Jedes Ergebnis ansehen (im Modell gezeigt) und als geprüft oder "
                        "abgelehnt markieren – Tasten G und A, bei Bedarf einen Kommentar.",
                        lambda: scan() is not None and self.scan.ergebnisse and self.scan.pruef_zaehler()["offen"] == 0,
                        "Prüfen starten", lambda: (self.dock_scan.raise_(), self.scan.pruefen_starten())),
                Schritt("Prüfbericht speichern", "Den Prüfbericht mit Farbkarte, Ergebnis und Prüfstatus je Merkmal "
                        "als PDF speichern.", lambda: "scan" in self._berichte_gespeichert,
                        "Prüfbericht (PDF) …", lambda: self.exportiere_scan_pdf())]
            name = "Geführt: Scan prüfen"
        else:
            self._berichte_gespeichert.discard("messgroessen")
            b = self.baugruppe
            schritte = [
                Schritt("Baugruppe öffnen", "Eine Baugruppe (STEP) öffnen. Zum Ausprobieren: die Testbaugruppe mit "
                        "Deckel, Grundplatte und Schrauben.", lambda: self.erg is not None,
                        "Beispiel öffnen", lambda: self.lade(beispiele.datei("baugruppe.stp"), warten=True)),
                Schritt("Teile verbinden", "Eine Fläche am Teil wählen, das sich bewegen soll, dann mit Strg/⌘ die "
                        "Gegenfläche am anderen Teil, und „Verbinden“ (Ebene auf Ebene, koaxial …).",
                        lambda: len(b.verbindungen) >= 1, "Zusammenbau öffnen", self._fuehrung_zusammenbau),
                Schritt("Spielräume prüfen", "In der Tabelle Verbindungen den Spielraum je Verbindung prüfen "
                        "(aus den Toleranzen der Flächen oder von Hand eintragen).",
                        lambda: any(v.toleranz > 0 for v in b.verbindungen), "Verbindungen zeigen",
                        lambda: (self._fuehrung_zusammenbau(), self.zusammenbau.reiter.setCurrentIndex(0))),
                Schritt("Messgröße anlegen", "Zwei Flächen an verschiedenen Teilen wählen (erst die gemessene, dann "
                        "mit Strg/⌘ die Bezugsfläche) und „Messgröße aus Auswahl“: Spalt, Bündigkeit oder Abstand.",
                        lambda: len(b.masse) >= 1, "Messgrößen zeigen",
                        lambda: (self._fuehrung_zusammenbau(), self.zusammenbau.reiter.setCurrentIndex(1))),
                Schritt("Soll eintragen", "In der Spalte Soll die Anforderung eintragen, z. B. 3,8 … 4,2 (ein Klick "
                        "in die getönte Zelle).", lambda: any(m.soll_min is not None or m.soll_max is not None
                                                             for m in b.masse), "Messgrößen zeigen",
                        lambda: (self._fuehrung_zusammenbau(), self.zusammenbau.reiter.setCurrentIndex(1))),
                Schritt("Ergebnis und Bericht", "Worst Case, Monte Carlo, Ampel und Beitragende ansehen und den "
                        "Bericht als PDF speichern.", lambda: "messgroessen" in self._berichte_gespeichert,
                        "Bericht (PDF) …", lambda: self.exportiere_messgroessen_pdf())]
            name = "Geführt: Spalt messen"
        self.fuehrung.setze(name, schritte)
        self.dock_fuehrung.show()
        self.dock_fuehrung.raise_()
        return self.fuehrung

    def _fuehrung_scan_oeffnen(self):
        from ..kern import beispiele
        # mit dem Beispielmodell gleich den Beispielscan vorschlagen, sonst Datei waehlen
        if self.erg is not None and os.path.basename(self.erg.pfad) == beispiele.CTC01:
            self.pruefe_scan(beispiele.datei("ctc01_scan_fehler.ply"))
        else:
            self.pruefe_scan("")

    def _fuehrung_ausrichtung_ok(self):
        self._ausrichtung_bestaetigt = True

    def _fuehrung_zusammenbau(self):
        self.bereiche.zeige("zusammenbau")
        self.zeige_zusammenbau()

    def inspektor_zeigen(self, quelle: str | None = None):
        """Inspektor nach der zuletzt geaenderten Auswahl: 3D (Flaechen/Kanten), Struktur (Teile) oder PMI-Liste."""
        from ..kern import schnellinfo
        if quelle is not None:
            self._inspektor_quelle = quelle
        quelle = getattr(self, "_inspektor_quelle", None)
        a = self.aktionen
        if self.erg is None:
            return self.inspektor.zeige("", [], [])
        if quelle == "3d" and self.ansicht.auswahl3d:
            formen = list(self.ansicht.auswahl3d)
            namen = {k.nummer: k.name for k in self.erg.baum.blaetter()}
            teile = sorted({namen.get(t, "") for t in self.ansicht.auswahl_teile if t is not None} - {""})
            idx = [i for i in (self.erg.modell.flaechen_index(f) for f in formen) if i is not None]
            pmi = [p for p in self.erg.pmi if p.flaechen & set(idx)]
            titel = (tr("{} Elemente").format(len(formen)) if len(formen) > 1 else
                     tr("Fläche {}").format(idx[0]) if idx else tr("Kante"))
            eigen = [(tr("Teil"), ", ".join(teile))] if teile else []
            eigen += schnellinfo.info(formen)
            eigen += [(tr("PMI an der Auswahl"), ", ".join(f"{p.nummer}: {p.wert_text()}" for p in pmi[:6]) +
                       (" …" if len(pmi) > 6 else ""))] if pmi else []
            befehle = [a[n] for n in ("zoom_auswahl", "normal_auswahl", "schnitt_auswahl", "teil_isolieren",
                                      "fokus", "teil_ausblenden")]
            if pmi:
                befehle.append(a["toleranzzone"])
            return self.inspektor.zeige(titel, eigen, befehle)
        if quelle == "pmi" and self.pmi.gewaehlte():
            pmi = self.pmi.gewaehlte()
            titel = (f"{pmi[0].nummer}: {pmi[0].wert_text()}" if len(pmi) == 1 else tr("{} PMI").format(len(pmi)))
            return self.inspektor.zeige(titel, schnellinfo.pmi_info(pmi), self._inspektor_pmi_aktionen(pmi))
        if quelle == "baum" and self.baum.gewaehlte_blaetter():
            nummern = self.baum.gewaehlte_blaetter()
            knoten = [k for k in self.erg.baum.blaetter() if k.nummer in nummern]
            titel = knoten[0].name if len(knoten) == 1 else tr("{} Teile").format(len(knoten))
            eigen = [(tr("Teile"), ", ".join(k.name for k in knoten[:8]) + (" …" if len(knoten) > 8 else ""))]
            return self.inspektor.zeige(titel, eigen, [a[n] for n in ("isolieren", "transparent", "fokus")])
        return self.inspektor.zeige("", [], [])

    def _inspektor_pmi_aktionen(self, pmi: list) -> list:
        """Befehle fuer gewaehlte PMI (eigene QActions, einmal angelegt)."""
        b = getattr(self, "_insp_pmi", None)
        if b is None:
            def aktion(text, tipp, slot):
                x = QtGui.QAction(text, self)
                x.setToolTip(tipp)
                x.triggered.connect(slot)
                return x
            b = self._insp_pmi = {
                "zoom": aktion(tr("Auf PMI zoomen"), tr("Ausschnitt auf die Flächen und die Darstellung der PMI"),
                               lambda: self._pmi_befehl("zoomen", self.pmi.gewaehlte())),
                "bearbeiten": aktion(tr("Bearbeiten …"), tr("Wert, Toleranz und Passung der PMI ändern"),
                                     lambda: self._pmi_befehl("bearbeiten", self.pmi.gewaehlte()[0])),
                "kette": aktion(tr("In die Toleranzkette (+)"), tr("Gewählte Maße als Glieder an die Toleranzkette "
                                                                    "anhängen"), lambda: self._kette_uebernehmen(+1)),
            }
        out = [b["zoom"], self.aktionen["toleranzzone"]]
        if len(pmi) == 1 and pmi[0].art in ("mass", "toleranz"):
            out.append(b["bearbeiten"])
        if any(p.art == "mass" and p.nennwert is not None for p in pmi):
            out.append(b["kette"])
        return out

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
        self._zone_aktualisieren(liste)  # danach: die Erklaerung der Zone ersetzt die Auswahlmeldung

    def _flaeche_gewaehlt(self, idx):
        """Nach einem Klick: PMI aller gewaehlten Flaechen in der Liste waehlen (nicht nur der zuletzt geklickten);
        hervorgehoben bleiben die Flaechen der PMI und die ganze 3D-Auswahl."""
        if self.erg is None or self.ansicht.szene is None:
            return
        modell = self.ansicht.szene.modell
        alle = {i for f in self.ansicht.auswahl3d if (i := modell.flaechen_index(f)) is not None}
        if not alle:
            self.pmi.waehle(lambda p: False)
            return
        n = self.pmi.waehle(lambda p: bool(alle & p.flaechen))
        self.ansicht.hebe_flaechen(self.ansicht.hervor | alle)
        text = tr("Fläche {}: {} PMI").format(next(iter(alle)), n) if len(alle) == 1 else \
            tr("{} Flächen gewählt: {} PMI").format(len(alle), n)
        self.statusBar().showMessage(text, 6000)

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

    def _zonen_je_instanz(self, formen: list, rollen: list, quellen: list) -> tuple[list, list]:
        """Zonen liegen an den Flaechen in Dateilage einer Instanz (die Flaechenliste kennt jede Flaeche nur einmal):
        je weiterer sichtbarer Instanz desselben Teils eine Kopie, dazu die Lage aus dem Zusammenbau. Die
        urspruengliche Instanz ist die, deren Flaeche gleich der Flaeche der Flaechenliste ist (Form und Lage)."""
        from OCC.Core.TopLoc import TopLoc_Location
        blaetter = [k for k in self.erg.baum.blaetter() if not k.hilfsgeometrie and k.form is not None]
        lagen = self.ansicht.teil_lagen
        if len(blaetter) < 2 and not lagen:
            return formen, rollen
        besitzer = self._flaechen_besitzer(blaetter)
        versteckt = self.ansicht.versteckt
        out_f, out_r = [], []
        for form, rolle, quelle in zip(formen, rollen, quellen):
            o = next((besitzer[i] for i in quelle if i in besitzer), None)
            if o is None:
                out_f.append(form)
                out_r.append(rolle)
                continue
            zurueck = o.form.Location().Inverted()
            for k in blaetter:
                if not k.form.IsPartner(o.form) or k.nummer in versteckt:
                    continue
                lage = k.form.Location().Multiplied(zurueck)
                if k.nummer in lagen:
                    lage = TopLoc_Location(ansicht3d.gp_trsf(lagen[k.nummer])).Multiplied(lage)
                out_f.append(form.Moved(lage))
                out_r.append(rolle)
        return out_f, out_r

    def _flaechen_besitzer(self, blaetter) -> dict:
        """Flaechenindex -> Blatt, dessen Flaeche genau die der Flaechenliste ist (gemerkt je Modell)."""
        gemerkt = getattr(self, "_besitzer", None)
        if gemerkt is not None and gemerkt[0] is self.erg:
            return gemerkt[1]
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        out = {}
        m = self.erg.modell
        for k in blaetter:
            ex = TopExp_Explorer(k.form, TopAbs_FACE)
            while ex.More():
                i = m.flaechen_index(ex.Current())
                if i is not None and i not in out and ex.Current().IsEqual(m.flaechen[i]):
                    out[i] = k
                ex.Next()
        self._besitzer = (self.erg, out)
        return out

    def _sichtbarkeit_zonen(self):
        """Alle Zonen folgen dem Aus-/Einblenden der Teile."""
        if self.aktionen["toleranzzonen_alle"].isChecked():
            self._zone_aktualisieren(self.pmi.gewaehlte())

    def _zone_aktualisieren(self, liste):
        """Toleranzzonen zeigen: alle (Schalter), sonst die gewaehlten PMI oder die PMI an gewaehlten Flaechen."""
        from ..kern import toleranzzone
        alle = self.aktionen["toleranzzonen_alle"].isChecked()
        if self.erg is None or not (alle or self.aktionen["toleranzzone"].isChecked()):
            self.ansicht.zeige_zone([])
            return
        allgemein = self._allgemein if self.aktionen["allgemein_zeigen"].isChecked() else None
        nur = None  # Flaechen fuer die Allgemeintoleranzen (None: alle ohne eigene Angabe)
        sichtbar = self.ansicht.sichtbare_flaechen()  # ausgeblendete Teile zeigen keine Zonen
        if alle:
            liste = list(self.erg.pmi) if sichtbar is None else [
                p for p in self.erg.pmi if p.flaechen & sichtbar or (not p.flaechen and (
                    getattr(p, "teilformen", None) or getattr(p, "ganzes_teil", False)))]
            nur = sichtbar
        elif not liste and self.ansicht.auswahl3d:
            nur = {i for f in self.ansicht.auswahl3d for i in [self.erg.modell.flaechen_index(f)] if i is not None}
            liste = [p for p in self.erg.pmi if p.flaechen & nur]
        else:
            allgemein = None  # gewaehlte PMI: nur deren Zonen
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        box = Bnd_Box()
        brepbndlib.Add(self.erg.modell.form, box)
        x0, y0, z0, x1, y1, z1 = box.Get()
        mindest = max(x1 - x0, y1 - y0, z1 - z0) / 250  # schmalere Zonen werden ueberhoeht
        schluessel = (id(self.erg), repr(allgemein), tuple(p.wert_text() for p in self.erg.pmi),
                      None if sichtbar is None else frozenset(sichtbar)) if alle else None
        if schluessel is not None and self._zonen_alle[0] == schluessel:
            ergebnis, zonen = self._zonen_alle[1]  # alle Zonen nicht bei jeder Auswahl neu berechnen
        else:
            ergebnis = toleranzzone.zonen(liste, self.erg.modell, mindest, self.erg.pmi)
            zonen = [z for _p, z in ergebnis]
            faktor = zonen[0].faktor if zonen else None
            if allgemein is not None:
                z = toleranzzone.allgemein_zone(self.erg.modell, self.erg.pmi, allgemein, mindest, faktor, nur)
                if z is not None:
                    zonen.append(z)
            if schluessel is not None:
                self._zonen_alle = (schluessel, (ergebnis, zonen))
        formen = [f for z in zonen for f in z.formen]
        rollen = [r for z in zonen for r in z.rollen]
        formen, rollen = self._zonen_je_instanz(formen, rollen, [q for z in zonen for q in z.quellen_je_form()])
        self.ansicht.zeige_zone(formen, rollen)
        if not zonen:
            if liste:
                self.statusBar().showMessage(tr("Für diese PMI gibt es keine Zonendarstellung"), 5000)
            elif nur:
                self.statusBar().showMessage(tr("Keine PMI an der Auswahl – Allgemeintoleranzen einschalten, um "
                                                "deren Zonen zu sehen"), 6000)
            return
        if len(ergebnis) == 1 and len(zonen) == 1:
            z = zonen[0]
            p0 = ergebnis[0][0]
            if "Angular" in (p0.typ or ""):  # Winkelmass: Zonenbreite in Grad
                h, m = p0.grenzen()
                text = tr("Toleranzzone {:.4g}°").format(h - m)
            else:
                text = tr("Toleranzzone {:.4g} mm").format(z.breite)
        else:
            text = tr("{} Toleranzzonen").format(len(ergebnis))
        # Erklaerungen: die der einzelnen Zone, bei vielen nur die der Allgemeintoleranzen
        hinweise = [h for z in zonen if len(ergebnis) == 1 or z.art == "allgemein" for h in z.hinweise]
        if hinweise:
            text += " · " + "; ".join(hinweise)
        if max(z.faktor for z in zonen) > 1.01:
            text += " " + tr("(Darstellung {:.3g}-fach überhöht)").format(max(z.faktor for z in zonen))
        self.statusBar().showMessage(text, 12000)

    def waehle_allgemeintoleranzen(self):
        from ..kern import toleranzzone
        from .allgemein_ui import AllgemeinDialog
        if self.erg is None:
            return
        d = AllgemeinDialog(self._allgemein, toleranzzone.allgemein_aus_hinweisen(self.erg.pmi),
                            self)
        if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._allgemein = d.wert()
        self.aktionen["allgemein_zeigen"].setChecked(self._allgemein is not None)
        self._allgemein_umschalten()

    def _allgemein_umschalten(self):
        """Allgemeintoleranzen ein/aus; ohne gewaehlte Klassen die aus der Datei, sonst zuerst der Dialog."""
        from ..kern import toleranzzone
        a = self.aktionen
        if a["allgemein_zeigen"].isChecked():
            if self._allgemein is None and self.erg is not None:
                self._allgemein = toleranzzone.allgemein_aus_hinweisen(self.erg.pmi)
            if self._allgemein is None:
                a["allgemein_zeigen"].setChecked(False)
                self.waehle_allgemeintoleranzen()
                return
            if not (a["toleranzzone"].isChecked() or a["toleranzzonen_alle"].isChecked()):
                a["toleranzzonen_alle"].setChecked(True)
        self._zone_aktualisieren(self.pmi.gewaehlte())

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

    # --- Kommentare ---

    def _kommentar_ziel(self):
        """(Ort, Flaechen, PMI-Nummern, Beschreibung) der aktuellen Auswahl oder None."""
        import numpy as np
        from ..kern import merkmale, pmi_erzeugen
        flaechen = {i for f in self.ansicht.auswahl3d for i in [self.erg.modell.flaechen_index(f)] if i is not None}
        pmi = list(self._schnell_pmi)
        ort = None
        if self.ansicht.auswahl3d:
            ort = pmi_erzeugen._schwerpunkt(list(self.ansicht.auswahl3d))
        elif pmi:
            ort = merkmale.anker(pmi[0], self.erg.grafik, self.ansicht.mitte_von)
            flaechen |= set(pmi[0].flaechen)
            if ort is None and pmi[0].flaechen:
                ort = pmi_erzeugen._schwerpunkt([self.erg.modell.flaechen[i] for i in pmi[0].flaechen])
        if ort is None:
            return None
        teile = []
        if pmi:
            teile.append(tr("PMI {}").format(", ".join(str(p.nummer) for p in pmi)))
        if flaechen:
            teile.append(tr("{} Flächen").format(len(flaechen)))
        return tuple(np.asarray(ort, float)), flaechen, [p.nummer for p in pmi], " · ".join(teile)

    def neuer_kommentar(self, text: str = "", art: str = "kommentar"):
        """Kommentar an der Auswahl; ohne Text fragt ein Dialog nach Art und Text."""
        from ..kern.kommentare import Kommentar
        from .kommentar_ui import KommentarDialog
        if self.erg is None:
            return None
        ziel = self._kommentar_ziel()
        if ziel is None:
            self.statusBar().showMessage(tr("Erst Flächen oder eine PMI wählen, dann kommentieren"), 5000)
            return None
        ort, flaechen, pmi, beschreibung = ziel
        if not text:
            d = KommentarDialog(beschreibung, self)
            if d.exec() != QtWidgets.QDialog.DialogCode.Accepted or not d.text.toPlainText().strip():
                return None
            text, art = d.text.toPlainText().strip(), d.art.currentData()
        k = Kommentar.neu(self.kommentare.naechste_nummer(), text, ort, art, flaechen, pmi)
        self.kommentare.fuege_hinzu(k)
        self.dock_kommentare.show()
        self.dock_kommentare.raise_()
        return k

    def _kommentare_zeigen(self):
        self.ansicht.zeige_kommentare([(k.nummer, k.ort, k.status == "erledigt") for k in self.kommentare.kommentare])

    def _kommentar_gewaehlt(self, k):
        if k is None:
            return
        self.ansicht.hebe_flaechen(set(k.flaechen))
        if k.flaechen:
            self.ansicht.zoome_auf(set(k.flaechen))

    def exportiere_kommentare(self, pfad: str = "") -> str | None:
        from ..kern import kommentare as km
        if self.erg is None:
            return None
        pfad = pfad or self._speicherpfad(tr("Kommentare speichern"),
                                          os.path.splitext(self.erg.pfad)[0] + "_kommentare.csv", "CSV (*.csv)")
        if not pfad:
            return None
        with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
            f.write(km.als_csv(self.kommentare.kommentare))
        return pfad

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

    def _starte_vorschau(self):
        """Vorschaubilder der gespeicherten Ansichten im Hintergrund zeichnen - erst wenn die 3D-Ansicht steht: die
        Kantenberechnung (HLR) haelt die Python-Sperre und wuerde sonst den Szenenaufbau um ein Vielfaches bremsen."""
        if getattr(self.ansicht, "_bereit", True) is False:
            QtCore.QTimer.singleShot(200, self._starte_vorschau)
            return
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        from .panels import VorschauLader
        alt = getattr(self, "_vorschau", None)
        if alt is not None and alt.isRunning():
            alt.abbrechen = True
            alt.wait(2000)
        if self.erg is None or not self.erg.ansichten:
            return
        form = TopoDS_Compound()
        bb = BRep_Builder()
        bb.MakeCompound(form)
        for k in self.erg.baum.blaetter():
            if not k.hilfsgeometrie:
                bb.Add(form, k.form)
        pmi_text = {p.step_id: p.wert_text() for p in self.erg.pmi if p.step_id}
        grafik = [self._grafik_fuer(a.pmi_ids) for a in self.erg.ansichten]
        lader = VorschauLader(form, self.erg.ansichten, grafik, pmi_text, self)
        lader.fertig.connect(self.ansichten.setze_vorschau)
        self._vorschau = lader
        lader.start()

    def _ansichten_neu(self, waehlen):
        self.ansichten.zeige(self.erg.ansichten)
        self._starte_vorschau()
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
            self.ansicht.setze_ansicht_schnitt([])
            self.pmi.nur_ansicht(None)
            self.ansicht.zeige_pmi(getattr(self, "_pmi_filter_ids", None))
            return
        self.pmi.nur_ansicht(set(ansicht.pmi_nummern))
        self.ansicht.zeige_pmi(ansicht.pmi_ids if getattr(self, "_pmi_filter_ids", None) is None
                               else self._pmi_filter_ids)
        self.ansicht.kamera(ansicht)
        self.ansicht.setze_ansicht_schnitt(ansicht.schnitt)
        text = tr("Ansicht {}: {} von {} PMI").format(ansicht.name, len(ansicht.pmi_nummern),
                                                       len(self.erg.pmi) if self.erg else 0)
        if ansicht.schnitt:
            text += " · " + tr("Schnittansicht ({} Ebenen)").format(sum(len(g) for g in ansicht.schnitt))
        self.statusBar().showMessage(text, 6000)

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
        self._laufbalken_pruefen()
        if getattr(self, "_projekt", None):
            from ..kern import projekt
            projekt.uebernimm_pruefstand(v, self._projekt.get("vergleich", {}).get("aenderungen", []))
        self.zeige_vergleich(v)
        self._projekt_messungen()
        self._danach()

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
                                 self.erg.ansichten, self.kommentare.kommentare,
                                 [p for p in self.erg.pmi if p.quelle == "eigen"],
                                 [{"step_id": p.step_id, "werte": {k: getattr(p, k) for k in p.original}}
                                  for p in self.erg.pmi if p.quelle != "eigen" and p.bearbeitet and p.original],
                                 self._kette_daten(),
                                 self.baugruppe.als_dict() if self.baugruppe.verbindungen or self.baugruppe.lagen
                                 else None, self._kollision_daten(),
                                 self._funktion.zustand() if getattr(self, "_funktion", None) is not None
                                 and self._funktion.rollen else None, self._raumketten(),
                                 [(z.pfad, z.versatz) for z in getattr(self.erg, "zusaetze", [])])
        self.statusBar().showMessage(tr("Projekt gespeichert: {}").format(ziel), 6000)
        return ziel

    def _kollision_daten(self):
        from ..kern import kollision as ko
        if not self.kollision.befunde:
            return None
        return {"werte": self.kollision.werte(), "befunde": ko.merke(self.kollision.befunde)}

    def _raumketten(self) -> dict | None:
        """2D- und 3D-Kette der offenen Fenster fuer das Projekt (nur mit Inhalt)."""
        from ..kern import kette2d, kette3d
        out = {}
        k2 = getattr(self, "_kette2d", None)
        if k2 is not None and k2.kette.segmente:
            out["kette2d"] = kette2d.als_dict(k2.kette)
        k3 = getattr(self, "_kette3d", None)
        if k3 is not None and k3.kette.glieder:
            out["kette3d"] = kette3d.als_dict(k3.kette)
        return out or None

    def _kette_daten(self):
        k = getattr(self, "_kette", None)
        return None if k is None or not k.glieder else (k.cp.value(), list(k.glieder), k.freigabe)

    def oeffne_projekt(self, pfad: str, warten: bool = False):
        from ..kern import projekt
        try:
            self._projekt = projekt.lade(pfad)
        except Exception as e:  # noqa: BLE001 - Fehler dem Nutzer zeigen
            QtWidgets.QMessageBox.warning(self, tr("Projekt öffnen"), str(e))
            return
        d = self._projekt
        self._projekt_warten = warten  # fuer Schritte nach dem Laden (Kollisionspruefung)
        if d["typ"] == "vergleich":
            v = d["vergleich"]
            self.starte_vergleich({"alt": d["pfade"]["alt"], "neu": d["pfade"]["neu"], "toleranz": v["toleranz"],
                                   "suchweite": v["suchweite"]}, warten)
        else:
            self.lade(d["pfade"]["modell"], warten, d.get("zusatz_pfade", []))

    # --- Modell hinzufuegen ---

    def modell_hinzufuegen(self, pfad: str = "", warten: bool = False):
        """Weitere Datei als zusaetzliche Teile ins geladene Modell aufnehmen (neben das Modell gelegt)."""
        if self.erg is None:
            return
        if self.vergleich is not None:
            self.statusBar().showMessage(tr("Modell hinzufügen geht nicht während eines Vergleichs"), 6000)
            return
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Modell hinzufügen"),
                                                            os.path.dirname(self.erg.pfad),
                                                            DATEIFILTER.format(tr("Alle Modelle"), tr("Netze")))
            if not pfad:
                return
        self.lade_abbrechen()
        self.statusBar().showMessage(tr("Füge {} hinzu …").format(os.path.basename(pfad)))
        self.fortschritt.show()
        self.abbrechen.show()
        self._lader = Lader(self.erg.pfad, self, [(pfad, None)], basis=self.erg)
        self._lader.stand.connect(lambda t: self.statusBar().showMessage(t))
        self._lader.fertig.connect(self._hinzugefuegt)
        self._lader.fehler.connect(self._ladefehler)
        self._lader.start()
        if warten:
            self._lader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def _hinzugefuegt(self, erg):
        """Zusammengefuegtes Modell zeigen; Zusammenbau, Messungen und Kommentare bleiben (gleiche erste Datei)."""
        if self.sender() is not self._lader:
            return
        self._lader = None
        self._laufbalken_pruefen()
        self.zeige_ergebnis(erg)
        self.ansicht.setze_teil_lagen(self.baugruppe.lagen)
        if self.dock_zusammenbau.isVisible():
            self._zusammenbau_zeigen()
        z = erg.zusaetze[-1]
        self.statusBar().showMessage(tr("{} hinzugefügt: {} Flächen, neben das Modell gelegt – im Zusammenbau "
                                        "verbinden").format(os.path.basename(z.pfad), z.flaechen), 8000)

    def _projekt_messungen(self):
        d = getattr(self, "_projekt", None)
        if d and d.get("messungen"):
            self.messen.messungen = list(d["messungen"])
            self.messen._fuelle()
            self.dock_messen.show()
        if d and d.get("eigene_pmi") and self.erg is not None:
            self.fuege_pmi_hinzu(d["eigene_pmi"])
        if d and d.get("pmi_aenderungen") and self.erg is not None:
            nach_id = {p.step_id: p for p in self.erg.pmi}
            for a in d["pmi_aenderungen"]:
                if a.get("step_id") in nach_id:
                    self.bearbeite_pmi(nach_id[a["step_id"]], a.get("werte", {}))
        if d and d.get("zusammenbau") and self.erg is not None:
            from ..kern.verbindung import flaeche_im_teil
            knoten = {k.nummer: k for k in self.erg.baum.blaetter()}
            self.baugruppe.lade(d["zusammenbau"], lambda t, i: flaeche_im_teil(knoten[t].form, i, self.erg.modell)
                                if t in knoten else None)
            self.zeige_zusammenbau()
        if d and d.get("kette") and self.erg is not None:
            k = self.zeige_toleranzkette(nur_anlegen=True)
            k.leeren()
            k.cp.setValue(d["kette"]["cp"])
            k.ergaenze(d["kette"]["glieder"])
            k.setze_freigabe(d["kette"].get("freigabe") or {})
        if d and d.get("raumketten"):
            from ..kern import kette2d, kette3d
            if d["raumketten"].get("kette2d"):
                self.zeige_kette2d(nur_anlegen=True).setze_kette(kette2d.von_dict(d["raumketten"]["kette2d"]))
            if d["raumketten"].get("kette3d"):
                self.zeige_kette3d(nur_anlegen=True).setze_kette(kette3d.von_dict(d["raumketten"]["kette3d"]))
        if d and d.get("funktion") and self.erg is not None:
            self.zeige_funktion(nur_anlegen=True).setze_zustand(d["funktion"])
        if d and d.get("kommentare"):
            self.kommentare.setze(d["kommentare"])
            self.dock_kommentare.show()
        if d and d.get("kollision") and self.erg is not None:  # Pruefung neu, Status und Kommentare zurueck
            gemerkt = d["kollision"]
            self._kollision_gemerkt = gemerkt.get("befunde", [])
            self.starte_kollision(gemerkt.get("werte", {}), getattr(self, "_projekt_warten", False))
        if d and d.get("ansichten") and self.erg is not None:
            self.erg.ansichten.extend(d["ansichten"])
            self._ansichten_neu(None)
        self._projekt = None

    def zeige_vergleich(self, v):
        self.vergleich = v
        self.zeige_ergebnis(v.neu, vergleich=v)
        self._alt_szene_fuer = None  # die Ansicht des alten Stands gehoert zum vorigen Vergleich
        self._anzeige_art = None
        self._vergleichsmodus = "vergleich"
        self._vergleich_anzeigen()
        self.modus_leiste.show()
        self.aenderungen.zeige(v, self.thema)
        self.spalten_anpassen()
        self.dock_aenderungen.toggleViewAction().setEnabled(True)
        self.vergleich_stand.setText(tr("Vergleich: {} → {}").format(os.path.basename(v.alt.pfad),
                                                                     os.path.basename(v.neu.pfad)))
        self.vergleich_stand.show()
        self.dock_aenderungen.show()
        self.dock_aenderungen.raise_()
        for n in self.VERGLEICH_AKTIONEN:
            self.aktionen[n].setEnabled(True)
        self.setWindowTitle(self._titel(f"{os.path.basename(v.alt.pfad)} → {os.path.basename(v.neu.pfad)}"))
        self.statusBar().showMessage(tr("Vergleich fertig: {} Änderungen").format(len(v.aenderungen)), 8000)

    # --- Vergleichsmodi (Alt, Neu, Vergleich, Ueberlagern, Nebeneinander, Blinken) ---

    def _baue_mitte(self) -> QtWidgets.QWidget:
        """Mittelbereich: Modusleiste (nur im Vergleich), darunter alte und neue 3D-Ansicht nebeneinander."""
        from .vergleich_ui import VergleichsmodusLeiste
        self.mitte = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(self.mitte)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.modus_leiste = VergleichsmodusLeiste()
        self.modus_leiste.hide()
        self.modus_leiste.modus.connect(self.setze_vergleichsmodus)
        self.modus_leiste.hervorheben.connect(lambda _an: self._vergleich_anzeigen())
        from .vergleich_ui import SCAN_MODI
        # Scanpruefung als Vergleich Soll (CAD) <-> Ist (Scan): dieselbe Leiste mit eigenen Modi
        self.scan_leiste = VergleichsmodusLeiste(modi=SCAN_MODI, hervor=False, staende=("Soll", "Ist"))
        self.scan_leiste.hide()
        self.scan_leiste.modus.connect(self.setze_scanmodus)
        self._scan_blink = QtCore.QTimer(self)
        self._scan_blink.setInterval(600)
        self._scan_blink.timeout.connect(self._scan_blinken)
        self.scan_leiste.takt.connect(self._scan_blink.setInterval)
        self.scan_leiste.pause.connect(lambda an: self._scan_blink.stop() if an else
                                       (self._scanmodus == "blinken" and self._scan_blink.start()))
        self._scanmodus = "vergleich"
        self.teiler = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.teiler.setChildrenCollapsible(False)
        self.teiler.addWidget(self.ansicht)
        lay.addWidget(self.modus_leiste)
        lay.addWidget(self.scan_leiste)
        lay.addWidget(self.teiler, 1)
        self.ansicht_alt = None  # entsteht beim ersten Bedarf
        self._alt_szene_fuer = None  # Vergleich, dessen alter Stand in ansicht_alt steht
        self._vergleichsmodus = "vergleich"
        self._blink_alt = False
        self._kopplung = QtCore.QTimer(self)
        self._kopplung.setInterval(50)
        self._kopplung.timeout.connect(self._kameras_koppeln)
        self._kamera_zuletzt = (None, None)
        self._blink = QtCore.QTimer(self)
        self._blink.setInterval(600)
        self._blink.timeout.connect(self._blink_schritt)
        self.modus_leiste.takt.connect(self._blink.setInterval)
        self.modus_leiste.pause.connect(lambda an: self._blink.stop() if an else
                                        (self._vergleichsmodus == "blinken" and self._blink.start()))
        self._leertaste = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Space), self.mitte)
        self._leertaste.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._leertaste.activated.connect(self._alt_neu_wechseln)
        return self.mitte

    def _baum_ansicht(self):
        return self.ansicht_alt if self._vergleichsmodus == "alt" and self.ansicht_alt is not None else self.ansicht

    def _zweite_ansicht_anlegen(self):
        """Zweite 3D-Ansicht links (Vergleich: alter Stand, Scanpruefung: Soll) - einmal anlegen."""
        if self.ansicht_alt is None:
            self.ansicht_alt = ansicht3d.erzeuge(self)
            self.ansicht_alt.setze_thema(self.thema)
            self.ansicht_alt.setze_navigation(self.ein.value("navigation", "catia"))
            self.ansicht_alt.setze_pmi_kontrast(self.ein.value("pmi_kontrast", True, type=bool))
            self.ansicht_alt.setze_draht_kontrast(self.ein.value("draht_kontrast", True, type=bool))
            self._farben_anwenden()
            self.teiler.insertWidget(0, self.ansicht_alt)
            self.ansicht_alt.hide()
        return self.ansicht_alt

    def _soll_ansicht(self):
        """Scanpruefung nebeneinander: links das CAD-Modell (Soll)."""
        a = self._zweite_ansicht_anlegen()
        if self._alt_szene_fuer is not self.erg:
            e = self.erg
            a.zeige(ansicht3d.Szene(e.modell, e.baum, e.farben, e.grafik, e.pmi))
            self._alt_szene_fuer = e
        return a

    def _alte_ansicht(self):
        """Ansicht des alten Stands anlegen bzw. mit dem alten Stand des aktuellen Vergleichs fuellen."""
        v = self.vergleich
        self._zweite_ansicht_anlegen()
        if self._alt_szene_fuer is not v:
            a = v.alt
            self.ansicht_alt.zeige(ansicht3d.Szene(a.modell, a.baum, a.farben, a.grafik, a.pmi))
            self._alt_szene_fuer = v
        return self.ansicht_alt

    def setze_vergleichsmodus(self, modus: str):
        if self.vergleich is None:
            return
        self._vergleichsmodus = modus
        self.modus_leiste.setze(modus)
        self._blink_alt = modus == "alt"
        self._vergleich_anzeigen()
        texte = {"alt": tr("Alter Stand"), "neu": tr("Neuer Stand"), "nebeneinander": tr("Links alt, rechts neu – "
                 "Kameras gekoppelt"), "blinken": tr("Blinken: Leertaste wechselt von Hand"),
                 "ueberlagern": tr("Alter Stand blau durchscheinend über dem neuen")}
        if modus in texte:
            self.statusBar().showMessage(texte[modus], 6000)

    def _vergleich_anzeigen(self):
        """Faerbung, Ueberlagerung, Sichtbarkeit beider Ansichten und Baum nach dem Vergleichsmodus."""
        v, m = self.vergleich, self._vergleichsmodus
        if v is None:
            return
        hervor = self.modus_leiste.hervor.isChecked()
        if m == "vergleich":
            entfernt = v.geo.entfernt_a
            if entfernt is None:
                entfernt = [v.alt.modell.flaechen[i] for i, st in v.geo.status_a.items() if st == "entfernt"]
            status = v.geo.status_b
        else:
            entfernt, status = [], v.geo.status_b if hervor or m == "ueberlagern" else {}
        art = (m == "vergleich", bool(status))  # Szene nur neu aufbauen, wenn sich die Faerbung aendert
        if getattr(self, "_anzeige_art", None) != art:
            self.ansicht.zeige_vergleich(status, entfernt, v.ausrichtung.gp_trsf(), v.geo.instanzen_b)
            self._anzeige_art = art
        self.ansicht.zeige_ueberlagerung(v.alt.modell.form if m == "ueberlagern" else None)
        braucht_alt = m in ("alt", "nebeneinander", "blinken")
        if braucht_alt:
            alt = self._alte_ansicht()
            alt.zeige_vergleich(v.geo.status_a if hervor else {}, [], None)
            alt.hebe_pmi({x.pmi_alt.step_id for x in v.aenderungen if x.pmi_alt is not None and x.pmi_alt.step_id}
                         if hervor else set())
        self.ansicht.hebe_pmi({x.pmi_neu.step_id for x in v.aenderungen if x.pmi_neu is not None and x.pmi_neu.step_id}
                              if hervor and m != "vergleich" else set())
        self._sichtbarkeit_vergleich()
        if braucht_alt:
            self._kopplung.start()
        else:
            self._kopplung.stop()
        if m == "blinken" and not self.modus_leiste.pause_knopf.isChecked():
            self._blink.start()
        else:
            self._blink.stop()
        # im Vergleich immer beide Strukturen (oben neu, unten alt, beschriftet) - unabhaengig vom Anzeigemodus
        if getattr(self, "_baum_zeigt_alt", False):
            self.baum.zeige(v.neu.baum)
            self._baum_zeigt_alt = False
        self.baum.setze_status(self._teil_status(v, False) if hervor or m == "vergleich" else None)
        self.dock_baum.setWindowTitle(tr("Struktur"))
        self._zweiter_baum(v, hervor)

    def _zweiter_baum(self, v, hervor: bool = True):
        """Nebeneinander: beide Strukturen untereinander (neu oben, alt unten); v None blendet den alten aus."""
        an = v is not None and getattr(v.alt, "baum", None) is not None
        if an and getattr(self, "_baum_alt_fuer", None) is not v:
            self.baum_alt.zeige(v.alt.baum)
            self._baum_alt_fuer = v
        if an:
            self.baum_alt.setze_status(self._teil_status(v, True) if hervor else None)
        self.baum_alt.setVisible(an)
        for titel in self._baum_titel:
            titel.setVisible(an)

    def _teil_status(self, v, alt: bool) -> dict:
        """Status je Teil des gezeigten Stands (gemerkt je Vergleich)."""
        from ..kern.vergleich_geo import teil_status
        gemerkt = getattr(self, "_teil_status_merk", None)
        if gemerkt is None or gemerkt[0] is not v:
            gemerkt = self._teil_status_merk = (v, {})
        if alt not in gemerkt[1]:
            e = v.alt if alt else v.neu
            status = teil_status(e.baum, e.modell, v.geo.status_a if alt else v.geo.status_b,
                                 None if alt else v.geo.instanzen_b)
            # Teile, die der Baugruppenvergleich als neu/entfernt kennt, gehen vor (eine Flaeche kann zufaellig in
            # einer alten Ebene liegen und zaehlt dann geometrisch als gleich)
            ziel = "entfernt" if alt else "neu"
            for a in v.aenderungen:
                if a.kategorie == "baugruppe" and a.status == ziel:
                    flaechen = a.flaechen_alt if alt else a.flaechen_neu
                    for nr in self._blaetter_mit(e, flaechen):
                        status[nr] = ziel
            gemerkt[1][alt] = status
        return gemerkt[1][alt]

    @staticmethod
    def _blaetter_mit(erg, flaechen: set) -> set[int]:
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        out = set()
        for k in erg.baum.blaetter():
            ex = TopExp_Explorer(k.form, TopAbs_FACE) if k.form is not None else None
            while ex is not None and ex.More():
                if erg.modell.flaechen_index(ex.Current()) in flaechen:
                    out.add(k.nummer)
                    break
                ex.Next()
        return out

    def _sichtbarkeit_vergleich(self):
        m = self._vergleichsmodus
        alt_an = m in ("alt", "nebeneinander") or (m == "blinken" and self._blink_alt)
        neu_an = m in ("vergleich", "neu", "ueberlagern", "nebeneinander") or (m == "blinken" and not self._blink_alt)
        alt = self.ansicht_alt
        if alt is not None and self._alt_szene_fuer is not None:
            # die Kamera geht von der bisher sichtbaren auf die neu sichtbare Ansicht ueber
            if alt_an and not alt.isVisible() and self.ansicht.isVisible():
                alt.setze_kamera_daten(self.ansicht.kamera_daten())
            elif neu_an and not self.ansicht.isVisible() and alt.isVisible():
                self.ansicht.setze_kamera_daten(alt.kamera_daten())
            alt.setVisible(alt_an)
        self.ansicht.setVisible(neu_an or alt is None)
        self.modus_leiste.zeige_stand(self._blink_alt if m == "blinken" else None)
        self._kamera_zuletzt = (None, None)

    def _kameras_koppeln(self):
        """Die zuletzt bewegte Kamera auf die andere Ansicht uebertragen (Nebeneinander, Blinken, Alt)."""
        alt = self.ansicht_alt
        if alt is None or (self.vergleich is None and getattr(self, "_scanmodus", "") != "nebeneinander"):
            return
        ka, kn = alt.kamera_daten(), self.ansicht.kamera_daten()
        za, zn = self._kamera_zuletzt
        if ka is not None and ka != za and za is not None:
            self.ansicht.setze_kamera_daten(ka)
            kn = ka
        elif kn is not None and kn != zn and zn is not None:
            alt.setze_kamera_daten(kn)
            ka = kn
        elif za is None:  # erster Takt: neue Ansicht gibt die Kamera vor
            if alt.isVisible() and not self.ansicht.isVisible():
                self.ansicht.setze_kamera_daten(ka)
                kn = ka
            else:
                alt.setze_kamera_daten(kn)
                ka = kn
        self._kamera_zuletzt = (ka, kn)

    def _blink_schritt(self):
        self._blink_alt = not self._blink_alt
        self._sichtbarkeit_vergleich()

    def _alt_neu_wechseln(self):
        """Leertaste: in Blinken von Hand wechseln, sonst zwischen Alt und Neu."""
        if self.vergleich is None:
            return
        if self._vergleichsmodus == "blinken":
            self.modus_leiste.pause_knopf.setChecked(True)
            self._blink_schritt()
        elif self._vergleichsmodus in ("alt", "neu"):
            self.setze_vergleichsmodus("neu" if self._vergleichsmodus == "alt" else "alt")

    def _vergleichsmodus_ende(self):
        self._blink.stop()
        self._kopplung.stop()
        self._vergleichsmodus = "vergleich"
        self.modus_leiste.setze("vergleich")
        self.modus_leiste.hide()
        self.ansicht.zeige_ueberlagerung(None)
        self.ansicht.hebe_pmi(set())
        if self.ansicht_alt is not None:
            self.ansicht_alt.hide()
        self.ansicht.show()
        self._alt_szene_fuer = None
        self._anzeige_art = None
        if getattr(self, "_baum_zeigt_alt", False) and self.erg is not None:
            self.baum.zeige(self.erg.baum)
        self._baum_zeigt_alt = False
        self.baum.setze_status(None)
        self.dock_baum.setWindowTitle(tr("Struktur"))
        self._zweiter_baum(None)
        self._baum_alt_fuer = None

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
        self.abbrechen.show()
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
            lader.stand.connect(self._prozent)
            lader.fehler.connect(lambda t: QtWidgets.QMessageBox.warning(self, tr("Farbkarte"), t))
            lader.fertig.connect(lambda k, v=v, l=lader: l.abgebrochen or self._farbkarte_fertig(v, k))
            self._karten_lader = lader
            self._aufgabe(lader, tr("Farbkarte berechnen …"))
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

    def zeige_material(self, an: bool, warten: bool = False):
        """Hinzugekommenes/entferntes Volumen im Vergleich (einmal je Vergleich berechnet)."""
        v = self.vergleich
        if v is None:
            return
        if not an:
            self.ansicht.zeige_material(None, None)
            return
        m = getattr(v, "material", None)
        if m is None:
            from .vergleich_ui import MaterialLader
            lader = MaterialLader(v, self)
            lader.fehler.connect(lambda t: self.statusBar().showMessage(tr("Materialvergleich: {}").format(t), 8000))
            lader.fertig.connect(lambda m, v=v, l=lader: l.abgebrochen or self._material_fertig(v, m))
            self._material_lader = lader
            self._aufgabe(lader, tr("Materialvergleich läuft …"))
            lader.start()
            if warten:
                lader.wait()
                QtWidgets.QApplication.processEvents()
            return
        self.ansicht.zeige_material(m.dazu, m.weg)
        self.statusBar().showMessage(tr("Material: +{:.2f} mm³ ({} Bereiche) hinzu, −{:.2f} mm³ ({} Bereiche) entfernt")
                                     .format(m.vol_dazu, m.teile_dazu, m.vol_weg, m.teile_weg), 12000)

    def _material_fertig(self, v, m):
        v.material = m
        if self.vergleich is v and self.aenderungen.material_an.isChecked():
            self.zeige_material(True)

    def _farbkarte_fertig(self, v, karte):
        v.karte = karte
        if self.vergleich is v and self.aenderungen.karte_an.isChecked():
            self.zeige_farbkarte(True, self.aenderungen.skala.value())

    def beende_vergleich(self, neu_zeigen: bool = True):
        if self.vergleich is None:
            return
        self.vergleich = None
        self._vergleichsmodus_ende()
        self.ansicht.zeige_vergleich(None)
        self.aenderungen.zeige(None)
        self.dock_aenderungen.hide()
        self.dock_aenderungen.toggleViewAction().setEnabled(False)
        self.vergleich_stand.hide()
        for n in self.VERGLEICH_AKTIONEN:
            self.aktionen[n].setEnabled(False)
        if neu_zeigen and self.erg is not None:
            self.setWindowTitle(self._titel(os.path.basename(self.erg.pfad)))

    def _aenderung_gewaehlt(self, a):
        alt = self.ansicht_alt if self._alt_szene_fuer is not None else None
        if a is None or self.vergleich is None:
            self.ansicht.hebe_flaechen(set())
            if alt is not None:
                alt.hebe_flaechen(set())
            return
        if alt is not None:
            alt.hebe_flaechen(a.flaechen_alt)  # im alten Stand dieselbe Aenderung zeigen
        self.ansicht.hebe_flaechen(a.flaechen_neu)
        alt_formen = [] if a.flaechen_neu else [self.vergleich.alt.modell.flaechen[i] for i in a.flaechen_alt]
        instanz = next((k for k in self.vergleich.neu.baum.blaetter() if k.nummer == a.knoten), None) \
            if a.knoten and getattr(self.vergleich.neu, "baum", None) is not None else None
        if instanz is not None:  # nur diese Instanz: Ausschnitt auf sie, im Baum markiert
            self.ansicht.zoome_auf(set(), [instanz.form])
            self.baum.zeige_knoten(instanz.nummer)
        else:
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
        for n in ("schnitt_auswahl", "schnitt_blick", "schnittbox", "schnitt_aus"):
            m.addAction(a[n])
        m.addSeparator()
        for n in ("pmi_anlegen", "kommentar"):
            m.addAction(a[n])
        m.addSeparator()
        for n in ("fokus", "toleranzzone", "toleranzzonen_alle", "allgemein_zeigen", "allgemeintoleranzen"):
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
        if self.erg is None or (art not in ("ansichten", "merkmale", "messungen", "kommentare") and
                                self.vergleich is None):
            return None
        basis = os.path.splitext((self.vergleich.neu.pfad if self.vergleich else self.erg.pfad))[0]
        endung = {"ansichten": "_ansichten.pdf", "vergleich": "_vergleich.pdf", "pmi_aenderungen": "_pmi_aenderungen.pdf",
                  "merkmale": "_merkmale.pdf", "messungen": "_messprotokoll.pdf", "kommentare": "_kommentare.pdf"}[art]
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
            elif art == "kommentare":
                berichte.kommentare_pdf(self, pfad)
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
        ebenen = self.ansicht.alle_schnitt_ebenen() if art == "schnitt" else []
        if art == "schnitt" and not ebenen:
            self.statusBar().showMessage(tr("Erst einen Schnitt wählen"), 5000)
            return None
        basis = os.path.splitext(self.erg.pfad)[0] + {"blatt": "_zeichnung", "aktuell": "_ansicht",
                                                      "ansichten": "_ansichten_zeichnung", "schnitt": "_schnitte"}[art]
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
            if art == "schnitt":
                import numpy as np
                from ..kern import schnitt
                buchstaben = "ABC"
                liste = [schnitt.Ebene(np.asarray(p, float), -np.asarray(r, float),
                                       tr("Schnitt {}").format(f"{buchstaben[i]}–{buchstaben[i]}"))
                         for i, (p, r) in enumerate(ebenen)]
                ansichten = schnitt.schnittansichten(form, liste)
                methode = tr("Schnittansicht")
            elif art == "blatt":
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
            zeile = f"{methode} · {tr('Maße in mm')} · 3DGmax {VERSION} · {datetime.date.today().isoformat()}"
            format_ = str(self.ein.value("zeichnung_format", ""))
            blatt = None
            if format_ in zeichnung.FORMATE:  # Normblatt mit Rahmen, Schriftfeld und Massstab
                ansichten, massstab = zeichnung.auf_blatt(ansichten, format_, titel=name, zeile=zeile)
                blatt = zeichnung.FORMATE[format_]
                self._letzter_massstab = massstab
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
                berichte.zeichnung_pdf(zeichnung.als_svg(ansichten, name), pfad, name, zeile, blatt)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(tr("Zeichnung gespeichert: {}").format(pfad), 8000)
        return pfad

    def _menue_blattformat(self, menue):
        """Zeichnungen frei (Ausdehnung der Ansichten) oder auf einem Normblatt mit Rahmen, Schriftfeld, Massstab."""
        from ..kern import zeichnung
        gruppe = QtGui.QActionGroup(self)
        jetzt = str(self.ein.value("zeichnung_format", ""))
        self.blattformat_aktionen = {}
        for schluessel, text in [("", tr("Ohne Blatt (Ausdehnung der Ansichten)"))] + \
                [(f, tr("{} quer, Maßstab automatisch").format(f)) for f in zeichnung.FORMATE]:
            akt = menue.addAction(text)
            akt.setCheckable(True)
            akt.setChecked(schluessel == jetzt)
            akt.triggered.connect(lambda _c=False, k=schluessel: self.ein.setValue("zeichnung_format", k))
            gruppe.addAction(akt)
            self.blattformat_aktionen[schluessel] = akt

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
            f.write(merkmale.als_csv(merkmale.liste(self.erg.pmi), self.erg.ansichten, self.messung_aktuell()))
        self.statusBar().showMessage(tr("Merkmalsliste gespeichert: {}").format(pfad), 8000)
        return pfad

    def messung_aktuell(self) -> dict | None:
        """Ballonnummer -> (Messwert, Bewertung) der eingelesenen Messergebnisse zum geladenen Modell."""
        gemerkt = getattr(self, "_messung", None)
        return gemerkt[1] if gemerkt and gemerkt[0] is self.erg else None

    def lies_messergebnisse(self, pfad: str = ""):
        from ..kern import merkmale, qif_ergebnisse as qe
        from .messergebnisse_ui import MessergebnisseFenster
        if self.erg is None:
            self.statusBar().showMessage(tr("Erst das Modell öffnen, dann die Messergebnisse"), 6000)
            return None
        pfad = pfad or QtWidgets.QFileDialog.getOpenFileName(self, tr("Messergebnisse öffnen"), "",
                                                             "QIF (*.qif *.QIF *.xml)")[0]
        if not pfad:
            return None
        try:
            werte, angaben = qe.lies(pfad)
        except Exception as e:  # noqa: BLE001 - kaputte Datei dem Nutzer melden
            QtWidgets.QMessageBox.warning(self, tr("Messergebnisse"), str(e))
            return None
        liste = merkmale.liste(self.erg.pmi)
        je = qe.zuordnen(werte, liste)
        messung = {m.ballon: qe.massgebend(m, je[m.ballon]) for m in liste if m.ballon in je}
        self._messung = (self.erg, messung)
        frei = len(werte) - sum(len(v) for v in je.values())
        f = MessergebnisseFenster(liste, messung, angaben, frei, self)
        f.gewaehlt.connect(lambda p: self.pmi.waehle(lambda q: q is p))
        f.show()
        self._messergebnisse = f
        return f

    def zeige_stueckliste(self, nur_anlegen: bool = False):
        if self.erg is None:
            return None
        from .stueckliste_ui import StuecklisteFenster
        f = StuecklisteFenster(self.erg.baum, self.ein, os.path.splitext(self.erg.pfad)[0] + "_stueckliste.csv", self,
                               self.erg.modell.datei)
        f.isolieren.connect(self.ansicht.isoliere)
        f.isolieren.connect(lambda _n: self.statusBar().showMessage(
            tr("Teil isoliert – Umschalt+H zeigt wieder alle Teile"), 6000))
        if not nur_anlegen:
            f.show()
        self._stueckliste = f
        return f

    def erkenne_verzahnung(self, warten: bool = False):
        """Verzahnungsdaten der gewaehlten (sonst aller sichtbaren) Teile im Hintergrund erkennen."""
        from OCC.Core.TopLoc import TopLoc_Location
        from .ansicht3d import gp_trsf
        from .verzahnung_ui import VerzahnungLader
        if self.erg is None:
            return None
        gewaehlt = self.baum.gewaehlte_blaetter()
        lagen = self.baugruppe.lagen
        teile = [(k.name, k.form.Moved(TopLoc_Location(gp_trsf(lagen[k.nummer]))) if k.nummer in lagen else k.form)
                 for k in self.erg.baum.blaetter() if not k.hilfsgeometrie and k.nummer not in self.ansicht.versteckt
                 and (not gewaehlt or k.nummer in gewaehlt)]
        if not teile:
            return None
        lader = VerzahnungLader(teile, self)
        lader.stand.connect(self._prozent)
        lader.fehler.connect(lambda t: QtWidgets.QMessageBox.warning(self, tr("Verzahnung"), t))
        lader.fertig.connect(lambda liste, l=lader: l.abgebrochen or self._verzahnung_fertig(liste))
        self._verzahnung_lader = lader
        self._aufgabe(lader, tr("Verzahnung erkennen …"))
        lader.start()
        if warten:
            lader.wait()
            QtWidgets.QApplication.processEvents()
        return lader

    def _verzahnung_fertig(self, liste):
        from .verzahnung_ui import VerzahnungFenster
        self._danach()
        self._verzahnung = VerzahnungFenster(liste, os.path.splitext(self.erg.pfad)[0], self)
        self._verzahnung.show()
        self.statusBar().showMessage(tr("{} Verzahnung(en) erkannt").format(len(liste)), 8000)

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
        lader.stand.connect(self._prozent)
        lader.fehler.connect(lambda t: (self.analyse.start.setEnabled(True),
                                        QtWidgets.QMessageBox.warning(self, tr("Analyse"), t)))
        lader.fertig.connect(lambda k, a=art, w=dict(werte), l=lader: l.abgebrochen or self._analyse_fertig(a, w, k))
        self._analyse_lader = lader
        self.analyse.start.setEnabled(False)
        self._aufgabe(lader, tr("Analyse …"))
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

    def pmi_anlegen(self, uebernehmen: list | None = None):
        """Vorschlaege fuer die gewaehlten Flaechen; uebernehmen=None fragt per Dialog (sonst Liste der Vorschlaege)."""
        from ..kern import pmi_vorschlag
        from .pmi_anlegen_ui import PmiAnlegenDialog
        if self.erg is None:
            return []
        flaechen = sorted({i for f in self.ansicht.auswahl3d for i in [self.erg.modell.flaechen_index(f)]
                           if i is not None})
        if not flaechen:
            self.statusBar().showMessage(tr("Erst Flächen im Modell wählen"), 5000)
            return []
        vorschlaege = pmi_vorschlag.vorschlaege(flaechen, self.erg.modell, self.erg.pmi)
        if not vorschlaege:
            self.statusBar().showMessage(tr("Für diese Auswahl gibt es keinen Vorschlag"), 5000)
            return []
        if uebernehmen is None:
            d = PmiAnlegenDialog(vorschlaege, self)
            if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return []
            neue = d.gewaehlte()
        else:
            neue = [v.pmi for v in vorschlaege if v.pmi.typ in uebernehmen]
        return self.fuege_pmi_hinzu(neue)

    def bearbeite_pmi(self, p, werte: dict):
        """Werte einer PMI aendern; Dateiwerte bleiben als Ursprung gemerkt (Projekt speichert die Aenderung)."""
        if p.quelle != "eigen" and not getattr(p, "original", None):
            p.original = {k: getattr(p, k) for k in werte}
        for k, v in werte.items():
            setattr(p, k, v)
        p.bearbeitet = True
        self.ansicht.aktualisiere_pmi_texte([p])
        self.pmi.zeige(self.erg.pmi, self.erg.ansichten)
        self.pmi.waehle(lambda q: q is p)
        self.statusBar().showMessage(tr("PMI {} geändert: {}").format(p.nummer, p.wert_text()), 6000)

    def speichere_step_pmi(self, pfad: str = "", melden: bool = True):
        """Bearbeitete PMI-Werte in eine Kopie der STEP-Datei schreiben (kern.step_schreiben) und berichten."""
        from ..kern import step_schreiben
        if self.erg is None or not self.erg.pfad.lower().endswith((".stp", ".step")):
            self.statusBar().showMessage(tr("Nur für STEP-Dateien"), 5000)
            return None
        if not any((p.bearbeitet and p.original and p.quelle != "eigen") or p.quelle == "eigen" for p in self.erg.pmi):
            self.statusBar().showMessage(tr("Keine bearbeiteten oder eigenen PMI"), 5000)
            return None
        basis, endung = os.path.splitext(self.erg.pfad)
        pfad = pfad or self._speicherpfad(tr("STEP speichern"), basis + "_geaendert" + endung, "STEP (*.stp *.step)")
        if not pfad:
            return None
        if os.path.abspath(pfad) == os.path.abspath(self.erg.pfad):
            QtWidgets.QMessageBox.warning(self, tr("STEP speichern"), tr("Bitte unter neuem Namen speichern – die "
                                                                         "Originaldatei bleibt unverändert."))
            return None
        from ..kern.zusammenfuegen import pmi_der_ersten_datei
        b = step_schreiben.schreibe(self.erg.pfad, pfad, pmi_der_ersten_datei(self.erg), self.erg.modell)
        felder = {"neu": tr("(eigene PMI)"), "nennwert": tr("Nennmaß"), "oben": tr("Oberes Abmaß"), "unten": tr("Unteres Abmaß"),
                  "wert": tr("Toleranzwert"), "passung": tr("Toleranzklasse"), "material": tr("Materialbedingung")}
        zeilen = [tr("{} Werte geschrieben.").format(len(b.geschrieben))]
        if b.neu:
            zeilen.append(tr("{} eigene PMI neu angelegt: {}").format(len(b.neu), ", ".join(map(str, b.neu))))
        zeilen += [tr("Nicht geschrieben: PMI {} {} – {}").format(n, felder.get(f, f), grund)
                   for n, f, grund in b.uebersprungen]
        if b.grafik_veraltet:
            zeilen.append(tr("Die grafische Darstellung von PMI {} zeigt noch die alten Werte.").format(
                ", ".join(map(str, b.grafik_veraltet))))
        self._step_bericht = b
        if melden:
            QtWidgets.QMessageBox.information(self, tr("STEP gespeichert"), f"{pfad}\n\n" + "\n".join(zeilen))
        self.statusBar().showMessage(tr("STEP gespeichert: {}").format(pfad), 8000)
        return pfad

    def loesche_eigene_pmi(self, liste):
        weg = {id(p) for p in liste if p.quelle == "eigen"}
        if not weg:
            return
        ids = {p.step_id for p in liste if id(p) in weg}
        self.erg.pmi = [p for p in self.erg.pmi if id(p) not in weg]
        # erst die Ansicht: ihre Szene teilt sich das Grafik-Woerterbuch mit erg - danach faende sie nichts mehr
        self.ansicht.entferne_grafik(ids)
        for cid in [c for c, g in self.erg.grafik.items() if g.pmi_ids & ids]:
            del self.erg.grafik[cid]
        self.pmi.zeige(self.erg.pmi, self.erg.ansichten)
        self.statusBar().showMessage(tr("{} eigene PMI gelöscht").format(len(weg)), 5000)

    def zeige_kette2d(self, nur_anlegen: bool = False):
        """Fenster 2D-Toleranzkette (Vektorzug); Uebernahme ersetzt die Glieder im Fenster Toleranzkette."""
        from .kette2d_ui import Kette2DFenster
        f = getattr(self, "_kette2d", None)
        if f is None:
            f = Kette2DFenster(self)
            f.uebernehmen.connect(lambda gl, f=f: self._kette2d_uebernehmen(gl, f.kette.temperaturen,
                                                                            f.kette.anforderung))
            f.aus_auswahl.connect(self.kette2d_aus_auswahl)
            self._kette2d = f
            self._als_leiste(f, tr("2D-Toleranzkette"), "kette2d")
        if not nur_anlegen:
            self._leiste_zeigen(f, "kette2d")
        return f

    def zeige_kette3d(self, nur_anlegen: bool = False):
        """Fenster 3D-Toleranzkette (Lagen); Uebernahme ersetzt die Glieder im Fenster Toleranzkette."""
        from .kette3d_ui import Kette3DFenster
        f = getattr(self, "_kette3d", None)
        if f is None:
            f = Kette3DFenster(self)
            f.uebernehmen.connect(lambda gl, f=f: self._kette2d_uebernehmen(gl, f.kette.temperaturen,
                                                                            f.kette.anforderung))
            f.aus_teil.connect(self.kette3d_aus_teil)
            f.zeigen.connect(lambda linien: self.ansicht.zeige_hilfslinien(linien or [], einpassen=bool(linien)))
            self._kette3d = f
            self._als_leiste(f, tr("3D-Toleranzkette"), "kette3d")
        if not nur_anlegen:
            self._leiste_zeigen(f, "kette3d")
        return f

    def _punkt_von_form(self, form):
        """Kennpunkt eines gewaehlten Elements: Punkt, Kreismitte bzw. Kantenmitte, Achspunkt eines Zylinders bzw.
        Flaechenschwerpunkt (Welt)."""
        import numpy as np
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
        from OCC.Core.TopoDS import topods
        art = form.ShapeType()
        if art == TopAbs_VERTEX:
            p = BRep_Tool.Pnt(topods.Vertex(form))
            return np.array([p.X(), p.Y(), p.Z()])
        pr = GProp_GProps()
        if art == TopAbs_EDGE:
            c = BRepAdaptor_Curve(topods.Edge(form))
            if c.GetType() == GeomAbs_Circle:
                p = c.Circle().Location()
                return np.array([p.X(), p.Y(), p.Z()])
            brepgprop.LinearProperties(form, pr)
        elif art == TopAbs_FACE:
            brepgprop.SurfaceProperties(form, pr)
            s = BRepAdaptor_Surface(topods.Face(form), True)
            if s.GetType() == GeomAbs_Cylinder:  # Achspunkt auf Hoehe des Schwerpunkts
                ax = s.Cylinder().Axis()
                o, d = ax.Location(), ax.Direction()
                o, d = np.array([o.X(), o.Y(), o.Z()]), np.array([d.X(), d.Y(), d.Z()])
                m = pr.CentreOfMass()
                m = np.array([m.X(), m.Y(), m.Z()])
                return o + d * float((m - o) @ d)
        else:
            return None
        m = pr.CentreOfMass()
        return np.array([m.X(), m.Y(), m.Z()])

    def kette2d_aus_auswahl(self) -> int:
        """2D-Kette aus den gewaehlten Elementen: Kennpunkte in Klickreihenfolge, projiziert in die Blickebene,
        Laengen mit der Allgemeintoleranz (Wahl oder Datei); ersetzt die Segmente des Fensters."""
        from ..kern import kette2d as k2, toleranzzone
        w = self.zeige_kette2d()
        if self.erg is None:
            return 0
        punkte = [p for f in self.ansicht.auswahl3d if (p := self._punkt_von_form(f)) is not None]
        if len(punkte) < 2:
            self.statusBar().showMessage(tr("Erst mindestens zwei Punkte, Kanten oder Flächen im Modell wählen "
                                            "(Strg/⌘ für weitere)"), 6000)
            return 0
        rechts, oben = self.ansicht.blickebene()
        pts2 = [(float(p @ rechts), float(p @ oben)) for p in punkte]
        allgemein = self._allgemein or toleranzzone.allgemein_aus_hinweisen(self.erg.pmi)
        klasse = allgemein.laenge if allgemein else ""
        segmente = k2.aus_punkten(pts2, [f"P{i + 1}" for i in range(len(pts2))],
                                  (lambda l: toleranzzone.iso2768_laenge(klasse, l)) if klasse else None)
        w.setze_kette(k2.Kette2D(segmente, w.kette.schluss, w.kette.werkstoff, w.kette.temperaturen,
                                 w.kette.anforderung, w.kette.freigabe))
        self.statusBar().showMessage(tr("{} Segmente aus der Auswahl (Blickebene){}").format(
            len(segmente), tr(", Längen ISO 2768-{}").format(klasse) if klasse else ""), 8000)
        return len(segmente)

    def kette3d_aus_teil(self) -> bool:
        """Glied fuer das gewaehlte Teil des Zusammenbaus an die 3D-Kette haengen (vom letzten Kettenpunkt aus)."""
        import numpy as np
        from ..kern import kette3d as k3
        from ..kern.baugruppe_mass import Analyse
        w = self.zeige_kette3d()
        teil = next((t for t in reversed(self.ansicht.auswahl_teile) if t is not None), None)
        if self.erg is None or teil is None:
            self.statusBar().showMessage(tr("Erst ein Teil des Zusammenbaus im Modell wählen"), 6000)
            return False
        k = w.kette
        vorher = k3.lagen(k)[-1][1] if k.glieder and k.basis is None else np.zeros(3)
        if k.basis is not None:
            self.statusBar().showMessage(tr("Diese Kette liegt in einer eigenen Basis – Teile nur in Ketten in "
                                            "Weltlage anhängen"), 6000)
            return False
        neu = Analyse(self.baugruppe).glied_fuer_teil(teil, vorher, self._teil_namen().get(teil, str(teil)))
        if neu is None:
            self.statusBar().showMessage(tr("Das Teil ist fest oder hat keine Verbindung im Zusammenbau"), 6000)
            return False
        w.neues_glied(neu[0])
        return True

    def _kette2d_uebernehmen(self, glieder: list, temperaturen: tuple | None = None, anforderung: tuple | None = None):
        """Linearisierte 2D/3D-Kette ins 1D-Fenster; die Werkstoffe stecken in den Gliedern, Grenztemperaturen und
        Anforderung der Kette werden mit uebernommen."""
        k = self.zeige_toleranzkette()
        k.beende_planspiel(False)
        k.setze_glieder(glieder)
        if temperaturen:
            k.t1.setValue(temperaturen[0])
            k.t2.setValue(temperaturen[1])
            k.waerme.setChecked(True)
        if anforderung:
            k.unten.setValue(anforderung[0])
            k.oben.setValue(anforderung[1])
            k.anforderung.setChecked(True)
        self.statusBar().showMessage(tr("Kette als {} Glieder übernommen (linearisiert)").format(len(glieder)), 6000)

    def zeige_funktion(self, nur_anlegen: bool = False):
        """Fenster Funktion -> Tolerierung (kern.funktion) fuer das geladene Modell."""
        from .funktion_ui import FunktionFenster
        f = getattr(self, "_funktion", None)
        if f is None:
            f = FunktionFenster(self)
            f.auswahl = lambda: sorted({i for x in self.ansicht.auswahl3d
                                        for i in [self.erg.modell.flaechen_index(x)] if i is not None}) \
                if self.erg is not None else []
            f.flaechen_zeigen.connect(self.ansicht.hebe_flaechen)
            f.flaechen_zeigen.connect(self._funktion_vorschau_hervor)
            f.vorschau.connect(self.funktion_vorschau)
            f.anlegen.connect(self._funktion_anlegen)
            self._funktion = f
            self._als_leiste(f, tr("Funktion → Tolerierung"), "funktion")
        f.setze_modell(self.erg.modell if self.erg is not None else None)
        if not nur_anlegen:
            self._leiste_zeigen(f, "funktion")
        return f

    def funktion_vorschau(self, d: dict | None):
        """Vorschau aus Funktion -> Tolerierung: Bezugsflaechen A/B/C farbig, offene Freiheitsgrade als Pfeile bzw.
        Kreise, die Vorschlaege als Callouts (eigene, nur angezeigte PMI) und auf Wunsch deren Toleranzzonen; None
        entfernt alles wieder."""
        import copy
        from ..kern import pmi_erzeugen
        alt = getattr(self, "_vorschau_pmi", [])
        if alt:
            self.ansicht.entferne_grafik({p.step_id for p in alt})
        if alt or getattr(self, "_vorschau_teile", False):
            self.ansicht.zeige_bezugssystem([])
            self.ansicht.zeige_hilfslinien([])
            self.ansicht.zeige_zone([])
        self._vorschau_pmi, self._vorschau_teile = [], False
        if d is None or self.erg is None:
            return
        self._vorschau_teile = True
        self.ansicht.zeige_bezugssystem(d["bezuege"])
        a = next((f for _b, _s, f in d["bezuege"]), None)
        self.ansicht.zeige_hilfslinien(self._freiheitsgrad_linien(d["offen"], a))
        neue = []
        for i, v in enumerate(d["vorschlaege"], 1):
            p = copy.deepcopy(v.pmi)
            p.nummer, p.step_id, p.quelle, p.semantisch = 0, -900_000 - i, "vorschau", True
            p.name = p.name or tr(p.merkmal())
            neue.append(p)
        grafik = pmi_erzeugen.ergaenze(neue, dict(self.erg.grafik), self.erg.modell, self.erg.ansichten)
        frei = min(list(self.erg.grafik) + [0]) - 1
        for g in grafik.values():
            g.vorschau = True  # eigene Farbe, immer sichtbar
        self.ansicht.ergaenze_grafik({frei - i: g for i, g in enumerate(grafik.values())}, neue)
        self._vorschau_pmi = neue
        if d.get("zonen"):
            from ..kern import toleranzzone
            ergebnis = toleranzzone.zonen(neue, self.erg.modell, self._zonen_mindest(), self.erg.pmi + neue)
            zonen = [z for _p, z in ergebnis]
            self.ansicht.zeige_zone([f for z in zonen for f in z.formen], [r for z in zonen for r in z.rollen])

    def _funktion_vorschau_hervor(self, flaechen: set):
        """Tabellenzeile gewaehlt: ihre Vorschau-Callouts hervorheben."""
        ids = {p.step_id for p in getattr(self, "_vorschau_pmi", []) if p.flaechen & set(flaechen)}
        if ids:
            self.ansicht.hebe_pmi(ids)

    def _zonen_mindest(self) -> float:
        """Mindestbreite der Zonendarstellung (schmalere werden ueberhoeht): 1/250 der Modellgroesse."""
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        box = Bnd_Box()
        brepbndlib.Add(self.erg.modell.form, box)
        x0, y0, z0, x1, y1, z1 = box.Get()
        return max(x1 - x0, y1 - y0, z1 - z0) / 250

    def _freiheitsgrad_linien(self, offen: list, flaechen) -> list:
        """Offene Freiheitsgrade als Hilfslinien: Verschiebung als Doppelpfeil, Drehung als Kreis um die Achse -
        am Bezug A (sonst in der Modellmitte)."""
        import math
        import numpy as np
        if not offen:
            return []
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        box = Bnd_Box()
        brepbndlib.Add(self.erg.modell.form, box)
        x0, y0, z0, x1, y1, z1 = box.Get()
        groesse = max(x1 - x0, y1 - y0, z1 - z0) or 1.0
        mitte = self.ansicht.mitte_von(flaechen) if flaechen else None
        mitte = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]) if mitte is None else np.asarray(mitte, float)
        farbe, lang, linien = (0.95, 0.55, 0.05), 0.35 * groesse, []
        for o in offen:
            r = np.asarray(o.richtung, float)
            if o.art == "verschiebung":
                a, b = mitte - r * lang / 2, mitte + r * lang / 2
                linien.append((a, b, tr("Verschiebung offen"), farbe, 3.0))
                for spitze, gegen in ((b, -r), (a, r)):  # Pfeilspitzen an beiden Enden
                    quer = np.cross(r, [1.0, 0, 0] if abs(r[0]) < 0.9 else [0, 1.0, 0])
                    quer = quer / np.linalg.norm(quer) * lang * 0.06
                    linien += [(spitze, spitze + gegen * lang * 0.1 + quer, "", farbe, 3.0),
                               (spitze, spitze + gegen * lang * 0.1 - quer, "", farbe, 3.0)]
                continue
            p = np.asarray(o.punkt, float) if o.punkt is not None else mitte
            p = p + r * float((mitte - p) @ r)  # Kreis auf Hoehe des Bezugs
            u = np.cross(r, [1.0, 0, 0] if abs(r[0]) < 0.9 else [0, 1.0, 0])
            u = u / np.linalg.norm(u)
            w = np.cross(r, u)
            rad, n = lang / 2, 36
            pkt = [p + rad * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w)
                   for k in range(n + 1)]
            linien += [(pkt[k], pkt[k + 1], tr("Drehung offen") if k == 0 else "", farbe, 3.0) for k in range(n)]
        return linien

    def _funktion_anlegen(self, vorschlaege: list, fragen: bool = True) -> list:
        """Vorschlaege aus Funktion -> Tolerierung im Dialog PMI anlegen pruefen und als eigene PMI uebernehmen."""
        from .pmi_anlegen_ui import PmiAnlegenDialog
        if not vorschlaege or self.erg is None:
            return []
        self.funktion_vorschau(None)  # die Vorschau weicht den echten PMI (die Tabelle zeigt sie danach neu)
        if fragen:
            d = PmiAnlegenDialog(vorschlaege, self)
            if d.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return []
            return self.fuege_pmi_hinzu(d.gewaehlte())
        return self.fuege_pmi_hinzu([v.pmi for v in vorschlaege])

    def fuege_pmi_hinzu(self, neue: list) -> list:
        """Eigene PMI ins Modell: Nummer, Kennung, Norm, erzeugte Darstellung, Liste aktualisieren."""
        from ..kern import pmi_erzeugen
        if not neue:
            return []
        start = max((p.nummer for p in self.erg.pmi), default=0)
        kleinste = min([p.step_id for p in self.erg.pmi if p.step_id < 0] + [-1000])
        norm = self.erg.pmi[0].norm if self.erg.pmi else "iso"
        for i, p in enumerate(neue, 1):
            p.nummer, p.step_id, p.quelle, p.norm = start + i, kleinste - i, "eigen", norm
            p.semantisch, p.grafisch = True, bool(p.callout)  # semantisch gemachte Grafik der Datei behaelt sie
            if not p.name:
                p.name = f"{tr(p.merkmal())}.{p.nummer}" if p.art != "bezug" else p.name
        ersetzt = {p.callout for p in neue if p.callout}  # der nur grafische Eintrag weicht der eigenen PMI
        self.erg.pmi = [q for q in self.erg.pmi if q.quelle == "eigen" or q.step_id not in ersetzt]
        self.erg.pmi.extend(neue)
        grafik = pmi_erzeugen.ergaenze(neue, self.erg.grafik, self.erg.modell, self.erg.ansichten)
        frei = min(list(self.erg.grafik) + [0]) - 1
        grafik = {frei - i: g for i, g in enumerate(grafik.values())}
        self.erg.grafik.update(grafik)
        self.ansicht.ergaenze_grafik(grafik, neue)
        self.pmi.zeige(self.erg.pmi, self.erg.ansichten)
        self.pmi.waehle(lambda p: p in neue)
        self.statusBar().showMessage(tr("{} PMI angelegt (eigene, werden im Projekt gespeichert)").format(len(neue)), 6000)
        return neue

    def zeige_toleranzkette(self, nur_anlegen: bool = False):
        """Fenster Toleranzkette; die Knoepfe uebernehmen die in der PMI-Liste gewaehlten Masse."""
        from .toleranzkette_ui import ToleranzketteFenster
        f = getattr(self, "_kette", None)
        if f is None:
            f = ToleranzketteFenster(self)
            f.plus.clicked.connect(lambda: self._kette_uebernehmen(+1))
            f.minus.clicked.connect(lambda: self._kette_uebernehmen(-1))
            f.auswahl.clicked.connect(self._kette_aus_auswahl)
            f.pdf.clicked.connect(lambda: self.exportiere_kette_pdf())
            f.flaechen_zeigen.connect(self.ansicht.hebe_flaechen)
            f.schluss_aus_auswahl.connect(self._kette_schluss)
            f.strecke_zeigen.connect(self._kette_strecke)
            f.bild_zeigen.connect(self._kette_bild)
            f.schluss_wiggle.connect(self.schluss_wiggle)
            f.finished.connect(lambda _r: f.wiggle.setChecked(False))  # Leiste zu: Wiggle aus
            f.oeffnen.connect(lambda: self.oeffne_kette())
            f.teil_von = self._teil_von_flaechen
            self._kette = f
            self._als_leiste(f, tr("Toleranzkette"), "kette")
        if self.erg is not None and f.modell_pfad != self.erg.pfad:
            f.modell_pfad = self.erg.pfad
            self._werkstoffe_vorbelegen(f)
        if not nur_anlegen:
            self._leiste_zeigen(f, "kette")
        return f

    def _teil_von_flaechen(self, flaechen) -> str:
        """Bauteil (Blattname im Baum) der meisten dieser Flaechen; leer ohne Zuordnung."""
        if self.erg is None or not flaechen:
            return ""
        zuordnung = getattr(self, "_flaeche_teil", None)
        if zuordnung is None or zuordnung[0] is not self.erg:
            from OCC.Core.TopAbs import TopAbs_FACE
            from OCC.Core.TopExp import TopExp_Explorer
            karte = {}
            for k in self.erg.baum.blaetter():
                ex = TopExp_Explorer(k.form, TopAbs_FACE)
                while ex.More():
                    i = self.erg.modell.flaechen_index(ex.Current())
                    if i is not None:
                        karte.setdefault(i, k.name)
                    ex.Next()
            zuordnung = self._flaeche_teil = (self.erg, karte)
        namen = [zuordnung[1][i] for i in flaechen if isinstance(i, int) and i in zuordnung[1]]
        return max(set(namen), key=namen.count) if namen else ""

    def _werkstoffe_vorbelegen(self, f):
        """Werkstoffe je Bauteil aus der STEP-Datei mit alpha aus der Bibliothek (ohne vorhandene zu ersetzen)."""
        from ..kern import werkstoffe
        for teil, name in werkstoffe.werkstoffe_aus_step(getattr(self.erg.modell, "datei", None)).items():
            f.werkstoffe.setdefault(teil, {"name": name, "alpha": werkstoffe.alpha_fuer(name)})

    def oeffne_kette(self, pfad: str = "", warten: bool = False):
        """Kettendatei laden; gehoert sie zu einem anderen Modell, wird dieses zuerst geladen."""
        from ..kern import kette_datei
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("Kette öffnen"), "",
                                                            tr("Toleranzkette (*.3dgkette)"))
            if not pfad:
                return None
        try:
            k = kette_datei.lade(pfad)
        except (OSError, ValueError) as fehler:
            QtWidgets.QMessageBox.warning(self, tr("Kette öffnen"), str(fehler))
            return None
        anderes = k.modell and os.path.isfile(k.modell) and (
            self.erg is None or os.path.abspath(self.erg.pfad) != os.path.abspath(k.modell))
        if anderes:
            self._nach_laden = lambda: self._kette_anwenden(k)
            self.lade(k.modell, warten)
        else:
            self._kette_anwenden(k)
        return k

    def _kette_anwenden(self, k):
        f = self.zeige_toleranzkette()
        f.lade_datei(k)
        if self.erg is None or (k.modell and os.path.basename(k.modell) != os.path.basename(self.erg.pfad)):
            self.statusBar().showMessage(tr("Kette gehört zu {} – Flächen nur mit diesem Modell").format(
                os.path.basename(k.modell) or "?"), 8000)
        else:
            self.statusBar().showMessage(tr("Kette geladen: {} Glieder").format(len(k.glieder)), 6000)

    def _kette_strecke(self, g):
        """Glied beim Ablaufen als Pfeil zwischen seinen Flaechen, Spitze in Wirkrichtung, Farbe wie im Kettenbild."""
        from ..kern import toleranzkette as tk
        linien = tk.glied_pfeil(g, self.erg.modell) if g is not None and self.erg is not None else []
        self.ansicht.zeige_hilfslinien(linien)

    def schluss_wiggle(self, an: bool) -> bool:
        """Wiggle der Schlussflaechen (kern.schluss_wiggle): Endflaeche zwischen den Worst-Case-Grenzen, ueberhoeht,
        gruen in der Anforderung, rot ausserhalb; False, wenn die Kette keine Schlussflaechen im Modell hat."""
        from ..kern import schluss_wiggle as sw
        uhr = getattr(self, "_schluss_uhr", None)
        if uhr is None:
            uhr = self._schluss_uhr = QtCore.QTimer(self)
            uhr.setInterval(60)
            uhr.timeout.connect(self._schluss_wiggle_schritt)
        k = getattr(self, "_kette", None)
        s = sw.schlussflaechen(k.glieder, self.erg.modell) if an and k is not None and self.erg is not None else None
        if s is None or getattr(k, "e", None) is None:
            uhr.stop()
            self.ansicht.zeige_schlussflaeche(None)
            if an:
                self.statusBar().showMessage(tr("Wiggle braucht eine Kette aus Modellflächen in Kettenreihenfolge "
                                                "(„Aus 3D-Auswahl“ oder „Richtungen aus Schlussmaß“)"), 8000)
                k.wiggle.setChecked(False)
            return False
        self._schluss = [s, 0]
        uhr.start()
        self._schluss_wiggle_schritt()
        return True

    def _schluss_wiggle_schritt(self):
        """Naechstes Bild aus dem aktuellen Ergebnis (Werte im Fenster duerfen sich waehrenddessen aendern)."""
        import numpy as np
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.gp import gp_Trsf, gp_Vec
        from ..kern import schluss_wiggle as sw
        k, (s, nr) = self._kette, self._schluss
        if self.erg is None or k.e is None:
            return self.schluss_wiggle(False)
        b = Bnd_Box()
        brepbndlib.Add(self.erg.modell.form, b)
        x0, y0, z0, x1, y1, z1 = b.Get()
        faktor = sw.faktor(k.e, max(x1 - x0, y1 - y0, z1 - z0))
        bilder = sw.bilder(s, k.e, k.anforderung_werte(), faktor)
        bild = bilder[nr % len(bilder)]
        self._schluss[1] = nr + 1
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(*map(float, bild.versatz)))
        form = BRepBuilderAPI_Transform(self.erg.modell.flaechen[s.ende], t, True).Shape()
        pr = GProp_GProps()
        brepgprop.SurfaceProperties(form, pr)
        c = pr.CentreOfMass()
        farbe = {"gruen": (0.18, 0.62, 0.28), "rot": (0.85, 0.20, 0.15)}.get(bild.stufe, (0.13, 0.42, 0.85))
        text = f"{round(bild.wert, 4) + 0.0:.4f} mm" + (tr("  (Bewegung ×{:.0f})").format(faktor) if faktor > 1.5 else "")
        self.ansicht.zeige_schlussflaeche(form, farbe, text, np.array([c.X(), c.Y(), c.Z()]))
        return True

    def _kette_bild(self, daten):
        """Ganze Kette als Pfeildiagramm im Modell (kern.toleranzkette.kettenbild); None blendet es aus."""
        from ..kern import toleranzkette as tk
        neu = not getattr(self, "_kettenbild_an", False)
        self._kettenbild_an = daten is not None
        if daten is None:
            self.ansicht.zeige_hilfslinien([])
            return
        glieder, text, ist, hervor = daten
        self.ansicht.zeige_hilfslinien(tk.kettenbild(glieder, self.erg.modell if self.erg else None, text, ist,
                                                     self.ansicht.oben_richtung(), hervor), einpassen=neu)

    def _kette_schluss(self):
        """Reihenfolge und Vorzeichen der Glieder aus den zwei gewaehlten Flaechen des Schlussmasses."""
        from ..kern import toleranzkette as tk
        f = self._kette
        idx = [self.erg.modell.flaechen_index(x) for x in self.ansicht.auswahl3d] if self.erg is not None else []
        idx = [i for i in idx if i is not None]
        if len(idx) != 2 or not f.glieder:
            self.statusBar().showMessage(tr("Erst die Glieder anlegen, dann genau zwei Flächen des Schlussmaßes "
                                            "wählen (die erste eben)"), 8000)
            return None
        glieder, hinweise = tk.richtungen_aus_schlussmass(f.glieder, self.erg.modell, idx[0], idx[1])
        f.setze_glieder(glieder)
        self.statusBar().showMessage(" · ".join(hinweise) if hinweise else
                                     tr("Richtungen aus dem Schlussmaß gesetzt – „Kette ablaufen“ zeigt sie"), 10000)
        return hinweise

    def _fuegestelle(self, flaechen: list, teile: list, k: int):
        """Teilewechsel zwischen der k-ten und (k+1)-ten Kettenflaeche: (Name, Spielraum) der Verbindung der Baugruppe
        zwischen diesen Flaechen, sonst None (Kontakt angenommen, Lage aus der Datei)."""
        ta, tb = teile[k], teile[k + 1]
        if ta is None or tb is None or ta == tb:
            return None
        fa, fb = flaechen[k], flaechen[k + 1]
        for v in self.baugruppe.verbindungen:
            if {(v.teil, v.flaeche), (v.gegen_teil, v.gegen_flaeche)} == {(ta, fa), (tb, fb)}:
                namen = self._teil_namen()
                return f"{namen.get(ta, ta)} / {namen.get(tb, tb)}", float(v.toleranz)
        return None

    def _kette_aus_auswahl(self) -> int:
        """Glieder aus den im Modell gewaehlten Flaechen (Klickreihenfolge); Allgemeintoleranz aus Wahl oder Datei."""
        from ..kern import toleranzkette as tk, toleranzzone
        if self.erg is None:
            return 0
        from OCC.Core.TopAbs import TopAbs_FACE
        # Flaechen als Index (PMI-Zuordnung), Kanten als Form
        paare = [(self.erg.modell.flaechen_index(f) if f.ShapeType() == TopAbs_FACE else f, t)
                 for f, t in zip(self.ansicht.auswahl3d, self.ansicht.auswahl_teile)]
        paare = [(f, t) for f, t in paare if f is not None]
        flaechen, teile = [f for f, _ in paare], [t for _, t in paare]
        allgemein = self._allgemein or toleranzzone.allgemein_aus_hinweisen(self.erg.pmi)
        k = self._kette
        glieder, richtung, hinweise = tk.kette_aus_flaechen(
            self.erg.modell, flaechen, self.erg.pmi, allgemein.laenge if allgemein else "", k.lage.isChecked(),
            k.mitte_anfang.isChecked(), k.mitte_ende.isChecked(), lambda i: self._fuegestelle(flaechen, teile, i))
        self._kette.ergaenze(glieder)
        if glieder:
            text = tr("{} Glieder entlang ({:.3g}, {:.3g}, {:.3g})").format(len(glieder), *richtung)
            self.statusBar().showMessage("; ".join([text] + hinweise), 10000)
        else:
            self.statusBar().showMessage("; ".join(hinweise), 8000)
        return len(glieder)

    def exportiere_kette_pdf(self, pfad: str = "") -> str | None:
        from .berichte import kette_pdf
        if self.erg is None or getattr(self, "_kette", None) is None or not self._kette.glieder:
            return None
        pfad = pfad or self._speicherpfad(tr("PDF-Bericht"), os.path.splitext(self.erg.pfad)[0] + "_kette.pdf",
                                          "PDF (*.pdf)")
        if not pfad:
            return None
        ziel = kette_pdf(self, pfad)
        self.statusBar().showMessage(tr("PDF gespeichert: {}").format(ziel), 6000)
        return ziel

    def _kette_uebernehmen(self, richtung: int):
        from ..kern import toleranzkette as tk
        gewaehlt = self.pmi.gewaehlte()
        n = self._kette.uebernimm(gewaehlt, richtung)
        winkel = sum(1 for p in gewaehlt if p.art == "mass" and tk.ist_winkel(p))
        if winkel:
            self.statusBar().showMessage(tr("{} Winkelmaße nicht übernommen (Kette rechnet Längen)").format(winkel), 6000)
        elif not n:
            self.statusBar().showMessage(tr("Erst Maße mit Nennmaß in der PMI-Liste wählen"), 5000)

    def _explosion_einpassen(self):
        """Alle Teile im Bild halten; ein gesetzter Drehpunkt bleibt dabei erhalten."""
        self.ansicht.alles_zeigen()

    def _explosion_umschalten(self):
        an = self.aktionen["explosion"].isChecked()
        self.explosion_regler_aktion.setVisible(an)
        self.explosion_achse_aktion.setVisible(an)
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
        fenster = PruefFenster(pmi_bericht.pruefe(self.erg.pmi, self.erg.ansichten, self.erg.modell), self)
        fenster.pmi_waehlen.connect(lambda nummern: self.pmi.waehle(lambda p: p.nummer in nummern))
        fenster.flaechen_waehlen.connect(self.ansicht.hebe_flaechen)
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
        elif art == "zone":
            self.aktionen["toleranzzone"].setChecked(True)
            self._zone_aktualisieren(wert)
        elif art == "bearbeiten":
            from .pmi_anlegen_ui import PmiBearbeitenDialog
            d = PmiBearbeitenDialog(wert, self)
            if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self.bearbeite_pmi(wert, d.werte())
        elif art == "loeschen":
            self.loesche_eigene_pmi(wert)
        elif art == "semantisch":
            from .semantik_ui import semantisch_machen
            semantisch_machen(self, wert)

    def _grafik_umschalten(self):
        an = self.aktionen["grafik"].isChecked()
        self.aktionen["grafik_auswahl"].setEnabled(an and self.erg is not None)
        self.aktionen["grafik_erzeugt"].setEnabled(an)
        self.ansicht.setze_grafik(an, self.aktionen["grafik_auswahl"].isChecked(),
                                  self.aktionen["grafik_erzeugt"].isChecked())

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
        if achse is None and self.ansicht.schnitt_ebenen:
            self.ansicht.schnitt_ebenen = []  # "Kein Schnitt" hebt auch festgehaltene Ebenen auf
        if achse is None and self.ansicht.ansicht_schnitt:
            self.ansicht.setze_ansicht_schnitt([])  # ... und den Schnitt einer gespeicherten Ansicht
        self._schnitt_achse = achse
        da = self.erg is not None
        self.schnitt_regler.setEnabled(da and achse is not None)
        self.schnitt_regler_aktion.setVisible(da and achse is not None)
        self.aktionen["schnitt_umkehren"].setEnabled(da and achse is not None)
        self.ansicht.schnitt(achse, self.schnitt_regler.value() / 1000.0,
                             self.aktionen["schnitt_umkehren"].isChecked())
        self._schnitt_aktionen()

    def _schnitt_aktionen(self):
        """Freigabe der Aktionen fuer mehrere Schnittebenen und den Konturexport."""
        da = self.erg is not None
        for n in ("schnitt_merken", "schnitt_kontur"):
            self.aktionen[n].setEnabled(da and self._schnitt_achse is not None)
        for n in ("schnitt_kette", "schnitt_loeschen"):
            self.aktionen[n].setEnabled(da and bool(self.ansicht.schnitt_ebenen))

    def _schnittbox(self):
        if not self.aktionen["schnittbox"].isChecked():
            self.ansicht.schnittbox(None)
            return
        if not self.ansicht.schnittbox_um_auswahl():
            self.aktionen["schnittbox"].setChecked(False)
            self.statusBar().showMessage(tr("Erst Flächen oder Kanten im Modell wählen"), 5000)
            return
        self.ansicht.zoome_auf(set(), list(self.ansicht.auswahl3d))

    def _schnitt_umkehren(self):
        self._schnitt(self._schnitt_achse)

    def _schnitt_merken(self):
        if not self.ansicht.schnitt_merken():
            self.statusBar().showMessage(tr("Höchstens drei Schnittebenen; erst einen Schnitt wählen"), 5000)
            return
        n = len(self.ansicht.schnitt_ebenen)
        self.statusBar().showMessage(tr("{} Schnittebene(n) festgehalten – jetzt die nächste wählen").format(n), 6000)
        self._schnitt(self._schnitt_achse)

    def _schnitt_kette(self):
        self.ansicht.setze_schnitt_kette(self.aktionen["schnitt_kette"].isChecked())

    def _schnitt_ebenen_loeschen(self):
        self.ansicht.schnitt_ebenen_loeschen()
        self._schnitt(self._schnitt_achse)
        self._schnitt_aktionen()

    def _sichtbare_form(self):
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        form = TopoDS_Compound()
        bb = BRep_Builder()
        bb.MakeCompound(form)
        for k in self.erg.baum.blaetter():
            if not k.hilfsgeometrie and k.nummer not in self.ansicht.versteckt:
                bb.Add(form, k.form)
        return form

    def exportiere_schnittkontur(self, pfad: str = "") -> str | None:
        """Schnittkonturen aller Ebenen (festgehaltene und aktuelle) nebeneinander als SVG, DXF oder PDF."""
        import numpy as np
        from ..kern import schnitt, zeichnung
        from . import berichte
        ebenen = self.ansicht.alle_schnitt_ebenen() if self.erg is not None else []
        if not ebenen:
            self.statusBar().showMessage(tr("Erst einen Schnitt wählen"), 5000)
            return None
        pfad = pfad or self._speicherpfad(tr("Schnittkontur speichern"),
                                          os.path.splitext(self.erg.pfad)[0] + "_schnitt.svg",
                                          "SVG (*.svg);;DXF (*.dxf);;PDF (*.pdf)")
        if not pfad:
            return None
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            liste = [schnitt.Ebene(np.asarray(p, float), -np.asarray(r, float), tr("Schnitt {}").format(i))
                     for i, (p, r) in enumerate(ebenen, 1)]
            ansichten = schnitt.blatt(self._sichtbare_form(), liste)
            name = os.path.basename(self.erg.pfad)
            endung = os.path.splitext(pfad)[1].lower()
            if endung == ".dxf":
                with open(pfad, "w", encoding="ascii", errors="replace") as f:
                    f.write(zeichnung.als_dxf(ansichten))
            elif endung == ".pdf":
                berichte.zeichnung_pdf(zeichnung.als_svg(ansichten, name), pfad, name,
                                       f"{tr('Schnittkontur')} · {tr('Maße in mm')} · 3DGmax {VERSION}")
            else:
                with open(pfad, "w", encoding="utf-8") as f:
                    f.write(zeichnung.als_svg(ansichten, name))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(tr("Schnittkontur gespeichert: {}").format(pfad), 8000)
        return pfad

    def _isolieren(self):
        nummern = self.baum.gewaehlte_blaetter()
        if nummern:
            self.ansicht.isoliere(nummern)
        else:
            self.statusBar().showMessage(tr("Erst Teile in der Struktur wählen"), 4000)

    def pruefe_scan(self, pfad: str = "", warten: bool = False, bezug: tuple | None = None, start=None,
                    anlage: bool | None = None):
        """Scan (Netz oder Punktwolke) gegen die PMI des geoeffneten CAD-Modells pruefen; bezug: Bezugssystem fuer
        die 3-2-1-Ausrichtung (None: Bestpassung)."""
        from .scan_ui import ScanLader
        if self.erg is None:
            return
        if not pfad:
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, tr("Scan wählen"), os.path.dirname(self.erg.pfad),
                tr("Netze und Punktwolken") + " (*.stl *.ply *.obj *.3mf *.glb *.gltf *.xyz *.asc *.txt *.csv *.pts *.e57);;"
                + tr("Alle Dateien") + " (*)")
        if not pfad:
            return
        self.scan_aus()
        anlage = self.scan.anlage.isChecked() if anlage is None else anlage
        lader = ScanLader(self.erg, pfad, self, bezug, start, anlage and bool(bezug))
        lader.stand.connect(lambda t: self.statusBar().showMessage(t))
        lader.fehler.connect(lambda t: QtWidgets.QMessageBox.warning(self, tr("Scanprüfung"), t))
        lader.fertig.connect(lambda d, l=lader: l.abgebrochen or self._scan_fertig(d))
        self._scan_lader = lader
        self._aufgabe(lader)
        lader.start()
        if warten:
            lader.wait()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()

    def _scan_fertig(self, d):
        from ..kern import abweichung, scanpruefung as sp
        self._scan = d
        karte = d["karte"]
        grenze = max(abweichung.standard_grenze(karte, 0.02), 0.05)
        self._scan_karte = (karte, grenze)
        self.scan.aus.blockSignals(True)
        self.scan.aus.setChecked(False)
        self.scan.aus.setText(tr("Scan ausblenden"))
        self.scan.aus.blockSignals(False)
        self.scan_leiste.show()
        self.setze_scanmodus("vergleich")
        kopf = self._scan_kopf(d)
        self.scan.setze_bezugssysteme(sp.bezugssysteme(self.erg.pmi), d.get("bezug"))
        self.scan.zeige(d["ergebnisse"], kopf)
        z = self.scan.zaehler()
        self.dock_scan.show()
        self.dock_scan.raise_()
        self.statusBar().showMessage(tr("Scanprüfung: {} i. O., {} n. i. O., {} am Grenzwert, {} nicht auswertbar").format(
            z[sp.OK], z[sp.NOK], z[sp.GRENZ], z[sp.OFFEN]), 15000)

    def scan_von_hand(self):
        """Startlage des Scans ueber Punktpaare: Scan durchscheinend und waehlbar, Modell wie gewohnt; danach neu
        auswerten (Feinausrichtung, ggf. Bezugssystem)."""
        import numpy as np
        from ..kern.laden import lade_modell
        d = getattr(self, "_scan", None)
        if d is None:
            return None
        if d.get("punktwolke"):
            self.statusBar().showMessage(tr("Punktwolken lassen sich nicht von Hand ausrichten – Netz verwenden"), 8000)
            return None
        scan = d.get("scan_modell") or lade_modell(d["pfad"])
        d["scan_modell"] = scan
        # Rollen: Scan "alt" (durchscheinend, in Dateilage), Modell "neu" – unverschoben gezeigt, daher Einheitsmatrix
        self._ausricht = AusrichtPanel(np.eye(4), self.ansicht.fang_toleranz, self)
        self.ansicht.setze_ausrichtmodus(scan.form)
        self.ansicht.ausricht_punkt.connect(self._ausricht.punkt)
        self._ausricht.ausrichten.connect(self._scan_hand_fertig)
        self._ausricht.beendet.connect(self._ausrichten_beenden)
        self._ausricht.show()
        return self._ausricht

    def _scan_hand_fertig(self, ausrichtung, warten: bool = False):
        """Ausrichtung Modell -> Scan aus den Punktpaaren: umgekehrt als Startlage der Scanpruefung."""
        import numpy as np
        d = self._scan
        start = np.linalg.inv(np.asarray(ausrichtung.matrix, float))
        self.pruefe_scan(d["pfad"], warten, d.get("bezug"), start)

    def _scan_kopf(self, d) -> str:
        a = d["ausrichtung"]
        art = tr("Bezugssystem {} (3-2-1, Gauß-Ausgleich je Bezug)").format("|".join(d["bezug"])) if d.get("bezug") \
            else tr({"gleich": "gleiche Lage", "bestpassung": "Bestpassung",
                     "punkte": "Punktpaare von Hand, dann Feinausrichtung"}.get(a.methode, a.methode))
        text = tr("Scan {}: Ausrichtung {} (mittlerer Abstand {:.4f} mm, {:.0%} der Punkte innerhalb 0,05 mm)").format(
            os.path.basename(d["pfad"]), art, a.mittel, a.anteil)
        if d.get("punktwolke"):
            text += " · " + tr("Punktwolke, {} Punkte").format(d.get("punkte", 0))
        return text

    def exportiere_scan_pdf(self, pfad: str = "", bilder: bool = True) -> str | None:
        from .berichte import scan_pdf
        if getattr(self, "_scan", None) is None:
            return None
        pfad = pfad or self._speicherpfad(tr("Prüfbericht"), os.path.splitext(self._scan["pfad"])[0] + "_pruefbericht.pdf",
                                          "PDF (*.pdf)")
        if not pfad:
            return None
        ziel = scan_pdf(self, pfad, bilder)
        self._berichte_gespeichert.add("scan")  # fuer den gefuehrten Ablauf
        self.statusBar().showMessage(tr("PDF gespeichert: {}").format(ziel), 6000)
        return ziel

    # --- Zusammenbau ---

    def zeige_zusammenbau(self):
        self.dock_zusammenbau.show()
        self.dock_zusammenbau.raise_()
        self._zusammenbau_zeigen()

    def _teil_namen(self) -> dict[int, str]:
        if self.erg is None:
            return {}
        blaetter = [k for k in self.erg.baum.blaetter() if not k.hilfsgeometrie]
        anzahl = {}
        for k in blaetter:
            anzahl[k.name] = anzahl.get(k.name, 0) + 1
        return {k.nummer: k.name if anzahl[k.name] == 1 else f"{k.name} ({k.nummer})" for k in blaetter}

    def _teil_ecken(self, nr: int):
        """Ecken des Huellquaders eines Teils in zusammengebauter Lage und dessen Mitte."""
        import itertools
        import numpy as np
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        k = next(k for k in self.erg.baum.blaetter() if k.nummer == nr)
        b = Bnd_Box()
        brepbndlib.Add(k.form, b)
        x0, y0, z0, x1, y1, z1 = b.Get()
        ecken = np.array(list(itertools.product((x0, x1), (y0, y1), (z0, z1))))
        m = self.baugruppe.lage(nr)
        ecken = ecken @ m[:3, :3].T + m[:3, 3]
        return ecken, ecken.mean(axis=0)

    def _zusammenbau_zeigen(self):
        streuung = {}
        for nr in self.baugruppe.teile():
            if not self.baugruppe.fest(nr):
                ecken, mitte = self._teil_ecken(nr)
                streuung[nr] = self.baugruppe.streuung(nr, ecken, mitte)
        namen = self._teil_namen()
        self._alpha_vorbelegen(namen)
        self.zusammenbau.zeige(self.baugruppe, namen, streuung)
        self.zusammenbau.zeige_masse(self.baugruppe, namen, self.messgroessen_ergebnisse())
        self.ansicht.setze_teil_lagen(self.baugruppe.lagen)
        if self.aktionen["toleranzzone"].isChecked() or self.aktionen["toleranzzonen_alle"].isChecked():
            self._zone_aktualisieren(self.pmi.gewaehlte())  # Zonen folgen den Teilen

    def messgroesse_zeigen(self):
        """Gewaehlte Messgroesse im 3D: ihre zwei Flaechen gewaehlt, Messlinie vom Bezug zum Messpunkt mit Name,
        Nennwert und Worst Case; ohne Wahl wieder aus."""
        import numpy as np
        from ..kern import baugruppe_mass as bm
        nr = self.zusammenbau.gewaehlte_messgroesse()
        m = next((x for x in self.baugruppe.masse if x.nummer == nr), None)
        if m is None or self.erg is None:
            if getattr(self, "_mass_linie", False):
                self.ansicht.zeige_hilfslinien([])
                self._mass_linie = False
            return None
        fa, fb = self.baugruppe.mass_formen[nr]
        self.ansicht.setze_auswahl([fa, fb], [m.teil_a, m.teil_b])
        p, q, n, _tp, _tq = bm.Analyse(self.baugruppe)._geometrie(m, fa, fb)
        fuss = p - n * float(n @ (p - q))
        e = self.zusammenbau._ergebnisse.get(nr)
        text = f"{m.nummer}: " + (f"{e.nenn:.4f} ({e.wc_min:.4f} … {e.wc_max:.4f})" if e else "")  # Name: Tabelle
        farbe = (0.85, 0.25, 0.0)
        linien = [(tuple(fuss), tuple(p), text, farbe, 3.0)]
        lang = float(np.linalg.norm(p - fuss))
        if lang > 1e-9:  # Pfeilspitze am Messpunkt
            richtung = (p - fuss) / lang
            quer = np.cross(richtung, [0.0, 0.0, 1.0])
            quer = quer if np.linalg.norm(quer) > 1e-6 else np.cross(richtung, [0.0, 1.0, 0.0])
            quer /= np.linalg.norm(quer)
            spitze = min(lang * 0.3, 2.0)
            for s in (1, -1):
                linien.append((tuple(p), tuple(p - richtung * spitze + quer * s * spitze * 0.5), "", farbe, 3.0))
        self.ansicht.zeige_hilfslinien(linien)
        self._mass_linie = True
        return linien

    def _alpha_vorbelegen(self, namen: dict[int, str]):
        """Ausdehnungskoeffizient je Teil aus den STEP-Werkstoffen (Bibliothek), vorhandene Eingaben bleiben."""
        from ..kern import werkstoffe
        z = self.zusammenbau
        z.teil_namen = dict(namen)
        aus_datei = werkstoffe.werkstoffe_aus_step(getattr(self.erg.modell, "datei", None)) if self.erg else {}
        for zusatz in getattr(self.erg, "zusaetze", []):  # Werkstoffe hinzugefuegter Dateien
            aus_datei = {**werkstoffe.werkstoffe_aus_step(getattr(zusatz.modell, "datei", None)), **aus_datei}
        for nr, name in namen.items():
            if nr not in z.alpha:
                w = aus_datei.get(name) or aus_datei.get(name.split(" (")[0])
                z.alpha[nr] = (werkstoffe.alpha_fuer(w) if w else None) or werkstoffe.BIBLIOTHEK["Stahl"]

    def messgroessen_ergebnisse(self) -> dict:
        """Nummer der Messgroesse -> Ergebnis (Worst Case, Monte Carlo, Beitragende) ueber alle Verbindungen; mit
        Waermeausdehnung zusaetzlich die Verschiebung beim Temperaturfall."""
        if not self.baugruppe.masse:
            return {}
        from ..kern.baugruppe_mass import Analyse
        a = Analyse(self.baugruppe, self.erg.pmi if self.erg is not None else [])
        out = {m.nummer: a.berechne(m, *self.baugruppe.mass_formen[m.nummer]) for m in self.baugruppe.masse}
        z = self.zusammenbau
        if z.waerme.isChecked():
            temp = {nr: z.temperatur.value() for nr in self.baugruppe.teile()}
            for m in self.baugruppe.masse:
                out[m.nummer].waerme = a.waermeverschiebung(m, *self.baugruppe.mass_formen[m.nummer], z.alpha, temp)
        return out

    def messgroesse_auswahl(self):
        """Spalt oder Buendigkeit zwischen den zwei gewaehlten Ebenen (erst gemessene, dann Bezugsflaeche)."""
        if self.erg is None or self.vergleich is not None:
            return None
        paare = [(f, t) for f, t in zip(self.ansicht.auswahl3d, self.ansicht.auswahl_teile)
                 if t is not None and self.erg.modell.flaechen_index(f) is not None]
        if len(paare) != 2:
            self.statusBar().showMessage(tr("Genau zwei Flächen (Ebenen oder Zylinder) an verschiedenen Teilen wählen"), 6000)
            return None
        (fa, ta), (fb, tb) = paare
        m = self.erg.modell
        punkt = None
        if self.zusammenbau.am_punkt.isChecked():
            punkt = self.ansicht.klickpunkte.get((ta, m.flaechen_index(fa)))
            if punkt is None:
                self.statusBar().showMessage(tr("Die gemessene Fläche zuerst an der gewünschten Stelle anklicken"), 6000)
                return None
        x = self.baugruppe.neue_messgroesse(ta, fa, m.flaechen_index(fa), tb, fb, m.flaechen_index(fb), punkt)
        if isinstance(x, str):
            self.statusBar().showMessage(x, 6000)
            return None
        self.zeige_zusammenbau()
        self.zusammenbau.reiter.setCurrentIndex(1)
        return x

    def messgroesse_als_kette3d(self, nummer: int):
        """Messgroesse des Zusammenbaus als 3D-Kette im Fenster 3D-Toleranzkette (im Modell gezeigt)."""
        from ..kern.baugruppe_mass import Analyse
        m = next((x for x in self.baugruppe.masse if x.nummer == nummer), None)
        if m is None:
            return None
        k = Analyse(self.baugruppe).als_kette3d(m, *self.baugruppe.mass_formen[nummer], self._teil_namen())
        f = self.zeige_kette3d()
        f.setze_kette(k)
        f.im_modell.setChecked(True)
        f._zeigen()
        return f

    def _messgroesse_entfernen(self, nummer: int):
        self.baugruppe.entferne_messgroesse(nummer)
        self._zusammenbau_zeigen()

    def _mass_freigabe(self, nummer: int, freigabe: dict):
        m = next((x for x in self.baugruppe.masse if x.nummer == nummer), None)
        if m is not None:
            m.freigabe = dict(freigabe)
            self._zusammenbau_zeigen()

    def _soll(self, nummer: int, text: str):
        from ..kern.baugruppe_mass import lies_soll
        m = next((x for x in self.baugruppe.masse if x.nummer == nummer), None)
        if m is None:
            return
        try:
            m.soll_min, m.soll_max = lies_soll(text)
        except ValueError:
            self.statusBar().showMessage(tr("Soll z. B. als 3,8 … 4,2, ≥ 1 oder ≤ 2 eingeben"), 6000)
        self._zusammenbau_zeigen()

    def exportiere_messgroessen_pdf(self, pfad: str = "") -> str | None:
        from .berichte import messgroessen_pdf
        if self.erg is None or not self.baugruppe.masse:
            return None
        pfad = pfad or self._speicherpfad(tr("PDF-Bericht"), os.path.splitext(self.erg.pfad)[0] + "_messgroessen.pdf",
                                          "PDF (*.pdf)")
        if not pfad:
            return None
        ziel = messgroessen_pdf(self, pfad)
        self._berichte_gespeichert.add("messgroessen")  # fuer den gefuehrten Ablauf
        self.statusBar().showMessage(tr("PDF gespeichert: {}").format(ziel), 6000)
        return ziel

    def _spielraum(self, nummer: int, wert: float):
        self.baugruppe.setze_toleranz(nummer, wert, None, tr("manuell"))
        self._zusammenbau_zeigen()

    def verbinde_auswahl(self, versatz: float = 0.0):
        """Erste gewaehlte Flaeche (bewegtes Teil) an die zweite fangen."""
        if self.erg is None or self.vergleich is not None:
            return None
        paare = [(f, t) for f, t in zip(self.ansicht.auswahl3d, self.ansicht.auswahl_teile)
                 if t is not None and self.erg.modell.flaechen_index(f) is not None]
        if len(paare) != 2:
            self.statusBar().showMessage(tr("Genau zwei Flächen wählen: erst am bewegten Teil, dann die Gegenfläche"),
                                         6000)
            return None
        (fa, ta), (fb, tb) = paare
        m = self.erg.modell
        v = self.baugruppe.verbinde(ta, fa, m.flaechen_index(fa), tb, fb, m.flaechen_index(fb), versatz)
        if isinstance(v, str):
            self.statusBar().showMessage(v, 6000)
            return None
        from ..kern import toleranzzone
        from ..kern.verbindung import toleranz_aus_pmi
        allgemein = self._allgemein or toleranzzone.allgemein_aus_hinweisen(self.erg.pmi)
        toleranz_aus_pmi(self.baugruppe, v, m, self.erg.pmi, allgemein.laenge if allgemein else "")
        self._zusammenbau_zeigen()
        verletzt = self.baugruppe.verletzt()
        text = tr("Verbindung {} angelegt").format(v.nummer)
        if verletzt:
            text += " · " + tr("nicht mehr erfüllt: {}").format(", ".join(str(x.nummer) for x in verletzt))
        self.statusBar().showMessage(text, 8000)
        return v

    def verbinde_321(self, versatz: float = 0.0):
        """3-2-1-Vorlage: sechs gewaehlte Ebenen paarweise (Teil, Gegenstueck), primaer bis tertiaer."""
        if self.erg is None or self.vergleich is not None:
            return None
        m = self.erg.modell
        paare = [(f, t) for f, t in zip(self.ansicht.auswahl3d, self.ansicht.auswahl_teile)
                 if t is not None and m.flaechen_index(f) is not None]
        if len(paare) != 6 or len({t for f, t in paare[0::2]}) != 1:
            self.statusBar().showMessage(tr("3-2-1: sechs Ebenen paarweise wählen – je eine am bewegten Teil, dann die "
                                            "Gegenfläche (primär, sekundär, tertiär)"), 8000)
            return None
        teil = paare[0][1]
        out = self.baugruppe.verbinde_321(teil, [(f, m.flaechen_index(f)) for f, _ in paare[0::2]],
                                          [(t, f, m.flaechen_index(f)) for f, t in paare[1::2]], versatz)
        if isinstance(out, str):
            self.statusBar().showMessage(out, 6000)
            return None
        from ..kern import toleranzzone
        from ..kern.verbindung import toleranz_aus_pmi
        allgemein = self._allgemein or toleranzzone.allgemein_aus_hinweisen(self.erg.pmi)
        for v in out:
            toleranz_aus_pmi(self.baugruppe, v, m, self.erg.pmi, allgemein.laenge if allgemein else "")
        self._zusammenbau_zeigen()
        self.statusBar().showMessage(tr("3-2-1: Verbindungen {} angelegt").format(", ".join(str(v.nummer) for v in out)),
                                     8000)
        return out

    def _frei_anzeigen(self):
        """Gewaehltes Teil: Felder je offenem Freiheitsgrad; die Lage beim Waehlen ist der Ausgangspunkt."""
        import numpy as np
        from ..kern import verbindung as vb
        teil = self.zusammenbau.gewaehltes_teil()
        if teil is None or self.baugruppe.fest(teil):
            self._frei = None
            self.zusammenbau.zeige_freiheitsgrade([], [])
            self._manipulator_zeigen()
            return
        basis = self.baugruppe.freiheitsgrade(teil)
        self._frei = (teil, basis, np.array(self.baugruppe.lage(teil)))
        self.zusammenbau.zeige_freiheitsgrade(vb.beschreibe(basis),
                                              [vb._gerade_ausrichten(z[:3], z[3:])[0] == "drehung" for z in basis])
        self._manipulator_zeigen()

    def _manipulator_zeigen(self):
        """3D-Griff am gewaehlten Teil des Zusammenbaus (nur offene Freiheitsgrade), sonst aus."""
        from ..kern import verbindung as vb
        frei = getattr(self, "_frei", None)
        an = frei is not None and len(frei[1]) and self.dock_zusammenbau.isVisible()
        rahmen = vb.manipulator_rahmen(frei[1], self._teil_ecken(frei[0])[1]) if an else None
        if rahmen is not None:
            rahmen["teil"] = frei[0]
        self._manip_rahmen = rahmen
        self.ansicht.zeige_manipulator(rahmen)

    def _manipulator_bewegt(self, m):
        """Ziehen am 3D-Griff: Bewegung auf die offenen Freiheitsgrade zurueckgerechnet, ab der Lage beim Waehlen;
        dabei rastet das Teil an passenden Gegenstuecken ein (kern.einrasten)."""
        from ..kern import verbindung as vb
        frei, rahmen = getattr(self, "_frei", None), getattr(self, "_manip_rahmen", None)
        if frei is None or rahmen is None:
            return
        teil, basis, start = frei
        if getattr(self, "_ziehen", None) is None:
            self._ziehen = self._neues_ziehen(teil, ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
        self.baugruppe.bewege_frei(teil, vb.werte_aus_bewegung(m, basis, rahmen["punkt"]), start, basis)
        if self._ziehen is not None:
            self.baugruppe.lagen[teil] = self._ziehen.einrasten(self.baugruppe.lage(teil))
            self._einrasten_zeigen()
        self.ansicht.setze_teil_lagen(self.baugruppe.lagen)

    def _manipulator_fertig(self):
        """Nach dem Ziehen: eingerastet -> Verbindung; neue Ausgangslage, Griff an die neue Stelle."""
        import numpy as np
        if getattr(self, "_ziehen", None) is not None:
            self._ziehen.lage = self.baugruppe.lage(self._ziehen.teil)
            self.teil_ziehen_ende()
        frei = getattr(self, "_frei", None)
        if frei is not None:
            self._frei = (frei[0], frei[1], np.array(self.baugruppe.lage(frei[0])))
        self._manipulator_zeigen()

    # --- Teil ziehen mit Einrasten (kern.einrasten) ---

    def _fangweite(self) -> float:
        """Fangweite in mm: 15 Bildpunkte, ohne echte Ansicht 2 % der Modellgroesse."""
        px = self.ansicht.mm_je_pixel()
        if px > 0:
            return 15.0 * px
        from ..kern.einrasten import _box
        import numpy as np
        box = _box(self.erg.modell.form)
        return 0.02 * float(np.linalg.norm(box[1] - box[0])) if box is not None else 1.0

    def _neues_ziehen(self, teil: int, strahl):
        from ..kern.einrasten import Ziehen
        knoten = {k.nummer: k for k in self.erg.baum.blaetter() if not k.hilfsgeometrie}
        if teil not in knoten:
            return None
        andere = [(n, k.form) for n, k in knoten.items() if n != teil and n not in self.ansicht.versteckt]
        return Ziehen(self.baugruppe, teil, knoten[teil].form, self.erg.modell, andere, strahl, self._fangweite())

    def teil_ziehen_start(self, teil: int, strahl):
        """Teil im 3D gepackt: nur in seinen offenen Freiheitsgraden ziehen, dabei einrasten."""
        self._ziehen = None
        if self.erg is None or self.vergleich is not None:
            return
        self.zusammenbau.wiggle_an.setChecked(False)
        z = self._neues_ziehen(teil, strahl)
        if z is None or not z.frei():
            self.statusBar().showMessage(tr("Das Teil ist durch seine Verbindungen bestimmt – nichts mehr frei"), 6000)
            return
        if len(z.schiebe) == 0 and z.dreh is not None:
            self.statusBar().showMessage(tr("Nur die Drehung um die Achse ist frei: Ziehen dreht das Teil"), 6000)
        self._ziehen = z

    def teil_gezogen(self, strahl):
        z = getattr(self, "_ziehen", None)
        if z is None:
            return
        z.bewege(strahl)
        lagen = dict(self.baugruppe.lagen)
        lagen[z.teil] = z.lage
        self.ansicht.setze_teil_lagen(lagen)
        self._einrasten_zeigen()

    def _einrasten_zeigen(self):
        """Gefangenes Flaechenpaar hervorheben und benennen, sonst Hervorhebung aus."""
        from ..kern import verbindung as vb
        z = self._ziehen
        k = z.kandidat
        if k is None:
            if self.ansicht.auswahl3d:
                self.ansicht.setze_auswahl([])
            self.statusBar().showMessage(tr("Ziehen – in die Nähe einer passenden Fläche bringen, dann rastet es ein"))
            return
        self.ansicht.setze_auswahl([k.element.form, k.gegen.form], [z.teil, k.gegen.teil])
        self.statusBar().showMessage(tr("Rastet ein: {} an {} – loslassen verbindet").format(
            tr(vb.ART_TEXT[k.art]), self._teil_namen().get(k.gegen.teil, str(k.gegen.teil))))

    def teil_ziehen_ende(self):
        """Losgelassen: Lage uebernehmen, eingerastet -> Verbindung (Spielraum aus Geometrie und PMI)."""
        z, self._ziehen = getattr(self, "_ziehen", None), None
        if z is None:
            return None
        v = z.loslassen()
        if isinstance(v, str):
            self.statusBar().showMessage(v, 6000)
            v = None
        elif v is not None:
            from ..kern import toleranzzone
            from ..kern.verbindung import toleranz_aus_pmi
            allgemein = self._allgemein or toleranzzone.allgemein_aus_hinweisen(self.erg.pmi)
            toleranz_aus_pmi(self.baugruppe, v, self.erg.modell, self.erg.pmi, allgemein.laenge if allgemein else "")
            self.statusBar().showMessage(tr("Verbindung {} angelegt").format(v.nummer), 8000)
        else:
            self.statusBar().clearMessage()
        self._zusammenbau_zeigen()
        if self.zusammenbau.gewaehltes_teil() is not None:
            self._frei_anzeigen()  # neue Ausgangslage und Freiheitsgrade fuer Felder und 3D-Griff
        return v

    def _frei_bewegen(self, werte: list):
        frei = getattr(self, "_frei", None)
        if frei is None:
            return
        teil, basis, start = frei
        self.baugruppe.bewege_frei(teil, werte, start, basis)
        self.ansicht.setze_teil_lagen(self.baugruppe.lagen)

    def _verbindung_aendern(self, aktion, nummer: int):
        """Umkehren oder Tauschen; danach melden, welche Verbindungen nicht mehr erfuellt sind."""
        fehler = aktion(nummer)
        self._zusammenbau_zeigen()
        verletzt = self.baugruppe.verletzt()
        text = fehler or (tr("nicht mehr erfüllt: {}").format(", ".join(str(x.nummer) for x in verletzt))
                          if verletzt else tr("Verbindung {} geändert").format(nummer))
        self.statusBar().showMessage(text, 8000)

    def _verbindung_entfernen(self, nummer: int):
        self.baugruppe.entferne(nummer)
        self._zusammenbau_zeigen()

    def zusammenbau_zuruecksetzen(self):
        self._wiggle(None)
        self.baugruppe.zuruecksetzen()
        self._zusammenbau_zeigen()

    def _wiggle(self, teil):
        """Teil in seinen offenen Freiheitsgraden nacheinander hin und her bewegen (teil None: aus)."""
        uhr = getattr(self, "_wiggle_uhr", None)
        if uhr is None:
            uhr = self._wiggle_uhr = QtCore.QTimer(self)
            uhr.setInterval(30)
            uhr.timeout.connect(self._wiggle_schritt)
        toleranz = self.zusammenbau.wiggle_art.currentData() == "toleranz"
        basis = []
        mitte = None
        if teil is not None and not self.baugruppe.fest(teil):
            if toleranz:
                mitte = self._teil_ecken(teil)[1]
                basis = self.baugruppe.grenzlagen(teil, mitte)
            else:
                basis = self.baugruppe.freiheitsgrade(teil)
        if teil is None or not len(basis):
            uhr.stop()
            self._wiggle_zustand = None
            self.ansicht.setze_teil_lagen(self.baugruppe.lagen)
            if teil is not None:
                self.statusBar().showMessage(tr("Kein Spielraum – Toleranzen der Verbindungen setzen") if toleranz
                                             else tr("Das Teil ist bestimmt – nichts zu bewegen"), 5000)
            return
        self._wiggle_zustand = [teil, basis, 0, mitte]
        uhr.start()

    def _wiggle_schritt(self):
        import math
        from ..kern import verbindung as vb
        z = getattr(self, "_wiggle_zustand", None)
        if z is None:
            return
        teil, basis, schritt, mitte = z
        z[2] += 1
        je = 60  # Schritte je Freiheitsgrad bzw. Grenzlage (eine Schwingung)
        i = (schritt // je) % len(basis)
        s = math.sin(2 * math.pi * (schritt % je) / je)
        if mitte is not None:  # innerhalb der Toleranzen: Grenzlage, ueberhoeht
            bewegung = vb.bewegung_klein(basis[i], s * self.zusammenbau.faktor.value(), mitte)
        else:
            dreht = float(sum(x * x for x in basis[i][:3])) > 1e-18
            bewegung = vb.bewegung(basis[i], s * (self.zusammenbau.winkel.value() if dreht
                                                  else self.zusammenbau.weg_mm.value()))
        lagen = dict(self.baugruppe.lagen)
        lagen[teil] = bewegung @ self.baugruppe.lage(teil)
        self.ansicht.setze_teil_lagen(lagen)

    def zeige_kollision_leiste(self):
        self.dock_kollision.show()
        self.dock_kollision.raise_()

    def starte_kollision(self, werte: dict, warten: bool = False):
        """Kollisionen und Abstaende im Hintergrund pruefen (Umfang aus der Strukturauswahl)."""
        from ..kern import kollision as ko
        from .kollision_ui import KollisionLader
        if self.erg is None:
            return
        if self.vergleich is not None:
            self.statusBar().showMessage(tr("Im Vergleich nicht möglich – erst Vergleich beenden"), 6000)
            return
        from OCC.Core.TopLoc import TopLoc_Location
        from .ansicht3d import gp_trsf
        lagen = self.baugruppe.lagen  # Teile wie zusammengebaut
        alle = [ko.Teil(k.nummer, k.name, k.form.Moved(TopLoc_Location(gp_trsf(lagen[k.nummer])))
                        if k.nummer in lagen else k.form)
                for k in self.erg.baum.blaetter() if not k.hilfsgeometrie and k.nummer not in self.ansicht.versteckt]
        gewaehlt = self.baum.gewaehlte_blaetter()
        teile, gruppe_b = alle, None
        if werte["umfang"] == "gegen":
            teile = [t for t in alle if t.nummer in gewaehlt]
            gruppe_b = [t for t in alle if t.nummer not in gewaehlt]
        elif werte["umfang"] == "auswahl":
            teile = [t for t in alle if t.nummer in gewaehlt]
        if not teile or (gruppe_b is not None and not gruppe_b) or (gruppe_b is None and len(teile) < 2):
            self.statusBar().showMessage(tr("Zu wenige Teile – Teile in der Struktur wählen"), 6000)
            return
        e = ko.Einstellung(werte["kontakt"], werte["mindest"], werte["hoechst"], werte["kontakte"])
        self.kollision_aus()
        gepaart = {frozenset((v.teil, v.gegen_teil)) for v in self.baugruppe.verbindungen}
        bereiche = self._bewegungsbereiche(teile + (gruppe_b or []), werte) if werte.get("bereich") else None
        lader = KollisionLader(teile, gruppe_b, e, self, self._grenzlagen() if werte.get("grenzlagen") else None,
                               gepaart, bereiche)
        lader.stand.connect(self._prozent)
        lader.fehler.connect(lambda t: (self.kollision.start.setEnabled(True),
                                        QtWidgets.QMessageBox.warning(self, tr("Kollisionen"), t)))
        lader.fertig.connect(lambda b, l=lader: l.abgebrochen or self._kollision_fertig(b, l.freie_bereiche))
        self._kollision_lader = lader
        self.kollision.start.setEnabled(False)
        self._aufgabe(lader, tr("Kollisionen prüfen …"))
        lader.start()
        if warten:
            lader.wait()
            QtWidgets.QApplication.processEvents()

    def _grenzlagen(self) -> dict:
        """Grenzlagen der Toleranzen je bewegtem Teil des Zusammenbaus als 4x4-Bewegungen in Weltlage."""
        from ..kern import verbindung as vb
        out = {}
        for nr in self.baugruppe.teile():
            if self.baugruppe.fest(nr):
                continue
            _ecken, mitte = self._teil_ecken(nr)
            out[nr] = [vb.bewegung_klein(x, 1.0, mitte) for x in self.baugruppe.grenzlagen(nr, mitte)]
        return {n: m for n, m in out.items() if m}

    def _bewegungsbereiche(self, teile: list, werte: dict) -> list:
        """Je bewegtem Teil im Pruefumfang und offenem Freiheitsgrad: (Teil, andere, Bewegung, bis, Text, Einheit)."""
        from ..kern import verbindung as vb
        out = []
        for t in teile:
            if t.nummer not in self.baugruppe.teile() or self.baugruppe.fest(t.nummer):
                continue
            basis = self.baugruppe.freiheitsgrade(t.nummer)
            for z, text in zip(basis, vb.beschreibe(basis)):
                dreht = vb._gerade_ausrichten(z[:3], z[3:])[0] == "drehung"
                out.append((t, [x for x in teile if x.nummer != t.nummer], lambda w, z=z: vb.bewegung(z, w),
                            werte["bereich_grad"] if dreht else werte["bereich_mm"], text, "°" if dreht else "mm"))
        return out

    def _kollision_fertig(self, befunde, freie_bereiche=()):
        from ..kern import kollision as ko
        self.kollision.start.setEnabled(True)
        gemerkt, self._kollision_gemerkt = getattr(self, "_kollision_gemerkt", None), None
        if gemerkt:
            ko.uebernimm(befunde, gemerkt)
        z = {k: 0 for k in ko.ART_TEXT}
        for b in befunde:
            z[b.art] += 1
        text = tr("{} Kollisionen, {} zu nah, {} Kontakte, {} zu weit").format(
            z[ko.KOLLISION], z[ko.ZU_NAH], z[ko.KONTAKT], z[ko.ZU_WEIT])
        kopf = text if befunde else tr("Keine Befunde")
        if freie_bereiche:
            kopf += "\n" + tr("Freier Bewegungsbereich:") + "".join(
                f"\n· {name}, {art}: {unten:+.4g} … {oben:+.4g} {einheit}"
                for name, art, unten, oben, einheit in freie_bereiche)
        self.freie_bereiche = list(freie_bereiche)
        self.kollision.zeige(befunde, kopf)
        self.zeige_kollision_leiste()
        self._danach()
        self.statusBar().showMessage(tr("Kollisionsprüfung: {}").format(text), 10000)

    def _kollision_gewaehlt(self, befund):
        if befund is None:
            self.ansicht.zeige_kollision(None)
            return
        form = befund.durchdringung
        if form is not None and befund.kurven is not None:  # Schnittkurven mit der Durchdringung zeigen
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.TopoDS import TopoDS_Compound
            bb, form = BRep_Builder(), TopoDS_Compound()
            bb.MakeCompound(form)
            bb.Add(form, befund.durchdringung)
            bb.Add(form, befund.kurven)
        self.ansicht.zeige_kollision({befund.a.nummer, befund.b.nummer}, form, befund.punkte)

    def exportiere_kollision_pdf(self, pfad: str = "") -> str | None:
        from .berichte import kollision_pdf
        if self.erg is None or not self.kollision.befunde:
            return None
        pfad = pfad or self._speicherpfad(tr("PDF-Bericht"), os.path.splitext(self.erg.pfad)[0] + "_kollisionen.pdf",
                                          "PDF (*.pdf)")
        if not pfad:
            return None
        ziel = kollision_pdf(self, pfad)
        self.statusBar().showMessage(tr("PDF gespeichert: {}").format(ziel), 6000)
        return ziel

    def kollision_aus(self):
        self.ansicht.zeige_kollision(None)
        self.kollision.zeige([], "")

    def scan_aus(self, aus: bool = True):
        """Scan aus- oder wieder einblenden (Knopf der Scan-Leiste): Modus Soll bzw. Vergleich; Reiter und
        Ergebnisse bleiben (der Reiter schliesst nur ueber sein ×)."""
        if getattr(self, "_scan", None) is None:
            return
        self.setze_scanmodus("soll" if aus else "vergleich")

    def setze_scanmodus(self, modus: str):
        """Scanpruefung wie ein Vergleich: Vergleich (Scan mit Farbkarte, CAD durchscheinend), Soll (nur CAD), Ist (nur
        Scan) oder Blinken (wechselt Soll/Ist)."""
        if getattr(self, "_scan", None) is None:
            return
        self._scanmodus = modus
        self.scan_leiste.setze(modus)
        self.scan.aus.blockSignals(True)  # Knopf "Scan ausblenden" folgt dem Modus
        self.scan.aus.setChecked(modus == "soll")
        self.scan.aus.setText(tr("Scan einblenden") if modus == "soll" else tr("Scan ausblenden"))
        self.scan.aus.blockSignals(False)
        if modus == "blinken" and not self.scan_leiste.pause_knopf.isChecked():
            self._scan_blink.start()
        else:
            self._scan_blink.stop()
        if modus == "nebeneinander":  # links Soll (CAD), rechts Ist (Scan), Kameras gekoppelt
            self._soll_ansicht().show()
            self._kamera_zuletzt = (None, None)
            self._kopplung.start()
        elif self.vergleich is None and self.ansicht_alt is not None:
            self.ansicht_alt.hide()
            self._kopplung.stop()
        self._scan_zeigen({"blinken": "soll", "nebeneinander": "ist"}.get(modus, modus))
        self.scan_leiste.zeige_stand(True if modus == "blinken" else None)

    def _scan_zeigen(self, art: str):
        karte = getattr(self, "_scan_karte", None)
        if art == "soll" or karte is None:
            self.ansicht.zeige_abweichung(None)
        else:
            self.ansicht.zeige_abweichung(karte[0], 0.02, karte[1], ueberlagert=art == "vergleich")
        self._scan_zeigt = art

    def _scan_blinken(self):
        soll = getattr(self, "_scan_zeigt", "soll") != "soll"
        self._scan_zeigen("soll" if soll else "ist")
        self.scan_leiste.zeige_stand(soll)

    def scan_verwerfen(self):
        """Scan ganz entfernen (Ergebnisse, Anzeige) und den Reiter schliessen."""
        if getattr(self, "_scan", None) is None:
            return
        self._scan = None
        self._scan_karte = None
        self._scan_blink.stop()
        if self.vergleich is None and self.ansicht_alt is not None:
            self.ansicht_alt.hide()
            self._kopplung.stop()
        self.scan_leiste.hide()
        self.ansicht.zeige_abweichung(None)
        self.scan.zeige([], "")
        self.dock_scan.hide()

    def _fokus_umschalten(self):
        self.ansicht.setze_fokus(self.aktionen["fokus"].isChecked(), self.baum.gewaehlte_blaetter())

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
        for f in _alle_fenster():  # das Thema gilt fuer die ganze App, also fuer alle Fenster
            f.thema = self.thema
            if "thema_" + name in f.aktionen:
                f.aktionen["thema_" + name].setChecked(True)
            for a in (f.ansicht, f.ansicht_alt):
                if a is not None:
                    a.setze_thema(self.thema)

    def setze_skalierung(self, v: float):
        if abs(v - skalierung(self.ein)) < 0.01:
            return
        self.ein.setValue("ui_skalierung", v)
        QtWidgets.QMessageBox.information(self, tr("Größe der Oberfläche"),
                                          tr("Die Oberfläche wird nach einem Neustart auf {:.0f} % gestellt.").format(
                                              v * 100))

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
        self.ein.setValue("pmi_kontrast", w.get("pmi_kontrast", True))
        self.ein.setValue("draht_kontrast", w.get("draht_kontrast", True))
        for k in ("pmi_eigen", "pmi_eigene_farbe", "hg_eigen", "hg_oben", "hg_unten"):
            if k in w:
                self.ein.setValue(k, w[k])
        if w["thema"] != self.ein.value("thema", "auto"):
            self.setze_thema(w["thema"])
        for f in _alle_fenster():  # alle Ansichten aller Fenster, nicht nur die Hauptansicht dieses Fensters
            f._ansichten_einstellen()
        if w["sprache"] != self.ein.value("sprache", "auto"):
            self.ein.setValue("sprache", w["sprache"])
            self.aktionen["sprache_" + w["sprache"]].setChecked(True)
            QtWidgets.QMessageBox.information(self, tr("Sprache"),
                                              tr("Die Sprache wird beim nächsten Start übernommen."))

    def _ansichten_einstellen(self):
        """Navigation, Kontrast, Farben und Thema aus den Einstellungen in alle Ansichten dieses Fensters."""
        e = self.ein
        for a in (self.ansicht, self.ansicht_alt):
            if a is None:
                continue
            a.setze_navigation(e.value("navigation", "catia"))
            a.setze_pmi_kontrast(e.value("pmi_kontrast", True, type=bool))
            a.setze_draht_kontrast(e.value("draht_kontrast", True, type=bool))
        name = e.value("thema", "auto")
        if "thema_" + name in self.aktionen:
            self.aktionen["thema_" + name].setChecked(True)
        self.thema = thema.wende_an(QtWidgets.QApplication.instance(), name)
        for a in (self.ansicht, self.ansicht_alt):
            if a is not None:
                a.setze_thema(self.thema)
        self._farben_anwenden()

    def _farben_anwenden(self):
        from .einstellungen import rgb
        e = self.ein
        pmi = rgb(e.value("pmi_eigene_farbe", "#d4145a")) if e.value("pmi_eigen", False, type=bool) else None
        hg = (rgb(e.value("hg_oben", "#dfe5ee")), rgb(e.value("hg_unten", "#a9b3c2"))) \
            if e.value("hg_eigen", False, type=bool) else None
        for a in (self.ansicht, getattr(self, "ansicht_alt", None)):
            if a is not None:
                a.setze_farben(pmi, hg)

    def zeige_anleitung(self):
        from .hilfe import zeige_anleitung
        zeige_anleitung(self)

    def zeige_ueber(self):
        from .hilfe import zeige_ueber
        zeige_ueber(self)

    def neues_fenster(self, pfad: str | None = None):
        """Weiteres Hauptfenster; pfad "" fragt nach einer Datei, None oeffnet leer."""
        if pfad == "":
            start = os.path.dirname(self.zuletzt()[0]) if self.zuletzt() else ""
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("In neuem Fenster öffnen"), start,
                                                            DATEIFILTER.format(tr("Alle Modelle"), tr("Netze")))
            if not pfad:
                return None
        f = Hauptfenster()
        f.move(self.pos() + QtCore.QPoint(40, 40))
        f.show()
        if pfad:
            f.lade(pfad)
        return f

    def _fenster_koppeln(self):
        """Kameras aller Fenster koppeln (an/aus fuer alle)."""
        an = self.aktionen["kameras_koppeln"].isChecked()
        for f in FENSTER:
            a = f.aktionen.get("kameras_koppeln")
            if a is not None and a.isChecked() != an:
                a.blockSignals(True)
                a.setChecked(an)
                a.blockSignals(False)
        uhr = _fenster_uhr()
        if an:
            uhr.start()
        else:
            uhr.stop()

    def closeEvent(self, ev):
        if self in FENSTER:
            FENSTER.remove(self)
        self._fenster_merken()
        if getattr(self, "_vorschau", None) is not None and self._vorschau.isRunning():
            self._vorschau.abbrechen = True
            self._vorschau.wait(5000)
        self.lade_abbrechen()
        if self._vlader is not None and self._vlader.isRunning():
            self._vlader.abgebrochen = True
            self._vlader.wait(30000)
        super().closeEvent(ev)
