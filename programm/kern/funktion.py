"""Von der Funktion zur ISO-GPS-Tolerierung (PLAN §8.33 Stufen 2 und 3, ohne Qt).

Der Konstrukteur ordnet den Flaechen eines Teils ihre Funktion zu (Rolle). Daraus folgen:
1. Bezugssystem (ISO 5459, 3-2-1): primaer die groesste ebene Auflage (sperrt 3 Freiheitsgrade), sekundaer eine
   Zentrierung senkrecht dazu (Achse, 2 FG) oder eine Auflage/ein Anschlag senkrecht dazu (2 FG), tertiaer die
   Verdrehsicherung oder ein Anschlag fuer den letzten Freiheitsgrad. Ohne ebene Auflage wird die laengste
   Zentrierung primaer (Achse, 4 FG).
2. Tolerierung je Rolle (ISO 1101/286): Auflage - Ebenheit, als Nicht-Bezug Parallelitaet zu A; Zentrierung - Passmass
   (Vorzugspassung H7/h6) und Rechtwinkligkeit bzw. Position zum Bezugssystem; Fuehrung - Passmass H7/f7 und
   Zylinderform; Presssitz - H7/p6; Verdrehsicherung - H7/m6 und Position mit Maximum-Material; Dichtflaeche -
   Ebenheit und Hinweis zur Rauheit; Anschlag - Flaechenprofil zum Bezugssystem; Freiflaeche - Allgemeintoleranz.
Passungen aus den Vorzugspassungen des ISO-Systems (Bohrungsbasis H, ISO 286-1/-2); Toleranzwerte als IT-Grad bei der
Groesse des Elements (Startwerte - die Kette und die Kostenoptimierung legen die endgueltigen Werte fest).

Ein Element kann aus mehreren Flaechen bestehen (gruppen: erste Flaeche -> alle Flaechen), z. B. zwei Halbschalen
einer Bohrung oder eine durch Nuten geteilte Auflage; Rollen und Werte haengen an der ersten Flaeche. werte: je Element
eine von Hand gesetzte Toleranz (alle Form-/Lagetoleranzen des Elements) und/oder Passung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..i18n import tr
from .pmi import BEZUG, HINWEIS, MASS, TOLERANZ, BezugsRef, Pmi
from .pmi_vorschlag import Vorschlag, _flaeche_info

# Rolle -> (Anzeigename, Passung (Bohrung, Welle) oder None)
ROLLEN = {
    "auflage": ("Auflage / Sitz", None),
    "zentrierung": ("Zentrierung (Passung)", ("H7", "h6")),
    "fuehrung": ("Führung (gleitend)", ("H7", "f7")),
    "presssitz": ("Presssitz", ("H7", "p6")),
    "verdrehsicherung": ("Verdrehsicherung (Stift)", ("H7", "m6")),
    "dichtung": ("Dichtfläche", None),
    "anschlag": ("Anschlag", None),
    "frei": ("Freifläche", None),
}
# IT-Grade der Startwerte je Rolle: (Form, Richtung/Lage)
GRADE = {"auflage": (6, 7), "zentrierung": (6, 7), "fuehrung": (6, 7), "presssitz": (6, 7),
         "verdrehsicherung": (7, 8), "dichtung": (5, 7), "anschlag": (7, 8)}


@dataclass
class BezugVorschlag:
    buchstabe: str
    flaeche: int
    element: str  # "ebene" oder "achse"
    freiheitsgrade: int  # gesperrte Freiheitsgrade
    grund: str


@dataclass
class Bezugssystem:
    bezuege: list[BezugVorschlag] = field(default_factory=list)
    offen: int = 6  # nicht gesperrte Freiheitsgrade
    hinweise: list[str] = field(default_factory=list)


def _geometrie(flaeche) -> dict | None:
    """Art, Richtung (Normale bzw. Achse), Punkt, Flaeche und Groesse (Ausdehnung bzw. Durchmesser) einer Flaeche."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    info = _flaeche_info(flaeche)
    if info is None or info[0] not in ("ebene", "zylinder"):
        return None
    art, d = info
    pr = GProp_GProps()
    brepgprop.SurfaceProperties(flaeche, pr)
    b = Bnd_Box()
    brepbndlib.Add(flaeche, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    ausdehnung = math.dist((x0, y0, z0), (x1, y1, z1))
    if art == "ebene":
        return {"art": "ebene", "richtung": np.array(d["normale"]), "punkt": np.array(d["punkt"]),
                "inhalt": pr.Mass(), "groesse": ausdehnung}
    ax = BRepAdaptor_Surface(flaeche, True).Cylinder().Axis()
    r = ax.Direction()
    p = ax.Location()
    return {"art": "zylinder", "richtung": np.array([r.X(), r.Y(), r.Z()]), "punkt": np.array([p.X(), p.Y(), p.Z()]),
            "inhalt": pr.Mass(), "groesse": 2 * d["r"], "bohrung": d["bohrung"], "laenge": ausdehnung}


def _geo(modell, i: int, gruppen: dict | None = None) -> dict | None:
    """Geometrie eines Elements (eine Flaeche oder eine Gruppe auf demselben Zylinder bzw. in derselben Ebene):
    Richtung und Groesse der ersten Flaeche, Inhalt summiert, Ausdehnung ueber alle Flaechen."""
    flaechen = (gruppen or {}).get(i, (i,))
    g = _geometrie(modell.flaechen[flaechen[0]])
    if g is None or len(flaechen) < 2:
        return g
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    b = Bnd_Box()
    inhalt = 0.0
    for j in flaechen:
        gj = _geometrie(modell.flaechen[j])
        inhalt += gj["inhalt"] if gj else 0.0
        brepbndlib.Add(modell.flaechen[j], b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    g = dict(g, inhalt=inhalt)
    g["laenge" if g["art"] == "zylinder" else "groesse"] = math.dist((x0, y0, z0), (x1, y1, z1))
    return g


def ein_element(modell, flaechen) -> bool:
    """Bilden die Flaechen ein Element: alle auf demselben Zylinder (Achse, Durchmesser) oder in derselben Ebene."""
    geo = [_geometrie(modell.flaechen[i]) for i in flaechen]
    if len(geo) < 2 or any(g is None for g in geo) or len({g["art"] for g in geo}) != 1:
        return False
    a = geo[0]
    for g in geo[1:]:
        q = g["punkt"] - a["punkt"]
        if not _parallel(g["richtung"], a["richtung"]):
            return False
        if a["art"] == "zylinder" and (abs(g["groesse"] - a["groesse"]) > 1e-4 or
                                       np.linalg.norm(q - a["richtung"] * float(q @ a["richtung"])) > 1e-3):
            return False
        if a["art"] == "ebene" and abs(float(q @ a["richtung"])) > 1e-3:
            return False
    return True


def startwerte(modell, i: int, rolle: str, gruppen: dict | None = None) -> dict:
    """Startwerte eines Elements ohne Eingabe: Formtoleranz, Lagetoleranz (IT-Grad bei der Groesse) und Passung."""
    g = _geo(modell, i, gruppen)
    if g is None or rolle == "frei":
        return {}
    form, lage = GRADE.get(rolle, (7, 8))
    passung = ROLLEN[rolle][1]
    klasse = (passung[0] if g.get("bohrung") else passung[1]) if passung and g["art"] == "zylinder" else ""
    return {"form": _it(form, g["groesse"]), "lage": _it(lage, g["groesse"]), "grad": (form, lage), "passung": klasse}


def _parallel(a, b) -> bool:
    return abs(abs(float(a @ b)) - 1) < 1e-4


def _senkrecht(a, b) -> bool:
    return abs(float(a @ b)) < 1e-4


def bezugssystem(modell, rollen: dict[int, str], gruppen: dict | None = None) -> Bezugssystem:
    """Bezugssystem A|B|C aus den Funktionsrollen (3-2-1); Begruendung je Bezug, Hinweis bei offenen Freiheitsgraden."""
    geo = {i: g for i in rollen if (g := _geo(modell, i, gruppen)) is not None}
    ebenen = lambda *r: sorted((i for i in geo if geo[i]["art"] == "ebene" and rollen[i] in r),  # noqa: E731
                               key=lambda i: -geo[i]["inhalt"])
    achsen = lambda *r: sorted((i for i in geo if geo[i]["art"] == "zylinder" and rollen[i] in r),  # noqa: E731
                               key=lambda i: -geo[i].get("laenge", 0))
    s = Bezugssystem()
    buchstaben = iter("ABC")
    auflagen = ebenen("auflage")
    if auflagen:
        a = auflagen[0]
        s.bezuege.append(BezugVorschlag(next(buchstaben), a, "ebene", 3,
                                        "Größte ebene Auflage: legt das Teil auf (3 Freiheitsgrade)"))
        na = geo[a]["richtung"]
        zentr = [i for i in achsen("zentrierung", "presssitz") if _parallel(geo[i]["richtung"], na)]
        if zentr:
            b = zentr[0]
            s.bezuege.append(BezugVorschlag(next(buchstaben), b, "achse", 2,
                                            "Zentrierung senkrecht zur Auflage: legt die Lage in der Ebene fest "
                                            "(2 Freiheitsgrade)"))
            nb = None
        else:
            seiten = [i for i in ebenen("auflage", "anschlag") if i != a and _senkrecht(geo[i]["richtung"], na)]
            if seiten:
                b = seiten[0]
                s.bezuege.append(BezugVorschlag(next(buchstaben), b, "ebene", 2,
                                                "Seitliche Anlage senkrecht zur Auflage (2 Freiheitsgrade)"))
                nb = geo[b]["richtung"]
            else:
                b = None
        if b is not None:
            gesperrt = {s.bezuege[0].flaeche, b}
            if nb is None:  # Achse B: Drehung um sie sperrt eine Verdrehsicherung oder ein Anschlag
                dritte = [i for i in achsen("verdrehsicherung", "zentrierung") if i not in gesperrt
                          and _parallel(geo[i]["richtung"], na)] + \
                         [i for i in ebenen("anschlag", "auflage") if i not in gesperrt
                          and _senkrecht(geo[i]["richtung"], na)]
                grund = "Verdrehsicherung um die Achse von B (1 Freiheitsgrad)"
            else:
                dritte = [i for i in ebenen("anschlag", "auflage") if i not in gesperrt
                          and _senkrecht(geo[i]["richtung"], na) and _senkrecht(geo[i]["richtung"], nb)] + \
                         [i for i in achsen("verdrehsicherung", "zentrierung") if i not in gesperrt
                          and _parallel(geo[i]["richtung"], na)]
                grund = "Anschlag senkrecht zu A und B (1 Freiheitsgrad)"
            if dritte:
                c = dritte[0]
                s.bezuege.append(BezugVorschlag(next(buchstaben), c, geo[c]["art"].replace("zylinder", "achse"), 1,
                                                grund))
    else:
        zentr = achsen("zentrierung", "presssitz", "fuehrung")
        if zentr:
            a = zentr[0]
            s.bezuege.append(BezugVorschlag(next(buchstaben), a, "achse", 4,
                                            "Längste Zentrierung als Achse (4 Freiheitsgrade, keine ebene Auflage)"))
            na = geo[a]["richtung"]
            anschlag = [i for i in ebenen("anschlag", "auflage") if _parallel(geo[i]["richtung"], na)]
            if anschlag:
                s.bezuege.append(BezugVorschlag(next(buchstaben), anschlag[0], "ebene", 1,
                                                "Anschlag in Achsrichtung (1 Freiheitsgrad)"))
    s.offen = 6 - sum(b.freiheitsgrade for b in s.bezuege)
    if not s.bezuege:
        s.hinweise.append(tr("Keine Auflage oder Zentrierung festgelegt – erst Funktionsrollen vergeben"))
    elif s.offen > 0:
        s.hinweise.append(tr("Noch {} Freiheitsgrad(e) offen – Verdrehsicherung oder Anschlag festlegen, falls die "
                             "Funktion sie braucht (rotationssymmetrische Teile brauchen keine)").format(s.offen))
    return s


def _it(grad: int, groesse: float) -> float:
    from .fertigung import _it_mm
    return round(_it_mm(grad, groesse), 4)


def tolerierung(modell, rollen: dict[int, str], system: Bezugssystem | None = None, gruppen: dict | None = None,
                werte: dict | None = None) -> list[Vorschlag]:
    """PMI-Vorschlaege aus Rollen und Bezugssystem: Bezuege, Passmasse, Form-, Richtungs- und Lagetoleranzen;
    gruppen und werte siehe Modulbeschreibung."""
    system = system or bezugssystem(modell, rollen, gruppen)
    out = _tolerierung(modell, rollen, system, gruppen or {})
    for v in out:  # von Hand gesetzte Werte des Elements
        w = (werte or {}).get(_element(v.pmi.flaechen, gruppen or {}), {})
        if v.pmi.art == TOLERANZ and w.get("toleranz") is not None:
            v.pmi.wert = float(w["toleranz"])
        if v.pmi.art == MASS and w.get("passung"):
            v.pmi.passung = w["passung"]
    return out


def _element(flaechen, gruppen: dict) -> int:
    """Erste Flaeche des Elements, zu dem die Flaechen gehoeren."""
    for erste, alle in gruppen.items():
        if set(flaechen) <= set(alle):
            return erste
    return min(flaechen) if flaechen else -1


def _tolerierung(modell, rollen: dict[int, str], system: Bezugssystem, gruppen: dict) -> list[Vorschlag]:
    drf = [BezugsRef(b.buchstabe, k) for k, b in enumerate(system.bezuege, 1)]
    bezug_von = {b.flaeche: b for b in system.bezuege}
    alle = lambda i: set(gruppen.get(i, (i,)))  # noqa: E731 - Flaechen des Elements
    out: list[Vorschlag] = []
    for b in system.bezuege:
        out.append(Vorschlag(Pmi(BEZUG, "Datum", b.buchstabe, flaechen=alle(b.flaeche)), b.grund))
    for i, rolle in sorted(rollen.items()):
        g = _geo(modell, i, gruppen)
        if g is None or rolle == "frei":
            continue
        form, lage = GRADE.get(rolle, (7, 8))
        vorher = [r for r in drf if bezug_von.get(i) is None or r.name < bezug_von[i].buchstabe]
        if g["art"] == "zylinder":
            passung = ROLLEN[rolle][1]
            if passung:
                klasse = passung[0] if g["bohrung"] else passung[1]
                out.append(Vorschlag(Pmi(MASS, "Size_Diameter", "", nennwert=round(g["groesse"], 4), passung=klasse,
                                         flaechen=alle(i)),
                                     tr("Passung nach Funktion: {} ({})").format(tr(ROLLEN[rolle][0]),
                                                                                 "/".join(passung))))
            t = _it(lage, g["groesse"])
            if i in bezug_von and len(vorher) == 1:
                out.append(Vorschlag(Pmi(TOLERANZ, "Perpendicularity", "", wert=t, modifikatoren=["Diameter"],
                                         bezuege=vorher[:1], flaechen=alle(i)), "Bezugsachse senkrecht zur Auflage"))
            elif i in bezug_von and vorher:  # tertiaerer Bezug: Lage zu den vorigen Bezuegen
                material = "M" if rolle == "verdrehsicherung" else ""
                out.append(Vorschlag(Pmi(TOLERANZ, "Position", "", wert=t, material=material,
                                         modifikatoren=["Diameter"], bezuege=vorher, flaechen=alle(i)),
                                     "Lage des Stifts zum Bezugssystem, Ⓜ für Montierbarkeit" if material else
                                     "Lage der Achse zum Bezugssystem"))
            elif i not in bezug_von and drf:
                material = "M" if rolle == "verdrehsicherung" else ""
                out.append(Vorschlag(Pmi(TOLERANZ, "Position", "", wert=t, material=material,
                                         modifikatoren=["Diameter"], bezuege=list(drf), flaechen=alle(i)),
                                     "Lage des Stifts zum Bezugssystem, Ⓜ für Montierbarkeit" if material else
                                     "Lage der Achse zum Bezugssystem"))
            if rolle == "fuehrung":
                out.append(Vorschlag(Pmi(TOLERANZ, "Cylindricity", "", wert=_it(form, g["groesse"]), flaechen=alle(i)),
                                     "Gleichmäßiges Spiel entlang der Führung"))
        else:
            t_form, t_lage = _it(form, g["groesse"]), _it(lage, g["groesse"])
            if rolle in ("auflage", "dichtung") or (i in bezug_von and bezug_von[i].freiheitsgrade == 3):
                out.append(Vorschlag(Pmi(TOLERANZ, "Flatness", "", wert=t_form, flaechen=alle(i)),
                                     "Ebenheit der Funktionsfläche" if rolle != "dichtung" else "Dichtheit"))
            if rolle == "dichtung":
                out.append(Vorschlag(Pmi(HINWEIS, "Note", "", nur_grafik_text="Ra ≤ 0,8 µm, drallfrei",
                                         flaechen=alle(i)), "Dichtfläche: Rauheit und Drallfreiheit"))
            if i in bezug_von and vorher:
                out.append(Vorschlag(Pmi(TOLERANZ, "Perpendicularity", "", wert=t_lage, bezuege=vorher[:1],
                                         flaechen=alle(i)), "Bezugsfläche rechtwinklig zum vorigen Bezug"))
            elif i not in bezug_von and drf:
                parallel_a = system.bezuege and system.bezuege[0].element == "ebene" and _parallel(
                    g["richtung"], _geo(modell, system.bezuege[0].flaeche, gruppen)["richtung"])
                if rolle == "auflage" and parallel_a:
                    out.append(Vorschlag(Pmi(TOLERANZ, "Parallelism", "", wert=t_lage, bezuege=drf[:1], flaechen=alle(i)),
                                         "Weitere Auflage parallel zu A"))
                else:
                    out.append(Vorschlag(Pmi(TOLERANZ, "ProfileOfSurface", "", wert=2 * t_lage, bezuege=list(drf),
                                             flaechen=alle(i)), "Lage und Form der Fläche zum Bezugssystem"))
    return out


GRUENDE = (
    "Größte ebene Auflage: legt das Teil auf (3 Freiheitsgrade)",
    "Zentrierung senkrecht zur Auflage: legt die Lage in der Ebene fest (2 Freiheitsgrade)",
    "Seitliche Anlage senkrecht zur Auflage (2 Freiheitsgrade)",
    "Verdrehsicherung um die Achse von B (1 Freiheitsgrad)", "Anschlag senkrecht zu A und B (1 Freiheitsgrad)",
    "Längste Zentrierung als Achse (4 Freiheitsgrade, keine ebene Auflage)",
    "Anschlag in Achsrichtung (1 Freiheitsgrad)",
    "Keine Auflage oder Zentrierung festgelegt – erst Funktionsrollen vergeben",
    "Noch {} Freiheitsgrad(e) offen – Verdrehsicherung oder Anschlag festlegen, falls die Funktion sie braucht "
    "(rotationssymmetrische Teile brauchen keine)",
    "Passung nach Funktion: {} ({})", *(name for name, _ in ROLLEN.values()), "Bezugsachse senkrecht zur Auflage", "Lage der Achse zum Bezugssystem",
    "Lage des Stifts zum Bezugssystem, Ⓜ für Montierbarkeit", "Gleichmäßiges Spiel entlang der Führung", "Ebenheit der Funktionsfläche", "Dichtheit",
    "Dichtfläche: Rauheit und Drallfreiheit", "Bezugsfläche rechtwinklig zum vorigen Bezug",
    "Weitere Auflage parallel zu A", "Lage und Form der Fläche zum Bezugssystem")
