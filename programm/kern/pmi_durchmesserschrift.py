"""Grafisches Hilfsmass zwischen den Tangenten eines Zylinderrands."""

import re

import numpy as np

from . import pmi_strichschrift as schrift
from .pmi_ableiten import aus_text
from .pmi_dickenschrift import verknuepfte_randkanten
from .pmi_hinweislinie import _gefuellte_endteile
from .pmi_vorschlag import _flaeche_info
from .zeichnungsansicht import _projektion, modellkreise


def _kreisrahmen(g, modell, ids):
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Circle
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopoDS import topods

    info = _flaeche_info(modell.flaechen[next(iter(ids))])
    if not info or info[0] != "zylinder":
        return None
    kanten = verknuepfte_randkanten(g, modell, ids)
    if kanten is None:
        return None
    _, basis = _projektion(info[1]["achse"], {})
    punkte = [*g.linien, *(p for p, _ in g.dreiecke)]
    if not punkte:
        return None
    tiefen = np.vstack(punkte) @ basis[2]
    # Nur ein geschlossener Rand aller verknuepften Flaechen in der Zeichenebene.
    for gruppe in modellkreise(modell, flaechen=ids):
        for kreis in gruppe:
            for tiefe, wand in kreis.raender:
                if wand != ids or not np.all(abs(tiefen-tiefe) < 1e-4):
                    continue
                mitte = np.array([kreis.x, kreis.y, tiefe]) @ basis
                for nr in kanten:
                    k = modell.form_von_step(nr)
                    if k is None or k.ShapeType() != TopAbs_EDGE:
                        return None
                    kurve = BRepAdaptor_Curve(topods.Edge(k))
                    if kurve.GetType() != GeomAbs_Circle:
                        return None
                    rand = kurve.Circle()
                    if (np.linalg.norm(mitte-rand.Location().Coord()) > 1e-4
                            or abs(kreis.r-rand.Radius()) > 1e-4
                            or abs(basis[2] @ rand.Axis().Direction().Coord()) < 1-1e-8):
                        return None
                return (mitte, basis[0]/kreis.r, basis[1]/kreis.r, basis[2]), 2*kreis.r
    return None


def _formen(teile):
    linien = [p for p, voll in teile if not voll]
    dreiecke = [p for p, voll in teile if voll]
    if dreiecke:
        gefuellt = _gefuellte_endteile(dreiecke)
        if not gefuellt:
            return []
        linien.extend(gefuellt)
    return linien


def _tangenten(pfade):
    nah, rest = [], []
    for p, voll in pfade:
        radien = np.linalg.norm(p, axis=1)
        (nah if abs(radien.min()-1) < .02 else rest).append((p, voll))
    linien = _formen(nah)
    if len(linien) != 2 or any(len(p) != 2 for p in linien):
        return None
    start, ende = np.array([p[np.argsort(np.linalg.norm(p, axis=1))] for p in linien]).transpose(1, 0, 2)
    x = start[1]-start[0]
    if np.linalg.norm(start.sum(axis=0)) > .002 or abs(np.linalg.norm(x)-2) > .002:
        return None
    x /= np.linalg.norm(x)
    if max(abs((ende-start) @ x)) > .002:
        return None
    y = np.array([-x[1], x[0]])
    if (ende[0]-start[0]) @ y < 0:
        y = -y
    laenge = min((ende-start) @ y)
    if laenge <= .1:
        return None
    return [(np.column_stack((p @ x, p @ y)), voll) for p, voll in rest], laenge


