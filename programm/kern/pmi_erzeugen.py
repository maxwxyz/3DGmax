"""Grafische PMI aus semantischer PMI erzeugen, wo die Datei keine Darstellung liefert (QIF, rein semantisches STEP).

Stufe 2 (PLAN §8.16):
- Schreibebene: aus einer gespeicherten Ansicht, die die PMI zeigt (Bildebene der Kamera), sonst die Modellebene
  (XY, XZ, YZ), deren Normale am besten zur Flaechennormale bzw. Achse des Elements passt.
- Inhalt als Vektorgrafik: Toleranzrahmen mit Feldern (Symbol, Wert, Bezuege), Bezugsdreieck mit Bezugskasten,
  Masstext mit Bezugslinie; Hinweislinie vom Element zum Rahmen. Texte stehen als Platzhalter je Feld in der Ebene.
- Anordnung ohne Ueberdeckung: Rahmen ausserhalb des Modellquaders, gierig nach aussen verschoben, bis sich kein
  Rechteck mit einem schon platzierten ueberschneidet.
Alles ist als 'erzeugt' markiert (eigene Farbe), damit es nie mit der Darstellung des Autors verwechselt wird.
"""

from __future__ import annotations

import numpy as np

from .pmi import BEZUG, HINWEIS, MASS, TOLERANZ, TOL_SYMBOL, MAT_SYMBOL, _zahl
from .praesentation import Grafik, Platzhalter

ACHSEN = np.eye(3)
BETRACHTER = np.array([1.0, -1.0, 1.0])  # Lage des Betrachters der Isoansicht (zeichnung.RICHTUNGEN["iso"])
ZEICHENBREITE = 0.72  # mittlere Zeichenbreite im Verhaeltnis zur Schrifthoehe (gegen 3D-Darstellung geprueft)


def _schwerpunkt(flaechen) -> np.ndarray | None:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    summe, gewicht = np.zeros(3), 0.0
    for f in flaechen:  # einzeln: nach innen zeigende Flaechen (Bohrungen) liefern negativen Inhalt
        g = GProp_GProps()
        brepgprop.SurfaceProperties(f, g)
        a = abs(g.Mass())
        if a > 0:
            c = g.CentreOfMass()
            summe += a * np.array([c.X(), c.Y(), c.Z()])
            gewicht += a
    return summe / gewicht if gewicht > 0 else None


def _richtung_element(flaechen) -> np.ndarray | None:
    """Normale einer ebenen Flaeche bzw. Achse eines Zylinders/Kegels (erste passende Flaeche)."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_REVERSED
    for f in flaechen:
        try:
            s = BRepAdaptor_Surface(f)
            art = s.GetType()
        except Exception:  # noqa: BLE001 - Netzflaechen ohne Geometrie
            continue
        if art == GeomAbs_Plane:
            d = s.Plane().Axis().Direction()
            v = np.array([d.X(), d.Y(), d.Z()])
            return -v if f.Orientation() == TopAbs_REVERSED else v
        if art in (GeomAbs_Cylinder, GeomAbs_Cone):
            ax = s.Cylinder().Axis() if art == GeomAbs_Cylinder else s.Cone().Axis()
            d = ax.Direction()
            return np.array([d.X(), d.Y(), d.Z()])
    return None


def modell_ebene(normale) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(x, y, n) der Modellebene, deren Normale am besten zu 'normale' passt; y moeglichst nach +Z, sonst +Y.

    Die Richtung der Normale (Vorzeichen) zeigt immer zum Betrachter der Isoansicht."""
    n = np.asarray(normale, float) if normale is not None else np.array([0.0, 0.0, 1.0])
    k = int(np.argmax(np.abs(n)))
    # Normale zum Betrachter der Standard-Isoansicht, damit der Text dort lesbar (nicht gespiegelt) ist
    z = ACHSEN[k] * (1.0 if BETRACHTER[k] >= 0 else -1.0)
    oben = ACHSEN[2] if k != 2 else ACHSEN[1]
    x = np.cross(oben, z)
    return x, oben.copy(), z


