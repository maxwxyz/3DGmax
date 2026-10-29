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

Wellen und andere Drehteile (Bezug A ist eine Achse): zwei koaxiale Lagersitze bilden die gemeinsame Bezugsachse A-B
(ISO 5459, gemeinsamer Bezug; A und B je an einem Lagersitz, im Toleranzrahmen "A-B"), ein Anschlag in Achsrichtung
wird C. Koaxiale Sitze bekommen Rundlauf zu A-B, Anschlaege Gesamtplanlauf, Passfedernuten Symmetrie. Startwerte:
- Lagersitz k6 (Umfangslast am Innenring, normale Last; Gehaeuse H7), Durchmesser IT6 nach den Waelzlagerherstellern,
  Zylinderform IT5/2, Rundlauf IT5; Schulter neben einem Lagersitz Planlauf IT5.
- Dichtsitz fuer Radialwellendichtringe h11 (Gehaeuse H8), Ra 0,2 ... 0,8 um, Rz 1 ... 4 um, drallfrei (DIN 3760 /
  ISO 6194-1, Herstellerangaben).
- Nabensitz H7/k6 (Zahnrad, Kupplung mit Passfeder), Rundlauf IT6.
- Passfedernut (DIN 6885-1, normale Passung): Breite N9 in der Welle, JS9 in der Nabe; Symmetrie IT9 der Breite.
- Sicherungsringnut (DIN 471 Welle, DIN 472 Bohrung): Nutbreite H13; Nutdurchmesser h10/h11/h12 bzw. H11/H12 je nach
  Groesse (Startwert, Tabelle der Norm pruefen); Lage der tragenden Flanke zum Anschlag C mit Plusabmass IT11, damit
  Lager und Ring immer montierbar sind (das Axialspiel folgt aus der Toleranzkette).

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
    "lagersitz": ("Lagersitz (Wälzlager)", ("H7", "k6")),
    "dichtsitz": ("Dichtsitz (Radialwellendichtring)", ("H8", "h11")),
    "nabensitz": ("Nabensitz (Zahnrad, Kupplung)", ("H7", "k6")),
    "passfedernut": ("Passfedernut (DIN 6885)", ("JS9", "N9")),  # (Nabe, Welle)
    "sicherungsringnut": ("Sicherungsringnut (DIN 471/472)", ("H12", "h12")),
    "frei": ("Freifläche", None),
}
# IT-Grade der Startwerte je Rolle: (Form, Richtung/Lage)
GRADE = {"auflage": (6, 7), "zentrierung": (6, 7), "fuehrung": (6, 7), "presssitz": (6, 7),
         "verdrehsicherung": (7, 8), "dichtung": (5, 7), "anschlag": (7, 8), "lagersitz": (5, 5),
         "dichtsitz": (6, 7), "nabensitz": (6, 6), "passfedernut": (8, 9), "sicherungsringnut": (8, 11)}
FORM_TEILER = {"lagersitz": 2}  # Zylinderform IT5/2 am Lagersitz
SITZE = ("lagersitz", "dichtsitz", "nabensitz")  # Drehteil: Rundlauf zur Bezugsachse
LAGERSCHULTER = 5  # IT-Grad des Planlaufs einer Schulter neben einem Lagersitz


@dataclass
class BezugVorschlag:
    buchstabe: str
    flaeche: int
    element: str  # "ebene" oder "achse"
    freiheitsgrade: int  # gesperrte Freiheitsgrade
    grund: str
    gemeinsam: str = ""  # Teil eines gemeinsamen Bezugs, z. B. "A-B"

    @property
    def name(self) -> str:
        """Name im Toleranzrahmen (gemeinsamer Bezug oder Buchstabe)."""
        return self.gemeinsam or self.buchstabe


