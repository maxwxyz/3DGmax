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

from .ansichten import darstellungskontext
from .p21 import DMIA_PH, Entity, P21Datei, Ref

ANNOTATIONEN = ("TESSELLATED_ANNOTATION_OCCURRENCE", "ANNOTATION_CURVE_OCCURRENCE", "ANNOTATION_TEXT_OCCURRENCE",
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
    text: str = ""  # eigener Text (erzeugte PMI: ein Feld des Rahmens); leer = Text der PMI


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
    markup: tuple | None = None  # PRC: (Markup-Art, Unterart) fuer nur grafische PMI
    kontext: int | None = None  # Darstellungskontext des DRAUGHTING_MODEL (Koordinatensystem des Teils)
    textfaktor: float | None = 1.0  # Laengeneinheit des Beschriftungstextes in mm

    def leer(self) -> bool:
        return not (self.linien or self.dreiecke or self.platzhalter)

    def grenzen(self):
        pts = [l for l in self.linien] + [p for p, _ in self.dreiecke]
        if not pts:
            for ph in self.platzhalter:
                o, b, h = ph.ursprung, ph.x * ph.breite, ph.y * ph.hoehe
                pts.append(np.array([o, o+b, o+h, o+b+h]))
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
        args = _eig(e, "AXIS2_PLACEMENT_3D")
        ort, achse, refx = (e.args("PLACEMENT") + args if e.is_a("PLACEMENT") else args)[:3]
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

    def textliteral(self, e: Entity, g: Grafik):
        """Lesbaren STEP-Text samt Schreibebene uebernehmen; ohne Ausdehnung mit Ersatz-Schrifthoehe."""
        typ = "TEXT_LITERAL" if e.is_a("TEXT_LITERAL") else "TEXT_LITERAL_WITH_EXTENT"
        args = _eig(e, typ)
        if len(args) < 2 or not isinstance(args[0], str) or not args[0].strip():
            return
        text, ort = args[:2]
        achsen = self.d.get(ort)
        if achsen is None:
            return
        if achsen.is_a("AXIS2_PLACEMENT_3D"):
            o, x, y, z = self.platzierung(ort)
        elif achsen.is_a("AXIS2_PLACEMENT_2D"):
            args = _eig(achsen, "AXIS2_PLACEMENT_2D")
            punkt, refx = achsen.args("PLACEMENT") + args if achsen.is_a("PLACEMENT") else args
            o = np.append(self.punkt(punkt), 0.)
            x = np.append(self.richtung(refx, (1., 0.)), 0.)
            z = np.array([0., 0., 1.])
            y = np.cross(z, x)
        else:
            return
        h = 2.5
        b = h * .6 * len(text)
        if e.is_a("TEXT_LITERAL_WITH_EXTENT"):
            box = self.d.get(e.args("TEXT_LITERAL_WITH_EXTENT")[-1])
            if box is not None and box.is_a("PLANAR_EXTENT"):
                b, h = (float(w) * self.skala for w in _eig(box, "PLANAR_EXTENT")[:2])
        g.platzhalter.append(Platzhalter(o, x, y, b, h, text=text))
        if g.ebene is None:
            g.ebene = (o, x, y, z)

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
        args = _eig(e, "STYLED_ITEM") if e.is_a("STYLED_ITEM") else _eig(e, teil)
        if g.farbe is None:
            stile = args[0]
            for st in stile or []:
                g.farbe = g.farbe or self.stilfarbe(st)
        if teil.startswith("ANNOTATION_PLACEHOLDER"):
            self.platzhalter(e, g, teil)
        else:
            item = args[1]
            ziel = self.d.get(item)
            if ziel is not None and (ziel.is_a("TEXT_LITERAL") or ziel.is_a("TEXT_LITERAL_WITH_EXTENT")):
                self.textliteral(ziel, g)
                return
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


def eigenstaendige_annotation(datei: P21Datei, e: Entity) -> bool:
    """Aeltere STEP-PMI liegt oft direkt in der Zeichnungsebene, ohne DRAUGHTING_CALLOUT."""
    if not e.parts.keys() & set(ANNOTATIONEN):
        return False
    eltern = [datei.entities[r] for r in datei.referrers().get(e.id, ())]
    return (not any(r.is_a("DRAUGHTING_CALLOUT") for r in eltern)
            and any(r.is_a("DRAUGHTING_MODEL") or r.is_a("ANNOTATION_PLANE")
                    or r.is_a("DRAUGHTING_MODEL_ITEM_ASSOCIATION") or r.is_a(DMIA_PH) for r in eltern))


def _grafikkontexte(datei):
    """Definitionskontext aus der PMI-Verknuepfung, sonst aus der zugehoerigen Ansicht."""
    from .ansichten import _items, _semantik_von
    von_ansicht, von_link, pmi_ids = {}, {}, {}
    grafiktypen = {"DRAUGHTING_CALLOUT", *ANNOTATIONEN}
    for m in datei.of_type("DRAUGHTING_MODEL"):
        kontext = darstellungskontext(m)
        if kontext is None:
            continue
        for ref in _items(datei, m):
            e = datei.get(ref)
            if e is None:
                continue
            if e.parts.keys() & grafiktypen:
                von_ansicht.setdefault(e.id, set()).add(kontext)
            if e.is_a("ANNOTATION_PLANE"):
                args = e.args("ANNOTATION_PLANE")
                if args and isinstance(args[-1], list):
                    for kind in args[-1]:
                        if isinstance(kind, Ref):
                            von_ansicht.setdefault(kind.id, set()).add(kontext)
    for d in datei.of_types_by_id(("DRAUGHTING_MODEL_ITEM_ASSOCIATION", DMIA_PH)):
        args = d.args()
        if len(args) < 5 or not isinstance(args[4], Ref):
            continue
        ziel = datei.get(args[4])
        if ziel is None or not ziel.parts.keys() & grafiktypen:
            continue
        if isinstance(args[2], Ref):
            pmi_ids.setdefault(ziel.id, set()).add(_semantik_von(datei, args[2].id))
        kontext = darstellungskontext(datei.get(args[3]))
        if kontext is not None:
            von_link.setdefault(ziel.id, set()).add(kontext)
    return von_ansicht, von_link, pmi_ids


def _textskala(kontexte, skalen, ersatz=None):
    if not kontexte:
        return ersatz
    werte = {skalen.get(k) for k in kontexte}
    return werte.pop() if len(werte) == 1 else None


def callout_einheiten(datei, ids):
    """Nur zugewiesene Beschriftungseinheiten lesen, ohne Grafik oder Modellskala als Ersatz."""
    from .ansichten import kontext_skalen
    skalen = kontext_skalen(datei)
    ansichten, definitionen, _ = _grafikkontexte(datei)
    return {eid: _textskala(definitionen.get(eid) or ansichten.get(eid), skalen) for eid in ids}


def lies_grafik(datei: P21Datei, skala: float | None = None) -> dict[int, Grafik]:
    """Grafik je Callout in mm. skala dient als Ersatz bei fehlender Laengeneinheit."""
    from .ansichten import _laengen_skala, kontext_skalen
    skalen = kontext_skalen(datei)
    ersatz = _laengen_skala(datei, skalen) if skala is None else skala
    ansichten, definitionen, pmi_ids = _grafikkontexte(datei)
    texteinheit = ersatz if len(set(skalen.values())) <= 1 else None
    leser_je_skala = {s: _Leser(datei, s) for s in {*skalen.values(), ersatz}}

    def grafik(e, name):
        definition = definitionen.get(e.id, ())
        faktor = _textskala(definition or ansichten.get(e.id), skalen, texteinheit)
        kontext = next(iter(definition)) if len(definition) == 1 else None
        g = Grafik(e.id, name or "", textfaktor=faktor, kontext=kontext, pmi_ids=pmi_ids.get(e.id, set()))
        return g, leser_je_skala[faktor or ersatz]

    out: dict[int, Grafik] = {}
    for e in datei.of_types_by_id(ANNOTATIONEN):
        if eigenstaendige_annotation(datei, e):
            name = e.args("REPRESENTATION_ITEM")[0] if e.is_a("REPRESENTATION_ITEM") else e.args()[0]
            g, leser = grafik(e, name)
            leser.annotation(Ref(e.id), g)
            g.linien.extend(g.hinweislinien)
            out[e.id] = g
    for c in datei.of_type("DRAUGHTING_CALLOUT"):
        name, teile = c.args("DRAUGHTING_CALLOUT")[:2]
        g, leser = grafik(c, name)
        for r in teile:
            leser.annotation(r, g)
        # Platzhalter nur, wenn es keine fertige Grafik gibt (NIST liefert oft beides)
        if g.fertig:
            g.platzhalter, g.hinweislinien = [ph for ph in g.platzhalter if ph.text], []
        else:
            g.linien += g.hinweislinien
        out[c.id] = g
    # Die Schreibachsen sind auch bei reiner Kurvengrafik fuer die Strichschrifterkennung noetig.
    for e in datei.of_type("ANNOTATION_PLANE"):
        args = e.args("ANNOTATION_PLANE")
        stil = e.parts.get("STYLED_ITEM")
        if not args or not isinstance(args[-1], list):
            continue
        flaeche = stil[-1] if stil else args[2] if len(args) >= 4 else None
        fl = datei.get(flaeche) if isinstance(flaeche, Ref) else None
        if fl is None or not fl.is_a("PLANE"):
            continue
        platz = _eig(fl, "PLANE")
        achse = datei.get(platz[0]) if platz and isinstance(platz[0], Ref) else None
        if achse is None or not achse.is_a("AXIS2_PLACEMENT_3D"):
            continue
        for ref in args[-1]:
            g = out.get(ref.id) if isinstance(ref, Ref) else None
            if g is not None and g.ebene is None:
                g.ebene = leser_je_skala[g.textfaktor or ersatz].platzierung(platz[0])
    mit_grafik = set().union(*(g.pmi_ids for g in out.values() if g.fertig)) if out else set()
    for g in out.values():
        g.doppelt = not g.fertig and bool(g.pmi_ids) and g.pmi_ids <= mit_grafik
    return out


def netz_darstellungen(datei: P21Datei, flaeche_step: int) -> set[int]:
    """Nur direkte Geometrie-Mitgliedschaften verfolgen, ohne Stile, PMI oder Verwendungsinstanzen."""
    gruppen = {"TESSELLATED_SOLID", "TESSELLATED_SHELL", "TESSELLATED_GEOMETRIC_SET"}
    darstellungen = {"TESSELLATED_SHAPE_REPRESENTATION", "SHAPE_REPRESENTATION"}
    offen, gesehen, treffer = [flaeche_step], {flaeche_step}, set()
    while offen:
        x = offen.pop()
        for r in datei.referrers().get(x, ()):
            if r in gesehen:
                continue
            e = datei.entities[r]
            if e.parts.keys() & darstellungen:
                args = e.parts.get("REPRESENTATION", e.args())
                if len(args) > 1 and isinstance(args[1], list) and Ref(x) in args[1]:
                    treffer.add(r)
            elif typen := e.parts.keys() & gruppen:
                args = _eig(e, next(iter(typen)))
                if args and isinstance(args[0], list) and Ref(x) in args[0]:
                    offen.append(r)
                    gesehen.add(r)
    return treffer


def eindeutige_netzdarstellung(datei: P21Datei, kandidaten: set[int]) -> int | None:
    netz = {r for r in kandidaten if datei.entities[r].is_a("TESSELLATED_SHAPE_REPRESENTATION")}
    treffer = netz or kandidaten
    return next(iter(treffer)) if len(treffer) == 1 else None


def darstellung_der_flaeche(datei: P21Datei, flaeche_step: int) -> int | None:
    """Formdarstellung (REPRESENTATION), in der eine Flaeche liegt: aufwaerts ueber die Verweise."""
    from .laden import NETZFLAECHEN
    if (e := datei.get(flaeche_step)) and e.parts.keys() & NETZFLAECHEN:
        return eindeutige_netzdarstellung(datei, netz_darstellungen(datei, flaeche_step))
    offen, gesehen = [flaeche_step], set()
    verweise = datei.referrers()
    while offen:
        x = offen.pop(0)
        for r in verweise.get(x, []):
            if r in gesehen:
                continue
            gesehen.add(r)
            e = datei.entities[r]
            if e.is_a("SHAPE_REPRESENTATION") or e.is_a("ADVANCED_BREP_SHAPE_REPRESENTATION") or \
                    e.is_a("MANIFOLD_SURFACE_SHAPE_REPRESENTATION"):
                return r
            if not (e.is_a("STYLED_ITEM") or e.is_a("GEOMETRIC_ITEM_SPECIFIC_USAGE")):
                offen.append(r)
    return None


def in_teillage(grafik: dict[int, Grafik], pmi: list, modell) -> None:
    """Baugruppe: Grafik im Koordinatensystem eines Teils an die Lage der Instanz setzen, deren Flaechen die
    verknuepfte PMI nennt - nur wenn das DRAUGHTING_MODEL den Kontext dieses Teils hat (sonst ist die Grafik schon
    in Baugruppenkoordinaten). Bei mehreren Instanzen: die der PMI."""
    datei = getattr(modell, "datei", None)
    step_von = {i: eid for eid, i in getattr(modell, "step_zu_flaeche", {}).items()}
    je_id = {p.step_id: p for p in pmi if p.flaechen}
    for g in grafik.values():
        p = next((je_id[i] for i in sorted(g.pmi_ids) if i in je_id), None)
        if datei is None or g.erzeugt or g.kontext is None or p is None:
            continue
        idx = min(p.flaechen)
        if idx >= len(modell.flaechen) or idx not in step_von:
            continue
        lage = modell.flaechen[idx].Location()
        if lage.IsIdentity() or darstellungskontext(datei.get(darstellung_der_flaeche(datei, step_von[idx]))) != g.kontext:
            continue
        _bewege(g, lage.Transformation())


def _bewege(g: Grafik, t) -> None:
    m = np.array([[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)])
    d, v = m[:, :3], m[:, 3]
    punkte = lambda p: np.asarray(p, float) @ d.T + v  # noqa: E731
    g.linien = [punkte(l) for l in g.linien]
    g.hinweislinien = [punkte(l) for l in g.hinweislinien]
    g.dreiecke = [(punkte(p), i) for p, i in g.dreiecke]
    for ph in g.platzhalter:
        ph.ursprung, ph.x, ph.y = punkte(ph.ursprung), ph.x @ d.T, ph.y @ d.T
    if g.ebene is not None:
        o, x, y, z = g.ebene
        g.ebene = (punkte(o), x @ d.T, y @ d.T, z @ d.T)


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
    faktor = prc.einheit_mm(modell_prc)
    for m in prc.markup_grafik(modell_prc):
        g = Grafik(m.eid, m.name, linien=_ketten(m.linien), fertig=True, farbe=m.farbe,
                   markup=(m.art, m.unterart), textfaktor=faktor)
        for text, o, x, y, breite, hoehe in m.texte:
            g.platzhalter.append(Platzhalter(o, x, y, breite, hoehe, text))
            if g.ebene is None:
                g.ebene = (o, x, y, np.cross(x, y))
        for d in m.dreiecke:
            if len(d) >= 3:
                n = len(d) // 3 * 3
                g.dreiecke.append((d[:n], np.arange(n).reshape(-1, 3)))
        out[m.eid] = g
    return out
