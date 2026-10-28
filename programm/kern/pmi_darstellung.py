"""Darstellung eigener PMI als AP242-Praesentation schreiben (PLAN §8.28, Stufe 3, ohne Qt).

CAD-Systeme zeigen semantische PMI ohne Praesentation schlecht oder gar nicht. Geschrieben wird die Grafik, die
3DGmax fuer die PMI erzeugt (kern.pmi_erzeugen: Rahmen, Hinweislinie, Masslinie, Pfeile, Texte), in der Form der
NIST-Dateien (CTC-01, FTC-10) - genau die Form, die unser Leser (kern.praesentation) und OCCT
(STEPCAFControl_Reader, GD&T-Modus) als Praesentation einer PMI erkennen (per Versuch geprueft):

  DRAUGHTING_CALLOUT -> TESSELLATED_ANNOTATION_OCCURRENCE (Stil: CURVE_STYLE mit Farbe)
    -> TESSELLATED_GEOMETRIC_SET -> TESSELLATED_CURVE_SET (Linien, Textumrisse)
                                 + COMPLEX_TRIANGULATED_SURFACE_SET (Pfeile, Bezugsdreieck, Textfuellung)
  ANNOTATION_PLANE (Schreibebene) mit dem Callout
  DRAUGHTING_MODEL je Teil (Darstellungskontext des Teils: Einheiten) mit Ebenen und Callouts
  DRAUGHTING_MODEL_ITEM_ASSOCIATION('PMI representation to presentation link', Semantik, Modell, Callout)
    - OCCT sucht die Verknuepfung genau ueber diesen Namen.

Texte stehen als Glyphen (Umriss als Linienzug und gefuellt als Dreiecke) in der Ebene, wie CATIA sie als Linien
schreibt; ein Platzhalter allein (ANNOTATION_PLACEHOLDER_OCCURRENCE) zeigt in anderen Systemen keinen Text.
Koordinaten im Teil (Baugruppe: Lage der Instanz herausgerechnet) und in der Laengeneinheit der Datei.
"""

from __future__ import annotations

import sys

import numpy as np

DMIA_NAME = "PMI representation to presentation link"
FARBE = (0.50, 0.28, 0.72)  # wie erzeugte PMI in der Ansicht: im CAD-System als von 3DGmax ergaenzt erkennbar
LINIENBREITE = 0.25  # mm
# Schrift mit den GD&T-Zeichen (⌀ ⌖ ⏥ ⟂ Ⓜ ...) je System; OCCT nimmt sonst eine Ersatzschrift
SCHRIFT = "Arial Unicode MS" if sys.platform == "darwin" else ("Segoe UI Symbol" if sys.platform == "win32"
                                                                else "DejaVu Sans")


def text_glyphen(text: str, ursprung, x, y, hoehe: float, schrift: str | None = None):
    """(Umrisse als Linienzuege, Dreiecke als (Punkte, Indizes)) der Glyphen eines Textes in der Ebene (mm).

    Lage wie die Glyphen der 3D-Ansicht: Grundlinie links unten im Ursprung, x Schreibrichtung, y nach oben."""
    from OCC.Core.Addons import Font_FA_Regular, text_to_brep
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    if not text.strip() or hoehe <= 0:
        return [], []
    try:
        form = text_to_brep(text, schrift or SCHRIFT, Font_FA_Regular, float(hoehe), True)
    except Exception:  # noqa: BLE001 - Schrift nicht ladbar: kein Text
        return [], []
    if form is None or form.IsNull():
        return [], []
    BRepMesh_IncrementalMesh(form, hoehe / 40, False, 0.3, False)
    x = np.asarray(x, float) / (np.linalg.norm(x) or 1.0)
    y = np.asarray(y, float) / (np.linalg.norm(y) or 1.0)
    o = np.asarray(ursprung, float)
    linien, dreiecke = _netz_und_umriss(form)
    abb = lambda p: o + p[:, :1] * x + p[:, 1:2] * y  # noqa: E731 - Glyphenebene (z = 0) in die Schreibebene
    return [abb(l) for l in linien], [(abb(p), i) for p, i in dreiecke]


