"""Testvarianten von NIST CTC-01 fuer den Vergleich erzeugen (gezielte Textaenderungen der STEP-Datei).

Aufruf: pixi run python werkzeuge/testmodelle.py   -> tests/daten/varianten/
- ctc01_pmi.stp      Geometrie gleich, PMI geaendert (Toleranzwert, Abmass, Bezugssystem)
- ctc01_geo.stp      Bohrung Ø20 -> Ø21 (Zylinder, Kreise, Ecken, Naht), PMI gleich
- ctc01_geo_pmi.stp  wie ctc01_geo, dazu Mass 20 -> 21
- ctc01_pmi_andere.stp     Geometrie gleich, andere PMI: Ebenheit -> Geradheit, Bezugsreihenfolge A|C|B,
                           Position.2 0.75 -> 1.0
- ctc01_geo_klein.stp      minimale Geometrieaenderung: Bohrung Ø20 um 0.1 mm in X verschoben, PMI gleich
- ctc01_geo_klein_pmi_andere.stp  beides
- ctc01_scan.ply           "Scan": feines Netz mit Rauschen (sigma 5 um), gedreht und verschoben (zum Ausrichten)
- ctc01_scan_fehler.ply    wie ctc01_scan, dazu Fase 3 mm an einer Aussenkante, Delle 0.4 mm in der Oberseite und
                           Welligkeit 0.3 mm auf der Ebenheitsflaeche (Ebenheit 0.2 nicht eingehalten)
"""

from __future__ import annotations

import math
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
from programm.kern import p21  # noqa: E402

QUELLE = os.path.join(WURZEL, "tests", "daten", "nist_ctc_01_asme1_ap242-e1.stp")
ZIEL = os.path.join(WURZEL, "tests", "daten", "varianten")
BOHRUNG = (814, 815)  # Flaechen der Bohrung Ø20 (Halbschalen), Achse durch (30, -125, z) in Richtung z
ACHSE = (30.0, -125.0)
R_ALT, R_NEU = 10.0, 10.5


def _ersetze_entitaet(text: str, eid: int, neu: str) -> str:
    """Die Anweisung '#eid=...;' durch 'neu' ersetzen (eine Zeile)."""
    muster = re.compile(rf"^#{eid}=.*?;\s*$", re.M | re.S)
    treffer = muster.search(text)
    if not treffer:
        raise KeyError(eid)
    return text[:treffer.start()] + neu + "\n" + text[treffer.end():].lstrip("\n")


def _zahl(x: float) -> str:
    s = repr(float(x))
    return s if "." in s or "E" in s or "e" in s else s + "."


def _referenzen(d: p21.P21Datei, eid: int, gesehen: set[int]):
    if eid in gesehen:
        return
    gesehen.add(eid)
    e = d.entities[eid]
    for r in p21._refs_in(list(e.parts.values())):
        if d.entities.get(r) is not None and not d.entities[r].is_a("AXIS2_PLACEMENT_3D"):
            _referenzen(d, r, gesehen)


def bohrung_aufweiten(text: str) -> str:
    d = p21.lese_text(text)
    alle: set[int] = set()
    for f in BOHRUNG:
        _referenzen(d, f, alle)
    for eid in sorted(alle):
        e = d.entities[eid]
        if e.is_a("CYLINDRICAL_SURFACE") and abs(e.args()[2] - R_ALT) < 1e-9:
            text = _ersetze_entitaet(text, eid, f"#{eid}=CYLINDRICAL_SURFACE('',#{e.args()[1].id},{_zahl(R_NEU)});")
        elif e.is_a("CIRCLE") and abs(e.args()[2] - R_ALT) < 1e-9:
            text = _ersetze_entitaet(text, eid, f"#{eid}=CIRCLE('{e.args()[0]}',#{e.args()[1].id},{_zahl(R_NEU)});")
        elif e.is_a("CARTESIAN_POINT"):
            x, y, z = e.args()[1]
            dx, dy = x - ACHSE[0], y - ACHSE[1]
            r = math.hypot(dx, dy)
            if abs(r - R_ALT) < 1e-6:
                s = R_NEU / r
                text = _ersetze_entitaet(text, eid, f"#{eid}=CARTESIAN_POINT('{e.args()[0]}',("
                                         f"{_zahl(ACHSE[0] + dx * s)},{_zahl(ACHSE[1] + dy * s)},{_zahl(z)}));")
    return text


