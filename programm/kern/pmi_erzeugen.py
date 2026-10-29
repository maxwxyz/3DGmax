"""Grafische PMI aus semantischer PMI erzeugen, wo die Datei keine Darstellung liefert (QIF, rein semantisches STEP).

Stufe 2 (PLAN §8.16):
- Schreibebene: aus einer gespeicherten Ansicht, die die PMI zeigt (Bildebene der Kamera), sonst die Modellebene
  (XY, XZ, YZ), deren Normale am besten zur Flaechennormale bzw. Achse des Elements passt.
- Inhalt als Vektorgrafik: Toleranzrahmen mit Feldern (Symbol, Wert, Bezuege), Bezugsdreieck mit Bezugskasten,
  Masstext mit Bezugslinie; Hinweislinie vom Element zum Rahmen. Texte stehen als Platzhalter je Feld in der Ebene.
- Anordnung ohne Ueberdeckung: Rahmen ausserhalb des Modellquaders, gierig nach aussen verschoben, bis sich kein
  Rechteck mit einem schon platzierten ueberschneidet.
Stufe 3: Abstands- und Dickenmasse zwischen zwei parallelen Ebenen als Masslinie mit Masshilfslinien und Pfeilen
ausserhalb des Modells (Schreibebene enthaelt die Massrichtung, Text ueber der Masslinie in Leserichtung); Hinweislinien
enden mit Pfeil am naechsten Punkt der Flaeche statt am Flaechenschwerpunkt (bei Bohrungen sonst auf der Achse).
Drehteile (Modell entlang einer Achse mindestens doppelt so lang wie quer): Angaben an Elementen auf dieser Achse
(Zylinder, Planflaechen) stehen wie in der Zeichnung in der Ebene durch die Achse und quer zur Achse ueber bzw. unter
dem Teil, statt im Querschnitt (dort lagen sie im Gesamtbild alle hintereinander).
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


def _pfeil(g: Grafik, spitze, richtung, h):
    """Gefuellter Pfeil: Spitze am Punkt, zeigt in 'richtung' (Laenge h)."""
    r = np.asarray(richtung, float)
    r = r / (np.linalg.norm(r) or 1.0)
    quer = np.cross(r, g.ebene[3]) if g.ebene is not None else np.cross(r, [0.0, 0.0, 1.0])
    quer = quer / (np.linalg.norm(quer) or 1.0)
    fuss = spitze - r * h
    g.dreiecke.append((np.array([spitze, fuss + quer * 0.3 * h, fuss - quer * 0.3 * h]), np.array([[0, 1, 2]])))


def _naechster_punkt(flaechen, ziel) -> np.ndarray | None:
    """Punkt der Flaechen, der dem Ziel am naechsten liegt (Ende der Hinweislinie)."""
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.TopoDS import TopoDS_Compound
    from OCC.Core.gp import gp_Pnt
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for f in flaechen:
        b.Add(c, f)
    d = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, ziel))).Vertex(), c)
    if not d.IsDone() or d.NbSolution() == 0:
        return None
    q = d.PointOnShape2(1)
    return np.array([q.X(), q.Y(), q.Z()])


def _ebenen_paar(flaechen):
    """((Punkt, Normale), (Punkt, Normale)) zweier paralleler Ebenen oder None."""
    from .plausibilitaet import _ebene
    if len(flaechen) != 2:
        return None
    e = [_ebene(f) for f in flaechen]
    if None in e or abs(abs(float(e[0][1] @ e[1][1])) - 1) > 1e-6:
        return None
    a, b = (_schwerpunkt([f]) for f in flaechen)
    return (a, e[0][1]), (b, e[1][1])


def _masslinie(p, flaechen, quader, mitte, belegt, h, nr) -> Grafik | None:
    """Abstandsmass zwischen zwei parallelen Ebenen: Masshilfslinien, Masslinie mit Pfeilen, Text darueber."""
    paar = _ebenen_paar(flaechen)
    if paar is None:
        return None
    (c1, u), (c2, _) = paar
    u = u / np.linalg.norm(u)
    kandidaten = [a * (1.0 if a @ BETRACHTER >= 0 else -1.0) for a in ACHSEN if abs(a @ u) < 1e-3]
    if not kandidaten:
        return None  # Massrichtung schraeg zu allen Modellebenen: Hinweislinie wie bisher
    n = max(kandidaten, key=lambda a: abs(a @ BETRACHTER))
    c2 = c2 - n * float((c2 - c1) @ n)  # in die Schreibebene durch c1
    d = float((c2 - c1) @ u)
    y = np.cross(n, u)
    if float((c1 + c2) / 2 @ y - mitte @ y) < 0:
        y = -y  # nach aussen
    rand = float(max((q - c1) @ y for q in quader))
    _, y_ref, _ = modell_ebene(n)
    u_text = u if float(np.cross(n, u) @ y_ref) >= 0 else -u  # Text von links nach rechts lesbar
    text = p.wert_text()
    breite = ZEICHENBREITE * h * len(text) + h
    for k in range(40):  # Abstand nach aussen, bis keine schon platzierte Grafik ueberdeckt wird
        hoehe = rand + (2.5 + 2.0 * k) * h
        a, b = c1 + y * hoehe, c1 + u * d + y * hoehe
        mitte_linie = (a + b) / 2
        ecken = np.array([a, b, mitte_linie - u_text * breite / 2 + y * 1.6 * h,
                          mitte_linie + u_text * breite / 2 + y * 1.6 * h])
        m = np.column_stack([u, y])
        if all(not _ueberlappt(ecken @ m, e @ m, 0.4 * h) for e in belegt):
            break
    g = Grafik(-nr, name=p.name or p.typ, fertig=True, pmi_ids={p.step_id}, erzeugt=True,
               ebene=(c1.copy(), u_text, np.cross(n, u_text), n))
    for fuss, ende in ((c1, a), (c2, b)):
        g.linien.append(np.array([fuss + y * 0.5 * h, ende + y * 0.8 * h]))  # Masshilfslinie
    g.linien.append(np.array([a, b]))  # Masslinie
    richtung = (b - a) / (np.linalg.norm(b - a) or 1.0)
    _pfeil(g, a, -richtung, h)
    _pfeil(g, b, richtung, h)
    yt = np.cross(n, u_text)
    ort = mitte_linie - u_text * (breite / 2 - 0.5 * h) + yt * 0.3 * h
    g.platzhalter.append(Platzhalter(ort, u_text.copy(), yt, breite - h, h, text=text))
    belegt.append(ecken)
    return g


def ergaenze(pmi: list, grafik: dict, modell, ansichten: list | None = None) -> dict:
    """Neue Grafiken (negative Callout-IDs) fuer PMI mit Flaechen, aber ohne vorhandene Darstellung."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    for p in pmi:  # semantisch gemachte Grafik der Datei: deren Callout ist die Darstellung
        if getattr(p, "callout", 0) in grafik:
            grafik[p.callout].pmi_ids.add(p.step_id)
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
    welle = _wellenachse(hi - lo)
    belegt: list[np.ndarray] = [np.array(g.grenzen()) for g in grafik.values() if g.erzeugt and g.grenzen()]
    neu = {}
    for i, p in enumerate(offen, 1):
        flaechen = [modell.flaechen[j] for j in sorted(p.flaechen) if j < len(modell.flaechen)]
        anker = _schwerpunkt(flaechen)
        if anker is None:
            continue
        if p.art == MASS and p.typ in ("Location_LinearDistance", "Size_Thickness"):
            g = _masslinie(p, flaechen, quader, mitte, belegt, h, i)
            if g is not None:
                neu[-i] = g
                continue
        ansicht = next((a for a in (ansichten or []) if p.step_id in a.pmi_ids and not a.eigen), None)
        richtung = _richtung_element(flaechen)
        drehteil = ansicht is None and welle is not None and richtung is not None and abs(richtung[welle]) > 0.9999
        x, y, n = ansicht_ebene(ansicht) if ansicht is not None else \
            modell_ebene(ACHSEN[1 if welle != 1 else 0] if drehteil else richtung)
        raus = anker - mitte
        raus = raus - n * (raus @ n)  # in der Ebene nach aussen
        if drehteil:  # quer zur Achse; Elemente auf der Achse abwechselnd ueber und unter das Teil
            raus = raus - ACHSEN[welle] * raus[welle]
            if np.linalg.norm(raus) < 1e-6 * diag:
                raus = y * (1.0 if i % 2 else -1.0)
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
        if p.art == BEZUG:
            g.linien.insert(0, np.array([ziel, andock]))
        else:  # Hinweislinie mit Pfeil am naechsten Punkt der Flaeche
            spitze = _naechster_punkt(flaechen, andock)
            spitze = anker if spitze is None else spitze
            g.linien.insert(0, np.array([spitze, andock]))
            if np.linalg.norm(andock - spitze) > h:
                _pfeil(g, spitze, spitze - andock, 0.8 * h)
        neu[-i] = g
    return neu