def _netz_und_umriss(form):
    """Dreiecke je Flaeche und Kantenzuege auf dem Netz (Glyphen-Koordinaten)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    linien, dreiecke = [], []
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        if tri is None or tri.NbTriangles() == 0:
            continue
        t = loc.Transformation()
        pts = np.array([[*tri.Node(i).Transformed(t).Coord()] for i in range(1, tri.NbNodes() + 1)])
        dreiecke.append((pts, np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1))
        kx = TopExp_Explorer(f, TopAbs_EDGE)
        while kx.More():
            poly = BRep_Tool.PolygonOnTriangulation(topods.Edge(kx.Current()), tri, loc)
            kx.Next()
            if poly is not None:
                knoten = poly.Nodes()
                idx = [knoten.Value(i) - 1 for i in range(knoten.Lower(), knoten.Upper() + 1)]
                if len(idx) > 1:
                    linien.append(pts[idx])
    return linien, dreiecke


def gesamt(g, schrift: str | None = None):
    """Alle Linienzuege und Dreiecke einer Grafik, Texte der Platzhalter als Glyphen (Modellkoordinaten, mm)."""
    linien = [np.asarray(l, float) for l in g.linien if len(l) > 1]
    dreiecke = [(np.asarray(p, float), np.asarray(i, int)) for p, i in g.dreiecke]
    for ph in g.platzhalter:
        if ph.text:
            l, d = text_glyphen(ph.text, ph.ursprung, ph.x, ph.y, max(ph.hoehe, 0.1), schrift)
            linien += l
            dreiecke += d
    return linien, dreiecke


class _Teillage:
    """Modellkoordinaten (mm, Baugruppe zusammengebaut) -> Koordinaten im Teil in der Laengeneinheit der Datei."""

    def __init__(self, flaeche, faktor_mm: float):
        t = flaeche.Location().Transformation().Inverted()
        m = np.array([[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)])
        self.drehung, self.verschiebung, self.faktor = m[:, :3], m[:, 3], faktor_mm or 1.0

    def punkte(self, p) -> np.ndarray:
        return (np.asarray(p, float) @ self.drehung.T + self.verschiebung) / self.faktor

    def richtung(self, v) -> np.ndarray:
        r = np.asarray(v, float) @ self.drehung.T
        return r / (np.linalg.norm(r) or 1.0)


def _zahl(x: float) -> str:
    from .step_schreiben import _real
    return _real(round(float(x), 6) + 0.0)


class _Punkte:
    """Eine Punktliste je Callout fuer Linien und Dreiecke (gleiche Punkte einmal, Nummern ab 1)."""

    def __init__(self):
        self.liste: list[str] = []
        self.nummer: dict[str, int] = {}

    def nr(self, p) -> int:
        text = "(" + ",".join(_zahl(c) for c in p) + ")"
        if text not in self.nummer:
            self.liste.append(text)
            self.nummer[text] = len(self.liste)
        return self.nummer[text]


class Praesentation:
    """Callouts eigener PMI an einen _Anhang (step_schreiben) haengen; je Teil ein DRAUGHTING_MODEL."""

    def __init__(self, anhang, modell, schrift: str | None = None):
        self.a, self.modell, self.schrift = anhang, modell, schrift
        self.modelle: dict[int, list[int]] = {}  # Darstellungskontext -> Callouts und Ebenen
        self.dmia: list[tuple[int, int, int]] = []  # (Kontext, Semantik, Callout)
        self.dmia_fest: list[tuple[int, int, int]] = []  # (vorhandenes DRAUGHTING_MODEL, Semantik, Callout)
        self._stil = None

    def stil(self) -> int:
        """Ein Kurvenstil (Farbe, Strichstaerke) fuer alle Callouts."""
        if self._stil is None:
            from .pmi_step import einheit_mm
            from .p21 import Ref
            a = self.a
            farbe = a.neu("COLOUR_RGB(''," + ",".join(_zahl(c) for c in FARBE) + ")")
            schrift = a.neu("DRAUGHTING_PRE_DEFINED_CURVE_FONT('continuous')")
            breite = LINIENBREITE / (einheit_mm(a.datei, Ref(a.einheit_laenge)) or 1.0)
            kurve = a.neu(f"CURVE_STYLE('',#{schrift},POSITIVE_LENGTH_MEASURE({_zahl(breite)}),#{farbe})")
            self._stil = a.neu(f"PRESENTATION_STYLE_ASSIGNMENT((#{kurve}))")
        return self._stil

    def callout(self, g, semantik: int, flaechen) -> bool:
        """Grafik g als Callout im gewaehlten Teil (a.waehle vorher) schreiben, mit der Semantik verknuepfen."""
        from .pmi_step import einheit_mm
        from .p21 import Ref
        a = self.a
        idx = [i for i in sorted(flaechen) if i < len(self.modell.flaechen)]
        if g is None or not idx or a.kontext is None:
            return False
        lage = _Teillage(self.modell.flaechen[idx[0]], einheit_mm(a.datei, Ref(a.einheit_laenge)))
        linien, dreiecke = gesamt(g, self.schrift)
        if not linien and not dreiecke:
            return False
        punkte = _Punkte()
        strips = ["(" + ",".join(str(punkte.nr(q)) for q in lage.punkte(l)) + ")" for l in linien]
        faecher = []
        for p, i in dreiecke:
            q = lage.punkte(p)
            faecher += [n for n in ([punkte.nr(q[k]) for k in t] for t in i) if len(set(n)) == 3]  # ohne entartete
        faecher = ["(" + ",".join(map(str, t)) + ")" for t in faecher]
        koord = a.neu(f"COORDINATES_LIST('',{len(punkte.liste)},({','.join(punkte.liste)}))")
        teile = [a.neu(f"TESSELLATED_CURVE_SET('',#{koord},({','.join(strips)}))")] if strips else []
        if faecher:  # gefuellt; eine Normale: die der Schreibebene
            normale = lage.richtung(g.ebene[3]) if g.ebene is not None else np.array([0.0, 0.0, 1.0])
            teile.append(a.neu(f"COMPLEX_TRIANGULATED_SURFACE_SET('',#{koord},{len(punkte.liste)},"
                               f"(({','.join(map(_zahl, normale))})),(),(),({','.join(faecher)}))"))
        name = (g.name or "").replace("'", "''")
        menge = a.neu(f"TESSELLATED_GEOMETRIC_SET('',({','.join(f'#{t}' for t in teile)}))")
        occ = a.neu(f"TESSELLATED_ANNOTATION_OCCURRENCE('{name}',(#{self.stil()}),#{menge})")
        callout = a.neu(f"DRAUGHTING_CALLOUT('{name}',(#{occ}))")
        ebene = self._ebene(g, lage, callout, lage.punkte(np.vstack(linien or [p for p, _ in dreiecke])))
        self.modelle.setdefault(a.kontext, []).extend([ebene, callout])
        self.dmia.append((a.kontext, semantik, callout))
        return True

    def verknuepfe(self, callout: int, semantik: int) -> bool:
        """Vorhandenen Callout der Datei mit der Semantik verknuepfen (nur grafische PMI reparieren); Modell aus
        der Datei, sonst ein neues im gewaehlten Teil."""
        d = self.a.datei.entities.get(callout)
        if d is None or not d.is_a("DRAUGHTING_CALLOUT"):
            return False
        modell = _modell_von(self.a.datei, callout)
        if modell is not None:
            self.dmia_fest.append((modell, semantik, callout))
        elif self.a.kontext is not None:
            self.modelle.setdefault(self.a.kontext, []).append(callout)
            self.dmia.append((self.a.kontext, semantik, callout))
        else:
            return False
        return True

    def _ebene(self, g, lage, callout: int, pts) -> int:
        """ANNOTATION_PLANE: Schreibebene der Grafik (ohne Ebene: XY durch den ersten Punkt, pts im Teil)."""
        a = self.a
        if g.ebene is not None:
            o, x, _, n = g.ebene
            o, x, n = lage.punkte([o])[0], lage.richtung(x), lage.richtung(n)
        else:
            o, x, n = pts[0], np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])
        p = a.neu(f"CARTESIAN_POINT('',({','.join(map(_zahl, o))}))")
        dn = a.neu(f"DIRECTION('',({','.join(map(_zahl, n))}))")
        dx = a.neu(f"DIRECTION('',({','.join(map(_zahl, x))}))")
        ax = a.neu(f"AXIS2_PLACEMENT_3D('',#{p},#{dn},#{dx})")
        flaeche = a.neu(f"PLANE('',#{ax})")
        leer = a.neu("PRESENTATION_STYLE_ASSIGNMENT((NULL_STYLE(.NULL.)))")
        return a.neu(f"ANNOTATION_PLANE('',(#{leer}),#{flaeche},(#{callout}))")

    def abschliessen(self):
        """Je Teil ein DRAUGHTING_MODEL und die Verknuepfungen Semantik -> Callout."""
        a = self.a
        modell_id = {}
        for kontext, items in self.modelle.items():
            modell_id[kontext] = a.neu(f"DRAUGHTING_MODEL('',({','.join(f'#{i}' for i in items)}),#{kontext})")
        for kontext, semantik, callout in self.dmia:
            a.neu(f"DRAUGHTING_MODEL_ITEM_ASSOCIATION('{DMIA_NAME}','',#{semantik},#{modell_id[kontext]},#{callout})")
        for modell, semantik, callout in self.dmia_fest:
            a.neu(f"DRAUGHTING_MODEL_ITEM_ASSOCIATION('{DMIA_NAME}','',#{semantik},#{modell},#{callout})")


def _modell_von(datei, callout: int) -> int | None:
    """DRAUGHTING_MODEL der Datei, das den Callout enthaelt (direkt oder ueber seine ANNOTATION_PLANE)."""
    huellen = {callout} | {r for r in datei.referrers().get(callout, []) if datei.entities[r].is_a("ANNOTATION_PLANE")}
    for h in huellen:
        for r in datei.referrers().get(h, []):
            if datei.entities[r].is_a("DRAUGHTING_MODEL"):
                return r
    return None