def _messwert(text: str, eid: int, neu: float) -> str:
    """Wert in einer (komplexen) MEASURE_WITH_UNIT-Entitaet ersetzen."""
    muster = re.compile(rf"(^#{eid}=.*?(?:LENGTH_MEASURE|POSITIVE_LENGTH_MEASURE)\()([-0-9.Ee+]+)(\))", re.M | re.S)
    t, n = muster.subn(lambda m: m.group(1) + _zahl(neu) + m.group(3), text, count=1)
    if n != 1:
        raise KeyError(eid)
    return t


def pmi_aendern(text: str) -> str:
    d = p21.lese_text(text)
    # 1. Position.1: Toleranzwert 0.75 -> 0.5
    pos = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == "Position.1")
    text = _messwert(text, pos.args("GEOMETRIC_TOLERANCE")[2].id, 0.5)
    # 2. Ø35 0/-0.2: unteres Abmass -0.2 -> -0.3
    tv = d.entities[58]  # TOLERANCE_VALUE(#72 unten, #71 oben) des Masses #120
    text = _messwert(text, tv.args()[0].id, -0.3)
    # 3. Flatness.1 0.2 -> 0.1
    flach = next(e for e in d.entities.values() if e.is_a("FLATNESS_TOLERANCE"))
    text = _messwert(text, flach.args()[2].id, 0.1)
    return text


def mass_20_auf_21(text: str) -> str:
    d = p21.lese_text(text)
    for dim in (122, 123):
        dcr = next(d.entities[r] for r in d.referrers()[dim]
                   if d.entities[r].is_a("DIMENSIONAL_CHARACTERISTIC_REPRESENTATION"))
        sdr = d.get(dcr.args()[1])
        for it in sdr.args()[1]:
            e = d.get(it)
            if e.is_a("REPRESENTATION_ITEM") and e.args("REPRESENTATION_ITEM")[0] == "nominal value":
                text = _messwert(text, it.id, 21.0)
    return text


def _punkte_von(d: p21.P21Datei, flaechen) -> set[int]:
    """Alle CARTESIAN_POINTs, die an den Flaechen haengen (auch ueber Achsensysteme)."""
    gesehen: set[int] = set()

    def lauf(eid):
        if eid in gesehen:
            return
        gesehen.add(eid)
        e = d.entities.get(eid)
        if e is None or e.is_a("DIRECTION"):
            return
        for ref in p21._refs_in(list(e.parts.values())):
            lauf(ref)
    for f in flaechen:
        lauf(f)
    return {i for i in gesehen if d.entities.get(i) is not None and d.entities[i].is_a("CARTESIAN_POINT")}


def bohrung_verschieben(text: str, dx: float = 0.1) -> str:
    """Bohrung Ø20 um dx in X verschieben: Punkte der Bohrungsflaechen und ihrer Kanten (nicht die der
    Nachbarflaechen-Geometrie)."""
    d = p21.lese_text(text)
    eigene = _punkte_von(d, BOHRUNG)
    andere_flaechen = [e.id for e in d.of_type("ADVANCED_FACE") if e.id not in BOHRUNG]
    fremd = _punkte_von(d, [d.entities[f].args()[2].id for f in andere_flaechen])  # Flaechengeometrie der anderen
    for eid in sorted(eigene - fremd):
        e = d.entities[eid]
        x, y, z = e.args()[1]
        text = _ersetze_entitaet(text, eid, f"#{eid}=CARTESIAN_POINT('{e.args()[0]}',({_zahl(x + dx)},{_zahl(y)},"
                                            f"{_zahl(z)}));")
    return text