@dataclass
class Bezugssystem:
    bezuege: list[BezugVorschlag] = field(default_factory=list)
    offen: int = 6  # nicht gesperrte Freiheitsgrade
    hinweise: list[str] = field(default_factory=list)

    def drf(self) -> list[BezugsRef]:
        """Bezuege im Toleranzrahmen: ein gemeinsamer Bezug (A-B) belegt eine Stelle."""
        namen = list(dict.fromkeys(b.name for b in self.bezuege))
        return [BezugsRef(n, k) for k, n in enumerate(namen, 1)]


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
    mitte = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    if art == "ebene":
        return {"art": "ebene", "richtung": np.array(d["normale"]), "punkt": np.array(d["punkt"]),
                "inhalt": pr.Mass(), "groesse": ausdehnung, "mitte": mitte}
    ax = BRepAdaptor_Surface(flaeche, True).Cylinder().Axis()
    r = ax.Direction()
    p = ax.Location()
    return {"art": "zylinder", "richtung": np.array([r.X(), r.Y(), r.Z()]), "punkt": np.array([p.X(), p.Y(), p.Z()]),
            "inhalt": pr.Mass(), "groesse": 2 * d["r"], "bohrung": d["bohrung"], "laenge": ausdehnung,
            "mitte": mitte}


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
    g = dict(g, inhalt=inhalt, mitte=np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]))
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


def startwerte(modell, i: int, rolle: str, gruppen: dict | None = None, rollen: dict | None = None) -> dict:
    """Startwerte eines Elements ohne Eingabe: Formtoleranz, Lagetoleranz (IT-Grad bei der Groesse) und Passung;
    rollen: ein Anschlag neben einem Lagersitz ist eine Lagerschulter (Planlauf IT5)."""
    g = _geo(modell, i, gruppen)
    if g is None or rolle == "frei":
        return {}
    form, lage = GRADE.get(rolle, (7, 8))
    if rolle == "anschlag" and rollen and _neben_lagersitz(modell, i, rollen, gruppen or {}):
        lage = LAGERSCHULTER
    groesse = g["groesse"]
    if rolle == "passfedernut":  # Werte an der Nutbreite
        nut = passfedernut(modell, i)
        groesse = nut["breite"] if nut else groesse
    return {"form": _it(form, groesse) / FORM_TEILER.get(rolle, 1), "lage": _it(lage, groesse), "grad": (form, lage),
            "passung": _klasse(modell, i, rolle, g)}


def _klasse(modell, i: int, rolle: str, g: dict) -> str:
    """Toleranzklasse des Passmasses: am Zylinder aus der Rolle (Bohrung bzw. Welle), an der Passfedernut die Breite
    (Nabe bzw. Welle), an der Sicherungsringnut der Nutdurchmesser nach Groesse."""
    passung = ROLLEN[rolle][1]
    if rolle == "passfedernut":
        nut = passfedernut(modell, i)
        return (passung[0] if nut["nabe"] else passung[1]) if nut else ""
    if not passung or g["art"] != "zylinder":
        return ""
    if rolle == "sicherungsringnut":  # DIN 471: h10 bis Welle 10, h11 bis 22, darueber h12; DIN 472: H11 bis 22
        d = g["groesse"]
        return ("H11" if d <= 22 else "H12") if g["bohrung"] else ("h10" if d < 10 else "h11" if d < 22 else "h12")
    return passung[0] if g["bohrung"] else passung[1]


def _neben_lagersitz(modell, i: int, rollen: dict, gruppen: dict) -> bool:
    lager = {f for e, r in rollen.items() if r == "lagersitz" for f in gruppen.get(e, (e,))}
    return bool(lager & set(_nachbarn(modell, i)))


def _nachbarn(modell, i: int) -> list[int]:
    """Flaechen mit gemeinsamer Kante."""
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer

    def kanten(f):
        out, ex = [], TopExp_Explorer(f, TopAbs_EDGE)
        while ex.More():
            out.append(ex.Current())
            ex.Next()
        return out
    eigene = kanten(modell.flaechen[i])
    return [j for j, f in enumerate(modell.flaechen) if j != i
            and any(k.IsSame(e) for k in kanten(f) for e in eigene)]


