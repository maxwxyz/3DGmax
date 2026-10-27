"""Kollisions-, Kontakt- und Bandanalyse zwischen Teilen einer Baugruppe (ohne Qt), PLAN §8.21 Stufe 1-4.

Paare: alle Teile untereinander oder Gruppe A gegen Gruppe B (Teil-Instanzen zaehlen einzeln). Vorauswahl ueber die
Huellquader (um den groessten gesuchten Abstand erweitert), dann je Paar exakt: kleinster Abstand mit Punkten
(BRepExtrema_DistShapeShape) und Durchdringungskoerper (BRepAlgoAPI_Common, Volumen).
Arten: Kollision (Durchdringungsvolumen > 0), Kontakt (Abstand <= Kontakttoleranz, kein Volumen), zu nah
(Abstand < Mindestabstand), zu weit (Abstand > Hoechstabstand, nur fuer Gruppe A gegen B: sonst waere jedes entfernte
Paar ein Befund).
"""

from __future__ import annotations

from dataclasses import dataclass, field

KOLLISION, KONTAKT, ZU_NAH, ZU_WEIT = "kollision", "kontakt", "zu_nah", "zu_weit"
ART_TEXT = {KOLLISION: "Kollision", KONTAKT: "Kontakt", ZU_NAH: "zu nah", ZU_WEIT: "zu weit"}
STATUS = {"offen": "offen", "akzeptiert": "akzeptiert", "ignoriert": "ignoriert"}


@dataclass
class Teil:
    nummer: int  # Knotennummer im Baum
    name: str
    form: object  # TopoDS_Shape in Baugruppenlage


@dataclass
class Befund:
    nummer: int
    a: Teil
    b: Teil
    art: str
    abstand: float
    volumen: float = 0.0
    punkte: tuple = ()  # (Punkt auf a, Punkt auf b) des kleinsten Abstands
    durchdringung: object = None  # TopoDS_Shape der Durchdringung (Kollision)
    status: str = "offen"
    kommentar: str = ""


@dataclass
class Einstellung:
    kontakt: float = 0.01  # mm: bis hierhin gilt eine Beruehrung als Kontakt
    mindest: float = 0.0  # mm: kleinere Abstaende melden (0: aus)
    hoechst: float = 0.0  # mm: groessere Abstaende melden, nur Gruppe A gegen B (0: aus)
    kontakte_melden: bool = True


def _box(form, rand: float):
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    brepbndlib.Add(form, b)
    if rand > 0:
        b.Enlarge(rand)
    return b


def paare(teile: list[Teil], gruppe_b: list[Teil] | None = None) -> list[tuple[Teil, Teil]]:
    if gruppe_b is None:
        return [(teile[i], teile[j]) for i in range(len(teile)) for j in range(i + 1, len(teile))]
    return [(a, b) for a in teile for b in gruppe_b if a.nummer != b.nummer]


def _volumen(form) -> float:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    g = GProp_GProps()
    brepgprop.VolumeProperties(form, g)
    return abs(g.Mass())


def _pruefe_paar(a: Teil, b: Teil, e: Einstellung, gegen: bool):
    """(Art, Abstand, Volumen, Punkte, Durchdringung) oder None ohne Befund."""
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    d = BRepExtrema_DistShapeShape(a.form, b.form)
    d.Perform()
    if not d.IsDone():
        return None
    abstand = d.Value()
    punkte = ()
    if d.NbSolution():
        pa, pb = d.PointOnShape1(1), d.PointOnShape2(1)
        punkte = ((pa.X(), pa.Y(), pa.Z()), (pb.X(), pb.Y(), pb.Z()))
    if abstand <= e.kontakt:
        common = BRepAlgoAPI_Common(a.form, b.form)
        if common.IsDone():
            volumen = _volumen(common.Shape())
            if volumen > 1e-6:
                return KOLLISION, 0.0, volumen, punkte, common.Shape()
        return (KONTAKT, abstand, 0.0, punkte, None) if e.kontakte_melden else None
    if e.mindest > 0 and abstand < e.mindest:
        return ZU_NAH, abstand, 0.0, punkte, None
    if gegen and e.hoechst > 0 and abstand > e.hoechst:
        return ZU_WEIT, abstand, 0.0, punkte, None
    return None


def pruefe(teile: list[Teil], gruppe_b: list[Teil] | None = None, e: Einstellung | None = None,
           fortschritt=lambda anteil: None) -> list[Befund]:
    """Befunde aller Paare; fortschritt(0..1) darf eine Ausnahme werfen (Abbruch)."""
    e = e or Einstellung()
    gegen = gruppe_b is not None
    rand = max(e.kontakt, e.mindest)
    liste = paare(teile, gruppe_b)
    boxen = {}
    for t in {id(t): t for p in liste for t in p}.values():
        boxen[id(t)] = _box(t.form, 0.0)
    befunde = []
    for k, (a, b) in enumerate(liste):
        fortschritt(k / max(len(liste), 1))
        ba = _box(a.form, rand) if rand > 0 else boxen[id(a)]
        if ba.IsOut(boxen[id(b)]) and not (gegen and e.hoechst > 0):
            continue  # weit genug auseinander (bei "zu weit" muss jedes Paar gemessen werden)
        erg = _pruefe_paar(a, b, e, gegen)
        if erg is not None:
            art, abstand, volumen, punkte, form = erg
            befunde.append(Befund(len(befunde) + 1, a, b, art, abstand, volumen, punkte, form))
    fortschritt(1.0)
    ordnung = {KOLLISION: 0, ZU_NAH: 1, KONTAKT: 2, ZU_WEIT: 3}
    befunde.sort(key=lambda x: (ordnung[x.art], -x.volumen, x.abstand))
    for i, x in enumerate(befunde, 1):
        x.nummer = i
    return befunde


SPALTEN = ("Nr", "Teil A", "Teil B", "Art", "Abstand", "Volumen", "Status", "Kommentar")


def als_csv(befunde: list[Befund]) -> str:
    import csv
    import io
    from ..i18n import tr
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow([tr(s) for s in SPALTEN])
    for x in befunde:
        w.writerow([x.nummer, x.a.name, x.b.name, tr(ART_TEXT[x.art]), f"{x.abstand:.4f}".replace(".", ","),
                    f"{x.volumen:.3f}".replace(".", ","), tr(STATUS[x.status]), x.kommentar])
    return puffer.getvalue()