def pmi_andere(text: str) -> str:
    """Andere PMI bei gleicher Geometrie: Toleranzart, Bezugsreihenfolge und ein Wert geaendert."""
    d = p21.lese_text(text)
    flach = next(e for e in d.entities.values() if e.is_a("FLATNESS_TOLERANCE"))
    zeile = re.compile(rf"^#{flach.id}=FLATNESS_TOLERANCE\(", re.M)
    text, n = zeile.subn(f"#{flach.id}=STRAIGHTNESS_TOLERANCE(", text)
    assert n == 1
    # Bezugssystem .2 (A|B|C): zweites und drittes Fach tauschen -> A|C|B
    system = next(e for e in d.of_type("DATUM_SYSTEM") if len(e.args()[4]) == 3)
    fach_b, fach_c = (d.entities[r.id] for r in system.args()[4][1:])
    for fach, bezug in ((fach_b, fach_c.args()[4]), (fach_c, fach_b.args()[4])):
        a = fach.args()
        text = _ersetze_entitaet(text, fach.id, f"#{fach.id}=DATUM_REFERENCE_COMPARTMENT('{a[0]}',$,#{a[2].id},"
                                                f".F.,#{bezug.id},$);")
    pos = next(e for e in d.of_type("GEOMETRIC_TOLERANCE") if e.args("GEOMETRIC_TOLERANCE")[0] == "Position.2")
    return _messwert(text, pos.args("GEOMETRIC_TOLERANCE")[2].id, 1.0)


# --- Netze ("Scans") ---

def _netz(form, abweichung: float = 0.03, laenge: float = 40.0):
    """Dreiecksnetz der Form wie ein Scan: neu vernetzt (feine Sehnen), Ebenen auf hoechstens 'laenge' unterteilt."""
    import numpy as np
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepTools import breptools
    from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    breptools.Clean(form)  # vorhandene (grobe) Vernetzung verwerfen
    BRepMesh_IncrementalMesh(form, abweichung, False, 0.3, True)
    punkte, dreiecke, n = [], [], 0
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        f = topods.Face(ex.Current())
        ex.Next()
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(f, loc)
        if tri is None:
            continue
        t = loc.Transformation()
        p = np.array([[q.X(), q.Y(), q.Z()] for q in (tri.Node(i).Transformed(t)
                                                     for i in range(1, tri.NbNodes() + 1))])
        ds = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)]) - 1
        if f.Orientation() == TopAbs_REVERSED:
            ds = ds[:, [0, 2, 1]]
        # wie ein Scanner: Punkte auch im Inneren der Flaechen. Ebenen beliebig teilen; Zylinder und Kegel nur
        # die langen (achsparallelen) Kanten - deren Mitten liegen exakt auf der Flaeche, Umfangssehnen nicht
        art = BRepAdaptor_Surface(f).GetType()
        if art == GeomAbs_Plane:
            p, ds = _teile_lange_kanten(p, ds, laenge)
        elif art == GeomAbs_Cone or (art == GeomAbs_Cylinder and BRepAdaptor_Surface(f).Cylinder().Radius() >= 3.0):
            # Mantellinien einmal halbieren: Punkte in halber Hoehe (Rundungen mit kleinem Radius nicht)
            p, ds = _teile_lange_kanten(p, ds, 6.0, runden=1)
        if art != GeomAbs_Plane:  # Knoten exakt auf die Flaeche (Sehnenmitten liegen sonst innen: Untermass)
            from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
            from OCC.Core.gp import gp_Pnt
            geom = BRep_Tool.Surface(f)
            for i, q in enumerate(p):
                pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*map(float, q)), geom)
                if pr.IsDone() and pr.NbPoints():
                    fuss = pr.NearestPoint()
                    p[i] = (fuss.X(), fuss.Y(), fuss.Z())
        punkte.append(p)
        dreiecke.append(ds + n)
        n += len(p)
    return np.vstack(punkte), np.vstack(dreiecke)


