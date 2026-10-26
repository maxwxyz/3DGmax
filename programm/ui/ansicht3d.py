"""3D-Ansicht: OCCT-Viewer im Qt-Fenster mit Navigation wie in CAD-Programmen.

Maussteuerung siehe navigation.py (Standard: CATIA, wahlweise klassisch in den Einstellungen).
Trackpad (beide Modi): zwei Finger verschieben, Aufziehen zoomt, Wahltaste/Alt + zwei Finger dreht.
Linksklick waehlt Flaeche oder grafische PMI.

Ohne Grafik (Tests mit QT_QPA_PLATFORM=offscreen) wird PlatzhalterAnsicht verwendet: gleiche
Schnittstelle, merkt sich nur den Zustand.
"""

from __future__ import annotations

import contextlib
import os
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from .navigation import Navigation

STANDARDANSICHTEN = ("vorne", "hinten", "oben", "unten", "links", "rechts", "iso")
DARSTELLUNGEN = ("kanten", "schattiert", "draht")


def grafik_verfuegbar() -> bool:
    if os.environ.get("DG_OHNE_3D"):
        return False
    return QtGui.QGuiApplication.platformName() not in ("offscreen", "minimal")


def erzeuge(parent=None) -> "AnsichtBasis":
    return OcctAnsicht(parent) if grafik_verfuegbar() else PlatzhalterAnsicht(parent)


class Szene:
    """Was angezeigt wird (vom Hauptfenster gefuellt)."""

    def __init__(self, modell, baum, farben, grafik, pmi):
        self.modell = modell
        self.baum = baum
        self.farben = farben  # Flaechenindex -> RGB
        self.grafik = grafik  # Callout-ID -> Grafik
        self.pmi = pmi
        self.pmi_text = {p.step_id: p.wert_text() for p in pmi if p.step_id}


class AnsichtBasis(QtWidgets.QWidget):
    """Gemeinsame Schnittstelle und Zustand (fuer Tests pruefbar)."""

    flaeche_gewaehlt = QtCore.Signal(int)  # Flaechenindex, -1 = nichts
    pmi_gewaehlt = QtCore.Signal(set)  # STEP-#IDs der angeklickten grafischen PMI
    element_gewaehlt = QtCore.Signal(object, object)  # Messmodus: TopoDS-Form, Punkt (x, y, z)
    auswahl_geaendert = QtCore.Signal(list)  # 3D-Auswahl (Flaechen/Kanten)
    ausricht_punkt = QtCore.Signal(str, object, object)  # "neu"/"alt", Form, Punkt (x, y, z) in Anzeigekoordinaten
    kontextmenue = QtCore.Signal(object)  # globale Bildschirmposition (QPoint)
    meldung = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.szene: Szene | None = None
        self.modus = "kanten"
        self.hervor: set[int] = set()
        self.pmi_ids_sichtbar: set[int] | None = None  # None = alle
        self.pmi_ids_hervor: set[int] = set()
        self.grafik_an = True
        self.grafik_nur_auswahl = False  # nur die gewaehlten PMI als Grafik zeigen
        self.hilfsgeometrie_an = False
        self.versteckt: set[int] = set()
        self.transparent: set[int] = set()
        self.schnitt_zustand = None  # (achse, anteil, umgekehrt) oder None
        self.letzte_ansicht = "iso"
        self.thema: dict = {}
        self.navigation = "catia"
        self.messmodus = False
        self.messungen: list = []
        self.pmi_kontrast = True  # PMI-Farbe ans Farbschema anpassen (sonst Farbe aus der Datei)
        self.pmi_eigene_farbe = None  # (r, g, b) oder None
        self.hintergrund = None  # ((r, g, b) oben, (r, g, b) unten) oder None = Farbschema
        self.vergleich_status: dict | None = None
        self.vergleich_entfernt: list = []
        self.vergleich_trsf = None
        self.abweichung = None  # (Karte, Toleranz, Grenze) der Farbkarte
        self.perspektive = False
        self.bezugssystem: list = []
        self.ballone: list = []
        self.explosion = 0.0
        self.letzter_zoom = None
        self.letzte_ausrichtung = None
        self.auswahl3d: list = []  # gewaehlte Flaechen/Kanten (TopoDS)
        self.schnitt_eigen = None  # (punkt, normale) fuer Schnitt an Auswahl / aus Blickrichtung
        self.ausricht_alt = None  # Form des alten Stands im Modus "manuell ausrichten", sonst None

    # --- Schnittstelle (Unterklassen ergaenzen die Darstellung) ---

    def zeige(self, szene: Szene | None):
        self.szene = szene
        self.hervor, self.pmi_ids_hervor = set(), set()
        self.versteckt, self.transparent = set(), set()
        self.pmi_ids_sichtbar = None
        self.schnitt_zustand = None

    def hebe_flaechen(self, flaechen: set[int]):
        self.hervor = set(flaechen)

    def zeige_pmi(self, ids: set[int] | None):
        self.pmi_ids_sichtbar = None if ids is None else set(ids)

    def zeige_ballone(self, ballone: list):
        """Ballonnummern [(Nummer, (x, y, z))] an den Merkmalen; [] blendet aus."""
        self.ballone = list(ballone)

    def oben_richtung(self) -> tuple[float, float, float]:
        """Richtung, die im Bild nach oben zeigt."""
        return (0.0, 1.0, 0.0)

    def blick_zum_betrachter(self) -> tuple[float, float, float]:
        """Richtung vom Modell zum Betrachter (fuer Entformung 'Blickrichtung')."""
        return (0.0, 0.0, 1.0)

    def setze_explosion(self, anteil: float):
        """Explosionsansicht: Teile vom Mittelpunkt weg verschieben (0 = aus, 1 = weit)."""
        self.explosion = max(0.0, min(1.0, anteil))

    def mitte_von(self, flaechen):
        """Schwerpunkt von Flaechen (Index) oder None."""
        return None

    def zeige_bezugssystem(self, bezuege: list):
        """Bezugssystem einer Toleranz: [(Name, Stelle 1..3, Flaechen)] farbig mit Beschriftung; [] blendet aus."""
        self.bezugssystem = list(bezuege)

    def hebe_pmi(self, ids: set[int]):
        self.pmi_ids_hervor = set(ids)

    def setze_grafik(self, an: bool, nur_auswahl: bool = False):
        self.grafik_an = an
        self.grafik_nur_auswahl = nur_auswahl

    def setze_hilfsgeometrie(self, an: bool):
        self.hilfsgeometrie_an = an

    def darstellung(self, modus: str):
        self.modus = modus

    def standard(self, name: str):
        self.letzte_ansicht = name

    def alles_zeigen(self):
        pass

    def kamera(self, ansicht):
        self.letzte_ansicht = ansicht.name

    def knoten_sichtbar(self, nummern: set[int], sichtbar: bool):
        self.versteckt = (self.versteckt - nummern) if sichtbar else (self.versteckt | nummern)

    def isoliere(self, nummern: set[int] | None):
        if self.szene is None:
            return
        alle = {k.nummer for k in self.szene.baum.blaetter()}
        self.versteckt = set() if not nummern else alle - nummern

    def knoten_transparent(self, nummern: set[int], an: bool):
        self.transparent = (self.transparent | nummern) if an else (self.transparent - nummern)

    def schnitt(self, achse: str | None, anteil: float = 0.5, umgekehrt: bool = False):
        self.schnitt_zustand = None if achse is None else (achse, anteil, umgekehrt)

    def setze_thema(self, thema: dict):
        self.thema = thema

    def setze_navigation(self, modus: str):
        self.navigation = modus

    def setze_messmodus(self, an: bool):
        self.messmodus = an

    def setze_pmi_kontrast(self, an: bool):
        self.pmi_kontrast = an

    def pmi_farbe(self, g) -> tuple:
        """Anzeigefarbe einer Annotation: eigene Farbe, Schemafarbe (gut lesbar) oder Farbe aus der Datei."""
        if self.pmi_eigene_farbe is not None:
            return self.pmi_eigene_farbe
        schema = (self.thema or {}).get("pmi", (0.05, 0.2, 0.55))
        return schema if self.pmi_kontrast or g.farbe is None else g.farbe

    def setze_farben(self, pmi_eigen, hintergrund):
        self.pmi_eigene_farbe = pmi_eigen
        self.hintergrund = hintergrund

    def zeige_messungen(self, messungen: list):
        self.messungen = list(messungen)

    def fang_toleranz(self) -> float:
        """Fangweite in mm (etwa 12 Pixel)."""
        return 1.0

    def zeige_vergleich(self, status: dict | None, entfernt_formen: list | None = None, trsf=None):
        """Vergleichsmodus: Flaechen des neuen Stands nach Status einfaerben, entfernte Flaechen (alt) zeigen.
        status None beendet den Vergleichsmodus."""
        self.vergleich_status = None if status is None else dict(status)
        if status is None:
            self.abweichung = None
        self.vergleich_entfernt = list(entfernt_formen or [])
        self.vergleich_trsf = trsf

    def zeige_abweichung(self, karte, toleranz: float = 0.01, grenze: float = 0.1):
        """Abweichungs-Farbkarte (kern.abweichung.Karte) statt der Statusfarben zeigen; None blendet sie aus."""
        from ..kern import abweichung as ab
        self.abweichung = None if karte is None else (karte, toleranz, grenze,
                                                      ab.abweichungs_skala(toleranz, grenze, tr("Abweichung (mm)")))

    def zeige_analyse(self, karte, skala=None):
        """Analyse-Farbkarte (Entformung, Kruemmung, Wandstaerke) mit eigener Skala; None blendet aus."""
        self.abweichung = None if karte is None else (karte, None, None, skala)

    def zoome_auf(self, flaechen: set[int], formen: list | None = None, pmi_ids: set | None = None):
        """Ausschnitt auf Flaechen (Index im angezeigten Modell), weitere Formen und PMI-Grafik setzen."""
        self.letzter_zoom = (set(flaechen), len(formen or []), set(pmi_ids or ()))

    def richte_normal_aus(self, flaechen: set[int], formen: list | None = None, pmi_ids: set | None = None):
        """Kamera senkrecht auf die Auswahl (Flaechennormale, Mittel bei mehreren, Ebene der Beschriftung)."""
        self.letzte_ausrichtung = (set(flaechen), len(formen or []), set(pmi_ids or ()))

    def setze_auswahl(self, formen: list):
        self.auswahl3d = list(formen)
        self.auswahl_geaendert.emit(list(self.auswahl3d))

    def schnitt_aus_auswahl(self) -> bool:
        """Schnittebene durch die gewaehlte Flaeche/Kante; False ohne passende Auswahl."""
        return False

    def schnitt_aus_blick(self) -> bool:
        return False

    def schnitt_anteil_von_punkt(self, achse) -> float | None:
        """Reglerstellung, bei der die Ebene durch den Auswahlpunkt geht (ohne 3D-Grafik: unbekannt)."""
        return None

    def setze_ausrichtmodus(self, alt_form):
        """Manuell ausrichten: alten Stand halbdurchsichtig zeigen, Klicks liefern Punkte an 'neu' und 'alt'."""
        self.ausricht_alt = alt_form

    def umdrehen(self):
        """Blick von der Gegenseite (180 Grad um die Hochachse)."""
        self.umgedreht = not getattr(self, "umgedreht", False)

    def bild(self, pfad: str) -> bool:
        return False

    def bild_qimage(self) -> QtGui.QImage:
        """Aktuelle Ansicht als Bild (fuer Berichte)."""
        img = self.grab().toImage()
        return img

    def drehpunkt_zuruecksetzen(self, melden: bool = True):
        pass

    def aktuelle_ansicht(self, name: str):
        """Kamera als gespeicherte Ansicht (vom Nutzer gemerkt)."""
        from ..kern.ansichten import Ansicht
        return Ansicht(name, 0, eigen=True)

    def setze_perspektive(self, an: bool):
        """Zentralperspektive statt Parallelprojektion."""
        self.perspektive = an

    def kamera_zurueck(self) -> bool:
        """Vorherige Kamera (Ansicht zurueck); False wenn es keine gibt."""
        return False

    def kamera_vor(self) -> bool:
        return False


