"""Hauptfenster: Menues, Werkzeugleiste, Seitenleisten, 3D-Ansicht, Laden."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets

from .. import i18n
from ..i18n import tr
from ..version import VERSION
from . import ansicht3d, thema
from .lader import Lader
from .panels import AnsichtenPanel, BaumPanel, PmiPanel

DATEIFILTER = "STEP (*.stp *.step *.STP *.STEP)"
ENDUNGEN = (".stp", ".step")
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

        self._baue_aktionen()
        self._baue_menues()
        self._baue_leiste()
        self._verbinde()
        self._modell_da(False)
        self.start.zeige_zuletzt(self.zuletzt())

    @staticmethod
    def _titel(datei: str = "") -> str:
        return f"3DGmax {VERSION}" + (f" – {datei}" if datei else "")

    # --- Aufbau ---

    def _dock(self, titel, widget, bereich):
        d = QtWidgets.QDockWidget(titel, self)
        d.setObjectName(titel)
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
        self.aktionen[name] = a
        return a

    def _baue_aktionen(self):
        A = self._aktion
        A("oeffnen", tr("Öffnen …"), lambda: self.oeffnen(""), QtGui.QKeySequence.StandardKey.Open,
          tipp=tr("STEP-Datei öffnen"), modell=False)
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
        A("drehpunkt", tr("Drehpunkt zurücksetzen"), self.ansicht.drehpunkt_zuruecksetzen,
          tipp=tr("Drehen wieder um die Mitte (Doppelklick setzt einen Drehpunkt)"))
        gruppe = QtGui.QActionGroup(self)
        for n, text, k in (("kanten", tr("Schattiert mit Kanten"), "E"), ("schattiert", tr("Schattiert"), "S"),
                           ("draht", tr("Drahtmodell"), "W")):
            a = A("darstellung_" + n, text, lambda _=False, n=n: self.ansicht.darstellung(n), k, pruefbar=True)
            gruppe.addAction(a)
        self.aktionen["darstellung_kanten"].setChecked(True)
        A("grafik", tr("Grafische PMI zeigen"), self._grafik_umschalten, "G", pruefbar=True,
          tipp=tr("PMI-Beschriftungen im 3D-Modell ein/aus"))
        self.aktionen["grafik"].setChecked(True)
        A("hilfsgeometrie", tr("Hilfsgeometrie zeigen"), self._hilfe_umschalten, pruefbar=True,
          tipp=tr("Punkte und Linien ohne Flächen (z. B. Konstruktionsgeometrie)"))
        sg = QtGui.QActionGroup(self)
        for n, text in ((None, tr("Kein Schnitt")), ("x", tr("Schnitt X")), ("y", tr("Schnitt Y")),
                        ("z", tr("Schnitt Z"))):
            a = A("schnitt_" + (n or "aus"), text, lambda _=False, n=n: self._schnitt(n), pruefbar=True,
                  tipp=tr("Schnittebene senkrecht zur Achse") if n else tr("Schnitt aufheben"))
            sg.addAction(a)
        self.aktionen["schnitt_aus"].setChecked(True)
        A("schnitt_umkehren", tr("Schnittseite umkehren"), self._schnitt_umkehren, pruefbar=True)
        A("alle_zeigen", tr("Alle Teile zeigen"), self.baum.alle_zeigen, tipp=tr("Ausgeblendete Teile wieder zeigen"))
        A("isolieren", tr("Gewählte Teile isolieren"), self._isolieren, "I")
        A("transparent", tr("Gewählte Teile transparent"), self._transparent, "T")
        A("pmi_suche", tr("PMI suchen"), self._suche_fokus, QtGui.QKeySequence.StandardKey.Find)
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

    def _baue_menues(self):
        mb = self.menuBar()
        a = self.aktionen
        m = mb.addMenu(tr("&Datei"))
        m.addAction(a["oeffnen"])
        self.menue_zuletzt = m.addMenu(tr("Zuletzt verwendet"))
        m.addSeparator()
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
        m.addAction(a["drehpunkt"])
        m.addSeparator()
        for n in ansicht3d.DARSTELLUNGEN:
            m.addAction(a["darstellung_" + n])
        m.addSeparator()
        m.addAction(a["grafik"])
        m.addAction(a["hilfsgeometrie"])
        m.addSeparator()
        ms = m.addMenu(tr("Schnitt"))
        for n in ("schnitt_aus", "schnitt_x", "schnitt_y", "schnitt_z"):
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
        for n in ("alle_zeigen", "isolieren", "transparent"):
            m.addAction(a[n])
        m.addSeparator()
        m.addAction(a["pmi_suche"])
        self.menue_fenster = mb.addMenu(tr("&Fenster"))
        for d in (self.dock_baum, self.dock_ansichten, self.dock_pmi):
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
        tb.addSeparator()
        for n in ("vorne", "oben", "rechts", "iso"):
            tb.addAction(a["ansicht_" + n])
        tb.addAction(a["alles"])
        tb.addSeparator()
        for n in ansicht3d.DARSTELLUNGEN:
            tb.addAction(a["darstellung_" + n])
        tb.addSeparator()
        tb.addAction(a["grafik"])
        tb.addSeparator()
        knopf = QtWidgets.QToolButton()
        knopf.setText(tr("Schnitt"))
        knopf.setToolTip(tr("Schnittebene wählen"))
        knopf.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menue = QtWidgets.QMenu(knopf)
        for n in ("schnitt_aus", "schnitt_x", "schnitt_y", "schnitt_z", "schnitt_umkehren"):
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
        tb.addWidget(self.schnitt_regler)
        self._schnitt_achse = None

    def _verbinde(self):
        self.start.oeffnen.connect(self.oeffnen)
        self.pmi.gewaehlt.connect(self._pmi_gewaehlt)
        self.ansichten.gewaehlt.connect(self._ansicht_gewaehlt)
        self.ansicht.flaeche_gewaehlt.connect(self._flaeche_gewaehlt)
        self.ansicht.pmi_gewaehlt.connect(self._grafik_pmi_gewaehlt)
        self.ansicht.meldung.connect(lambda t: self.statusBar().showMessage(t, 5000))
        self.baum.sichtbar_geaendert.connect(self.ansicht.knoten_sichtbar)
        self.baum.isolieren.connect(self.ansicht.isoliere)
        self.baum.transparent.connect(self.ansicht.knoten_transparent)

    def _modell_da(self, da: bool):
        for a in self.aktionen.values():
            if a.property("braucht_modell"):
                a.setEnabled(da)
        self.schnitt_knopf.setEnabled(da)
        self.schnitt_regler.setEnabled(da and self._schnitt_achse is not None)
        self.aktionen["schnitt_umkehren"].setEnabled(da and self._schnitt_achse is not None)
        self.stapel.setCurrentWidget(self.ansicht if da else self.start)
        for d in (self.dock_baum, self.dock_ansichten, self.dock_pmi):
            d.setVisible(da)

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
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(self, tr("STEP-Datei öffnen"), start, DATEIFILTER)
            if not pfad:
                return
        self.lade(pfad)

    def lade(self, pfad: str, warten: bool = False):
        """Laedt im Hintergrund; warten=True blockiert bis fertig (Tests, Selbsttest)."""
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

    def zeige_ergebnis(self, erg):
        self.erg = erg
        self.setWindowTitle(self._titel(os.path.basename(erg.pfad)))
        szene = ansicht3d.Szene(erg.modell, erg.baum, erg.farben, erg.grafik, erg.pmi)
        self._modell_da(True)
        self.ansicht.zeige(szene)
        self.baum.zeige(erg.baum)
        self.pmi.zeige(erg.pmi)
        self.ansichten.zeige(erg.ansichten)
        self._merke_zuletzt(erg.pfad)
        n = len(erg.pmi)
        self.statusBar().showMessage(tr("{} geladen: {} Flächen, {} PMI, {} Ansichten ({:.1f} s)").format(
            os.path.basename(erg.pfad), len(erg.modell.flaechen), n, len(erg.ansichten), erg.modell.ladezeit), 8000)

    def _ladefehler(self, text):
        self._lader = None
        self.fortschritt.hide()
        self.abbrechen.hide()
        self.statusBar().clearMessage()
        QtWidgets.QMessageBox.warning(self, tr("Laden fehlgeschlagen"), text)

    def schliesse_modell(self):
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

    def _pmi_gewaehlt(self, liste):
        flaechen = set()
        for p in liste:
            flaechen |= p.flaechen
        self.ansicht.hebe_flaechen(flaechen)
        self.ansicht.hebe_pmi({p.step_id for p in liste if p.step_id})
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

    def _ansicht_gewaehlt(self, ansicht):
        if ansicht is None:
            self.pmi.nur_ansicht(None)
            self.ansicht.zeige_pmi(None)
            return
        self.pmi.nur_ansicht(set(ansicht.pmi_nummern))
        self.ansicht.zeige_pmi(ansicht.pmi_ids)
        self.ansicht.kamera(ansicht)
        self.statusBar().showMessage(tr("Ansicht {}: {} PMI").format(ansicht.name, len(ansicht.pmi_nummern)), 5000)

    # --- Befehle ---

    def _grafik_umschalten(self):
        self.ansicht.setze_grafik(self.aktionen["grafik"].isChecked())

    def _hilfe_umschalten(self):
        self.ansicht.setze_hilfsgeometrie(self.aktionen["hilfsgeometrie"].isChecked())

    def _schnitt(self, achse):
        self._schnitt_achse = achse
        da = self.erg is not None
        self.schnitt_regler.setEnabled(da and achse is not None)
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
        if w["thema"] != self.ein.value("thema", "auto"):
            self.setze_thema(w["thema"])
            self.aktionen["thema_" + w["thema"]].setChecked(True)
        if w["sprache"] != self.ein.value("sprache", "auto"):
            self.ein.setValue("sprache", w["sprache"])
            self.aktionen["sprache_" + w["sprache"]].setChecked(True)
            QtWidgets.QMessageBox.information(self, tr("Sprache"),
                                              tr("Die Sprache wird beim nächsten Start übernommen."))

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
        self.lade_abbrechen()
        super().closeEvent(ev)
