"""Modelleigenschaften: Volumen, Oberflaeche, Schwerpunkt, Groesse, Anzahl, Dateikopf und Produkte (ohne Qt)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer

DICHTE_STAHL = 7.85  # g/cm3


@dataclass
class Eigenschaften:
    volumen: float  # mm3
    oberflaeche: float  # mm2
    schwerpunkt: tuple[float, float, float]
    groesse: tuple[float, float, float]  # Ausdehnung X, Y, Z in mm (achsparallel)
    kleinst: tuple[float, float, float]  # Ecke min der Box
    koerper: int
    flaechen: int

    def masse(self, dichte_g_cm3: float) -> float:
        """Masse in kg bei gegebener Dichte (g/cm3)."""
        return self.volumen * dichte_g_cm3 * 1e-6


@dataclass
class Kopf:
    beschreibung: str = ""
    name: str = ""
    zeit: str = ""
    autor: str = ""
    organisation: str = ""
    praeprozessor: str = ""
    system: str = ""
    schema: str = ""
    produkte: list[tuple[str, str, str]] = field(default_factory=list)  # (Kennung, Name, Beschreibung)


def _zaehle(form, art) -> int:
    ex, n = TopExp_Explorer(form, art), 0
    while ex.More():
        n += 1
        ex.Next()
    return n


def berechne(form) -> Eigenschaften:
    """Kennwerte einer Form (Modell oder gewaehlte Teile)."""
    vp, fp = GProp_GProps(), GProp_GProps()
    brepgprop.VolumeProperties(form, vp)
    brepgprop.SurfaceProperties(form, fp)
    volumen = vp.Mass()
    sp = vp.CentreOfMass() if abs(volumen) > 1e-12 else fp.CentreOfMass()
    box = Bnd_Box()
    brepbndlib.Add(form, box, False)  # ohne Netz, auf der exakten Geometrie
    box.SetGap(0.0)
    if box.IsVoid():
        x0 = y0 = z0 = x1 = y1 = z1 = 0.0
    else:
        x0, y0, z0, x1, y1, z1 = box.Get()
    return Eigenschaften(abs(volumen), fp.Mass(), (sp.X(), sp.Y(), sp.Z()), (x1 - x0, y1 - y0, z1 - z0),
                         (x0, y0, z0), _zaehle(form, TopAbs_SOLID), _zaehle(form, TopAbs_FACE))


def _texte(argumente: str) -> list[str]:
    """Textwerte einer Kopfzeile in Reihenfolge, Listen zusammengefasst ('a','b')."""
    out, i = [], 0
    for teil in re.finditer(r"\(([^()]*)\)|'((?:[^']|'')*)'|\$", argumente):
        if teil.group(1) is not None:
            werte = [w.replace("''", "'") for w in re.findall(r"'((?:[^']|'')*)'", teil.group(1))]
            out.append(", ".join(w for w in werte if w))
        else:
            out.append((teil.group(2) or "").replace("''", "'"))
        i += 1
    return out


def lies_kopf(pfad: str, datei=None) -> Kopf:
    """Kopf einer STEP-Datei (FILE_DESCRIPTION, FILE_NAME, FILE_SCHEMA) und Produkte aus dem Datenteil."""
    k = Kopf()
    try:
        with open(pfad, encoding="latin-1") as f:
            text = f.read(200_000)
    except OSError:
        return k
    ende = text.find("ENDSEC;")
    kopf = text[:ende if ende > 0 else len(text)]
    m = re.search(r"FILE_DESCRIPTION\s*\((.*?)\)\s*;", kopf, re.S)
    if m:
        werte = _texte(m.group(1))
        k.beschreibung = werte[0] if werte else ""
    m = re.search(r"FILE_NAME\s*\((.*?)\)\s*;", kopf, re.S)
    if m:
        werte = _texte(m.group(1)) + [""] * 7
        k.name, k.zeit, k.autor, k.organisation, k.praeprozessor, k.system = werte[:6]
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'", kopf)
    if m:
        k.schema = m.group(1).split("{")[0].strip()
    if datei is not None:
        for e in datei.of_type("PRODUCT"):
            a = e.args("PRODUCT")
            k.produkte.append(tuple(str(x) if isinstance(x, str) else "" for x in a[:3]))
    return k