def passfedernut(modell, i: int) -> dict | None:
    """Passfedernut am Nutgrund i: Seitenwaende (zwei parallele Ebenen senkrecht zum Grund), Breite, Zylinder der Welle
    bzw. Nabe (Achse quer zur Grundnormalen) und ob die Nut in einer Nabe liegt; None, wenn i kein Nutgrund ist."""
    grund = _geometrie(modell.flaechen[i])
    if grund is None or grund["art"] != "ebene":
        return None
    n = grund["richtung"]
    nachbarn = {j: g for j in _nachbarn(modell, i) if (g := _geometrie(modell.flaechen[j])) is not None}
    waende = [j for j, g in nachbarn.items() if g["art"] == "ebene" and _senkrecht(g["richtung"], n)]
    paar = next(((a, b) for a in waende for b in waende if a < b and float(
        nachbarn[a]["richtung"] @ nachbarn[b]["richtung"]) < -0.9999), None)
    if paar is None:
        return None
    a, b = nachbarn[paar[0]], nachbarn[paar[1]]
    zylinder = next((j for w in paar for j in _nachbarn(modell, w) if (g := _geometrie(modell.flaechen[j]))
                     and g["art"] == "zylinder" and _senkrecht(g["richtung"], n)), None)
    nabe = zylinder is not None and _geometrie(modell.flaechen[zylinder])["bohrung"]
    return {"waende": paar, "breite": abs(float((b["punkt"] - a["punkt"]) @ a["richtung"])), "zylinder": zylinder,
            "nabe": bool(nabe)}


def ringnut(modell, i: int) -> dict | None:
    """Sicherungsringnut am Nutgrund i (Zylinder): Flanken (zwei Ebenen senkrecht zur Achse) und Nutbreite."""
    g = _geometrie(modell.flaechen[i])
    if g is None or g["art"] != "zylinder":
        return None
    flanken = [j for j in _nachbarn(modell, i) if (f := _geometrie(modell.flaechen[j])) is not None
               and f["art"] == "ebene" and _parallel(f["richtung"], g["richtung"])]
    if len(flanken) != 2:
        return None
    a, b = (_geometrie(modell.flaechen[j]) for j in flanken)
    return {"flanken": tuple(sorted(flanken)), "breite": abs(float((b["punkt"] - a["punkt"]) @ g["richtung"]))}


def _parallel(a, b) -> bool:
    return abs(abs(float(a @ b)) - 1) < 1e-4


def _senkrecht(a, b) -> bool:
    return abs(float(a @ b)) < 1e-4


def _koaxial(a: dict, b: dict) -> bool:
    """Zwei Zylinder auf derselben Achse."""
    q = b["punkt"] - a["punkt"]
    return _parallel(a["richtung"], b["richtung"]) and \
        np.linalg.norm(q - a["richtung"] * float(q @ a["richtung"])) < 1e-3


def _gemeinsame_achse(geo: dict, sitze: list[int]) -> tuple[int, int] | None:
    """Zwei koaxiale Sitze mit dem groessten Abstand (laengste Bezugsachse), in Achsrichtung geordnet."""
    paare = [(a, b) for a in sitze for b in sitze if a < b and _koaxial(geo[a], geo[b])]
    if not paare:
        return None
    lage = lambda i, r: float(geo[i]["mitte"] @ r)  # noqa: E731
    a, b = max(paare, key=lambda p: abs(lage(p[0], geo[p[0]]["richtung"]) - lage(p[1], geo[p[0]]["richtung"])))
    r = geo[a]["richtung"]
    return (a, b) if lage(a, r) <= lage(b, r) else (b, a)


