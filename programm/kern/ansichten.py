"""Gespeicherte Ansichten (Saved Views) aus AP242 lesen.

Eine Ansicht ist ein DRAUGHTING_MODEL mit einer Kamera (CAMERA_MODEL_D3). Die PMI einer Ansicht
ergeben sich aus DRAUGHTING_MODEL_ITEM_ASSOCIATION: Semantik -> Annotation, die in der Ansicht liegt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .laden import StepModell
from .p21 import DMIA_PH, Entity, P21Datei, Ref
from .pmi import Pmi

KAMERA_TYPEN = ("CAMERA_MODEL_D3", "CAMERA_MODEL_D3_MULTI_CLIPPING")


@dataclass
class Ansicht:
    name: str
    step_id: int
    ort: tuple[float, float, float] = (0.0, 0.0, 0.0)
    richtung: tuple[float, float, float] = (0.0, 0.0, -1.0)  # Blickrichtung
    oben: tuple[float, float, float] = (0.0, 1.0, 0.0)
    breite: float = 0.0  # Fenster der Ansicht (mm)
    hoehe: float = 0.0
    abstand: float = 0.0  # Abstand Kamera -> Bildebene (view_plane_distance, mm)
    perspektive: bool = False
    pmi_ids: set[int] = field(default_factory=set)  # STEP-#IDs der sichtbaren PMI
    pmi_nummern: list[int] = field(default_factory=list)
    eigen: bool = False  # vom Nutzer gemerkt (nicht aus der Datei)
    messungen: list[int] = field(default_factory=list)  # Nummern der dabei sichtbaren Messungen


def _punkt(datei: P21Datei, ref, skala=1.0):
    e = datei.get(ref)
    if e is None:
        return None
    werte = e.args("CARTESIAN_POINT")[1] if e.is_a("CARTESIAN_POINT") else e.args("DIRECTION")[1]
    v = [float(x) * skala for x in werte] + [0.0] * (3 - len(werte))
    return tuple(v[:3])


def _laengen_skala(datei: P21Datei) -> float:
    """Faktor Datei-Laengeneinheit -> mm (aus dem ersten LENGTH_UNIT)."""
    from .pmi_step import einheit_mm
    for e in datei.entities.values():
        if e.is_a("LENGTH_UNIT") and (e.is_a("SI_UNIT") or e.is_a("CONVERSION_BASED_UNIT")):
            return einheit_mm(datei, Ref(e.id))
    return 1.0


def _kamera(datei: P21Datei, e: Entity, ansicht: Ansicht, skala: float):
    teil = next(t for t in KAMERA_TYPEN if e.is_a(t))
    _, platz, volumen = e.args(teil)[:3]
    pl = datei.get(platz)
    if pl is not None and pl.is_a("AXIS2_PLACEMENT_3D"):
        _, ort, achse, ref_x = pl.args("AXIS2_PLACEMENT_3D")[:4]
        ansicht.ort = _punkt(datei, ort, skala) or ansicht.ort
        z = _punkt(datei, achse) if achse else (0.0, 0.0, 1.0)
        x = _punkt(datei, ref_x) if ref_x else (1.0, 0.0, 0.0)
        # Kamera blickt entlang +z der Platzierung (gegengeprueft: sonst Schrift gespiegelt), y = z x x ist oben
        ansicht.richtung = tuple(z)
        ansicht.oben = _kreuz(z, x)
    vv = datei.get(volumen)
    if vv is not None and vv.is_a("VIEW_VOLUME"):
        args = vv.args("VIEW_VOLUME")
        ansicht.perspektive = getattr(args[0], "name", "") == "CENTRAL"
        if isinstance(args[2], (int, float)):
            ansicht.abstand = float(args[2]) * skala
        box = datei.get(args[8]) if len(args) > 8 else None
        if box is not None and box.is_a("PLANAR_BOX"):
            ansicht.breite = float(box.args("PLANAR_BOX")[1]) * skala
            ansicht.hoehe = float(box.args("PLANAR_BOX")[2]) * skala


def _kreuz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _items(datei: P21Datei, modell_e: Entity) -> list:
    teil = "REPRESENTATION" if modell_e.is_a("REPRESENTATION") else next(iter(modell_e.parts))
    args = modell_e.args(teil)
    return args[1] if len(args) > 1 and isinstance(args[1], list) else []


def _semantik_von(datei: P21Datei, definition: int) -> int:
    """DMIA-Definition auf die PMI-#ID abbilden (Bezugsmerkmal -> DATUM)."""
    e = datei.get(definition)
    if e is not None and e.is_a("DATUM_FEATURE"):
        for rid in datei.referrers().get(definition, []):
            r = datei.entities[rid]
            if r.is_a("SHAPE_ASPECT_RELATIONSHIP"):
                ziel = r.args("SHAPE_ASPECT_RELATIONSHIP")[3]
                if isinstance(ziel, Ref) and datei.entities[ziel.id].is_a("DATUM"):
                    return ziel.id
    return definition