class PlatzhalterAnsicht(AnsichtBasis):
    """Ersatz ohne 3D-Grafik (Tests, Rechner ohne OpenGL)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        self.text = QtWidgets.QLabel(tr("3D-Ansicht nicht verfügbar (keine Grafik)"))
        self.text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.text)

    def bild(self, pfad: str) -> bool:
        return self.grab().save(pfad)


# ----------------------------------------------------------------------------- OCCT

# Bezugssystem: primaer, sekundaer, tertiaer (gut unterscheidbar, auch neben der Hervorhebung in Orange)
BEZUG_FARBEN = {1: (0.85, 0.20, 0.25), 2: (0.20, 0.65, 0.35), 3: (0.25, 0.45, 0.90)}
SCHRIFT = "Helvetica Neue" if sys.platform == "darwin" else ("Segoe UI" if sys.platform == "win32" else "DejaVu Sans")


def _farbe(rgb):
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    return Quantity_Color(float(rgb[0]), float(rgb[1]), float(rgb[2]), Quantity_TOC_RGB)


def _grafik_form(g, pmi_text: dict):
    """Callout-Grafik als OCCT-Formen: (Linien+Flaechen-Compound, Texte[(Platzhalter, Text)])."""
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakePolygon
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.Poly import Poly_Triangle, Poly_Triangulation
    from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Face

    bb = BRep_Builder()
    comp = TopoDS_Compound()
    bb.MakeCompound(comp)
    leer = True
    for linie in g.linien:
        pts = [gp_Pnt(*map(float, p)) for p in linie]
        if len(pts) == 2:
            if pts[0].Distance(pts[1]) > 1e-9:
                bb.Add(comp, BRepBuilderAPI_MakeEdge(pts[0], pts[1]).Edge())
                leer = False
        elif len(pts) > 2:
            poly = BRepBuilderAPI_MakePolygon()
            for p in pts:
                poly.Add(p)
            if poly.IsDone():
                bb.Add(comp, poly.Wire())
                leer = False
    for punkte, tris in g.dreiecke:
        tri = Poly_Triangulation(len(punkte), len(tris), False)
        for i, p in enumerate(punkte, 1):
            tri.SetNode(i, gp_Pnt(*map(float, p)))
        for i, (a, b, c) in enumerate(tris, 1):
            tri.SetTriangle(i, Poly_Triangle(int(a) + 1, int(b) + 1, int(c) + 1))
        f = TopoDS_Face()
        bb.MakeFace(f, tri)
        bb.Add(comp, f)
        leer = False
    texte = []
    if g.platzhalter and not g.doppelt:
        text = "  ".join(pmi_text[i] for i in sorted(g.pmi_ids) if i in pmi_text) or g.name
        texte = [(ph, text) for ph in g.platzhalter]
    return (None if leer else comp), texte


class OcctAnsicht(AnsichtBasis):
    def __init__(self, parent=None):
        super().__init__(parent)
        from OCC.Display.backend import load_backend
        load_backend("pyside6")
        from OCC.Display.qtDisplay import qtBaseViewer

        self.viewer = qtBaseViewer(self)
        self.viewer.installEventFilter(self)
        self.viewer.setMouseTracking(True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.viewer)
        self._bereit = False
        self._teile: dict[int, object] = {}  # Knotennummer -> AIS_ColoredShape
        self._kanten: dict[int, object] = {}  # Knotennummer -> AIS_Shape (nur Kanten)
        self._flaechen_ais: dict[int, list] = {}  # Flaechenindex -> [(ais, face)]
        self._hilfe: list = []
        self._callouts: dict[int, list] = {}  # Callout-ID -> [AIS]
        self._ais_callout: dict = {}
        self._clip = None
        self._drehpunkt = None
        self.nav = Navigation(self.navigation)
        # Kameraverlauf fuer Ansicht zurueck/vor: gemerkt, wenn die Kamera kurz ruht
        self._verlauf: list[tuple] = []
        self._verlauf_pos = -1
        self._verlauf_uhr = QtCore.QTimer(self)
        self._verlauf_uhr.setSingleShot(True)
        self._verlauf_uhr.setInterval(450)
        self._verlauf_uhr.timeout.connect(self._kamera_merken)

    # --- Start und Grundlagen ---

    @property
    def d(self):
        return self.viewer._display

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._bereit:
            QtCore.QTimer.singleShot(0, self._starte)

    def _starte(self):
        if self._bereit:
            return
        self.d.Create(window_handle=int(self.viewer.winId()), parent=self.viewer, display_glinfo=False)
        self.d.SetModeShaded()
        self.d.Context.SetAutomaticHilight(True)
        # Kanten zeichnet die eigene Kantenebene; die Standard-Flaechenraender (blasse Linien) abschalten
        self.d.Context.DefaultDrawer().SetFaceBoundaryDraw(False)
        try:
            self.d.View.ChangeRenderingParams().NbMsaaSamples = 4  # Kantenglaettung
        except Exception:  # noqa: BLE001 - aeltere Treiber ohne MSAA
            pass
        self._baue_wuerfel()
        self._bereit = True
        self.viewer._inited = True
        self.setze_thema(self.thema)
        if self.szene is not None:
            self._baue_szene()

    # --- Ansichtswuerfel (mit Achsenkreuz) ---

    WUERFEL_SEITEN = (("V3d_Yneg", "Vorne"), ("V3d_Ypos", "Hinten"), ("V3d_Zpos", "Oben"),
                      ("V3d_Zneg", "Unten"), ("V3d_Xneg", "Links"), ("V3d_Xpos", "Rechts"))

    def _baue_wuerfel(self):
        """Wuerfel oben rechts: abgeschraegte Kanten/Ecken, beschriftete Seiten, Achsen X/Y/Z.
        Klick auf Seite/Kante/Ecke richtet die Kamera aus, Ziehen dreht die Kamera."""
        from OCC.Core import V3d
        from OCC.Core.AIS import AIS_ViewCube
        from OCC.Core.Aspect import Aspect_TOTP_RIGHT_UPPER
        from OCC.Core.Graphic3d import Graphic3d_TMF_TriedronPers, Graphic3d_TransformPers, Graphic3d_Vec2i
        from OCC.Core.TCollection import TCollection_AsciiString
        from OCC.Core import Prs3d
        from OCC.Core.Aspect import Aspect_TOL_SOLID
        from OCC.Core.Prs3d import Prs3d_DatumAspect, Prs3d_LineAspect
        w = AIS_ViewCube()
        # macOS: Wuerfel (Transform-Persistenz) wird in Geraetepixeln gezeichnet, aber in logischen Punkten
        # gepickt -> auf Retina mitskalieren und beim Picken umrechnen (_wuerfel_unter_maus)
        k = max(1.0, self.viewer.devicePixelRatioF()) if sys.platform == "darwin" else 1.0
        self._wuerfel_k = k
        w.SetSize(48 * k)
        w.SetBoxFacetExtension(7 * k)  # abgeschraegte Ecken und Kanten
        w.SetBoxEdgeGap(0)
        schrift = SCHRIFT
        w.SetFont(TCollection_AsciiString(schrift))
        w.SetFontHeight(11 * k)
        w.SetDrawAxes(True)
        w.SetAxesPadding(4 * k)
        w.SetAxesRadius(0.9 * k)
        w.SetAxesConeRadius(2.4 * k)
        w.SetAxesSphereRadius(2.6 * k)
        w.SetAxesLabels(TCollection_AsciiString("X"), TCollection_AsciiString("Y"), TCollection_AsciiString("Z"))
        # Achsen farbig wie ueblich: X rot, Y gruen, Z blau
        datum = Prs3d_DatumAspect()
        for teil, pfeil, rgb in ((Prs3d.Prs3d_DatumParts_XAxis, Prs3d.Prs3d_DatumParts_XArrow, (0.86, 0.24, 0.22)),
                                 (Prs3d.Prs3d_DatumParts_YAxis, Prs3d.Prs3d_DatumParts_YArrow, (0.30, 0.68, 0.30)),
                                 (Prs3d.Prs3d_DatumParts_ZAxis, Prs3d.Prs3d_DatumParts_ZArrow, (0.25, 0.48, 0.90))):
            farbe = _farbe(rgb)
            for t in (teil, pfeil):
                datum.ShadingAspect(t).SetColor(farbe)
            text = datum.TextAspect(teil)
            text.SetColor(farbe)
            text.SetHeight(12 * k)
            text.Aspect().SetFont(schrift)  # serifenlos wie die Seitenbeschriftung
            datum.LineAspect(teil).SetColor(farbe) if datum.LineAspect(teil) else None
        w.Attributes().SetDatumAspect(datum)
        _ = Aspect_TOL_SOLID, Prs3d_LineAspect
        w.SetTransformPersistence(Graphic3d_TransformPers(Graphic3d_TMF_TriedronPers, Aspect_TOTP_RIGHT_UPPER,
                                                          Graphic3d_Vec2i(int(80 * k), int(80 * k))))
        for name, text in self.WUERFEL_SEITEN:
            w.SetBoxSideLabel(getattr(V3d, name), TCollection_AsciiString(tr(text)))
        w.SetAutoStartAnimation(False)
        self._wuerfel = w
        self._wuerfel_ziehen = None
        self._faerbe_wuerfel()

    def _faerbe_wuerfel(self):
        w = getattr(self, "_wuerfel", None)
        if w is None:
            return
        from OCC.Core.Graphic3d import Graphic3d_NameOfMaterial_UserDefined, Graphic3d_MaterialAspect
        # hell und matt auf hellem wie dunklem Hintergrund (wie gaengige CAD-Wuerfel), Schrift dunkel
        mat = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial_UserDefined)
        mat.SetSpecularColor(_farbe((0.02, 0.02, 0.02)))
        mat.SetAmbientColor(_farbe((0.75, 0.75, 0.75)))
        mat.SetDiffuseColor(_farbe((0.55, 0.55, 0.55)))
        w.SetMaterial(mat)
        w.SetBoxColor(_farbe((0.97, 0.97, 0.98)))
        w.SetInnerColor(_farbe((0.78, 0.80, 0.84)))
        w.SetTextColor(_farbe((0.10, 0.11, 0.13)))
        w.SetBoxTransparency(0.0 if getattr(self, "_wuerfel_hover", False) else 0.55)  # dezent, beim Hovern deckend
        akzent = (self.thema or {}).get("hervor", (1, 0.45, 0))
        hover = w.DynamicHilightAttributes()
        if hover is not None:
            hover.SetColor(_farbe(akzent))

    def _zeige_wuerfel(self):
        w = getattr(self, "_wuerfel", None)
        if w is not None:
            ctx = self.d.Context
            ctx.Remove(w, False)
            self._faerbe_wuerfel()
            ctx.Display(w, False)

    def _wuerfel_unter_maus(self, x, y, zeichnen=False):
        """Teil des Ansichtswuerfels unter der Maus (Owner) oder None."""
        from OCC.Core.AIS import AIS_ViewCubeOwner
        w = getattr(self, "_wuerfel", None)
        ctx = self.d.Context
        if w is None:
            ctx.MoveTo(int(x), int(y), self.d.View, zeichnen)
            return None
        k = getattr(self, "_wuerfel_k", 1.0)
        breite = self.viewer.width()
        # sichtbare Lage (Geraetepixel ab Ecke oben rechts) in die Pick-Lage umrechnen
        ctx.MoveTo(int(breite - k * (breite - x)), int(k * y), self.d.View, zeichnen)
        treffer = ctx.HasDetected() and ctx.DetectedInteractive() == w
        if zeichnen and treffer != getattr(self, "_wuerfel_hover", False):
            self._wuerfel_hover = treffer
            w.SetBoxTransparency(0.0 if treffer else 0.55)
            ctx.Redisplay(w, True)
        if not treffer:
            if k != 1.0:
                ctx.MoveTo(int(x), int(y), self.d.View, zeichnen)  # sonst normal am echten Ort
            return None
        besitzer = AIS_ViewCubeOwner.DownCast(ctx.DetectedOwner())
        return besitzer if besitzer is not None else None

    def wuerfel_ausrichten(self, orientierung):
        """Kamera auf eine Wuerfelseite, -kante oder -ecke ausrichten und einpassen."""
        self.d.View.SetProj(orientierung)
        self.alles_zeigen()
        self._kamera_bewegt()

    def _wuerfel_maus(self, typ, ev, x, y) -> bool:
        """Maus auf dem Wuerfel: Klick richtet aus, Ziehen dreht. True = Ereignis verbraucht."""
        E = QtCore.QEvent.Type
        links = QtCore.Qt.MouseButton.LeftButton
        if typ == E.MouseButtonPress and ev.button() == links and self.nav.start is None:
            besitzer = self._wuerfel_unter_maus(x, y)
            if besitzer is None:
                return False
            self._mitte_cache = self._mitte()
            self._wuerfel_ziehen = [x, y, False, besitzer.MainOrientation()]
            return True
        z = self._wuerfel_ziehen
        if z is None:
            return False
        if typ == E.MouseMove:
            dx, dy = x - z[0], y - z[1]
            if z[2] or abs(dx) + abs(dy) > 3:
                z[2] = True
                self._drehe(dx, dy)
                z[0], z[1] = x, y
            return True
        if typ == E.MouseButtonRelease and ev.button() == links:
            self._wuerfel_ziehen = None
            if not z[2]:
                self.wuerfel_ausrichten(z[3])
            return True
        return typ == E.MouseButtonDblClick

    def _neu_zeichnen(self):
        if self._bereit:
            self.d.Context.UpdateCurrentViewer()
            self.d.View.Redraw()

    def setze_thema(self, thema: dict):
        super().setze_thema(thema)
        if not self._bereit or not thema:
            return
        from OCC.Core.Aspect import Aspect_GFM_VER
        oben, unten = self.hintergrund or (thema["hg_oben"], thema["hg_unten"])
        self.d.View.SetBgGradientColors(_farbe(oben), _farbe(unten), Aspect_GFM_VER, True)
        if self.szene is not None:
            self._baue_szene()
        else:
            self._zeige_wuerfel()
            self._neu_zeichnen()

    # --- Szene ---

    def zeige(self, szene):
        super().zeige(szene)
        if self._bereit:
            self._baue_szene()

    def _baue_szene(self):
        from OCC.Core.AIS import AIS_ColoredShape, AIS_Shape
        from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NameOfMaterial_Plastified
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopoDS import topods

        ctx = self.d.Context
        ctx.RemoveAll(False)
        self._drehpunkt_ais = None
        self._zeige_wuerfel()
        self._teile, self._kanten, self._flaechen_ais, self._hilfe = {}, {}, {}, []
        self._callouts, self._ais_callout = {}, {}
        self._entferne_schnitt()
        sz = self.szene
        if sz is None:
            self._neu_zeichnen()
            return
        t = self.thema or {}
        grundfarbe = t.get("modell", (0.78, 0.8, 0.84))
        for k in sz.baum.blaetter():
            if k.hilfsgeometrie:
                ais = AIS_Shape(k.form)
                ais.SetColor(_farbe(t.get("kante", (0.2, 0.2, 0.2))))
                self._hilfe.append(ais)
                continue
            ais = AIS_ColoredShape(k.form)
            ais.SetMaterial(Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial_Plastified))
            ais.SetColor(_farbe(grundfarbe))
            ex = TopExp_Explorer(k.form, TopAbs_FACE)
            while ex.More():
                f = topods.Face(ex.Current())
                idx = sz.modell.flaechen_index(f)
                if idx is not None:
                    self._flaechen_ais.setdefault(idx, []).append((ais, f))
                    farbe = self._grundfarbe(idx)
                    if farbe is not None:
                        ais.SetCustomColor(f, _farbe(farbe))
                ex.Next()
            self._teile[k.nummer] = ais
            if self.vergleich_trsf is not None:
                ais.SetLocalTransformation(self.vergleich_trsf)
            ctx.Display(ais, 1, -1, False)
            ctx.Deactivate(ais)
            ctx.Activate(ais, 4, False)  # 4 = Flaechen waehlbar
            # Kanten als eigene Ebene: Flaechen mit eigener Farbe zeichnen in OCCT keine Raender
            kanten = AIS_Shape(_kanten_von(k.form))
            kanten.SetColor(_farbe(t.get("kante", (0.15, 0.17, 0.2))))
            kanten.SetWidth(1.0)
            if self.vergleich_trsf is not None:
                kanten.SetLocalTransformation(self.vergleich_trsf)
            self._kanten[k.nummer] = kanten
        self._mess_ais = []
        self._karte_ais = []
        self._bezug_ais = []
        self._ballon_ais = []
        self._baue_entfernt()
        self._baue_grafik()
        self._baue_abweichung()
        if self.ballone:
            self.zeige_ballone(self.ballone)
        if self.explosion > 0:
            self.setze_explosion(self.explosion)
        self._wende_darstellung_an()
        self._wende_sichtbarkeit_an()
        self._verlauf, self._verlauf_pos = [], -1
        self.setze_perspektive(self.perspektive)
        self.standard(self.letzte_ansicht if self.letzte_ansicht in STANDARDANSICHTEN else "iso")
        self._drehpunkt = None

    def _baue_entfernt(self):
        """Im alten Stand vorhandene, im neuen entfernte Flaechen: rot, durchscheinend, nicht waehlbar."""
        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        self._entfernt_ais = None
        if not self.vergleich_entfernt:
            return
        bb = BRep_Builder()
        comp = TopoDS_Compound()
        bb.MakeCompound(comp)
        for f in self.vergleich_entfernt:
            bb.Add(comp, f)
        ais = AIS_Shape(comp)
        ais.SetColor(_farbe(_status_farbe(self.thema or {}, "entfernt") or (0.9, 0.15, 0.15)))
        self.d.Context.Display(ais, 1, -1, False)
        self.d.Context.SetTransparency(ais, 0.55, False)
        self.d.Context.Deactivate(ais)
        self._entfernt_ais = ais

    def zeige_vergleich(self, status, entfernt_formen=None, trsf=None):
        super().zeige_vergleich(status, entfernt_formen, trsf)
        if status is None:
            self.abweichung = None
        if self._bereit and self.szene is not None:
            self._baue_szene()

    def zeige_analyse(self, karte, skala=None):
        super().zeige_analyse(karte, skala)
        if self._bereit:
            self._baue_abweichung()
            self._wende_sichtbarkeit_an()
            self._neu_zeichnen()

    def zeige_abweichung(self, karte, toleranz=0.01, grenze=0.1):
        super().zeige_abweichung(karte, toleranz, grenze)
        if self._bereit:
            self._baue_abweichung()
            self._wende_sichtbarkeit_an()
            self._neu_zeichnen()

    def _baue_abweichung(self):
        """Farbiges Netz (Farbe je Knoten) und Legende; Teile werden dabei ausgeblendet."""
        from OCC.Core.AIS import AIS_ColorScale, AIS_Triangulation
        from OCC.Core.Aspect import Aspect_TOCSD_USER, Aspect_TOTP_LEFT_LOWER
        from OCC.Core.Graphic3d import (Graphic3d_MaterialAspect, Graphic3d_NameOfMaterial_UserDefined,
                                        Graphic3d_TMF_2d, Graphic3d_TransformPers, Graphic3d_Vec2i)
        from OCC.Core.Poly import Poly_Triangle, Poly_Triangulation
        from OCC.Core.TColStd import TColStd_HArray1OfInteger, TColStd_SequenceOfExtendedString
        from OCC.Core.TCollection import TCollection_ExtendedString
        from OCC.Core.gp import gp_Pnt
        ctx = self.d.Context
        for alt in getattr(self, "_karte_ais", []):
            ctx.Remove(alt, False)
        self._karte_ais = []
        if self.abweichung is None:
            return
        karte, _tol, _grenze, sk = self.abweichung
        pts, tris, werte = karte.gesamt()
        if not len(tris):
            return
        netz = Poly_Triangulation(len(pts), len(tris), False)
        for i, p in enumerate(pts, 1):
            netz.SetNode(i, gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
        for i, t in enumerate(tris, 1):
            netz.SetTriangle(i, Poly_Triangle(int(t[0]) + 1, int(t[1]) + 1, int(t[2]) + 1))
        farben = TColStd_HArray1OfInteger(1, len(pts))
        for i, w in enumerate(werte, 1):
            r, g, b = sk.farbe(float(w))
            c = int(r * 255) | int(g * 255) << 8 | int(b * 255) << 16 | 255 << 24  # RGBA als Bytes
            farben.SetValue(i, c - (1 << 32))  # als vorzeichenbehaftete 32-Bit-Zahl
        flaeche = AIS_Triangulation(netz)
        flaeche.SetColors(farben)
        mat = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial_UserDefined)
        mat.SetAmbientColor(_farbe((0.55, 0.55, 0.55)))
        mat.SetDiffuseColor(_farbe((0.8, 0.8, 0.8)))
        mat.SetSpecularColor(_farbe((0.1, 0.1, 0.1)))
        flaeche.SetMaterial(mat)
        ctx.Display(flaeche, 0, -1, False)  # AIS_Triangulation kennt nur Modus 0
        ctx.Deactivate(flaeche)
        self._karte_ais.append(flaeche)
        # Legende unten links nach den Stufen der Skala
        grenzen = sk.grenzen
        k = max(1.0, self.viewer.devicePixelRatioF()) if sys.platform == "darwin" else 1.0
        skala = AIS_ColorScale()
        skala.SetRange(grenzen[0], grenzen[-1])
        skala.SetNumberOfIntervals(len(grenzen) - 1)
        skala.SetColorType(Aspect_TOCSD_USER)
        for i in range(len(grenzen) - 1):
            mitte = (grenzen[i] + grenzen[i + 1]) / 2
            skala.SetIntervalColor(_farbe(sk.farbe(mitte)), i + 1)
        texte = TColStd_SequenceOfExtendedString()
        for t in sk.texte():
            texte.Append(TCollection_ExtendedString(t, True))
        skala.SetLabelType(Aspect_TOCSD_USER)
        skala.SetLabels(texte)
        skala.SetLabelAtBorder(True)
        skala.SetTitle(TCollection_ExtendedString(sk.titel, True))
        skala.SetTextHeight(int(13 * k))
        dunkel = sum((self.thema or {}).get("hg_oben", (1, 1, 1))) < 1.5
        skala.SetColor(_farbe((0.95, 0.95, 0.95) if dunkel else (0.1, 0.1, 0.12)))  # Schriftfarbe
        # Breite = Farbbalken + Beschriftung (OCCT begrenzt den Balken auf 20 px)
        skala.SetSize(int(110 * k), int(260 * k))
        from OCC.Core.Prs3d import Prs3d_TextAspect
        text = Prs3d_TextAspect()
        text.Aspect().SetFont(SCHRIFT)
        text.SetColor(_farbe((0.95, 0.95, 0.95) if dunkel else (0.1, 0.1, 0.12)))
        text.SetHeight(int(13 * k))
        skala.Attributes().SetTextAspect(text)
        skala.SetTransformPersistence(Graphic3d_TransformPers(Graphic3d_TMF_2d, Aspect_TOTP_LEFT_LOWER,
                                                              Graphic3d_Vec2i(int(20 * k), int(20 * k))))
        ctx.Display(skala, False)
        ctx.Deactivate(skala)
        self._karte_ais.append(skala)

    def abweichung_bei(self, x, y) -> tuple | None:
        """(Punkt, Abweichung) der Farbkarte unter der Maus."""
        if self.abweichung is None or not self._bereit:
            return None
        px, py, pz, vx, vy, vz = self.d.View.ConvertWithProj(int(x), int(y))
        return self.abweichung[0].am_strahl((px, py, pz), (vx, vy, vz))

    def setze_ausrichtmodus(self, alt_form):
        super().setze_ausrichtmodus(alt_form)
        if not self._bereit:
            return
        from OCC.Core.AIS import AIS_Shape
        ctx = self.d.Context
        if getattr(self, "_alt_ais", None) is not None:
            ctx.Remove(self._alt_ais, False)
            self._alt_ais = None
        if alt_form is not None:
            ais = AIS_Shape(alt_form)
            ais.SetColor(_farbe((0.25, 0.55, 0.95)))
            ctx.Display(ais, 1, -1, False)
            ctx.SetTransparency(ais, 0.6, False)
            ctx.Deactivate(ais)
            for modus in (1, 2, 4):
                ctx.Activate(ais, modus, False)
            self._alt_ais = ais
        self.messmodus = alt_form is not None or self.messmodus
        self._aktiviere_auswahl()
        self._neu_zeichnen()

    def umdrehen(self):
        super().umdrehen()
        if not self._bereit:
            return
        from OCC.Core.gp import gp_Pnt
        cam = self.d.View.Camera()
        c, e = cam.Center(), cam.Eye()
        cam.SetEye(gp_Pnt(2 * c.X() - e.X(), 2 * c.Y() - e.Y(), 2 * c.Z() - e.Z()))
        self.d.View.ZFitAll()
        self._kamera_bewegt()
        self._neu_zeichnen()

    def _baue_grafik(self):
        from OCC.Core.AIS import AIS_Shape, AIS_TextLabel
        from OCC.Core.Graphic3d import Graphic3d_ZLayerId_Top
        from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
        from OCC.Core.TCollection import TCollection_ExtendedString

        sz = self.szene
        farbe = _farbe((self.thema or {}).get("pmi", (0.05, 0.2, 0.55)))
        for cid, g in sz.grafik.items():
            liste = []
            form, texte = _grafik_form(g, sz.pmi_text)
            if form is not None:
                ais = AIS_Shape(form)
                ais.SetColor(farbe)
                ais.SetWidth(2.0)
                liste.append(ais)
            for ph, text in texte:
                lab = AIS_TextLabel()
                lab.SetFont(SCHRIFT)
                lab.SetText(TCollection_ExtendedString(text, True))
                o = ph.ursprung
                lab.SetPosition(gp_Pnt(float(o[0]), float(o[1]), float(o[2])))
                z = ph.x[1] * ph.y[2] - ph.x[2] * ph.y[1], ph.x[2] * ph.y[0] - ph.x[0] * ph.y[2], \
                    ph.x[0] * ph.y[1] - ph.x[1] * ph.y[0]
                try:
                    lab.SetOrientation3D(gp_Ax2(gp_Pnt(*map(float, o)), gp_Dir(*map(float, z)),
                                                gp_Dir(*map(float, ph.x))))
                except Exception:  # noqa: BLE001 - degenerierte Achsen: Text zum Betrachter
                    pass
                lab.SetHeight(max(ph.hoehe * 0.7, 1.0))
                lab.SetColor(farbe)
                liste.append(lab)
            for ais in liste:
                ais.SetZLayer(Graphic3d_ZLayerId_Top)
                self._ais_callout[ais] = cid
            self._callouts[cid] = liste

    # --- Sichtbarkeit und Hervorhebung ---

    def _wende_sichtbarkeit_an(self):
        if not self._bereit or self.szene is None:
            return
        ctx = self.d.Context
        for nr, kanten in self._kanten.items():
            if nr in self.versteckt or self.modus != "kanten":
                ctx.Erase(kanten, False)
            else:
                ctx.Display(kanten, 0, -1, False)
                ctx.Deactivate(kanten)
        for nr, ais in self._teile.items():
            if nr in self.versteckt or self.abweichung is not None:
                ctx.Erase(ais, False)
            else:
                ctx.Display(ais, False)
                ctx.SetTransparency(ais, 0.65 if nr in self.transparent else 0.0, False)
        self._aktiviere_auswahl()
        for ais in self._hilfe:
            if self.hilfsgeometrie_an:
                ctx.Display(ais, False)
            else:
                ctx.Erase(ais, False)
        hervor_farbe = _farbe((self.thema or {}).get("pmi_hervor", (0.85, 0.25, 0.0)))
        for cid, liste in self._callouts.items():
            normal = _farbe(self.pmi_farbe(self.szene.grafik[cid]))
            g = self.szene.grafik[cid]
            zeigen = self.grafik_an and not self.grafik_nur_auswahl and \
                (self.pmi_ids_sichtbar is None or bool(g.pmi_ids & self.pmi_ids_sichtbar))
            hervor = bool(g.pmi_ids & self.pmi_ids_hervor)
            zeigen = (zeigen or hervor) and self.explosion <= 0  # Beschriftungen passen nur zur Einbaulage
            for ais in liste:
                if zeigen:
                    ais.SetColor(hervor_farbe if hervor else normal)
                    ctx.Display(ais, False)
                    ctx.Redisplay(ais, False)
                else:
                    ctx.Erase(ais, False)
        self._neu_zeichnen()

    def _grundfarbe(self, idx):
        """Farbe einer Flaeche ohne Hervorhebung: Bezugssystem, Vergleichsstatus, Dateifarbe, sonst None."""
        t = self.thema or {}
        for _name, stelle, flaechen in self.bezugssystem:
            if idx in flaechen:
                return BEZUG_FARBEN.get(stelle, BEZUG_FARBEN[3])
        grund = t.get("modell", (0.78, 0.8, 0.84))
        if self.vergleich_status is not None:
            st = _status_farbe(t, self.vergleich_status.get(idx, "gleich"))
            return st if st is not None else grund
        if idx in self.szene.farben:
            return _abgetoent(self.szene.farben[idx], grund)
        return None

    def hebe_flaechen(self, flaechen):
        alt = self.hervor
        super().hebe_flaechen(flaechen)
        if not self._bereit or self.szene is None:
            return
        t = self.thema or {}
        grund = t.get("modell", (0.78, 0.8, 0.84))
        geaendert = set()
        for idx in alt | self.hervor:
            for ais, f in self._flaechen_ais.get(idx, []):
                if idx in self.hervor:
                    ais.SetCustomColor(f, _farbe(t.get("hervor", (1, 0.45, 0))))
                else:
                    ais.SetCustomColor(f, _farbe(self._grundfarbe(idx) or grund))
                geaendert.add(ais)
        for ais in geaendert:
            self.d.Context.Redisplay(ais, False)
        self._neu_zeichnen()

    def zeige_pmi(self, ids):
        super().zeige_pmi(ids)
        self._wende_sichtbarkeit_an()

    def zeige_bezugssystem(self, bezuege):
        alt = {i for _n, _s, f in self.bezugssystem for i in f}
        super().zeige_bezugssystem(bezuege)
        if not self._bereit or self.szene is None:
            return
        from OCC.Core.AIS import AIS_TextLabel
        from OCC.Core.Graphic3d import Graphic3d_ZLayerId_Topmost
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.TCollection import TCollection_ExtendedString
        ctx = self.d.Context
        for lab in getattr(self, "_bezug_ais", []):
            ctx.Remove(lab, False)
        self._bezug_ais = []
        neu = {i for _n, _s, f in self.bezugssystem for i in f}
        t = self.thema or {}
        geaendert = set()
        for idx in alt | neu:
            for ais, f in self._flaechen_ais.get(idx, []):
                farbe = t.get("hervor", (1, 0.45, 0)) if idx in self.hervor else \
                    (self._grundfarbe(idx) or t.get("modell", (0.78, 0.8, 0.84)))
                ais.SetCustomColor(f, _farbe(farbe))
                geaendert.add(ais)
        for ais in geaendert:
            ctx.Redisplay(ais, False)
        for name, stelle, flaechen in self.bezugssystem:
            mitte = self._mitte_von(flaechen)
            if mitte is None:
                continue
            lab = AIS_TextLabel()
            lab.SetFont(SCHRIFT)
            lab.SetText(TCollection_ExtendedString(f" {name} ({stelle}.) ", True))
            lab.SetPosition(gp_Pnt(*mitte))
            # weisse Schrift auf Feld in Bezugsfarbe: lesbar auch auf der gleichfarbigen Flaeche
            from OCC.Core.Aspect import Aspect_TODT_SUBTITLE
            lab.SetDisplayType(Aspect_TODT_SUBTITLE)
            lab.SetColorSubTitle(_farbe(tuple(c * 0.8 for c in BEZUG_FARBEN.get(stelle, BEZUG_FARBEN[3]))))
            lab.SetColor(_farbe((1.0, 1.0, 1.0)))
            lab.SetHeight(18)
            lab.SetZLayer(Graphic3d_ZLayerId_Topmost)
            ctx.Display(lab, False)
            ctx.Deactivate(lab)
            self._bezug_ais.append(lab)
        self._neu_zeichnen()

    def aktuelle_ansicht(self, name):
        a = super().aktuelle_ansicht(name)
        if not self._bereit:
            return a
        cam = self.d.View.Camera()
        e, d, u = cam.Eye(), cam.Direction(), cam.Up()
        a.ort, a.richtung, a.oben = (e.X(), e.Y(), e.Z()), (d.X(), d.Y(), d.Z()), (u.X(), u.Y(), u.Z())
        b, h = max(self.viewer.width(), 1), max(self.viewer.height(), 1)
        a.hoehe, a.breite, a.abstand = cam.Scale(), cam.Scale() * b / h, cam.Distance()
        return a

    def oben_richtung(self):
        if not self._bereit:
            return super().oben_richtung()
        u = self.d.View.Camera().Up()
        return (u.X(), u.Y(), u.Z())

    def blick_zum_betrachter(self):
        if not self._bereit:
            return super().blick_zum_betrachter()
        d = self.d.View.Camera().Direction()
        return (-d.X(), -d.Y(), -d.Z())

    def setze_explosion(self, anteil):
        super().setze_explosion(anteil)
        if not self._bereit or self.szene is None:
            return
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.gp import gp_Trsf, gp_Vec
        mitten, alle = {}, Bnd_Box()
        for nr, ais in self._teile.items():
            box = Bnd_Box()
            brepbndlib.Add(ais.Shape(), box)
            if box.IsVoid():
                continue
            x0, y0, z0, x1, y1, z1 = box.Get()
            mitten[nr] = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
            alle.Add(box)
        if alle.IsVoid():
            return
        x0, y0, z0, x1, y1, z1 = alle.Get()
        c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        ctx = self.d.Context
        for nr, ais in self._teile.items():
            t = gp_Trsf()
            if nr in mitten and self.explosion > 0:
                m = mitten[nr]
                t.SetTranslation(gp_Vec(*((m[i] - c[i]) * 1.6 * self.explosion for i in range(3))))
            if self.vergleich_trsf is not None:
                t = t.Multiplied(self.vergleich_trsf)
            for a in (ais, self._kanten.get(nr)):
                if a is not None:
                    a.SetLocalTransformation(t)
                    ctx.Redisplay(a, False)
        self._wende_sichtbarkeit_an()

    def zeige_ballone(self, ballone):
        super().zeige_ballone(ballone)
        if not self._bereit:
            return
        from OCC.Core.AIS import AIS_TextLabel
        from OCC.Core.Aspect import Aspect_TODT_SUBTITLE
        from OCC.Core.Graphic3d import Graphic3d_ZLayerId_Topmost
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.TCollection import TCollection_ExtendedString
        ctx = self.d.Context
        for lab in getattr(self, "_ballon_ais", []):
            ctx.Remove(lab, False)
        self._ballon_ais = []
        for nummer, ort in self.ballone:
            lab = AIS_TextLabel()
            lab.SetFont(SCHRIFT)
            lab.SetText(TCollection_ExtendedString(f" {nummer} ", True))
            p = gp_Pnt(*ort)
            if self.vergleich_trsf is not None:
                p = p.Transformed(self.vergleich_trsf)
            lab.SetPosition(p)
            lab.SetDisplayType(Aspect_TODT_SUBTITLE)
            lab.SetColorSubTitle(_farbe((0.15, 0.40, 0.85)))
            lab.SetColor(_farbe((1.0, 1.0, 1.0)))
            lab.SetHeight(15)
            lab.SetZLayer(Graphic3d_ZLayerId_Topmost)
            ctx.Display(lab, False)
            ctx.Deactivate(lab)
            self._ballon_ais.append(lab)
        self._neu_zeichnen()

    def mitte_von(self, flaechen):
        return self._mitte_von(flaechen, lage=False) if self._bereit else None

    def _mitte_von(self, flaechen, lage: bool = True):
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GProp import GProp_GProps
        p = GProp_GProps()
        n = 0
        for idx in flaechen:
            for _ais, f in self._flaechen_ais.get(idx, [])[:1]:
                brepgprop.SurfaceProperties(f, p)
                n += 1
        if not n:
            return None
        c = p.CentreOfMass()
        if lage and self.vergleich_trsf is not None:
            c = c.Transformed(self.vergleich_trsf)
        return (c.X(), c.Y(), c.Z())

    def hebe_pmi(self, ids):
        super().hebe_pmi(ids)
        self._wende_sichtbarkeit_an()

    def setze_grafik(self, an, nur_auswahl=False):
        super().setze_grafik(an, nur_auswahl)
        self._wende_sichtbarkeit_an()

    def setze_hilfsgeometrie(self, an):
        super().setze_hilfsgeometrie(an)
        self._wende_sichtbarkeit_an()

    def knoten_sichtbar(self, nummern, sichtbar):
        super().knoten_sichtbar(nummern, sichtbar)
        self._wende_sichtbarkeit_an()

    def isoliere(self, nummern):
        super().isoliere(nummern)
        self._wende_sichtbarkeit_an()
        self.alles_zeigen()

    def knoten_transparent(self, nummern, an):
        super().knoten_transparent(nummern, an)
        self._wende_sichtbarkeit_an()

    # --- Darstellung ---

    def darstellung(self, modus):
        super().darstellung(modus)
        self._wende_darstellung_an()

    def _wende_darstellung_an(self):
        if not self._bereit:
            return
        ctx = self.d.Context
        for ais in self._teile.values():
            ctx.SetDisplayMode(ais, 0 if self.modus == "draht" else 1, False)
        self._wende_sichtbarkeit_an()
        self._aktiviere_auswahl()

    # --- Kamera ---

    def standard(self, name):
        super().standard(name)
        if not self._bereit:
            return
        from OCC.Core import V3d
        richtung = {"vorne": V3d.V3d_Yneg, "hinten": V3d.V3d_Ypos, "oben": V3d.V3d_Zpos,
                    "unten": V3d.V3d_Zneg, "links": V3d.V3d_Xneg, "rechts": V3d.V3d_Xpos,
                    "iso": V3d.V3d_XposYnegZpos}[name]
        self.d.View.SetProj(richtung)
        self.alles_zeigen()
        self._kamera_bewegt()

    def _sichtbare_box(self):
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.TopLoc import TopLoc_Location
        box = Bnd_Box()
        for nr, ais in self._teile.items():
            if nr not in self.versteckt:
                # angezeigte Lage: Vergleichsausrichtung und Explosion stecken in der lokalen Transformation
                lage = TopLoc_Location(ais.LocalTransformation()) if ais.HasTransformation() else None
                brepbndlib.Add(ais.Shape().Moved(lage) if lage is not None else ais.Shape(), box)
        return box

    def alles_zeigen(self):
        """Auf die sichtbaren Teile einpassen (PMI-Beschriftungen ragen oft weit hinaus)."""
        if not self._bereit:
            return
        if self._drehpunkt is not None:
            self.drehpunkt_zuruecksetzen(melden=False)  # neuer Ausschnitt: Drehen wieder um die Bildmitte
        box = self._sichtbare_box()
        if box.IsVoid():
            self.d.View.FitAll(0.05, False)
        else:
            self.d.View.FitAll(box, 0.08, False)
        self.d.View.ZFitAll()
        self._neu_zeichnen()
        self._kamera_bewegt()

    def kamera(self, ansicht):
        super().kamera(ansicht)
        if not self._bereit:
            return
        from OCC.Core.gp import gp_Dir, gp_Pnt
        v = self.d.View
        if ansicht.breite <= 0:
            v.SetProj(*(-c for c in ansicht.richtung))
            v.SetUp(*ansicht.oben)
            self.alles_zeigen()
            return
        # Kamera wie in der Datei: Ort, Blickrichtung, oben und Fenstergroesse
        cam = v.Camera()
        o, r = ansicht.ort, ansicht.richtung
        tiefe = ansicht.abstand if ansicht.abstand > 0 else 1000.0
        cam.SetEye(gp_Pnt(*o))
        cam.SetCenter(gp_Pnt(o[0] + r[0] * tiefe, o[1] + r[1] * tiefe, o[2] + r[2] * tiefe))
        cam.SetUp(gp_Dir(*ansicht.oben))
        breite, hoehe = self.viewer.width() or 1, self.viewer.height() or 1
        cam.SetScale(max(ansicht.hoehe or ansicht.breite, (ansicht.breite or ansicht.hoehe) * hoehe / breite))
        v.ZFitAll()
        self._neu_zeichnen()
        self._kamera_bewegt()

    def drehpunkt_zuruecksetzen(self, melden: bool = True):
        self._drehpunkt = None
        if self._bereit:
            self._zeige_drehpunkt()
        if melden:
            self.meldung.emit(tr("Drehpunkt: Mitte des Modells"))

    def _mitte(self):
        from OCC.Core.gp import gp_Pnt
        if self._drehpunkt is not None:
            return self._drehpunkt
        if self.navigation == "catia":
            return self.d.View.Camera().Center()
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        box = Bnd_Box()
        for nr, ais in self._teile.items():
            if nr not in self.versteckt:
                brepbndlib.Add(ais.Shape(), box)
        if box.IsVoid():
            return gp_Pnt(0, 0, 0)
        x0, y0, z0, x1, y1, z1 = box.Get()
        return gp_Pnt((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)

    # --- Kameraverlauf und Projektion ---

    def _kamera_jetzt(self) -> tuple:
        cam = self.d.View.Camera()
        e, c, u = cam.Eye(), cam.Center(), cam.Up()
        return (e.X(), e.Y(), e.Z()), (c.X(), c.Y(), c.Z()), (u.X(), u.Y(), u.Z()), cam.Scale()

    @staticmethod
    def _gleich(a, b) -> bool:
        if a is None or b is None:
            return False
        flach = [x for t in a[:3] for x in t] + [a[3]], [x for t in b[:3] for x in t] + [b[3]]
        return all(abs(x - y) <= 1e-6 * max(1.0, abs(x)) for x, y in zip(*flach))

    def _kamera_merken(self):
        if not self._bereit or self.szene is None:
            return
        jetzt = self._kamera_jetzt()
        if self._verlauf_pos >= 0 and self._gleich(self._verlauf[self._verlauf_pos], jetzt):
            return
        del self._verlauf[self._verlauf_pos + 1:]
        self._verlauf.append(jetzt)
        self._verlauf = self._verlauf[-50:]
        self._verlauf_pos = len(self._verlauf) - 1

    def _kamera_setzen(self, k):
        from OCC.Core.gp import gp_Dir, gp_Pnt
        cam = self.d.View.Camera()
        cam.SetEye(gp_Pnt(*k[0]))
        cam.SetCenter(gp_Pnt(*k[1]))
        cam.SetUp(gp_Dir(*k[2]))
        cam.SetScale(k[3])
        self.d.View.ZFitAll()
        self._verlauf_uhr.stop()
        self._kamera_bewegt(merken=False)
        self.d.View.Redraw()

    def kamera_zurueck(self) -> bool:
        if not self._bereit:
            return False
        self._verlauf_uhr.stop()
        self._kamera_merken()  # laufende Bewegung zuerst abschliessen
        if self._verlauf_pos <= 0:
            return False
        self._verlauf_pos -= 1
        self._kamera_setzen(self._verlauf[self._verlauf_pos])
        return True

    def kamera_vor(self) -> bool:
        if not self._bereit or self._verlauf_pos >= len(self._verlauf) - 1:
            return False
        self._verlauf_pos += 1
        self._kamera_setzen(self._verlauf[self._verlauf_pos])
        return True

    def setze_perspektive(self, an: bool):
        super().setze_perspektive(an)
        if not self._bereit:
            return
        from OCC.Core.Graphic3d import Graphic3d_Camera
        cam = self.d.View.Camera()
        cam.SetProjectionType(Graphic3d_Camera.Projection_Perspective if an else
                              Graphic3d_Camera.Projection_Orthographic)
        if an:
            cam.SetFOVy(30.0)
        self.d.View.ZFitAll()
        self.d.View.Redraw()

    def _kamera_bewegt(self, merken: bool = True):
        """Schnitt aus Blickrichtung folgt der Kamera; Kamera fuer Ansicht zurueck/vor merken."""
        if merken and self._bereit:
            self._verlauf_uhr.start()
        if self.schnitt_zustand is not None and self.schnitt_zustand[0] == "blick":
            self.schnitt_aus_blick()
            self.schnitt(*self.schnitt_zustand)

    def _drehe(self, dx, dy):
        from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Trsf
        cam = self.d.View.Camera()
        p = self._mitte_cache
        oben = cam.Up()
        blick = cam.Direction()
        seite = blick.Crossed(oben)
        t1, t2 = gp_Trsf(), gp_Trsf()
        t1.SetRotation(gp_Ax1(p, gp_Dir(oben.X(), oben.Y(), oben.Z())), -dx * 0.008)
        t2.SetRotation(gp_Ax1(p, gp_Dir(seite.X(), seite.Y(), seite.Z())), -dy * 0.008)
        t1.Multiply(t2)
        cam.Transform(t1)
        self._kamera_bewegt()
        self.d.View.Redraw()

    def _verschiebe(self, dx, dy):
        from OCC.Core.gp import gp_Trsf, gp_Vec
        v = self.d.View
        cam = v.Camera()
        massstab = v.Convert(1)  # Weltlaenge je Pixel
        oben = gp_Vec(cam.Up())
        seite = gp_Vec(cam.Direction()).Crossed(oben)
        verschiebung = seite.Multiplied(-dx * massstab).Added(oben.Multiplied(dy * massstab))
        t = gp_Trsf()
        t.SetTranslation(verschiebung)
        cam.Transform(t)
        self._kamera_bewegt()
        v.Redraw()

    def _zoome(self, faktor, x, y):
        from OCC.Core.gp import gp_Pnt, gp_Trsf, gp_Vec
        v = self.d.View
        cam = v.Camera()
        px, py, pz = v.ConvertWithProj(int(x), int(y))[:3]
        c = cam.Center()
        ziel = gp_Pnt(px, py, pz)
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(c, ziel).Multiplied(1 - 1 / faktor))
        cam.Transform(t)
        cam.SetScale(cam.Scale() / faktor)
        v.ZFitAll()
        self._kamera_bewegt()
        v.Redraw()

    # --- Schnitt ---

    def _entferne_schnitt(self):
        if self._clip is not None and self._bereit:
            self.d.View.RemoveClipPlane(self._clip)
        self._clip = None

    def _schnitt_normale(self, achse):
        """(Normale, Punkt auf der Ebene oder None) fuer Achse, Auswahl oder Blickrichtung."""
        import numpy as np
        if achse in ("x", "y", "z"):
            n = np.zeros(3)
            n["xyz".index(achse)] = 1.0
            return n, None
        if self.schnitt_eigen is None:
            return None, None
        return np.asarray(self.schnitt_eigen[1], float), np.asarray(self.schnitt_eigen[0], float)

    def _schnitt_bereich(self, n):
        """Bereich der Modellteile entlang der Normalen (min, max des Hüllquaders)."""
        import itertools
        import numpy as np
        box = self._sichtbare_box()
        if box.IsVoid():
            return None
        x0, y0, z0, x1, y1, z1 = box.Get()
        ecken = np.array(list(itertools.product((x0, x1), (y0, y1), (z0, z1))))
        werte = ecken @ n
        return float(werte.min()), float(werte.max()), ecken.mean(axis=0)

    def schnitt_anteil_von_punkt(self, achse) -> float | None:
        """Reglerstellung, bei der die Ebene durch den Auswahlpunkt geht."""
        n, p = self._schnitt_normale(achse)
        if n is None or p is None:
            return None
        bereich = self._schnitt_bereich(n)
        if bereich is None or bereich[1] - bereich[0] < 1e-9:
            return None
        return min(max((float(p @ n) - bereich[0]) / (bereich[1] - bereich[0]), 0.0), 1.0)

    def schnitt_aus_auswahl(self) -> bool:
        if not self._bereit or not self.auswahl3d:
            return False
        import numpy as np
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.TopAbs import TopAbs_FACE
        form = self.auswahl3d[-1]
        n = self._normale(form)
        if n is None:
            return False
        props = GProp_GProps()
        (brepgprop.SurfaceProperties if form.ShapeType() == TopAbs_FACE else brepgprop.LinearProperties)(form, props)
        c = props.CentreOfMass()
        if self.vergleich_trsf is not None:
            c = c.Transformed(self.vergleich_trsf)
            n = n.Transformed(self.vergleich_trsf)
        self.schnitt_eigen = (np.array([c.X(), c.Y(), c.Z()]), np.array([n.X(), n.Y(), n.Z()]))
        return True

    def schnitt_aus_blick(self) -> bool:
        if not self._bereit:
            return False
        import numpy as np
        cam = self.d.View.Camera()
        d, c = cam.Direction(), cam.Center()
        self.schnitt_eigen = (np.array([c.X(), c.Y(), c.Z()]), -np.array([d.X(), d.Y(), d.Z()]))
        return True

    def schnitt(self, achse, anteil=0.5, umgekehrt=False):
        super().schnitt(achse, anteil, umgekehrt)
        if not self._bereit:
            return
        from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
        from OCC.Core.Graphic3d import Graphic3d_ClipPlane
        self._entferne_schnitt()
        if achse is None or self.szene is None:
            self._neu_zeichnen()
            return
        n, _ = self._schnitt_normale(achse)
        bereich = self._schnitt_bereich(n) if n is not None else None
        if bereich is None:
            self._neu_zeichnen()
            return
        lo, hi, mitte = bereich
        abstand = lo + (hi - lo) * anteil
        pos = mitte + n * (abstand - float(mitte @ n))
        # weggeschnitten wird die Seite in Normalenrichtung (beim Blick: die Seite zum Betrachter)
        richtung = n if umgekehrt else -n
        ebene = Graphic3d_ClipPlane(gp_Pln(gp_Pnt(*map(float, pos)), gp_Dir(*map(float, richtung))))
        ebene.SetCapping(True)
        ebene.SetCappingColor(_farbe((self.thema or {}).get("schnitt", (1, 0.55, 0.1))))
        ebene.SetOn(True)
        self.d.View.AddClipPlane(ebene)
        self._clip = ebene
        self._neu_zeichnen()

    def bild(self, pfad):
        if not self._bereit:
            return False
        with self._ohne_wuerfel():
            self._neu_zeichnen()
            return bool(self.d.View.Dump(pfad))

    def bild_qimage(self):
        """Bildschirmabgriff der 3D-Ansicht in Geraeteaufloesung (Retina), sonst View.Dump."""
        import os
        import tempfile
        if not self._bereit:
            return QtGui.QImage()
        with self._ohne_wuerfel():
            self._neu_zeichnen()
            QtWidgets.QApplication.processEvents()
            oben_links = self.viewer.mapToGlobal(QtCore.QPoint(0, 0))
            bildschirm = self.viewer.screen()
            lokal = oben_links - bildschirm.geometry().topLeft()
            img = bildschirm.grabWindow(0, lokal.x(), lokal.y(), self.viewer.width(), self.viewer.height()).toImage()
            if not img.isNull() and img.width() > 10:
                return img
            pfad = os.path.join(tempfile.mkdtemp(), "ansicht.png")
            self.d.View.Dump(pfad)
            return QtGui.QImage(pfad)

    @contextlib.contextmanager
    def _ohne_wuerfel(self):
        """Ansichtswuerfel und Drehpunktkreuz fuer Bilder (Berichte) kurz ausblenden."""
        weg = [a for a in (getattr(self, "_wuerfel", None), getattr(self, "_drehpunkt_ais", None)) if a is not None]
        for a in weg:
            self.d.Context.Erase(a, False)
        try:
            yield
        finally:
            for a in weg:
                self.d.Context.Display(a, False)
                self.d.Context.Deactivate(a)
            if weg:
                self._neu_zeichnen()

    # --- Maus und Trackpad ---

    def _px(self, pos):
        # OCCT rechnet in logischen Punkten (Cocoa_Window), nicht in Geraetepixeln
        return int(pos.x()), int(pos.y())

    def setze_navigation(self, modus: str):
        super().setze_navigation(modus)
        self.nav = Navigation(modus)

    def setze_messmodus(self, an: bool):
        super().setze_messmodus(an)
        self._aktiviere_auswahl()

    def setze_pmi_kontrast(self, an: bool):
        super().setze_pmi_kontrast(an)
        self._wende_sichtbarkeit_an()

    def setze_farben(self, pmi_eigen, hintergrund):
        super().setze_farben(pmi_eigen, hintergrund)
        if self._bereit:
            self.setze_thema(self.thema)

    def _aktiviere_auswahl(self):
        if not self._bereit:
            return
        ctx = self.d.Context
        for nr, ais in self._teile.items():
            if nr in self.versteckt:
                continue
            ctx.Deactivate(ais)
            if self.modus == "draht":
                arten = (1, 2)  # Drahtmodell: Flaechen nicht waehlbar -> verdeckte Kanten durchklicken
            else:
                arten = (1, 2, 4) if self.messmodus else (2, 4)  # Punkte, Kanten, Flaechen
            for modus in arten:
                ctx.Activate(ais, modus, False)

    def fang_toleranz(self) -> float:
        return self.d.View.Convert(12) if self._bereit else 1.0

    def zeige_messungen(self, messungen):
        super().zeige_messungen(messungen)
        if not self._bereit:
            return
        from OCC.Core.AIS import AIS_Shape, AIS_TextLabel
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex
        from OCC.Core.Graphic3d import Graphic3d_ZLayerId_Topmost
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.TCollection import TCollection_ExtendedString
        ctx = self.d.Context
        for ais in getattr(self, "_mess_ais", []):
            ctx.Remove(ais, False)
        self._mess_ais = []
        farbe = _farbe((self.thema or {}).get("hervor", (1, 0.45, 0)))
        for m in self.messungen:
            pts = [gp_Pnt(*p) for p in m.punkte]
            formen = [BRepBuilderAPI_MakeVertex(p).Vertex() for p in pts]
            if len(pts) == 2 and pts[0].Distance(pts[1]) > 1e-9:
                formen.append(BRepBuilderAPI_MakeEdge(pts[0], pts[1]).Edge())
            for f in formen:
                a = AIS_Shape(f)
                a.SetColor(farbe)
                a.SetWidth(2.0)
                self._mess_ais.append(a)
            lab = AIS_TextLabel()
            lab.SetFont(SCHRIFT)
            mitte = pts[0] if len(pts) == 1 else gp_Pnt((pts[0].X() + pts[1].X()) / 2,
                                                      (pts[0].Y() + pts[1].Y()) / 2, (pts[0].Z() + pts[1].Z()) / 2)
            lab.SetPosition(mitte)
            lab.SetText(TCollection_ExtendedString(f"{m.nummer}: {m.text()}", True))
            lab.SetColor(farbe)
            lab.SetHeight(20)
            self._mess_ais.append(lab)
        for a in self._mess_ais:
            a.SetZLayer(Graphic3d_ZLayerId_Topmost)
            ctx.Display(a, False)
            ctx.Deactivate(a)
        self._neu_zeichnen()

    def eventFilter(self, obj, ev):
        if obj is not self.viewer or not self._bereit:
            return False
        typ = ev.type()
        E = QtCore.QEvent.Type
        if typ in (E.MouseButtonPress, E.MouseMove, E.MouseButtonRelease, E.MouseButtonDblClick):
            x, y = self._px(ev.position())
            if self._wuerfel_maus(typ, ev, x, y):
                return True
            knopf, knoepfe = int(ev.button().value), int(ev.buttons().value)
            umschalt = int(ev.modifiers().value)
            if typ == E.MouseButtonPress:
                if self.nav.start is None:
                    self._mitte_cache = self._mitte()
                befehle = self.nav.druecken(knopf, knoepfe, umschalt, x, y)
            elif typ == E.MouseMove:
                befehle = self.nav.bewegen(knoepfe, umschalt, x, y)
            elif typ == E.MouseButtonRelease:
                befehle = self.nav.loslassen(knopf, knoepfe, x, y)
                if not knoepfe and getattr(self, "_drehpunkt_ais", None) is not None:
                    self._zeige_drehpunkt(an=False)
            else:
                befehle = self.nav.doppelklick(knopf, x, y)
            for b in befehle:
                self._fuehre_aus(b)
            return True
        if typ == E.Wheel:
            return self._rad(ev)
        if typ == E.NativeGesture:
            return self._geste(ev)
        if typ == E.Resize:
            self.d.View.MustBeResized()
            return False
        if typ == E.Paint:
            self._neu_zeichnen()
            return True
        return False

    def _fuehre_aus(self, befehl):
        art, *werte = befehl
        if art in ("drehen", "schieben") and getattr(self, "_drehpunkt_ais", None) is None:
            self._zeige_drehpunkt(an=True)  # Kreuz zeigt, um welchen Punkt gedreht wird
        if art == "drehen":
            self._drehe(*werte)
        elif art == "schieben":
            self._verschiebe(*werte)
        elif art == "zoomen":
            self._zoome(*werte)
        elif art == "klick":
            self._klick(*werte)
        elif art == "zentrieren":
            self._zentriere(*werte)
        elif art == "drehpunkt":
            self._setze_drehpunkt(*werte)
        elif art == "hover":
            self._wuerfel_unter_maus(werte[0], werte[1], zeichnen=True)  # hebt Wuerfel oder Modell hervor
        elif art == "kontext":
            self.kontextmenue.emit(self.viewer.mapToGlobal(QtCore.QPoint(int(werte[0]), int(werte[1]))))

    def _zentriere(self, x, y):
        """CATIA: Punkt unter der Maus wird Bildmitte (und Drehzentrum)."""
        from OCC.Core.gp import gp_Trsf, gp_Vec
        p = self._punkt_unter_maus(x, y)
        if p is None:
            return
        cam = self.d.View.Camera()
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(cam.Center(), p))
        cam.Transform(t)
        # Punkt bleibt Drehpunkt, auch wenn danach gezoomt oder verschoben wird
        self._drehpunkt = p
        self._zeige_drehpunkt()
        self.d.View.Redraw()
        self.meldung.emit(tr("Bildmitte und Drehpunkt versetzt"))

    def _rad(self, ev):
        x, y = self._px(ev.position())
        pixel = ev.pixelDelta()
        trackpad = not pixel.isNull() and ev.phase() != QtCore.Qt.ScrollPhase.NoScrollPhase
        if trackpad:
            r = 1.0
            # Zwei Finger: Modell folgt den Fingern wie beim Ziehen mit der Maus (macOS liefert die Richtung
            # schon passend zum "natuerlichen" Scrollen)
            if ev.modifiers() & QtCore.Qt.KeyboardModifier.AltModifier:
                self._mitte_cache = self._mitte()
                self._drehe(pixel.x() * r, pixel.y() * r)
            else:
                self._verschiebe(pixel.x() * r, pixel.y() * r)
        else:
            for b in self.nav.rad(ev.angleDelta().y() / 120.0, x, y):
                self._fuehre_aus(b)
        return True

    def _geste(self, ev):
        if ev.gestureType() == QtCore.Qt.NativeGestureType.ZoomNativeGesture:
            x, y = self._px(ev.position())
            self._zoome(1.0 + ev.value(), x, y)
            return True
        return False

    def _klick(self, x, y):
        ctx = self.d.Context
        if self.abweichung is not None and not self.messmodus:
            treffer = self.abweichung_bei(x, y)
            if treffer is not None:
                p, w = treffer
                sk = self.abweichung[3]
                self.meldung.emit(tr("{} {} bei ({:.2f}, {:.2f}, {:.2f})").format(tr(sk.name), sk.wert_text(w), *p))
                return
        ctx.MoveTo(x, y, self.d.View, False)
        if not ctx.HasDetected():
            if not QtWidgets.QApplication.keyboardModifiers():
                self.setze_auswahl([])
            self.flaeche_gewaehlt.emit(-1)
            return
        obj = ctx.DetectedInteractive()
        cid = next((c for a, c in self._ais_callout.items() if a == obj), None)
        if cid is not None:
            self.pmi_gewaehlt.emit(set(self.szene.grafik[cid].pmi_ids))
            return
        if self.ausricht_alt is not None and ctx.HasDetectedShape():
            form = ctx.DetectedShape()
            seite = "alt" if obj == getattr(self, "_alt_ais", None) else "neu"
            if seite == "neu" and self.vergleich_trsf is not None:
                from OCC.Core.TopLoc import TopLoc_Location
                form = form.Moved(TopLoc_Location(self.vergleich_trsf))
            p = self._punkt_unter_maus(x, y, form)
            if p is not None:
                self.ausricht_punkt.emit(seite, form, (p.X(), p.Y(), p.Z()))
            return
        if ctx.HasDetectedShape():
            form = ctx.DetectedShape()
            if self.vergleich_trsf is not None:
                # im Vergleich ist der neue Stand ins System des alten verschoben: Form wie angezeigt verwenden
                from OCC.Core.TopLoc import TopLoc_Location
                form = form.Moved(TopLoc_Location(self.vergleich_trsf))
            if self.messmodus and self.explosion > 0:
                self.meldung.emit(tr("In der Explosionsansicht wird nicht gemessen – erst zurücksetzen"))
                return
            if self.messmodus:
                p = self._punkt_unter_maus(x, y, form)
                if p is not None:
                    self.element_gewaehlt.emit(form, (p.X(), p.Y(), p.Z()))
                return
            mehr = bool(QtWidgets.QApplication.keyboardModifiers() &
                        (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.ShiftModifier |
                         QtCore.Qt.KeyboardModifier.MetaModifier))
            self._waehle_3d(form, mehr)
            idx = self.szene.modell.flaechen_index(form)
            self.flaeche_gewaehlt.emit(-1 if idx is None else idx)

    # --- 3D-Auswahl ---

    def _waehle_3d(self, form, ergaenzen: bool):
        gleich = [f for f in self.auswahl3d if f.IsSame(form)]
        if ergaenzen:
            neu = [f for f in self.auswahl3d if not f.IsSame(form)] if gleich else self.auswahl3d + [form]
        else:
            neu = [form]
        self.setze_auswahl(neu)

    def setze_auswahl(self, formen):
        super().setze_auswahl(formen)
        if not self._bereit:
            return
        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.Graphic3d import Graphic3d_ZLayerId_Topmost
        from OCC.Core.TopAbs import TopAbs_EDGE
        from OCC.Core.TopoDS import TopoDS_Compound
        ctx = self.d.Context
        if getattr(self, "_auswahl_ais", None) is not None:
            ctx.Remove(self._auswahl_ais, False)
            self._auswahl_ais = None
        kanten = [f for f in self.auswahl3d if f.ShapeType() == TopAbs_EDGE]
        flaechen = {self.szene.modell.flaechen_index(f) for f in self.auswahl3d if f.ShapeType() != TopAbs_EDGE}
        self.hebe_flaechen({i for i in flaechen if i is not None})
        if kanten:
            bb, comp = BRep_Builder(), TopoDS_Compound()
            bb.MakeCompound(comp)
            for k in kanten:
                bb.Add(comp, k)
            ais = AIS_Shape(comp)
            ais.SetColor(_farbe((self.thema or {}).get("hervor", (1, 0.45, 0))))
            ais.SetWidth(4.0)
            ais.SetZLayer(Graphic3d_ZLayerId_Topmost)
            if self.vergleich_trsf is not None:
                ais.SetLocalTransformation(self.vergleich_trsf)
            ctx.Display(ais, 0, -1, False)
            ctx.Deactivate(ais)
            self._auswahl_ais = ais
        self._neu_zeichnen()

    def _auswahl_formen(self, flaechen, formen=None, pmi_ids=None):
        """Formen (in Anzeigekoordinaten) fuer Zoom/Ausrichten: Flaechen, weitere Formen, PMI-Grafik."""
        from OCC.Core.TopLoc import TopLoc_Location
        lage = TopLoc_Location(self.vergleich_trsf) if self.vergleich_trsf is not None else None
        out = []
        for idx in flaechen:
            for _ais, f in self._flaechen_ais.get(idx, [])[:1]:
                out.append(f.Moved(lage) if lage is not None else f)
        out += list(formen or [])
        for cid, liste in self._callouts.items():
            if pmi_ids and self.szene.grafik[cid].pmi_ids & set(pmi_ids):
                for ais in liste:
                    if hasattr(ais, "Shape"):
                        out.append(ais.Shape())
        return out

    def _pmi_punkte(self, pmi_ids):
        import numpy as np
        pts = []
        for g in self.szene.grafik.values():
            if pmi_ids and g.pmi_ids & set(pmi_ids):
                pts += [l for l in g.linien] + [p for p, _ in g.dreiecke]
                pts += [np.array([ph.ursprung]) for ph in g.platzhalter]
        return np.vstack(pts) if pts else None

    def zoome_auf(self, flaechen, formen=None, pmi_ids=None):
        AnsichtBasis.zoome_auf(self, flaechen, formen, pmi_ids)
        if not self._bereit:
            return
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        box = Bnd_Box()
        for f in self._auswahl_formen(flaechen, formen, pmi_ids):
            brepbndlib.Add(f, box)
        if box.IsVoid():
            return
        x0, y0, z0, x1, y1, z1 = box.Get()
        gesamt = self._sichtbare_box()
        g = 0.0
        if not gesamt.IsVoid():
            gx0, gy0, gz0, gx1, gy1, gz1 = gesamt.Get()
            g = max(gx1 - gx0, gy1 - gy0, gz1 - gz0)
        box.Enlarge(max(max(x1 - x0, y1 - y0, z1 - z0) * 0.6, 0.15 * g, 1.0))
        self.d.View.FitAll(box, 0.05, False)
        self.d.View.ZFitAll()
        self._neu_zeichnen()

    def _normale(self, form):
        """Aeussere Normale in der Flaechenmitte, Achse eines Kreises, Richtung einer Geraden (gp_Dir) oder None."""
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.BRepGProp import BRepGProp_Face
        from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Line
        from OCC.Core.gp import gp_Dir, gp_Pnt, gp_Vec
        from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
        from OCC.Core.TopoDS import topods
        if form.ShapeType() == TopAbs_FACE:
            f = topods.Face(form)
            prop = BRepGProp_Face(f)
            u0, u1, v0, v1 = prop.Bounds()
            p, n = gp_Pnt(), gp_Vec()
            prop.Normal((u0 + u1) / 2, (v0 + v1) / 2, p, n)
            return gp_Dir(n) if n.Magnitude() > 1e-12 else None
        if form.ShapeType() == TopAbs_EDGE:
            c = BRepAdaptor_Curve(topods.Edge(form))
            if c.GetType() == GeomAbs_Circle:
                return c.Circle().Axis().Direction()
            if c.GetType() == GeomAbs_Line:
                return c.Line().Direction()
        return None

    def _pmi_ebene(self, pmi_ids):
        for g in self.szene.grafik.values():
            if g.ebene is not None and g.pmi_ids & set(pmi_ids):
                return g.ebene
        return None

    def _gerade(self, oben, n, formen, pts):
        """Hochachse auf eine Kantenrichtung der Auswahl (bzw. Hauptachse der Beschriftung) einrasten,
        damit Kanten waagrecht/senkrecht liegen."""
        import numpy as np
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.GeomAbs import GeomAbs_Line
        from OCC.Core.TopAbs import TopAbs_EDGE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopoDS import topods
        kandidaten = []
        for f in formen:
            ex = TopExp_Explorer(f, TopAbs_EDGE)
            while ex.More():
                c = BRepAdaptor_Curve(topods.Edge(ex.Current()))
                if c.GetType() == GeomAbs_Line:
                    d = c.Line().Direction()
                    kandidaten.append(np.array([d.X(), d.Y(), d.Z()]))
                ex.Next()
        if not kandidaten and pts is not None and len(pts) >= 3:
            _, _, vt = np.linalg.svd(pts - pts.mean(axis=0))
            kandidaten.append(vt[0])  # Schreibrichtung (laengste Ausdehnung)
        richtungen = []
        for d in kandidaten:
            d = d - n * (d @ n)
            if np.linalg.norm(d) > 1e-6:
                d = d / np.linalg.norm(d)
                richtungen += [d, np.cross(n, d)]
        if not richtungen:
            return oben
        o = oben - n * (oben @ n)
        o = o / (np.linalg.norm(o) or 1.0)
        beste = max(richtungen, key=lambda d: abs(d @ o))
        return beste if beste @ o >= 0 else -beste

    def richte_normal_aus(self, flaechen, formen=None, pmi_ids=None):
        AnsichtBasis.richte_normal_aus(self, flaechen, formen, pmi_ids)
        if not self._bereit:
            return
        import numpy as np
        normalen = []
        for f in self._auswahl_formen(flaechen, formen, None):
            n = self._normale(f)
            if n is not None:
                normalen.append(np.array([n.X(), n.Y(), n.Z()]))
        pts = self._pmi_punkte(pmi_ids) if pmi_ids else None
        ebene = self._pmi_ebene(pmi_ids) if pmi_ids else None
        if ebene is not None and not normalen:
            # Schreibebene der Beschriftung aus der Datei: Blick auf +z, x nach rechts, y nach oben -> lesbar
            _o, ex, ey, ez = ebene
            self.d.View.SetProj(*map(float, ez))
            self.d.View.SetUp(*map(float, ey))
            self.zoome_auf(flaechen, formen, pmi_ids)
            return
        if pts is not None and len(pts) >= 3:
            mitte = pts.mean(axis=0)
            _, _, vt = np.linalg.svd(pts - mitte)
            normalen.append(vt[2])  # Ebene der Beschriftung
        if not normalen:
            self.meldung.emit(tr("Keine Fläche oder Beschriftung zum Ausrichten gewählt"))
            return
        cam = self.d.View.Camera()
        zum_auge = -np.array([cam.Direction().X(), cam.Direction().Y(), cam.Direction().Z()])
        # Mittel der Normalen (Flaechen: aeussere Normale); Beschriftungsebene zum Betrachter hin
        n = np.sum(normalen, axis=0)
        if pts is not None and n @ zum_auge < 0:
            n = -n
        if np.linalg.norm(n) < 1e-9:
            n = normalen[0]
        n = n / np.linalg.norm(n)
        oben = np.array([cam.Up().X(), cam.Up().Y(), cam.Up().Z()])
        oben = self._gerade(oben, n, self._auswahl_formen(flaechen, formen, None), pts)
        oben = oben - n * (oben @ n)
        if np.linalg.norm(oben) < 1e-6:
            oben = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
            oben = oben - n * (oben @ n)
        self.d.View.SetProj(*map(float, n))
        self.d.View.SetUp(*map(float, oben / np.linalg.norm(oben)))
        self.zoome_auf(flaechen, formen, pmi_ids)

    def _punkt_unter_maus(self, x, y, form=None):
        """3D-Punkt auf dem Element unter der Maus (Sichtstrahl geschnitten mit dem Element)."""
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
        from OCC.Core.gp import gp_Dir, gp_Lin, gp_Pnt
        from OCC.Core.IntCurvesFace import IntCurvesFace_ShapeIntersector
        from OCC.Core.TopAbs import TopAbs_FACE
        x, y = int(x), int(y)
        if form is None:
            ctx = self.d.Context
            ctx.MoveTo(x, y, self.d.View, False)
            if not ctx.HasDetectedShape():
                return None
            form = ctx.DetectedShape()
        px, py, pz, vx, vy, vz = self.d.View.ConvertWithProj(int(x), int(y))
        strahl = gp_Lin(gp_Pnt(px, py, pz), gp_Dir(vx, vy, vz))
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopoDS import topods
        if form.ShapeType() == TopAbs_FACE and BRep_Tool.Surface(topods.Face(form)) is None:
            return _netz_treffer(form, (px, py, pz), (vx, vy, vz))  # Netzflaeche (STL, OBJ ...)
        if form.ShapeType() == TopAbs_FACE:
            schnitt = IntCurvesFace_ShapeIntersector()
            schnitt.Load(form, 1e-6)
            schnitt.Perform(strahl, -1e9, 1e9)
            if schnitt.IsDone() and schnitt.NbPnt() > 0:
                return schnitt.Pnt(min(range(1, schnitt.NbPnt() + 1), key=schnitt.WParameter))
        kante = BRepBuilderAPI_MakeEdge(strahl, -1e7, 1e7).Edge()
        ext = BRepExtrema_DistShapeShape(kante, form)
        ext.Perform()
        return ext.PointOnShape2(1) if ext.IsDone() and ext.NbSolution() > 0 else None

    def _zeige_drehpunkt(self, an: bool = False):
        """Drehpunkt als kleines Linienkreuz in X, Y, Z (feste Groesse in Pixeln) – nur waehrend Drehen/Schieben."""
        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCC.Core.Graphic3d import Graphic3d_TMF_ZoomPers, Graphic3d_TransformPers, Graphic3d_ZLayerId_Topmost
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.TopoDS import TopoDS_Compound
        ctx = self.d.Context
        if getattr(self, "_drehpunkt_ais", None) is not None:
            ctx.Remove(self._drehpunkt_ais, False)
            self._drehpunkt_ais = None
        punkt = self._mitte_cache if getattr(self, "_mitte_cache", None) is not None else self._drehpunkt
        if not an or punkt is None:
            self._neu_zeichnen()
            return
        k = max(1.0, self.viewer.devicePixelRatioF()) if sys.platform == "darwin" else 1.0
        l = 11.0 * k  # halbe Armlaenge in Pixeln (Zoom-Persistenz: Einheiten = Pixel)
        kreuz = TopoDS_Compound()
        bb = BRep_Builder()
        bb.MakeCompound(kreuz)
        for d in ((l, 0, 0), (0, l, 0), (0, 0, l)):
            bb.Add(kreuz, BRepBuilderAPI_MakeEdge(gp_Pnt(-d[0], -d[1], -d[2]), gp_Pnt(*d)).Edge())
        ais = AIS_Shape(kreuz)
        ais.SetColor(_farbe((self.thema or {}).get("hervor", (1.0, 0.45, 0.0))))
        ais.SetWidth(2.0 * k)
        ais.SetTransformPersistence(Graphic3d_TransformPers(Graphic3d_TMF_ZoomPers, punkt))
        ais.SetZLayer(Graphic3d_ZLayerId_Topmost)
        ctx.Display(ais, 0, -1, False)
        ctx.Deactivate(ais)
        self._drehpunkt_ais = ais
        self._neu_zeichnen()

    def _setze_drehpunkt(self, x, y):
        p = self._punkt_unter_maus(x, y)
        if p is not None:
            self._drehpunkt = p
            self._zeige_drehpunkt()
            self.meldung.emit(tr("Drehpunkt gesetzt: {:.1f}, {:.1f}, {:.1f}").format(p.X(), p.Y(), p.Z()))
        else:
            self.drehpunkt_zuruecksetzen()


def _netz_treffer(flaeche, ursprung, richtung):
    """Erster Schnitt eines Strahls mit den Dreiecken einer Netzflaeche (gp_Pnt) oder None."""
    from OCC.Core.gp import gp_Pnt
    from ..kern.abweichung import Karte
    from ..kern.ausrichten import tesselliere
    pts, tri = tesselliere([flaeche])[0]
    if not len(tri):
        return None
    import numpy as np
    treffer = Karte([(pts, tri)], [np.zeros(len(pts))], 0.0).am_strahl(ursprung, richtung)
    return None if treffer is None else gp_Pnt(*map(float, treffer[0]))


def _kanten_von(form):
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import TopoDS_Compound
    bb = BRep_Builder()
    comp = TopoDS_Compound()
    bb.MakeCompound(comp)
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    while ex.More():
        bb.Add(comp, ex.Current())
        ex.Next()
    return comp


def _status_farbe(thema: dict, status: str):
    return thema.get({"geaendert": "v_geaendert", "neu": "v_neu", "entfernt": "v_entfernt"}.get(status, ""))


def _abgetoent(rgb, grund):
    """Dateifarbe leicht zur Grundfarbe ziehen (zu grelle Farben vermeiden)."""
    return tuple(0.8 * a + 0.2 * b for a, b in zip(rgb, grund))