def bezugssystem(modell, rollen: dict[int, str], gruppen: dict | None = None,
                 vorgabe: dict[int, str] | None = None) -> Bezugssystem:
    """Bezugssystem A|B|C aus den Funktionsrollen (3-2-1); Begruendung je Bezug, Hinweis bei offenen Freiheitsgraden.
    vorgabe: Element -> Buchstabe von Hand ("A", "B", "C"); dann gilt nur diese Zuordnung."""
    if vorgabe:
        return _bezugssystem_von_hand(modell, rollen, gruppen, vorgabe)
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
        gemeinsam = _gemeinsame_achse(geo, achsen("lagersitz"))
        zentr = achsen("lagersitz", "zentrierung", "presssitz", "fuehrung")
        if gemeinsam:  # Welle: Bezugsachse durch beide Lagersitze (ISO 5459 gemeinsamer Bezug)
            s.bezuege += [BezugVorschlag(next(buchstaben), gemeinsam[0], "achse", 4, "Gemeinsame Bezugsachse A-B aus "
                                         "zwei koaxialen Lagersitzen (4 Freiheitsgrade)", "A-B"),
                          BezugVorschlag(next(buchstaben), gemeinsam[1], "achse", 0,
                                         "Zweiter Lagersitz der gemeinsamen Bezugsachse A-B", "A-B")]
        elif zentr:
            s.bezuege.append(BezugVorschlag(next(buchstaben), zentr[0], "achse", 4,
                                            "Längste Zentrierung als Achse (4 Freiheitsgrade, keine ebene Auflage)"))
        if s.bezuege:
            na = geo[s.bezuege[0].flaeche]["richtung"]
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


def _bezugssystem_von_hand(modell, rollen, gruppen, vorgabe: dict[int, str]) -> Bezugssystem:
    """Bezuege in der Reihenfolge der Buchstaben; gesperrte Freiheitsgrade wie beim Vorschlag (A Ebene 3 / Achse 4,
    B 2 - parallele Achse zu einer Achse A nur 1, C 1)."""
    s = Bezugssystem()
    vorher = []
    for erste, buchstabe in sorted(vorgabe.items(), key=lambda e: e[1]):
        g = _geo(modell, erste, gruppen) if erste in rollen else None
        if g is None or buchstabe not in "ABC" or not buchstabe:
            continue
        element = "ebene" if g["art"] == "ebene" else "achse"
        if not vorher:
            fg = 3 if element == "ebene" else 4
        elif len(vorher) == 1:
            fg = 1 if element == "achse" and vorher[0][0] == "achse" and _parallel(g["richtung"], vorher[0][1]) else 2
        else:
            fg = 1
        s.bezuege.append(BezugVorschlag(buchstabe, erste, element, fg, "Von Hand als Bezug festgelegt"))
        vorher.append((element, g["richtung"]))
        a = s.bezuege[0]
        if len(s.bezuege) == 2 and element == "achse" and a.element == "achse" and \
                rollen.get(a.flaeche) == rollen.get(erste) == "lagersitz" and \
                _koaxial(_geo(modell, a.flaeche, gruppen), g):  # zwei Lagersitze: gemeinsame Bezugsachse
            a.gemeinsam = s.bezuege[1].gemeinsam = f"{a.buchstabe}-{buchstabe}"
            s.bezuege[1].freiheitsgrade = 0
    s.offen = max(0, 6 - sum(b.freiheitsgrade for b in s.bezuege))
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
    k = _Kontext(modell, rollen, system or bezugssystem(modell, rollen, gruppen), gruppen or {})
    _tolerierung(k)
    for v in k.out:  # von Hand gesetzte Werte des Elements
        element, eigene = k.herkunft.get(id(v), (-1, False))
        w = (werte or {}).get(element, {}) if eigene else {}
        if v.pmi.art == TOLERANZ and w.get("toleranz") is not None:
            v.pmi.wert = float(w["toleranz"])
        if v.pmi.art == MASS and w.get("passung"):
            v.pmi.passung = w["passung"]
    return k.out