def ansicht_ebene(ansicht) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bildebene einer gespeicherten Ansicht: x nach rechts, y nach oben, n zum Betrachter."""
    n = -np.asarray(ansicht.richtung, float)
    n = n / (np.linalg.norm(n) or 1.0)
    o = np.asarray(ansicht.oben, float)
    o = o - n * (o @ n)
    if np.linalg.norm(o) < 1e-9:
        return modell_ebene(n)
    y = o / np.linalg.norm(o)
    return np.cross(y, n), y, n


# --- Inhalt ---

def felder(p) -> list[str]:
    """Texte der Felder: Toleranzrahmen (Symbol, Wert, Bezuege), Bezug (Buchstabe), sonst ein Feld."""
    if p.art == TOLERANZ:
        zone = "⌀" if ("Diameter" in p.modifikatoren or p.zone == "Diameter") else ""
        wert = f"{zone}{_zahl(p.wert)}" if p.wert is not None else "?"
        wert += MAT_SYMBOL.get(p.material, "")
        if p.zone == "Projected":
            wert += " Ⓟ" + (_zahl(p.zonen_wert) if p.zonen_wert else "")
        bez = [b.text() for b in sorted(p.bezuege, key=lambda b: b.stelle)]
        return [TOL_SYMBOL.get(p.typ, p.typ), wert] + bez
    if p.art == BEZUG:
        return [p.name or "?"]
    if p.art == MASS and p.nennwert is None:
        return [p.name or p.wert_text()]
    return [p.wert_text()]


def _feldbreiten(texte: list[str], h: float) -> list[float]:
    return [max(1.6 * h, ZEICHENBREITE * h * len(t) + 1.0 * h) for t in texte]


class _Rahmen:
    """Rechteck in der Ebene (Ursprung = linke untere Ecke) mit Feldern; Masse in mm."""

    def __init__(self, texte: list[str], h: float, kasten: bool):
        self.texte = texte
        self.h = h
        self.kasten = kasten
        self.breiten = _feldbreiten(texte, h)
        self.breite = sum(self.breiten)
        self.hoehe = 1.6 * h

    def ecken(self, ursprung, x, y) -> np.ndarray:
        return np.array([ursprung, ursprung + x * self.breite, ursprung + x * self.breite + y * self.hoehe,
                         ursprung + y * self.hoehe])

    def grafik(self, g: Grafik, ursprung, x, y):
        e = self.ecken(ursprung, x, y)
        if self.kasten:
            g.linien.append(np.vstack([e, e[:1]]))
            pos = 0.0
            for b in self.breiten[:-1]:
                pos += b
                g.linien.append(np.array([ursprung + x * pos, ursprung + x * pos + y * self.hoehe]))
        else:  # Masstext: Bezugslinie unter dem Text
            g.linien.append(np.array([e[0], e[1]]))
        pos = 0.0
        for t, b in zip(self.texte, self.breiten):
            ort = ursprung + x * (pos + 0.4 * self.h) + y * (0.3 * self.h)
            g.platzhalter.append(Platzhalter(ort, x.copy(), y.copy(), b - 0.8 * self.h, self.h, text=t))
            pos += b


def _ueberlappt(a: np.ndarray, b: np.ndarray, abstand: float) -> bool:
    """Achsparallele Quader zweier Punktmengen ueberschneiden sich (mit Mindestabstand)."""
    return bool(np.all(a.min(axis=0) - abstand <= b.max(axis=0)) and np.all(b.min(axis=0) - abstand <= a.max(axis=0)))


def _bezugsdreieck(g: Grafik, anker, richtung, quer, h):
    """Gefuelltes Dreieck auf dem Element, Spitze zeigt weg vom Element (ASME/ISO Bezugsdreieck)."""
    a = anker + quer * 0.6 * h
    b = anker - quer * 0.6 * h
    c = anker + richtung * 1.0 * h
    g.dreiecke.append((np.array([a, b, c]), np.array([[0, 1, 2]])))
    return c


def ergaenze(pmi: list, grafik: dict, modell, ansichten: list | None = None) -> dict:
    """Neue Grafiken (negative Callout-IDs) fuer PMI mit Flaechen, aber ohne vorhandene Darstellung."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    dargestellt = {i for g in grafik.values() for i in g.pmi_ids}
    offen = [p for p in pmi if p.step_id and p.step_id not in dargestellt and p.flaechen and p.art != HINWEIS]
    if not offen:
        return {}
    box = Bnd_Box()
    brepbndlib.Add(modell.form, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    lo, hi = np.array([x0, y0, z0]), np.array([x1, y1, z1])
    mitte = (lo + hi) / 2
    diag = float(np.linalg.norm(hi - lo)) or 1.0
    h = diag / 70
    quader = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    belegt: list[np.ndarray] = [np.array(g.grenzen()) for g in grafik.values() if g.erzeugt and g.grenzen()]
    neu = {}
    for i, p in enumerate(offen, 1):
        flaechen = [modell.flaechen[j] for j in sorted(p.flaechen) if j < len(modell.flaechen)]
        anker = _schwerpunkt(flaechen)
        if anker is None:
            continue
        ansicht = next((a for a in (ansichten or []) if p.step_id in a.pmi_ids and not a.eigen), None)
        x, y, n = ansicht_ebene(ansicht) if ansicht is not None else modell_ebene(_richtung_element(flaechen))
        raus = anker - mitte
        raus = raus - n * (raus @ n)  # in der Ebene nach aussen
        if np.linalg.norm(raus) < 1e-6 * diag:
            raus = x.copy()
        raus = raus / np.linalg.norm(raus)
        rahmen = _Rahmen(felder(p), h, kasten=p.art in (TOLERANZ, BEZUG))
        g = Grafik(-i, name=p.name or p.typ, fertig=True, pmi_ids={p.step_id}, erzeugt=True,
                   ebene=(anker.copy(), x, y, n))
        ziel = anker + raus * 3.0 * h
        if p.art == BEZUG:
            ziel = _bezugsdreieck(g, anker, raus, np.cross(n, raus), h)
        ursprung = _platz(rahmen, ziel, raus, x, y, quader, belegt, h)
        e = rahmen.ecken(ursprung, x, y)
        belegt.append(e)
        rahmen.grafik(g, ursprung, x, y)
        # Hinweislinie zum naechsten Punkt auf der Rahmenkante (Mitte links/rechts bzw. unten)
        andock = min((e[0] + e[3]) / 2, (e[1] + e[2]) / 2, (e[0] + e[1]) / 2, key=lambda q: np.linalg.norm(q - ziel))
        g.linien.insert(0, np.array([anker if p.art != BEZUG else ziel, andock]))
        neu[-i] = g
    return neu


def _platz(rahmen: _Rahmen, start, raus, x, y, quader, belegt, h) -> np.ndarray:
    """Linke untere Ecke: in der Schreibebene ausserhalb des Modellumrisses (projizierter Modellquader), ohne
    Ueberschneidung mit schon platzierten Rahmen. Geprueft wird in der Ebene, weil eine Ebene schraeg aus dem
    Quader herausfuehren kann und der Rahmen im Bild dann trotzdem vor dem Modell laege."""
    m = np.column_stack([x, y])
    modell = quader @ m
    andere = [b @ m for b in belegt]
    ursprung = start - x * (rahmen.breite / 2) - y * (rahmen.hoehe / 2)
    for _ in range(400):
        e = rahmen.ecken(ursprung, x, y)
        e2 = e @ m
        frei = not _ueberlappt(e2, modell, 0.5 * h) and all(not _ueberlappt(e2, b, 0.4 * h) for b in andere)
        if frei:
            return ursprung
        ursprung = ursprung + raus * 0.8 * h
    return ursprung