def _teile_lange_kanten(p, t, laenge: float, runden: int = 1000):
    """Laengste Kante halbieren, bis keine Kante laenger als 'laenge' ist (Anzahl waechst nur mit der Flaeche);
    runden begrenzt die Teilungen je Dreieck."""
    import numpy as np
    p, t = [tuple(x) for x in p], [tuple(x) for x in t]
    fertig, offen = [], t
    for _ in range(runden):
        if not offen:
            break
        neu = []
        for a, b, c in offen:
            ecken = (a, b, c)
            kanten = [(np.linalg.norm(np.subtract(p[ecken[i]], p[ecken[(i + 1) % 3]])), i) for i in range(3)]
            lg, i = max(kanten)
            if lg <= laenge:
                fertig.append((a, b, c))
                continue
            u, v, w = ecken[i], ecken[(i + 1) % 3], ecken[(i + 2) % 3]
            p.append(tuple((np.add(p[u], p[v]) / 2).tolist()))
            m = len(p) - 1
            neu += [(u, m, w), (m, v, w)]
        offen = neu
    return np.array(p), np.array(fertig + offen, dtype=int)


def _knotennormalen(p, t):
    import numpy as np
    fn = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    n = np.zeros_like(p)
    for k in range(3):
        np.add.at(n, t[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def schreibe_ply(pfad: str, p, t):
    """Binaeres PLY mit gemeinsamen Knoten (deutlich kleiner als STL)."""
    import numpy as np
    kopf = (f"ply\nformat binary_little_endian 1.0\ncomment 3DGmax Testdaten (aus NIST CTC-01)\n"
            f"element vertex {len(p)}\nproperty float x\nproperty float y\nproperty float z\n"
            f"element face {len(t)}\nproperty list uchar int vertex_indices\nend_header\n")
    flaechen = np.zeros(len(t), dtype=[("n", "u1"), ("i", "<i4", 3)])
    flaechen["n"], flaechen["i"] = 3, t
    with open(pfad, "wb") as f:
        f.write(kopf.encode("ascii"))
        f.write(np.asarray(p, "<f4").tobytes())
        f.write(flaechen.tobytes())


def schreibe_stl(pfad: str, p, t):
    """Binaeres STL."""
    import numpy as np
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    daten = np.zeros(len(t), dtype=[("n", "<f4", 3), ("a", "<f4", 3), ("b", "<f4", 3), ("c", "<f4", 3),
                                    ("attr", "<u2")])
    daten["n"], daten["a"], daten["b"], daten["c"] = n, a, b, c
    with open(pfad, "wb") as f:
        f.write(b"3DGmax Testdaten (aus NIST CTC-01)".ljust(80, b" "))
        f.write(np.uint32(len(t)).tobytes())
        f.write(daten.tobytes())


SCAN_LAGE = (2.5, (1.0, 1.0, 1.0), (12.0, -7.0, 3.0))  # Drehung (Grad) um Achse, Verschiebung (mm)


def _als_scan(p, t, rauschen: float = 0.005, zufall: int = 7):
    """Rauschen entlang der Knotennormalen, dann gedreht und verschoben (der Scan liegt nicht im CAD-System)."""
    import numpy as np
    rng = np.random.default_rng(zufall)
    p = p + _knotennormalen(p, t) * rng.normal(0.0, rauschen, (len(p), 1))
    winkel, achse, verschiebung = SCAN_LAGE
    k = np.asarray(achse) / np.linalg.norm(achse)
    w = np.radians(winkel)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    rot = np.eye(3) + np.sin(w) * kx + (1 - np.cos(w)) * kx @ kx
    return p @ rot.T + np.asarray(verschiebung)


def _ctc01_form():
    from programm.kern.laden import lade_step
    return lade_step(QUELLE).form


def scan_fehlerhaft(form):
    """Fase 3 mm an der laengsten senkrechten Aussenkante, Delle und Welligkeit (im CAD-System)."""
    import numpy as np
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeChamfer
    from OCC.Core.GCPnts import GCPnts_AbscissaPoint
    from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_Plane
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from programm.kern.pmi_lesen import lies_pmi
    from programm.kern.laden import lade_step
    modell = lade_step(QUELLE)
    kanten = []
    ex = TopExp_Explorer(form, TopAbs_EDGE)
    while ex.More():
        e = topods.Edge(ex.Current())
        ex.Next()
        c = BRepAdaptor_Curve(e)
        if c.GetType() == GeomAbs_Line and abs(c.Line().Direction().Z()) > 0.99:
            kanten.append((GCPnts_AbscissaPoint.Length(c), e))
    for _laenge, e in sorted(kanten, key=lambda k: -k[0]):  # laengste geeignete Kante (konvex, zwei Ebenen)
        try:
            fase = BRepFilletAPI_MakeChamfer(form)
            fase.Add(3.0, e)
            neu = fase.Shape()
        except RuntimeError:
            continue
        form = neu
        break
    p, t = _netz(form)
    # Ebenheitsflaeche aus der PMI des Originals: Welligkeit 0.3 mm (Spannweite) senkrecht zur Flaeche
    flach = next(x for x in lies_pmi(modell) if x.typ == "Flatness")
    fl = modell.flaechen[sorted(flach.flaechen)[0]]
    s = BRepAdaptor_Surface(fl)
    ebene = s.Plane()
    o = np.array([ebene.Location().X(), ebene.Location().Y(), ebene.Location().Z()])
    n = np.array([ebene.Axis().Direction().X(), ebene.Axis().Direction().Y(), ebene.Axis().Direction().Z()])
    auf = np.abs((p - o) @ n) < 1e-6
    x = (p - o) @ np.array([ebene.XAxis().Direction().X(), ebene.XAxis().Direction().Y(), ebene.XAxis().Direction().Z()])
    p[auf] += np.outer(0.15 * np.sin(x[auf] / 6.0), n)
    # Delle 0.4 mm in der hoechsten Ebene (Gaussglocke, Radius 8 mm) nahe der Mitte
    oben = np.isclose(p[:, 2], p[:, 2].max(), atol=1e-6)
    mitte = p[oben].mean(axis=0)
    r2 = np.sum((p[:, :2] - mitte[:2]) ** 2, axis=1)
    p[oben, 2] -= 0.4 * np.exp(-r2[oben] / (2 * 4.0 ** 2))
    del GeomAbs_Plane, TopAbs_FACE
    return p, t


def main():
    os.makedirs(ZIEL, exist_ok=True)
    with open(QUELLE, encoding="latin-1", newline="") as f:
        text = f.read()
    varianten = {"ctc01_pmi.stp": pmi_aendern(text), "ctc01_geo.stp": bohrung_aufweiten(text)}
    varianten["ctc01_geo_pmi.stp"] = mass_20_auf_21(varianten["ctc01_geo.stp"])
    varianten["ctc01_pmi_andere.stp"] = pmi_andere(text)
    varianten["ctc01_geo_klein.stp"] = bohrung_verschieben(text)
    varianten["ctc01_geo_klein_pmi_andere.stp"] = pmi_andere(varianten["ctc01_geo_klein.stp"])
    for name, inhalt in varianten.items():
        with open(os.path.join(ZIEL, name), "w", encoding="latin-1", newline="") as f:
            f.write(inhalt)
        print("geschrieben:", name)
    form = _ctc01_form()
    p, t = _netz(form)
    schreibe_ply(os.path.join(ZIEL, "ctc01_scan.ply"), _als_scan(p, t), t)
    p, t = scan_fehlerhaft(form)
    schreibe_ply(os.path.join(ZIEL, "ctc01_scan_fehler.ply"), _als_scan(p, t, zufall=8), t)
    print("geschrieben: ctc01_scan.ply, ctc01_scan_fehler.ply")


if __name__ == "__main__":
    main()