class _Kontext:
    """Gemeinsame Daten der Tolerierung: Bezugssystem, Toleranzrahmen, Bezugsachse eines Drehteils, Ergebnis und je
    Vorschlag das Element, dessen von Hand gesetzte Werte gelten."""

    def __init__(self, modell, rollen: dict[int, str], system: Bezugssystem, gruppen: dict):
        self.modell, self.rollen, self.system, self.gruppen = modell, rollen, system, gruppen
        self.drf = system.drf()
        self.bezug_von = {b.flaeche: b for b in system.bezuege}
        erster = system.bezuege[0] if system.bezuege else None
        self.achse = _geo(modell, erster.flaeche, gruppen) if erster and erster.element == "achse" else None
        self.out: list[Vorschlag] = []
        self.herkunft: dict[int, tuple[int, bool]] = {}

    def alle(self, i: int) -> set:
        return set(self.gruppen.get(i, (i,)))

    def vorher(self, i: int) -> list[BezugsRef]:
        """Bezuege vor dem eigenen (alle, wenn das Element kein Bezug ist)."""
        b = self.bezug_von.get(i)
        return self.drf[:[r.name for r in self.drf].index(b.name)] if b else list(self.drf)

    def dazu(self, pmi: Pmi, grund: str, element: int | None = None, eigene: bool = True):
        v = Vorschlag(pmi, grund)
        self.out.append(v)
        if element is not None:
            self.herkunft[id(v)] = (element, eigene)


def _tolerierung(k: _Kontext):
    for b in k.system.bezuege:
        k.dazu(Pmi(BEZUG, "Datum", b.buchstabe, flaechen=k.alle(b.flaeche)), b.grund)
    for i, rolle in sorted(k.rollen.items()):
        g = _geo(k.modell, i, k.gruppen)
        if g is None or rolle == "frei":
            continue
        if rolle == "passfedernut":
            _passfedernut(k, i)
        elif rolle == "sicherungsringnut":
            _ringnut(k, i, g)
        elif not _drehteil(k, i, rolle, g):
            (_zylinder if g["art"] == "zylinder" else _ebene)(k, i, rolle, g)
        if rolle == "dichtsitz" and g["art"] == "zylinder":
            k.dazu(Pmi(HINWEIS, "Note", "", nur_grafik_text="Ra 0,2 … 0,8 µm, Rz 1 … 4 µm, drallfrei",
                       flaechen=k.alle(i)), "Lauffläche des Radialwellendichtrings: Rauheit, drallfrei geschliffen "
                                            "(DIN 3760)")


def _passmass(k: _Kontext, i: int, rolle: str, g: dict):
    klasse = _klasse(k.modell, i, rolle, g)
    if klasse:
        grund = tr("Sicherungsringnut: Nutdurchmesser {} nach Größe (DIN 471/472)").format(klasse) \
            if rolle == "sicherungsringnut" else \
            tr("Passung nach Funktion: {} ({})").format(tr(ROLLEN[rolle][0]), "/".join(ROLLEN[rolle][1]))
        k.dazu(Pmi(MASS, "Size_Diameter", "", nennwert=round(g["groesse"], 4), passung=klasse, flaechen=k.alle(i)),
               grund, i)


def _drehteil(k: _Kontext, i: int, rolle: str, g: dict) -> bool:
    """Drehteil (Bezug A ist eine Achse): Sitze auf der Achse mit Rundlauf, Anschlaege senkrecht dazu mit
    Gesamtplanlauf zum ersten Bezug (A-B); False, wenn die Regel nicht passt."""
    a = k.achse
    if a is None or not k.drf:
        return False
    start = startwerte(k.modell, i, rolle, k.gruppen, k.rollen)
    if g["art"] == "zylinder" and rolle in SITZE and _koaxial(a, g):
        _passmass(k, i, rolle, g)
        if rolle == "lagersitz":
            k.dazu(Pmi(TOLERANZ, "Cylindricity", "", wert=round(start["form"], 4), flaechen=k.alle(i)),
                   "Lagersitz: Zylinderform IT5/2 (Wälzlagerhersteller)", i)
        if k.bezug_von.get(i) is None or k.bezug_von[i].gemeinsam:
            k.dazu(Pmi(TOLERANZ, "CircularRunout", "", wert=start["lage"], bezuege=k.drf[:1], flaechen=k.alle(i)),
                   "Rundlauf zur Bezugsachse: Sitz läuft rund zu den Lagern", i)
        return True
    if g["art"] == "ebene" and rolle in ("anschlag", "auflage") and _parallel(g["richtung"], a["richtung"]):
        schulter = rolle == "anschlag" and _neben_lagersitz(k.modell, i, k.rollen, k.gruppen)
        k.dazu(Pmi(TOLERANZ, "TotalRunout", "", wert=start["lage"], bezuege=k.drf[:1], flaechen=k.alle(i)),
               "Lagerschulter: Gesamtplanlauf IT5 zur Bezugsachse" if schulter else
               "Anschlag: Gesamtplanlauf zur Bezugsachse", i)
        return True
    return False