def _prc_ansichten(modell) -> list[Ansicht]:
    """Gespeicherte Ansichten aus PRC (Kamera in mm, sichtbare Markups als PMI-IDs)."""
    import numpy as np
    from . import prc
    out = []
    for a in prc.ansichten(modell.prc):
        ansicht = Ansicht(a["name"], a["eid"])
        k = a["kamera"]
        if k is not None:
            r = np.asarray(k["ziel"], float) - np.asarray(k["ort"], float)
            laenge = float(np.linalg.norm(r)) or 1.0
            ansicht.ort = tuple(float(x) for x in k["ort"])
            ansicht.richtung = tuple(float(x) for x in r / laenge)
            ansicht.oben = tuple(float(x) for x in k["oben"])
            ansicht.breite, ansicht.hoehe = float(k["breite"]), float(k["hoehe"])
            ansicht.abstand = laenge
            ansicht.perspektive = not k["ortho"]
        ansicht.pmi_ids = set(a["markups"])
        out.append(ansicht)
    return out


def lies_ansichten(modell: StepModell, pmi: list[Pmi] | None = None) -> list[Ansicht]:
    datei = modell.datei
    if datei is None and (getattr(modell, "prc", None) is not None or getattr(modell, "qif", None) is not None):
        if getattr(modell, "qif", None) is not None:
            from . import qif_grafik
            ansichten = qif_grafik.ansichten(modell.qif)
        else:
            ansichten = _prc_ansichten(modell)
        if pmi is not None:
            nr = {p.step_id: p.nummer for p in pmi if p.step_id}
            for a in ansichten:
                a.pmi_nummern = sorted(nr[i] for i in a.pmi_ids if i in nr)
        return ansichten
    if datei is None:
        return []
    skala = _laengen_skala(datei)
    # Annotation -> semantische PMI
    zu_pmi: dict[int, set[int]] = {}
    for d in datei.of_type("DRAUGHTING_MODEL_ITEM_ASSOCIATION") + datei.of_type(DMIA_PH):
        args = d.args(next(iter(d.parts)))
        if isinstance(args[2], Ref) and isinstance(args[4], Ref):
            zu_pmi.setdefault(args[4].id, set()).add(_semantik_von(datei, args[2].id))
    ansichten = []
    for m in datei.of_type("DRAUGHTING_MODEL"):
        items = [r.id for r in _items(datei, m) if isinstance(r, Ref)]
        kameras = [datei.entities[i] for i in items if any(datei.entities[i].is_a(t) for t in KAMERA_TYPEN)]
        for k in kameras:
            name = k.args(next(t for t in KAMERA_TYPEN if k.is_a(t)))[0]
            a = Ansicht(name, k.id)
            _kamera(datei, k, a, skala)
            for i in items:
                # Callouts ohne Semantik (Hinweise) stehen mit ihrer eigenen #ID in der Liste
                ohne = {i} if datei.entities[i].is_a("DRAUGHTING_CALLOUT") else set()
                a.pmi_ids |= zu_pmi.get(i) or ohne
            ansichten.append(a)
    if pmi is not None:
        nr = {p.step_id: p.nummer for p in pmi if p.step_id}
        for a in ansichten:
            a.pmi_nummern = sorted(nr[i] for i in a.pmi_ids if i in nr)
    return ansichten
