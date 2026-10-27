"""Grafische PMI (Presentation) aus AP242 lesen: Linienzuege, gefuellte Dreiecke, Textplatzhalter.

Struktur: DRAUGHTING_CALLOUT -> Annotationen
- TESSELLATED_ANNOTATION_OCCURRENCE -> TESSELLATED_GEOMETRIC_SET (ggf. REPOSITIONED) ->
  TESSELLATED_CURVE_SET (Linien) / COMPLEX_TRIANGULATED_SURFACE_SET (Flaechen, z. B. Pfeile, Schrift)
- ANNOTATION_CURVE_OCCURRENCE -> GEOMETRIC_CURVE_SET -> POLYLINE / CIRCLE
- ANNOTATION_PLACEHOLDER_OCCURRENCE[_WITH_LEADER_LINE] -> Platz fuer Text (Text erzeugt 3DGmax), Hinweislinie
Die Verknuepfung zur Semantik laeuft ueber DRAUGHTING_MODEL_ITEM_ASSOCIATION (Callout -> PMI-#ID).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .p21 import DMIA_PH, Entity, P21Datei, Ref

ANNOTATIONEN = ("TESSELLATED_ANNOTATION_OCCURRENCE", "ANNOTATION_CURVE_OCCURRENCE",
                "ANNOTATION_PLACEHOLDER_OCCURRENCE_WITH_LEADER_LINE", "ANNOTATION_PLACEHOLDER_OCCURRENCE",
                "ANNOTATION_OCCURRENCE")


@dataclass
class Platzhalter:
    """Rechteck fuer einen Text, den das Programm selbst schreibt."""
    ursprung: np.ndarray
    x: np.ndarray
    y: np.ndarray
    breite: float
    hoehe: float


@dataclass
class Grafik:
    """Grafik eines Callouts in Modellkoordinaten (mm)."""
    callout_id: int
    name: str = ""
    linien: list[np.ndarray] = field(default_factory=list)  # je (n, 3)
    dreiecke: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)  # (punkte, (m, 3) Indizes)
    platzhalter: list[Platzhalter] = field(default_factory=list)
    hinweislinien: list[np.ndarray] = field(default_factory=list)  # nur zu Platzhaltern
    fertig: bool = False  # Datei liefert fertige Grafik (tesselliert oder Kurven)
    doppelt: bool = False  # nur Platzhalter fuer PMI, die schon fertige Grafik haben
    farbe: tuple[float, float, float] | None = None  # Farbe laut Datei (RGB 0..1)
    ebene: tuple | None = None  # Schreibebene (ursprung, x, y, z) laut Datei, fuer lesbares Ausrichten
    erzeugt: bool = False  # von 3DGmax aus der Semantik erzeugt (nicht aus der Datei)
    pmi_ids: set[int] = field(default_factory=set)

    def leer(self) -> bool:
        return not (self.linien or self.dreiecke or self.platzhalter)

    def grenzen(self):
        pts = [l for l in self.linien] + [p for p, _ in self.dreiecke]
        if not pts:
            return None
        alle = np.vstack(pts)
        return alle.min(axis=0), alle.max(axis=0)


class _Leser:
    def __init__(self, datei: P21Datei, skala: float):
        self.d = datei
        self.skala = skala

    # --- Grundelemente ---

    def punkt(self, ref) -> np.ndarray:
        e = self.d.get(ref)
        return np.array(_eig(e, "CARTESIAN_POINT")[0], dtype=float) * self.skala

    def richtung(self, ref, ersatz) -> np.ndarray:
        e = self.d.get(ref) if isinstance(ref, Ref) else None
        if e is None:
            return np.array(ersatz, dtype=float)
        v = np.array(_eig(e, "DIRECTION")[0], dtype=float)
        return v / (np.linalg.norm(v) or 1.0)

    def platzierung(self, ref):
        """AXIS2_PLACEMENT_3D -> (ursprung, x, y, z)."""
        e = self.d.get(ref)
        ort, achse, refx = _eig(e, "AXIS2_PLACEMENT_3D")[:3]
        z = self.richtung(achse, (0, 0, 1))
        x = self.richtung(refx, (1, 0, 0))
        x = x - z * float(x @ z)
        x /= np.linalg.norm(x) or 1.0
        return self.punkt(ort), x, np.cross(z, x), z

    def koordinaten(self, ref) -> np.ndarray:
        e = self.d.get(ref)
        return np.array(_eig(e, "COORDINATES_LIST")[1], dtype=float) * self.skala

    # --- Geometrie ---

    def menge(self, ref, g: Grafik, trafo=None):
        e = self.d.get(ref)
        if e is None:
            return
        if e.is_a("REPOSITIONED_TESSELLATED_ITEM"):
            trafo = self.platzierung(e.args("REPOSITIONED_TESSELLATED_ITEM")[-1])
            if g.ebene is None:
                g.ebene = trafo
        if e.is_a("TESSELLATED_GEOMETRIC_SET"):
            for r in _eig(e, "TESSELLATED_GEOMETRIC_SET")[0]:
                self.element(r, g, trafo)
        elif e.is_a("GEOMETRIC_CURVE_SET") or e.is_a("GEOMETRIC_SET"):
            teil = "GEOMETRIC_CURVE_SET" if e.is_a("GEOMETRIC_CURVE_SET") else "GEOMETRIC_SET"
            for r in _eig(e, teil)[0]:
                self.element(r, g, trafo)
        else:
            self.element(ref, g, trafo)

    def element(self, ref, g: Grafik, trafo):
        e = self.d.get(ref)
        if e is None:
            return
        if e.is_a("TESSELLATED_CURVE_SET"):
            koord, strips = _eig(e, "TESSELLATED_CURVE_SET")[:2]
            pts = _trafo(self.koordinaten(koord), trafo)
            for strip in strips:
                g.linien.append(pts[np.array(strip, dtype=int) - 1])
        elif e.is_a("COMPLEX_TRIANGULATED_SURFACE_SET"):
            self.dreiecke(e, g, trafo)
        elif e.is_a("POLYLINE"):
            g.linien.append(_trafo(np.array([self.punkt(p) for p in _eig(e, "POLYLINE")[0]]), trafo))
        elif e.is_a("CIRCLE"):
            g.linien.append(_trafo(self.kreis(e), trafo))
        elif e.is_a("TRIMMED_CURVE"):
            self.element(_eig(e, "TRIMMED_CURVE")[0], g, trafo)

    def kreis(self, e: Entity, n: int = 48) -> np.ndarray:
        platz, radius = _eig(e, "CIRCLE")[:2]
        o, x, y, _ = self.platzierung(platz)
        r = float(radius) * self.skala
        w = np.linspace(0, 2 * math.pi, n)
        return o + r * (np.outer(np.cos(w), x) + np.outer(np.sin(w), y))

    def dreiecke(self, e: Entity, g: Grafik, trafo):
        args = _eig(e, "COMPLEX_TRIANGULATED_SURFACE_SET")
        pts = _trafo(self.koordinaten(args[0]), trafo)
        pnindex = args[3] or []
        idx = (lambda i: pnindex[i - 1] - 1) if pnindex else (lambda i: i - 1)
        tris = []
        for strip in args[4] or []:
            for k in range(len(strip) - 2):
                a, b, c = strip[k], strip[k + 1], strip[k + 2]
                tris.append((a, b, c) if k % 2 == 0 else (b, a, c))
        for fan in args[5] or []:
            for k in range(1, len(fan) - 1):
                tris.append((fan[0], fan[k], fan[k + 1]))
        tris = [t for t in tris if len(set(t)) == 3]
        if tris:
            g.dreiecke.append((pts, np.array([[idx(i) for i in t] for t in tris], dtype=int)))

    def platzhalter(self, e: Entity, g: Grafik, teil: str):
        args = e.args(teil)
        menge = self.d.get(args[2])
        for r in (_eig(menge, "GEOMETRIC_SET")[0] if menge is not None else []):
            box = self.d.get(r)
            if box is not None and box.is_a("PLANAR_BOX"):
                b, h, platz = _eig(box, "PLANAR_BOX")[:3]
                o, x, y, z = self.platzierung(platz)
                g.platzhalter.append(Platzhalter(o, x, y, float(b) * self.skala, float(h) * self.skala))
                if g.ebene is None:
                    g.ebene = (o, x, y, z)
        if teil.endswith("WITH_LEADER_LINE"):
            for r in args[5] or []:
                linie = self.d.get(r)
                if linie is None:
                    continue
                pts = [np.array(_eig(self.d.get(p), next(iter(self.d.get(p).parts)))[0], dtype=float) * self.skala
                       for p in _eig(linie, next(iter(linie.parts)))[0]]
                if len(pts) > 1:
                    g.hinweislinien.append(np.array(pts))

    def stilfarbe(self, ref, tiefe=0):
        """Erste Farbe in einem Darstellungsstil (Kurven- oder Flaechenstil)."""
        from .farben import VORDEFINIERT
        e = self.d.get(ref) if isinstance(ref, Ref) else None
        if e is None or tiefe > 8:
            return None
        if e.is_a("COLOUR_RGB"):
            return tuple(float(x) for x in e.args("COLOUR_RGB")[1:4])
        if e.is_a("DRAUGHTING_PRE_DEFINED_COLOUR"):
            return VORDEFINIERT.get(e.args("DRAUGHTING_PRE_DEFINED_COLOUR")[0])
        for werte in e.parts.values():
            for w in werte:
                for r in (w if isinstance(w, list) else [w]):
                    f = self.stilfarbe(r, tiefe + 1) if isinstance(r, Ref) else None
                    if f is not None:
                        return f
        return None

    def annotation(self, ref, g: Grafik):
        e = self.d.get(ref)
        if e is None:
            return
        teil = next((t for t in ANNOTATIONEN if e.is_a(t)), None)
        if teil is None:
            return
        if g.farbe is None:
            stile = e.args("STYLED_ITEM")[1] if e.is_a("STYLED_ITEM") else e.args(teil)[1]
            for st in stile or []:
                g.farbe = g.farbe or self.stilfarbe(st)
        if teil.startswith("ANNOTATION_PLACEHOLDER"):
            self.platzhalter(e, g, teil)
        else:
            item = e.args("STYLED_ITEM")[2] if e.is_a("STYLED_ITEM") else e.args(teil)[2]
            self.menge(item, g)
            g.fertig = True


def _eig(e: Entity, teil: str) -> list:
    """Eigene Attribute ohne den geerbten Namen (REPRESENTATION_ITEM.name).

    Einfache Entitaeten schreiben den Namen als erstes Attribut, komplexe in REPRESENTATION_ITEM.
    """
    args = e.args(teil)
    return args if len(e.parts) > 1 else args[1:]


def _trafo(pts: np.ndarray, trafo) -> np.ndarray:
    if trafo is None or len(pts) == 0:
        return pts
    o, x, y, z = trafo
    return o + pts[:, :1] * x + pts[:, 1:2] * y + pts[:, 2:3] * z


def lies_grafik(datei: P21Datei, skala: float = 1.0) -> dict[int, Grafik]:
    """Callout-ID -> Grafik (mit verknuepften PMI-#IDs)."""
    from .ansichten import _semantik_von
    leser = _Leser(datei, skala)
    out: dict[int, Grafik] = {}
    for c in datei.of_type("DRAUGHTING_CALLOUT"):
        name, teile = c.args("DRAUGHTING_CALLOUT")[:2]
        g = Grafik(c.id, name or "")
        for r in teile:
            leser.annotation(r, g)
        # Platzhalter nur, wenn es keine fertige Grafik gibt (NIST liefert oft beides)
        if g.fertig:
            g.platzhalter, g.hinweislinien = [], []
        else:
            g.linien += g.hinweislinien
        out[c.id] = g
    for d in datei.of_type("DRAUGHTING_MODEL_ITEM_ASSOCIATION") + datei.of_type(DMIA_PH):
        args = d.args(next(iter(d.parts)))
        if isinstance(args[2], Ref) and isinstance(args[4], Ref) and args[4].id in out:
            out[args[4].id].pmi_ids.add(_semantik_von(datei, args[2].id))
    mit_grafik = set().union(*(g.pmi_ids for g in out.values() if g.fertig)) if out else set()
    for g in out.values():
        g.doppelt = not g.fertig and bool(g.pmi_ids) and g.pmi_ids <= mit_grafik
    return out


def _ketten(linien: list[np.ndarray], eps: float = 1e-9) -> list[np.ndarray]:
    """Aufeinanderfolgende Linienstuecke mit gemeinsamem Endpunkt zu Linienzuegen verbinden."""
    out: list[list] = []
    for l in linien:
        if len(l) < 2:
            continue
        if out and np.abs(out[-1][-1] - l[0]).max() <= eps:
            out[-1].extend(l[1:])
        else:
            out.append(list(l))
    return [np.asarray(k) for k in out]


def prc_grafik(modell_prc) -> dict[int, Grafik]:
    """Markup-ID -> Grafik aus PRC (fertige Linien und Flaechen, Name des Markups)."""
    from . import prc
    out: dict[int, Grafik] = {}
    for m in prc.markup_grafik(modell_prc):
        g = Grafik(m.eid, m.name, linien=_ketten(m.linien), fertig=True, farbe=m.farbe)
        for d in m.dreiecke:
            if len(d) >= 3:
                n = len(d) // 3 * 3
                g.dreiecke.append((d[:n], np.arange(n).reshape(-1, 3)))
        out[m.eid] = g
    return out