def _passfedernut(k: _Kontext, i: int):
    """Breite mit Passung N9 bzw. JS9 an den Seitenwaenden, Symmetrie der Mittelebene zur Bezugsachse."""
    nut = passfedernut(k.modell, i)
    if nut is None:
        return
    waende, b = set(nut["waende"]), nut["breite"]
    k.dazu(Pmi(MASS, "Size_Thickness", "", nennwert=round(b, 4), passung=_klasse(k.modell, i, "passfedernut", {}),
               flaechen=waende), "Passfedernut: Breite nach DIN 6885-1 (Welle N9, Nabe JS9)", i)
    if k.drf:
        k.dazu(Pmi(TOLERANZ, "Symmetry", "", wert=_it(GRADE["passfedernut"][1], b), bezuege=k.drf[:1],
                   flaechen=waende),
               "Mittelebene der Nut symmetrisch zur Bezugsachse (Passfeder trägt gleichmäßig)", i)


def _ringnut(k: _Kontext, i: int, g: dict):
    """Nutdurchmesser und -breite (DIN 471/472), Lage der tragenden Flanke zum ebenen Anschlagbezug."""
    _passmass(k, i, "sicherungsringnut", g)
    nut = ringnut(k.modell, i)
    if nut is None:
        return
    k.dazu(Pmi(MASS, "Size_Thickness", "", nennwert=round(nut["breite"], 4), passung="H13",
               flaechen=set(nut["flanken"])), "Sicherungsringnut: Nutbreite H13 (DIN 471/472)", i, eigene=False)
    anschlag = next((b for b in k.system.bezuege if b.element == "ebene"
                     and _parallel(_geo(k.modell, b.flaeche, k.gruppen)["richtung"], g["richtung"])), None)
    if anschlag is None:
        return
    ebene = _geo(k.modell, anschlag.flaeche, k.gruppen)
    abstand = {j: abs(float((_geometrie(k.modell.flaechen[j])["punkt"] - ebene["punkt"]) @ ebene["richtung"]))
               for j in nut["flanken"]}
    flanke = min(abstand, key=abstand.get)
    k.dazu(Pmi(MASS, "Location_LinearDistance", "", nennwert=round(abstand[flanke], 4),
               oben=_it(GRADE["sicherungsringnut"][1], abstand[flanke]), unten=0.0,
               flaechen={flanke} | k.alle(anschlag.flaeche)),
           "Tragende Nutflanke zum Anschlag: Plusabmaß, damit Lager und Ring immer passen (Axialspiel aus der "
           "Toleranzkette)", i, eigene=False)


def _zylinder(k: _Kontext, i: int, rolle: str, g: dict):
    """Passmass, Rechtwinkligkeit bzw. Position zum Bezugssystem, Zylinderform an Fuehrungen."""
    form, lage = GRADE.get(rolle, (7, 8))
    vorher = k.vorher(i)
    _passmass(k, i, rolle, g)
    t = _it(lage, g["groesse"])
    material = "M" if rolle == "verdrehsicherung" else ""
    grund = "Lage des Stifts zum Bezugssystem, Ⓜ für Montierbarkeit" if material else \
        "Lage der Achse zum Bezugssystem"
    if i in k.bezug_von and len(vorher) == 1:
        k.dazu(Pmi(TOLERANZ, "Perpendicularity", "", wert=t, modifikatoren=["Diameter"], bezuege=vorher[:1],
                   flaechen=k.alle(i)), "Bezugsachse senkrecht zur Auflage", i)
    elif vorher:  # tertiaerer Bezug bzw. kein Bezug: Lage zu den vorigen Bezuegen
        k.dazu(Pmi(TOLERANZ, "Position", "", wert=t, material=material, modifikatoren=["Diameter"], bezuege=vorher,
                   flaechen=k.alle(i)), grund, i)
    if rolle == "fuehrung":
        k.dazu(Pmi(TOLERANZ, "Cylindricity", "", wert=_it(form, g["groesse"]), flaechen=k.alle(i)),
               "Gleichmäßiges Spiel entlang der Führung", i)