def _masslinie(teile, laenge):
    linien = []
    spitzen = {}
    for p in _formen(teile):
        if len(p) == 2 and np.ptp(p[:, 1]) < .002:
            linien.append((min(p[:, 0]), max(p[:, 0]), p[:, 1].mean()))
            continue
        if len(p) != 4 or np.linalg.norm(p[0]-p[-1]) > .002:
            return None
        i = np.argmin(abs(abs(p[:3, 0])-1))
        x, y = p[i]
        seite = np.sign(x)
        a, b = np.delete(p[:3], i, axis=0) - p[i]
        if (abs(abs(x)-1) > .002 or not .01 < -seite*a[0] < .5 or abs(a[0]-b[0]) > .002
                or a[1]*b[1] >= 0 or abs(a[1]+b[1]) > .002 or seite in spitzen):
            return None
        spitzen[seite] = y
    if len(spitzen) != 2 or not linien:
        return None
    linien.sort()
    niveau = spitzen[1]
    if (not 0 < niveau < laenge+.002 or abs(niveau-spitzen[-1]) > .002
            or any(abs(y-niveau) > .002 for _, _, y in linien)
            or any(abs(a[1]-b[0]) > .002 for a,b in zip(linien, linien[1:]))
            or linien[0][0] > -.998 or linien[-1][1] < .998):
        return None
    return niveau


def _schriftfeld(rest, laenge):
    # Die zusammenhaengende Masslinie in Breitenrichtung von der Schrift trennen.
    gruppen = []
    ende = -np.inf
    for p, voll in sorted(rest, key=lambda paar: paar[0][:, 0].min()):
        if p[:, 0].min() > ende+.002:
            gruppen.append([])
        gruppen[-1].append((p, voll))
        ende = max(ende, p[:, 0].max())
    for i, teile in enumerate(gruppen):
        if i not in (0, len(gruppen)-1) or len(gruppen) < 2:
            continue
        punkte = np.vstack([p for p, _ in teile])
        if punkte[:, 0].min() > -.998 or punkte[:, 0].max() < .998:
            continue
        niveau = _masslinie(teile, laenge)
        if niveau is None:
            return None
        feld = [teil for j, gruppe in enumerate(gruppen) if j != i for teil in gruppe]
        text = np.vstack([p for p, _ in feld])
        luecke = max(text[:, 0].min()-punkte[:, 0].max(), punkte[:, 0].min()-text[:, 0].max())
        if 0 < luecke < np.ptp(text[:, 1]) and text[:, 1].min() < niveau < text[:, 1].max():
            return feld
    return None


def _lesung(feld, faktor, durchmesser):
    hoehe = np.ptp(np.vstack([p for p, _ in feld])[:, 1])
    wort = ""
    for aufloesung in (100, 150):
        maske, _ = schrift._gesamtbild(feld, aufloesung/hoehe)
        if maske is None:
            return None
        werte = {schrift._masszeile(b) for b in (maske, maske[::-1], maske[:, ::-1], maske[::-1, ::-1])}
        lesbar = [w for w in werte if re.fullmatch(r"\((?:\d+|\d*[.,]\d+)\)", w)]
        if len(lesbar) != 1 or (wort and wort != lesbar[0]):
            return None
        wort = lesbar[0]
    zahl = wort[1:-1].replace(",", ".")
    if re.fullmatch(r"[01689]+", zahl) and zahl != zahl[::-1].translate(schrift._HALBDREHUNG):
        return None
    daten = aus_text([wort], faktor)
    rundung = .5*faktor*10**-len(zahl.partition(".")[2])
    if not daten or abs(daten["nennwert"]-durchmesser) > rundung+1e-6:
        return None
    return wort, dict(daten, typ="Size_Diameter")


def tangentendurchmesser(g, modell, ids):
    """Den geklammerten Wert nur mit beiden belegten Tangenten und Masspfeilen uebernehmen."""
    ids = frozenset(ids)
    if (not g.textfaktor or not ids or min(ids) < 0 or max(ids) >= len(modell.flaechen)
            or not schrift._lesbar(g)):
        return None
    rahmen = _kreisrahmen(g, modell, ids)
    if rahmen is None:
        return None
    ebene, durchmesser = rahmen
    tangenten = _tangenten(schrift._pfade(g, ebene))
    if tangenten and (feld := _schriftfeld(*tangenten)):
        return _lesung(feld, g.textfaktor, durchmesser)
    return None