def _wellenachse(groesse) -> int | None:
    """Index der Modellachse, entlang der das Modell mindestens doppelt so lang ist wie quer (Drehteil), sonst None."""
    k = int(np.argmax(groesse))
    quer = max(groesse[j] for j in range(3) if j != k)
    return k if groesse[k] >= 2 * quer > 0 else None


def _platz(rahmen: _Rahmen, start, raus, x, y, quader, belegt, h) -> np.ndarray:
    """Linke untere Ecke: in der Schreibebene ausserhalb des Modellumrisses (projizierter Modellquader), ohne
    Ueberschneidung mit schon platzierten Rahmen. Geprueft wird in der Ebene, weil eine Ebene schraeg aus dem
    Quader herausfuehren kann und der Rahmen im Bild dann trotzdem vor dem Modell laege."""
    m = np.column_stack([x, y])
    modell = quader @ m
    andere = [b @ m for b in belegt]
    iso = ISO_BILD
    andere_iso = [b @ iso for b in belegt]  # Rahmen anderer Ebenen: im ueblichen Gesamtbild nicht uebereinander
    ursprung = start - x * (rahmen.breite / 2) - y * (rahmen.hoehe / 2)
    for _ in range(400):
        e = rahmen.ecken(ursprung, x, y)
        e2, ei = e @ m, e @ iso
        frei = not _ueberlappt(e2, modell, 0.5 * h) and all(not _ueberlappt(e2, b, 0.4 * h) for b in andere) and \
            all(not _ueberlappt(ei, b, 0.3 * h) for b in andere_iso) and \
            all(not _ueberlappt(e, b, 0.3 * h) for b in belegt)
        if frei:
            return ursprung
        ursprung = ursprung + raus * 0.8 * h
    return ursprung


def _iso_bild() -> np.ndarray:
    """Projektion ins isometrische Bild (Blick (-1,-1,-1), Z oben) als 3x2-Matrix."""
    blick = -np.ones(3) / np.sqrt(3)
    oben = np.array([0.0, 0.0, 1.0]) - blick * (-blick[2])
    oben /= np.linalg.norm(oben)
    return np.column_stack([np.cross(blick, oben), oben])


ISO_BILD = _iso_bild()