def _ebene(k: _Kontext, i: int, rolle: str, g: dict):
    """Ebenheit an Auflagen und Dichtflaechen, Richtung bzw. Profil zum Bezugssystem."""
    form, lage = GRADE.get(rolle, (7, 8))
    t_form, t_lage = _it(form, g["groesse"]), _it(lage, g["groesse"])
    b = k.bezug_von.get(i)
    vorher = k.vorher(i)
    if rolle in ("auflage", "dichtung") or (b is not None and b.freiheitsgrade == 3):
        k.dazu(Pmi(TOLERANZ, "Flatness", "", wert=t_form, flaechen=k.alle(i)),
               "Ebenheit der Funktionsfläche" if rolle != "dichtung" else "Dichtheit", i)
    if rolle == "dichtung":
        k.dazu(Pmi(HINWEIS, "Note", "", nur_grafik_text="Ra ≤ 0,8 µm, drallfrei", flaechen=k.alle(i)),
               "Dichtfläche: Rauheit und Drallfreiheit", i)
    if b is not None and vorher:
        k.dazu(Pmi(TOLERANZ, "Perpendicularity", "", wert=t_lage, bezuege=vorher[:1], flaechen=k.alle(i)),
               "Bezugsfläche rechtwinklig zum vorigen Bezug", i)
    elif b is None and k.drf:
        erste = k.system.bezuege[0]
        parallel_a = erste.element == "ebene" and _parallel(
            g["richtung"], _geo(k.modell, erste.flaeche, k.gruppen)["richtung"])
        if rolle == "auflage" and parallel_a:
            k.dazu(Pmi(TOLERANZ, "Parallelism", "", wert=t_lage, bezuege=k.drf[:1], flaechen=k.alle(i)),
                   "Weitere Auflage parallel zu A", i)
        else:
            k.dazu(Pmi(TOLERANZ, "ProfileOfSurface", "", wert=2 * t_lage, bezuege=list(k.drf), flaechen=k.alle(i)),
                   "Lage und Form der Fläche zum Bezugssystem", i)


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
    "Weitere Auflage parallel zu A", "Lage und Form der Fläche zum Bezugssystem", "Von Hand als Bezug festgelegt",
    "Gemeinsame Bezugsachse A-B aus zwei koaxialen Lagersitzen (4 Freiheitsgrade)",
    "Zweiter Lagersitz der gemeinsamen Bezugsachse A-B", "Lagersitz: Zylinderform IT5/2 (Wälzlagerhersteller)",
    "Rundlauf zur Bezugsachse: Sitz läuft rund zu den Lagern", "Lagerschulter: Gesamtplanlauf IT5 zur Bezugsachse",
    "Anschlag: Gesamtplanlauf zur Bezugsachse", "Passfedernut: Breite nach DIN 6885-1 (Welle N9, Nabe JS9)",
    "Mittelebene der Nut symmetrisch zur Bezugsachse (Passfeder trägt gleichmäßig)",
    "Sicherungsringnut: Nutbreite H13 (DIN 471/472)",
    "Tragende Nutflanke zum Anschlag: Plusabmaß, damit Lager und Ring immer passen (Axialspiel aus der Toleranzkette)",
    "Lauffläche des Radialwellendichtrings: Rauheit, drallfrei geschliffen (DIN 3760)")
