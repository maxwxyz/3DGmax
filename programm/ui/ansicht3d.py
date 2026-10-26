"""3D-Ansicht: OCCT-Viewer im Qt-Fenster mit Navigation wie in CAD-Programmen.

Maussteuerung siehe navigation.py (Standard: CATIA, wahlweise klassisch in den Einstellungen).
Trackpad (beide Modi): zwei Finger verschieben, Aufziehen zoomt, Wahltaste/Alt + zwei Finger dreht.
Linksklick waehlt Flaeche oder grafische PMI.

Ohne Grafik (Tests mit QT_QPA_PLATFORM=offscreen) wird PlatzhalterAnsicht verwendet: gleiche
Schnittstelle, merkt sich nur den Zustand.
"""

from __future__ import annotations

import os

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
        self.letzter_zoom = None
        self.letzte_ausrichtung = None
        self.auswahl3d: list = []  # gewaehlte Flaechen/Kanten (TopoDS)
        self.schnitt_eigen = None  # (punkt, normale) fuer Schnitt an Auswahl / aus Blickrichtung

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

    def hebe_pmi(self, ids: set[int]):
        self.pmi_ids_hervor = set(ids)

    def setze_grafik(self, an: bool):
        self.grafik_an = an

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
        self.vergleich_entfernt = list(entfernt_formen or [])
        self.vergleich_trsf = trsf

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

    def bild(self, pfad: str) -> bool:
        return False

    def bild_qimage(self) -> QtGui.QImage:
        """Aktuelle Ansicht als Bild (fuer Berichte)."""
        img = self.grab().toImage()
        return img

    def drehpunkt_zuruecksetzen(self):
        pass


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
        self.d.display_triedron()
        self._bereit = True
        self.viewer._inited = True
        self.setze_thema(self.thema)
        if self.szene is not None:
            self._baue_szene()

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
        self._baue_entfernt()
        self._baue_grafik()
        self._wende_darstellung_an()
        self._wende_sichtbarkeit_an()
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
        if self._bereit and self.szene is not None:
            self._baue_szene()

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
                ais.SetWidth(1.4)
                liste.append(ais)
            for ph, text in texte:
                lab = AIS_TextLabel()
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
            if nr in self.versteckt:
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
            zeigen = self.grafik_an and (self.pmi_ids_sichtbar is None or bool(g.pmi_ids & self.pmi_ids_sichtbar))
            hervor = bool(g.pmi_ids & self.pmi_ids_hervor)
            zeigen = zeigen or hervor
            for ais in liste:
                if zeigen:
                    ais.SetColor(hervor_farbe if hervor else normal)
                    ctx.Display(ais, False)
                    ctx.Redisplay(ais, False)
                else:
                    ctx.Erase(ais, False)
        self._neu_zeichnen()

    def _grundfarbe(self, idx):
        """Farbe einer Flaeche ohne Hervorhebung: Vergleichsstatus, sonst Dateifarbe, sonst None (Grundfarbe)."""
        t = self.thema or {}
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

    def hebe_pmi(self, ids):
        super().hebe_pmi(ids)
        self._wende_sichtbarkeit_an()

    def setze_grafik(self, an):
        super().setze_grafik(an)
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

    def _sichtbare_box(self):
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.TopLoc import TopLoc_Location
        box = Bnd_Box()
        lage = TopLoc_Location(self.vergleich_trsf) if self.vergleich_trsf is not None else None
        for nr, ais in self._teile.items():
            if nr not in self.versteckt:
                brepbndlib.Add(ais.Shape().Moved(lage) if lage is not None else ais.Shape(), box)
        return box

    def alles_zeigen(self):
        """Auf die sichtbaren Teile einpassen (PMI-Beschriftungen ragen oft weit hinaus)."""
        if not self._bereit:
            return
        box = self._sichtbare_box()
        if box.IsVoid():
            self.d.View.FitAll(0.05, False)
        else:
            self.d.View.FitAll(box, 0.08, False)
        self.d.View.ZFitAll()
        self._neu_zeichnen()

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

    def drehpunkt_zuruecksetzen(self):
        self._drehpunkt = None
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
        self._neu_zeichnen()
        return bool(self.d.View.Dump(pfad))

    def bild_qimage(self):
        """Bildschirmabgriff der 3D-Ansicht in Geraeteaufloesung (Retina), sonst View.Dump."""
        import os
        import tempfile
        if not self._bereit:
            return QtGui.QImage()
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
            for modus in ((1, 2, 4) if self.messmodus else (2, 4)):  # Punkte, Kanten, Flaechen
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
            self.d.Context.MoveTo(werte[0], werte[1], self.d.View, True)
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
        self.d.View.Redraw()
        self.meldung.emit(tr("Bildmitte versetzt"))

    def _rad(self, ev):
        x, y = self._px(ev.position())
        pixel = ev.pixelDelta()
        trackpad = not pixel.isNull() and ev.phase() != QtCore.Qt.ScrollPhase.NoScrollPhase
        if trackpad:
            r = 1.0
            if ev.modifiers() & QtCore.Qt.KeyboardModifier.AltModifier:
                self._mitte_cache = self._mitte()
                self._drehe(-pixel.x() * r, -pixel.y() * r)
            else:
                self._verschiebe(-pixel.x() * r, -pixel.y() * r)
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
        if ctx.HasDetectedShape():
            form = ctx.DetectedShape()
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

    def _setze_drehpunkt(self, x, y):
        p = self._punkt_unter_maus(x, y)
        if p is not None:
            self._drehpunkt = p
            self.meldung.emit(tr("Drehpunkt gesetzt: {:.1f}, {:.1f}, {:.1f}").format(p.X(), p.Y(), p.Z()))
        else:
            self.drehpunkt_zuruecksetzen()


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

